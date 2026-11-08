"""Typed contract between the NLP subsystem and everything downstream.

Design rule: the schema checks SHAPE (types, enums, internal consistency of a
single object). It does not check COMPLETENESS. A query with no location is a
valid StructuredQuery; whether that is acceptable for its intent is decided by
the validator in Phase 11, which answers with a clarification request rather
than an exception.
"""

from datetime import date
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, computed_field, model_validator

from backend.nlp.query.enums import (
    AnswerKind,
    ChangeUnit,
    Direction,
    Disaster,
    EntityType,
    Intent,
    Language,
    LocationType,
    Operation,
    RiskTarget,
    Status,
    TimeType,
    TimeUnit,
    Variable,
)

SCHEMA_VERSION = "1.0"


class _Model(BaseModel):
    model_config = ConfigDict(extra="forbid")


class LocationRef(_Model):
    """A resolved place. `id` is the key shared with the future database."""

    id: str = Field(pattern=r"^loc:[a-z0-9_]+$")
    name: str
    type: LocationType
    parent: str | None = None


class TimePeriod(_Model):
    """Either relative ("last 5 years": value=5, unit=year) or an explicit range."""

    type: TimeType
    value: int | None = Field(default=None, gt=0)
    unit: TimeUnit | None = None
    start: date | None = None
    end: date | None = None

    @model_validator(mode="after")
    def _check_fields_match_type(self) -> Self:
        relative = self.type in (TimeType.RELATIVE_PAST, TimeType.RELATIVE_FUTURE)
        has_amount = self.value is not None and self.unit is not None
        has_any_amount = self.value is not None or self.unit is not None
        has_range = self.start is not None and self.end is not None
        has_any_range = self.start is not None or self.end is not None

        if relative and (not has_amount or has_any_range):
            raise ValueError(f"{self.type} needs value and unit, and no start/end")
        if self.type is TimeType.DATE_RANGE:
            if not has_range or has_any_amount:
                raise ValueError("date_range needs start and end, and no value/unit")
            if self.start > self.end:
                raise ValueError("start must not be after end")
        if self.type is TimeType.CURRENT and (has_any_amount or has_any_range):
            raise ValueError("current takes no other fields")
        return self


class Scenario(_Model):
    """A hypothetical change to one variable."""

    variable: Variable
    change: float = Field(gt=0)
    unit: ChangeUnit
    direction: Direction


class StructuredQuery(_Model):
    """Language-independent representation of what the user asked."""

    schema_version: str = SCHEMA_VERSION
    intent: Intent
    operation: Operation
    answer_kind: AnswerKind
    locations: list[LocationRef] = Field(default_factory=list)
    variables: list[Variable] = Field(default_factory=list)
    disasters: list[Disaster] = Field(default_factory=list)
    time_period: TimePeriod | None = None
    scenario: Scenario | None = None
    target: RiskTarget | Variable | None = None
    # Names of fields inherited from earlier turns of the conversation.
    context_used: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _no_query_for_out_of_domain(self) -> Self:
        if self.intent is Intent.OUT_OF_DOMAIN:
            raise ValueError("OUT_OF_DOMAIN has no structured query")
        return self


class LanguageResult(_Model):
    code: Language
    confidence: float = Field(ge=0, le=1)


class IntentResult(_Model):
    label: Intent
    confidence: float = Field(ge=0, le=1)


class Entity(_Model):
    """A span found by NER. `start`/`end` are character offsets into the
    normalised query text; `normalized` is None when no canonical ID was found."""

    text: str = Field(min_length=1)
    type: EntityType
    start: int = Field(ge=0)
    end: int
    normalized: str | None = None
    confidence: float = Field(ge=0, le=1)

    @model_validator(mode="after")
    def _check_span(self) -> Self:
        if self.end <= self.start:
            raise ValueError("end must be greater than start")
        return self


class Clarification(_Model):
    """What to ask the user. `message_key` is translated by the UI/LLM later."""

    reason: str
    message_key: str
    missing_fields: list[str] = Field(default_factory=list)
    # Choices to offer the user, e.g. the two most likely intents.
    options: list[str] = Field(default_factory=list)


class AnalyzeRequest(_Model):
    query: str = Field(min_length=1)
    session_id: str | None = None


class AnalyzeResponse(_Model):
    """Response of POST /nlp/analyze."""

    language: LanguageResult
    intent: IntentResult
    entities: list[Entity] = Field(default_factory=list)
    structured_query: StructuredQuery | None = None
    status: Status
    clarification: Clarification | None = None
    warnings: list[str] = Field(default_factory=list)

    @computed_field
    @property
    def needs_clarification(self) -> bool:
        return self.status is Status.NEEDS_CLARIFICATION

    @model_validator(mode="before")
    @classmethod
    def _accept_own_json(cls, data):
        # `needs_clarification` is derived from `status` and appears in the
        # JSON output. A consumer that parses a response back into this model
        # must not be rejected for sending it.
        if isinstance(data, dict) and "needs_clarification" in data:
            data = {k: v for k, v in data.items() if k != "needs_clarification"}
        return data

    @model_validator(mode="after")
    def _check_status_consistency(self) -> Self:
        if self.status is Status.OUT_OF_DOMAIN and self.structured_query is not None:
            raise ValueError("out_of_domain response must not carry a structured query")
        if self.status is Status.OK and self.structured_query is None:
            raise ValueError("ok response must carry a structured query")
        if self.status is Status.NEEDS_CLARIFICATION and self.clarification is None:
            raise ValueError("needs_clarification response must say what to clarify")
        if self.status is not Status.NEEDS_CLARIFICATION and self.clarification is not None:
            raise ValueError("clarification is only allowed with needs_clarification")
        return self
