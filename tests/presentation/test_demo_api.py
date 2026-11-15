import pytest
from fastapi.testclient import TestClient
from backend.presentation.app import create_app
from backend.presentation.demo import DemoAnalyzer
from streamlit_app.api_client import APIClient, APIError
from streamlit_app.config import EXAMPLES


@pytest.mark.parametrize('text,language', [
    (EXAMPLES[0], 'en'), (EXAMPLES[1],'hi'),(EXAMPLES[2],'ne'),
    ('गंगटोक में आज तापमान कितना है?', 'hi'),
    ('गान्तोकमा अहिले तापक्रम कति छ?', 'ne'),
])
def test_native_language_examples_retain_existing_contract(text,language):
    r = DemoAnalyzer().analyze(text)
    assert r.status == 'ok'
    assert r.language.code == language
    assert r.language.confidence == r.intent.confidence == 0
    assert r.structured_query.locations[0].id == 'loc:gangtok'
    assert 'TEMPERATURE' in r.structured_query.variables
    assert any('DEMO' in w for w in r.warnings)
    assert all(text[e.start:e.end] == e.text for e in r.entities)


def test_context_uses_existing_resolver():
    p=DemoAnalyzer()
    p.analyze(EXAMPLES[0],session_id='test')
    r=p.analyze('And rainfall?',session_id='test')
    assert r.status == 'ok'
    assert 'locations' in r.structured_query.context_used
    assert 'time_period' in r.structured_query.context_used
    assert r.structured_query.variables == ['PRECIPITATION']


@pytest.mark.parametrize('text',['Show temperature in Gangtok.',
    'Compare rainfall in Gangtok and Paris today.',
    'Show rainfall in Gangtok from 2025-02-30 to 2025-03-01.',
    'Show rainfall in Gangtok from 2025-03-02 to 2025-03-01.',
    'Show rainfall in Gangtok on 2025-03-01.',
    'Predict landslide risk in Gangtok today.'])
def test_unsupported_demo_asks(text):
    assert DemoAnalyzer().analyze(text).status == 'needs_clarification'


def test_out_of_domain():
    r=DemoAnalyzer().analyze('Tell me a joke.')
    assert r.status == 'out_of_domain'
    assert r.structured_query is None


def test_demo_is_opt_in_and_never_substitutes_production():
    with TestClient(create_app(demo_enabled=False)) as client:
        assert client.get('/health').json()['models_loaded'] is False
        assert client.post('/demo/analyze',json={'query':EXAMPLES[0]}).status_code == 404
        assert client.post('/nlp/analyze',json={'query':EXAMPLES[0]}).status_code == 503
    with TestClient(create_app(demo_enabled=True)) as client:
        assert client.post('/demo/analyze',json={'query':EXAMPLES[0]}).json()['status'] == 'ok'
        assert client.post('/nlp/analyze',json={'query':EXAMPLES[0]}).status_code == 503


def test_full_api_workflow_with_recorded_real_data():
    with TestClient(create_app(demo_enabled=True)) as client:
        for text in [EXAMPLES[0],
            'गंगटोक में 2025-01-01 से 2025-01-07 तक तापमान और बारिश दिखाओ।',
            'गान्तोकमा 2025-01-01 देखि 2025-01-07 सम्म तापक्रम र वर्षा देखाउनुहोस्।']:
            analysis=client.post('/demo/analyze',json={'query':text}).json()
            assert analysis['status'] == 'ok'
            data=client.post('/environment/query',json={'query':analysis['structured_query'],'source_mode':'snapshot'})
            assert data.status_code == 200
            assert data.json()['status'] == 'ok'
            assert len(data.json()['results'][0]['daily']) == 7
        assert client.post('/environment/query',json={'query':{},'source_mode':'bogus'}).status_code == 422
        assert client.post('/demo/analyze',json={'query':'???'}).status_code == 422


def test_dashboard_client_stops_on_clarification_and_surfaces_failures():
    import httpx
    calls=[]
    def answer(request):
        calls.append(request.url.path)
        return httpx.Response(200,json={'status':'needs_clarification','structured_query':None})
    client=APIClient('http://backend',transport=httpx.MockTransport(answer))
    assert client.run('question','session','demo','live')['environment'] is None
    assert calls == ['/demo/analyze']
    client=APIClient('http://backend',transport=httpx.MockTransport(lambda r:httpx.Response(503)))
    with pytest.raises(APIError, match='Trained NLP'):
        client.run('q','s','trained','live')
