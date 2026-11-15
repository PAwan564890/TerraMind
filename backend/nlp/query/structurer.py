"""Turns normalised entities into slots, and a resolved turn into a StructuredQuery."""

from dataclasses import dataclass

from backend.nlp.context.state import ResolvedTurn, TurnParse
from backend.nlp.normalization import ChangeValue, Resolution, parse_change, parse_time
from backend.nlp.normalization.explicit_dates import parse_explicit_period
from backend.nlp.ontology import Ontology
from backend.nlp.query.cues import derive_operation, detect_direction
from backend.nlp.query.enums import EntityType, Intent, Language, Variable
from backend.nlp.query.intents import derive_answer_kind
from backend.nlp.query.schema import LocationRef, Scenario, StructuredQuery, TimePeriod


@dataclass(frozen=True)
class FoundEntity:
    """An entity span together with its normalisation result."""

    text: str
    start: int
    end: int
    confidence: float      # from NER
    resolution: Resolution


def _unique(items: list) -> list:
    seen, result = set(), []
    for item in items:
        key = item.id if isinstance(item, LocationRef) else item
        if key not in seen:
            seen.add(key)
            result.append(item)
    return result


def _gap(a: FoundEntity, b: FoundEntity) -> int:
    """Characters between two spans (0 if they touch or overlap)."""
    return max(a.start - b.end, b.start - a.end, 0)


def build_turn(
    text: str, language: Language, intent: Intent, entities: list[FoundEntity],
    ontology: Ontology, is_fragment: bool,
) -> tuple[TurnParse, list[str]]:
    """Slots stated in this query alone, plus warnings about what was dropped."""
    warnings: list[str] = []
    resolved = [e for e in entities if e.resolution.resolved]
    for entity in entities:
        if not entity.resolution.resolved:
            # Kept visible: the validator turns an unknown place into a
            # clarification instead of silently ignoring it.
            warnings.append(f"unresolved_{entity.resolution.type.value.lower()}:{entity.text}")

    def values(entity_type: EntityType) -> list[FoundEntity]:
        return [e for e in resolved if e.resolution.type is entity_type]

    locations = _unique([e.resolution.value for e in values(EntityType.LOCATION)])
    variable_entities = values(EntityType.ENV_VARIABLE)
    variables = _unique([e.resolution.value for e in variable_entities])
    disasters = _unique([e.resolution.value for e in values(EntityType.DISASTER)])

    time_entities = values(EntityType.TIME)
    time_period: TimePeriod | None = parse_explicit_period(text)
    if time_period is not None:
        # Full-query explicit dates are more specific than any partial TIME
        # span; do this before context storage, including when NER misses time.
        warnings.append("explicit_time_from_text")
    elif time_entities:
        time_period = time_entities[0].resolution.value
        if len(time_entities) > 1:
            warnings.append("multiple_time_expressions")
        if time_entities[0].resolution.confidence < 1.0:
            warnings.append("ambiguous_time")
    else:
        # Safety net: the time rules are cheap, so run them over the whole
        # query in case NER missed the expression.
        parsed = parse_time(text, text, language=language)
        if parsed is not None:
            time_period = parsed.period
            warnings.append("time_from_rules")

    scenario: Scenario | None = None
    target = None
    if intent is Intent.SCENARIO_ANALYSIS:
        change_entities = values(EntityType.CHANGE)
        change: ChangeValue | None = change_entities[0].resolution.value if change_entities else None
        anchor = change_entities[0] if change_entities else None
        if change is None:
            change = parse_change(text)
            if change is not None:
                warnings.append("change_from_rules")

        # With two variables ("how would vegetation be affected if rainfall
        # drops by 20%"), the one next to the amount is the one that changes.
        changed: Variable | None = None
        if variable_entities:
            nearest = (min(variable_entities, key=lambda v: _gap(v, anchor))
                       if anchor else variable_entities[0])
            changed = nearest.resolution.value
        direction = detect_direction(text, anchor.start if anchor else None)

        if change is not None and changed is not None and direction is not None:
            scenario = Scenario(variable=changed, change=change.change, unit=change.unit,
                                direction=direction)
        else:
            missing = [name for name, value in (("variable", changed), ("change", change),
                                                ("direction", direction)) if value is None]
            warnings.append("incomplete_scenario:" + ",".join(missing))

        # What the question is about: a named hazard's risk, else a second variable.
        if disasters:
            target = ontology.risk_target(disasters[0])
        if target is None:
            others = [v for v in variables if v is not changed]
            target = others[0] if others else None

    turn = TurnParse(
        text=text, language=language, intent=intent, locations=locations,
        variables=variables, disasters=disasters, time_period=time_period,
        scenario=scenario, target=target, is_fragment=is_fragment,
    )
    return turn, warnings


def build_query(resolved: ResolvedTurn, text: str) -> StructuredQuery:
    """The final language-independent query. `text` is read only for cue words."""
    operation = derive_operation(resolved.intent, resolved.language, text, resolved.time_period)
    return StructuredQuery(
        intent=resolved.intent,
        operation=operation,
        answer_kind=derive_answer_kind(resolved.intent, operation),
        locations=resolved.locations,
        variables=resolved.variables,
        disasters=resolved.disasters,
        time_period=resolved.time_period,
        scenario=resolved.scenario,
        target=resolved.target,
        context_used=resolved.context_used,
    )
