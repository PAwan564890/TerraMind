"""Maps an entity span found by NER to its canonical value.

Locations, variables and disasters go through a cascade, cheapest and most
certain step first:
    1. exact alias match
    2. match after removing case endings / postpositions
    3. fuzzy string match (spelling mistakes), above a threshold
    4. embedding similarity to an alias (synonyms such as "cold"), for
       variables and disasters only, and only if a matcher is supplied
If nothing matches, the entity stays unresolved. It is never guessed.

Time and change expressions are parsed by rules.
"""

import difflib
import re
from typing import Any, Literal

from pydantic import BaseModel

from backend.core.config import NormalizationConfig
from backend.nlp.normalization.change_parser import ChangeValue, parse_change
from backend.nlp.normalization.morphology import ATTACHED_ENDINGS, TRAILING_WORDS
from backend.nlp.normalization.time_parser import parse_time
from backend.nlp.ontology import Ontology
from backend.nlp.preprocessing import lookup_key
from backend.nlp.query.enums import Disaster, EntityType, Language, Variable
from backend.nlp.query.schema import LocationRef, TimePeriod

Method = Literal["exact", "suffix", "fuzzy", "embedding", "rule", "none"]

_ATTACHED_ENDINGS = ATTACHED_ENDINGS
_TRAILING_WORDS = TRAILING_WORDS
_LEADING_WORDS = {"the"}
# Words that may sit between or beside place names inside one NER span.
_CONNECTING_WORDS = TRAILING_WORDS | {
    "the", "in", "near", "around", "and", "or", "to", "from",
    "और", "या", "आसपास", "पास",
    "र", "कि", "वरपर", "वरपरका", "नजिक",
}

# Reward for the certainty of each step, used as the confidence of the match.
_METHOD_CONFIDENCE = {"exact": 1.0, "suffix": 0.95}


class Resolution(BaseModel):
    """Result of normalising one entity."""

    # May differ from the NER label: "flood" tagged as a variable is corrected.
    type: EntityType
    value: LocationRef | Variable | Disaster | TimePeriod | ChangeValue | None = None
    # String form for the API's `normalized` field; None when unresolved.
    canonical: str | None = None
    method: Method = "none"
    confidence: float = 0.0

    @property
    def resolved(self) -> bool:
        return self.value is not None


def stripped_variants(key: str) -> list[str]:
    """Forms of a lookup key with endings removed, most conservative first.
    The unchanged key is not included."""
    variants: list[str] = []

    def add(candidate: str) -> None:
        candidate = candidate.strip(" .,?!।'\"")
        if candidate and candidate != key and candidate not in variants:
            variants.append(candidate)

    add(key)  # punctuation only
    words = key.split()
    while len(words) > 1 and words[-1] in _TRAILING_WORDS:
        words = words[:-1]
        add(" ".join(words))
    if len(words) > 1 and words[0] in _LEADING_WORDS:
        add(" ".join(words[1:]))
    if key.endswith("'s"):
        add(key[:-2])

    # Up to two attached endings, e.g. "सहरहरूको" -> "सहरहरू" -> "सहर".
    frontier = [key, *variants]
    for _ in range(2):
        next_frontier = []
        for form in frontier:
            for ending in _ATTACHED_ENDINGS:
                if form.endswith(ending) and len(form) > len(ending) + 1:
                    stripped = form[: -len(ending)]
                    if stripped not in variants:
                        add(stripped)
                        next_frontier.append(stripped)
        frontier = next_frontier
    return variants


def canonical_time(period: TimePeriod) -> str:
    if period.value is not None:
        return f"{period.type.value}:{period.value}:{period.unit.value}"
    if period.start is not None:
        return f"{period.type.value}:{period.start.isoformat()}:{period.end.isoformat()}"
    return period.type.value


def canonical_change(change: ChangeValue) -> str:
    return f"{change.change:g}:{change.unit.value}"


class EntityNormalizer:
    def __init__(self, ontology: Ontology, config: NormalizationConfig,
                 alias_matcher=None) -> None:
        """`alias_matcher` is an optional embeddings.AliasMatcher. Without it
        the normaliser needs no neural model at all."""
        self._ontology = ontology
        self._config = config
        self._alias_matcher = alias_matcher

    def normalize(self, text: str, entity_type: EntityType, context: str = "",
                  language: Language | None = None) -> Resolution:
        """Resolve one entity. `context` is the full query text; `language`
        is the detected language of the query, if known."""
        if entity_type is EntityType.TIME:
            parsed = parse_time(text, context, language=language)
            if parsed is None:
                return Resolution(type=entity_type)
            return Resolution(type=entity_type, value=parsed.period,
                              canonical=canonical_time(parsed.period),
                              method="rule", confidence=parsed.confidence)

        if entity_type is EntityType.CHANGE:
            change = parse_change(text)
            if change is None:
                return Resolution(type=entity_type)
            return Resolution(type=entity_type, value=change,
                              canonical=canonical_change(change),
                              method="rule", confidence=1.0)

        if entity_type is EntityType.LOCATION:
            return self._resolve(text, entity_type, self._ontology.location_index)
        return self._resolve(text, entity_type, self._ontology.concept_index)

    def split_locations(self, text: str) -> list[tuple[int, int, Resolution]] | None:
        """Recover the places inside a location span that did not resolve whole.

        NER sometimes draws one span around two neighbouring names
        ("मंगन नामची") or around a name and the word beside it
        ("लाचेन वरपर", "around Lachen"). Looked up whole, such a span matches
        nothing and the user is asked about a place they named correctly.

        Returns (start, end, resolution) for each place found, with offsets
        relative to `text`, or None. It succeeds only if EVERY word of the span
        is part of a known place or a connecting word. One unexplained word
        fails the whole span, so a genuinely unknown place ("Siliguri Gangtok")
        still produces a question rather than being silently dropped.
        Spelling correction is not applied to the pieces.
        """
        words = [(m.start(), m.end()) for m in re.finditer(r"\S+", text)]
        if len(words) < 2:
            return None
        parts: list[tuple[int, int, Resolution]] = []
        i = 0
        while i < len(words):
            for j in range(len(words), i, -1):  # longest run of words first
                start, end = words[i][0], words[j - 1][1]
                resolution = self._resolve(text[start:end], EntityType.LOCATION,
                                           self._ontology.location_index, fuzzy=False)
                if resolution.resolved:
                    parts.append((start, end, resolution))
                    i = j
                    break
            else:
                word = lookup_key(text[words[i][0]:words[i][1]]).strip(" .,?!।'\"")
                if word not in _CONNECTING_WORDS:
                    return None
                i += 1
        return parts or None

    def _resolve(self, text: str, entity_type: EntityType, index: dict[str, str],
                 fuzzy: bool = True) -> Resolution:
        key = lookup_key(text)

        if key in index:
            return self._found(index[key], entity_type, "exact", _METHOD_CONFIDENCE["exact"])

        variants = stripped_variants(key)
        for variant in variants:
            if variant in index:
                return self._found(index[variant], entity_type, "suffix",
                                   _METHOD_CONFIDENCE["suffix"])

        match = self._fuzzy([key, *variants], index) if fuzzy else None
        if match is not None:
            return self._found(match[0], entity_type, "fuzzy", match[1])

        if self._alias_matcher is not None and entity_type is not EntityType.LOCATION:
            match = self._alias_matcher.match(text)
            if match is not None:
                return self._found(match[0], entity_type, "embedding", match[1])
        return Resolution(type=entity_type)

    def _fuzzy(self, forms: list[str], index: dict[str, str]) -> tuple[str, float] | None:
        """Closest alias by character similarity, if clearly above the threshold."""
        best: dict[str, float] = {}  # canonical id -> best similarity
        for form in forms:
            if len(form) < self._config.fuzzy_min_chars:
                continue
            # Compare only against aliases in the same script.
            candidates = [alias for alias in index if alias[0].isascii() == form[0].isascii()]
            for alias in difflib.get_close_matches(
                form, candidates, n=3, cutoff=self._config.fuzzy_threshold
            ):
                similarity = difflib.SequenceMatcher(None, form, alias).ratio()
                best[index[alias]] = max(best.get(index[alias], 0.0), similarity)

        if not best:
            return None
        ranked = sorted(best.items(), key=lambda item: item[1], reverse=True)
        # Two different places almost equally close: refuse to choose.
        if len(ranked) > 1 and ranked[0][1] - ranked[1][1] < self._config.fuzzy_margin:
            return None
        return ranked[0]

    def _found(self, found_id: str, entity_type: EntityType, method: Method,
               confidence: float) -> Resolution:
        value: Any
        if found_id in self._ontology.locations:
            value, resolved_type = self._ontology.location_ref(found_id), EntityType.LOCATION
        elif found_id in Variable:
            value, resolved_type = Variable(found_id), EntityType.ENV_VARIABLE
        else:
            value, resolved_type = Disaster(found_id), EntityType.DISASTER
        return Resolution(type=resolved_type, value=value, canonical=found_id,
                          method=method, confidence=confidence)
