"""Fine-tuning for the NER model."""

from pathlib import Path

import torch
from torch.utils.data import DataLoader
from transformers import AutoModelForTokenClassification, AutoTokenizer

from backend.core.config import NerConfig
from backend.core.seed import set_seed
from backend.nlp.dataset.records import DatasetRecord
from backend.nlp.evaluation.ner import entity_report
from backend.nlp.ner.model import (
    ID2TAG,
    IGNORE,
    TAG2ID,
    TAGS,
    NerDataset,
    Span,
    make_collate,
    predict_entities,
)
from backend.nlp.training.loop import TrainResult, fine_tune, pick_device


def record_spans(record: DatasetRecord) -> list[Span]:
    return [(e.start, e.end, e.type.value) for e in record.entities]


def load_pretrained(model_name: str):
    """Download (or load from cache) an encoder and attach a fresh
    token-classification head with one output per BIO tag."""
    tokenizer = AutoTokenizer.from_pretrained(model_name)
    if not tokenizer.is_fast:
        raise ValueError("NER needs a fast tokenizer: it provides character offsets.")
    model = AutoModelForTokenClassification.from_pretrained(
        model_name, num_labels=len(TAGS), id2label=ID2TAG, label2id=TAG2ID
    )
    return tokenizer, model


def train_ner_model(
    train_records: list[DatasetRecord],
    val_records: list[DatasetRecord],
    tokenizer,
    model,
    config: NerConfig,
    seed: int,
    output_dir: Path,
    device: torch.device | None = None,
) -> TrainResult:
    """Fine-tune `model` and save the best epoch by validation entity F1."""
    set_seed(seed)
    device = device or pick_device()

    loader = DataLoader(
        NerDataset(
            [r.text for r in train_records],
            [record_spans(r) for r in train_records],
            tokenizer, config.max_length,
        ),
        batch_size=config.batch_size,
        shuffle=True,
        collate_fn=make_collate(tokenizer),
        generator=torch.Generator().manual_seed(seed),
    )

    cross_entropy = torch.nn.CrossEntropyLoss(ignore_index=IGNORE)

    def loss_fn(logits: torch.Tensor, labels: torch.Tensor) -> torch.Tensor:
        # logits: (batch, tokens, tags) -> one row per token.
        return cross_entropy(logits.view(-1, len(TAGS)), labels.view(-1))

    val_texts = [r.text for r in val_records]
    val_spans = [record_spans(r) for r in val_records]

    def score() -> dict:
        predicted = predict_entities(
            model, tokenizer, val_texts, config.max_length, config.batch_size * 4, device
        )
        overall = entity_report(val_spans, [[e.span for e in row] for row in predicted])["overall"]
        return {"score": overall["f1"], "val_entity_f1": overall["f1"],
                "val_precision": overall["precision"], "val_recall": overall["recall"]}

    return fine_tune(model, tokenizer, loader, loss_fn, score, config, output_dir, device,
                     label=f"ner seed {seed}")


def load_finetuned(model_dir: Path):
    """Load a checkpoint written by train_ner_model."""
    tokenizer = AutoTokenizer.from_pretrained(model_dir)
    model = AutoModelForTokenClassification.from_pretrained(model_dir)
    return tokenizer, model
