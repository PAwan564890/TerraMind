"""End-to-end evaluation of the whole NLP pipeline.

Run from the project root:
    python scripts/evaluate_end_to_end.py --tag baseline
    python scripts/evaluate_end_to_end.py --tag after_fixes --compare baseline

Runs the real models over four sets and saves models/evaluation/<tag>.json:
  gold        hand-written, studied during development (a development set)
  gold_v2     hand-written; inspected once, so now also a development set
  realistic   real-user-style queries, never used to choose a fix or threshold
  test        generated from template families unseen in training
  dialogues   multi-turn conversations
"""

import argparse
import json
import statistics
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.core import load_settings, setup_logging  # noqa: E402
from backend.nlp.context.dialogues import load_dialogues  # noqa: E402
from backend.nlp.dataset.records import load_gold, load_realistic, read_jsonl  # noqa: E402
from backend.nlp.evaluation.end_to_end import (  # noqa: E402
    CATEGORIES,
    actual_fields,
    aggregate,
    categorize,
    compare,
    decision_summary,
    errors_by_category,
    expected_from_gold,
    expected_from_record,
)
from backend.nlp.ontology import get_ontology  # noqa: E402
from backend.nlp.pipeline import NlpPipeline  # noqa: E402
from backend.nlp.training.loop import pick_device  # noqa: E402

SCOPES = ("all", "en", "hi", "ne")
HEADLINE = ("exact", "status", "intent", "operation", "locations", "variables", "disasters",
            "time_period", "scenario", "scenario_amount", "target", "language")


def run_set(pipeline, items) -> list[dict]:
    """items: (text, language code, expected fields)."""
    rows = []
    for text, language, expected in items:
        response = pipeline.analyze(text)
        actual = actual_fields(response)
        fields = compare(expected, actual)
        rows.append({
            "text": text, "language": language, "fields": fields,
            "category": categorize(expected, response, fields),
            "expected": {k: sorted(v) if isinstance(v, frozenset) else v
                         for k, v in expected.items()},
            "actual": {k: sorted(v) if isinstance(v, frozenset) else v
                       for k, v in actual.items()},
            "confidence": response.intent.confidence,
            "warnings": response.warnings,
            "clarification": response.clarification.reason if response.clarification else None,
        })
    return rows


def run_dialogues(pipeline, dialogues) -> dict:
    turns = turns_right = dialogues_right = 0
    failures = []
    for dialogue in dialogues:
        all_right = True
        for number, turn in enumerate(dialogue.turns, start=1):
            response = pipeline.analyze(turn.text, session_id=dialogue.id, now=float(number))
            actual = actual_fields(response)
            query = response.structured_query
            actual["context_used"] = sorted(query.context_used) if query else []
            problems = []
            for name, expected in turn.expect.items():
                got = actual[name]
                if name in ("locations", "variables", "disasters"):
                    expected, got = sorted(expected), sorted(got)
                if name == "context_used":
                    expected = sorted(expected)
                if got != expected:
                    problems.append(f"{name}: expected {expected}, got {got}")
            turns += 1
            turns_right += not problems
            if problems:
                all_right = False
                failures.append({"dialogue": dialogue.id, "turn": number, "text": turn.text,
                                 "problems": problems})
        dialogues_right += all_right
    return {"dialogues": len(dialogues), "dialogues_right": dialogues_right, "turns": turns,
            "turns_right": turns_right, "turn_accuracy": turns_right / turns,
            "dialogue_accuracy": dialogues_right / len(dialogues), "failures": failures}


def print_set(name: str, report: dict) -> None:
    present = [f for f in HEADLINE if f in report["all"]["fields"]]
    print(f"\n{name}")
    print(f"  {'field':<17}" + "".join(f"{s:>9}" for s in SCOPES)
          + "   (n=" + "/".join(str(report[s]["n"]) for s in SCOPES) + ")")
    for field in present:
        label = "COMPLETE QUERY" if field == "exact" else field
        print(f"  {label:<17}" + "".join(
            f"{report[s]['fields'].get(field, float('nan')):>9.3f}" for s in SCOPES))
    print("  first cause of each failed query:")
    for category in CATEGORIES:
        counts = [report[s]["errors"].get(category, 0) for s in SCOPES]
        if counts[0]:
            print(f"    {category:<30}" + "".join(f"{c:>6}" for c in counts))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--tag", required=True, help="name for this run's result file")
    parser.add_argument("--compare", help="tag of an earlier run to compare against")
    parser.add_argument("--examples", type=int, default=4, help="failures shown per category")
    args = parser.parse_args()

    setup_logging("WARNING")
    sys.stdout.reconfigure(encoding="utf-8")
    settings = load_settings()
    ontology = get_ontology()
    data_dir = settings.paths.data_dir / "test"
    pipeline = NlpPipeline.from_settings(settings)

    gold_sets = {name: load_gold(data_dir / f"{name}.yaml", ontology)
                 for name in ("gold", "gold_v2")}
    test = read_jsonl(data_dir / "test.jsonl")
    items = {
        name: [(g.text, g.language.value, expected_from_gold(g.expected, g.language))
               for g in records]
        for name, records in gold_sets.items()
    }
    realistic = load_realistic(data_dir / "realistic.yaml", ontology)
    items["realistic"] = [(r.text, r.language.value, expected_from_gold(r.expected, r.language))
                          for r in realistic if r.scored]
    items["test"] = [(r.text, r.language.value, expected_from_record(r, ontology, settings.decision))
                     for r in test]

    results, rows_by_set = {}, {}
    for name, set_items in items.items():
        rows_by_set[name] = run_set(pipeline, set_items)
        results[name] = aggregate(rows_by_set[name])
        print_set(f"=== {name} ===", results[name])

    # Decision behaviour: out-of-domain detection and confidence, per language.
    print("\n=== decision behaviour ===")
    print(f"  {'set':<10}{'scope':<5}{'off-topic':>10}{'rejected':>9}{'answered':>9}"
          f"{'real':>6}{'rejected':>9}{'asked(conf)':>12}{'answered':>9}{'wrong intent':>13}")
    results["decision"] = {}
    for name, rows in rows_by_set.items():
        summary = decision_summary(rows)
        results["decision"][name] = summary
        for scope in SCOPES:
            d = summary[scope]

            def pct(value):
                return f"{value:.1%}" if value is not None else "-"

            print(f"  {name:<10}{scope:<5}{d['n_off_topic']:>10}{pct(d['off_topic_rejected']):>9}"
                  f"{pct(d['off_topic_answered']):>9}{d['n_real']:>6}{pct(d['real_rejected']):>9}"
                  f"{pct(d['real_asked_low_confidence']):>12}{pct(d['real_answered']):>9}"
                  f"{pct(d['answered_with_wrong_intent']):>13}")

    # Real-user-style set by phenomenon, and the unsupported inputs.
    by_text = {r.text: r for r in realistic}
    print("\n=== realistic set by phenomenon (complete-query match) ===")
    phenomena = {}
    for row in rows_by_set["realistic"]:
        bucket = phenomena.setdefault(by_text[row["text"]].phenomenon, [0, 0])
        bucket[0] += row["fields"]["exact"]
        bucket[1] += 1
    results["realistic_by_phenomenon"] = {k: {"right": v[0], "n": v[1]}
                                          for k, v in phenomena.items()}
    for phenomenon, (right, total) in sorted(phenomena.items()):
        print(f"  {phenomenon:<24}{right:>3} of {total}")
    print("  unsupported input (not scored), what the pipeline did:")
    results["unsupported"] = []
    for record in realistic:
        if not record.scored:
            response = pipeline.analyze(record.text)
            results["unsupported"].append({
                "text": record.text, "phenomenon": record.phenomenon,
                "language": response.language.code.value, "status": response.status.value,
                "intent": response.intent.label.value})
            print(f"    [{record.phenomenon}] {record.text}\n"
                  f"        -> language {response.language.code.value}, "
                  f"{response.intent.label.value}, {response.status.value}")

    dialogues = run_dialogues(pipeline, load_dialogues(data_dir / "dialogues.yaml"))
    results["dialogues"] = dialogues
    print(f"\n=== dialogues ===\n  turns right {dialogues['turns_right']} of {dialogues['turns']} "
          f"({dialogues['turn_accuracy']:.1%}); whole dialogues right "
          f"{dialogues['dialogues_right']} of {dialogues['dialogues']}")
    for failure in dialogues["failures"]:
        print(f"  FAIL {failure['dialogue']} turn {failure['turn']}: {failure['text']}")
        for problem in failure["problems"]:
            print(f"       {problem}")

    # Latency: one query at a time, as the API will serve them.
    sample = [text for text, _, _ in items["test"][::6]]
    pipeline.analyze(sample[0])  # warm-up
    timings = []
    for text in sample:
        started = time.perf_counter()
        pipeline.analyze(text)
        timings.append((time.perf_counter() - started) * 1000)
    timings.sort()
    latency = {"n": len(timings), "median_ms": statistics.median(timings),
               "p95_ms": timings[int(0.95 * len(timings)) - 1], "device": str(pick_device())}
    results["latency"] = latency
    print(f"\n=== latency ({latency["device"]}, {latency["n"]} queries, one at a time) ===\n"
          f"  median {latency['median_ms']:.0f} ms, 95th percentile {latency['p95_ms']:.0f} ms")

    print("\n=== error examples (hand-written sets) ===")
    for name in ("gold", "gold_v2", "realistic"):
        for category, rows in errors_by_category(rows_by_set[name]).items():
            print(f"\n[{name}] {category}: {len(rows)}")
            for row in rows[:args.examples]:
                wrong = [f for f, ok in row["fields"].items() if not ok and f != "exact"]
                print(f"  ({row['language']}) {row['text']}")
                for field in wrong:
                    print(f"       {field}: expected {row['expected'].get(field)}, "
                          f"got {row['actual'].get('scenario' if field == 'scenario_amount' else field)}")
                if row["warnings"]:
                    print(f"       warnings: {row['warnings']}")

    out_dir = settings.paths.models_dir / "evaluation"
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / f"{args.tag}.json").write_text(json.dumps(
        {"summary": results, "rows": rows_by_set},
        indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nsaved to {out_dir / (args.tag + '.json')}")

    if args.compare:
        before = json.loads((out_dir / f"{args.compare}.json").read_text(encoding="utf-8"))["summary"]
        print(f"\n=== complete-query exact match: {args.compare} -> {args.tag} ===")
        print(f"  {'set':<10}" + "".join(f"{s:>18}" for s in SCOPES))
        for name in ("gold", "gold_v2", "realistic", "test"):
            if name not in before:
                continue
            cells = "".join(
                f"{before[name][s]['fields']['exact']:>9.3f} ->{results[name][s]['fields']['exact']:>6.3f}"
                for s in SCOPES)
            print(f"  {name:<10}{cells}")
        print(f"  dialogue turns: {before['dialogues']['turns_right']} -> "
              f"{dialogues['turns_right']} of {dialogues['turns']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
