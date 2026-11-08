"""End-to-end scoring: compare what the whole pipeline returns with what a
perfect pipeline would return, field by field, and name the first thing
that went wrong."""

from collections import Counter, defaultdict
from typing import Any

from backend.core.config import DecisionConfig
from backend.nlp.dataset.records import DatasetRecord, GoldExpected
from backend.nlp.query.enums import EntityType, Intent, Language, Status
from backend.nlp.query.intents import derive_answer_kind
from backend.nlp.query.schema import AnalyzeResponse, Scenario, StructuredQuery, TimePeriod
from backend.nlp.query.validator import validate_query

# Fields compared for a query that should be answered or questioned.
QUERY_FIELDS = ("intent", "operation", "locations", "variables", "disasters",
                "time_period", "scenario", "target")

# First match wins, so the order is the order of the pipeline: an early
# failure is blamed before the later ones it causes.
CATEGORIES = (
    "ood_missed", "false_rejection", "low_confidence", "intent_confusion",
    "unknown_or_unresolved_entity", "entity_missed_or_wrong", "time", "scenario",
    "operation", "validation",
)


def _time(period: TimePeriod | None):
    return period.model_dump(mode="json", exclude_none=True) if period else None


def actual_fields(response: AnalyzeResponse) -> dict[str, Any]:
    query = response.structured_query
    fields: dict[str, Any] = {
        "status": response.status.value,
        "language": response.language.code.value,
        "intent": response.intent.label.value,
    }
    if query is None:
        fields.update(operation=None, locations=frozenset(), variables=frozenset(),
                      disasters=frozenset(), time_period=None, scenario=None, target=None)
        return fields
    fields.update(
        operation=query.operation.value,
        # Sets: "Gangtok and Namchi" equals "Namchi and Gangtok".
        locations=frozenset(loc.id for loc in query.locations),
        variables=frozenset(v.value for v in query.variables),
        disasters=frozenset(d.value for d in query.disasters),
        time_period=_time(query.time_period),
        scenario=query.scenario.model_dump(mode="json") if query.scenario else None,
        target=query.target.value if query.target else None,
    )
    return fields


def expected_from_gold(expected: GoldExpected, language: Language) -> dict[str, Any]:
    return {
        "status": expected.status.value,
        "language": language.value,
        "intent": expected.intent.value,
        "operation": expected.operation.value if expected.operation else None,
        "locations": frozenset(expected.locations),
        "variables": frozenset(v.value for v in expected.variables),
        "disasters": frozenset(d.value for d in expected.disasters),
        "time_period": _time(expected.time_period),
        "scenario": expected.scenario.model_dump(mode="json") if expected.scenario else None,
        "target": expected.target.value if expected.target else None,
    }


def expected_from_record(record: DatasetRecord, ontology, config: DecisionConfig) -> dict[str, Any]:
    """Expected result for a generated row, derived from its labels.

    The expected STATUS comes from running the validator on the labelled
    slots: a template with no location slot must yield a clarification.
    Only the amount and direction of a scenario are compared (key
    `scenario_amount`); which variable changes is not labelled in the data.
    """
    if record.intent is Intent.OUT_OF_DOMAIN:
        return {"status": Status.OUT_OF_DOMAIN.value, "language": record.language.value,
                "intent": record.intent.value}

    def of(entity_type):
        return [e for e in record.entities if e.type is entity_type]

    locations = [ontology.location_ref(e.normalized) for e in of(EntityType.LOCATION)]
    variables = list(dict.fromkeys(e.normalized for e in of(EntityType.ENV_VARIABLE)))
    disasters = list(dict.fromkeys(e.normalized for e in of(EntityType.DISASTER)))
    times = of(EntityType.TIME)
    changes = of(EntityType.CHANGE)
    scenario = None
    if record.intent is Intent.SCENARIO_ANALYSIS and changes and variables and record.direction:
        scenario = Scenario(variable=variables[0], direction=record.direction,
                            change=changes[0].normalized["change"],
                            unit=changes[0].normalized["unit"])
    query = StructuredQuery(
        intent=record.intent, operation=record.operation,
        answer_kind=derive_answer_kind(record.intent, record.operation),
        locations=list({loc.id: loc for loc in locations}.values()),
        variables=variables, disasters=disasters,
        time_period=TimePeriod.model_validate(times[0].normalized) if times else None,
        scenario=scenario,
    )
    result = validate_query(query, [], config)
    final = result.query
    return {
        "status": (Status.OK if result.ok else Status.NEEDS_CLARIFICATION).value,
        "language": record.language.value,
        "intent": final.intent.value,
        "operation": final.operation.value,
        "locations": frozenset(loc.id for loc in final.locations),
        "variables": frozenset(v.value for v in final.variables),
        "disasters": frozenset(d.value for d in final.disasters),
        "time_period": _time(final.time_period),
        "scenario_amount": ({k: v for k, v in scenario.model_dump(mode="json").items()
                             if k != "variable"} if scenario else None),
    }


def compare(expected: dict[str, Any], actual: dict[str, Any]) -> dict[str, bool]:
    """Per-field correctness, plus `exact` for the complete query.

    An out-of-domain query is right if it is rejected; nothing else about it
    is compared. Language is scored separately and is not part of `exact`,
    because a wrong language does not change the structured query.
    """
    result = {"status": expected["status"] == actual["status"],
              "language": expected["language"] == actual["language"]}
    if expected["status"] == Status.OUT_OF_DOMAIN.value:
        result["exact"] = result["status"]
        return result
    for name in expected:
        if name in ("status", "language"):
            continue
        if name == "scenario_amount":
            got = actual["scenario"]
            got = {k: v for k, v in got.items() if k != "variable"} if got else None
            result[name] = expected[name] == got
        else:
            result[name] = expected[name] == actual[name]
    result["exact"] = all(v for k, v in result.items() if k != "language")
    return result


def categorize(expected: dict[str, Any], response: AnalyzeResponse,
               fields: dict[str, bool]) -> str | None:
    """The first cause of a failed query, or None if the query is exactly right."""
    if fields["exact"]:
        return None
    out = Status.OUT_OF_DOMAIN.value
    if expected["status"] == out:
        return "ood_missed"
    if response.status.value == out:
        return "false_rejection"
    if response.clarification and response.clarification.reason == "low_confidence":
        return "low_confidence"
    if not fields.get("intent", True):
        return "intent_confusion"
    slots_wrong = not all(fields.get(name, True) for name in ("locations", "variables", "disasters"))
    if slots_wrong and any(w.startswith("unresolved_") for w in response.warnings):
        return "unknown_or_unresolved_entity"
    if slots_wrong:
        return "entity_missed_or_wrong"
    if not fields.get("time_period", True):
        return "time"
    if not all(fields.get(name, True) for name in ("scenario", "scenario_amount", "target")):
        return "scenario"
    if not fields.get("operation", True):
        return "operation"
    return "validation"


def aggregate(rows: list[dict]) -> dict:
    """rows: [{'language', 'fields': {...}, 'category'}] -> rates per scope."""
    report = {}
    for scope in ("all", *[language.value for language in Language]):
        chosen = [r for r in rows if scope == "all" or r["language"] == scope]
        if not chosen:
            continue
        totals, right = Counter(), Counter()
        for row in chosen:
            for name, ok in row["fields"].items():
                totals[name] += 1
                right[name] += ok
        report[scope] = {
            "n": len(chosen),
            "fields": {name: right[name] / totals[name] for name in totals},
            "field_counts": {name: totals[name] for name in totals},
            "errors": dict(Counter(r["category"] for r in chosen if r["category"])),
        }
    return report


def errors_by_category(rows: list[dict]) -> dict[str, list[dict]]:
    grouped = defaultdict(list)
    for row in rows:
        if row["category"]:
            grouped[row["category"]].append(row)
    return grouped


def decision_summary(rows: list[dict]) -> dict:
    """How the ok / ask / reject decision behaved, per language.

    rows need `language`, `expected` and `actual` (field dicts), and
    `clarification` (the reason, or None).
    """
    out = Status.OUT_OF_DOMAIN.value
    report = {}
    for scope in ("all", *[language.value for language in Language]):
        chosen = [r for r in rows if scope == "all" or r["language"] == scope]
        if not chosen:
            continue
        off_topic = [r for r in chosen if r["expected"]["status"] == out]
        real = [r for r in chosen if r["expected"]["status"] != out]
        answered = [r for r in real if r["actual"]["status"] == Status.OK.value]

        def share(part, whole):
            return len(part) / len(whole) if whole else None

        report[scope] = {
            "n_off_topic": len(off_topic),
            "n_real": len(real),
            # Out-of-domain detection
            "off_topic_rejected": share([r for r in off_topic if r["actual"]["status"] == out],
                                        off_topic),
            "off_topic_answered": share([r for r in off_topic
                                         if r["actual"]["status"] == Status.OK.value], off_topic),
            "real_rejected": share([r for r in real if r["actual"]["status"] == out], real),
            # Confidence behaviour
            "real_asked_low_confidence": share(
                [r for r in real if r["clarification"] == "low_confidence"], real),
            "real_answered": share(answered, real),
            "answered_with_wrong_intent": share(
                [r for r in answered if r["actual"]["intent"] != r["expected"]["intent"]],
                answered),
        }
    return report
