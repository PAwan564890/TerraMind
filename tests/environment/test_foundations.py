"""Synthetic edge cases and real recorded provider/geocoding fixtures; no live NLP/LLM."""
import copy,json
from datetime import date
from pathlib import Path
import httpx,pytest
from fastapi.testclient import TestClient
from backend.environment.registry import TOWNS,active_towns,Town
from backend.environment.provider import OpenMeteo
from backend.environment.insights import temporal,comparisons
from backend.environment.transport import get_json,RetrievalFailure
from backend.environment.measurements import retrieve_measurements
from backend.presentation.demo import DemoAnalyzer
from backend.presentation.app import create_app
from backend.genai.context import ContextStore
from backend.genai.facts import compile_facts
from backend.genai.questions import select_facts
from backend.genai.schema import Claim
from backend.nlp.query.enums import Variable

FIXTURES=Path(__file__).parents[1]/'fixtures'

def query(variable='HUMIDITY'):
 q=DemoAnalyzer().analyze('Show temperature in Gangtok from 2025-01-01 to 2025-01-07.').structured_query
 return q.model_copy(update={'variables':[Variable(variable)]})

def weather(town='loc:gangtok'):
 return OpenMeteo().retrieve(town,date(2025,1,1),date(2025,1,7),date(2026,11,16),'snapshot')

@pytest.mark.parametrize('town',TOWNS,ids=lambda t:t.id)
def test_registry_coordinates_are_traceable(town):
 raw=json.loads((FIXTURES/'geocoding_evidence.json').read_text(encoding='utf-8'))[town.name]
 candidates=[r for r in raw['results'] if r['id']==town.geonames_id]
 assert len(candidates)==1
 point=candidates[0]
 assert point['country_code']=='IN' and point['admin1']=='Sikkim' and point['feature_code'].startswith('PPL')
 assert (town.latitude,town.longitude)==(point['latitude'],point['longitude'])
 assert town.attribution and town.source_url.startswith('https://')

def test_expansion_is_opt_in_and_excludes_ambiguity(monkeypatch):
 monkeypatch.delenv('TERRAMIND_EXTENDED_LOCATIONS',raising=False);assert len(active_towns())==3
 monkeypatch.setenv('TERRAMIND_EXTENDED_LOCATIONS','1');assert len(active_towns())==10
 assert not {'loc:pakyong','loc:singtam','loc:chungthang'} & active_towns().keys()

@pytest.mark.parametrize('change',[{'latitude':0},{'country_code':'US'},{'admin1':'Other'},{'feature_code':'AIRP'},{'source_url':'http://untrusted.test'}])
def test_registry_rejects_unverified_points(change):
 with pytest.raises(ValueError):Town.model_validate({**TOWNS[0].model_dump(),**change})

def test_temporal_extrema_and_original_values_unchanged():
 r=weather();before=r.model_dump_json();v=temporal(r)
 assert v['temperature_days']['highest']['date']=='2025-01-06'
 assert v['rainfall_days']['highest']['value']==9.2
 assert v['rainfall_days']['lowest']['date']=='2025-01-02'
 assert len(v['rainfall_days']['lowest']['tied_dates'])==5
 assert v['period_temperature_range_c']==pytest.approx(15.1)
 assert v['monthly'][0]['rainfall_total_mm']==pytest.approx(11.9)
 assert v['day_to_day'][0]['temperature_mean_change_c']==pytest.approx(1.7)
 assert r.model_dump_json()==before

def test_missing_values_and_missing_rows_are_not_zero_filled():
 r=weather();r.daily[0].temperature_mean_c=None;r.daily.pop(2);v=temporal(r)
 assert v['coverage']['temperature_mean_c']=={'valid':5,'missing':2,'expected':7}
 assert all(x['previous_date']!='2025-01-02' for x in v['day_to_day'])  # no bridge across absent Jan 3
 assert v['day_to_day'][0]['temperature_mean_change_c'] is None

def test_all_missing_events_unavailable():
 r=weather()
 for row in r.daily:
  row.temperature_mean_c=None;row.rainfall_mm=None;row.temperature_min_c=None;row.temperature_max_c=None
 v=temporal(r);assert v['temperature_days']['highest'] is None and v['rainfall_days']['lowest'] is None and v['period_temperature_range_c'] is None

@pytest.mark.parametrize('change',['partial','period','kind','rows'])
def test_incomplete_comparison_never_ranks(change):
 a,b=weather(),weather('loc:namchi')
 if change=='partial':a.daily[0].temperature_mean_c=None
 if change=='period':b.start=date(2025,1,2)
 if change=='kind':b.data_kind='weather_model'
 if change=='rows':a.daily.pop();b.daily.pop()
 result=comparisons([a,b])[0]
 assert result['temperature_difference_c'] is None and result['warmer'] is None and result['warnings']

def test_complete_comparison_and_ties():
 a,b=weather(),weather('loc:namchi');row=comparisons([a,b])[0]
 assert row['left_name']=='Gangtok' and row['right_name']=='Namchi'
 assert row['warmer_name'] in ('Gangtok','Namchi','Tie')
 assert row['temperature_difference_c']==pytest.approx(a.summary['temperature_mean_c']-b.summary['temperature_mean_c'])
 assert row['rainfall_difference_mm']==pytest.approx(a.summary['rainfall_total_mm']-b.summary['rainfall_total_mm'])
 tied=comparisons([a,a])[0];assert tied['warmer']=='tie' and tied['wetter']=='tie'

@pytest.mark.parametrize('status,code',[(400,'provider_rejection'),(401,'provider_rejection'),(429,'rate_limit'),(500,'provider_error'),(501,'provider_error')])
def test_retrieval_diagnostics_no_raw_payload(status,code):
 calls=[];sleeps=[]
 def handler(req):calls.append(req);return httpx.Response(status,json={'secret':'private-payload'},headers={'Authorization':'private-header'})
 with pytest.raises(RetrievalFailure) as caught:get_json('https://example.test',{},httpx.MockTransport(handler),sleeps.append)
 assert caught.value.code==code and 'private' not in str(caught.value)
 assert len(calls)==(2 if status in (429,500) else 1)
 assert len(sleeps)==(1 if status in (429,500) else 0)

def test_retry_after_is_not_shortened_and_transient_success():
 sleeps=[]
 with pytest.raises(RetrievalFailure) as e:get_json('https://example.test',{},httpx.MockTransport(lambda r:httpx.Response(429,headers={'Retry-After':'30'})),sleeps.append)
 assert e.value.retry_after==30 and not sleeps
 codes=iter([503,200]);body,url=get_json('https://example.test',{},httpx.MockTransport(lambda r:httpx.Response(next(codes),json={'ok':True})),sleeps.append)
 assert body=={'ok':True} and sleeps==[.25]

@pytest.mark.parametrize('error,code',[(httpx.ReadTimeout,'timeout'),(httpx.ConnectError,'transport')])
def test_transport_errors_are_sanitized(error,code):
 def handler(request):raise error('private-details',request=request)
 with pytest.raises(RetrievalFailure) as e:get_json('https://example.test',{},httpx.MockTransport(handler),lambda _:None)
 assert e.value.code==code and 'private-details' not in str(e.value)

@pytest.mark.parametrize('recent',[False,True])
def test_supplemental_real_recorded_fields_and_units(monkeypatch,recent):
 monkeypatch.setenv('TERRAMIND_ADDITIONAL_MEASUREMENTS','1')
 raw=json.loads((FIXTURES/('supplemental_recent.json' if recent else 'supplemental_era5.json')).read_text())['response']
 q=query();q=q.model_copy(update={'variables':[Variable.HUMIDITY,Variable.WIND_SPEED]})
 if recent:q.time_period.start=q.time_period.end=date(2026,11,14)
 v=retrieve_measurements(q,transport=httpx.MockTransport(lambda r:httpx.Response(200,json=raw)),today=date(2026,11,16))
 assert v['status']=='ok'
 row=v['results'][0];assert row['summary']['HUMIDITY']['unit']=='%' and row['summary']['WIND_SPEED']['unit']=='m/s'
 assert row['data_kind']==('weather_model' if recent else 'reanalysis')
 assert row['daily'][0]['HUMIDITY']==raw['daily']['relative_humidity_2m_mean'][0]

@pytest.mark.parametrize('change',['unit','negative','over100','nonfinite','alignment','timezone','grid','all_missing','partial'])
def test_supplemental_invalid_and_missing_semantics(monkeypatch,change):
 monkeypatch.setenv('TERRAMIND_ADDITIONAL_MEASUREMENTS','1')
 raw=json.loads((FIXTURES/'supplemental_era5.json').read_text())['response']
 if change=='unit':raw['daily_units']['relative_humidity_2m_mean']='°C'
 if change=='negative':raw['daily']['relative_humidity_2m_mean'][0]=-1
 if change=='over100':raw['daily']['relative_humidity_2m_mean'][0]=101
 if change=='nonfinite':raw['daily']['relative_humidity_2m_mean'][0]='nan'
 if change=='alignment':raw['daily']['time'].pop()
 if change=='timezone':raw['timezone']='UTC'
 if change=='grid':raw['latitude']=999
 if change=='all_missing':raw['daily']['relative_humidity_2m_mean']=[None]*7
 if change=='partial':raw['daily']['relative_humidity_2m_mean'][0]=None
 value=retrieve_measurements(query(),transport=httpx.MockTransport(lambda r:httpx.Response(200,json=raw)),today=date(2026,11,16))
 if change=='partial':assert value['status']=='ok' and value['results'][0]['summary']['HUMIDITY']['missing_days']==1
 else:assert value['status']=='unavailable'

def test_supplemental_no_snapshot_or_future_substitution(monkeypatch):
 monkeypatch.setenv('TERRAMIND_ADDITIONAL_MEASUREMENTS','1')
 assert retrieve_measurements(query(),'snapshot')['status']=='needs_clarification'
 q=query();q.time_period.end=date(2099,1,1);assert retrieve_measurements(q)['status']=='needs_clarification'
 monkeypatch.delenv('TERRAMIND_ADDITIONAL_MEASUREMENTS');assert retrieve_measurements(query())['status']=='needs_clarification'

def test_api_selected_is_explicit_and_insights_session_bound(monkeypatch):
 monkeypatch.setenv('TERRAMIND_EXTENDED_LOCATIONS','1')
 with TestClient(create_app(pipeline=object(),demo_enabled=True)) as client:
  registry=client.get('/locations').json();assert len(registry['locations'])==10
  selected=client.post('/environment/selected',json={'location_ids':['loc:gangtok','loc:namchi'],'start':'2025-01-01','end':'2025-01-07','session_id':'owner','source_mode':'snapshot'}).json()
  assert selected['environment']['status']=='ok' and 'no trained NLP' in selected['inference']
  assert selected['insights']['comparisons'][0]['temperature_difference_c'] is not None
  body={'session_id':'owner','context_id':selected['context_id']}
  assert client.post('/environment/insights',json=body).json()['status']=='ok'
  assert client.post('/environment/insights',json={**body,'session_id':'other'}).json()['status']=='no_context'
  assert client.post('/environment/selected',json={'location_ids':['loc:fake'],'start':'2025-01-01','end':'2025-01-07','session_id':'owner'}).status_code==422
  assert client.post('/assistant/route',json={'question':'Show temperature in Pelling during January 2025','session_id':'owner'}).json()['category']=='environment'

def test_day_fact_date_metadata_cannot_be_authored_by_llm():
 from backend.environment.schema import EnvironmentResponse
 r=weather();store=ContextStore();token=store.save('s',EnvironmentResponse(status='ok',query=query('TEMPERATURE'),results=[r]),'snapshot')
 facts,_=compile_facts(store.get(token,'s'));fact=select_facts('What was the warmest day?',facts)[0]
 assert fact.start=='2025-01-01' and fact.end=='2025-01-07'
 assert fact.event_dates==['2025-01-06'] and fact.value=='13.00'
 assert 'event_dates' not in Claim.model_fields
 with pytest.raises(ValueError):Claim.model_validate({**{field:getattr(fact,field) for field in Claim.model_fields},'event_dates':['2099-01-01']})

def test_provider_error_envelope_and_invalid_json_are_not_retried():
 calls=[]
 def envelope(req):calls.append(req);return httpx.Response(200,json={'error':True,'reason':'private-body'})
 with pytest.raises(RetrievalFailure) as error:get_json('https://example.test',{},httpx.MockTransport(envelope),lambda _:None)
 assert error.value.code=='provider_rejection' and len(calls)==1 and 'private' not in str(error.value)
 with pytest.raises(RetrievalFailure) as error:get_json('https://example.test',{},httpx.MockTransport(lambda r:httpx.Response(200,text='not-json')),lambda _:None)
 assert error.value.code=='invalid_response' and error.value.attempts==1

def test_default_genai_summary_stays_compact_and_explicit_days_still_work():
 from backend.environment.schema import EnvironmentResponse
 store=ContextStore();token=store.save('s',EnvironmentResponse(status='ok',query=query('TEMPERATURE'),results=[weather()]),'snapshot')
 facts,_=compile_facts(store.get(token,'s'))
 assert not any(f.metric.endswith('_day') for f in select_facts('Summarize these environmental results.',facts))
 assert select_facts('What was the wettest day?',facts)[0].value=='9.20'

def test_measurement_api_contract_validates_recorded_response(monkeypatch):
 from backend.environment import measurements
 monkeypatch.setenv('TERRAMIND_ADDITIONAL_MEASUREMENTS','1')
 raw=json.loads((FIXTURES/'supplemental_era5.json').read_text())['response']
 transport=httpx.MockTransport(lambda r:httpx.Response(200,json=raw))
 monkeypatch.setattr('backend.presentation.app.retrieve_measurements',lambda query,mode:measurements.retrieve_measurements(query,mode,transport=transport,today=date(2026,11,16)))
 with TestClient(create_app(pipeline=object())) as client:
  response=client.post('/environment/measurements',json={'query':query().model_dump(mode='json'),'source_mode':'live'})
  assert response.status_code==200 and response.json()['status']=='ok'
  assert response.json()['results'][0]['summary']['HUMIDITY']['unit']=='%'
  assert client.post('/environment/measurements',json={'query':query().model_dump(mode='json'),'source_mode':'invented'}).status_code==422

@pytest.mark.parametrize('language,question',[('en','What was the warmest day?'),('hi','सबसे गर्म दिन कौन सा था?'),('ne','सबैभन्दा न्यानो दिन कुन थियो?')])
def test_grounded_event_followup_uses_server_dates_not_model_arithmetic(language,question):
 from backend.environment.schema import EnvironmentResponse
 from backend.genai.client import LLMConfig,OpenAICompatibleClient
 from backend.genai.service import ExplanationService
 def handler(request):
  supplied=json.loads(json.loads(request.content)['messages'][1]['content'])
  assert all(f['metric']=='warmest_day' for f in supplied['facts'])
  fact=supplied['facts'][0]
  claim={field:fact[field] for field in Claim.model_fields}
  return httpx.Response(200,json={'choices':[{'finish_reason':'stop','message':{'content':json.dumps({'language':language,'answerable':True,'claims':[claim]})}}]})
 store=ContextStore();token=store.save('event',EnvironmentResponse(status='ok',query=query('TEMPERATURE'),results=[weather()]),'snapshot')
 client=OpenAICompatibleClient(LLMConfig('openai_compatible','mock-model','https://example.test/v1','test-key-not-secret'),httpx.MockTransport(handler))
 result=ExplanationService(client).explain(store.get(token,'event'),language,question)
 assert result.status=='ok' and result.claims[0].value=='13.00' and result.claims[0].event_dates==['2025-01-06']
 assert result.claims[0].start=='2025-01-01' and result.claims[0].end=='2025-01-07'
 assert '2025-01-06' in result.text and result.sources[0].source_mode=='snapshot'

@pytest.mark.parametrize('variable',['wind direction','surface pressure','snowfall','cloud cover','wind gusts'])
def test_unimplemented_measurements_never_substitute_connected_variables(monkeypatch,variable):
 from backend.presentation.routing import RouteBody,route_question
 monkeypatch.setenv('TERRAMIND_ADDITIONAL_MEASUREMENTS','1')
 result=route_question(RouteBody(question=f'Show {variable} in Gangtok during January 2025',session_id='s'),ContextStore())
 assert result.category=='unsupported'

@pytest.mark.parametrize('intent,operation',[('WEATHER_QUERY','COMPARE'),('COMPARISON','COMPARE'),('CLIMATE_TREND','LOOKUP')])
def test_measurement_service_preserves_intent_operation_and_comparison_contract(monkeypatch,intent,operation):
 from backend.nlp.query.schema import StructuredQuery
 monkeypatch.setenv('TERRAMIND_ADDITIONAL_MEASUREMENTS','1')
 payload=query().model_dump(mode='json');payload.update(intent=intent,operation=operation)
 result=retrieve_measurements(StructuredQuery.model_validate(payload))
 assert result['status']=='needs_clarification' and not result['results']
