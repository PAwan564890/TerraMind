"""Inference wrapper for the fine-tuned NER model."""

import json
from pathlib import Path

import torch

from backend.core.config import Settings
from backend.nlp.ner.model import TAGS, PredictedEntity, predict_entities
from backend.nlp.ner.train import load_finetuned
from backend.nlp.training.loop import pick_device


class NerModelNotFound(Exception):
    """Raised when no trained NER model exists at the configured path."""


def resolve_model_dir(settings: Settings) -> Path:
    """Folder of the best seed of the active run, as recorded by the training script."""
    run_dir = settings.paths.models_dir / "ner" / settings.ner.active_run
    summary_path = run_dir / "summary.json"
    if not summary_path.is_file():
        raise NerModelNotFound(f"{summary_path} not found. Run: python scripts/train_ner.py")
    best_seed = json.loads(summary_path.read_text(encoding="utf-8"))["best_seed"]
    return run_dir / f"seed_{best_seed}"


class EntityRecognizer:
    def __init__(self, tokenizer, model, max_length: int, batch_size: int = 32,
                 device: torch.device | None = None) -> None:
        self._tokenizer = tokenizer
        self._device = device or pick_device()
        self._model = model.to(self._device).eval()
        self._max_length = max_length
        self._batch_size = batch_size

        saved = [self._model.config.id2label[i] for i in range(len(TAGS))]
        if saved != TAGS:
            raise ValueError("Checkpoint tag order does not match the EntityType enum; retrain.")

    @classmethod
    def load(cls, model_dir: Path, max_length: int) -> "EntityRecognizer":
        if not (model_dir / "config.json").is_file():
            raise NerModelNotFound(f"No NER model in {model_dir}")
        tokenizer, model = load_finetuned(model_dir)
        return cls(tokenizer, model, max_length)

    @classmethod
    def from_settings(cls, settings: Settings) -> "EntityRecognizer":
        return cls.load(resolve_model_dir(settings), settings.ner.max_length)

    def predict(self, texts: list[str]) -> list[list[PredictedEntity]]:
        """Entities per text, in reading order, with character offsets."""
        return predict_entities(
            self._model, self._tokenizer, texts, self._max_length, self._batch_size, self._device
        )
