"""Train and evaluate the language detector.

Run from the project root:
    python scripts/train_language_detector.py
"""

import json
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import joblib  # noqa: E402

from backend.core import load_settings, setup_logging  # noqa: E402
from backend.nlp.dataset.records import load_gold, read_jsonl  # noqa: E402
from backend.nlp.evaluation.classification import classification_report, format_report  # noqa: E402
from backend.nlp.language_detection.detector import LanguageDetector  # noqa: E402
from backend.nlp.language_detection.train import (  # noqa: E402
    build_training_set,
    make_fragments,
    train_classifier,
)
from backend.nlp.ontology import get_ontology  # noqa: E402
from backend.nlp.query.enums import Language  # noqa: E402

LABELS = [language.value for language in Language]
MODEL_FILE = "hi_ne.joblib"


def length_bucket(text: str) -> str:
    words = len(text.split())
    return "1-2 words" if words <= 2 else "3-5 words" if words <= 5 else "6+ words"


def baseline_predict(texts: list[str]) -> list[str] | None:
    """Predictions from the off-the-shelf `langdetect` package, for comparison."""
    try:
        from langdetect import DetectorFactory, LangDetectException, detect
    except ImportError:
        return None
    DetectorFactory.seed = 0  # langdetect is random unless seeded
    predictions = []
    for text in texts:
        try:
            predictions.append(detect(text))
        except LangDetectException:
            predictions.append("unknown")
    return predictions


def main() -> int:
    setup_logging()
    sys.stdout.reconfigure(encoding="utf-8")

    settings = load_settings()
    config = settings.language_detection
    seed = settings.project.seed
    data_dir = settings.paths.data_dir
    out_dir = settings.paths.models_dir / "language_detection"

    train = read_jsonl(data_dir / "train.jsonl")
    val = read_jsonl(data_dir / "val.jsonl")
    test = read_jsonl(data_dir / "test" / "test.jsonl")
    gold = load_gold(data_dir / "test" / "gold.yaml", get_ontology())

    texts, labels = build_training_set(train, config, seed)
    model = train_classifier(texts, labels, config, seed)
    out_dir.mkdir(parents=True, exist_ok=True)
    joblib.dump(model, out_dir / MODEL_FILE)
    print(f"trained on {len(texts)} Hindi/Nepali texts -> {out_dir / MODEL_FILE}\n")

    detector = LanguageDetector(model, config.min_confidence)

    def evaluate(title: str, texts: list[str], truth: list[str], labels=LABELS) -> dict:
        predictions = [detector.detect(text).code.value for text in texts]
        report = classification_report(truth, predictions, labels)
        print(format_report(title, report) + "\n")
        return report

    metrics = {}
    eval_sets = {
        "validation": ([r.text for r in val], [r.language.value for r in val]),
        "test": ([r.text for r in test], [r.language.value for r in test]),
        "gold": ([g.text for g in gold], [g.language.value for g in gold]),
    }
    for name, (set_texts, truth) in eval_sets.items():
        metrics[name] = evaluate(name, set_texts, truth)

    # Accuracy by query length, on the test split.
    test_texts, test_truth = eval_sets["test"]
    metrics["test_by_length"] = {}
    for bucket in ("1-2 words", "3-5 words", "6+ words"):
        chosen = [i for i, text in enumerate(test_texts) if length_bucket(text) == bucket]
        if chosen:
            metrics["test_by_length"][bucket] = evaluate(
                f"test, {bucket}",
                [test_texts[i] for i in chosen],
                [test_truth[i] for i in chosen],
            )

    # Hard case: one- and two-word pieces cut from Hindi and Nepali test rows.
    rng = random.Random(seed)
    fragment_texts, fragment_truth = [], []
    for record in test:
        if record.language is not Language.EN:
            words = record.text.split()[:2]
            fragment_texts.append(" ".join(words[: rng.randint(1, len(words))]))
            fragment_truth.append(record.language.value)
    metrics["test_fragments"] = evaluate(
        "test, 1-2 word fragments (hi/ne only)", fragment_texts, fragment_truth,
        labels=["hi", "ne"],
    )

    for name in ("test", "gold"):
        set_texts, truth = eval_sets[name]
        predictions = baseline_predict(set_texts)
        if predictions is None:
            print("langdetect not installed; baseline skipped")
            break
        report = classification_report(truth, predictions, LABELS)
        print(format_report(f"BASELINE langdetect, {name}", report) + "\n")
        metrics[f"baseline_langdetect_{name}"] = report

    metrics["config"] = {"seed": seed, **config.model_dump()}
    metrics_path = out_dir / "metrics.json"
    metrics_path.write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    print(f"metrics saved to {metrics_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
