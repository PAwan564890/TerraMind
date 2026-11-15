"""Calendar phrases only; deterministic normalization, never model predictions."""
import calendar
import re
from datetime import date, datetime
from zoneinfo import ZoneInfo

MONTHS = {}
for i, name in enumerate(('January','February','March','April','May','June','July','August','September','October','November','December'), 1):
    MONTHS[name.lower()] = MONTHS[name[:3].lower()] = i
MONTHS['sept'] = 9
for i, aliases in enumerate([
    ('जनवरी',),('फरवरी','फ़रवरी','फेब्रुअरी'),('मार्च',),('अप्रैल','अप्रिल'),
    ('मई','मे'),('जून','जुन'),('जुलाई','जुलाइ'),('अगस्त','अगस्ट'),
    ('सितंबर','सितम्बर','सेप्टेम्बर'),('अक्टूबर','अक्टोबर'),('नवंबर','नवम्बर','नोभेम्बर'),
    ('दिसंबर','दिसम्बर','डिसेम्बर')], 1):
    MONTHS.update({alias:i for alias in aliases})
MONTH = '(?:'+'|'.join(sorted(MONTHS, key=len, reverse=True))+')'
LEFT = r'(?<![\wऀ-ॿ])'
RIGHT = r'(?![\wऀ-ॿ])'
PATTERNS = [
    re.compile(rf'{LEFT}(?:the )?first week of (?P<month>{MONTH}) (?P<year>\d{{4}}){RIGHT}'),
    re.compile(rf'{LEFT}(?P<month>{MONTH}) (?P<year>\d{{4}}) (?:के पहले सप्ताह|के प्रथम सप्ताह|को पहिलो हप्ता|को पहिलो साता){RIGHT}'),
    re.compile(rf'{LEFT}(?P<month>{MONTH})\s+(?:of\s+)?(?P<year>\d{{4}}){RIGHT}'),
    re.compile(rf'{LEFT}(?:last|पिछली|पिछले|गत|पछिल्लो)\s+(?P<month>{MONTH}){RIGHT}'),
]


def calendar_records(key, existing, today=None):
    today = today or datetime.now(ZoneInfo('Asia/Kolkata')).date()
    result = []
    for index, pattern in enumerate(PATTERNS):
        for match in pattern.finditer(key):
            if any(match.start()<b and match.end()>a for a,b,*_ in [*existing,*result]):
                continue
            if index == 2 and (re.search(r'(?:(?:weeks?|half|quarter) (?:of|in)|early|late|mid[- ]?)\s*$',key[:match.start()]) or re.match(r'\s+(?:(?:के|को)\s+(?:दूसरे|दोस्रो|अंतिम|अन्तिम)|(?:first|second|last) week)',key[match.end():])):
                raise ValueError('Unsupported calendar subdivision; supply explicit dates.')
            month = MONTHS[match['month']]
            year = int(match['year']) if 'year' in match.groupdict() else today.year - (month >= today.month)
            end_day = 7 if index < 2 else calendar.monthrange(year,month)[1]
            result.append((match.start(),match.end(),date(year,month,1),date(year,month,end_day)))
    # A known month without a complete accepted period is not a bare year.
    for match in re.finditer(LEFT + MONTH + RIGHT, key):
        if match.group() == 'may' and not re.search(r'\d{4}',key):
            continue  # English modal 'may' is not necessarily a month.
        if not any(a <= match.start() and match.end() <= b for a,b,*_ in [*existing,*result]):
            raise ValueError('Specify a month and year, last named month, or explicit dates.')
    return result
