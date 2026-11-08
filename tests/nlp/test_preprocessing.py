import pytest

from backend.core import load_settings
from backend.nlp.dataset.records import load_gold, read_jsonl
from backend.nlp.ontology import get_ontology
from backend.nlp.preprocessing import (
    InvalidQueryError,
    lookup_key,
    normalize_query,
    prepare_query,
)

SETTINGS = load_settings()
MAX_CHARS = SETTINGS.input.max_query_chars


def test_whitespace_is_collapsed_and_trimmed():
    assert normalize_query("  What is\tthe   rainfall\nin Gangtok ?  ") == (
        "What is the rainfall in Gangtok?"
    )


def test_non_breaking_and_other_unicode_spaces_become_plain_spaces():
    assert normalize_query("गंगटोक में बारिश") == "गंगटोक में बारिश"


def test_invisible_characters_are_removed():
    # zero-width space, byte-order mark, soft hyphen
    assert normalize_query("rain​fall ﻿in Gang­tok") == "rainfall in Gangtok"


def test_zero_width_joiners_are_kept_in_devanagari():
    word = "गर्‍यो"
    assert normalize_query(word) == word


def test_nukta_forms_become_identical():
    precomposed = "बाढ़"            # single code point: DDHA with nukta
    combining = "बाढ़"        # DDHA followed by combining nukta
    assert precomposed != combining
    assert normalize_query(precomposed) == normalize_query(combining)


def test_punctuation_variants_are_unified():
    assert normalize_query("“Gangtok’s” rainfall — 20％…") == '"Gangtok\'s" rainfall - 20%...'
    assert normalize_query("बारिश कितनी है॥") == "बारिश कितनी है।"
    assert normalize_query("तापमान कितना है ???") == "तापमान कितना है?"


def test_words_case_and_digits_are_untouched():
    text = "What is the NDVI in North Sikkim over the last 5 years"
    assert normalize_query(text) == text
    # Devanagari digits and function words stay as typed.
    assert normalize_query("गान्तोकमा १० प्रतिशत") == "गान्तोकमा १० प्रतिशत"
    assert normalize_query("गंगटोक में बारिश का रुझान") == "गंगटोक में बारिश का रुझान"


@pytest.mark.parametrize(
    "text",
    [
        "  What   is the “rainfall” in Gangtok ??",
        "गंगटोक में बारिश का क्या रुझान रहा है ।।",
        "गान्तोकमा​ वर्षा कति छ?",
    ],
)
def test_normalisation_is_idempotent(text):
    once = normalize_query(text)
    assert normalize_query(once) == once


def test_lookup_key_ignores_case_and_joiners():
    assert lookup_key("  North   SIKKIM ") == "north sikkim"
    assert lookup_key("गर्‍यो") == lookup_key("गर्यो")


def test_prepare_query_returns_normalised_text():
    assert prepare_query("  गंगटोक में   बारिश ?", MAX_CHARS) == "गंगटोक में बारिश?"


@pytest.mark.parametrize(
    "raw, code",
    [
        ("", "empty"),
        ("   \n\t ", "empty"),
        ("​﻿", "empty"),
        ("???", "no_content"),
        ("।।। --", "no_content"),
        ("a" * (MAX_CHARS + 1), "too_long"),
        (None, "empty"),
    ],
)
def test_prepare_query_rejects_unusable_input(raw, code):
    with pytest.raises(InvalidQueryError) as error:
        prepare_query(raw, MAX_CHARS)
    assert error.value.code == code


def test_length_limit_applies_after_normalisation():
    padded = "rainfall in Gangtok" + " " * (MAX_CHARS * 2)
    assert prepare_query(padded, MAX_CHARS) == "rainfall in Gangtok"


def test_digits_only_query_is_accepted():
    # "20%" is a meaningful follow-up in a scenario conversation.
    assert prepare_query("20%", MAX_CHARS) == "20%"


def test_dataset_and_gold_text_are_already_normalised():
    # Entity offsets in the training data are only valid if the pipeline's
    # normaliser leaves that text unchanged.
    data_dir = SETTINGS.paths.data_dir
    rows = [
        *read_jsonl(data_dir / "train.jsonl"),
        *read_jsonl(data_dir / "val.jsonl"),
        *read_jsonl(data_dir / "test" / "test.jsonl"),
    ]
    assert all(normalize_query(r.text) == r.text for r in rows)
    gold = load_gold(data_dir / "test" / "gold.yaml", get_ontology())
    assert all(normalize_query(g.text) == g.text for g in gold)
