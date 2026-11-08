"""Per-intent specification: the single source of truth for what each intent
means structurally. The dataset generator (Phase 2), the query structurer
(Phase 10) and the validator (Phase 11) all read this table.
"""

from dataclasses import dataclass

from backend.nlp.query.enums import AnswerKind, Intent, Operation


@dataclass(frozen=True)
class IntentSpec:
    purpose: str
    default_operation: Operation
    allowed_operations: frozenset[Operation]
    # Each group is a set of StructuredQuery field names; at least one field in
    # every group must be non-empty. {"variables", "disasters"} means "a
    # variable or a disaster".
    required: tuple[frozenset[str], ...]


def _spec(purpose, default, allowed, *required) -> IntentSpec:
    return IntentSpec(
        purpose=purpose,
        default_operation=default,
        allowed_operations=frozenset(allowed),
        required=tuple(frozenset(group) for group in required),
    )


O = Operation

INTENT_SPECS: dict[Intent, IntentSpec] = {
    Intent.WEATHER_QUERY: _spec(
        "Current or short-range conditions",
        O.LOOKUP, {O.LOOKUP, O.FORECAST},
        {"locations"}, {"variables"},
    ),
    Intent.CLIMATE_TREND: _spec(
        "Change of a climate variable over time",
        O.TREND, {O.TREND, O.EXPLAIN},
        {"locations"}, {"variables"},
    ),
    Intent.VEGETATION_ANALYSIS: _spec(
        "Vegetation, NDVI or land-cover state or change",
        O.LOOKUP, {O.LOOKUP, O.TREND, O.EXPLAIN},
        {"locations"},
    ),
    Intent.DISASTER_RISK: _spec(
        "Hazard risk or history",
        O.LOOKUP, {O.LOOKUP, O.RANK, O.EXPLAIN},
        {"disasters"},
    ),
    Intent.GEOLOCATION_QUERY: _spec(
        "Static geography: where, elevation, rivers, boundaries",
        O.LOOKUP, {O.LOOKUP},
        {"locations"},
    ),
    Intent.COMPARISON: _spec(
        "Same quantity across two or more places or periods",
        O.COMPARE, {O.COMPARE},
        {"variables", "disasters"},
    ),
    Intent.SCENARIO_ANALYSIS: _spec(
        "Hypothetical change and its effect",
        O.SCENARIO, {O.SCENARIO},
        {"scenario"}, {"locations"},
    ),
    Intent.GENERAL_ENVIRONMENT: _spec(
        "In-domain question with no data slot; routes to RAG later",
        O.EXPLAIN, {O.EXPLAIN},
    ),
}
# OUT_OF_DOMAIN has no spec: it never produces a structured query.

# When two intents apply to one query, the earlier one in this tuple wins.
INTENT_PRECEDENCE: tuple[Intent, ...] = (Intent.SCENARIO_ANALYSIS, Intent.COMPARISON)

_OPERATION_ANSWER_KIND: dict[Operation, AnswerKind] = {
    O.LOOKUP: AnswerKind.OBSERVATION,
    O.TREND: AnswerKind.ANALYSIS,
    O.COMPARE: AnswerKind.ANALYSIS,
    O.EXPLAIN: AnswerKind.ANALYSIS,
    O.RANK: AnswerKind.ANALYSIS,
    O.FORECAST: AnswerKind.PREDICTION,
    O.SCENARIO: AnswerKind.SCENARIO,
}


def derive_answer_kind(intent: Intent, operation: Operation) -> AnswerKind:
    """Scientific status of the answer this query will need."""
    # Risk is never observed directly; it is always a model output.
    if intent is Intent.DISASTER_RISK and operation in (O.LOOKUP, O.RANK):
        return AnswerKind.PREDICTION
    return _OPERATION_ANSWER_KIND[operation]
