"""Record types for the training data and the gold test set, plus JSONL I/O."""

import json
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field

from backend.nlp.ontology import Ontology
from backend.nlp.query.enums import (
    Direction,
    Disaster,
    EntityType,
    Intent,
    Language,
    Operation,
    RiskTarget,
    Status,
    Variable,
)
from backend.nlp.query.schema import Scenario, TimePeriod

Split = Literal["train", "val", "test"]


class _Model(BaseModel):
    model_config = ConfigDict(extra="forbid")


class SpanLabel(_Model):
    """One labelled entity. Offsets are character positions in `text`
    (start inclusive, end exclusive), so text[start:end] is the entity."""

    start: int
    end: int
    type: EntityType
    text: str
    # Canonical value: an ID string for locations/variables/disasters, a small
    # object for time and change expressions.
    normalized: str | dict[str, Any]


class DatasetRecord(_Model):
    """One query, labelled for both intent classification and NER."""

    id: str
    text: str
    language: Language
    intent: Intent
    operation: Operation | None = None
    direction: Direction | None = None
    entities: list[SpanLabel] = Field(default_factory=list)
    # Every row from the same template family shares a group_id; a group never
    # crosses a split boundary.
    group_id: str
    source: Literal["template", "manual"]
    split: Split
    heldout_location: bool = False


def write_jsonl(path: Path, records: list[DatasetRecord]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    # newline="\n" keeps the file byte-identical on Windows and Linux.
    with path.open("w", encoding="utf-8", newline="\n") as f:
        for record in records:
            f.write(json.dumps(record.model_dump(mode="json"), ensure_ascii=False) + "\n")


def read_jsonl(path: Path) -> list[DatasetRecord]:
    with path.open(encoding="utf-8") as f:
        return [DatasetRecord.model_validate_json(line) for line in f if line.strip()]


# --- Gold test set -----------------------------------------------------------


class GoldExpected(_Model):
    """The structured result a perfect pipeline would produce."""

    status: Status
    intent: Intent
    operation: Operation | None = None
    locations: list[str] = Field(default_factory=list)
    variables: list[Variable] = Field(default_factory=list)
    disasters: list[Disaster] = Field(default_factory=list)
    time_period: TimePeriod | None = None
    scenario: Scenario | None = None
    target: RiskTarget | Variable | None = None
    missing_fields: list[str] = Field(default_factory=list)


class GoldRecord(_Model):
    id: str
    text: str
    language: Language
    expected: GoldExpected


def load_gold(path: Path, ontology: Ontology) -> list[GoldRecord]:
    """Read the hand-written gold file: one item per meaning, with the same
    expected output for its English, Hindi and Nepali phrasing."""
    with path.open(encoding="utf-8") as f:
        items = yaml.safe_load(f)

    records = []
    for item in items:
        expected = GoldExpected.model_validate(item["expected"])
        for loc_id in expected.locations:
            if loc_id not in ontology.locations:
                raise ValueError(f"gold item {item['id']}: unknown location {loc_id}")
        for language in Language:
            records.append(
                GoldRecord(
                    id=f"{item['id']}.{language.value}",
                    text=item[language.value],
                    language=language,
                    expected=expected,
                )
            )
    return records


# --- Real-user-style set -----------------------------------------------------


class RealisticRecord(_Model):
    """One query from realistic.yaml. Unlike the gold sets, each query exists
    in one language only and names the phenomenon it tests."""

    id: str
    text: str
    language: Language
    phenomenon: str
    # False for input the system does not claim to support. Such a query is
    # run and reported, but does not count towards any score.
    scored: bool = True
    expected: GoldExpected


def load_realistic(path: Path, ontology: Ontology) -> list[RealisticRecord]:
    with path.open(encoding="utf-8") as f:
        records = [RealisticRecord.model_validate(item) for item in yaml.safe_load(f)]
    for record in records:
        for loc_id in record.expected.locations:
            if loc_id not in ontology.locations:
                raise ValueError(f"{record.id}: unknown location {loc_id}")
    return records
