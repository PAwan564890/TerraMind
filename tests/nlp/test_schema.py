import pytest
from pydantic import ValidationError

from backend.nlp.ontology import get_ontology
from backend.nlp.query.enums import (
    AnswerKind,
    ChangeUnit,
    Direction,
    Intent,
    Operation,
    RiskTarget,
    Status,
    TimeType,
    TimeUnit,
    Variable,
)
from backend.nlp.query.schema import (
    AnalyzeResponse,
    Clarification,
    Entity,
    IntentResult,
    LanguageResult,
    Scenario,
    StructuredQuery,
    TimePeriod,
)

ONTOLOGY = get_ontology()


def loc(name):
    return ONTOLOGY.lookup_location(name)


# The three end-to-end examples from the project brief.
TREND_QUERY = StructuredQuery(
    intent=Intent.CLIMATE_TREND,
    operation=Operation.TREND,
    answer_kind=AnswerKind.ANALYSIS,
    locations=[loc("Gangtok")],
    variables=[Variable.PRECIPITATION],
    time_period=TimePeriod(type=TimeType.RELATIVE_PAST, value=5, unit=TimeUnit.YEAR),
)
SCENARIO_QUERY = StructuredQuery(
    intent=Intent.SCENARIO_ANALYSIS,
    operation=Operation.SCENARIO,
    answer_kind=AnswerKind.SCENARIO,
    locations=[loc("गंगटोक")],
    variables=[Variable.PRECIPITATION],
    scenario=Scenario(
        variable=Variable.PRECIPITATION,
        change=20,
        unit=ChangeUnit.PERCENT,
        direction=Direction.INCREASE,
    ),
    target=RiskTarget.FLOOD_RISK,
)
COMPARE_QUERY = StructuredQuery(
    intent=Intent.COMPARISON,
    operation=Operation.COMPARE,
    answer_kind=AnswerKind.ANALYSIS,
    locations=[loc("North Sikkim"), loc("South Sikkim")],
    variables=[Variable.PRECIPITATION],
)


@pytest.mark.parametrize("query", [TREND_QUERY, SCENARIO_QUERY, COMPARE_QUERY])
def test_brief_examples_round_trip_through_json(query):
    assert StructuredQuery.model_validate_json(query.model_dump_json()) == query


def test_json_uses_plain_strings():
    data = SCENARIO_QUERY.model_dump(mode="json")
    assert data["intent"] == "SCENARIO_ANALYSIS"
    assert data["variables"] == ["PRECIPITATION"]
    assert data["target"] == "FLOOD_RISK"
    assert data["locations"][0]["id"] == "loc:gangtok"
    assert data["scenario"] == {
        "variable": "PRECIPITATION",
        "change": 20.0,
        "unit": "percent",
        "direction": "increase",
    }


def test_target_keeps_its_enum_type_after_round_trip():
    restored = StructuredQuery.model_validate_json(SCENARIO_QUERY.model_dump_json())
    assert restored.target is RiskTarget.FLOOD_RISK


def test_incomplete_query_is_still_a_valid_shape():
    # Completeness is the validator's job (Phase 11), not the schema's.
    query = StructuredQuery(
        intent=Intent.WEATHER_QUERY,
        operation=Operation.LOOKUP,
        answer_kind=AnswerKind.OBSERVATION,
        variables=[Variable.TEMPERATURE],
    )
    assert query.locations == []


def test_out_of_domain_cannot_be_a_structured_query():
    with pytest.raises(ValidationError):
        StructuredQuery(
            intent=Intent.OUT_OF_DOMAIN,
            operation=Operation.LOOKUP,
            answer_kind=AnswerKind.OBSERVATION,
        )


def test_unknown_field_and_unknown_enum_value_are_rejected():
    base = TREND_QUERY.model_dump(mode="json")
    with pytest.raises(ValidationError):
        StructuredQuery.model_validate({**base, "extra_field": 1})
    with pytest.raises(ValidationError):
        StructuredQuery.model_validate({**base, "variables": ["RAIN"]})


@pytest.mark.parametrize(
    "kwargs",
    [
        {"type": "relative_past"},
        {"type": "relative_past", "value": 5},
        {"type": "relative_past", "value": 0, "unit": "year"},
        {"type": "date_range", "start": "2020-01-01"},
        {"type": "date_range", "start": "2021-01-01", "end": "2020-01-01"},
        {"type": "current", "value": 1, "unit": "day"},
    ],
)
def test_invalid_time_periods_are_rejected(kwargs):
    with pytest.raises(ValidationError):
        TimePeriod.model_validate(kwargs)


def test_valid_time_periods():
    TimePeriod(type=TimeType.CURRENT)
    TimePeriod(type=TimeType.RELATIVE_FUTURE, value=1, unit=TimeUnit.DAY)
    TimePeriod.model_validate({"type": "date_range", "start": "2015-01-01", "end": "2020-12-31"})


def test_entity_span_must_be_ordered():
    with pytest.raises(ValidationError):
        Entity(text="x", type="LOCATION", start=5, end=5, confidence=0.9)


LANG = LanguageResult(code="hi", confidence=0.98)


def test_ok_response_serialises_needs_clarification_flag():
    response = AnalyzeResponse(
        language=LANG,
        intent=IntentResult(label=Intent.CLIMATE_TREND, confidence=0.93),
        entities=[
            Entity(text="गंगटोक", type="LOCATION", start=0, end=6,
                   normalized="loc:gangtok", confidence=0.97)
        ],
        structured_query=TREND_QUERY,
        status=Status.OK,
    )
    data = response.model_dump(mode="json")
    assert data["needs_clarification"] is False
    assert data["status"] == "ok"
    assert data["language"] == {"code": "hi", "confidence": 0.98}


def test_clarification_response():
    response = AnalyzeResponse(
        language=LANG,
        intent=IntentResult(label=Intent.WEATHER_QUERY, confidence=0.88),
        status=Status.NEEDS_CLARIFICATION,
        clarification=Clarification(
            reason="missing_required_field",
            message_key="missing_location",
            missing_fields=["locations"],
        ),
    )
    assert response.needs_clarification is True


def test_inconsistent_responses_are_rejected():
    ood = IntentResult(label=Intent.OUT_OF_DOMAIN, confidence=0.96)
    AnalyzeResponse(language=LANG, intent=ood, status=Status.OUT_OF_DOMAIN)
    with pytest.raises(ValidationError):
        AnalyzeResponse(language=LANG, intent=ood, status=Status.OUT_OF_DOMAIN,
                        structured_query=TREND_QUERY)
    with pytest.raises(ValidationError):
        AnalyzeResponse(language=LANG, intent=ood, status=Status.OK)
    with pytest.raises(ValidationError):
        AnalyzeResponse(language=LANG, intent=ood, status=Status.NEEDS_CLARIFICATION)
