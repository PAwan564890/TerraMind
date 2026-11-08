"""Rule-based parser for change magnitudes: "20%", "10 प्रतिशत", "2 degrees"."""

import re
from dataclasses import dataclass

from backend.nlp.normalization.numbers import NUMBER_PATTERN, ascii_digits, to_number
from backend.nlp.preprocessing import lookup_key
from backend.nlp.query.enums import ChangeUnit


@dataclass(frozen=True)
class ChangeValue:
    change: float
    unit: ChangeUnit


_PERCENT = re.compile(
    rf"(?P<n>{NUMBER_PATTERN})\s*(?:%|percent|per cent|pct|प्रतिशत|फीसदी|फ़ीसदी|प्रतिसत)"
)
# Absolute changes are only meaningful for temperature in this project.
_DEGREES = re.compile(
    rf"(?P<n>{NUMBER_PATTERN})\s*(?:°\s*c?|degrees?|deg|डिग्री)"
)


def parse_change(text: str) -> ChangeValue | None:
    """Value and unit of a change expression, or None if no rule applies.

    The direction (increase or decrease) is not in this span; it is read from
    the verb by the query structurer.
    """
    key = ascii_digits(lookup_key(text))
    for pattern, unit in ((_PERCENT, ChangeUnit.PERCENT), (_DEGREES, ChangeUnit.ABSOLUTE)):
        match = pattern.search(key)
        if match:
            value = to_number(match["n"])
            if value > 0:
                return ChangeValue(value, unit)
    return None
