"""Tests for the intent classifier code path.

They use a tiny randomly initialised BERT and a character-level vocabulary
built on the fly, so they need no download and run in seconds. They check the
training loop, checkpointing and inference wrapper, not model quality.
"""

import json

import pytest
import torch
from transformers import BertConfig, BertForSequenceClassification, BertTokenizerFast

from backend.core import load_settings
from backend.nlp.dataset.records import read_jsonl
from backend.nlp.intent.model import (
    ID2LABEL,
    LABEL2ID,
    LABELS,
    IntentDataset,
    make_collate,
    predict_probabilities,
)
from backend.nlp.intent.predictor import IntentClassifier, IntentModelNotFound, resolve_model_dir
from backend.nlp.intent.train import train_intent_model
from backend.nlp.query.enums import Intent

SETTINGS = load_settings()
CPU = torch.device("cpu")


@pytest.fixture(scope="module")
def records():
    rows = read_jsonl(SETTINGS.paths.data_dir / "train.jsonl")
    # Two easily separable intents keep the tiny model's job simple.
    chosen = [r for r in rows if r.intent in (Intent.WEATHER_QUERY, Intent.OUT_OF_DOMAIN)]
    return chosen[::4]


@pytest.fixture(scope="module")
def tokenizer(tmp_path_factory, records):
    characters = sorted({ch for r in records for ch in r.text if not ch.isspace()})
    vocab = ["[PAD]", "[UNK]", "[CLS]", "[SEP]", "[MASK]"]
    vocab += characters + [f"##{ch}" for ch in characters]
    path = tmp_path_factory.mktemp("vocab") / "vocab.txt"
    path.write_text("\n".join(vocab), encoding="utf-8")
    return BertTokenizerFast(str(path), do_lower_case=False, strip_accents=False)


def tiny_model(tokenizer):
    torch.manual_seed(0)
    return BertForSequenceClassification(BertConfig(
        vocab_size=len(tokenizer), hidden_size=32, num_hidden_layers=1,
        num_attention_heads=2, intermediate_size=64, max_position_embeddings=128,
        num_labels=len(LABELS), id2label=ID2LABEL, label2id=LABEL2ID,
    ))


@pytest.fixture(scope="module")
def trained(tmp_path_factory, records, tokenizer):
    config = SETTINGS.intent.model_copy(update={
        "max_epochs": 4, "patience": 4, "learning_rate": 3e-3, "batch_size": 16,
    })
    output_dir = tmp_path_factory.mktemp("intent") / "seed_0"
    result = train_intent_model(
        records, records, tokenizer, tiny_model(tokenizer), config, 0, output_dir, CPU
    )
    return result


def test_labels_follow_the_intent_enum():
    assert LABELS == [intent.value for intent in Intent]
    assert len(LABELS) == 9
    assert LABEL2ID["OUT_OF_DOMAIN"] == 8


def test_batches_are_padded_to_their_own_longest_item(tokenizer):
    dataset = IntentDataset(
        ["And the rain?", "What is the temperature in Gangtok right now?"],
        ["WEATHER_QUERY", "WEATHER_QUERY"], tokenizer, max_length=64,
    )
    batch = make_collate(tokenizer)([dataset[0], dataset[1]])
    longest = max(len(dataset[0]["input_ids"]), len(dataset[1]["input_ids"]))
    assert batch["input_ids"].shape == (2, longest)
    assert batch["labels"].tolist() == [0, 0]
    # The shorter item is padded, and the attention mask hides the padding.
    assert batch["attention_mask"][0].sum() < batch["attention_mask"][1].sum()


def test_long_queries_are_truncated(tokenizer):
    dataset = IntentDataset(["rain " * 200], ["WEATHER_QUERY"], tokenizer, max_length=16)
    assert len(dataset[0]["input_ids"]) == 16


def test_training_loop_runs_and_reduces_loss(trained):
    # A random one-layer model cannot learn the task in a few steps; this only
    # checks that the loop optimises, tracks history and picks a best epoch.
    # Model quality is measured by scripts/train_intent.py on a real encoder.
    losses = [epoch["train_loss"] for epoch in trained.history]
    assert len(losses) == 4
    assert losses[-1] < losses[0]
    assert 1 <= trained.best_epoch <= 4


def test_checkpoint_contains_model_tokenizer_and_label_map(trained):
    files = {p.name for p in trained.output_dir.iterdir()}
    assert "config.json" in files
    assert "model.safetensors" in files
    assert "tokenizer.json" in files or "vocab.txt" in files
    saved = json.loads((trained.output_dir / "config.json").read_text(encoding="utf-8"))
    assert saved["id2label"]["0"] == "WEATHER_QUERY"


def test_reloaded_checkpoint_predicts_valid_distributions(trained):
    classifier = IntentClassifier.load(trained.output_dir, SETTINGS.intent.max_length)
    predictions = classifier.predict(["What is the rainfall in Gangtok?", "Tell me a joke."])
    assert len(predictions) == 2
    for prediction in predictions:
        assert isinstance(prediction.label, Intent)
        assert prediction.ranked[0] == (prediction.label, prediction.confidence)
        assert len(prediction.ranked) == 9
        assert sum(p for _, p in prediction.ranked) == pytest.approx(1.0, abs=1e-4)


def test_reloading_twice_gives_identical_predictions(trained):
    texts = ["What is the rainfall in Gangtok?", "गंगटोक में तापमान का स्तर क्या है?"]
    first = IntentClassifier.load(trained.output_dir, 64).predict(texts)
    second = IntentClassifier.load(trained.output_dir, 64).predict(texts)
    assert first == second


def test_predict_probabilities_handles_empty_input(tokenizer):
    result = predict_probabilities(tiny_model(tokenizer), tokenizer, [], 64, 8, CPU)
    assert result.shape == (0, 9)


def test_missing_model_gives_helpful_errors(tmp_path):
    with pytest.raises(IntentModelNotFound):
        IntentClassifier.load(tmp_path, 64)
    settings = SETTINGS.model_copy(update={
        "paths": SETTINGS.paths.model_copy(update={"models_dir": tmp_path})
    })
    with pytest.raises(IntentModelNotFound, match="train_intent"):
        resolve_model_dir(settings)
