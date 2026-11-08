"""Sentence embeddings from a pretrained multilingual encoder.

An embedding is a fixed-length vector that summarises a sentence, built so
that sentences with similar meaning get similar vectors, across languages.
Nothing here is fine-tuned: the model is used exactly as published.

Implemented directly on `transformers` (tokenise, run the encoder, average
the token vectors) rather than through the sentence-transformers package,
which would add a dependency for about ten lines of code.
"""

import numpy as np
import torch
from transformers import AutoModel, AutoTokenizer

from backend.core.config import EmbeddingsConfig
from backend.nlp.training.loop import pick_device


class EmbeddingModel:
    def __init__(self, tokenizer, model, name: str, prefix: str, max_length: int,
                 batch_size: int, device: torch.device | None = None) -> None:
        self.name = name
        self._tokenizer = tokenizer
        self._device = device or pick_device()
        self._model = model.to(self._device).eval()
        self._prefix = prefix
        self._max_length = max_length
        self._batch_size = batch_size

    @classmethod
    def load(cls, name: str, prefix: str, config: EmbeddingsConfig) -> "EmbeddingModel":
        return cls(AutoTokenizer.from_pretrained(name), AutoModel.from_pretrained(name),
                   name, prefix, config.max_length, config.batch_size)

    @classmethod
    def from_config(cls, config: EmbeddingsConfig) -> "EmbeddingModel":
        return cls.load(config.model_name, config.prefix, config)

    @torch.no_grad()
    def encode(self, texts: list[str]) -> np.ndarray:
        """One unit-length vector per text, shape (len(texts), dimension).

        Because the vectors have length 1, the dot product of two of them is
        their cosine similarity.
        """
        rows = []
        for start in range(0, len(texts), self._batch_size):
            # Some models (the E5 family) were trained with a task prefix and
            # give worse embeddings without it.
            chunk = [self._prefix + text for text in texts[start:start + self._batch_size]]
            batch = self._tokenizer(
                chunk, truncation=True, max_length=self._max_length, padding=True,
                return_tensors="pt",
            ).to(self._device)
            hidden = self._model(**batch).last_hidden_state
            # Mean pooling: average the token vectors, ignoring padding.
            mask = batch["attention_mask"].unsqueeze(-1).to(hidden.dtype)
            pooled = (hidden * mask).sum(dim=1) / mask.sum(dim=1)
            rows.append(torch.nn.functional.normalize(pooled, dim=-1).cpu().numpy())
        if not rows:
            return np.zeros((0, self._model.config.hidden_size), dtype=np.float32)
        return np.concatenate(rows).astype(np.float32)
