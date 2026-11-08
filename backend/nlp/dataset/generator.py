"""Generates the labelled query dataset from template families.

Pipeline: load families -> assign each family to a split -> fill every
template's slots with sampled values, recording the character span of each
filled slot as an entity label -> apply light noise.

Everything is driven by one seeded random generator, so the same config
always produces byte-identical files.
"""

import random
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict, Field

from backend.core.config import DatasetConfig
from backend.nlp.dataset.records import DatasetRecord, SpanLabel, Split
from backend.nlp.ontology import Ontology
from backend.nlp.query.enums import (
    Direction,
    EntityType,
    Intent,
    Language,
    LocationType,
    Operation,
    Variable,
)

DATASET_DIR = Path(__file__).resolve().parent
TEMPLATES_PATH = DATASET_DIR / "templates.yaml"
LEXICON_PATH = DATASET_DIR / "lexicon.yaml"

# {loc} or {loc2}: a slot name, optionally followed by one digit.
SLOT_RE = re.compile(r"\{([a-z]+)(\d?)\}")

V = Variable
CLIMATE_VARS = [V.TEMPERATURE, V.PRECIPITATION, V.HUMIDITY, V.WIND_SPEED, V.AIR_QUALITY]
VARIABLE_SLOTS: dict[str, list[Variable]] = {
    "cvar": CLIMATE_VARS,
    "temp": [V.TEMPERATURE],
    "ndvi": [V.NDVI],
    "vvar": [V.NDVI, V.LAND_COVER],
    "gvar": [V.ELEVATION, V.SLOPE],
    "elev": [V.ELEVATION],
    "var": [*CLIMATE_VARS, V.NDVI, V.SOIL_MOISTURE, V.LAND_COVER, V.LAND_SURFACE_TEMPERATURE],
}
# Slots filled with descriptors ("cold", "humid") instead of nouns.
DESCRIPTOR_SLOTS: dict[str, list[Variable]] = {
    "tdesc": [V.TEMPERATURE],
    "hdesc": [V.HUMIDITY],
    "desc": [V.TEMPERATURE, V.HUMIDITY],
}
LOCATION_SLOTS: dict[str, set[LocationType]] = {
    "loc": {LocationType.STATE, LocationType.DISTRICT, LocationType.TOWN},
    "town": {LocationType.TOWN},
    "district": {LocationType.DISTRICT},
    "river": {LocationType.RIVER},
}


class Family(BaseModel):
    """One meaning, phrased independently in each language."""

    model_config = ConfigDict(extra="forbid")

    id: str
    operation: Operation | None = None
    direction: Direction | None = None
    # Pins the family to one split instead of assigning it at random.
    split: Split | None = None
    en: list[str] = Field(min_length=1)
    hi: list[str] = Field(min_length=1)
    ne: list[str] = Field(min_length=1)

    def templates(self, language: Language) -> list[str]:
        return getattr(self, language.value)


@dataclass(frozen=True)
class SlotValue:
    text: str
    normalized: str | dict[str, Any]
    entity_type: EntityType | None  # None: the slot is not an entity (OOD words)
    heldout: bool = False


# pools[slot][language][key] -> surface forms of one canonical value.
# Sampling picks a key first, then a surface form, so a concept with many
# aliases is not over-represented.
Pools = dict[str, dict[Language, dict[str, list[SlotValue]]]]


def load_families(path: Path = TEMPLATES_PATH) -> dict[Intent, list[Family]]:
    with path.open(encoding="utf-8") as f:
        raw = yaml.safe_load(f)
    families = {Intent(k): [Family.model_validate(x) for x in v] for k, v in raw.items()}

    seen: set[str] = set()
    for group in families.values():
        for family in group:
            if family.id in seen:
                raise ValueError(f"Duplicate family id: {family.id}")
            seen.add(family.id)
    return families


def load_lexicon(path: Path = LEXICON_PATH) -> dict:
    with path.open(encoding="utf-8") as f:
        return yaml.safe_load(f)


def build_pools(ontology: Ontology, lexicon: dict) -> Pools:
    pools: Pools = {}

    def add(slot: str, language: Language, key: str, value: SlotValue) -> None:
        pools.setdefault(slot, {}).setdefault(language, {}).setdefault(key, []).append(value)

    heldout = set(lexicon["heldout_locations"])
    for slot, types in LOCATION_SLOTS.items():
        for loc_id, entry in ontology.locations.items():
            if entry.type not in types:
                continue
            for language, aliases in entry.aliases.by_language().items():
                for alias in aliases:
                    add(slot, language, loc_id,
                        SlotValue(alias, loc_id, EntityType.LOCATION, loc_id in heldout))

    for slot, variables in VARIABLE_SLOTS.items():
        for variable in variables:
            for language, aliases in ontology.variables[variable].aliases.by_language().items():
                for alias in aliases:
                    add(slot, language, variable.value,
                        SlotValue(alias, variable.value, EntityType.ENV_VARIABLE))

    for slot, variables in DESCRIPTOR_SLOTS.items():
        for variable in variables:
            descriptors = ontology.variables[variable].descriptors.by_language()
            for language, words in descriptors.items():
                for word in words:
                    add(slot, language, variable.value,
                        SlotValue(word, variable.value, EntityType.ENV_VARIABLE))

    for disaster, entry in ontology.disasters.items():
        for language, aliases in entry.aliases.by_language().items():
            for alias in aliases:
                add("dis", language, disaster.value,
                    SlotValue(alias, disaster.value, EntityType.DISASTER))

    for language in Language:
        code = language.value
        time = lexicon["time"]
        for text in time["now"][code]:
            add("now", language, text, SlotValue(text, {"type": "current"}, EntityType.TIME))
        for slot, time_type in (("past", "relative_past"), ("future", "relative_future")):
            for text, value, unit in time[slot][code]:
                norm = {"type": time_type, "value": value, "unit": unit}
                add(slot, language, text, SlotValue(text, norm, EntityType.TIME))
        for text, start, end in time["range"][code]:
            norm = {"type": "date_range", "start": start, "end": end}
            add("range", language, text, SlotValue(text, norm, EntityType.TIME))

        for slot, unit in (("pct", "percent"), ("abs", "absolute")):
            for text, value in lexicon["change"][slot][code]:
                norm = {"change": value, "unit": unit}
                add(slot, language, text, SlotValue(text, norm, EntityType.CHANGE))

        for slot, by_language in lexicon["ood"].items():
            for text in by_language[code]:
                add(slot, language, text, SlotValue(text, text, None))
        for n in range(2, 100):
            add("num", language, str(n), SlotValue(str(n), str(n), None))

    return pools


def assign_splits(
    families: dict[Intent, list[Family]], config: DatasetConfig, rng: random.Random
) -> dict[str, Split]:
    """Give every family one split, stratified by intent."""
    assignment: dict[str, Split] = {}
    for intent, group in families.items():
        assignment.update({family.id: family.split for family in group if family.split})
        ids = [family.id for family in group if not family.split]
        rng.shuffle(ids)
        n_val = max(1, round(len(ids) * config.val_fraction))
        n_test = max(1, round(len(ids) * config.test_fraction))
        if n_val + n_test >= len(ids):
            raise ValueError(f"{intent}: too few families ({len(ids)}) to split")
        for i, family_id in enumerate(ids):
            assignment[family_id] = (
                "test" if i < n_test else "val" if i < n_test + n_val else "train"
            )
    return assignment


def _pick(
    pool: dict[str, list[SlotValue]],
    used_keys: set[str],
    split: Split,
    config: DatasetConfig,
    rng: random.Random,
) -> tuple[str, SlotValue]:
    """Sample one value, never repeating a key already used in this sentence."""
    regular = [k for k, vs in pool.items() if k not in used_keys and not vs[0].heldout]
    heldout = [k for k, vs in pool.items() if k not in used_keys and vs[0].heldout]

    # Held-out places are reachable only from the test split.
    use_heldout = (
        split == "test" and heldout and rng.random() < config.heldout_location_rate
    )
    key = rng.choice(heldout if use_heldout else regular)
    return key, rng.choice(pool[key])


def fill_template(
    template: str,
    language: Language,
    split: Split,
    pools: Pools,
    config: DatasetConfig,
    rng: random.Random,
) -> tuple[str, list[SpanLabel], bool]:
    """Replace every slot and return (text, entity spans, used a held-out place)."""
    parts: list[str] = []
    spans: list[SpanLabel] = []
    used: dict[str, set[str]] = {}
    has_heldout = False
    cursor = 0  # position in the template
    length = 0  # length of the text built so far

    for match in SLOT_RE.finditer(template):
        literal = template[cursor:match.start()]
        parts.append(literal)
        length += len(literal)

        slot = match.group(1)
        if slot not in pools:
            raise ValueError(f"Unknown slot {{{slot}}} in template: {template}")
        key, value = _pick(pools[slot][language], used.setdefault(slot, set()), split, config, rng)
        used[slot].add(key)
        has_heldout = has_heldout or value.heldout

        if value.entity_type is not None:
            spans.append(SpanLabel(
                start=length,
                end=length + len(value.text),
                type=value.entity_type,
                text=value.text,
                normalized=value.normalized,
            ))
        parts.append(value.text)
        length += len(value.text)
        cursor = match.end()

    parts.append(template[cursor:])
    return "".join(parts), spans, has_heldout


def _add_noise(
    text: str, spans: list[SpanLabel], language: Language,
    config: DatasetConfig, rng: random.Random,
) -> tuple[str, list[SpanLabel]]:
    """Mimic casual typing without moving any entity offset."""
    if language is Language.EN and rng.random() < config.lowercase_rate:
        lowered = text.lower()
        if len(lowered) == len(text):
            text = lowered
            spans = [s.model_copy(update={"text": s.text.lower()}) for s in spans]

    last_entity_end = max((s.end for s in spans), default=0)
    if (
        text[-1] in "?.।!"
        and last_entity_end < len(text)
        and rng.random() < config.drop_punctuation_rate
    ):
        text = text[:-1].rstrip()
    return text, spans


def generate(ontology: Ontology, config: DatasetConfig, seed: int) -> list[DatasetRecord]:
    """Build the full dataset. Deterministic for a given config and seed."""
    rng = random.Random(seed)
    families = load_families()
    pools = build_pools(ontology, load_lexicon())
    splits = assign_splits(families, config, rng)

    records: list[DatasetRecord] = []
    seen_texts: set[str] = set()

    for intent, group in families.items():
        for family in group:
            split = splits[family.id]
            for language in Language:
                count = 0
                for template in family.templates(language):
                    has_slots = SLOT_RE.search(template) is not None
                    wanted = config.fills_per_template if has_slots else 1
                    made = 0
                    # Small slot spaces run out of new sentences; stop trying
                    # after a bounded number of attempts.
                    for _ in range(wanted * 5):
                        if made == wanted:
                            break
                        text, spans, heldout = fill_template(
                            template, language, split, pools, config, rng
                        )
                        text, spans = _add_noise(text, spans, language, config, rng)
                        if text in seen_texts:
                            continue
                        seen_texts.add(text)
                        made += 1
                        count += 1
                        records.append(DatasetRecord(
                            id=f"{family.id}.{language.value}.{count:03d}",
                            text=text,
                            language=language,
                            intent=intent,
                            operation=family.operation,
                            direction=family.direction,
                            entities=spans,
                            group_id=family.id,
                            source="template",
                            split=split,
                            heldout_location=heldout,
                        ))
    return records
