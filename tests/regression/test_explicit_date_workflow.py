"""Original NlpPipeline wiring with scripted MODEL outputs, not live checkpoints.

Intent is held at the reported CLIMATE_TREND prediction. Only test doubles
supply model outputs; runtime trained predictors and model loading are unchanged.
Weather evidence is a real recorded ERA5 response. LLM responses are mocked.
"""
import json
from datetime import date
from urllib.parse import parse_qs, urlsplit
import httpx
import pytest
from fastapi.testclient import TestClient
from streamlit.testing.v1 import AppTest

from backend.core import load_settings
from backend.environment.provider import OpenMeteo
from backend.genai.client import LLMConfig, OpenAICompatibleClient
from backend.genai.context import ContextStore
from backend.genai.facts import compile_facts
from backend.genai.service import ExplanationService
from backend.nlp.context import ConversationManager
from backend.nlp.intent.predictor import IntentPrediction
from backend.nlp.language_detection import LanguageDetection
from backend.nlp.ner.model import PredictedEntity
from backend.nlp.normalization import EntityNormalizer
from backend.nlp.ontology import get_ontology
from backend.nlp.pipeline import NlpPipeline
from backend.nlp.query.enums import EntityType,Intent,Language
from backend.presentation.app import create_app
from streamlit_app.api_client import APIClient

QUESTION='Show temperature and rainfall in Gangtok from 2025-01-01 to 2025-01-07.'


class RecordedOutputs:
    def __init__(self, language='en', time_spans=()):
        self.language=Language(language)
        self.time_spans=time_spans
        self.calls=[]

    def detect(self,text,fallback=None):
        return LanguageDetection(code=self.language,confidence=.99,method='model')

    def predict_intent(self,texts):
        self.calls.append('intent')
        return [IntentPrediction(label=Intent.CLIMATE_TREND,confidence=.92,
            ranked=[(Intent.CLIMATE_TREND,.92)]+[(i,.01) for i in Intent if i!=Intent.CLIMATE_TREND])]

    def predict(self,texts):
        self.calls.append('ner')
        text=texts[0]
        spans=[]
        for phrase,kind in [('Gangtok',EntityType.LOCATION),('गंगटोक',EntityType.LOCATION),
                            ('गान्तोक',EntityType.LOCATION),('temperature',EntityType.ENV_VARIABLE),
                            ('rainfall',EntityType.ENV_VARIABLE),('तापमान',EntityType.ENV_VARIABLE),
                            ('तापक्रम',EntityType.ENV_VARIABLE),('बारिश',EntityType.ENV_VARIABLE),
                            ('वर्षा',EntityType.ENV_VARIABLE),
                            *[(value,EntityType.TIME) for value in self.time_spans]]:
            if phrase in text:
                start=text.index(phrase)
                spans.append(PredictedEntity(start,start+len(phrase),kind,phrase,.95))
        return [sorted(spans,key=lambda e:e.start)]


def pipeline(language='en', time_spans=()):
    settings=load_settings(); ontology=get_ontology()
    outputs=RecordedOutputs(language,time_spans)
    class Classifier:
        predict=staticmethod(outputs.predict_intent)
    result=NlpPipeline(settings,ontology,outputs,Classifier(),outputs,
        EntityNormalizer(ontology,settings.normalization),ConversationManager(settings.context))
    return result,outputs


class RecordingProvider(OpenMeteo):
    def __init__(self):
        super().__init__();self.calls=[]

    def retrieve(self,loc,start,end,today,source_mode):
        self.calls.append((loc,start,end))
        return super().retrieve(loc,start,end,today,source_mode)


def mock_llm():
    def generate(request):
        supplied=json.loads(json.loads(request.content)['messages'][1]['content'])
        fields=('fact_id','value','unit','location_ids','start','end','source_ids')
        claim={k:supplied['facts'][0][k] for k in fields}
        plan={'language':supplied['requested_language'],'answerable':True,'claims':[claim]}
        return httpx.Response(200,json={'choices':[{'finish_reason':'stop','message':{'content':json.dumps(plan)}}]})
    config=LLMConfig('openai_compatible','test-model','https://llm.example.test/v1','test-token-not-a-secret')
    return ExplanationService(OpenAICompatibleClient(config,httpx.MockTransport(generate)))


@pytest.mark.parametrize('time_spans',[(),('2025',),('2025-01',),('2025-01-01',),('2025-01-01','2025-01-07'),('2025-01-01 to 2025-01-07',)])
def test_original_pipeline_keeps_reported_model_intent_and_corrects_dates(time_spans):
    nlp,outputs=pipeline(time_spans=time_spans)
    result=nlp.analyze(QUESTION,session_id='s')
    assert outputs.calls==['intent','ner']
    assert result.status=='ok' and result.intent.label=='CLIMATE_TREND'
    assert result.structured_query.operation=='TREND'
    assert (result.structured_query.time_period.start,result.structured_query.time_period.end)==(date(2025,1,1),date(2025,1,7))
    assert 'explicit_time_from_text' in result.warnings
    follow=nlp.analyze('And rainfall?',session_id='s')
    assert follow.structured_query.time_period==result.structured_query.time_period
    assert 'time_period' in follow.structured_query.context_used


@pytest.mark.parametrize('language,text',[
    ('en',QUESTION),
    ('hi','गंगटोक में 2025-01-01 से 2025-01-07 तक तापमान और बारिश दिखाओ।'),
    ('ne','गान्तोकमा २०२५-०१-०१ देखि २०२५-०१-०७ सम्म तापक्रम र वर्षा देखाउनुहोस्।'),
])
def test_api_retrieval_summary_sources_and_genai_context_share_seven_days(language,text):
    nlp,_=pipeline(language); provider=RecordingProvider();store=ContextStore()
    with TestClient(create_app(pipeline=nlp,demo_enabled=False,provider=provider,
                    context_store=store,explanation_service=mock_llm())) as app:
        analysis=app.post('/nlp/analyze',json={'query':text,'session_id':'date-test'}).json()
        assert analysis['status']=='ok'
        bundle=app.post('/environment/session',json={'query':analysis['structured_query'],
            'session_id':'date-test','language':language,'source_mode':'snapshot'}).json()
        assert bundle['environment']['status']=='ok'
        weather=bundle['environment']['results'][0]
        assert weather['start']=='2025-01-01' and weather['end']=='2025-01-07'
        assert len(weather['daily'])==weather['summary']['days']==7
        assert weather['summary']['rainfall_total_mm']==pytest.approx(11.9)
        assert weather['summary']['rainfall_total_mm']!=5519.8
        assert provider.calls==[('loc:gangtok',date(2025,1,1),date(2025,1,7))]
        params=parse_qs(urlsplit(weather['source_url']).query)
        assert params['start_date']==['2025-01-01'] and params['end_date']==['2025-01-07']
        context=store.get(bundle['context_id'],'date-test')
        facts,_=compile_facts(context)
        assert all(f.start=='2025-01-01' and f.end=='2025-01-07' for f in facts)
        follow=app.post('/genai/explain',json={'context_id':bundle['context_id'],
            'session_id':'date-test','language':language,'question':'Explain these results'}).json()
        assert follow['status']=='ok' and '2025-01-07' in follow['text']
        assert '2025-12-31' not in follow['text']


@pytest.mark.parametrize('period',[
    '2025-01-07 to 2025-01-01','2025-02-30 to 2025-03-07',
    '01/02/2025 to 07/02/2025','2025-01 to 2025-02',
])
def test_invalid_dates_use_existing_422_contract_without_retrieval_or_context_pollution(period):
    nlp,_=pipeline()
    with TestClient(create_app(pipeline=nlp,demo_enabled=False)) as app:
        good=app.post('/nlp/analyze',json={'query':QUESTION,'session_id':'s'}).json()
        bad=app.post('/nlp/analyze',json={'query':'Show rainfall in Gangtok from '+period,'session_id':'s'})
        assert bad.status_code==422 and bad.json()['detail']['code']=='invalid_time_period'
        follow=app.post('/nlp/analyze',json={'query':'And rainfall?','session_id':'s'}).json()
        assert follow['structured_query']['time_period']==good['structured_query']['time_period']


@pytest.mark.parametrize('period',['1939-01-01 to 1939-01-07','2025-01-01 to 2026-01-02','2099-01-01 to 2099-01-07'])
def test_retrieval_limits_are_validated_without_calling_provider(period):
    nlp,_=pipeline();provider=RecordingProvider()
    with TestClient(create_app(pipeline=nlp,demo_enabled=False,provider=provider)) as app:
        analysis=app.post('/nlp/analyze',json={'query':'Show rainfall in Gangtok from '+period}).json()
        result=app.post('/environment/query',json={'query':analysis['structured_query'],'source_mode':'snapshot'}).json()
        assert result['status']=='needs_clarification' and not result['results']
        assert not provider.calls


def test_streamlit_charts_and_cards_use_corrected_production_query(monkeypatch):
    nlp,_=pipeline(time_spans=('2025',));provider=RecordingProvider()
    with TestClient(create_app(pipeline=nlp,demo_enabled=False,provider=provider,explanation_service=mock_llm())) as backend:
        def request(self,method,path,**kwargs):
            response=backend.request(method,path,**kwargs);response.raise_for_status();return response.json()
        monkeypatch.setattr(APIClient,'request',request)
        app=AppTest.from_file('streamlit_app/app.py',default_timeout=30).run()
        next(w for w in app.selectbox if w.label=='Environmental data').select('Recorded snapshot · 1–7 Jan 2025').run()
        next(w for w in app.button if w.label=='Analyze and retrieve').click().run()
        assert not app.exception and not app.error
        assert next(w for w in app.selectbox if w.label=='NLP mode').value=='Trained NLP'
        assert next(w for w in app.metric if w.label=='Rainfall sum').value=='11.9 mm'
        assert len(app.get('arrow_vega_lite_chart'))==2
        frame=next(w.value for w in app.dataframe if len(w.value)==7)
        assert str(frame.index.min().date())=='2025-01-01' and str(frame.index.max().date())=='2025-01-07'
        assert provider.calls==[('loc:gangtok',date(2025,1,1),date(2025,1,7))]


@pytest.mark.parametrize('period,allowed',[
    ('2024-01-01 to 2024-12-31',True),  # leap-year range: exactly 366 inclusive days
    ('2024-01-01 to 2025-01-01',False),
])
def test_inclusive_retrieval_limit_is_preserved(period,allowed):
    from backend.environment.provider import DataUnavailable
    class Capture:
        def __init__(self): self.calls=[]
        def retrieve(self,loc,start,end,today,source_mode):
            self.calls.append((start,end))
            raise DataUnavailable('Intentional test boundary capture; no network call.')
    provider=Capture();nlp,_=pipeline()
    with TestClient(create_app(pipeline=nlp,demo_enabled=False,provider=provider)) as app:
        analysis=app.post('/nlp/analyze',json={'query':'Show rainfall in Gangtok from '+period}).json()
        result=app.post('/environment/query',json={'query':analysis['structured_query'],'source_mode':'live'}).json()
        assert bool(provider.calls)==allowed
        assert result['status']==('unavailable' if allowed else 'needs_clarification')
