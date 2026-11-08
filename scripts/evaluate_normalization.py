"""Evaluate entity normalisation.

Run from the project root:
    python scripts/evaluate_normalization.py

Three measurements:
  1. Given the CORRECT span (from the dataset labels), is the canonical value right?
  2. How does the fuzzy threshold trade recall on typos against false matches?
  3. Given spans PREDICTED by the NER model, how many true values are recovered?
     (Skipped if no NER model has been trained.)
"""

import json
import random
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.core import load_settings, setup_logging  # noqa: E402
from backend.nlp.dataset.generator import load_lexicon  # noqa: E402
from backend.nlp.dataset.records import DatasetRecord, SpanLabel, read_jsonl  # noqa: E402
from backend.nlp.normalization import ChangeValue, EntityNormalizer  # noqa: E402
from backend.nlp.normalization.normalizer import canonical_change, canonical_time  # noqa: E402
from backend.nlp.ontology import get_ontology  # noqa: E402
from backend.nlp.query.enums import ChangeUnit, EntityType, Language  # noqa: E402
from backend.nlp.query.schema import TimePeriod  # noqa: E402

SCOPES = ("all", "en", "hi", "ne")


def gold_canonical(entity: SpanLabel) -> str:
    """The dataset's normalised value in the same string form the normaliser emits."""
    if entity.type is EntityType.TIME:
        return canonical_time(TimePeriod.model_validate(entity.normalized))
    if entity.type is EntityType.CHANGE:
        return canonical_change(ChangeValue(float(entity.normalized["change"]),
                                            ChangeUnit(entity.normalized["unit"])))
    return entity.normalized


def given_correct_spans(records: list[DatasetRecord], normalizer: EntityNormalizer) -> dict:
    right = defaultdict(Counter)   # scope -> entity type -> count
    total = defaultdict(Counter)
    methods = Counter()
    failures = []
    for record in records:
        for entity in record.entities:
            resolution = normalizer.normalize(entity.text, entity.type, record.text)
            correct = resolution.canonical == gold_canonical(entity)
            methods[resolution.method] += 1
            for scope in ("all", record.language.value):
                total[scope][entity.type.value] += 1
                right[scope][entity.type.value] += correct
            if not correct:
                failures.append({"text": entity.text, "query": record.text,
                                 "expected": gold_canonical(entity),
                                 "got": resolution.canonical})
    return {
        "accuracy": {
            scope: {
                **{t: right[scope][t] / total[scope][t] for t in sorted(total[scope])},
                "ALL": sum(right[scope].values()) / sum(total[scope].values()),
                "n": sum(total[scope].values()),
            }
            for scope in SCOPES
        },
        "methods": dict(methods),
        "failures": failures,
    }


def make_typo(word: str, rng: random.Random) -> str:
    """One random edit: delete, duplicate or swap neighbouring characters."""
    i = rng.randrange(len(word) - 1)
    edit = rng.choice(("delete", "duplicate", "swap"))
    if edit == "delete":
        return word[:i] + word[i + 1:]
    if edit == "duplicate":
        return word[:i] + word[i] + word[i:]
    return word[:i] + word[i + 1] + word[i] + word[i + 2:]


def fuzzy_sweep(ontology, settings, seed: int) -> list[dict]:
    """Recall on misspelled place names versus false matches on unrelated words."""
    rng = random.Random(seed)
    typos = []
    for loc_id, entry in ontology.locations.items():
        for alias in entry.aliases.all():
            if len(alias) >= 5:
                for _ in range(3):
                    typo = make_typo(alias, rng)
                    if ontology.lookup_location(typo) is None:  # still a real error
                        typos.append((typo, loc_id))

    # Words that are not places and must not be matched to one.
    lexicon = load_lexicon()
    negatives = [word for pool in lexicon["ood"].values() for words in pool.values()
                 for word in words]
    negatives += [alias for entry in [*ontology.variables.values(), *ontology.disasters.values()]
                  for alias in entry.aliases.all()]
    negatives += ["Siliguri", "Darjeeling", "Kathmandu", "Delhi", "Kolkata", "Guwahati",
                  "सिलीगुड़ी", "दार्जिलिंग", "काठमांडू", "दिल्ली", "सिलिगुडी", "काठमाडौँ"]
    # Real places elsewhere whose names resemble Sikkim place names. These are
    # the dangerous cases: a loose threshold silently turns them into the
    # wrong place.
    negatives += ["Namche", "Manang", "Mangalore", "Rangpur", "Gangotri", "Gangapur",
                  "Pakur", "Sitamarhi", "Lachin", "Singrauli",
                  "नाम्चे", "मनाङ", "रंगपुर", "गंगोत्री", "गंगापुर"]

    rows = []
    for threshold in (0.70, 0.75, 0.80, 0.85, 0.90, 0.95):
        config = settings.normalization.model_copy(update={"fuzzy_threshold": threshold})
        normalizer = EntityNormalizer(ontology, config)
        recovered = wrong = 0
        for typo, loc_id in typos:
            canonical = normalizer.normalize(typo, EntityType.LOCATION).canonical
            recovered += canonical == loc_id
            wrong += canonical not in (None, loc_id)
        false_matches = [word for word in negatives
                         if normalizer.normalize(word, EntityType.LOCATION).resolved]
        rows.append({
            "threshold": threshold,
            "typo_recall": recovered / len(typos),
            "typo_wrong_place": wrong / len(typos),
            "false_match_rate": len(false_matches) / len(negatives),
            "false_matches": false_matches,
            "n_typos": len(typos), "n_negatives": len(negatives),
        })
    return rows


def given_predicted_spans(records, normalizer, settings) -> dict | None:
    """Value-level scores: a gold (type, value) pair counts as found if the
    NER model plus the normaliser produce the same pair for that query,
    whatever the exact character boundaries were."""
    try:
        from backend.nlp.ner.predictor import EntityRecognizer, NerModelNotFound
    except ImportError:
        return None
    try:
        recognizer = EntityRecognizer.from_settings(settings)
    except NerModelNotFound:
        return None

    predictions = recognizer.predict([r.text for r in records])
    counts = {scope: Counter() for scope in SCOPES}
    for record, entities in zip(records, predictions):
        gold = Counter((e.type.value, gold_canonical(e)) for e in record.entities)
        found = Counter()
        unresolved = 0
        for entity in entities:
            resolution = normalizer.normalize(entity.text, entity.type, record.text)
            if resolution.resolved:
                found[(resolution.type.value, resolution.canonical)] += 1
            else:
                unresolved += 1
        correct = sum((gold & found).values())
        for scope in ("all", record.language.value):
            counts[scope].update(correct=correct, gold=sum(gold.values()),
                                 predicted=sum(found.values()), unresolved=unresolved,
                                 texts=1, exact_texts=int(gold == found))
    report = {}
    for scope, c in counts.items():
        precision = c["correct"] / c["predicted"] if c["predicted"] else 0.0
        recall = c["correct"] / c["gold"] if c["gold"] else 0.0
        report[scope] = {
            "precision": precision, "recall": recall,
            "f1": 2 * precision * recall / (precision + recall) if precision + recall else 0.0,
            "unresolved_spans": c["unresolved"],
            "text_exact_match": c["exact_texts"] / c["texts"],
        }
    return report


def main() -> int:
    setup_logging("WARNING")
    sys.stdout.reconfigure(encoding="utf-8")
    settings = load_settings()
    ontology = get_ontology()
    normalizer = EntityNormalizer(ontology, settings.normalization)
    data_dir = settings.paths.data_dir
    val = read_jsonl(data_dir / "val.jsonl")
    test = read_jsonl(data_dir / "test" / "test.jsonl")

    results = {}

    print("1. Canonical value given the correct span (validation + test)")
    correct = given_correct_spans([*val, *test], normalizer)
    results["given_correct_spans"] = correct
    types = [t.value for t in EntityType]
    print(f"   {'scope':<6}" + "".join(f"{t:>14}" for t in types) + f"{'ALL':>8}{'n':>7}")
    for scope in SCOPES:
        row = correct["accuracy"][scope]
        print(f"   {scope:<6}" + "".join(f"{row[t]:>14.3f}" for t in types)
              + f"{row['ALL']:>8.3f}{row['n']:>7}")
    print(f"   resolved by: {correct['methods']}")
    for failure in correct["failures"][:10]:
        print(f"   FAIL '{failure['text']}' expected {failure['expected']} got {failure['got']}"
              f"   in: {failure['query']}")

    print("\n2. Fuzzy threshold sweep (synthetic one-character typos in place names)")
    sweep = fuzzy_sweep(ontology, settings, settings.project.seed)
    results["fuzzy_sweep"] = sweep
    print(f"   {sweep[0]['n_typos']} typos, {sweep[0]['n_negatives']} unrelated words")
    print(f"   {'threshold':>9}{'typo recall':>13}{'wrong place':>13}{'false match':>13}")
    for row in sweep:
        print(f"   {row['threshold']:>9.2f}{row['typo_recall']:>13.3f}"
              f"{row['typo_wrong_place']:>13.3f}{row['false_match_rate']:>13.3f}"
              + (f"   e.g. {row['false_matches'][:4]}" if row["false_matches"] else ""))
    print(f"   configured threshold: {settings.normalization.fuzzy_threshold}")

    print("\n3. Values recovered from NER-predicted spans (test split)")
    predicted = given_predicted_spans(test, normalizer, settings)
    results["given_predicted_spans"] = predicted
    if predicted is None:
        print("   skipped: no trained NER model. Run scripts/train_ner.py first.")
    else:
        print(f"   {'scope':<6}{'precision':>10}{'recall':>8}{'f1':>8}{'unresolved':>12}"
              f"{'all right':>11}")
        for scope in SCOPES:
            row = predicted[scope]
            print(f"   {scope:<6}{row['precision']:>10.3f}{row['recall']:>8.3f}{row['f1']:>8.3f}"
                  f"{row['unresolved_spans']:>12}{row['text_exact_match']:>11.1%}")

    out_dir = settings.paths.models_dir / "normalization"
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "metrics.json").write_text(
        json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(f"\nmetrics saved to {out_dir / 'metrics.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
