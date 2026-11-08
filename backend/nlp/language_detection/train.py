"""Training for the Hindi-versus-Nepali classifier."""

import random

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline

from backend.core.config import LanguageDetectionConfig
from backend.nlp.dataset.records import DatasetRecord
from backend.nlp.language_detection.detector import devanagari_only
from backend.nlp.query.enums import Language


def make_fragments(text: str, count: int, rng: random.Random) -> list[str]:
    """Random 1-3 word windows from a sentence.

    Follow-up questions are often one or two words. Training only on full
    sentences would leave the classifier with no experience of short input.
    """
    words = text.split()
    fragments = []
    for _ in range(count):
        size = rng.randint(1, min(3, len(words)))
        start = rng.randint(0, len(words) - size)
        fragments.append(" ".join(words[start:start + size]))
    return fragments


def build_training_set(
    records: list[DatasetRecord], config: LanguageDetectionConfig, seed: int
) -> tuple[list[str], list[str]]:
    """Devanagari-only text and labels from the Hindi and Nepali rows."""
    rng = random.Random(seed)
    texts, labels = [], []
    for record in records:
        if record.language is Language.EN:
            continue
        cleaned = devanagari_only(record.text)
        if not cleaned:
            continue
        for text in [cleaned, *make_fragments(cleaned, config.fragments_per_row, rng)]:
            texts.append(text)
            labels.append(record.language.value)
    return texts, labels


def train_classifier(
    texts: list[str], labels: list[str], config: LanguageDetectionConfig, seed: int
) -> Pipeline:
    """TF-IDF over character n-grams, then logistic regression.

    "char_wb" builds n-grams inside word boundaries and pads each word with a
    space, so a word ending such as "मा " becomes a feature of its own.
    """
    model = Pipeline([
        ("tfidf", TfidfVectorizer(
            analyzer="char_wb",
            ngram_range=(config.ngram_min, config.ngram_max),
            sublinear_tf=True,
        )),
        ("classifier", LogisticRegression(max_iter=1000, random_state=seed)),
    ])
    model.fit(texts, labels)
    return model
