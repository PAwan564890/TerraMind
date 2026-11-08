"""Measure what a set of training template families contributes.

Trains the intent classifier with the named families REMOVED from the training
data, and reports accuracy and wrongly rejected real queries per language.
Compare with the normal run to see what those families bought.

Run from the project root:
    python scripts/ablate_families.py --tag no_general_fix --model full ^
        --exclude general.how_to_prepare general.how_it_happens ^
                  general.how_variable_matters general.precautions

Results go to models/intent/ablation_<tag>/. The pipeline never loads them.
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np  # noqa: E402

from backend.core import load_settings, setup_logging  # noqa: E402
from backend.core.keep_awake import keep_awake  # noqa: E402
from backend.core.seed import set_seed  # noqa: E402
from backend.nlp.dataset.records import read_jsonl  # noqa: E402
from backend.nlp.intent.model import LABELS, pick_device, predict_probabilities  # noqa: E402
from backend.nlp.intent.train import load_finetuned, load_pretrained, train_intent_model  # noqa: E402
from backend.nlp.query.enums import Intent, Language  # noqa: E402

OOD = Intent.OUT_OF_DOMAIN.value


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--tag", required=True)
    parser.add_argument("--exclude", nargs="*", default=[],
                        help="family ids to remove; none gives the reference run")
    parser.add_argument("--model", choices=["dev", "full"], default="dev")
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    setup_logging()
    sys.stdout.reconfigure(encoding="utf-8")
    keep_awake()
    settings = load_settings()
    config = settings.intent
    data_dir = settings.paths.data_dir
    model_name = config.model_name if args.model == "full" else config.dev_model_name
    device = pick_device()

    train = read_jsonl(data_dir / "train.jsonl")
    known = {r.group_id for r in train}
    missing = set(args.exclude) - known
    if missing:
        print(f"not training families: {sorted(missing)}")
        return 1
    kept = [r for r in train if r.group_id not in args.exclude]
    print(f"model {model_name} on {device}; training rows {len(train)} -> {len(kept)} "
          f"after removing {len(args.exclude)} families")

    out_dir = settings.paths.models_dir / "intent" / f"ablation_{args.tag}" / f"seed_{args.seed}"
    set_seed(args.seed)
    tokenizer, model = load_pretrained(model_name)
    val = read_jsonl(data_dir / "val.jsonl")
    result = train_intent_model(kept, val, tokenizer, model, config, args.seed, out_dir, device)
    tokenizer, model = load_finetuned(out_dir)
    model.to(device)

    report = {"excluded": args.exclude, "model_name": model_name, "seed": args.seed,
              "training_rows": len(kept), "best_epoch": result.best_epoch}
    print(f"{'set':<12}{'scope':<6}{'accuracy':>9}{'real rejected':>15}")
    for name, rows in (("validation", val), ("test", read_jsonl(data_dir / "test" / "test.jsonl"))):
        probabilities = predict_probabilities(
            model, tokenizer, [r.text for r in rows], config.max_length, 64, device)
        predicted = [LABELS[i] for i in probabilities.argmax(axis=1)]
        report[name] = {}
        for scope in ("all", *[language.value for language in Language]):
            chosen = [i for i, r in enumerate(rows) if scope in ("all", r.language.value)]
            real = [i for i in chosen if rows[i].intent.value != OOD]
            accuracy = float(np.mean([predicted[i] == rows[i].intent.value for i in chosen]))
            rejected = sum(predicted[i] == OOD for i in real)
            report[name][scope] = {"accuracy": accuracy, "real_rejected": rejected,
                                   "real": len(real)}
            print(f"{name:<12}{scope:<6}{accuracy:>9.3f}{rejected:>9} of {len(real)}")

    (out_dir / "ablation.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    # The weights are only needed for the numbers above.
    (out_dir / "model.safetensors").unlink(missing_ok=True)
    print(f"saved {out_dir / 'ablation.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
