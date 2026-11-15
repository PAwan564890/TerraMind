"""FastAPI + dashboard HTTP client + real snapshot data; LLM provider is mocked."""
import json
import httpx
import pytest
from fastapi.testclient import TestClient
from backend.genai.client import LLMConfig, OpenAICompatibleClient
from backend.genai.context import ContextStore
from backend.genai.service import ExplanationService
from backend.presentation.app import create_app
from backend.presentation.demo import DemoAnalyzer
from streamlit_app.api_client import APIClient

QUERY='Show temperature and rainfall in Gangtok from 2025-01-01 to 2025-01-07.'


def llm(status=200):
    def respond(request):
        supplied=json.loads(json.loads(request.content)['messages'][1]['content'])
        fields=('fact_id','value','unit','location_ids','start','end','source_ids')
        plan={'language':supplied['requested_language'],'answerable':True,
              'claims':[{k:supplied['facts'][0][k] for k in fields}]}
        return httpx.Response(status,json={'choices':[{'finish_reason':'stop','message':{'content':json.dumps(plan)}}]})
    return ExplanationService(OpenAICompatibleClient(LLMConfig('openai_compatible','mock-model','https://llm.example.test/v1','test-token-not-a-secret'),httpx.MockTransport(respond)))


def body():
    return {'query':DemoAnalyzer().analyze(QUERY).structured_query.model_dump(mode='json'),
            'source_mode':'snapshot','session_id':'browser-session','language':'en'}


@pytest.mark.parametrize('language',['en','hi','ne'])
def test_api_full_result_and_contextual_followup(language):
    with TestClient(create_app(demo_enabled=True,explanation_service=llm())) as client:
        payload=body();payload['language']=language
        response=client.post('/environment/session',json=payload)
        assert response.status_code==200
        bundle=response.json()
        assert bundle['environment']['status']=='ok'
        assert bundle['explanation']['status']=='ok'
        assert len(bundle['environment']['results'][0]['daily'])==7
        follow={'session_id':'browser-session','context_id':bundle['context_id'],
                'language':language,'question':'Explain these temperature results'}
        answer=client.post('/genai/explain',json=follow).json()
        assert answer['status']=='ok' and answer['language']==language
        follow['session_id']='different-browser'
        denied=client.post('/genai/explain',json=follow).json()
        assert denied['status']=='no_context' and denied['text'] is None
        assert client.post('/nlp/analyze',json={'query':QUERY}).status_code==503
        assert client.post('/demo/analyze',json={'query':QUERY}).json()['warnings'][0].startswith('DEMO')
        original=client.post('/environment/query',json={k:v for k,v in payload.items() if k in ('query','source_mode')}).json()
        assert set(original)=={'status','message','query','results','errors'}


@pytest.mark.parametrize('status',[401,429,503])
def test_provider_failure_never_blocks_environmental_results(status):
    with TestClient(create_app(demo_enabled=True,explanation_service=llm(status))) as client:
        bundle=client.post('/environment/session',json=body()).json()
        assert bundle['explanation']['status']=='unavailable'
        assert bundle['environment']['status']=='ok'
        assert bundle['environment']['results'][0]['summary']['temperature_mean_c'] is not None
        assert bundle['context_id']


def test_no_credentials_still_returns_real_environment(monkeypatch):
    monkeypatch.delenv('TERRAMIND_LLM_API_KEY',raising=False)
    monkeypatch.delenv('OPENAI_API_KEY',raising=False)
    monkeypatch.setenv('TERRAMIND_LLM_PROVIDER','disabled')
    with TestClient(create_app(demo_enabled=True)) as client:
        assert client.get('/system').json()['genai']['configured'] is False
        bundle=client.post('/environment/session',json=body()).json()
        assert bundle['explanation']['status']=='disabled'
        assert bundle['explanation']['text'] is None
        assert bundle['environment']['status']=='ok'
        assert 'snapshot' in ' '.join(bundle['environment']['results'][0]['warnings']).lower()
        assert 'api_key' not in client.get('/system').text


def test_expired_context_and_client_result_injection_are_refused():
    now=[0]
    store=ContextStore(ttl_seconds=1,clock=lambda:now[0])
    with TestClient(create_app(demo_enabled=True,explanation_service=llm(),context_store=store)) as client:
        bundle=client.post('/environment/session',json=body()).json()
        follow={'session_id':'browser-session','context_id':bundle['context_id'], 'question':'Explain rainfall','language':'en'}
        now[0]=1
        assert client.post('/genai/explain',json=follow).json()['status']=='no_context'
        follow['environment']={'fake':999}
        assert client.post('/genai/explain',json=follow).status_code==422


def test_unexpected_generation_bug_is_isolated():
    s=llm()
    def broken(*args): raise RuntimeError('private details')
    s.explain=broken
    with TestClient(create_app(demo_enabled=True,explanation_service=s)) as client:
        result=client.post('/environment/session',json=body()).json()
        assert result['environment']['status']=='ok'
        assert result['explanation']['status']=='unavailable'
        assert 'private' not in json.dumps(result)


def test_dashboard_client_http_workflow(monkeypatch):
    with TestClient(create_app(demo_enabled=True,explanation_service=llm())) as client:
        # Exercise real HTTP client serialization against ASGI route behavior;
        # only transport is bridged here, not the backend/business logic.
        def bridge(request):
            r=client.request(request.method,request.url.path,content=request.content,headers={'content-type':'application/json'})
            return httpx.Response(r.status_code,json=r.json())
        api=APIClient('http://backend',transport=httpx.MockTransport(bridge))
        result=api.run(QUERY,'browser-session','demo','snapshot','ne')
        assert result['environment']['status']=='ok'
        assert result['explanation']['status']=='ok' and result['explanation']['language']=='ne'
        assert api.explain('browser-session',result['context_id'],'Explain the temperature','hi')['status']=='ok'
