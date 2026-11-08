"""Tests for the NER code path.

Like the intent tests, these use a tiny random BERT and a vocabulary built on
the fly: no download, and they check the code, not model quality.
"""

import pytest
import torch
from transformers import BertConfig, BertForTokenClassification, BertTokenizerFast

from backend.core import load_settings
from backend.nlp.dataset.records import read_jsonl
from backend.nlp.evaluation.ner import entity_report
from backend.nlp.ner.model import (
    ID2TAG,
    IGNORE,
    TAG2ID,
    TAGS,
    NerDataset,
    align_tags,
    decode_tags,
    make_collate,
    predict_entities,
)
from backend.nlp.ner.predictor import EntityRecognizer, NerModelNotFound, resolve_model_dir
from backend.nlp.ner.train import record_spans, train_ner_model
from backend.nlp.query.enums import EntityType

SETTINGS = load_settings()
CPU = torch.device("cpu")


@pytest.fixture(scope="module")
def records():
    return read_jsonl(SETTINGS.paths.data_dir / "train.jsonl")[::12]


@pytest.fixture(scope="module")
def tokenizer(tmp_path_factory, records):
    # Character-level WordPiece: every word is split into single characters,
    # so a token boundary exists at every position, including before a
    # Nepali case ending.
    characters = sorted({ch for r in records for ch in r.text if not ch.isspace()})
    vocab = ["[PAD]", "[UNK]", "[CLS]", "[SEP]", "[MASK]"]
    vocab += characters + [f"##{ch}" for ch in characters]
    path = tmp_path_factory.mktemp("vocab") / "vocab.txt"
    path.write_text("\n".join(vocab), encoding="utf-8")
    return BertTokenizerFast(str(path), do_lower_case=False, strip_accents=False)


def tiny_model(tokenizer):
    torch.manual_seed(0)
    return BertForTokenClassification(BertConfig(
        vocab_size=len(tokenizer), hidden_size=32, num_hidden_layers=1,
        num_attention_heads=2, intermediate_size=64, max_position_embeddings=256,
        num_labels=len(TAGS), id2label=ID2TAG, label2id=TAG2ID,
    ))


def test_tag_set_is_bio_over_five_entity_types():
    assert len(TAGS) == 11
    assert TAGS[0] == "O"
    assert "B-LOCATION" in TAGS and "I-CHANGE" in TAGS


def test_align_tags_on_word_tokens():
    #          <s>     What    is      Gangtok   district  rainfall  </s>
    offsets = [(0, 0), (0, 4), (5, 7), (8, 15), (16, 24), (25, 33), (0, 0)]
    spans = [(8, 24, "LOCATION"), (25, 33, "ENV_VARIABLE")]
    tags = [ID2TAG.get(i, "IGNORE") for i in align_tags(offsets, spans)]
    assert tags == ["IGNORE", "O", "O", "B-LOCATION", "I-LOCATION", "B-ENV_VARIABLE", "IGNORE"]


def test_adjacent_entities_of_the_same_type_stay_separate():
    text = "Gangtok Namchi"
    offsets = [(0, 7), (8, 14)]
    spans = [(0, 7, "LOCATION"), (8, 14, "LOCATION")]
    tag_ids = align_tags(offsets, spans)
    assert [ID2TAG[i] for i in tag_ids] == ["B-LOCATION", "B-LOCATION"]
    assert [e.span for e in decode_tags(text, offsets, tag_ids)] == spans


def test_decode_forgives_a_missing_b_tag_and_trims_spaces():
    text = "in  Gangtok now"
    offsets = [(0, 2), (3, 11), (12, 15)]  # middle token includes a leading space
    tag_ids = [TAG2ID["O"], TAG2ID["I-LOCATION"], TAG2ID["O"]]
    (entity,) = decode_tags(text, offsets, tag_ids, [0.9, 0.8, 0.9])
    assert (entity.text, entity.type, entity.confidence) == ("Gangtok", EntityType.LOCATION, 0.8)
    assert text[entity.start:entity.end] == "Gangtok"


def test_nepali_case_ending_stays_outside_the_entity(tokenizer):
    text = "गान्तोकमा तापक्रम कति छ?"
    spans = [(0, 7, "LOCATION"), (10, 17, "ENV_VARIABLE")]
    offsets = tokenizer(text, return_offsets_mapping=True)["offset_mapping"]
    decoded = decode_tags(text, offsets, align_tags(offsets, spans))
    assert [e.span for e in decoded] == spans
    assert decoded[0].text == "गान्तोक"


def test_labels_round_trip_through_tokens_for_real_rows(records, tokenizer):
    for record in records:
        offsets = tokenizer(record.text, return_offsets_mapping=True)["offset_mapping"]
        spans = record_spans(record)
        decoded = decode_tags(record.text, offsets, align_tags(offsets, spans))
        assert sorted(e.span for e in decoded) == sorted(spans), record.id


def test_collate_pads_labels_with_ignore(tokenizer):
    dataset = NerDataset(
        ["rain in Gangtok", "What is the temperature in North Sikkim today?"],
        [[(0, 4, "ENV_VARIABLE"), (8, 15, "LOCATION")], []],
        tokenizer, max_length=128,
    )
    batch = make_collate(tokenizer)([dataset[0], dataset[1]])
    assert batch["labels"].shape == batch["input_ids"].shape
    short_length = len(dataset[0]["input_ids"])
    assert (batch["labels"][0, short_length:] == IGNORE).all()
    assert batch["labels"][0, 0] == IGNORE  # [CLS]
    assert batch["labels"][0, 1] == TAG2ID["B-ENV_VARIABLE"]


def test_entity_report_requires_exact_boundaries_and_type():
    gold = [[(0, 7, "LOCATION"), (10, 17, "ENV_VARIABLE")], [(0, 5, "DISASTER")]]
    predicted = [[(0, 9, "LOCATION"), (10, 17, "ENV_VARIABLE")], [(0, 5, "DISASTER")]]
    report = entity_report(gold, predicted)
    assert report["overall"]["correct"] == 2
    assert report["overall"]["precision"] == pytest.approx(2 / 3)
    assert report["per_type"]["LOCATION"]["f1"] == 0.0
    assert report["per_type"]["DISASTER"]["f1"] == 1.0
    assert report["text_exact_match"] == 0.5


@pytest.fixture(scope="module")
def trained(tmp_path_factory, records, tokenizer):
    config = SETTINGS.ner.model_copy(update={
        "max_epochs": 3, "patience": 3, "learning_rate": 3e-3, "max_length": 128,
    })
    output_dir = tmp_path_factory.mktemp("ner") / "seed_0"
    return train_ner_model(
        records, records[:40], tokenizer, tiny_model(tokenizer), config, 0, output_dir, CPU
    )


def test_training_loop_runs_and_reduces_loss(trained):
    losses = [epoch["train_loss"] for epoch in trained.history]
    assert len(losses) == 3
    assert losses[-1] < losses[0]
    assert "val_entity_f1" in trained.history[0]


def test_reloaded_checkpoint_returns_well_formed_entities(trained):
    recognizer = EntityRecognizer.load(trained.output_dir, 128)
    texts = ["What is the rainfall in Gangtok?", "गान्तोकमा तापक्रम कति छ?", "Hello"]
    results = recognizer.predict(texts)
    assert len(results) == 3
    for text, entities in zip(texts, results):
        for entity in entities:
            assert text[entity.start:entity.end] == entity.text
            assert 0.0 <= entity.confidence <= 1.0
        starts = [e.start for e in entities]
        assert starts == sorted(starts)
    assert results == recognizer.predict(texts)  # deterministic


def test_predict_entities_handles_empty_input(tokenizer):
    assert predict_entities(tiny_model(tokenizer), tokenizer, [], 64, 8, CPU) == []


def test_missing_model_gives_helpful_errors(tmp_path):
    with pytest.raises(NerModelNotFound):
        EntityRecognizer.load(tmp_path, 64)
    settings = SETTINGS.model_copy(update={
        "paths": SETTINGS.paths.model_copy(update={"models_dir": tmp_path})
    })
    with pytest.raises(NerModelNotFound, match="train_ner"):
        resolve_model_dir(settings)
