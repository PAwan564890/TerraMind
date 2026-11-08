"""Data types for conversation context."""

from pydantic import BaseModel, ConfigDict, Field

from backend.nlp.query.enums import Disaster, Intent, Language, RiskTarget, Variable
from backend.nlp.query.schema import LocationRef, Scenario, TimePeriod

# Slots that can be carried from one turn to the next.
SLOTS = ("locations", "variables", "disasters", "time_period")


class _Model(BaseModel):
    model_config = ConfigDict(extra="forbid")


class TurnParse(_Model):
    """What the NLP components extracted from ONE query, before context."""

    text: str
    language: Language
    intent: Intent
    locations: list[LocationRef] = Field(default_factory=list)
    variables: list[Variable] = Field(default_factory=list)
    disasters: list[Disaster] = Field(default_factory=list)
    time_period: TimePeriod | None = None
    scenario: Scenario | None = None
    target: RiskTarget | Variable | None = None
    # True when the query is only entities plus filler words ("What about
    # rainfall?", "गान्तोकमा?"). See fragments.is_fragment.
    is_fragment: bool = False
    # False when the classifier's confidence is below the decision threshold.
    intent_confident: bool = True


class ResolvedTurn(_Model):
    """The same turn after missing slots were filled from the conversation."""

    language: Language
    intent: Intent
    locations: list[LocationRef] = Field(default_factory=list)
    variables: list[Variable] = Field(default_factory=list)
    disasters: list[Disaster] = Field(default_factory=list)
    time_period: TimePeriod | None = None
    scenario: Scenario | None = None
    target: RiskTarget | Variable | None = None
    # Names of the fields that were inherited, so the caller can see (and
    # show the user) what was assumed.
    context_used: list[str] = Field(default_factory=list)
    is_followup: bool = False


class ConversationState(_Model):
    """What is remembered about one conversation."""

    language: Language | None = None
    intent: Intent | None = None
    locations: list[LocationRef] = Field(default_factory=list)
    variables: list[Variable] = Field(default_factory=list)
    disasters: list[Disaster] = Field(default_factory=list)
    time_period: TimePeriod | None = None
    # Number of turns processed so far.
    turn_count: int = 0
    # For each slot, the turn in which the user last STATED it.
    stated_at: dict[str, int] = Field(default_factory=dict)
    # Seconds since the epoch of the last message, for idle expiry.
    updated_at: float = 0.0
