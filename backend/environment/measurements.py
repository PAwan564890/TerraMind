"""Opt-in daily RH and scalar wind-speed means; separate from old weather schema."""
import math
import os
from datetime import date,datetime,timedelta,timezone
from statistics import fmean
from zoneinfo import ZoneInfo
from typing import Literal
from pydantic import BaseModel,ConfigDict,Field
from backend.environment.registry import active_towns
from backend.environment.provider import ARCHIVE,FORECAST
from backend.environment.transport import get_json,RetrievalFailure
from backend.nlp.query.schema import StructuredQuery
from backend.nlp.query.enums import Intent,Operation,TimeType
from backend.nlp.query.validator import validate_query
from backend.core import load_settings

FIELDS={'HUMIDITY':('relative_humidity_2m_mean','%'),'WIND_SPEED':('wind_speed_10m_mean','m/s')}

def enabled():return os.environ.get('TERRAMIND_ADDITIONAL_MEASUREMENTS')=='1'

class MeasurementBody(BaseModel):
    model_config=ConfigDict(extra='forbid')
    query: StructuredQuery
    source_mode: Literal['live','snapshot']='live'


class MeasurementSummary(BaseModel):
    mean: float | None
    minimum: float | None
    maximum: float | None
    unit: Literal['%','m/s']
    valid_days: int
    missing_days: int
    expected_days: int


class MeasurementResult(BaseModel):
    location_id: str
    location_name: str
    requested_latitude: float
    requested_longitude: float
    grid_latitude: float
    grid_longitude: float
    start: date
    end: date
    timezone: str
    data_kind: Literal['reanalysis','weather_model']
    source: str
    source_url: str
    attribution: str
    retrieved_at: str
    daily: list[dict[str,str|float|None]]
    summary: dict[Literal['HUMIDITY','WIND_SPEED'],MeasurementSummary]
    limitations: list[str]


class MeasurementResponse(BaseModel):
    status: Literal['ok','unavailable','needs_clarification']
    message: str | None
    results: list[MeasurementResult]
    errors: list[str]
    query: StructuredQuery


def retrieve_measurements(query,source_mode='live',transport=None,today=None):
    response={'status':'needs_clarification','message':None,'results':[],'errors':[],'query':query.model_dump(mode='json')}
    def fail(message):response['message']=message;return response
    if not enabled():return fail('Additional measurements are disabled; set TERRAMIND_ADDITIONAL_MEASUREMENTS=1 on the backend.')
    if source_mode!='live':return fail('Additional measurements require explicit live retrieval. No humidity/wind recorded snapshots are provided.')
    checked=validate_query(query,[],load_settings().decision)
    if not checked.ok:return fail('Incomplete or invalid structured measurement query: '+', '.join(checked.clarification.missing_fields))
    if query.intent not in (Intent.WEATHER_QUERY,Intent.CLIMATE_TREND,Intent.COMPARISON) or query.operation not in (Operation.LOOKUP,Operation.TREND,Operation.COMPARE) or query.scenario or query.disasters or query.target:
        return fail('Only descriptive measurements are supported; no forecast, hazard or causal inference.')
    variables=[str(v) for v in query.variables]
    if not variables or any(v not in FIELDS for v in variables):return fail('Request HUMIDITY and/or WIND_SPEED only. Weather temperature/rainfall use the original environmental service.')
    if not 1<=len(query.locations)<=2 or len({l.id for l in query.locations})!=len(query.locations) or any(l.id not in active_towns() for l in query.locations):return fail('Select one or two distinct supported town points.')
    if len(query.locations)>1 and query.operation!=Operation.COMPARE:return fail('Use a comparison query for two towns.')
    today=today or datetime.now(ZoneInfo('Asia/Kolkata')).date()
    period=query.time_period
    if not period or period.type!=TimeType.DATE_RANGE:return fail('Supply explicit start/end dates for additional measurements.')
    start,end=period.start,period.end
    if start<date(1940,1,1) or end>today or (end-start).days>=366:return fail('Use a non-future period of 1–366 days from 1940 onward.')
    historical=end<=today-timedelta(days=6)
    if not historical and start<today-timedelta(days=92):return fail('Recent-product ranges must stay within the 92-day past-data window.')
    for location in query.locations:
        town=active_towns()[location.id]
        params={'latitude':town.latitude,'longitude':town.longitude,'start_date':str(start),'end_date':str(end),'timezone':'Asia/Kolkata','daily':','.join(FIELDS[v][0] for v in variables),'wind_speed_unit':'ms'}
        if historical:params['models']='era5'
        try:
            raw,url=get_json(ARCHIVE if historical else FORECAST,params,transport)
            if raw.get('error') or raw['timezone']!='Asia/Kolkata':raise ValueError('provider metadata')
            for coordinate,limit in [('latitude',90),('longitude',180)]:
                v=raw[coordinate]
                if isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v) or abs(v)>limit:raise ValueError('grid coordinate')
            expected=[str(start+timedelta(days=i)) for i in range((end-start).days+1)]
            if raw['daily']['time']!=expected:raise ValueError('date alignment')
            records=[{'date':day} for day in expected];summary={}
            for variable in variables:
                field,unit=FIELDS[variable];values=raw['daily'][field]
                if raw['daily_units'][field]!=unit or len(values)!=len(expected):raise ValueError('unit/alignment')
                for i,value in enumerate(values):
                    if value is not None and (isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value) or value<0 or (variable=='HUMIDITY' and value>100)):raise ValueError('numeric domain')
                    records[i][variable]=value
                valid=[v for v in values if v is not None]
                summary[variable]={'mean':fmean(valid) if valid else None,'minimum':min(valid) if valid else None,'maximum':max(valid) if valid else None,'unit':unit,'valid_days':len(valid),'missing_days':len(values)-len(valid),'expected_days':len(values)}
            response['results'].append({'location_id':town.id,'location_name':town.name,'requested_latitude':town.latitude,'requested_longitude':town.longitude,'grid_latitude':raw['latitude'],'grid_longitude':raw['longitude'],'start':str(start),'end':str(end),'timezone':'Asia/Kolkata','data_kind':'reanalysis' if historical else 'weather_model','source':'Open-Meteo ERA5' if historical else 'Open-Meteo weather model','source_url':url,'attribution':('Weather data by Open-Meteo.com (CC BY 4.0); ERA5: ECMWF / Copernicus Climate Change Service.' if historical else 'Weather data by Open-Meteo.com (CC BY 4.0); best-match weather models, not station observations.'),'retrieved_at':datetime.now(timezone.utc).isoformat(),'daily':records,'summary':summary,'limitations':['Daily means of 2 m relative humidity and/or 10 m scalar wind speed; period mean is the arithmetic mean of valid daily means, not a gust or vector wind.','Available grid estimates only; missing days omitted, never zero-filled. Today may include forecast hours. No station measurement, causal claim or significance test.','Separate supplemental product; these facts are not included in the weather GenAI context.']})
        except RetrievalFailure as error:response['errors'].append(f'{town.id}: {error}')
        except (KeyError,ValueError,TypeError,AttributeError,OverflowError):response['errors'].append(f'{town.id}: Invalid additional-measurement response [code=invalid_response].')
    response['status']='unavailable' if response['errors'] or not any(any(s['valid_days'] for s in r['summary'].values()) for r in response['results']) else 'ok'
    return response
