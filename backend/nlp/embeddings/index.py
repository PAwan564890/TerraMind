"""Nearest-neighbour index over the embedded training queries.

Two uses:
  - domain_similarity: how close is a new query to known environmental
    queries? A low value is evidence that the query is out of domain.
  - knn_intent: the majority intent among the nearest training queries, as a
    cross-check on the trained classifier.

With a few thousand vectors, a plain matrix product is fast enough; a vector
database (FAISS, Chroma) is not needed until the RAG phase.
"""

from collections import defaultdict
from pathlib import Path

import numpy as np

from backend.nlp.dataset.records import DatasetRecord
from backend.nlp.embeddings.encoder import EmbeddingModel
from backend.nlp.query.enums import Intent


class NeighbourIndex:
    def __init__(self, vectors: np.ndarray, intents: list[str], texts: list[str],
                 model_name: str) -> None:
        self.vectors = vectors
        self.intents = intents
        self.texts = texts
        self.model_name = model_name
        self._in_domain = np.array([i != Intent.OUT_OF_DOMAIN.value for i in intents])

    @classmethod
    def build(cls, model: EmbeddingModel, records: list[DatasetRecord],
              texts: list[str] | None = None) -> "NeighbourIndex":
        """`texts` replaces the records' own text, e.g. with place names removed."""
        texts = texts if texts is not None else [r.text for r in records]
        return cls(model.encode(texts), [r.intent.value for r in records], texts, model.name)

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        np.savez_compressed(
            path, vectors=self.vectors, intents=np.array(self.intents),
            texts=np.array(self.texts), model_name=np.array(self.model_name),
        )

    @classmethod
    def load(cls, path: Path, expected_model: str) -> "NeighbourIndex":
        data = np.load(path)
        model_name = str(data["model_name"])
        if model_name != expected_model:
            # Vectors from different models live in unrelated spaces.
            raise ValueError(
                f"Index was built with {model_name}, but the config uses {expected_model}. "
                "Rebuild it: python scripts/evaluate_embeddings.py"
            )
        return cls(data["vectors"], data["intents"].tolist(), data["texts"].tolist(), model_name)

    def domain_similarity(self, queries: np.ndarray, k: int) -> np.ndarray:
        """Mean cosine similarity to the k nearest IN-DOMAIN training queries."""
        similarities = queries @ self.vectors[self._in_domain].T
        k = min(k, similarities.shape[1])
        top = np.partition(similarities, -k, axis=1)[:, -k:]
        return top.mean(axis=1)

    def knn_intent(self, queries: np.ndarray, k: int) -> list[str]:
        """Intent with the largest total similarity among the k nearest neighbours."""
        similarities = queries @ self.vectors.T
        k = min(k, similarities.shape[1])
        nearest = np.argpartition(similarities, -k, axis=1)[:, -k:]
        labels = []
        for row, neighbours in zip(similarities, nearest):
            votes: dict[str, float] = defaultdict(float)
            for index in neighbours:
                votes[self.intents[index]] += float(row[index])
            labels.append(max(votes, key=votes.get))
        return labels
