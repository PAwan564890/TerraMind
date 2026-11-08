"""Loads the test conversations and scores context resolution on them."""

from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict, Field

from backend.core.config import ContextConfig
from backend.nlp.context.state import ResolvedTurn, TurnParse
from backend.nlp.context.store import ConversationManager
from backend.nlp.ontology import Ontology
from backend.nlp.query.enums import Disaster, Intent, Language, Variable
from backend.nlp.query.schema import Scenario, TimePeriod


class _Model(BaseModel):
    model_config = ConfigDict(extra="forbid")


class OracleParse(_Model):
    language: Language
    intent: Intent
    locations: list[str] = Field(default_factory=list)
    variables: list[Variable] = Field(default_factory=list)
    disasters: list[Disaster] = Field(default_factory=list)
    time_period: TimePeriod | None = None
    scenario: Scenario | None = None
    fragment: bool = False


class DialogueTurn(_Model):
    text: str
    parse: OracleParse
    # Only the keys present are checked.
    expect: dict[str, Any]


class Dialogue(_Model):
    id: str
    note: str = ""
    turns: list[DialogueTurn]


def load_dialogues(path: Path) -> list[Dialogue]:
    with path.open(encoding="utf-8") as f:
        return [Dialogue.model_validate(item) for item in yaml.safe_load(f)]


def to_turn_parse(turn: DialogueTurn, ontology: Ontology) -> TurnParse:
    parse = turn.parse
    return TurnParse(
        text=turn.text, language=parse.language, intent=parse.intent,
        locations=[ontology.location_ref(loc_id) for loc_id in parse.locations],
        variables=parse.variables, disasters=parse.disasters,
        time_period=parse.time_period, scenario=parse.scenario,
        is_fragment=parse.fragment,
    )


def mismatches(resolved: ResolvedTurn, expect: dict[str, Any]) -> list[str]:
    """Fields where the resolved turn differs from the expectation."""
    actual = {
        "intent": resolved.intent.value,
        "locations": [loc.id for loc in resolved.locations],
        "variables": [v.value for v in resolved.variables],
        "disasters": [d.value for d in resolved.disasters],
        "time_period": (resolved.time_period.model_dump(mode="json", exclude_none=True)
                        if resolved.time_period else None),
        "context_used": sorted(resolved.context_used),
    }
    problems = []
    for field, expected in expect.items():
        if field == "context_used":
            expected = sorted(expected)
        if actual[field] != expected:
            problems.append(f"{field}: expected {expected}, got {actual[field]}")
    return problems


def run_dialogues(dialogues: list[Dialogue], ontology: Ontology, config: ContextConfig) -> dict:
    """Feed every dialogue's oracle parses through the context rules."""
    manager = ConversationManager(config)
    turns = turns_right = dialogues_right = 0
    failures = []
    for dialogue in dialogues:
        all_right = True
        for number, turn in enumerate(dialogue.turns, start=1):
            # A fixed clock: these dialogues do not test idle expiry.
            resolved = manager.process(dialogue.id, to_turn_parse(turn, ontology), now=0.0)
            problems = mismatches(resolved, turn.expect)
            turns += 1
            turns_right += not problems
            if problems:
                all_right = False
                failures.append({"dialogue": dialogue.id, "turn": number, "text": turn.text,
                                 "problems": problems})
        dialogues_right += all_right
    return {
        "dialogues": len(dialogues), "dialogues_right": dialogues_right,
        "turns": turns, "turns_right": turns_right,
        "turn_accuracy": turns_right / turns, "dialogue_accuracy": dialogues_right / len(dialogues),
        "failures": failures,
    }
