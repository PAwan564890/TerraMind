"""Structured query -> guarded routing -> retrieval -> descriptive summaries."""
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo
from dateutil.relativedelta import relativedelta

from backend.core import load_settings
from backend.environment.provider import LOCATIONS, DataUnavailable, OpenMeteo
from backend.environment.schema import EnvironmentResponse
from backend.nlp.query.enums import Intent, Operation, TimeType, Variable
from backend.nlp.query.schema import StructuredQuery
from backend.nlp.query.validator import validate_query


def retrieve_query(query: StructuredQuery, source_mode='live', provider=None, today: date | None = None):
    today = today or datetime.now(ZoneInfo('Asia/Kolkata')).date()
    def ask(message):
        return EnvironmentResponse(status='needs_clarification', message=message, query=query)
    checked = validate_query(query, [], load_settings().decision)
    if not checked.ok:
        return ask('Missing or invalid query fields: ' + ', '.join(checked.clarification.missing_fields))
    if query.intent not in (Intent.WEATHER_QUERY, Intent.CLIMATE_TREND, Intent.COMPARISON) or query.operation not in (Operation.LOOKUP, Operation.TREND, Operation.COMPARE):
        return ask('Only weather lookup, descriptive time series and town comparisons are supported; no hazard prediction, forecast or causal explanation.')
    if query.disasters or query.scenario is not None or query.target is not None:
        return ask('Hazard, scenario and target-model queries are not supported by the weather adapter.')
    if not query.variables or any(v not in (Variable.TEMPERATURE, Variable.PRECIPITATION) for v in query.variables):
        return ask('Choose TEMPERATURE or PRECIPITATION. Other variables are not connected.')
    if not 1 <= len(query.locations) <= 3 or any(loc.id not in LOCATIONS for loc in query.locations):
        return ask('Choose a supported town from /locations, not a district, state or river. At most three town points per query.')
    if len({loc.id for loc in query.locations}) != len(query.locations):
        return ask('Choose distinct towns for comparison.')
    if len(query.locations) > 1 and query.operation != Operation.COMPARE:
        return ask('Use a comparison query when requesting more than one town.')
    if query.time_period is None or 'time_period_defaulted' in checked.warnings:
        return ask('Specify a period explicitly: today, last 7 days, or two dates.')
    period = query.time_period
    if period.type == TimeType.CURRENT:
        start = end = today
    elif period.type == TimeType.DATE_RANGE:
        start, end = period.start, period.end
    elif period.type == TimeType.RELATIVE_PAST:
        n = period.value
        if n > 366:
            return ask('Choose a period of at most 366 days.')
        end = today - timedelta(days=1)
        delta = {'day': relativedelta(days=n), 'week': relativedelta(weeks=n),
                 'month': relativedelta(months=n), 'year': relativedelta(years=n)}[period.unit.value]
        start = today - delta
    else:
        return ask('Future periods are not supported by this academic prototype.')
    if start < date(1940, 1, 1) or end > today or (end-start).days >= 366:
        return ask('Choose a non-future period of at most 366 days, starting on or after 1940-01-01.')
    # Recent periods use the forecast API past-data window. Do not mix providers
    # inside one result or silently truncate a long requested range.
    if end > today - timedelta(days=6) and start < today - timedelta(days=92):
        return ask('For a range longer than 92 days, end it at least 6 days ago (ERA5 delay).')
    results, errors = [], []
    provider = provider or OpenMeteo()
    for location in query.locations:
        try:
            results.append(provider.retrieve(location.id, start, end, today, source_mode))
        except DataUnavailable as error:
            errors.append(f'{location.id}: {error}')
    if errors:
        return EnvironmentResponse(status='unavailable', message='Retrieval incomplete. Any returned town results remain inspectable; a complete comparison is unavailable.',
                                   query=query, results=results, errors=errors)
    if not any(any(count for count in r.summary['valid_days'].values()) for r in results):
        return EnvironmentResponse(status='unavailable', message='Provider returned only missing values.', query=query, results=results)
    return EnvironmentResponse(status='ok', query=query, results=results)
