"""Generate, validate and write the query dataset.

Run from the project root:
    python scripts/generate_dataset.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.core import load_settings, setup_logging  # noqa: E402
from backend.nlp.dataset.generator import generate  # noqa: E402
from backend.nlp.dataset.records import load_gold, write_jsonl  # noqa: E402
from backend.nlp.dataset.validate import summarize, validate_records  # noqa: E402
from backend.nlp.ontology import get_ontology  # noqa: E402


def main() -> int:
    setup_logging()
    # Devanagari in warnings must print on a Windows console too.
    sys.stdout.reconfigure(encoding="utf-8")

    settings = load_settings()
    ontology = get_ontology()
    data_dir = settings.paths.data_dir

    records = generate(ontology, settings.dataset, settings.project.seed)
    report = validate_records(records, ontology)

    print(summarize(records))
    print(f"\nwarnings: {len(report.warnings)}")
    for warning in report.warnings:
        print("  " + warning)

    if report.errors:
        print(f"\nERRORS: {len(report.errors)} (nothing written)")
        for error in report.errors:
            print("  " + error)
        return 1

    outputs = {
        "train": data_dir / "train.jsonl",
        "val": data_dir / "val.jsonl",
        "test": data_dir / "test" / "test.jsonl",
    }
    for split, path in outputs.items():
        write_jsonl(path, [r for r in records if r.split == split])
        print(f"wrote {path.relative_to(Path.cwd()) if path.is_relative_to(Path.cwd()) else path}")

    gold = load_gold(data_dir / "test" / "gold.yaml", ontology)
    print(f"gold test set: {len(gold)} hand-written queries (valid)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
