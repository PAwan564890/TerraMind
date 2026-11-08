"""Language detection for English, Hindi and Nepali.

Two stages:
  1. Script check. English is written in Latin letters, Hindi and Nepali in
     Devanagari, so counting letters separates English from the other two.
  2. For Devanagari text, a character n-gram classifier separates Hindi from
     Nepali. The two share a script and much vocabulary, but differ in
     function words and endings (है / में / का  vs  छ / मा / को).
"""

import unicodedata
from pathlib import Path
from typing import Literal

import joblib
from pydantic import BaseModel
from sklearn.pipeline import Pipeline

from backend.nlp.query.enums import Language

# Above this share of Latin letters, a query is treated as English even if it
# contains a few Devanagari characters.
_ENGLISH_LATIN_SHARE = 0.8


class LanguageModelNotFound(Exception):
    """Raised when the Hindi/Nepali classifier has not been trained yet."""


class LanguageDetection(BaseModel):
    code: Language
    confidence: float
    # script: decided by counting letters; model: decided by the classifier;
    # fallback: detection was unsure and the caller's fallback was used.
    method: Literal["script", "model", "fallback"]
    mixed_script: bool = False


def _is_devanagari(ch: str) -> bool:
    # Letters (L*) and vowel signs / marks (M*) in the Devanagari block.
    # Digits and the danda are excluded: they carry no language signal.
    return "ऀ" <= ch <= "ॿ" and unicodedata.category(ch)[0] in "LM"


def script_counts(text: str) -> tuple[int, int]:
    """Number of (Devanagari, Latin) letters in the text."""
    devanagari = sum(_is_devanagari(ch) for ch in text)
    latin = sum(ch.isascii() and ch.isalpha() for ch in text)
    return devanagari, latin


def devanagari_only(text: str) -> str:
    """Keep Devanagari words, drop everything else.

    Digits are removed on purpose: whether someone types "10" or "१०" is a
    typing habit, not a property of the language, and the classifier must not
    learn it as one.
    """
    text = unicodedata.normalize("NFC", text)
    kept = "".join(ch if _is_devanagari(ch) else " " for ch in text)
    return " ".join(kept.split())


class LanguageDetector:
    def __init__(self, model: Pipeline, min_confidence: float) -> None:
        self._model = model
        self._min_confidence = min_confidence

    @classmethod
    def load(cls, model_path: Path, min_confidence: float) -> "LanguageDetector":
        if not model_path.is_file():
            raise LanguageModelNotFound(
                f"{model_path} not found. Run: python scripts/train_language_detector.py"
            )
        return cls(joblib.load(model_path), min_confidence)

    def detect(self, text: str, fallback: Language | None = None) -> LanguageDetection:
        """Detect the language of one query.

        `fallback` is the language of the previous turn in the conversation.
        It is used only when the text itself gives too little evidence, as
        with a one-word follow-up.
        """
        devanagari, latin = script_counts(text)
        letters = devanagari + latin
        mixed = devanagari > 0 and latin > 0

        if letters == 0:
            # Only digits or punctuation: nothing to detect.
            return LanguageDetection(
                code=fallback or Language.EN, confidence=0.0, method="fallback"
            )

        latin_share = latin / letters
        if devanagari == 0 or latin_share > _ENGLISH_LATIN_SHARE:
            return LanguageDetection(
                code=Language.EN, confidence=latin_share, method="script", mixed_script=mixed
            )

        probabilities = self._model.predict_proba([devanagari_only(text)])[0]
        best = int(probabilities.argmax())
        code = Language(self._model.classes_[best])
        confidence = float(probabilities[best])

        if confidence < self._min_confidence and fallback in (Language.HI, Language.NE):
            return LanguageDetection(
                code=fallback, confidence=confidence, method="fallback", mixed_script=mixed
            )
        return LanguageDetection(
            code=code, confidence=confidence, method="model", mixed_script=mixed
        )
