"""Inference wrapper for the fine-tuned intent classifier."""

import json
from pathlib import Path

import torch
from pydantic import BaseModel

from backend.core.config import Settings
from backend.nlp.intent.model import LABELS, pick_device, predict_probabilities
from backend.nlp.intent.train import load_finetuned
from backend.nlp.query.enums import Intent


class IntentModelNotFound(Exception):
    """Raised when no trained intent model exists at the configured path."""


class IntentPrediction(BaseModel):
    label: Intent
    # Raw softmax probability, NOT calibrated. The pipeline applies
    # temperature scaling (see intent/calibration.py) before using it.
    confidence: float
    # Every intent with its probability, most likely first. The top two are
    # what a clarification question would offer the user.
    ranked: list[tuple[Intent, float]]


def resolve_model_dir(settings: Settings) -> Path:
    """Folder of the best seed of the active run, as recorded by the training script."""
    run_dir = settings.paths.models_dir / "intent" / settings.intent.active_run
    summary_path = run_dir / "summary.json"
    if not summary_path.is_file():
        raise IntentModelNotFound(
            f"{summary_path} not found. Run: python scripts/train_intent.py"
        )
    best_seed = json.loads(summary_path.read_text(encoding="utf-8"))["best_seed"]
    return run_dir / f"seed_{best_seed}"


class IntentClassifier:
    def __init__(self, tokenizer, model, max_length: int, batch_size: int = 32,
                 device: torch.device | None = None) -> None:
        self._tokenizer = tokenizer
        self._device = device or pick_device()
        self._model = model.to(self._device).eval()
        self._max_length = max_length
        self._batch_size = batch_size

        saved = [self._model.config.id2label[i] for i in range(len(LABELS))]
        if saved != LABELS:
            raise ValueError("Checkpoint label order does not match the Intent enum; retrain.")

    @classmethod
    def load(cls, model_dir: Path, max_length: int) -> "IntentClassifier":
        if not (model_dir / "config.json").is_file():
            raise IntentModelNotFound(f"No intent model in {model_dir}")
        tokenizer, model = load_finetuned(model_dir)
        return cls(tokenizer, model, max_length)

    @classmethod
    def from_settings(cls, settings: Settings) -> "IntentClassifier":
        return cls.load(resolve_model_dir(settings), settings.intent.max_length)

    def probabilities(self, texts: list[str]):
        """Raw probability matrix, one row per text, columns in LABELS order."""
        return predict_probabilities(
            self._model, self._tokenizer, texts, self._max_length, self._batch_size, self._device
        )

    def predict(self, texts: list[str]) -> list[IntentPrediction]:
        probabilities = self.probabilities(texts)
        predictions = []
        for row in probabilities:
            ranked = sorted(zip(LABELS, row.tolist()), key=lambda pair: pair[1], reverse=True)
            predictions.append(IntentPrediction(
                label=Intent(ranked[0][0]),
                confidence=ranked[0][1],
                ranked=[(Intent(label), p) for label, p in ranked],
            ))
        return predictions
