"""Detects follow-up fragments: queries that are only entities and filler.

"What about rainfall?", "और बारिश?", "गान्तोकमा?" and a bare "Gangtok" say
nothing about what the user wants on their own. They only make sense as a
change to the previous question, so their intent is taken from context.
"""

from backend.nlp.preprocessing import lookup_key

_PUNCTUATION = "?.,!।:;\"'()-"

# Words that add no intent of their own, in any of the three languages.
# Verbs are deliberately absent ("is", "है", "छ"): "What is the temperature
# in Gangtok?" is a complete question, "What about temperature?" is not.
# Case endings are included because a Nepali ending is left behind when the
# entity it was attached to is removed ("गान्तोकमा" minus "गान्तोक" = "मा").
_FILLER = {
    # English
    "what", "what's", "whats", "about", "and", "how", "the", "also", "in", "for", "of",
    "then", "now", "at", "on",
    # Hindi
    "और", "के", "बारे", "में", "क्या", "भी", "का", "की", "को", "तो", "फिर", "पर", "से",
    # Nepali
    "अनि", "नि", "र", "पनि", "मा", "त", "चाहिँ", "बारे", "बारेमा", "को", "का", "की",
}


def is_fragment(text: str, entity_spans: list[tuple[int, int]]) -> bool:
    """True if the query has at least one entity and nothing else of substance.

    `entity_spans` are (start, end) character offsets of the entities found.
    """
    if not entity_spans:
        return False
    pieces, cursor = [], 0
    for start, end in sorted(entity_spans):
        pieces.append(text[cursor:start])
        cursor = max(cursor, end)
    pieces.append(text[cursor:])

    for word in lookup_key(" ".join(pieces)).split():
        word = word.strip(_PUNCTUATION)
        if word and word not in _FILLER:
            return False
    return True
