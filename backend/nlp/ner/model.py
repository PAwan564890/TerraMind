"""Tagging scheme, label alignment and span decoding for NER.

The model predicts one BIO tag per subword token:
    B-LOCATION   first token of a location
    I-LOCATION   a later token of the same location
    O            not part of any entity

ALIGNMENT. Our labels are character spans; the model sees subword tokens. A
fast tokenizer reports, for every token, the character range it came from
(the "offset mapping"). A token is given an entity's tag if its range
overlaps the entity's range.

Tags are assigned to EVERY subword rather than only to the first subword of
each word. That is deliberate: in Nepali the case ending is attached to the
name ("गान्तोकमा" = Gangtok + "in"), so an entity can end in the middle of a
word. Per-subword tags let the model end the entity where the name ends,
whenever the tokenizer splits there.
"""

from dataclasses import dataclass

import numpy as np
import torch
from torch.utils.data import Dataset

from backend.nlp.query.enums import EntityType

TAGS: list[str] = ["O"] + [
    f"{prefix}-{entity_type.value}" for entity_type in EntityType for prefix in ("B", "I")
]
TAG2ID: dict[str, int] = {tag: i for i, tag in enumerate(TAGS)}
ID2TAG: dict[int, str] = dict(enumerate(TAGS))

# PyTorch's cross-entropy skips positions labelled -100. Used for special
# tokens (<s>, </s>) and padding, which have no tag.
IGNORE = -100

Span = tuple[int, int, str]  # (start, end, entity type), character offsets


@dataclass(frozen=True)
class PredictedEntity:
    start: int
    end: int
    type: EntityType
    text: str
    confidence: float

    @property
    def span(self) -> Span:
        return (self.start, self.end, self.type.value)


def align_tags(offsets: list[tuple[int, int]], spans: list[Span]) -> list[int]:
    """Tag id for each token, given the token offsets and the labelled spans."""
    tag_ids = []
    started: set[Span] = set()
    for token_start, token_end in offsets:
        if token_start == token_end:  # special token
            tag_ids.append(IGNORE)
            continue
        tag = "O"
        for span in spans:
            start, end, entity_type = span
            if token_start < end and start < token_end:  # ranges overlap
                tag = f"{'I' if span in started else 'B'}-{entity_type}"
                started.add(span)
                break
        tag_ids.append(TAG2ID[tag])
    return tag_ids


def decode_tags(
    text: str,
    offsets: list[tuple[int, int]],
    tag_ids: list[int],
    confidences: list[float] | None = None,
) -> list[PredictedEntity]:
    """Merge per-token tags back into character-level entities."""
    entities: list[PredictedEntity] = []
    current: list | None = None  # [start, end, type, token confidences]

    def close() -> None:
        nonlocal current
        if current is not None:
            start, end, entity_type, scores = current
            # A SentencePiece token can include the space before a word.
            while start < end and text[start].isspace():
                start += 1
            while end > start and text[end - 1].isspace():
                end -= 1
            if end > start:
                entities.append(PredictedEntity(
                    start, end, EntityType(entity_type), text[start:end],
                    float(np.mean(scores)),
                ))
        current = None

    for i, ((token_start, token_end), tag_id) in enumerate(zip(offsets, tag_ids)):
        tag = ID2TAG.get(tag_id, "O")
        if token_start == token_end or tag == "O":
            close()
            continue
        prefix, entity_type = tag.split("-", 1)
        score = confidences[i] if confidences is not None else 1.0
        # An I- tag continues the open entity only if the type matches.
        # Otherwise it starts a new one, which forgives a missing B- tag.
        if prefix == "I" and current is not None and current[2] == entity_type:
            current[1] = token_end
            current[3].append(score)
        else:
            close()
            current = [token_start, token_end, entity_type, [score]]
    close()
    return entities


class NerDataset(Dataset):
    """Tokenised queries with one tag id per token (unpadded)."""

    def __init__(self, texts: list[str], spans: list[list[Span]], tokenizer, max_length: int):
        encodings = tokenizer(
            texts, truncation=True, max_length=max_length, return_offsets_mapping=True
        )
        self._input_ids = encodings["input_ids"]
        self._attention_mask = encodings["attention_mask"]
        self._labels = [
            align_tags(offsets, text_spans)
            for offsets, text_spans in zip(encodings["offset_mapping"], spans)
        ]

    def __len__(self) -> int:
        return len(self._input_ids)

    def __getitem__(self, index: int) -> dict:
        return {
            "input_ids": self._input_ids[index],
            "attention_mask": self._attention_mask[index],
            "labels": self._labels[index],
        }


def make_collate(tokenizer):
    """Pad inputs with the tokenizer and labels with IGNORE, per batch."""

    def collate(batch: list[dict]) -> dict:
        labels = [item["labels"] for item in batch]
        features = [{k: v for k, v in item.items() if k != "labels"} for item in batch]
        padded = tokenizer.pad(features, return_tensors="pt")
        length = padded["input_ids"].shape[1]
        padded["labels"] = torch.tensor(
            [row + [IGNORE] * (length - len(row)) for row in labels]
        )
        return padded

    return collate


@torch.no_grad()
def predict_entities(
    model, tokenizer, texts: list[str], max_length: int, batch_size: int, device: torch.device
) -> list[list[PredictedEntity]]:
    """Entities for each text. An entity's confidence is the mean probability
    of the tags chosen for its tokens."""
    model.eval()
    results: list[list[PredictedEntity]] = []
    for start in range(0, len(texts), batch_size):
        chunk = texts[start:start + batch_size]
        encoded = tokenizer(
            chunk, truncation=True, max_length=max_length, padding=True,
            return_offsets_mapping=True, return_tensors="pt",
        )
        offsets = encoded.pop("offset_mapping").tolist()
        logits = model(**encoded.to(device)).logits
        probabilities = torch.softmax(logits.float(), dim=-1)
        confidences, tag_ids = probabilities.max(dim=-1)
        for i, text in enumerate(chunk):
            results.append(decode_tags(
                text,
                [tuple(pair) for pair in offsets[i]],
                tag_ids[i].tolist(),
                confidences[i].tolist(),
            ))
    return results
