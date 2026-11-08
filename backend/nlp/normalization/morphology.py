"""Hindi and Nepali word endings shared by the normaliser and the time rules."""

# Nepali case endings and the plural marker attach directly to the noun.
# Longest first, so "हरूको" is tried before "को".
ATTACHED_ENDINGS: list[str] = sorted(
    ["हरूको", "हरूमा", "हरूले", "हरू", "मध्ये", "भित्र", "भन्दा", "बाट", "लाई", "सँग", "सम्म",
     "देखि", "तिर", "को", "का", "की", "मा", "ले"],
    key=len, reverse=True,
)

# Hindi postpositions are separate words; NER sometimes includes one in a span.
TRAILING_WORDS: set[str] = {"में", "का", "की", "के", "से", "को", "पर", "तक", "ने"}
