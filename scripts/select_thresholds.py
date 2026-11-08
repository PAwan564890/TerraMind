"""Calibrate the intent classifier and choose the decision thresholds.

Run from the project root, after training the intent and NER models:
    python scripts/select_thresholds.py

Everything is chosen on VALIDATION data and then reported once on the test
and gold sets. The result is saved to models/decision/thresholds.json, which
the pipeline loads. Re-run this whenever the intent model changes.
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np  # noqa: E402

from backend.core import load_settings, setup_logging  # noqa: E402
from backend.nlp.dataset.records import load_gold, read_jsonl  # noqa: E402
from backend.nlp.embeddings.encoder import EmbeddingModel  # noqa: E402
from backend.nlp.embeddings.index import NeighbourIndex  # noqa: E402
from backend.nlp.evaluation.retrieval import separation_metrics  # noqa: E402
from backend.nlp.intent.calibration import (  # noqa: E402
    add_clustered_bound,
    apply_temperature,
    calibration_report,
    coverage_curve,
    fit_temperature,
    select_threshold,
)
from backend.nlp.intent.model import LABEL2ID, LABELS  # noqa: E402
from backend.nlp.intent.predictor import IntentClassifier, resolve_model_dir  # noqa: E402
from backend.nlp.ontology import get_ontology  # noqa: E402
from backend.nlp.ner.predictor import EntityRecognizer  # noqa: E402
from backend.nlp.pipeline.decision import (  # noqa: E402
    DecisionThresholds,
    DomainScorer,
    without_spans,
)
from backend.nlp.query.enums import EntityType, Intent, Language  # noqa: E402

OOD_ID = LABEL2ID[Intent.OUT_OF_DOMAIN.value]
SCOPES = ("all", "en", "hi", "ne")


def scope_masks(languages: list[str]) -> dict[str, np.ndarray]:
    masks = {"all": np.ones(len(languages), dtype=bool)}
    for language in Language:
        masks[language.value] = np.array([code == language.value for code in languages])
    return masks


def ood_report(labels, predicted, confidence, similarity, thresholds) -> dict:
    """Out-of-domain detection three ways: classifier alone, similarity alone,
    and the combination the pipeline uses."""
    truly_out = labels == OOD_ID
    by_classifier = predicted == OOD_ID
    by_similarity = similarity < thresholds.min_domain_similarity
    confident = confidence >= thresholds.min_intent_confidence
    looks_in_domain = similarity >= thresholds.in_domain_similarity
    combined = by_similarity | (by_classifier & confident & ~looks_in_domain)
    # Queries answered with a question instead of a result or a rejection:
    # unsure intent, or the two off-topic signals disagreeing.
    asked = ~combined & (~confident | (by_classifier & looks_in_domain))

    def rates(decision):
        return {
            "ood_detected": float(decision[truly_out].mean()) if truly_out.any() else None,
            "in_domain_rejected": float(decision[~truly_out].mean()) if (~truly_out).any() else None,
        }

    return {
        "n_ood": int(truly_out.sum()), "n_in_domain": int((~truly_out).sum()),
        "classifier": rates(by_classifier), "similarity": rates(by_similarity),
        "combined": rates(combined),
        "in_domain_asked_to_clarify": float(asked[~truly_out].mean()) if (~truly_out).any() else None,
        "ood_asked_to_clarify": float(asked[truly_out].mean()) if truly_out.any() else None,
    }


def main() -> int:
    setup_logging("WARNING")
    sys.stdout.reconfigure(encoding="utf-8")
    settings = load_settings()
    config = settings.decision
    data_dir = settings.paths.data_dir

    val = read_jsonl(data_dir / "val.jsonl")
    test = read_jsonl(data_dir / "test" / "test.jsonl")
    gold = load_gold(data_dir / "test" / "gold.yaml", get_ontology())
    sets = {
        "validation": ([r.text for r in val], [r.language.value for r in val],
                       [r.intent.value for r in val]),
        "test": ([r.text for r in test], [r.language.value for r in test],
                 [r.intent.value for r in test]),
        "gold": ([g.text for g in gold], [g.language.value for g in gold],
                 [g.expected.intent.value for g in gold]),
    }

    classifier = IntentClassifier.from_settings(settings)
    embedder = EmbeddingModel.from_config(settings.embeddings)
    recognizer = EntityRecognizer.from_settings(settings)

    # Index of in-domain training queries with place names removed (from the
    # labels). At run time, and below, the places come from the NER model.
    train = read_jsonl(data_dir / "train.jsonl")
    index = NeighbourIndex.build(embedder, train, texts=[
        without_spans(r.text, [(e.start, e.end) for e in r.entities
                               if e.type is EntityType.LOCATION])
        for r in train
    ])
    index.save(DomainScorer.index_path(settings))
    scorer = DomainScorer(embedder, index, settings.embeddings.neighbours)

    raw, labels, languages, similarity = {}, {}, {}, {}
    for name, (texts, codes, intents) in sets.items():
        raw[name] = classifier.probabilities(texts)
        labels[name] = np.array([LABEL2ID[intent] for intent in intents])
        languages[name] = codes
        places = [[(e.start, e.end) for e in found if e.type is EntityType.LOCATION]
                  for found in recognizer.predict(texts)]
        similarity[name] = np.array(scorer.score_many(texts, places))

    # ---- 1. Calibration ---------------------------------------------------------
    temperature = fit_temperature(raw["validation"], labels["validation"])
    cal = {name: apply_temperature(raw[name], temperature) for name in sets}
    print(f"1. Calibration: temperature = {temperature:.3f} (fitted on validation)")
    print(f"   {'set':<12}{'accuracy':>9}{'mean conf before':>18}{'ECE before':>12}"
          f"{'mean conf after':>17}{'ECE after':>11}")
    calibration = {}
    for name in sets:
        before = calibration_report(raw[name], labels[name])
        after = calibration_report(cal[name], labels[name])
        calibration[name] = {"before": before, "after": after}
        print(f"   {name:<12}{before['accuracy']:>9.3f}{before['mean_confidence']:>18.3f}"
              f"{before['ece']:>12.3f}{after['mean_confidence']:>17.3f}{after['ece']:>11.3f}")
    print("   reliability on test after calibration (confidence range: accuracy, n)")
    for row in calibration["test"]["after"]["bins"]:
        print(f"     {row['range']}: accuracy {row['accuracy']:.2f} "
              f"at mean confidence {row['mean_confidence']:.2f}  (n={row['n']})")

    confidence = {name: cal[name].max(axis=1) for name in sets}
    predicted = {name: cal[name].argmax(axis=1) for name in sets}
    correct = {name: predicted[name] == labels[name] for name in sets}

    # ---- 2. Confidence threshold ---------------------------------------------------
    grid = np.round(np.arange(0.30, 0.991, 0.01), 2)
    curve = coverage_curve(confidence["validation"], correct["validation"], grid)
    curve = add_clustered_bound(
        curve, confidence["validation"], correct["validation"], [r.group_id for r in val],
        config.error_bound_quantile, config.bootstrap_resamples, settings.project.seed,
    )
    families = len({r.group_id for r in val})
    chosen = select_threshold(curve, config.target_answered_error, key="answered_error_upper")
    naive = select_threshold(curve, config.target_answered_error)
    min_confidence = chosen["threshold"]
    print(f"\n2. Confidence threshold (target: at most {config.target_answered_error:.0%} wrong "
          f"among answered; applied to the {config.error_bound_quantile:.0%} upper bound over "
          f"{families} validation families)")
    print(f"   {'threshold':>9}{'answered':>10}{'wrong among answered':>22}{'upper bound':>13}")
    for row in curve[::10]:
        print(f"   {row['threshold']:>9.2f}{row['coverage']:>10.3f}{row['answered_error']:>22.3f}"
              f"{row['answered_error_upper']:>13.3f}")
    met = chosen["answered_error_upper"] <= config.target_answered_error
    print(f"   chosen: {min_confidence:.2f}" + ("" if met else
          "  (target NOT reachable even at the bound; this is the lowest bound available)"))
    print(f"   for comparison, the rule on the plain error rate would choose "
          f"{naive['threshold']:.2f}")
    operating = {}
    print(f"   {'set':<12}{'scope':<6}{'answered':>10}{'wrong among answered':>22}")
    for name in sets:
        operating[name] = {}
        for scope, mask in scope_masks(languages[name]).items():
            answered = (confidence[name] >= min_confidence) & mask
            point = {
                "coverage": float(answered.sum() / mask.sum()),
                "answered_error": float(1 - correct[name][answered].mean()) if answered.any() else 0.0,
                "n": int(mask.sum()),
            }
            operating[name][scope] = point
            print(f"   {name:<12}{scope:<6}{point['coverage']:>10.3f}{point['answered_error']:>22.3f}")

    # ---- 3. Similarity threshold ------------------------------------------------------
    in_domain_val = similarity["validation"][labels["validation"] != OOD_ID]
    min_similarity = float(np.percentile(in_domain_val, 100 * config.in_domain_rejection_target))
    off_topic_val = similarity["validation"][labels["validation"] == OOD_ID]
    in_domain_similarity = float(np.percentile(off_topic_val, 100 * (1 - config.ood_veto_target)))
    thresholds = DecisionThresholds(temperature=temperature,
                                    min_intent_confidence=min_confidence,
                                    min_domain_similarity=min_similarity,
                                    in_domain_similarity=in_domain_similarity)
    print(f"\n3. Domain-similarity thresholds (from validation)")
    print(f"   below {min_similarity:.3f}: off-topic "
          f"({config.in_domain_rejection_target:.0%} of real queries fall below it)")
    print(f"   at or above {in_domain_similarity:.3f}: firmly in-domain "
          f"({config.ood_veto_target:.0%} of off-topic queries reach it); a classifier "
          f"'off-topic' verdict there becomes a question")

    # ---- 4. Out-of-domain decision -----------------------------------------------------
    print("\n4. Out-of-domain detection (share of off-topic queries caught / "
          "share of real queries wrongly rejected)")
    print(f"   {'set':<12}{'scope':<6}{'n ood':>6}{'classifier':>16}{'similarity':>16}"
          f"{'combined':>16}{'real asked':>12}")
    ood = {}
    for name in sets:
        ood[name] = {}
        for scope, mask in scope_masks(languages[name]).items():
            report = ood_report(labels[name][mask], predicted[name][mask],
                                confidence[name][mask], similarity[name][mask], thresholds)
            ood[name][scope] = report

            def cell(key):
                caught, rejected = report[key]["ood_detected"], report[key]["in_domain_rejected"]
                return f"{caught:>8.2f} /{rejected:>5.2f}" if caught is not None else f"{'-':>15}"

            print(f"   {name:<12}{scope:<6}{report['n_ood']:>6}{cell('classifier'):>16}"
                  f"{cell('similarity'):>16}{cell('combined'):>16}"
                  f"{report['in_domain_asked_to_clarify']:>12.2f}")

    inside = similarity["test"][labels["test"] != OOD_ID]
    outside = similarity["test"][labels["test"] == OOD_ID]
    separation = separation_metrics(inside, outside)
    print(f"   similarity alone on test: AUROC {separation['auroc']:.3f}, "
          f"FPR at 95% TPR {separation['fpr_at_95_tpr']:.3f}")

    out_path = DecisionThresholds.path(settings)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps({
        **thresholds.model_dump(),
        "selected_on": "validation",
        "intent_model_dir": str(resolve_model_dir(settings).relative_to(settings.paths.models_dir)),
        "embedding_model": settings.embeddings.model_name,
        "targets": config.model_dump(),
        "labels": LABELS,
        "calibration": calibration, "coverage_curve_validation": curve,
        "operating_point": operating, "out_of_domain": ood,
        "similarity_separation_test": separation,
    }, indent=2), encoding="utf-8")
    print(f"\nthresholds saved to {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
