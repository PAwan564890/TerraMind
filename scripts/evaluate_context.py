"""Evaluate the conversation-context rules on the test dialogues.

Run from the project root:
    python scripts/evaluate_context.py

The rules are fed a perfect parse of each turn, so this measures the context
logic alone, not the models in front of it.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.core import load_settings  # noqa: E402
from backend.nlp.context.dialogues import load_dialogues, run_dialogues  # noqa: E402
from backend.nlp.ontology import get_ontology  # noqa: E402


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    settings = load_settings()
    dialogues = load_dialogues(settings.paths.data_dir / "test" / "dialogues.yaml")
    report = run_dialogues(dialogues, get_ontology(), settings.context)

    print(f"turns right:     {report['turns_right']} of {report['turns']} "
          f"({report['turn_accuracy']:.1%})")
    print(f"dialogues right: {report['dialogues_right']} of {report['dialogues']} "
          f"({report['dialogue_accuracy']:.1%})")
    for failure in report["failures"]:
        print(f"\nFAIL {failure['dialogue']} turn {failure['turn']}: {failure['text']}")
        for problem in failure["problems"]:
            print(f"     {problem}")
    return 1 if report["failures"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
