"""Tests for calibration, validation and the final ok / clarify / reject decision."""

import json

import numpy as np
import pytest

from backend.core import load_settings
from backend.nlp.context import ConversationManager
from backend.nlp.intent.calibration import (
    apply_temperature,
    calibration_report,
    coverage_curve,
    fit_temperature,
    select_threshold,
)
from backend.nlp.intent.predictor import IntentPrediction
from backend.nlp.normalization import EntityNormalizer
from backend.nlp.ontology import get_ontology
from backend.nlp.pipeline import NlpPipeline
from backend.nlp.pipeline.decision import (
    DecisionThresholds,
    DomainScorer,
    ThresholdsNotFound,
    without_spans,
)
from backend.nlp.query.enums import (
    AnswerKind,
    ChangeUnit,
    Direction,
    Disaster,
    Intent,
    Operation,
    Status,
    TimeType,
    Variable,
)
from backend.nlp.query.schema import Scenario, StructuredQuery
from backend.nlp.query.validator import validate_query
from tests.nlp.test_pipeline import DictionaryRecognizer, KeywordClassifier, detector  # noqa: F401

SETTINGS = load_settings()
CONFIG = SETTINGS.decision
ONTOLOGY = get_ontology()
GANGTOK = ONTOLOGY.location_ref("loc:gangtok")
NAMCHI = ONTOLOGY.location_ref("loc:namchi")


# --- calibration -------------------------------------------------------------------

def test_temperature_keeps_the_ranking_and_sums_to_one():
    probabilities = np.array([[0.5, 0.3, 0.2], [0.1, 0.2, 0.7]])
    for temperature in (0.3, 1.0, 3.0):
        scaled = apply_temperature(probabilities, temperature)
        assert np.allclose(scaled.sum(axis=1), 1.0)
        assert (scaled.argmax(axis=1) == probabilities.argmax(axis=1)).all()
    assert np.allclose(apply_temperature(probabilities, 1.0), probabilities)
    assert apply_temperature(probabilities, 0.3)[0, 0] > 0.5   # sharpened
    assert apply_temperature(probabilities, 3.0)[0, 0] < 0.5   # flattened


def test_fit_temperature_corrects_under_and_over_confidence():
    rng = np.random.default_rng(0)
    labels = rng.integers(0, 3, size=600)
    # Always right, but only 50% confident: under-confident -> T < 1.
    timid = np.full((600, 3), 0.25)
    timid[np.arange(600), labels] = 0.5
    assert fit_temperature(timid, labels) < 0.5

    # 99% confident but right only 70% of the time: over-confident -> T > 1.
    predicted = np.where(rng.random(600) < 0.7, labels, (labels + 1) % 3)
    bold = np.full((600, 3), 0.005)
    bold[np.arange(600), predicted] = 0.99
    temperature = fit_temperature(bold, labels)
    assert temperature > 1.5
    before = calibration_report(bold, labels)["ece"]
    after = calibration_report(apply_temperature(bold, temperature), labels)["ece"]
    assert after < before / 3


def test_calibration_report_of_a_perfectly_calibrated_model():
    probabilities = np.array([[0.75, 0.25]] * 4)
    labels = np.array([0, 0, 0, 1])   # 75% confident, 75% right
    report = calibration_report(probabilities, labels)
    assert report["ece"] == pytest.approx(0.0)
    assert report["bins"][0]["n"] == 4


def test_threshold_selection_takes_the_lowest_that_meets_the_target():
    confidence = np.array([0.95, 0.9, 0.85, 0.6, 0.55, 0.5])
    correct = np.array([True, True, True, True, False, False])
    curve = coverage_curve(confidence, correct, np.array([0.5, 0.58, 0.7, 0.9]))
    assert curve[0] == {"threshold": 0.5, "coverage": 1.0,
                        "answered_error": pytest.approx(2 / 6)}
    chosen = select_threshold(curve, target_error=0.05)
    assert chosen["threshold"] == 0.58          # lowest with no wrong answers
    assert chosen["coverage"] == pytest.approx(4 / 6)
    # An unreachable target falls back to the lowest error on offer.
    hopeless = coverage_curve(confidence, ~correct | True & ~correct, np.array([0.5, 0.9]))
    assert select_threshold(hopeless, target_error=-1.0) in hopeless


# --- validator ------------------------------------------------------------------------

def query(intent, operation=None, **slots):
    from backend.nlp.query.intents import INTENT_SPECS, derive_answer_kind

    operation = operation or INTENT_SPECS[intent].default_operation
    return StructuredQuery(intent=intent, operation=operation,
                           answer_kind=derive_answer_kind(intent, operation), **slots)


def check(structured, warnings=()):
    return validate_query(structured, list(warnings), CONFIG)


def test_complete_query_passes():
    result = check(query(Intent.WEATHER_QUERY, locations=[GANGTOK],
                         variables=[Variable.TEMPERATURE]))
    assert result.ok and result.warnings == []


@pytest.mark.parametrize(
    "structured, missing, message_key",
    [
        (query(Intent.WEATHER_QUERY, variables=[Variable.TEMPERATURE]),
         ["locations"], "missing_locations"),
        (query(Intent.WEATHER_QUERY, locations=[GANGTOK]), ["variables"], "missing_variables"),
        (query(Intent.WEATHER_QUERY), ["locations", "variables"], "missing_locations"),
        (query(Intent.DISASTER_RISK, locations=[GANGTOK]), ["disasters"], "missing_disasters"),
        (query(Intent.COMPARISON, locations=[GANGTOK, NAMCHI]),
         ["disasters|variables"], "missing_disasters"),
        (query(Intent.SCENARIO_ANALYSIS, locations=[GANGTOK]), ["scenario"], "missing_scenario"),
    ],
)
def test_missing_required_fields(structured, missing, message_key):
    result = check(structured)
    assert not result.ok
    assert result.clarification.reason == "missing_required_field"
    assert result.clarification.missing_fields == missing
    assert result.clarification.message_key == message_key


def test_either_member_of_a_group_satisfies_it():
    assert check(query(Intent.COMPARISON, locations=[GANGTOK, NAMCHI],
                       disasters=[Disaster.LANDSLIDE])).ok


def test_general_question_needs_nothing():
    assert check(query(Intent.GENERAL_ENVIRONMENT)).ok


def test_ranking_question_needs_no_location():
    assert check(query(Intent.DISASTER_RISK, Operation.RANK, disasters=[Disaster.FLOOD])).ok


def test_comparison_needs_two_places():
    result = check(query(Intent.COMPARISON, locations=[GANGTOK],
                         variables=[Variable.PRECIPITATION]))
    assert result.clarification.reason == "comparison_needs_two"


def test_unknown_location_is_asked_about_even_if_another_resolved():
    result = check(
        query(Intent.COMPARISON, locations=[GANGTOK], variables=[Variable.PRECIPITATION]),
        ["unresolved_location:Paris"],
    )
    assert result.clarification.reason == "unknown_location"
    assert result.clarification.options == ["Paris"]


def scenario(change, unit):
    return query(Intent.SCENARIO_ANALYSIS, locations=[GANGTOK],
                 variables=[Variable.PRECIPITATION],
                 scenario=Scenario(variable=Variable.PRECIPITATION, change=change, unit=unit,
                                   direction=Direction.INCREASE))


def test_implausible_scenario_amounts_are_questioned():
    assert check(scenario(20, ChangeUnit.PERCENT)).ok
    assert check(scenario(5000, ChangeUnit.PERCENT)).clarification.reason == "implausible_change"
    assert check(scenario(3, ChangeUnit.ABSOLUTE)).ok
    assert check(scenario(80, ChangeUnit.ABSOLUTE)).clarification.reason == "implausible_change"


def test_trend_without_time_gets_the_documented_default():
    original = query(Intent.CLIMATE_TREND, locations=[GANGTOK],
                     variables=[Variable.PRECIPITATION])
    result = check(original)
    assert result.ok
    assert result.warnings == ["time_period_defaulted"]
    period = result.query.time_period
    assert (period.type, period.value) == (TimeType.RELATIVE_PAST, CONFIG.default_trend_years)
    assert original.time_period is None   # the input is not modified


def test_lookup_without_time_is_not_given_one():
    result = check(query(Intent.WEATHER_QUERY, locations=[GANGTOK],
                         variables=[Variable.TEMPERATURE]))
    assert result.query.time_period is None


# --- thresholds file and scorer helpers -------------------------------------------------

def test_default_thresholds_never_block_anything():
    thresholds = DecisionThresholds()
    assert (thresholds.temperature, thresholds.min_intent_confidence) == (1.0, 0.0)
    assert thresholds.min_domain_similarity == -1.0


def test_thresholds_load_and_missing_file(tmp_path):
    settings = SETTINGS.model_copy(update={
        "paths": SETTINGS.paths.model_copy(update={"models_dir": tmp_path})
    })
    with pytest.raises(ThresholdsNotFound, match="select_thresholds"):
        DecisionThresholds.load(settings)
    with pytest.raises(ThresholdsNotFound, match="select_thresholds"):
        DomainScorer.from_settings(settings)
    path = DecisionThresholds.path(settings)
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps({"temperature": 0.4, "min_intent_confidence": 0.86,
                                "min_domain_similarity": 0.85, "extra_report": {}}))
    loaded = DecisionThresholds.load(settings)
    assert (loaded.temperature, loaded.min_intent_confidence) == (0.4, 0.86)


def test_without_spans():
    text = "Can you check the temperature for Yuksom?"
    start = text.index("Yuksom")
    assert without_spans(text, [(start, start + 6)]) == "Can you check the temperature for ?"
    assert without_spans("Gangtok", [(0, 7)]) == ""
    assert without_spans("rain in Gangtok and Namchi", [(8, 15), (20, 26)]) == "rain in and"


# --- the decision inside the pipeline ------------------------------------------------------

class FixedClassifier:
    """Always answers with the given label and probability."""

    def __init__(self, label, probability, runner_up=Intent.GENERAL_ENVIRONMENT):
        self.label, self.probability, self.runner_up = label, probability, runner_up

    def predict(self, texts):
        rest = [i for i in Intent if i not in (self.label, self.runner_up)]
        second = (1 - self.probability) * 0.9
        ranked = [(self.label, self.probability), (self.runner_up, second)]
        ranked += [(i, (1 - self.probability - second) / len(rest)) for i in rest]
        return [IntentPrediction(label=self.label, confidence=self.probability, ranked=ranked)
                for _ in texts]


class FixedScorer:
    def __init__(self, value):
        self.value, self.calls = value, []

    def score(self, text, location_spans):
        self.calls.append((text, location_spans))
        return self.value


THRESHOLDS = DecisionThresholds(temperature=1.0, min_intent_confidence=0.8,
                                min_domain_similarity=0.85)


def make(detector, classifier=None, scorer=None, thresholds=THRESHOLDS):  # noqa: F811
    return NlpPipeline(
        settings=SETTINGS, ontology=ONTOLOGY, detector=detector,
        classifier=classifier or KeywordClassifier(), recognizer=DictionaryRecognizer(),
        normalizer=EntityNormalizer(ONTOLOGY, SETTINGS.normalization),
        conversations=ConversationManager(SETTINGS.context),
        thresholds=thresholds, domain_scorer=scorer,
    )


def test_complete_confident_query_is_ok(detector):  # noqa: F811
    response = make(detector).analyze("What is the temperature in Gangtok?")
    assert response.status is Status.OK
    assert response.clarification is None
    assert response.needs_clarification is False


def test_missing_location_asks_for_it(detector):  # noqa: F811
    response = make(detector).analyze("What is the temperature?")
    assert response.status is Status.NEEDS_CLARIFICATION
    assert response.needs_clarification is True
    assert response.clarification.missing_fields == ["locations"]
    assert response.clarification.message_key == "missing_locations"
    # The partial query is still returned, so the UI can show what was understood.
    assert response.structured_query.variables == [Variable.TEMPERATURE]


def test_clarification_answer_completes_the_query(detector):  # noqa: F811
    pipeline = make(detector)
    pipeline.analyze("What is the temperature?", session_id="s", now=0)
    response = pipeline.analyze("Gangtok", session_id="s", now=1)
    assert response.status is Status.OK
    query_ = response.structured_query
    assert ([loc.id for loc in query_.locations], query_.variables) == (
        ["loc:gangtok"], [Variable.TEMPERATURE])


def test_scenario_without_location_asks_for_it(detector):  # noqa: F811
    response = make(detector).analyze("What happens if rainfall increases by 20%?")
    assert response.status is Status.NEEDS_CLARIFICATION
    assert response.clarification.missing_fields == ["locations"]
    assert response.structured_query.scenario.change == 20


def test_fragment_without_history_asks(detector):  # noqa: F811
    response = make(detector).analyze("What about rainfall?")
    assert response.status is Status.NEEDS_CLARIFICATION
    assert response.clarification.missing_fields == ["locations"]


def test_low_confidence_offers_the_two_likeliest_intents(detector):  # noqa: F811
    classifier = FixedClassifier(Intent.CLIMATE_TREND, 0.5, runner_up=Intent.WEATHER_QUERY)
    response = make(detector, classifier).analyze("rainfall in Gangtok")
    assert response.status is Status.NEEDS_CLARIFICATION
    assert response.clarification.reason == "low_confidence"
    assert response.clarification.options == ["CLIMATE_TREND", "WEATHER_QUERY"]


def test_low_confidence_followup_inherits_the_intent_instead_of_asking(detector):  # noqa: F811
    pipeline = make(detector)
    pipeline.analyze("What is the temperature in Gangtok?", session_id="s", now=0)
    # An unsure, wrong label on a query that only adds a time.
    pipeline._classifier = FixedClassifier(Intent.GENERAL_ENVIRONMENT, 0.42)
    response = pipeline.analyze("भोलिको अवस्था कस्तो हुन्छ?", session_id="s", now=1)
    assert response.status is Status.OK
    structured = response.structured_query
    assert structured.intent is Intent.WEATHER_QUERY
    assert structured.operation is Operation.FORECAST
    assert structured.answer_kind is AnswerKind.PREDICTION
    assert [loc.id for loc in structured.locations] == ["loc:gangtok"]
    assert "intent" in structured.context_used


def test_confident_out_of_domain_is_rejected(detector):  # noqa: F811
    response = make(detector).analyze("Who won yesterday's cricket match?")
    assert response.status is Status.OUT_OF_DOMAIN
    assert response.structured_query is None


def test_unsure_out_of_domain_is_asked_not_rejected(detector):  # noqa: F811
    classifier = FixedClassifier(Intent.OUT_OF_DOMAIN, 0.5, runner_up=Intent.WEATHER_QUERY)
    response = make(detector, classifier, FixedScorer(0.95)).analyze("Is it nice out there?")
    assert response.status is Status.NEEDS_CLARIFICATION
    assert response.clarification.reason == "low_confidence"
    assert response.structured_query is None


def test_low_similarity_overrides_a_confident_in_domain_label(detector):  # noqa: F811
    scorer = FixedScorer(0.5)
    pipeline = make(detector, FixedClassifier(Intent.WEATHER_QUERY, 0.95), scorer)
    response = pipeline.analyze("Book me a taxi from Siliguri to Gangtok")
    assert response.status is Status.OUT_OF_DOMAIN
    assert "low_domain_similarity" in response.warnings
    # The scorer was given the place spans to remove before embedding.
    text, spans = scorer.calls[0]
    assert [text[s:e] for s, e in spans] == ["Gangtok"]


def test_similarity_rejection_does_not_disturb_the_conversation(detector):  # noqa: F811
    pipeline = make(detector)
    pipeline.analyze("What is the temperature in Gangtok?", session_id="s", now=0)
    pipeline._domain_scorer = FixedScorer(0.5)
    rejected = pipeline.analyze("Book me a taxi to Gangtok", session_id="s", now=1)
    assert rejected.status is Status.OUT_OF_DOMAIN
    pipeline._domain_scorer = None
    followup = pipeline.analyze("What about humidity?", session_id="s", now=2)
    assert followup.status is Status.OK
    assert followup.structured_query.variables == [Variable.HUMIDITY]


def test_fragments_skip_the_similarity_check(detector):  # noqa: F811
    scorer = FixedScorer(0.1)
    pipeline = make(detector, scorer=scorer)
    pipeline._domain_scorer = None
    pipeline.analyze("What is the temperature in Gangtok?", session_id="s", now=0)
    pipeline._domain_scorer = scorer
    response = pipeline.analyze("Namchi", session_id="s", now=1)
    assert response.status is Status.OK
    assert scorer.calls == []


def test_unknown_place_asks_which_place(detector, monkeypatch):  # noqa: F811
    from backend.nlp.ner.model import PredictedEntity
    from backend.nlp.query.enums import EntityType

    pipeline = make(detector)
    monkeypatch.setattr(pipeline._recognizer, "predict", lambda texts: [[
        PredictedEntity(12, 23, EntityType.ENV_VARIABLE, "temperature", 0.9),
        PredictedEntity(27, 32, EntityType.LOCATION, "Paris", 0.9),
    ]])
    response = pipeline.analyze("What is the temperature in Paris?")
    assert response.status is Status.NEEDS_CLARIFICATION
    assert response.clarification.reason == "unknown_location"
    assert response.clarification.options == ["Paris"]


def test_trend_default_time_is_reported(detector):  # noqa: F811
    response = make(detector).analyze("Show the rainfall trend in Gangtok")
    assert response.status is Status.OK
    assert response.structured_query.time_period.value == CONFIG.default_trend_years
    assert "time_period_defaulted" in response.warnings


def test_calibration_changes_the_reported_confidence(detector):  # noqa: F811
    class Timid:
        """Right label at 0.5, the rest spread evenly: an under-confident model."""

        def predict(self, texts):
            others = [i for i in Intent if i is not Intent.WEATHER_QUERY]
            ranked = [(Intent.WEATHER_QUERY, 0.5)] + [(i, 0.5 / len(others)) for i in others]
            return [IntentPrediction(label=Intent.WEATHER_QUERY, confidence=0.5, ranked=ranked)
                    for _ in texts]

    sharpen = DecisionThresholds(temperature=0.35, min_intent_confidence=0.8)
    text = "What is the temperature in Gangtok?"
    raw = make(detector, Timid(), thresholds=DecisionThresholds()).analyze(text)
    assert raw.intent.confidence == pytest.approx(0.5)
    response = make(detector, Timid(), thresholds=sharpen).analyze(text)
    assert response.intent.confidence > 0.95
    assert response.status is Status.OK


# --- regressions from the final-evaluation investigation --------------------------

def clustered_example():
    """10 families of 20 rows. One whole family is wrong at high confidence."""
    groups = [f"family_{i}" for i in range(10) for _ in range(20)]
    correct = np.array([g != "family_0" for g in groups])
    confidence = np.full(200, 0.9)
    return groups, correct, confidence


def test_family_level_bound_is_wider_than_the_row_level_error():
    from backend.nlp.intent.calibration import add_clustered_bound

    groups, correct, confidence = clustered_example()
    curve = coverage_curve(confidence, correct, np.array([0.3]))
    assert curve[0]["answered_error"] == pytest.approx(0.10)

    by_family = add_clustered_bound(curve, confidence, correct, groups, 0.9, 500, seed=0)
    by_row = add_clustered_bound(curve, confidence, correct,
                                 [str(i) for i in range(200)], 0.9, 500, seed=0)
    # Treating rows as independent understates the uncertainty.
    assert by_row[0]["answered_error_upper"] < by_family[0]["answered_error_upper"]
    assert by_family[0]["answered_error_upper"] >= 0.15


def test_threshold_is_not_inert_when_errors_come_in_whole_families():
    # The defect: validation error was under the target at every threshold, so
    # the rule returned its minimum and nothing was ever questioned. With the
    # family-level bound, a model whose mistakes are low-confidence gets a
    # threshold that removes them.
    from backend.nlp.intent.calibration import add_clustered_bound

    groups = [f"family_{i}" for i in range(25) for _ in range(10)]
    correct = np.array([g != "family_0" for g in groups])           # 4% wrong
    confidence = np.where(correct, 0.95, 0.6)
    grid = np.round(np.arange(0.30, 0.991, 0.01), 2)
    curve = add_clustered_bound(coverage_curve(confidence, correct, grid),
                                confidence, correct, groups, 0.9, 500, seed=0)

    naive = select_threshold(curve, target_error=0.05)
    bounded = select_threshold(curve, target_error=0.05, key="answered_error_upper")
    assert naive["threshold"] == pytest.approx(0.30)       # the old, inert choice
    assert 0.6 < bounded["threshold"] <= 0.95              # now it rejects the weak family
    assert bounded["answered_error"] == 0.0


def test_select_threshold_falls_back_to_the_lowest_bound():
    curve = [{"threshold": 0.3, "answered_error": 0.2, "answered_error_upper": 0.4},
             {"threshold": 0.9, "answered_error": 0.1, "answered_error_upper": 0.3}]
    assert select_threshold(curve, 0.05, key="answered_error_upper")["threshold"] == 0.9


DISAGREE = DecisionThresholds(temperature=1.0, min_intent_confidence=0.8,
                              min_domain_similarity=0.85, in_domain_similarity=0.93)


def test_confident_off_topic_verdict_on_an_in_domain_looking_query_is_asked(detector):  # noqa: F811
    # The defect: Hindi and Nepali questions such as "how can a flood be
    # prevented?" were rejected at 0.98 confidence. A threshold cannot catch a
    # confident error; an independent signal can.
    classifier = FixedClassifier(Intent.OUT_OF_DOMAIN, 0.98)
    pipeline = make(detector, classifier, FixedScorer(0.95), thresholds=DISAGREE)
    response = pipeline.analyze("बाढ़ से कैसे बचा जा सकता है?")
    assert response.status is Status.NEEDS_CLARIFICATION
    assert response.clarification.reason == "signals_disagree"
    assert "signals_disagree" in response.warnings
    assert response.structured_query is None


def test_confident_off_topic_verdict_is_kept_when_similarity_is_unremarkable(detector):  # noqa: F811
    classifier = FixedClassifier(Intent.OUT_OF_DOMAIN, 0.98)
    pipeline = make(detector, classifier, FixedScorer(0.88), thresholds=DISAGREE)
    assert pipeline.analyze("Tell me a joke about a cat").status is Status.OUT_OF_DOMAIN


def test_disagreement_rule_is_off_by_default():
    assert DecisionThresholds().in_domain_similarity > 1.0
