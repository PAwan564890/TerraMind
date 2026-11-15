"""Calendar normalization regressions; no model weights or network required."""
from datetime import date
import pytest

from backend.nlp.normalization import EntityNormalizer, parse_time
from backend.nlp.normalization.explicit_dates import ExplicitDateError, parse_explicit_period
from backend.core import load_settings
from backend.nlp.ontology import get_ontology
from backend.nlp.query.enums import EntityType, Language

QUESTION = 'Show temperature and rainfall in Gangtok from 2025-01-01 to 2025-01-07.'


@pytest.mark.parametrize('text', [
    QUESTION,
    'between 2025-01-01 and 2025-01-07',
    '2025-01-01 through 2025-01-07',
    '2025-01-01 until 2025-01-07',
    '2025-01-01 – 2025-01-07',
    'गंगटोक में 2025-01-01 से 2025-01-07 तक वर्षा',
    'गान्तोकमा २०२५-०१-०१ देखि २०२५-०१-०७ सम्म तापक्रम',
    '1 January 2025 to 7 January 2025',
    'January 1, 2025 through January 7, 2025',
    '1st Jan. 2025 until 7th Jan. 2025',
    'between January 1, 2025 and January 7, 2025',
    'from 1–7 January 2025',
    'January 1-7, 2025',
    '1 to 7 Jan 2025',
])
def test_explicit_seven_day_range_never_expands_to_a_year(text):
    period = parse_time(text, text).period
    assert (period.start, period.end) == (date(2025,1,1),date(2025,1,7))
    assert (period.end-period.start).days+1 == 7


@pytest.mark.parametrize('text,start,end', [
    ('2024-02-28 to 2024-02-29',date(2024,2,28),date(2024,2,29)),
    ('2024-12-31 to 2025-01-02',date(2024,12,31),date(2025,1,2)),
    ('31 December 2024 to 2 January 2025',date(2024,12,31),date(2025,1,2)),
    ('on 2025-01-07',date(2025,1,7),date(2025,1,7)),
    ('7 January 2025 to 7 January 2025',date(2025,1,7),date(2025,1,7)),
    ('from January 1-1, 2025',date(2025,1,1),date(2025,1,1)),
    ('2025-01-07 to 2025-01-07',date(2025,1,7),date(2025,1,7)),
])
def test_calendar_boundaries_and_single_days(text,start,end):
    period = parse_time(text).period
    assert (period.start,period.end)==(start,end)


@pytest.mark.parametrize('text', [
    '2025-01-07 to 2025-01-01',
    '7 January 2025 to 1 January 2025',
    '7-1 January 2025',
    '2025-02-29 to 2025-03-01',
    '2025-02-30 to 2025-03-01',
    '2025-13-01 to 2025-13-07',
    '2025-00-01 to 2025-01-07',
    '2025-01-00 to 2025-01-07',
    '31 April 2025 to 7 May 2025',
    'January 32, 2025 to February 2, 2025',
    'January 32 to February 2',
    '2025-1-1 to 2025-1-7',
    '2025-01 to 2025-02',
    '2025/01/01 to 2025/01/07',
    '01/02/2025 to 07/02/2025',
    '2025-01-01 to 2025',
    '2025-01-01 to tomorrow',
    'from 2025-01-01',
    'since 2025-01-01',
    'from yesterday to 2025-01-07',
    'January 2025 to February 2025',
    '32 January to 7 February',
    'between 2025-01-01',
    '1 January to 7 January 2025',
    '2025-01-01 to 2025-01-07 and 2025-02-01',
    '2025-01-01 or 2025-01-07',
    '2025-01-01 and 2025-01-07',
])
def test_invalid_or_ambiguous_explicit_period_never_falls_back_to_year(text):
    with pytest.raises(ExplicitDateError) as error:
        parse_time(text,text)
    assert error.value.code=='invalid_time_period'


@pytest.mark.parametrize('span',['2025','2025-01','2025-01-01','2025-01-07','01-07'])
def test_full_query_wins_over_partial_ner_time_spans(span):
    normalizer=EntityNormalizer(get_ontology(),load_settings().normalization)
    resolved=normalizer.normalize(span,EntityType.TIME,QUESTION,Language.EN)
    assert resolved.value.start==date(2025,1,1)
    assert resolved.value.end==date(2025,1,7)
    assert resolved.canonical=='date_range:2025-01-01:2025-01-07'


@pytest.mark.parametrize('text',['from 2015 to 2020','2020 to 2015','२०१५ देखि २०२० सम्म','2015-2020'])
def test_existing_year_only_ranges_are_preserved(text):
    assert parse_explicit_period(text) is None
    period=parse_time(text).period
    assert (period.start,period.end)==(date(2015,1,1),date(2020,12,31))
