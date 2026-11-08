"""Cue words that refine a query beyond its intent.

Two things are read from plain wording rather than learned:
  - the OPERATION, when it differs from the intent's default
    ("why ..." turns a trend question into an explanation), and
  - the DIRECTION of a scenario's change (increase or decrease).

Both are small closed vocabularies, so a word list is exact, testable and
needs no training data. The price is coverage: an unlisted phrasing keeps
the default operation, or leaves the direction unknown.
"""

import re

from backend.nlp.query.enums import Direction, Intent, Language, Operation, TimeType
from backend.nlp.query.intents import INTENT_SPECS
from backend.nlp.query.schema import TimePeriod

# Per language, because the same letters can mean different things: "किन" is
# "why" in Nepali but part of "which" ("किन इलाकों") in Hindi.
_EXPLAIN = {
    Language.EN: r"\bwhy\b|\breasons?\b|\bcaus\w*|going on|\bexplain\w*|how come|"
                 r"\bbehind\b|\bdue to\b",
    Language.HI: r"क्यों|वजह|कारण",
    Language.NE: r"किन(?![ऀ-ॿ])|कारण",
}
_TREND = {
    Language.EN: r"trend|chang|increasing|decreasing|declin|history|pattern|over time|"
                 r"year-by-year|getting",
    Language.HI: r"रुझान|बदलाव|बदल|बढ़ रहा|घट रहा|इतिहास|पैटर्न",
    Language.NE: r"प्रवृत्ति|परिवर्तन|बदलि|बढ्दै|घट्दै|इतिहास|ढाँचा",
}
_RANK = {
    Language.EN: r"which (?:areas|parts|towns|places|districts)|\bwhere\b|\blist\b|highest|"
                 r"most (?:prone|likely|at risk|vulnerable)",
    Language.HI: r"किन इलाकों|कौन से|सबसे|कहां|कहाँ|सूची",
    Language.NE: r"कुन क्षेत्र|कुन भाग|सबैभन्दा|कहाँ|सूची",
}

_INCREASE = re.compile(
    r"increas|\brise|rising|\brose\b|go(?:es)? up|went up|\bmore\b|higher|climb|grow|"
    r"बढ|वृद्धि|ज़्यादा|अधिक"
)
_DECREASE = re.compile(
    r"decreas|\bdrop|\bfall|\bfell\b|\bless\b|lower|reduc|declin|go(?:es)? down|"
    r"घट|कम|गिर"
)


def _has(patterns: dict[Language, str], language: Language, text: str) -> bool:
    return re.search(patterns[language], text) is not None


def derive_operation(
    intent: Intent, language: Language, text: str, time_period: TimePeriod | None
) -> Operation:
    """The intent's default operation, unless a cue says otherwise.

    Only operations the intent allows are ever returned.
    """
    spec = INTENT_SPECS[intent]
    text = text.casefold()
    wants = spec.default_operation
    future = time_period is not None and time_period.type is TimeType.RELATIVE_FUTURE
    has_span = time_period is not None and time_period.type in (
        TimeType.RELATIVE_PAST, TimeType.DATE_RANGE
    )

    if intent is Intent.WEATHER_QUERY:
        if future:
            wants = Operation.FORECAST
    elif intent is Intent.CLIMATE_TREND:
        if _has(_EXPLAIN, language, text):
            wants = Operation.EXPLAIN
    elif intent is Intent.VEGETATION_ANALYSIS:
        if _has(_EXPLAIN, language, text):
            wants = Operation.EXPLAIN
        elif has_span or _has(_TREND, language, text):
            wants = Operation.TREND
    elif intent is Intent.DISASTER_RISK:
        if _has(_EXPLAIN, language, text):
            wants = Operation.EXPLAIN
        elif _has(_RANK, language, text):
            wants = Operation.RANK

    return wants if wants in spec.allowed_operations else spec.default_operation


def detect_direction(text: str, near: int | None = None) -> Direction | None:
    """Increase or decrease, from the verb.

    If both kinds of cue occur ("would flooding get worse if rain increased
    less"), the one closest to character position `near` wins; pass the
    position of the change amount ("20%").
    """
    text = text.casefold()
    found = [(m.start(), Direction.INCREASE) for m in _INCREASE.finditer(text)]
    found += [(m.start(), Direction.DECREASE) for m in _DECREASE.finditer(text)]
    if not found:
        return None
    if near is None:
        return min(found)[1]
    return min(found, key=lambda item: abs(item[0] - near))[1]
