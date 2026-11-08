"""Builds parallel queries: the same meaning in English, Hindi and Nepali.

Used only to evaluate cross-language retrieval. Each template family is
filled once with the SAME canonical values (same place, same variable, same
time span) in all three languages; only the surface words differ.
"""

import random

from backend.nlp.dataset.generator import SLOT_RE, Family, Pools, SlotValue, load_families
from backend.nlp.query.enums import Intent, Language


def _counterpart(
    slot: str, chosen: SlotValue, key: str, language: Language, pools: Pools,
    rng: random.Random,
) -> SlotValue | None:
    """A value in `language` that means the same as the English `chosen`."""
    pool = pools[slot][language]
    if key in pool and chosen.entity_type is not None and isinstance(chosen.normalized, str):
        return rng.choice(pool[key])  # ontology slot: keys are canonical IDs
    if chosen.entity_type is not None:
        # Time and change: match on the normalised value.
        same = [v for values in pool.values() for v in values
                if v.normalized == chosen.normalized]
        return rng.choice(same) if same else None
    # Out-of-domain vocabulary lists are written in the same order per language.
    english_keys = list(pools[slot][Language.EN])
    target_keys = list(pool)
    index = english_keys.index(key)
    return pool[target_keys[index]][0] if index < len(target_keys) else None


def make_triple(family: Family, pools: Pools, rng: random.Random) -> dict[Language, str] | None:
    """One parallel triple from a family, or None if it cannot be aligned."""
    templates = {language: family.templates(language)[0] for language in Language}
    slots = {language: sorted(SLOT_RE.findall(t)) for language, t in templates.items()}
    if not slots[Language.EN] or len({tuple(s) for s in slots.values()}) != 1:
        return None  # no slots, or the languages use different slots

    values: dict[tuple[str, str], dict[Language, SlotValue]] = {}
    used: dict[str, set[str]] = {}
    for slot, digit in slots[Language.EN]:
        english_pool = pools[slot][Language.EN]
        keys = [k for k in english_pool
                if k not in used.setdefault(slot, set()) and not english_pool[k][0].heldout]
        key = rng.choice(keys)
        used[slot].add(key)
        chosen = rng.choice(english_pool[key])
        per_language = {Language.EN: chosen}
        for language in (Language.HI, Language.NE):
            counterpart = _counterpart(slot, chosen, key, language, pools, rng)
            if counterpart is None:
                return None
            per_language[language] = counterpart
        values[(slot, digit)] = per_language

    return {
        language: SLOT_RE.sub(lambda m: values[(m.group(1), m.group(2))][language].text, template)
        for language, template in templates.items()
    }


def make_parallel_set(pools: Pools, count: int, seed: int) -> list[dict[Language, str]]:
    """`count` distinct triples, drawn evenly from the in-domain families."""
    rng = random.Random(seed)
    families = [f for intent, group in load_families().items()
                if intent is not Intent.OUT_OF_DOMAIN for f in group]
    triples, seen = [], set()
    attempts = 0
    while len(triples) < count and attempts < count * 20:
        attempts += 1
        triple = make_triple(families[attempts % len(families)], pools, rng)
        if triple is not None and triple[Language.EN] not in seen:
            seen.add(triple[Language.EN])
            triples.append(triple)
    return triples
