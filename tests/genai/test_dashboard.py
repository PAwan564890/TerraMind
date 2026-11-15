"""Streamlit integration uses FastAPI TestClient; external LLM is mocked."""
import json
import httpx
import pytest
from fastapi.testclient import TestClient
from streamlit.testing.v1 import AppTest
from backend.genai.client import LLMConfig, OpenAICompatibleClient
from backend.genai.service import ExplanationService
from backend.presentation.app import create_app
from streamlit_app.api_client import APIClient


@pytest.mark.parametrize('mode',['success','provider_failure','hallucination','disabled'])
def test_dashboard_renders_genai_separately_without_hiding_evidence(monkeypatch,mode):
    def provider(request):
        if mode=='provider_failure': return httpx.Response(503)
        supplied=json.loads(json.loads(request.content)['messages'][1]['content'])
        fact=(next(f for f in supplied['facts'] if f['metric']=='rainfall_total_mm')
              if 'वर्षा' in supplied['question'] else supplied['facts'][0])
        claim={k:fact[k] for k in ('fact_id','value','unit','location_ids','start','end','source_ids')}
        if mode=='hallucination': claim['value']='999.00'
        plan={'language':supplied['requested_language'],'answerable':True,'claims':[claim]}
        return httpx.Response(200,json={'choices':[{'finish_reason':'stop','message':{'content':json.dumps(plan)}}]})
    config=LLMConfig() if mode=='disabled' else LLMConfig('openai_compatible','mock-model','https://llm.example.test/v1','test-token-not-a-secret')
    service=ExplanationService(OpenAICompatibleClient(config,httpx.MockTransport(provider)))
    with TestClient(create_app(demo_enabled=True,explanation_service=service)) as backend:
        def request(self,method,path,**kwargs):
            r=backend.request(method,path,**kwargs)
            r.raise_for_status()
            return r.json()
        monkeypatch.setattr(APIClient,'request',request)
        app=AppTest.from_file('streamlit_app/app.py',default_timeout=30).run()
        next(x for x in app.selectbox if x.label=='Environmental data').select('Recorded snapshot · 1–7 Jan 2025').run()
        next(x for x in app.selectbox if x.label=='Explanation language').select('Hindi').run()
        next(x for x in app.button if x.label=='Analyze and retrieve').click().run()
        assert not app.exception and not app.error
        assert len(app.metric)==7 and len(app.get('arrow_vega_lite_chart'))==2
        assert any(x.value=='AI-generated explanation' for x in app.header)
        assert any('RULE DEMONSTRATION' in x.value for x in app.warning)
        if mode=='success':
            assert any('औसत दैनिक तापमान' in x.value for x in app.text)
            app.text_input[0].input('वर्षा का सारांश समझाएँ').run()
            next(x for x in app.button if x.label=='Explain stored results').click().run()
            assert not app.exception and not app.error
            assert any('Contextual follow-up' in x.value for x in app.subheader)
            assert any('वर्षा का योग: 11.90 mm' in x.value for x in app.text)
        else:
            assert not app.text
            messages=' '.join(x.value for x in app.info)
            assert ('failed grounding' in messages if mode=='hallucination' else
                    'not configured' in messages if mode=='disabled' else 'provider failed' in messages)
            assert '999' not in messages
