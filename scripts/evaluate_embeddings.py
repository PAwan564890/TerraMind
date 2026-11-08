"""Compare embedding models and build the neighbour index.

Run from the project root:
    python scripts/evaluate_embeddings.py

For every candidate model in the config it measures:
  1. Cross-language retrieval (same meaning in another language).
  2. Out-of-domain separation by similarity to in-domain training queries.
  3. Nearest-neighbour intent accuracy (a cross-check on the classifier).
  4. Synonym matching for the normalisation fallback, across thresholds.
Then it saves the neighbour index for the model named in the config.
"""

import json
import sys
from itertools import permutations
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np  # noqa: E402
import yaml  # noqa: E402

from backend.core import load_settings, setup_logging  # noqa: E402
from backend.nlp.dataset.generator import build_pools, load_lexicon  # noqa: E402
from backend.nlp.dataset.records import load_gold, read_jsonl  # noqa: E402
from backend.nlp.embeddings.alias_matcher import AliasMatcher  # noqa: E402
from backend.nlp.embeddings.encoder import EmbeddingModel  # noqa: E402
from backend.nlp.embeddings.index import NeighbourIndex  # noqa: E402
from backend.nlp.embeddings.parallel import make_parallel_set  # noqa: E402
from backend.nlp.evaluation.retrieval import retrieval_metrics, separation_metrics  # noqa: E402
from backend.nlp.ontology import get_ontology  # noqa: E402
from backend.nlp.query.enums import Intent, Language  # noqa: E402

OOD = Intent.OUT_OF_DOMAIN.value
SCOPES = ("all", "en", "hi", "ne")
THRESHOLDS = (0.80, 0.84, 0.86, 0.88, 0.90, 0.92, 0.94)


def retrieval(model, triples, distractors) -> dict:
    """Six language directions. Candidates are the other-language versions of
    all triples, plus optional distractor queries in that language."""
    vectors = {lang: model.encode([t[lang] for t in triples]) for lang in Language}
    extra = {lang: model.encode(texts) for lang, texts in distractors.items()} if distractors else {}
    results = {}
    for source, target in permutations(Language, 2):
        candidates = vectors[target]
        if extra:
            candidates = np.concatenate([candidates, extra[target]])
        results[f"{source.value}->{target.value}"] = retrieval_metrics(
            vectors[source] @ candidates.T, list(range(len(triples)))
        )
    results["mean"] = {
        key: float(np.mean([r[key] for r in results.values()]))
        for key in ("recall_at_1", "recall_at_5", "mrr")
    }
    return results


def by_scope(items):
    """items: list of (language code, ...) tuples -> index lists per scope."""
    groups = {"all": list(range(len(items)))}
    for language in Language:
        groups[language.value] = [i for i, item in enumerate(items) if item[0] == language.value]
    return groups


def domain_and_knn(model, index, items, k) -> dict:
    """items: list of (language code, text, intent)."""
    vectors = model.encode([text for _, text, _ in items])
    scores = index.domain_similarity(vectors, k)
    predicted = index.knn_intent(vectors, k)
    truth = [intent for _, _, intent in items]
    report = {}
    for scope, chosen in by_scope(items).items():
        inside = np.array([scores[i] for i in chosen if truth[i] != OOD])
        outside = np.array([scores[i] for i in chosen if truth[i] == OOD])
        report[scope] = {
            "ood": separation_metrics(inside, outside) if len(inside) and len(outside) else None,
            "knn_intent_accuracy": float(np.mean([predicted[i] == truth[i] for i in chosen])),
        }
    return report


def synonym_sweep(model, ontology, synonyms, margin) -> list[dict]:
    matcher = AliasMatcher(model, ontology, threshold=0.0, margin=0.0)
    positives = [(text, expected, matcher.scores(text)) for text, _, expected in synonyms["positives"]]
    negatives = [(text, matcher.scores(text)) for text, _ in synonyms["negatives"]]

    def accepted(ranked, threshold):
        return ranked[0][1] >= threshold and ranked[0][1] - ranked[1][1] >= margin

    rows = []
    for threshold in THRESHOLDS:
        right = sum(accepted(r, threshold) and r[0][0] == e for _, e, r in positives)
        wrong = sum(accepted(r, threshold) and r[0][0] != e for _, e, r in positives)
        false = [text for text, r in negatives if accepted(r, threshold)]
        rows.append({
            "threshold": threshold,
            "synonyms_right": right / len(positives),
            "synonyms_wrong": wrong / len(positives),
            "negatives_matched": len(false) / len(negatives),
            "negatives_matched_examples": false[:5],
        })
    top1 = sum(r[0][0] == e for _, e, r in positives) / len(positives)
    return {"top1_ignoring_threshold": top1, "n_positives": len(positives),
            "n_negatives": len(negatives), "sweep": rows}


def main() -> int:
    setup_logging("WARNING")
    sys.stdout.reconfigure(encoding="utf-8")
    settings = load_settings()
    config = settings.embeddings
    ontology = get_ontology()
    data_dir = settings.paths.data_dir

    train = read_jsonl(data_dir / "train.jsonl")
    val = read_jsonl(data_dir / "val.jsonl")
    test = read_jsonl(data_dir / "test" / "test.jsonl")
    gold = load_gold(data_dir / "test" / "gold.yaml", ontology)
    synonyms = yaml.safe_load((data_dir / "test" / "synonyms.yaml").read_text(encoding="utf-8"))

    triples = make_parallel_set(
        build_pools(ontology, load_lexicon()), config.parallel_triples, settings.project.seed
    )
    # Gold items are hand-written parallel triples: three consecutive records.
    gold_triples = [
        {g.language: g.text for g in gold[i:i + 3]} for i in range(0, len(gold), 3)
    ]
    test_by_language = {
        lang: [r.text for r in test if r.language is lang] for lang in Language
    }
    eval_sets = {
        "validation": [(r.language.value, r.text, r.intent.value) for r in val],
        "test": [(r.language.value, r.text, r.intent.value) for r in test],
        "gold": [(g.language.value, g.text, g.expected.intent.value) for g in gold],
    }

    print(f"{len(triples)} generated triples, {len(gold_triples)} hand-written triples")
    print("example triple:")
    for language in Language:
        print(f"  [{language.value}] {triples[0][language]}")

    results = {}
    for candidate in config.candidates:
        print(f"\n===== {candidate.name} =====")
        try:
            model = EmbeddingModel.load(candidate.name, candidate.prefix, config)
        except OSError as error:
            print(f"  could not load (not downloaded?): {str(error)[:120]}")
            continue

        generated = retrieval(model, triples, None)
        handwritten = retrieval(model, gold_triples, test_by_language)
        index = NeighbourIndex.build(model, train)
        sets = {name: domain_and_knn(model, index, items, config.neighbours)
                for name, items in eval_sets.items()}
        sweep = synonym_sweep(model, ontology, synonyms, config.alias_margin)
        results[candidate.name] = {
            "retrieval_generated": generated, "retrieval_handwritten": handwritten,
            "sets": sets, "synonyms": sweep,
        }

        print("1. Cross-language retrieval")
        for title, report, pool in (
            (f"generated triples, pool of {len(triples)}", generated, None),
            (f"hand-written triples, pool of {len(gold_triples)} + 216 distractors",
             handwritten, None),
        ):
            print(f"   {title}")
            print(f"   {'direction':<10}{'R@1':>7}{'R@5':>7}{'MRR':>7}")
            for direction, m in report.items():
                print(f"   {direction:<10}{m['recall_at_1']:>7.3f}{m['recall_at_5']:>7.3f}"
                      f"{m['mrr']:>7.3f}")

        print("2. Out-of-domain separation by domain similarity, and 3. kNN intent accuracy")
        print(f"   {'set':<12}{'scope':<6}{'AUROC':>7}{'FPR@95':>8}{'kNN acc':>9}")
        for name, report in sets.items():
            for scope in SCOPES:
                ood = report[scope]["ood"]
                auroc = f"{ood['auroc']:.3f}" if ood else "-"
                fpr = f"{ood['fpr_at_95_tpr']:.3f}" if ood else "-"
                print(f"   {name:<12}{scope:<6}{auroc:>7}{fpr:>8}"
                      f"{report[scope]['knn_intent_accuracy']:>9.3f}")

        print(f"4. Synonym fallback ({sweep['n_positives']} synonyms, "
              f"{sweep['n_negatives']} unrelated words); "
              f"nearest concept is right for {sweep['top1_ignoring_threshold']:.1%}")
        print(f"   {'threshold':>9}{'right':>8}{'wrong':>8}{'unrelated matched':>19}")
        for row in sweep["sweep"]:
            print(f"   {row['threshold']:>9.2f}{row['synonyms_right']:>8.3f}"
                  f"{row['synonyms_wrong']:>8.3f}{row['negatives_matched']:>19.3f}"
                  f"   {row['negatives_matched_examples'] or ''}")

        if candidate.name == config.model_name:
            index_path = settings.paths.models_dir / "embeddings" / "index.npz"
            index.save(index_path)
            print(f"   neighbour index saved to {index_path}")

    out_dir = settings.paths.models_dir / "embeddings"
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "metrics.json").write_text(
        json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(f"\nmetrics saved to {out_dir / 'metrics.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
