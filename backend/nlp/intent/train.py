"""Fine-tuning for the intent classifier."""

from pathlib import Path

import torch
from sklearn.metrics import f1_score
from torch.utils.data import DataLoader
from transformers import AutoModelForSequenceClassification, AutoTokenizer

from backend.core.config import IntentConfig
from backend.core.seed import set_seed
from backend.nlp.dataset.records import DatasetRecord
from backend.nlp.intent.model import (
    ID2LABEL,
    LABEL2ID,
    LABELS,
    IntentDataset,
    make_collate,
    predict_probabilities,
)
from backend.nlp.training.loop import TrainResult, fine_tune, pick_device


def load_pretrained(model_name: str):
    """Download (or load from cache) an encoder and attach a fresh
    classification head with one output per intent."""
    tokenizer = AutoTokenizer.from_pretrained(model_name)
    model = AutoModelForSequenceClassification.from_pretrained(
        model_name, num_labels=len(LABELS), id2label=ID2LABEL, label2id=LABEL2ID
    )
    return tokenizer, model


def _class_weights(labels: list[str], device: torch.device) -> torch.Tensor:
    """Inverse-frequency weights: rare classes count more in the loss."""
    counts = torch.tensor([labels.count(label) for label in LABELS], dtype=torch.float)
    weights = counts.sum() / (len(LABELS) * counts.clamp(min=1))
    return weights.to(device)


def train_intent_model(
    train_records: list[DatasetRecord],
    val_records: list[DatasetRecord],
    tokenizer,
    model,
    config: IntentConfig,
    seed: int,
    output_dir: Path,
    device: torch.device | None = None,
) -> TrainResult:
    """Fine-tune `model` and save the best epoch by validation macro-F1."""
    set_seed(seed)
    device = device or pick_device()

    train_texts = [r.text for r in train_records]
    train_labels = [r.intent.value for r in train_records]
    val_texts = [r.text for r in val_records]
    val_labels = [r.intent.value for r in val_records]

    loader = DataLoader(
        IntentDataset(train_texts, train_labels, tokenizer, config.max_length),
        batch_size=config.batch_size,
        shuffle=True,
        collate_fn=make_collate(tokenizer),
        generator=torch.Generator().manual_seed(seed),
    )
    loss_fn = torch.nn.CrossEntropyLoss(
        weight=_class_weights(train_labels, device) if config.class_weighting else None
    )

    def score() -> dict:
        probabilities = predict_probabilities(
            model, tokenizer, val_texts, config.max_length, config.batch_size * 4, device
        )
        predicted = [LABELS[i] for i in probabilities.argmax(axis=1)]
        macro_f1 = float(f1_score(val_labels, predicted, labels=LABELS, average="macro",
                                  zero_division=0))
        accuracy = sum(p == t for p, t in zip(predicted, val_labels)) / len(val_labels)
        # Macro-F1 is the selection metric: accuracy can hide a class the
        # model never predicts.
        return {"score": macro_f1, "val_macro_f1": macro_f1, "val_accuracy": accuracy}

    return fine_tune(model, tokenizer, loader, loss_fn, score, config, output_dir, device,
                     label=f"intent seed {seed}")


def load_finetuned(model_dir: Path):
    """Load a checkpoint written by train_intent_model."""
    tokenizer = AutoTokenizer.from_pretrained(model_dir)
    model = AutoModelForSequenceClassification.from_pretrained(model_dir)
    return tokenizer, model
