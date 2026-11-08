import pytest

from backend.core import load_settings
from backend.nlp.dataset.records import read_jsonl
from backend.nlp.evaluation.classification import classification_report
from backend.nlp.language_detection import (
    LanguageDetector,
    LanguageModelNotFound,
    devanagari_only,
    script_counts,
)
from backend.nlp.language_detection.train import build_training_set, train_classifier
from backend.nlp.query.enums import Language

SETTINGS = load_settings()
CONFIG = SETTINGS.language_detection


@pytest.fixture(scope="module")
def detector():
    # Trained from the committed data, so the test needs no saved model file.
    train = read_jsonl(SETTINGS.paths.data_dir / "train.jsonl")
    texts, labels = build_training_set(train, CONFIG, SETTINGS.project.seed)
    return LanguageDetector(
        train_classifier(texts, labels, CONFIG, SETTINGS.project.seed), CONFIG.min_confidence
    )


def test_script_counts():
    assert script_counts("Gangtok") == (0, 7)
    assert script_counts("बारिश") == (5, 0)
    assert script_counts("20% १०!") == (0, 0)


def test_devanagari_only_drops_latin_digits_and_punctuation():
    assert devanagari_only("Gangtok में 20% बारिश, १० दिन?") == "में बारिश दिन"


@pytest.mark.parametrize(
    "text, expected",
    [
        ("What is the rainfall trend in Gangtok over the last five years?", Language.EN),
        ("temperature in Namchi", Language.EN),
        ("गंगटोक में पिछले पांच सालों में बारिश का क्या रुझान रहा है?", Language.HI),
        ("गंगटोक में अगर बारिश 20% बढ़ जाए तो बाढ़ का खतरा कितना बदल सकता है?", Language.HI),
        ("गान्तोकमा पछिल्ला पाँच वर्षको वर्षाको प्रवृत्ति कस्तो रहेको छ?", Language.NE),
        ("भोलिको अवस्था कस्तो हुन्छ?", Language.NE),
    ],
)
def test_detects_the_three_languages(detector, text, expected):
    assert detector.detect(text).code is expected


def test_english_is_decided_by_script_alone(detector):
    result = detector.detect("Compare rainfall in North Sikkim and South Sikkim.")
    assert result.method == "script"
    assert result.confidence == 1.0
    assert result.mixed_script is False


def test_code_mixed_text_is_flagged(detector):
    result = detector.detect("Gangtok में rainfall कितना है?")
    assert result.mixed_script is True
    assert result.code is Language.HI


def test_mostly_english_with_one_devanagari_word_stays_english(detector):
    result = detector.detect("What is the meaning of the word बारिश in English please?")
    assert result.code is Language.EN
    assert result.mixed_script is True


def test_no_letters_uses_fallback(detector):
    assert detector.detect("20%").code is Language.EN
    result = detector.detect("२०%", fallback=Language.NE)
    assert result.code is Language.NE
    assert result.method == "fallback"
    assert result.confidence == 0.0


def test_fallback_applies_only_when_the_model_is_unsure():
    class Unsure:
        classes_ = ["hi", "ne"]

        def predict_proba(self, texts):
            import numpy as np

            return np.array([[0.55, 0.45]])

    unsure = LanguageDetector(Unsure(), min_confidence=0.6)
    assert unsure.detect("सिक्किम").code is Language.HI
    result = unsure.detect("सिक्किम", fallback=Language.NE)
    assert (result.code, result.method) == (Language.NE, "fallback")
    # An English fallback cannot override Devanagari text.
    assert unsure.detect("सिक्किम", fallback=Language.EN).code is Language.HI


def test_missing_model_gives_a_helpful_error(tmp_path):
    with pytest.raises(LanguageModelNotFound, match="train_language_detector"):
        LanguageDetector.load(tmp_path / "missing.joblib", 0.6)


def test_accuracy_on_validation_split(detector):
    val = read_jsonl(SETTINGS.paths.data_dir / "val.jsonl")
    predicted = [detector.detect(r.text).code for r in val]
    accuracy = sum(p is r.language for p, r in zip(predicted, val)) / len(val)
    assert accuracy >= 0.95


def test_classification_report_counts_unexpected_predictions():
    report = classification_report(["en", "hi", "ne"], ["en", "mr", "ne"], ["en", "hi", "ne"])
    assert report["accuracy"] == pytest.approx(2 / 3)
    assert report["per_class"]["hi"]["recall"] == 0.0
    assert report["confusion"]["cols_predicted"][-1] == "other"
    assert report["confusion"]["matrix"][1] == [0, 0, 0, 1]
