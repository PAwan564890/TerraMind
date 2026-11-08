"""Checks that a structured query is complete enough to act on.

The schema (schema.py) guarantees the query's SHAPE. This module checks its
SENSE for the given intent. When something is missing it never guesses: it
returns a Clarification that says what to ask the user.

The one deliberate default is the time span of a trend question, which is
documented, configurable, and reported in the warnings.
"""

from dataclasses import dataclass, field

from backend.core.config import DecisionConfig
from backend.nlp.query.enums import ChangeUnit, Intent, Operation, TimeType, TimeUnit
from backend.nlp.query.intents import INTENT_SPECS
from backend.nlp.query.schema import Clarification, StructuredQuery, TimePeriod


@dataclass
class ValidationResult:
    query: StructuredQuery
    clarification: Clarification | None = None
    warnings: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return self.clarification is None


def _empty(query: StructuredQuery, field_name: str) -> bool:
    value = getattr(query, field_name)
    return value is None or value == []


def validate_query(
    query: StructuredQuery, pipeline_warnings: list[str], config: DecisionConfig
) -> ValidationResult:
    """Apply the rules in order; the first failure becomes the clarification.

    `pipeline_warnings` are the notes produced earlier in the pipeline, such
    as "unresolved_location:Paris".
    """
    spec = INTENT_SPECS[query.intent]

    def ask(reason: str, message_key: str, missing: list[str]) -> ValidationResult:
        return ValidationResult(query, Clarification(
            reason=reason, message_key=message_key, missing_fields=missing,
        ))

    # 1. A place the gazetteer does not know. Asked about even if another
    #    place in the query did resolve: dropping it silently would answer a
    #    different question from the one asked.
    unknown = [w.split(":", 1)[1] for w in pipeline_warnings
               if w.startswith("unresolved_location:")]
    if unknown:
        result = ask("unknown_location", "unknown_location", ["locations"])
        result.clarification.options = unknown
        return result

    # 2. The operation must be one the intent allows. Cannot happen through
    #    the pipeline; guarded in case a query is built some other way.
    if query.operation not in spec.allowed_operations:
        return ask("invalid_operation", "unclear_request", ["operation"])

    # 3. Required fields. A group such as {variables, disasters} is satisfied
    #    by either.
    missing = []
    for group in spec.required:
        if all(_empty(query, name) for name in group):
            missing.append("|".join(sorted(group)))
    if missing:
        first = missing[0].split("|")[0]
        return ask("missing_required_field", f"missing_{first}", missing)

    # 4. A comparison needs two things to compare.
    if query.intent is Intent.COMPARISON and len(query.locations) < 2:
        return ask("comparison_needs_two", "missing_comparison_target", ["locations"])

    # 5. A scenario's amount must be plausible.
    if query.scenario is not None:
        limit = (config.max_percent_change if query.scenario.unit is ChangeUnit.PERCENT
                 else config.max_absolute_change)
        if query.scenario.change > limit:
            return ask("implausible_change", "confirm_change_amount", ["scenario"])

    # 6. Documented default: a trend with no time span.
    warnings = []
    if query.operation is Operation.TREND and query.time_period is None:
        query = query.model_copy(update={"time_period": TimePeriod(
            type=TimeType.RELATIVE_PAST, value=config.default_trend_years, unit=TimeUnit.YEAR,
        )})
        warnings.append("time_period_defaulted")

    return ValidationResult(query, None, warnings)
