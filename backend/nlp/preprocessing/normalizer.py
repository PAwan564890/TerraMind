"""Light text normalisation and input validation.

The goal is to make text that LOOKS the same BE the same, and nothing more.
Words are never removed, reordered, stemmed or lowercased: the transformer
models downstream were pretrained on natural text and read meaning from
function words, word order and casing.
"""

import re
import unicodedata

# Zero-width joiner / non-joiner change how Devanagari conjuncts are drawn
# (Nepali uses them, e.g. in "र्‍य"), so they are kept in query text.
_ZWJ_ZWNJ = {"‌", "‍"}

# Visually similar punctuation mapped to one form.
_PUNCTUATION = str.maketrans({
    "‘": "'", "’": "'", "‚": "'",    # curly single quotes
    "“": '"', "”": '"', "„": '"',    # curly double quotes
    "–": "-", "—": "-", "−": "-",    # en dash, em dash, minus sign
    "…": "...",                                # ellipsis
    "？": "?", "！": "!", "％": "%",    # full-width ? ! %
    "॥": "।",                             # double danda -> danda
})

_REPEATED_END = re.compile(r"([?!।])\1+")
_SPACE_BEFORE_PUNCTUATION = re.compile(r"\s+([?!।,.;:])")
_WHITESPACE = re.compile(r"\s+")


def normalize_query(text: str) -> str:
    """Return a canonical form of the query. Safe to apply more than once."""
    # NFC: one code-point sequence per visible character. Devanagari letters
    # with a nukta (ज़, ढ़) can be typed two ways; NFC settles on one.
    text = unicodedata.normalize("NFC", text)
    text = text.translate(_PUNCTUATION)

    cleaned = []
    for ch in text:
        category = unicodedata.category(ch)
        if ch in _ZWJ_ZWNJ:
            cleaned.append(ch)
        elif category == "Cc" or category[0] == "Z":
            # Control characters (tab, newline) and every kind of Unicode
            # space, including non-breaking space, become a plain space.
            cleaned.append(" ")
        elif category == "Cf":
            # Other invisible format characters (zero-width space, BOM,
            # soft hyphen) are dropped.
            continue
        else:
            cleaned.append(ch)
    text = "".join(cleaned)

    text = _REPEATED_END.sub(r"\1", text)
    text = _SPACE_BEFORE_PUNCTUATION.sub(r"\1", text)
    return _WHITESPACE.sub(" ", text).strip()


def lookup_key(text: str) -> str:
    """Stricter form used only as a dictionary key for alias lookup.

    Unlike normalize_query this is lossy: it ignores case and joiner
    characters so that small typing differences still find the same entry.
    """
    text = normalize_query(text)
    return "".join(ch for ch in text if ch not in _ZWJ_ZWNJ).casefold()


class InvalidQueryError(ValueError):
    """The query cannot be processed. `code` is stable and machine-readable."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def prepare_query(raw: str, max_chars: int) -> str:
    """Normalise a raw query and check that it is usable.

    Raises InvalidQueryError with code `empty`, `too_long` or `no_content`.
    """
    if not isinstance(raw, str):
        raise InvalidQueryError("empty", "Query must be text.")

    text = normalize_query(raw)
    if not text:
        raise InvalidQueryError("empty", "Query is empty.")
    if len(text) > max_chars:
        raise InvalidQueryError(
            "too_long", f"Query has {len(text)} characters; the limit is {max_chars}."
        )
    # Letters (L*), combining marks (M*) or digits (N*) must be present.
    if not any(unicodedata.category(ch)[0] in "LMN" for ch in text):
        raise InvalidQueryError("no_content", "Query contains no letters or digits.")
    return text
