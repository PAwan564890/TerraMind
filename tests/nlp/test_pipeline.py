"""Pipeline tests with stand-in components.

The language detector and normaliser are real. The intent classifier and NER
model are replaced by simple stand-ins (a keyword table and a dictionary
scan), so these tests need no trained model and check the WIRING: that the
right pieces are called in the right order and combined correctly.
"""

import re

import pytest

from backend.core import load_settings
from backend.nlp.context import ConversationManager
from backend.nlp.dataset.generator import load_lexicon
from backend.nlp.dataset.records import read_jsonl
from backend.nlp.intent.predictor import IntentPrediction
from backend.nlp.language_detection import LanguageDetector
from backend.nlp.language_detection.train import build_training_set, train_classifier
from backend.nlp.ner.model import PredictedEntity
from backend.nlp.normalization import EntityNormalizer
from backend.nlp.ontology import get_ontology
from backend.nlp.pipeline import NlpPipeline
from backend.nlp.preprocessing import InvalidQueryError, lookup_key
from backend.nlp.query.cues import derive_operation, detect_direction
from backend.nlp.query.enums import (
    AnswerKind,
    Direction,
    EntityType,
    Intent,
    Language,
    Operation,
    RiskTarget,
    Status,
    TimeType,
    Variable,
)
from backend.nlp.query.schema import StructuredQuery

SETTINGS = load_settings()
ONTOLOGY = get_ontology()


class KeywordClassifier:
    """Picks the intent from a few keywords; first match wins."""

    RULES = [
        (r"cricket|joke|क्रिकेट", Intent.OUT_OF_DOMAIN),
        (r"\bif\b|अगर|यदि|भने", Intent.SCENARIO_ANALYSIS),
        (r"compare|तुलना", Intent.COMPARISON),
        (r"risk|खतरा|जोखिम|landslide", Intent.DISASTER_RISK),
        (r"trend|रुझान|प्रवृत्ति", Intent.CLIMATE_TREND),
        (r"vegetation|ndvi", Intent.VEGETATION_ANALYSIS),
        (r"where is", Intent.GEOLOCATION_QUERY),
    ]

    def predict(self, texts):
        results = []
        for text in texts:
            label = next((intent for pattern, intent in self.RULES
                          if re.search(pattern, text.casefold())), Intent.WEATHER_QUERY)
            ranked = [(label, 0.9)] + [(i, 0.0125) for i in Intent if i is not label]
            results.append(IntentPrediction(label=label, confidence=0.9, ranked=ranked))
        return results


class DictionaryRecognizer:
    """Finds entities by scanning for known aliases and lexicon phrases."""

    def __init__(self):
        phrases: list[tuple[str, EntityType]] = []
        for entry in ONTOLOGY.locations.values():
            phrases += [(a, EntityType.LOCATION) for a in entry.aliases.all()]
        for entry in ONTOLOGY.variables.values():
            phrases += [(a, EntityType.ENV_VARIABLE) for a in entry.aliases.all()]
        for entry in ONTOLOGY.disasters.values():
            phrases += [(a, EntityType.DISASTER) for a in entry.aliases.all()]
        lexicon = load_lexicon()
        for slot in ("now", "past", "future", "range"):
            for items in lexicon["time"][slot].values():
                phrases += [(i if isinstance(i, str) else i[0], EntityType.TIME) for i in items]
        for slot in ("pct", "abs"):
            for items in lexicon["change"][slot].values():
                phrases += [(i[0], EntityType.CHANGE) for i in items]
        # Longest first, so "North Sikkim" wins over "Sikkim".
        self._phrases = sorted(set(phrases), key=lambda p: len(p[0]), reverse=True)

    def predict(self, texts):
        results = []
        for text in texts:
            lowered, taken, found = text.casefold(), [], []
            for phrase, entity_type in self._phrases:
                start = lowered.find(phrase.casefold())
                if start < 0:
                    continue
                end = start + len(phrase)
                if any(start < e and s < end for s, e in taken):
                    continue
                # Latin phrases must be whole words ("rain" not inside "train").
                if phrase.isascii() and (
                    (start > 0 and lowered[start - 1].isalnum())
                    or (end < len(lowered) and lowered[end].isalnum())
                ):
                    continue
                taken.append((start, end))
                found.append(PredictedEntity(start, end, entity_type, text[start:end], 0.9))
            results.append(sorted(found, key=lambda e: e.start))
        return results


@pytest.fixture(scope="module")
def detector():
    train = read_jsonl(SETTINGS.paths.data_dir / "train.jsonl")
    config = SETTINGS.language_detection
    texts, labels = build_training_set(train, config, SETTINGS.project.seed)
    return LanguageDetector(train_classifier(texts, labels, config, SETTINGS.project.seed),
                            config.min_confidence)


@pytest.fixture
def pipeline(detector):
    # A fresh pipeline per test, so conversations do not leak between tests.
    return NlpPipeline(
        settings=SETTINGS, ontology=ONTOLOGY, detector=detector,
        classifier=KeywordClassifier(), recognizer=DictionaryRecognizer(),
        normalizer=EntityNormalizer(ONTOLOGY, SETTINGS.normalization),
        conversations=ConversationManager(SETTINGS.context),
    )


def comparable(query: StructuredQuery) -> dict:
    return query.model_dump(mode="json")


# --- the three examples from the project brief -------------------------------------

TREND_IN_THREE_LANGUAGES = {
    Language.EN: "What is the rainfall trend in Gangtok over the last five years?",
    Language.HI: "गंगटोक में पिछले पांच सालों में बारिश का क्या रुझान रहा है?",
    Language.NE: "गान्तोकमा पछिल्ला पाँच वर्षको वर्षाको प्रवृत्ति कस्तो रहेको छ?",
}


def test_same_question_in_three_languages_gives_the_same_query(pipeline):
    responses = {lang: pipeline.analyze(text) for lang, text in TREND_IN_THREE_LANGUAGES.items()}
    for language, response in responses.items():
        assert response.language.code is language
        assert response.status is Status.OK

    english = responses[Language.EN].structured_query
    assert english.intent is Intent.CLIMATE_TREND
    assert english.operation is Operation.TREND
    assert english.answer_kind is AnswerKind.ANALYSIS
    assert [loc.id for loc in english.locations] == ["loc:gangtok"]
    assert english.variables == [Variable.PRECIPITATION]
    assert (english.time_period.type, english.time_period.value) == (TimeType.RELATIVE_PAST, 5)
    # Only the language field differs; the structured query is identical.
    assert comparable(responses[Language.HI].structured_query) == comparable(english)
    assert comparable(responses[Language.NE].structured_query) == comparable(english)


def test_hindi_scenario_example(pipeline):
    response = pipeline.analyze(
        "गंगटोक में अगर बारिश 20% बढ़ जाए तो बाढ़ का खतरा कितना बदल सकता है?"
    )
    query = response.structured_query
    assert response.language.code is Language.HI
    assert query.intent is Intent.SCENARIO_ANALYSIS
    assert query.operation is Operation.SCENARIO
    assert query.answer_kind is AnswerKind.SCENARIO
    assert [loc.id for loc in query.locations] == ["loc:gangtok"]
    assert query.variables == [Variable.PRECIPITATION]
    assert query.scenario.model_dump(mode="json") == {
        "variable": "PRECIPITATION", "change": 20.0, "unit": "percent", "direction": "increase",
    }
    assert query.target is RiskTarget.FLOOD_RISK


def test_comparison_example(pipeline):
    query = pipeline.analyze("Compare rainfall in North Sikkim and South Sikkim.").structured_query
    assert query.intent is Intent.COMPARISON
    assert query.operation is Operation.COMPARE
    assert [loc.id for loc in query.locations] == ["loc:mangan_district", "loc:namchi_district"]
    assert query.variables == [Variable.PRECIPITATION]


# --- response shape -----------------------------------------------------------------

def test_entities_carry_offsets_into_the_normalised_text(pipeline):
    response = pipeline.analyze("  What is the   rainfall in Gangtok ??  ")
    text = "What is the rainfall in Gangtok?"
    assert [(text[e.start:e.end], e.type, e.normalized) for e in response.entities] == [
        ("rainfall", EntityType.ENV_VARIABLE, "PRECIPITATION"),
        ("Gangtok", EntityType.LOCATION, "loc:gangtok"),
    ]


def test_nepali_suffix_is_handled_end_to_end(pipeline):
    response = pipeline.analyze("नाम्चीमा तापक्रम कति छ?")
    assert [loc.id for loc in response.structured_query.locations] == ["loc:namchi"]


def test_out_of_domain_has_no_structured_query(pipeline):
    response = pipeline.analyze("Who won yesterday's cricket match?")
    assert response.status is Status.OUT_OF_DOMAIN
    assert response.structured_query is None
    assert response.intent.label is Intent.OUT_OF_DOMAIN


def test_unknown_place_is_reported_not_guessed(pipeline, monkeypatch):
    def fake_predict(texts):
        return [[PredictedEntity(19, 24, EntityType.LOCATION, "Paris", 0.9)]]

    monkeypatch.setattr(pipeline._recognizer, "predict", fake_predict)
    response = pipeline.analyze("What is the weather in Paris?")
    assert response.structured_query.locations == []
    assert "unresolved_location:Paris" in response.warnings
    assert response.entities[0].normalized is None


def test_invalid_input_raises(pipeline):
    with pytest.raises(InvalidQueryError):
        pipeline.analyze("   ")


def test_time_is_found_by_rules_when_ner_misses_it(pipeline):
    response = pipeline.analyze("What is the temperature in Gangtok these days?")
    assert response.structured_query.time_period.type is TimeType.CURRENT
    assert "time_from_rules" in response.warnings


def test_forecast_and_answer_kind(pipeline):
    query = pipeline.analyze("What will the temperature be in Gangtok tomorrow?").structured_query
    assert (query.operation, query.answer_kind) == (Operation.FORECAST, AnswerKind.PREDICTION)


def test_incomplete_scenario_is_flagged(pipeline):
    response = pipeline.analyze("What if rainfall changes by 20% in Gangtok?")
    assert response.structured_query.scenario is None
    assert "incomplete_scenario:direction" in response.warnings


def test_two_variable_scenario_separates_cause_and_target(pipeline):
    query = pipeline.analyze(
        "How would vegetation be affected if rainfall drops by 20% in Gangtok?"
    ).structured_query
    assert query.scenario.variable is Variable.PRECIPITATION
    assert query.scenario.direction is Direction.DECREASE
    assert query.target is Variable.NDVI


# --- conversations -------------------------------------------------------------------

def test_cross_language_followup(pipeline):
    pipeline.analyze("What is the temperature in Gangtok?", session_id="s", now=0)
    second = pipeline.analyze("और बारिश?", session_id="s", now=1)
    assert second.language.code is Language.HI
    query = second.structured_query
    assert query.intent is Intent.WEATHER_QUERY
    assert [loc.id for loc in query.locations] == ["loc:gangtok"]
    assert query.variables == [Variable.PRECIPITATION]
    assert sorted(query.context_used) == ["intent", "locations"]

    third = pipeline.analyze("What about tomorrow?", session_id="s", now=2)
    query = third.structured_query
    assert query.operation is Operation.FORECAST
    assert query.variables == [Variable.PRECIPITATION]
    assert sorted(query.context_used) == ["intent", "locations", "variables"]


def test_without_session_there_is_no_memory(pipeline):
    pipeline.analyze("What is the temperature in Gangtok?")
    response = pipeline.analyze("What about rainfall?")
    assert response.structured_query.locations == []
    assert response.structured_query.context_used == []


def test_followup_intent_reports_the_classifiers_probability_for_it(pipeline):
    pipeline.analyze("Show the rainfall trend in Gangtok", session_id="s", now=0)
    response = pipeline.analyze("What about Namchi?", session_id="s", now=1)
    # The stand-in classifier said WEATHER_QUERY (0.9); context made it a trend.
    assert response.intent.label is Intent.CLIMATE_TREND
    assert response.intent.confidence == pytest.approx(0.0125)


def test_short_devanagari_followup_uses_session_language(pipeline):
    pipeline.analyze("गान्तोकमा तापक्रम कति छ?", session_id="s", now=0)
    response = pipeline.analyze("२०%", session_id="s", now=1)
    assert response.language.code is Language.NE
    assert "language_from_context" in response.warnings


# --- cue words ------------------------------------------------------------------------

@pytest.mark.parametrize(
    "intent, language, text, expected",
    [
        (Intent.CLIMATE_TREND, Language.EN, "Why has the rainfall been changing?", Operation.EXPLAIN),
        (Intent.CLIMATE_TREND, Language.HI, "बारिश क्यों बदल रही है?", Operation.EXPLAIN),
        (Intent.CLIMATE_TREND, Language.NE, "वर्षा किन परिवर्तन भइरहेको छ?", Operation.EXPLAIN),
        (Intent.CLIMATE_TREND, Language.EN, "Show the rainfall trend", Operation.TREND),
        (Intent.VEGETATION_ANALYSIS, Language.EN, "Is vegetation increasing in Gangtok?", Operation.TREND),
        (Intent.VEGETATION_ANALYSIS, Language.EN, "What is the land cover status?", Operation.LOOKUP),
        (Intent.DISASTER_RISK, Language.EN, "Which areas have high landslide risk?", Operation.RANK),
        (Intent.DISASTER_RISK, Language.HI, "किन इलाकों में बाढ़ का खतरा ज़्यादा है?", Operation.RANK),
        (Intent.DISASTER_RISK, Language.NE, "गान्तोक किन पहिरोको उच्च जोखिममा छ?", Operation.EXPLAIN),
        (Intent.DISASTER_RISK, Language.EN, "What is the flood risk in Rangpo?", Operation.LOOKUP),
        # A cue never produces an operation the intent does not allow.
        (Intent.WEATHER_QUERY, Language.EN, "Why is the temperature high?", Operation.LOOKUP),
        (Intent.COMPARISON, Language.EN, "Why compare the trend?", Operation.COMPARE),
    ],
)
def test_operation_cues(intent, language, text, expected):
    assert derive_operation(intent, language, lookup_key(text), None) is expected


@pytest.mark.parametrize(
    "text, expected",
    [
        ("What happens if rainfall increases by 20%?", Direction.INCREASE),
        ("If Gangtok got 20% more rain", Direction.INCREASE),
        ("What if the temperature falls by 2 degrees?", Direction.DECREASE),
        ("if rainfall drops by 20%", Direction.DECREASE),
        ("अगर बारिश 20% बढ़ जाए तो", Direction.INCREASE),
        ("बारिश 20% घट जाए तो", Direction.DECREASE),
        ("वर्षा 20%ले बढ्यो भने", Direction.INCREASE),
        ("वर्षा 20%ले घट्यो भने", Direction.DECREASE),
        ("What if rainfall changes by 20%?", None),
    ],
)
def test_direction_cues(text, expected):
    assert detect_direction(text) is expected


def test_direction_nearest_to_the_amount_wins():
    text = "Would flood risk rise if rainfall dropped by 20%?"
    assert detect_direction(text, near=text.index("20%")) is Direction.DECREASE


# --- regressions ------------------------------------------------------------------

@pytest.mark.parametrize(
    "text",
    ["What explains the drop in greenery in West Sikkim?",
     "Can you explain why vegetation is falling?",
     "How come the greenery is shrinking?",
     "What is behind the loss of vegetation?"],
)
def test_explanation_cues_beyond_why(text):
    # "explain" itself was missing: the cue list had been written from the
    # wording of the training templates only.
    assert derive_operation(
        Intent.VEGETATION_ANALYSIS, Language.EN, lookup_key(text), None
    ) is Operation.EXPLAIN


def test_hindi_idiom_haal_adds_no_time_to_the_query(pipeline):
    response = pipeline.analyze("लाचुंग में वनस्पति का क्या हाल है?")
    assert response.structured_query.time_period is None
    assert "time_from_rules" not in response.warnings


def test_merged_place_span_from_ner_is_split_end_to_end(pipeline, monkeypatch):
    # The defect: the final NER model returned one LOCATION span for two
    # adjacent names, which matched nothing and produced "unknown place".
    text = "क्या मंगन नामची से ज़्यादा ठंडा है?"
    start = text.index("मंगन")
    end = text.index("नामची") + len("नामची")
    monkeypatch.setattr(pipeline._recognizer, "predict", lambda texts: [[
        PredictedEntity(start, end, EntityType.LOCATION, text[start:end], 0.9),
    ]])
    response = pipeline.analyze(text)
    assert [loc.id for loc in response.structured_query.locations] == ["loc:mangan", "loc:namchi"]
    assert [(e.text, e.normalized) for e in response.entities] == [
        ("मंगन", "loc:mangan"), ("नामची", "loc:namchi")]
    assert not any(w.startswith("unresolved_location") for w in response.warnings)
    for entity in response.entities:
        assert text[entity.start:entity.end] == entity.text
