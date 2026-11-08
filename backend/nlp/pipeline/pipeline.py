"""The NLP pipeline: one query in, one AnalyzeResponse out.

Order of steps:
    prepare (normalise + validate input)
    -> language detection
    -> intent classification   } independent of each other;
    -> NER                     } both read the same normalised text
    -> entity normalisation
    -> out-of-domain check by embedding similarity
    -> context resolution
    -> query structuring
    -> decision: ok / needs_clarification / out_of_domain

The components are passed in rather than created here, so tests can run the
whole pipeline with small stand-ins and no model files.
"""

import logging
from typing import Protocol

import numpy as np

from backend.core.config import Settings
from backend.nlp.context import ConversationManager, is_fragment
from backend.nlp.intent.calibration import apply_temperature
from backend.nlp.intent.predictor import IntentPrediction
from backend.nlp.language_detection import LanguageDetection
from backend.nlp.ner.model import PredictedEntity
from backend.nlp.normalization import EntityNormalizer
from backend.nlp.ontology import Ontology
from backend.nlp.pipeline.decision import DecisionThresholds
from backend.nlp.preprocessing import prepare_query
from backend.nlp.query.enums import EntityType, Intent, Language, Status
from backend.nlp.query.schema import (
    AnalyzeResponse,
    Clarification,
    Entity,
    IntentResult,
    LanguageResult,
)
from backend.nlp.query.structurer import FoundEntity, build_query, build_turn
from backend.nlp.query.validator import validate_query

log = logging.getLogger(__name__)


class Detector(Protocol):
    def detect(self, text: str, fallback: Language | None = None) -> LanguageDetection: ...


class Classifier(Protocol):
    def predict(self, texts: list[str]) -> list[IntentPrediction]: ...


class Recognizer(Protocol):
    def predict(self, texts: list[str]) -> list[list[PredictedEntity]]: ...


class Scorer(Protocol):
    def score(self, text: str, location_spans: list[tuple[int, int]]) -> float: ...


def calibrated(prediction: IntentPrediction, temperature: float) -> dict[Intent, float]:
    """Calibrated probability for every intent."""
    labels = [label for label, _ in prediction.ranked]
    raw = np.array([[p for _, p in prediction.ranked]])
    return dict(zip(labels, apply_temperature(raw, temperature)[0].tolist()))


class NlpPipeline:
    def __init__(
        self,
        settings: Settings,
        ontology: Ontology,
        detector: Detector,
        classifier: Classifier,
        recognizer: Recognizer,
        normalizer: EntityNormalizer,
        conversations: ConversationManager,
        thresholds: DecisionThresholds | None = None,
        domain_scorer: Scorer | None = None,
    ) -> None:
        """Without `thresholds`, no confidence is ever too low; without a
        `domain_scorer`, only the classifier decides what is out of domain."""
        self._settings = settings
        self._ontology = ontology
        self._detector = detector
        self._classifier = classifier
        self._recognizer = recognizer
        self._normalizer = normalizer
        self._conversations = conversations
        self._thresholds = thresholds or DecisionThresholds()
        self._domain_scorer = domain_scorer

    @classmethod
    def from_settings(cls, settings: Settings) -> "NlpPipeline":
        """Load every trained component named in the config."""
        from backend.nlp.intent.predictor import IntentClassifier
        from backend.nlp.language_detection import LanguageDetector
        from backend.nlp.ner.predictor import EntityRecognizer
        from backend.nlp.ontology import get_ontology
        from backend.nlp.pipeline.decision import DomainScorer

        ontology = get_ontology()
        alias_matcher = None
        if settings.pipeline.use_embedding_fallback:
            from backend.nlp.embeddings.alias_matcher import AliasMatcher
            from backend.nlp.embeddings.encoder import EmbeddingModel

            alias_matcher = AliasMatcher(
                EmbeddingModel.from_config(settings.embeddings), ontology,
                settings.embeddings.alias_threshold, settings.embeddings.alias_margin,
            )
        return cls(
            settings=settings,
            ontology=ontology,
            detector=LanguageDetector.load(
                settings.paths.models_dir / "language_detection" / "hi_ne.joblib",
                settings.language_detection.min_confidence,
            ),
            classifier=IntentClassifier.from_settings(settings),
            recognizer=EntityRecognizer.from_settings(settings),
            normalizer=EntityNormalizer(ontology, settings.normalization, alias_matcher),
            conversations=ConversationManager(settings.context),
            thresholds=DecisionThresholds.load(settings),
            domain_scorer=DomainScorer.from_settings(settings),
        )

    def analyze(self, query: str, session_id: str | None = None,
                now: float | None = None) -> AnalyzeResponse:
        """Analyse one query. Raises InvalidQueryError for unusable input.

        With a `session_id`, earlier turns of that conversation fill in what
        this query leaves out.
        """
        text = prepare_query(query, self._settings.input.max_query_chars)
        warnings: list[str] = []
        thresholds = self._thresholds

        previous_language = self._conversations.language_of(session_id, now)
        detection = self._detector.detect(text, fallback=previous_language)
        if detection.method == "fallback":
            warnings.append("language_from_context")
        if detection.mixed_script:
            warnings.append("mixed_script")

        prediction = self._classifier.predict([text])[0]
        probabilities = calibrated(prediction, thresholds.temperature)
        confident = probabilities[prediction.label] >= thresholds.min_intent_confidence
        spans = self._recognizer.predict([text])[0]

        found: list[FoundEntity] = []
        for e in spans:
            resolution = self._normalizer.normalize(e.text, e.type, text, detection.code)
            if not resolution.resolved and e.type is EntityType.LOCATION:
                # One span drawn around several names, or a name plus a
                # neighbouring word: recover the places inside it.
                parts = self._normalizer.split_locations(e.text)
                if parts:
                    found += [FoundEntity(e.text[s:t], e.start + s, e.start + t, e.confidence, r)
                              for s, t, r in parts]
                    continue
            found.append(FoundEntity(e.text, e.start, e.end, e.confidence, resolution))
        fragment = is_fragment(text, [(e.start, e.end) for e in found])

        # Second out-of-domain signal, independent of the classifier: is this
        # query unlike every in-domain query seen in training? Entity-only
        # fragments ("Gangtok", "20%") are exempt: they are short and odd by
        # nature, and they name an environmental entity.
        classified_as = prediction.label
        far_from_domain = False
        looks_in_domain = False
        if self._domain_scorer is not None and not fragment:
            places = [(e.start, e.end) for e in found
                      if e.resolution.type is EntityType.LOCATION]
            similarity = self._domain_scorer.score(text, places)
            far_from_domain = similarity < thresholds.min_domain_similarity
            looks_in_domain = similarity >= thresholds.in_domain_similarity
            if far_from_domain:
                classified_as = Intent.OUT_OF_DOMAIN
                warnings.append("low_domain_similarity")

        turn, turn_warnings = build_turn(
            text, detection.code, classified_as, found, self._ontology, fragment
        )
        # A similarity rejection is final; it must not be reopened as an
        # "unsure follow-up" by the context rules.
        turn.intent_confident = confident or far_from_domain
        warnings += turn_warnings

        resolved = self._conversations.process(session_id, turn, now)
        intent_from_context = "intent" in resolved.context_used

        entities = [
            Entity(
                text=e.text, type=e.resolution.type, start=e.start, end=e.end,
                normalized=e.resolution.canonical,
                # Unresolved entities keep the NER confidence alone.
                confidence=e.confidence * (e.resolution.confidence if e.resolution.resolved else 1),
            )
            for e in found
        ]
        language = LanguageResult(code=detection.code, confidence=detection.confidence)
        # Context may have replaced the classifier's label. Report the final
        # label with the calibrated probability the classifier gave to it.
        intent = IntentResult(label=resolved.intent, confidence=probabilities[resolved.intent])

        def respond(status: Status, structured=None, clarification=None) -> AnalyzeResponse:
            return AnalyzeResponse(
                language=language, intent=intent, entities=entities,
                structured_query=structured, status=status, clarification=clarification,
                warnings=warnings,
            )

        def unsure(reason: str = "low_confidence") -> Clarification:
            top_two = sorted(probabilities, key=probabilities.get, reverse=True)[:2]
            return Clarification(reason=reason, message_key="unclear_request",
                                 options=[label.value for label in top_two])

        if resolved.intent is Intent.OUT_OF_DOMAIN:
            if far_from_domain:
                return respond(Status.OUT_OF_DOMAIN)
            if confident and looks_in_domain:
                # The classifier is sure the query is off-topic, yet it sits
                # as close to known in-domain queries as almost no off-topic
                # query does. Two independent signals disagree, so neither is
                # trusted: a wrong rejection would lose a real question.
                warnings.append("signals_disagree")
                return respond(Status.NEEDS_CLARIFICATION,
                               clarification=unsure("signals_disagree"))
            if confident:
                return respond(Status.OUT_OF_DOMAIN)
            # The classifier leans out-of-domain but is not sure, and the
            # query is not far from the domain: ask rather than reject.
            return respond(Status.NEEDS_CLARIFICATION, clarification=unsure())

        structured = build_query(resolved, text)
        if not confident and not intent_from_context:
            return respond(Status.NEEDS_CLARIFICATION, structured, unsure())

        result = validate_query(structured, warnings, self._settings.decision)
        warnings += result.warnings
        if result.ok:
            return respond(Status.OK, result.query)
        return respond(Status.NEEDS_CLARIFICATION, result.query, result.clarification)
