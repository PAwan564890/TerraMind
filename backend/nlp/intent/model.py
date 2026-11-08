"""Pieces shared by intent training and inference."""

import numpy as np
import torch
from torch.utils.data import Dataset

from backend.nlp.query.enums import Intent
from backend.nlp.training.loop import pick_device  # noqa: F401  (re-exported)

# The position of an intent in this list is its class id in the model.
LABELS: list[str] = [intent.value for intent in Intent]
LABEL2ID: dict[str, int] = {label: i for i, label in enumerate(LABELS)}
ID2LABEL: dict[int, str] = dict(enumerate(LABELS))


class IntentDataset(Dataset):
    """Tokenised queries with their class ids.

    Each item is tokenised WITHOUT padding. Padding is added per batch by the
    collate function, to the length of the longest query in that batch, which
    wastes far less computation than padding everything to max_length.
    """

    def __init__(self, texts: list[str], labels: list[str] | None, tokenizer, max_length: int):
        self._encodings = tokenizer(texts, truncation=True, max_length=max_length)
        self._labels = [LABEL2ID[label] for label in labels] if labels is not None else None

    def __len__(self) -> int:
        return len(self._encodings["input_ids"])

    def __getitem__(self, index: int) -> dict:
        item = {key: values[index] for key, values in self._encodings.items()}
        if self._labels is not None:
            item["labels"] = self._labels[index]
        return item


def make_collate(tokenizer):
    """Collate function that pads a batch to its own longest sequence."""

    def collate(batch: list[dict]) -> dict:
        return tokenizer.pad(batch, return_tensors="pt")

    return collate


@torch.no_grad()
def predict_probabilities(
    model, tokenizer, texts: list[str], max_length: int, batch_size: int, device: torch.device
) -> np.ndarray:
    """Class probabilities for each text, shape (len(texts), number of intents)."""
    model.eval()
    rows = []
    for start in range(0, len(texts), batch_size):
        batch = tokenizer(
            texts[start:start + batch_size],
            truncation=True, max_length=max_length, padding=True, return_tensors="pt",
        ).to(device)
        logits = model(**batch).logits
        rows.append(torch.softmax(logits.float(), dim=-1).cpu().numpy())
    return np.concatenate(rows) if rows else np.zeros((0, len(LABELS)))
