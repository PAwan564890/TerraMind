"""Run the NLP pipeline on one or more queries and print the result.

Run from the project root:
    python scripts/analyze.py "What is the rainfall trend in Gangtok over the last five years?"
    python scripts/analyze.py "What is the temperature in Gangtok?" "और बारिश?" "भोलिको अवस्था कस्तो हुन्छ?"

Several queries are treated as consecutive turns of one conversation.
Add --json to print the full response instead of the summary.
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.core import load_settings, setup_logging  # noqa: E402
from backend.nlp.pipeline import NlpPipeline  # noqa: E402
from backend.nlp.preprocessing import InvalidQueryError  # noqa: E402


def summarize(response) -> str:
    lines = [f"  language: {response.language.code.value} ({response.language.confidence:.2f})   "
             f"intent: {response.intent.label.value} ({response.intent.confidence:.2f})   "
             f"status: {response.status.value}"]
    for entity in response.entities:
        lines.append(f"  entity:   {entity.text!r} {entity.type.value} -> {entity.normalized}")
    query = response.structured_query
    if query is not None:
        parts = [f"operation={query.operation.value}", f"answer_kind={query.answer_kind.value}"]
        if query.locations:
            parts.append("locations=" + ",".join(loc.id for loc in query.locations))
        if query.variables:
            parts.append("variables=" + ",".join(v.value for v in query.variables))
        if query.disasters:
            parts.append("disasters=" + ",".join(d.value for d in query.disasters))
        if query.time_period:
            parts.append("time=" + str(query.time_period.model_dump(mode="json", exclude_none=True)))
        if query.scenario:
            parts.append("scenario=" + str(query.scenario.model_dump(mode="json")))
        if query.target:
            parts.append(f"target={query.target.value}")
        if query.context_used:
            parts.append("context_used=" + ",".join(query.context_used))
        lines.append("  query:    " + "  ".join(parts))
    if response.clarification:
        c = response.clarification
        detail = [f"reason={c.reason}", f"message_key={c.message_key}"]
        if c.missing_fields:
            detail.append("missing=" + ",".join(c.missing_fields))
        if c.options:
            detail.append("options=" + ",".join(c.options))
        lines.append("  ask:      " + "  ".join(detail))
    if response.warnings:
        lines.append("  warnings: " + ", ".join(response.warnings))
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("queries", nargs="+")
    parser.add_argument("--json", action="store_true", help="print the full JSON response")
    args = parser.parse_args()

    setup_logging("WARNING")
    sys.stdout.reconfigure(encoding="utf-8")
    pipeline = NlpPipeline.from_settings(load_settings())
    session = "cli" if len(args.queries) > 1 else None

    for query in args.queries:
        print(f"\n> {query}")
        try:
            response = pipeline.analyze(query, session_id=session)
        except InvalidQueryError as error:
            print(f"  rejected ({error.code}): {error}")
            continue
        print(response.model_dump_json(indent=2) if args.json else summarize(response))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
