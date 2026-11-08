"""Rule-based parser for time expressions in English, Hindi and Nepali.

Time expressions are a small, regular vocabulary ("last five years",
"पिछले पांच सालों", "पछिल्ला पाँच वर्ष"), so rules are more reliable and
far easier to debug than a model. The cost is coverage: a phrasing with no
rule returns None, and the query is then treated as having no usable time.
"""

import re
from dataclasses import dataclass
from datetime import date

from backend.nlp.normalization.morphology import ATTACHED_ENDINGS
from backend.nlp.normalization.numbers import NUMBER_PATTERN, ascii_digits, to_number
from backend.nlp.preprocessing import lookup_key
from backend.nlp.query.enums import Language, TimeType, TimeUnit
from backend.nlp.query.schema import TimePeriod


@dataclass(frozen=True)
class TimeParse:
    period: TimePeriod
    # 1.0 for an unambiguous rule; lower when the reading was a guess.
    confidence: float = 1.0


# A Devanagari keyword must be a whole word. Python's \b does not work here
# (Devanagari vowel signs are not "word characters"), so both edges are spelled
# out. It must not start mid-word ("कल" inside "आजकल"), and what follows must
# be the end of the word or a case ending ("भोलिको" = tomorrow's). Without the
# right-hand rule "हाल" (currently) matched inside "हालत" (condition).
_NOT_AFTER_DEVANAGARI = r"(?<![ऀ-ॿ])"
_WORD_END = "(?=$|[^ऀ-ॿ]|" + "|".join(ATTACHED_ENDINGS) + ")"

_UNITS: dict[str, tuple[TimeUnit, int]] = {
    r"days?|दिनों|दिन": (TimeUnit.DAY, 1),
    r"weeks?|हफ्तों|हफ्ते|हफ्ता|सप्ताह|हप्ता": (TimeUnit.WEEK, 1),
    r"months?|महीनों|महीने|महीना|माह|महिना": (TimeUnit.MONTH, 1),
    r"years?|सालों|साल|वर्षों|वर्ष": (TimeUnit.YEAR, 1),
    r"decades?|दशकों|दशक": (TimeUnit.YEAR, 10),
}
_UNIT = "|".join(f"(?:{pattern})" for pattern in _UNITS)

_PAST = r"last|past|previous|पिछले|पिछला|पिछली|बीते|गत|पछिल्ला|पछिल्लो|बितेका|बितेको"
_FUTURE = r"next|coming|upcoming|अगले|अगला|अगली|आने वाले|आगामी|अर्को|आउँदो|आउने"

_RELATIVE = re.compile(
    rf"(?P<mark>{_PAST}|{_FUTURE})\s+(?:(?P<n>{NUMBER_PATTERN})\s+)?(?P<unit>{_UNIT})"
)
_AGO = re.compile(rf"(?P<n>{NUMBER_PATTERN})\s+(?P<unit>{_UNIT})\s+(?:ago|पहले|अघि)")
_PAST_MARK = re.compile(rf"^(?:{_PAST})$")

_YEAR = r"((?:19|20)\d{2})"
_YEAR_RANGE = re.compile(
    rf"{_YEAR}\s*(?:to|through|till|until|and|-|से|देखि)\s*{_YEAR}"
)
_SINCE = re.compile(rf"(?:since\s+{_YEAR}|{_YEAR}\s*(?:से|देखि|के बाद|पछि))")
_SINGLE_YEAR = re.compile(rf"(?<!\d){_YEAR}(?!\d)")


def _keyword(*words: str) -> re.Pattern:
    parts = []
    for word in sorted(words, key=len, reverse=True):
        if word.isascii():
            parts.append(rf"\b{re.escape(word)}\b")
        else:
            parts.append(_NOT_AFTER_DEVANAGARI + re.escape(word) + _WORD_END)
    return re.compile("|".join(parts))


_CURRENT = _keyword(
    "today", "now", "right now", "currently", "at present", "at the moment",
    "these days", "nowadays",
    "आज", "अभी", "इस समय", "आजकल", "फिलहाल", "इन दिनों",
    "अहिले", "आजभोलि", "अचेल",
)
# "हाल" means "currently" in Nepali. In Hindi it is the noun in "क्या हाल है"
# ("how is it"), which says nothing about time, so it counts only for Nepali.
_CURRENT_NEPALI_ONLY = _keyword("हाल")
_DAY_AFTER_TOMORROW = _keyword("day after tomorrow", "पर्सि")
_TOMORROW = _keyword("tomorrow", "भोलि")
_DAY_BEFORE_YESTERDAY = _keyword("day before yesterday", "अस्ति")
_YESTERDAY = _keyword("yesterday", "हिजो")
# Hindi uses one word for yesterday and tomorrow, and one for the day before
# and the day after. Only the verb tense tells them apart.
_HINDI_ONE_DAY = _keyword("कल")
_HINDI_TWO_DAYS = _keyword("परसों")
_HINDI_FUTURE_TENSE = re.compile(
    r"ेगा|ेगी|ेंगे|ोगा|ोगी|ोंगे|एगा|एगी|एंगे|ऊंगा|पूर्वानुमान|होने वाल"
)
_HINDI_PAST_TENSE = re.compile(r"था|थी|थे|हुआ|हुई|हुए|गया|गई|गए|रहा था")


def _unit_of(text: str) -> tuple[TimeUnit, int]:
    for pattern, unit in _UNITS.items():
        if re.fullmatch(pattern, text):
            return unit
    raise ValueError(text)


def _relative(time_type: TimeType, value: float, unit: TimeUnit) -> TimePeriod:
    return TimePeriod(type=time_type, value=int(value), unit=unit)


def parse_time(text: str, context: str = "", today: date | None = None,
               language: Language | None = None) -> TimeParse | None:
    """Turn a time expression into a TimePeriod, or None if no rule applies.

    `context` is the whole query; it is read only to settle the Hindi
    yesterday/tomorrow ambiguity. `today` anchors open-ended ranges such as
    "since 2015" and defaults to the current date. `language` switches off
    keywords that mean something else in that language; with None, every
    keyword applies.
    """
    key = ascii_digits(lookup_key(text))

    match = _YEAR_RANGE.search(key)
    if match:
        start, end = sorted(int(year) for year in match.groups())
        return TimeParse(TimePeriod(
            type=TimeType.DATE_RANGE, start=date(start, 1, 1), end=date(end, 12, 31)
        ))

    match = _SINCE.search(key)
    if match:
        year = int(next(group for group in match.groups() if group))
        end = today or date.today()
        if year <= end.year:
            return TimeParse(TimePeriod(
                type=TimeType.DATE_RANGE, start=date(year, 1, 1), end=end
            ))

    match = _RELATIVE.search(key)
    if match:
        unit, multiplier = _unit_of(match["unit"])
        value = (to_number(match["n"]) if match["n"] else 1) * multiplier
        time_type = (
            TimeType.RELATIVE_PAST if _PAST_MARK.match(match["mark"])
            else TimeType.RELATIVE_FUTURE
        )
        return TimeParse(_relative(time_type, value, unit))

    match = _AGO.search(key)
    if match:
        unit, multiplier = _unit_of(match["unit"])
        return TimeParse(
            _relative(TimeType.RELATIVE_PAST, to_number(match["n"]) * multiplier, unit)
        )

    # Longer phrases first: "day after tomorrow" contains "tomorrow".
    fixed = [
        (_DAY_AFTER_TOMORROW, TimeType.RELATIVE_FUTURE, 2),
        (_DAY_BEFORE_YESTERDAY, TimeType.RELATIVE_PAST, 2),
        (_TOMORROW, TimeType.RELATIVE_FUTURE, 1),
        (_YESTERDAY, TimeType.RELATIVE_PAST, 1),
    ]
    for pattern, time_type, days in fixed:
        if pattern.search(key):
            return TimeParse(_relative(time_type, days, TimeUnit.DAY))

    for pattern, days in ((_HINDI_TWO_DAYS, 2), (_HINDI_ONE_DAY, 1)):
        if pattern.search(key):
            context_key = lookup_key(context)
            if _HINDI_FUTURE_TENSE.search(context_key):
                return TimeParse(_relative(TimeType.RELATIVE_FUTURE, days, TimeUnit.DAY))
            if _HINDI_PAST_TENSE.search(context_key):
                return TimeParse(_relative(TimeType.RELATIVE_PAST, days, TimeUnit.DAY))
            # No tense cue: assume the future, and say it was a guess.
            return TimeParse(_relative(TimeType.RELATIVE_FUTURE, days, TimeUnit.DAY), 0.6)

    if _CURRENT.search(key):
        return TimeParse(TimePeriod(type=TimeType.CURRENT))
    if language in (None, Language.NE) and _CURRENT_NEPALI_ONLY.search(key):
        return TimeParse(TimePeriod(type=TimeType.CURRENT))

    match = _SINGLE_YEAR.search(key)
    if match:
        year = int(match.group(1))
        return TimeParse(TimePeriod(
            type=TimeType.DATE_RANGE, start=date(year, 1, 1), end=date(year, 12, 31)
        ))

    return None
