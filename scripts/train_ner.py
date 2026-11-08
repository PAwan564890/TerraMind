"""Fine-tune and evaluate the NER model.

Run from the project root:
    python scripts/train_ner.py                 # small model, CPU-friendly
    python scripts/train_ner.py --model full    # xlm-roberta-base, needs a GPU
    python scripts/train_ner.py --seeds 42      # a single seed

Results go to models/ner/<dev|full>/: one folder per seed with the best
checkpoint and metrics.json, plus summary.json across seeds.
"""

import argparse
import json
import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import torch  # noqa: E402
import transformers  # noqa: E402

from backend.core import load_settings, setup_logging  # noqa: E402
from backend.core.keep_awake import keep_awake  # noqa: E402
from backend.core.seed import set_seed  # noqa: E402
from backend.nlp.dataset.generator import load_lexicon  # noqa: E402
from backend.nlp.dataset.records import read_jsonl  # noqa: E402
from backend.nlp.evaluation.ner import entity_report, format_entity_report  # noqa: E402
from backend.nlp.ner.model import align_tags, decode_tags, predict_entities  # noqa: E402
from backend.nlp.ner.train import (  # noqa: E402
    load_finetuned,
    load_pretrained,
    record_spans,
    train_ner_model,
)
from backend.nlp.query.enums import EntityType, Language  # noqa: E402
from backend.nlp.training.loop import pick_device  # noqa: E402

SCOPES = ("all", "en", "hi", "ne")


def by_language(records, values):
    """Split parallel lists into {'all': ..., 'en': ..., 'hi': ..., 'ne': ...}."""
    groups = {"all": list(range(len(records)))}
    for language in Language:
        groups[language.value] = [i for i, r in enumerate(records) if r.language is language]
    return {scope: [values[i] for i in chosen] for scope, chosen in groups.items()}


def alignment_ceiling(records, tokenizer, max_length: int) -> dict:
    """Best score any model could reach with this tokenizer.

    The gold spans are converted to token tags and straight back. A span that
    does not survive the round trip (because no token boundary falls where the
    entity ends) can never be predicted exactly.
    """
    encodings = tokenizer([r.text for r in records], truncation=True, max_length=max_length,
                          return_offsets_mapping=True)
    gold = [record_spans(r) for r in records]
    recovered = [
        [e.span for e in decode_tags(r.text, offsets, align_tags(offsets, spans))]
        for r, offsets, spans in zip(records, encodings["offset_mapping"], gold)
    ]
    gold_groups, recovered_groups = by_language(records, gold), by_language(records, recovered)
    return {scope: entity_report(gold_groups[scope], recovered_groups[scope]) for scope in SCOPES}


def evaluate_set(model, tokenizer, records, config, device, heldout: set[str]) -> dict:
    predicted = predict_entities(
        model, tokenizer, [r.text for r in records], config.max_length, config.batch_size * 4,
        device,
    )
    gold = [record_spans(r) for r in records]
    predicted_spans = [[e.span for e in row] for row in predicted]
    gold_groups = by_language(records, gold)
    predicted_groups = by_language(records, predicted_spans)
    reports = {s: entity_report(gold_groups[s], predicted_groups[s]) for s in SCOPES}

    # Recall on places the model never saw during training.
    found = total = 0
    for record, spans in zip(records, predicted_spans):
        for entity in record.entities:
            if entity.type is EntityType.LOCATION and entity.normalized in heldout:
                total += 1
                found += (entity.start, entity.end, entity.type.value) in spans
    reports["heldout_location_recall"] = {"found": found, "total": total,
                                          "recall": found / total if total else None}

    reports["errors"] = [
        {"text": r.text, "language": r.language.value,
         "missed": [r.text[s:e] + "=" + t for s, e, t in sorted(set(g) - set(p))],
         "wrong": [r.text[s:e] + "=" + t for s, e, t in sorted(set(p) - set(g))]}
        for r, g, p in zip(records, gold, predicted_spans) if set(g) != set(p)
    ]
    return reports


def mean_std(values: list[float]) -> dict:
    return {"mean": statistics.fmean(values),
            "std": statistics.stdev(values) if len(values) > 1 else 0.0, "values": values}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--model", choices=["dev", "full"], default="dev")
    parser.add_argument("--seeds", type=int, nargs="+", help="override the seeds in the config")
    parser.add_argument("--max-epochs", type=int, help="override max_epochs in the config")
    args = parser.parse_args()

    setup_logging()
    sys.stdout.reconfigure(encoding="utf-8")
    keep_awake()

    settings = load_settings()
    config = settings.ner
    if args.max_epochs:
        config = config.model_copy(update={"max_epochs": args.max_epochs})
    seeds = args.seeds or config.seeds
    model_name = config.model_name if args.model == "full" else config.dev_model_name
    device = pick_device()
    run_dir = settings.paths.models_dir / "ner" / args.model

    print(f"model: {model_name}   device: {device}   seeds: {seeds}")
    if args.model == "full" and device.type == "cpu":
        print("WARNING: training xlm-roberta-base on a CPU is very slow. Use a GPU or --model dev.")

    data_dir = settings.paths.data_dir
    train = read_jsonl(data_dir / "train.jsonl")
    eval_sets = {
        "validation": read_jsonl(data_dir / "val.jsonl"),
        "test": read_jsonl(data_dir / "test" / "test.jsonl"),
    }
    heldout = set(load_lexicon()["heldout_locations"])

    per_seed = {}
    ceiling = None
    for seed in seeds:
        set_seed(seed)  # the new tagging head is initialised randomly
        tokenizer, model = load_pretrained(model_name)
        if ceiling is None:
            ceiling = alignment_ceiling(eval_sets["test"], tokenizer, config.max_length)
            print("\ntokenizer ceiling on test (entity F1 if every tag were predicted perfectly):")
            print("  " + "   ".join(f"{s} {ceiling[s]['overall']['f1']:.3f}" for s in SCOPES))

        seed_dir = run_dir / f"seed_{seed}"
        result = train_ner_model(train, eval_sets["validation"], tokenizer, model, config, seed,
                                 seed_dir, device)

        # Evaluate the SAVED best checkpoint, not the last epoch in memory.
        tokenizer, model = load_finetuned(seed_dir)
        model.to(device)
        metrics = {name: evaluate_set(model, tokenizer, records, config, device, heldout)
                   for name, records in eval_sets.items()}
        metrics["tokenizer_ceiling_test"] = ceiling
        metrics["training"] = {
            "model_name": model_name, "seed": seed, "device": str(device),
            "best_epoch": result.best_epoch, "best_val_entity_f1": result.best_score,
            "seconds": result.seconds, "history": result.history,
            "config": config.model_dump(),
            "versions": {"torch": torch.__version__, "transformers": transformers.__version__},
        }
        (seed_dir / "metrics.json").write_text(
            json.dumps(metrics, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        per_seed[seed] = metrics
        print(f"\nseed {seed}: best epoch {result.best_epoch}, {result.seconds:.0f}s, "
              f"val entity F1 {result.best_score:.4f}")

    best_seed = max(seeds, key=lambda s: per_seed[s]["training"]["best_val_entity_f1"])
    summary = {"model_name": model_name, "seeds": seeds, "best_seed": best_seed}
    for name in eval_sets:
        summary[name] = {
            scope: {key: mean_std([per_seed[s][name][scope]["overall"][key] for s in seeds])
                    for key in ("precision", "recall", "f1")}
            for scope in SCOPES
        }
    (run_dir / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")

    print(f"\n=== Entity-level summary over {len(seeds)} seed(s): mean ± std ===")
    print(f"{'set':<12}{'scope':<7}{'precision':>16}{'recall':>16}{'f1':>16}")
    for name in eval_sets:
        for scope in SCOPES:
            cells = "".join(
                f"{summary[name][scope][k]['mean']:>9.3f} ± {summary[name][scope][k]['std']:.3f}"
                for k in ("precision", "recall", "f1")
            )
            print(f"{name:<12}{scope:<7}{cells}")

    best = per_seed[best_seed]["test"]
    print(f"\n=== Best seed ({best_seed}) on the test split ===")
    for scope in SCOPES:
        print(format_entity_report(f"test, {scope}", best[scope]) + "\n")
    held = best["heldout_location_recall"]
    print(f"held-out locations found exactly: {held['found']} of {held['total']}")
    print("\nfirst test errors:")
    for error in best["errors"][:12]:
        print(f"  [{error['language']}] {error['text']}\n"
              f"       missed {error['missed']}   wrong {error['wrong']}")
    print(f"\nsaved to {run_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
