"""Fine-tune and evaluate the intent classifier.

Run from the project root:
    python scripts/train_intent.py                 # small model, CPU-friendly
    python scripts/train_intent.py --model full    # xlm-roberta-base, needs a GPU
    python scripts/train_intent.py --seeds 42      # a single seed

Results go to models/intent/<dev|full>/: one folder per seed with the best
checkpoint and metrics.json, plus summary.json across seeds.
"""

import argparse
import json
import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np  # noqa: E402
import torch  # noqa: E402
import transformers  # noqa: E402

from backend.core import load_settings, setup_logging  # noqa: E402
from backend.core.keep_awake import keep_awake  # noqa: E402
from backend.core.seed import set_seed  # noqa: E402
from backend.nlp.dataset.records import load_gold, read_jsonl  # noqa: E402
from backend.nlp.evaluation.classification import classification_report, format_report  # noqa: E402
from backend.nlp.intent.model import LABELS, pick_device, predict_probabilities  # noqa: E402
from backend.nlp.intent.train import load_finetuned, load_pretrained, train_intent_model  # noqa: E402
from backend.nlp.ontology import get_ontology  # noqa: E402
from backend.nlp.query.enums import Language  # noqa: E402


def evaluate_set(model, tokenizer, items, config, device) -> dict:
    """Report for all languages together and for each language separately.
    `items` is a list of (text, language code, true intent)."""
    texts = [text for text, _, _ in items]
    probabilities = predict_probabilities(
        model, tokenizer, texts, config.max_length, config.batch_size * 4, device
    )
    predicted = [LABELS[i] for i in probabilities.argmax(axis=1)]
    truth = [intent for _, _, intent in items]

    reports = {"all": classification_report(truth, predicted, LABELS)}
    for language in Language:
        chosen = [i for i, (_, code, _) in enumerate(items) if code == language.value]
        reports[language.value] = classification_report(
            [truth[i] for i in chosen], [predicted[i] for i in chosen], LABELS
        )
    reports["errors"] = [
        {"text": texts[i], "language": items[i][1], "true": truth[i], "predicted": predicted[i],
         "confidence": float(probabilities[i].max())}
        for i in range(len(items)) if predicted[i] != truth[i]
    ]
    return reports


def mean_std(values: list[float]) -> dict:
    return {
        "mean": statistics.fmean(values),
        "std": statistics.stdev(values) if len(values) > 1 else 0.0,
        "values": values,
    }


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
    config = settings.intent
    if args.max_epochs:
        config = config.model_copy(update={"max_epochs": args.max_epochs})
    seeds = args.seeds or config.seeds
    model_name = config.model_name if args.model == "full" else config.dev_model_name
    device = pick_device()
    run_dir = settings.paths.models_dir / "intent" / args.model

    print(f"model: {model_name}   device: {device}   seeds: {seeds}")
    if args.model == "full" and device.type == "cpu":
        print("WARNING: training xlm-roberta-base on a CPU is very slow. Use a GPU or --model dev.")

    data_dir = settings.paths.data_dir
    train = read_jsonl(data_dir / "train.jsonl")
    val = read_jsonl(data_dir / "val.jsonl")
    test = read_jsonl(data_dir / "test" / "test.jsonl")
    gold = load_gold(data_dir / "test" / "gold.yaml", get_ontology())

    eval_sets = {
        "validation": [(r.text, r.language.value, r.intent.value) for r in val],
        "test": [(r.text, r.language.value, r.intent.value) for r in test],
        "gold": [(g.text, g.language.value, g.expected.intent.value) for g in gold],
    }

    per_seed = {}
    for seed in seeds:
        set_seed(seed)  # the new classification head is initialised randomly
        tokenizer, model = load_pretrained(model_name)
        if seed == seeds[0]:
            # Check that max_length does not cut real queries short.
            lengths = [len(ids) for ids in tokenizer([r.text for r in train])["input_ids"]]
            print(f"token lengths in train: median {int(np.median(lengths))}, "
                  f"99th percentile {int(np.percentile(lengths, 99))}, max {max(lengths)} "
                  f"(max_length = {config.max_length})")

        seed_dir = run_dir / f"seed_{seed}"
        result = train_intent_model(train, val, tokenizer, model, config, seed, seed_dir, device)

        # Evaluate the SAVED best checkpoint, not the last epoch in memory.
        tokenizer, model = load_finetuned(seed_dir)
        model.to(device)
        metrics = {
            name: evaluate_set(model, tokenizer, items, config, device)
            for name, items in eval_sets.items()
        }
        metrics["training"] = {
            "model_name": model_name,
            "seed": seed,
            "device": str(device),
            "best_epoch": result.best_epoch,
            "best_val_macro_f1": result.best_score,
            "seconds": result.seconds,
            "history": result.history,
            "config": config.model_dump(),
            "versions": {"torch": torch.__version__, "transformers": transformers.__version__},
        }
        (seed_dir / "metrics.json").write_text(
            json.dumps(metrics, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        per_seed[seed] = metrics
        print(f"\nseed {seed}: best epoch {result.best_epoch}, "
              f"{result.seconds:.0f}s, val macro-F1 {result.best_score:.4f}")

    best_seed = max(seeds, key=lambda s: per_seed[s]["training"]["best_val_macro_f1"])
    summary = {"model_name": model_name, "seeds": seeds, "best_seed": best_seed}
    for name in eval_sets:
        summary[name] = {
            scope: {
                "accuracy": mean_std([per_seed[s][name][scope]["accuracy"] for s in seeds]),
                "macro_f1": mean_std([per_seed[s][name][scope]["macro_f1"] for s in seeds]),
            }
            for scope in ("all", "en", "hi", "ne")
        }
    (run_dir / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")

    print(f"\n=== Summary over {len(seeds)} seed(s): mean ± std ===")
    print(f"{'set':<12}{'scope':<7}{'accuracy':>16}{'macro-F1':>16}")
    for name in eval_sets:
        for scope in ("all", "en", "hi", "ne"):
            a, f = summary[name][scope]["accuracy"], summary[name][scope]["macro_f1"]
            print(f"{name:<12}{scope:<7}{a['mean']:>9.3f} ± {a['std']:.3f}"
                  f"{f['mean']:>9.3f} ± {f['std']:.3f}")

    best = per_seed[best_seed]
    print(f"\n=== Best seed ({best_seed}) on the test split ===")
    print(format_report("test, all languages", best["test"]["all"]))
    print(f"\ngold-set errors for seed {best_seed}:")
    for error in best["gold"]["errors"]:
        print(f"  [{error['language']}] {error['text']}\n"
              f"       true {error['true']}, predicted {error['predicted']} "
              f"({error['confidence']:.2f})")
    print(f"\nsaved to {run_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
