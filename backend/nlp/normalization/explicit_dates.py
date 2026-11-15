"""Deterministic explicit calendar dates, before less-specific year rules.

Native-script queries and Devanagari digits are supported. Named months are
English (full or abbreviated), deliberately independent of OS locale. Ambiguous
numeric forms are refused rather than interpreted as whole-year requests.
"""
import re
from datetime import date

from backend.nlp.normalization.calendar_periods import calendar_records
from backend.nlp.normalization.numbers import ascii_digits
from backend.nlp.preprocessing import InvalidQueryError, lookup_key
from backend.nlp.query.enums import TimeType
from backend.nlp.query.schema import TimePeriod


class ExplicitDateError(InvalidQueryError):
    def __init__(self, message: str):
        super().__init__('invalid_time_period', message)


_MONTHS = {}
for number, name in enumerate(('january', 'february', 'march', 'april', 'may', 'june',
                               'july', 'august', 'september', 'october', 'november', 'december'), 1):
    _MONTHS[name] = _MONTHS[name[:3]] = number
_MONTHS['sept'] = 9
_MONTH = '(?:' + '|'.join(sorted(_MONTHS, key=len, reverse=True)) + r')\.?'
_DAY = r'\d{1,2}(?:st|nd|rd|th)?'
_JOIN = r'(?:to|through|till|until|-|से|देखि)'
_ISO = re.compile(r'(?<![\d/-])(?P<year>\d{4})-(?P<month>\d{2})-(?P<day>\d{2})(?![\d/-])')
_DMY = re.compile(rf'(?<![\wऀ-ॿ])(?P<day>{_DAY})\s+(?P<month>{_MONTH})\s*,?\s*(?P<year>\d{{4}})(?!\d)')
_MDY = re.compile(rf'(?<![\wऀ-ॿ])(?P<month>{_MONTH})\s+(?P<day>{_DAY})\s*,?\s*(?P<year>\d{{4}})(?!\d)')
_SHARED_DMY = re.compile(rf'(?<![\wऀ-ॿ])(?P<first>{_DAY})\s*{_JOIN}\s*(?P<day>{_DAY})\s+(?P<month>{_MONTH})\s*,?\s*(?P<year>\d{{4}})(?!\d)')
_SHARED_MDY = re.compile(rf'(?<![\wऀ-ॿ])(?P<month>{_MONTH})\s+(?P<first>{_DAY})\s*{_JOIN}\s*(?P<day>{_DAY})\s*,?\s*(?P<year>\d{{4}})(?!\d)')
# Recognize unsupported numeric dates too, so their year cannot become a fallback.
_NUMERIC_LIKE = re.compile(r'(?<!\d)(?:\d{4}[-/]\d{1,2}(?:[-/]\d{1,3})?|\d{1,2}[-/]\d{1,2}[-/]\d{2,4})(?!\d)')
_NAMED_LIKE = re.compile(rf'(?<![\wऀ-ॿ])(?:{_DAY}\s+{_MONTH}(?![\wऀ-ॿ])|{_MONTH}\s+\d)')
_YEAR = re.compile(r'(?<!\d)\d{4}(?!\d)')


def _calendar(match, day='day'):
    month = match['month'].rstrip('.')
    month = int(month) if month.isdigit() else _MONTHS[month]
    number = int(re.match(r'\d+', match[day]).group())
    try:
        return date(int(match['year']), month, number)
    except ValueError as error:
        raise ExplicitDateError('Invalid calendar date. Use real dates in YYYY-MM-DD format.') from error


def parse_explicit_period(text: str, today: date | None = None) -> TimePeriod | None:
    """One explicit day or ordered range, or None when there is no explicit date.

    Raises ExplicitDateError for invalid, reversed, incomplete, ambiguous or
    multiple explicit periods. Never guesses a numeric locale or reorders dates.
    Retrieval limits (1940+, past/current, <=366 days) remain in the data service.
    """
    key = ascii_digits(lookup_key(text))
    records = []
    for pattern in (_SHARED_DMY, _SHARED_MDY, _ISO, _DMY, _MDY):
        for match in pattern.finditer(key):
            if any(match.start() < end and match.end() > start for start, end, _, _ in records):
                continue
            first = _calendar(match, 'first') if 'first' in match.groupdict() else _calendar(match)
            records.append((match.start(), match.end(), first, _calendar(match)))
    try:
        records.extend(calendar_records(key, records, today))
    except ValueError as error:
        raise ExplicitDateError("Invalid calendar period.") from error
    records.sort()

    # Any unconsumed date-like fragment blocks year fallback (including NER
    # fragments). Whole-query context takes precedence in parse_time().
    for pattern in (_NUMERIC_LIKE, _NAMED_LIKE):
        for match in pattern.finditer(key):
            if not any(start <= match.start() and match.end() <= end for start, end, _, _ in records):
                raise ExplicitDateError('Incomplete or ambiguous date. Use YYYY-MM-DD or a complete named-month date.')
    if not records:
        return None
    if len(records) > 2 or (len(records) == 2 and any(first != last for _, _, first, last in records)):
        raise ExplicitDateError('Specify only one explicit date range per question.')
    for match in _YEAR.finditer(key):
        if not any(start <= match.start() and match.end() <= end for start, end, _, _ in records):
            raise ExplicitDateError('An explicit date range needs two complete dates; do not mix dates and bare years.')
    if len(records) == 1:
        left, right = records[0][:2]
        shared = _SHARED_DMY.fullmatch(key[left:right]) or _SHARED_MDY.fullmatch(key[left:right])
        if (re.match(rf'\s*(?:{_JOIN}|and)(?=$|\W)', key[right:]) or
                (not shared and records[0][2] == records[0][3] and re.search(r'\b(?:from|since|between|to|through|until|till)\s*$', key[:left]))):
            raise ExplicitDateError('An explicit range needs both endpoints; supply two complete dates.')
    if len(records) == 2:
        gap = key[records[0][1]:records[1][0]].strip()
        between = re.search(r'\bbetween\b', key[:records[0][0]])
        if not re.fullmatch(_JOIN, gap) and not (gap == 'and' and between):
            raise ExplicitDateError('Connect the two dates with to, through, until, a dash, से or देखि.')
    start, end = records[0][2], records[-1][3]
    if start > end:
        raise ExplicitDateError('Start date must not be after end date; dates are not silently reordered.')
    return TimePeriod(type=TimeType.DATE_RANGE, start=start, end=end)
