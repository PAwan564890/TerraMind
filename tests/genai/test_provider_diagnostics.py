"""Provider failures are simulated; no live Groq credentials or model calls."""
import json
import logging
from dataclasses import replace
from datetime import datetime, timezone
from email.utils import format_datetime
import httpx
import pytest

from backend.genai.client import LLMConfig,OpenAICompatibleClient,ProviderError,retry_guidance
from backend.genai.service import ExplanationService
from backend.genai.context import ContextStore
from backend.environment.service import retrieve_query
from backend.presentation.demo import DemoAnalyzer
from backend.presentation.app import create_app
from fastapi.testclient import TestClient
from scripts.verify_genai import VerificationPacer,pacing_seconds

SECRET='test-private-provider-credential'
PRIVATE='test-private-question-and-generated-payload'
CONFIG=LLMConfig('openai_compatible','mock-model','https://provider.example.test/v1',SECRET)


def completion(content='{}',finish='stop',**extra):
    return {'choices':[{'finish_reason':finish,'message':{'content':content,**extra}}]}


class Harness:
    def __init__(self,handler,config=CONFIG):
        self.calls=[];self.sleeps=[];self.now=0
        def send(request):
            self.calls.append(request)
            return handler(request,len(self.calls))
        def sleep(seconds):self.sleeps.append(seconds);self.now+=seconds
        self.client=OpenAICompatibleClient(config,httpx.MockTransport(send),sleep=sleep,
            clock=lambda:self.now,wall_clock=lambda:1700000000,jitter=lambda:0)
    def generate(self):return self.client.generate(PRIVATE,{'question':PRIVATE})


@pytest.mark.parametrize('status,category,attempts',[
    (429,'rate_limit',2),(401,'authentication',1),(403,'authentication',1),
    (500,'http_server_error',2),(502,'http_server_error',2),(503,'http_server_error',2),
    (504,'http_server_error',2),(501,'http_server_error',1),
    (400,'provider_rejection',1),(422,'provider_rejection',1),(408,'timeout',1),
])
def test_http_failures_are_distinct_sanitized_and_bounded(status,category,attempts,caplog):
    caplog.set_level(logging.WARNING,logger='terramind.genai')
    h=Harness(lambda r,n:httpx.Response(status,json={'error':{'message':SECRET+PRIVATE}},
        headers={'x-request-id':SECRET,'retry-after':SECRET}))
    with pytest.raises(ProviderError) as error:h.generate()
    assert error.value.code==category and error.value.status==status
    assert error.value.attempts==attempts and len(h.calls)==attempts
    assert len(h.sleeps)==attempts-1
    assert f'category={category}' in caplog.text and f'http_status={status}' in caplog.text
    assert 'ref=' in str(error.value)
    assert SECRET not in caplog.text+str(error.value)
    assert PRIVATE not in caplog.text+str(error.value)
    assert 'Authorization' not in caplog.text and 'Bearer ' not in caplog.text


@pytest.mark.parametrize('status',[429,503])
def test_retry_after_is_respected_then_real_response_is_returned(status,caplog):
    h=Harness(lambda r,n:httpx.Response(status,headers={'Retry-After':'2'}) if n==1 else httpx.Response(200,json=completion('valid content')))
    assert h.generate()=='valid content'
    assert h.sleeps==[2.0] and len(h.calls)==2
    assert 'retry=True' in caplog.text


def test_retry_after_http_date():
    stamp=format_datetime(datetime.fromtimestamp(1700000003,timezone.utc),usegmt=True)
    assert retry_guidance(httpx.Headers({'Retry-After':stamp}),1700000000)==3


@pytest.mark.parametrize('raw',['NaN','inf','-1','secret-not-a-delay'])
def test_invalid_retry_after_falls_back_without_logging_header(raw,caplog):
    h=Harness(lambda r,n:httpx.Response(429,headers={'Retry-After':raw}) if n==1 else httpx.Response(200,json=completion()))
    assert h.generate()=='{}' and h.sleeps==[.5]
    assert raw not in caplog.text


def test_long_retry_after_stops_instead_of_retrying_early():
    h=Harness(lambda r,n:httpx.Response(429,headers={'Retry-After':'120'}))
    with pytest.raises(ProviderError) as error:h.generate()
    assert error.value.retry_after==120 and error.value.code=='rate_limit'
    assert not h.sleeps and len(h.calls)==1


def test_groq_token_reset_uses_only_exhausted_quota():
    headers={'x-ratelimit-remaining-requests':'100','x-ratelimit-reset-requests':'2m59.56s',
             'x-ratelimit-remaining-tokens':'0','x-ratelimit-reset-tokens':'7.66s'}
    h=Harness(lambda r,n:httpx.Response(429,headers=headers) if n==1 else httpx.Response(200,json=completion()),replace(CONFIG,retry_max_wait=10))
    assert h.generate()=='{}' and h.sleeps==[7.66]
    headers['x-ratelimit-remaining-requests']='0'
    assert retry_guidance(httpx.Headers(headers),1700000000)==179.56
    headers['Retry-After']='3'
    assert retry_guidance(httpx.Headers(headers),1700000000)==3


def test_nonexhausted_reset_is_not_used_as_retry_guidance():
    assert retry_guidance(httpx.Headers({'x-ratelimit-remaining-tokens':'5','x-ratelimit-reset-tokens':'7s'}),1700000000) is None


def test_attempt_cap_and_exponential_backoff():
    h=Harness(lambda r,n:httpx.Response(503),replace(CONFIG,max_attempts=3))
    with pytest.raises(ProviderError) as error:h.generate()
    assert len(h.calls)==3 and h.sleeps==[.5,1]
    assert error.value.attempts==3


def test_retries_can_be_disabled():
    h=Harness(lambda r,n:httpx.Response(429),replace(CONFIG,max_attempts=1))
    with pytest.raises(ProviderError):h.generate()
    assert len(h.calls)==1 and h.sleeps==[]


def test_retry_admission_budget_is_enforced():
    def handler(request,n):
        h.now+=12
        return httpx.Response(503,headers={'Retry-After':'15'})
    h=Harness(handler,replace(CONFIG,max_attempts=3,retry_max_wait=15))
    with pytest.raises(ProviderError):h.generate()
    assert len(h.calls)==2 and h.sleeps==[15]
    assert h.calls[1].extensions['timeout']['read']==8


@pytest.mark.parametrize('kind,category,retry',[
    (httpx.ConnectError,'transport',True),(httpx.ConnectTimeout,'timeout',True),
    (httpx.ReadTimeout,'timeout',False),(httpx.WriteTimeout,'timeout',False),
    (httpx.ReadError,'transport',False),(httpx.RemoteProtocolError,'transport',False),
    (httpx.DecodingError,'malformed_response',False),
])
def test_transport_and_timeout_categories_without_duplicate_ambiguous_requests(kind,category,retry):
    def handler(request,n):
        if n==1:raise kind(SECRET+PRIVATE,request=request)
        return httpx.Response(200,json=completion())
    h=Harness(handler)
    if retry:
        assert h.generate()=='{}' and h.sleeps==[.5] and len(h.calls)==2
    else:
        with pytest.raises(ProviderError) as error:h.generate()
        assert error.value.code==category and SECRET not in str(error.value)
        assert len(h.calls)==1 and not h.sleeps


@pytest.mark.parametrize('payload', [None,[],42,{}, {'choices':[]}, {'choices':[None]},
    {'choices':[{'finish_reason':'stop','message':None}]},completion(content=None),completion(content=['wrong']),
])
def test_malformed_response_shape_never_retries_or_succeeds(payload):
    h=Harness(lambda r,n:httpx.Response(200,content=json.dumps(payload)))
    with pytest.raises(ProviderError) as error:h.generate()
    assert error.value.code=='malformed_response' and len(h.calls)==1 and not h.sleeps


def test_malformed_outer_json_and_oversized_body():
    for body in [b'not-json',b'x'*70000]:
        h=Harness(lambda r,n:httpx.Response(200,content=body))
        with pytest.raises(ProviderError) as error:h.generate()
        assert error.value.code=='malformed_response' and len(h.calls)==1


@pytest.mark.parametrize('payload,category',[
    (completion(finish='length'),'incomplete_response'),
    (completion(finish='content_filter'),'provider_rejection'),
    (completion(refusal=PRIVATE),'provider_rejection'),
    (completion(finish='tool_calls'),'provider_rejection'),
])
def test_provider_rejection_and_truncation_are_not_retried(payload,category,caplog):
    h=Harness(lambda r,n:httpx.Response(200,json=payload))
    with pytest.raises(ProviderError) as error:h.generate()
    assert error.value.code==category and len(h.calls)==1
    assert PRIVATE not in str(error.value)+caplog.text


def test_provider_json_generation_failure_has_specific_safe_category(caplog):
    h=Harness(lambda r,n:httpx.Response(400,json={'error':{'code':'json_validate_failed',
        'message':SECRET,'failed_generation':PRIVATE}}))
    with pytest.raises(ProviderError) as error:h.generate()
    assert error.value.code=='structured_output' and len(h.calls)==1
    assert 'HTTP=400' in str(error.value)
    assert SECRET not in caplog.text+str(error.value) and PRIVATE not in caplog.text+str(error.value)


def context_and_query():
    q=DemoAnalyzer().analyze('Show temperature and rainfall in Gangtok from 2025-01-01 to 2025-01-07.').structured_query
    env=retrieve_query(q,source_mode='snapshot')
    store=ContextStore();token=store.save('s',env,'snapshot')
    return store.get(token,'s'),q


@pytest.mark.parametrize('failure,category,status',[
    ('json','structured_output','rejected'),('schema','structured_output','rejected'),
    ('number','grounding_validation','rejected'),('decline','provider_rejection','unavailable')])
def test_service_logs_validation_and_refusal_without_raw_content_or_retry(failure,category,status,caplog):
    context,_=context_and_query()
    def handler(request,n):
        data=json.loads(json.loads(request.content)['messages'][1]['content'])
        plan=data['response_example']
        if failure=='json': content=PRIVATE+' not JSON'
        else:
            if failure=='schema':plan['secret-prose']=PRIVATE
            if failure=='number':plan['claims'][0]['value']='999.00'
            if failure=='decline':plan.update(answerable=False,claims=[])
            content=json.dumps(plan)
        return httpx.Response(200,json=completion(content))
    h=Harness(handler)
    result=ExplanationService(h.client).explain(context,'en')
    assert result.status==status and result.text is None
    assert len(h.calls)==1 and not h.sleeps
    assert f'category={category}' in caplog.text and f'code={category}' in result.message
    assert PRIVATE not in caplog.text+result.message and SECRET not in caplog.text+result.message


def test_exhausted_provider_retries_leave_environmental_data_available():
    _,query=context_and_query();h=Harness(lambda r,n:httpx.Response(503))
    with TestClient(create_app(demo_enabled=False,explanation_service=ExplanationService(h.client))) as client:
        result=client.post('/environment/session',json={'query':query.model_dump(mode='json'),
            'source_mode':'snapshot','session_id':'s','language':'en'}).json()
        assert result['environment']['status']=='ok'
        assert result['environment']['results'][0]['summary']['days']==7
        assert result['explanation']['status']=='unavailable' and result['explanation']['text'] is None
        assert 'code=http_server_error' in result['explanation']['message'] and len(h.calls)==2


def test_unsupported_question_never_enters_provider_retry_loop():
    context,_=context_and_query();h=Harness(lambda r,n:pytest.fail('unsupported question contacted provider'))
    result=ExplanationService(h.client).explain(context,'en','Explain the humidity')
    assert result.status=='unsupported' and not h.calls and not h.sleeps


@pytest.mark.parametrize('value',['-1','61','nan','inf','not-a-number'])
def test_verification_pacing_rejects_unbounded_values(value):
    import argparse
    with pytest.raises(argparse.ArgumentTypeError):pacing_seconds(value)


def test_verification_pacer_waits_only_for_remaining_interval():
    now=[0];delays=[]
    def sleep(seconds):delays.append(seconds);now[0]+=seconds
    pacer=VerificationPacer(10,clock=lambda:now[0],sleep=sleep)
    pacer.wait();assert not delays
    now[0]=3;pacer.wait();assert delays==[7]
    now[0]=25;pacer.wait();assert delays==[7]
    no_delay=VerificationPacer(0,clock=lambda:now[0],sleep=sleep)
    no_delay.wait();no_delay.wait();assert delays==[7]


def test_retry_environment_bounds(monkeypatch):
    monkeypatch.setenv('TERRAMIND_LLM_MAX_ATTEMPTS','3')
    monkeypatch.setenv('TERRAMIND_LLM_RETRY_MAX_WAIT_SECONDS','12')
    assert LLMConfig.from_env().max_attempts==3 and LLMConfig.from_env().retry_max_wait==12
    monkeypatch.setenv('TERRAMIND_LLM_MAX_ATTEMPTS','99')
    monkeypatch.setenv('TERRAMIND_LLM_RETRY_MAX_WAIT_SECONDS','inf')
    assert LLMConfig.from_env().max_attempts==2 and LLMConfig.from_env().retry_max_wait==5


def test_provider_transport_debug_logs_cannot_expose_url_or_headers(caplog):
    caplog.set_level(logging.DEBUG)
    config=replace(CONFIG,base_url='https://provider.example.test/'+PRIVATE)
    def handler(request,n):
        # Simulate dependency debug logging while handling the request.
        logging.getLogger('httpcore.http11').debug('Authorization: %s private=%s',SECRET,PRIVATE)
        return httpx.Response(401)
    h=Harness(handler,config)
    with pytest.raises(ProviderError):h.generate()
    assert SECRET not in caplog.text and PRIVATE not in caplog.text
    assert 'category=authentication' in caplog.text
    logging.getLogger('httpx').info('outside-provider-call-is-visible')
    assert 'outside-provider-call-is-visible' in caplog.text
