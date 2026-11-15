"""Boundary tests use real recorded payloads and injected network failures."""
import copy
import json
from datetime import date
import httpx
import pytest
from backend.environment.analytics import summarize
from backend.environment.provider import OpenMeteo, DataUnavailable, SNAPSHOT_DIR
from backend.environment.schema import DailyRow
from backend.environment.service import retrieve_query
from backend.presentation.demo import DemoAnalyzer


def query(text='Show temperature and rainfall in Gangtok from 2025-01-01 to 2025-01-07.'):
    return DemoAnalyzer().analyze(text).structured_query


def payload():
    return json.loads((SNAPSHOT_DIR / 'gangtok.json').read_text())['response']


def provider_with(data, status=200):
    return OpenMeteo(httpx.MockTransport(lambda request: httpx.Response(status, json=data)))


def test_real_snapshot_statistics_and_provenance():
    result = retrieve_query(query(), source_mode='snapshot', today=date(2026, 11, 15))
    assert result.status == 'ok'
    data = result.results[0]
    assert data.data_kind == 'reanalysis'
    assert data.summary['temperature_mean_c'] == pytest.approx(sum([8.7,10.4,11.9,12.7,12,13,9.9])/7)
    assert data.summary['totals_complete']
    assert 'RECORDED SNAPSHOT' in ' '.join(data.warnings)
    assert data.retrieved_at.tzinfo is not None
    assert data.source_url.startswith('https://archive-api.open-meteo.com/')
    assert data.grid_latitude != data.requested_latitude


def test_missing_values_are_not_zero_and_totals_are_partial():
    raw = payload()
    raw['daily']['rain_sum'][0] = None
    raw['daily']['temperature_2m_mean'] = [None]*7
    result = retrieve_query(query(), provider=provider_with(raw), today=date(2026,11,15))
    assert result.status == 'ok'
    summary = result.results[0].summary
    assert summary['temperature_mean_c'] is None
    assert summary['valid_days']['rainfall_mm'] == 6
    assert not summary['totals_complete']


def test_all_missing_is_unavailable():
    raw = payload()
    for key in raw['daily']:
        if key != 'time': raw['daily'][key] = [None]*7
    result = retrieve_query(query(), provider=provider_with(raw), today=date(2026,11,15))
    assert result.status == 'unavailable'
    assert result.results[0].summary['precipitation_total_mm'] is None


@pytest.mark.parametrize('change', ['unit','length','bad_number','negative_rain','wrong_date','duplicate','timezone','no_daily'])
def test_invalid_provider_response_never_becomes_a_result(change):
    raw = copy.deepcopy(payload())
    if change == 'unit': raw['daily_units']['temperature_2m_mean'] = '°F'
    if change == 'length': raw['daily']['rain_sum'].pop()
    if change == 'bad_number': raw['daily']['rain_sum'][0] = 'unavailable'
    if change == 'negative_rain': raw['daily']['rain_sum'][0] = -1
    if change == 'wrong_date': raw['daily']['time'][0] = '2024-01-01'
    if change == 'duplicate': raw['daily']['time'][0] = raw['daily']['time'][1]
    if change == 'timezone': raw['timezone'] = 'UTC'
    if change == 'no_daily': raw.pop('daily')
    with pytest.raises(DataUnavailable):
        provider_with(raw).retrieve('loc:gangtok',date(2025,1,1),date(2025,1,7),date(2026,11,15))


@pytest.mark.parametrize('status',[400,429,500,503])
def test_http_failure_does_not_silently_use_a_snapshot(status):
    result = retrieve_query(query(), provider=provider_with({},status), today=date(2026,11,15))
    assert result.status == 'unavailable'
    assert result.results == []
    assert result.errors


def test_timeout_handled():
    def fail(request): raise httpx.ReadTimeout('timeout',request=request)
    result = retrieve_query(query(), provider=OpenMeteo(httpx.MockTransport(fail)))
    assert result.status == 'unavailable'


@pytest.mark.parametrize('text',[
    'Show temperature in Sikkim today.',
    'Show temperature in Gangtok district today.',
    'Show humidity in Gangtok today.',
    'Show temperature in Gangtok next week.',
    'Show temperature in Gangtok from 2025-01-01 to 2026-12-31.',
    'Show temperature in Gangtok last 5 years.',
    'Show temperature in Gangtok and Namchi today.',
])
def test_unsupported_requests_ask_instead_of_inventing(text):
    result = retrieve_query(query(text), today=date(2026,11,15))
    assert result.status == 'needs_clarification'
    assert not result.results


def test_missing_period_does_not_inherit_validator_default():
    q = query().model_copy(update={'time_period':None})
    assert retrieve_query(q).status == 'needs_clarification'


def test_relative_days_are_completed_local_dates_and_calendar_months():
    class Capture:
        def retrieve(self, loc, start, end, today, mode):
            assert start == date(2026, 10, 15)
            assert end == date(2026, 11, 14)
            raise DataUnavailable('test capture')
    result = retrieve_query(query('Show temperature in Gangtok last month.'),provider=Capture(),today=date(2026,11,15))
    assert result.errors == ['loc:gangtok: test capture']


def test_comparison_uses_same_period_and_canonical_locations():
    result = retrieve_query(query('Compare temperature in Gangtok and Namchi from 2025-01-01 to 2025-01-07.'),source_mode='snapshot')
    assert result.status == 'ok'
    assert [r.location_id for r in result.results] == ['loc:gangtok','loc:namchi']
    assert len({(r.start,r.end) for r in result.results}) == 1


def test_snapshot_does_not_ignore_requested_dates():
    result = retrieve_query(query('Show rainfall in Gangtok from 2025-02-01 to 2025-02-07.'),source_mode='snapshot')
    assert result.status == 'unavailable'
    assert not result.results


def test_empty_statistics():
    assert summarize([])['temperature_mean_c'] is None
    assert not summarize([])['totals_complete']


def test_recent_weather_rain_includes_convective_showers():
    raw=payload()
    raw['daily']['showers_sum']=[1.0]*7
    raw['daily_units']['showers_sum']='mm'
    weather=provider_with(raw).retrieve('loc:gangtok',date(2025,1,1),date(2025,1,7),date(2025,1,8))
    assert weather.data_kind=='weather_model'
    assert weather.summary['rainfall_total_mm']==pytest.approx(sum(raw['daily']['rain_sum'])+7)
    assert any('weather-model rainfall' in w for w in weather.warnings)


@pytest.mark.parametrize('raw',[[],None,'not an object'])
def test_non_object_json_is_unavailable(raw):
    with pytest.raises(DataUnavailable):
        provider_with(raw).retrieve('loc:gangtok',date(2025,1,1),date(2025,1,7),date(2026,11,15))
