"""Number parsing shared by the time and change parsers."""

import re

_DEVANAGARI_DIGITS = str.maketrans("०१२३४५६७८९", "0123456789")

# Number words that plausibly appear in a query. Nepali "छ" (six) is left out
# on purpose: it is also the verb "is" and ends most Nepali sentences.
NUMBER_WORDS: dict[str, int] = {
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7,
    "eight": 8, "nine": 9, "ten": 10, "eleven": 11, "twelve": 12, "fifteen": 15,
    "twenty": 20, "thirty": 30, "forty": 40, "fifty": 50, "hundred": 100,
    "एक": 1, "दो": 2, "दुई": 2, "तीन": 3, "चार": 4, "पांच": 5, "पाँच": 5,
    "छह": 6, "सात": 7, "आठ": 8, "नौ": 9, "दस": 10, "पंद्रह": 15, "पन्ध्र": 15,
    "बीस": 20, "तीस": 30, "चालीस": 40, "पचास": 50, "सौ": 100, "सय": 100,
}

# Longest first, so "fifteen" is tried before "five".
_WORDS = "|".join(sorted(map(re.escape, NUMBER_WORDS), key=len, reverse=True))
NUMBER_PATTERN = rf"(?:\d+(?:\.\d+)?|{_WORDS})"


def ascii_digits(text: str) -> str:
    """Replace Devanagari digits (०-९) with 0-9. Length is unchanged."""
    return text.translate(_DEVANAGARI_DIGITS)


def to_number(token: str) -> float:
    """Value of a token matched by NUMBER_PATTERN."""
    return float(NUMBER_WORDS[token]) if token in NUMBER_WORDS else float(token)
