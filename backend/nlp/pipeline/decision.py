"""Thresholds and the out-of-domain similarity score used to decide whether
a query is answered, questioned or rejected."""

import json
from pathlib import Path

from pydantic import BaseModel, ConfigDict

from backend.core.config import Settings
from backend.nlp.embeddings.encoder import EmbeddingModel
from backend.nlp.embeddings.index import NeighbourIndex


class ThresholdsNotFound(Exception):
    """Raised when thresholds have not been selected for the current models."""


class DecisionThresholds(BaseModel):
    """Values chosen from validation data by scripts/select_thresholds.py.
    They belong to a specific trained model and must be re-selected whenever
    the intent model changes."""

    model_config = ConfigDict(extra="ignore")

    # Temperature for calibrating intent probabilities (1.0 = unchanged).
    temperature: float = 1.0
    # Below this calibrated confidence the intent is not trusted.
    min_intent_confidence: float = 0.0
    # Below this similarity to in-domain training queries, a query is out of
    # domain. -1 disables the check (cosine similarity is never below -1).
    min_domain_similarity: float = -1.0
    # At or above this similarity a query looks firmly in-domain. If the
    # classifier nevertheless says "off-topic", the signals disagree and the
    # user is asked. 2.0 disables the rule (cosine similarity never exceeds 1).
    in_domain_similarity: float = 2.0

    @classmethod
    def path(cls, settings: Settings) -> Path:
        return settings.paths.models_dir / "decision" / "thresholds.json"

    @classmethod
    def load(cls, settings: Settings) -> "DecisionThresholds":
        path = cls.path(settings)
        if not path.is_file():
            raise ThresholdsNotFound(
                f"{path} not found. Run: python scripts/select_thresholds.py"
            )
        return cls.model_validate(json.loads(path.read_text(encoding="utf-8")))


def without_spans(text: str, spans: list[tuple[int, int]]) -> str:
    """The text with the given character ranges removed."""
    pieces, cursor = [], 0
    for start, end in sorted(spans):
        pieces.append(text[cursor:start])
        cursor = max(cursor, end)
    pieces.append(text[cursor:])
    return " ".join("".join(pieces).split())


class DomainScorer:
    """Similarity of a query to the nearest in-domain training queries.

    PLACE NAMES ARE REMOVED before embedding, from the training queries and
    from the query being scored. Measured without this step, a real question
    about a town absent from the training data scored as low as an off-topic
    one: the unfamiliar name, not the topic, drove the similarity down. What
    makes a query in-domain is what it asks, not where.
    """

    def __init__(self, model: EmbeddingModel, index: NeighbourIndex, neighbours: int) -> None:
        self._model = model
        self._index = index
        self._neighbours = neighbours

    @staticmethod
    def index_path(settings: Settings) -> Path:
        return settings.paths.models_dir / "decision" / "domain_index.npz"

    @classmethod
    def from_settings(cls, settings: Settings) -> "DomainScorer":
        config = settings.embeddings
        index_path = cls.index_path(settings)
        if not index_path.is_file():
            raise ThresholdsNotFound(
                f"{index_path} not found. Run: python scripts/select_thresholds.py"
            )
        return cls(EmbeddingModel.from_config(config),
                   NeighbourIndex.load(index_path, config.model_name), config.neighbours)

    def score_many(self, texts: list[str],
                   location_spans: list[list[tuple[int, int]]]) -> list[float]:
        stripped = [without_spans(t, spans) for t, spans in zip(texts, location_spans)]
        # A query that is nothing but a place name has no topic to judge.
        keep = [i for i, text in enumerate(stripped) if text]
        scores = [1.0] * len(texts)
        if keep:
            vectors = self._model.encode([stripped[i] for i in keep])
            for i, value in zip(keep, self._index.domain_similarity(vectors, self._neighbours)):
                scores[i] = float(value)
        return scores

    def score(self, text: str, location_spans: list[tuple[int, int]]) -> float:
        return self.score_many([text], [location_spans])[0]
