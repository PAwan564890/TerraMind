"""Embedding fallback for normalising variables and disasters.

Dictionary lookup fails on words that are not listed as aliases: "cold" for
temperature, "जाडो" (cold) in Nepali, "forests" for vegetation. This matcher
embeds the unknown word and every alias, and returns the concept whose alias
is closest, if it is close enough.

It is the LAST step of normalisation and the least certain. It is not used
for place names: a town's name carries no meaning an embedding could match.
"""

from backend.nlp.embeddings.encoder import EmbeddingModel
from backend.nlp.ontology import Ontology


class AliasMatcher:
    def __init__(self, model: EmbeddingModel, ontology: Ontology, threshold: float,
                 margin: float) -> None:
        self._model = model
        self._threshold = threshold
        self._margin = margin
        self._ids: list[str] = []
        aliases: list[str] = []
        for concept, entry in [*ontology.variables.items(), *ontology.disasters.items()]:
            for alias in entry.aliases.all():
                self._ids.append(concept.value)
                aliases.append(alias)
        self._vectors = model.encode(aliases)

    def scores(self, text: str) -> list[tuple[str, float]]:
        """Best similarity per concept, highest first."""
        similarities = self._vectors @ self._model.encode([text])[0]
        best: dict[str, float] = {}
        for concept_id, similarity in zip(self._ids, similarities.tolist()):
            best[concept_id] = max(best.get(concept_id, -1.0), similarity)
        return sorted(best.items(), key=lambda item: item[1], reverse=True)

    def match(self, text: str) -> tuple[str, float] | None:
        """(concept id, similarity) if one concept is clearly the closest."""
        ranked = self.scores(text)
        (best_id, best), (_, runner_up) = ranked[0], ranked[1]
        if best >= self._threshold and best - runner_up >= self._margin:
            return best_id, best
        return None
