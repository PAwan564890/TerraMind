import random

import pytest

from backend.core import load_settings
from backend.core.config import DatasetConfig
from backend.nlp.dataset.generator import (
    SLOT_RE,
    build_pools,
    fill_template,
    generate,
    load_families,
    load_lexicon,
)
from backend.nlp.dataset.records import load_gold, read_jsonl
from backend.nlp.dataset.validate import validate_records
from backend.nlp.ontology import get_ontology
from backend.nlp.query.enums import EntityType, Intent, Language, Status
from backend.nlp.query.intents import INTENT_SPECS

SETTINGS = load_settings()
ONTOLOGY = get_ontology()
DATA_DIR = SETTINGS.paths.data_dir


@pytest.fixture(scope="module")
def records():
    return generate(ONTOLOGY, SETTINGS.dataset, SETTINGS.project.seed)


@pytest.fixture(scope="module")
def pools():
    return build_pools(ONTOLOGY, load_lexicon())


def test_generated_dataset_has_no_integrity_errors(records):
    report = validate_records(records, ONTOLOGY)
    assert report.errors == []
    assert report.warnings == []


def test_generation_is_deterministic(records):
    again = generate(ONTOLOGY, SETTINGS.dataset, SETTINGS.project.seed)
    assert again == records


def test_files_on_disk_match_the_generator(records):
    # If this fails, rerun scripts/generate_dataset.py and commit the result.
    on_disk = [
        *read_jsonl(DATA_DIR / "train.jsonl"),
        *read_jsonl(DATA_DIR / "val.jsonl"),
        *read_jsonl(DATA_DIR / "test" / "test.jsonl"),
    ]
    assert sorted(on_disk, key=lambda r: r.id) == sorted(records, key=lambda r: r.id)


def test_no_template_family_crosses_a_split(records):
    splits_by_group = {}
    for r in records:
        splits_by_group.setdefault(r.group_id, set()).add(r.split)
    assert all(len(splits) == 1 for splits in splits_by_group.values())


def test_no_text_is_shared_between_splits(records):
    train = {r.text for r in records if r.split == "train"}
    held = {r.text for r in records if r.split != "train"}
    assert train.isdisjoint(held)


def test_entity_offsets_point_at_the_entity_text(records):
    for r in records:
        for e in r.entities:
            assert r.text[e.start:e.end] == e.text, r.id


def test_heldout_locations_appear_only_in_test(records):
    heldout = set(load_lexicon()["heldout_locations"])
    seen_in_test = set()
    for r in records:
        for e in r.entities:
            if e.type is EntityType.LOCATION and e.normalized in heldout:
                assert r.split == "test", r.id
                seen_in_test.add(e.normalized)
    assert seen_in_test == heldout


def test_languages_are_balanced_within_each_intent(records):
    for intent in Intent:
        counts = [
            sum(r.intent is intent and r.language is language for r in records)
            for language in Language
        ]
        assert max(counts) <= 1.25 * min(counts), (intent, counts)


def test_family_operations_are_allowed_for_their_intent():
    for intent, families in load_families().items():
        for family in families:
            if intent is Intent.OUT_OF_DOMAIN:
                assert family.operation is None, family.id
            else:
                assert family.operation in INTENT_SPECS[intent].allowed_operations, family.id


def test_every_template_slot_has_a_pool(pools):
    for families in load_families().values():
        for family in families:
            for language in Language:
                for template in family.templates(language):
                    for slot, _ in SLOT_RE.findall(template):
                        assert slot in pools, (family.id, slot)


def test_fill_template_labels_suffixed_nepali_location(pools):
    # The Nepali case suffix "मा" is attached to the place name but must stay
    # outside the entity span.
    text, spans, _ = fill_template(
        "{loc}मा {cvar} कति छ?", Language.NE, "train", pools, DatasetConfig(), random.Random(0)
    )
    location = spans[0]
    assert location.type is EntityType.LOCATION
    assert text[location.end:location.end + 2] == "मा"
    assert ONTOLOGY.lookup_location(location.text).id == location.normalized


def test_repeated_slot_gets_two_different_values(pools):
    rng = random.Random(1)
    for _ in range(50):
        _, spans, _ = fill_template(
            "Compare {cvar} in {loc} and {loc2}.", Language.EN, "train", pools, DatasetConfig(), rng
        )
        places = [s.normalized for s in spans if s.type is EntityType.LOCATION]
        assert len(set(places)) == 2


def test_gold_set_is_valid_and_parallel():
    gold = load_gold(DATA_DIR / "test" / "gold.yaml", ONTOLOGY)
    assert len(gold) % 3 == 0
    assert {g.language for g in gold} == set(Language)
    assert {g.expected.status for g in gold} == set(Status)
    in_domain = {g.expected.intent for g in gold}
    assert in_domain == set(Intent)


def test_gold_text_never_appears_in_generated_data(records):
    generated = {r.text for r in records}
    for name in ("gold.yaml", "gold_v2.yaml"):
        gold = load_gold(DATA_DIR / "test" / name, ONTOLOGY)
        leaked = [g.text for g in gold if g.text in generated]
        assert leaked == [], name
