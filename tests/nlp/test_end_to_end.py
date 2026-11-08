"""Tests for the end-to-end scoring code (not for model quality)."""

import pytest

from backend.core import load_settings
from backend.nlp.dataset.records import GoldExpected, load_gold, read_jsonl
from backend.nlp.evaluation.end_to_end import (
    CATEGORIES,
    actual_fields,
    aggregate,
    categorize,
    compare,
    expected_from_gold,
    expected_from_record,
)
from backend.nlp.ontology import get_ontology
from backend.nlp.query.enums import (
    AnswerKind,
    Intent,
    Language,
    Operation,
    Status,
    TimeType,
    TimeUnit,
    Variable,
)
from backend.nlp.query.schema import (
    AnalyzeResponse,
    Clarification,
    IntentResult,
    LanguageResult,
    StructuredQuery,
    TimePeriod,
)

SETTINGS = load_settings()
ONTOLOGY = get_ontology()
GANGTOK = ONTOLOGY.location_ref("loc:gangtok")
NAMCHI = ONTOLOGY.location_ref("loc:namchi")


def response(status=Status.OK, intent=Intent.WEATHER_QUERY, operation=Operation.LOOKUP,
             language="en", clarification=None, warnings=(), **slots):
    query = None
    if status is not Status.OUT_OF_DOMAIN and intent is not Intent.OUT_OF_DOMAIN:
        query = StructuredQuery(intent=intent, operation=operation,
                                answer_kind=AnswerKind.OBSERVATION, **slots)
    return AnalyzeResponse(
        language=LanguageResult(code=language, confidence=1.0),
        intent=IntentResult(label=intent, confidence=0.9),
        structured_query=query, status=status, clarification=clarification,
        warnings=list(warnings),
    )


def gold(status="ok", intent="WEATHER_QUERY", operation="LOOKUP", **slots):
    return expected_from_gold(
        GoldExpected(status=status, intent=intent, operation=operation, **slots), Language.EN
    )


WEATHER = gold(locations=["loc:gangtok"], variables=["TEMPERATURE"])


def score(expected, actual_response):
    fields = compare(expected, actual_fields(actual_response))
    return fields, categorize(expected, actual_response, fields)


def test_exact_match():
    fields, category = score(WEATHER, response(locations=[GANGTOK],
                                               variables=[Variable.TEMPERATURE]))
    assert fields["exact"] is True
    assert category is None


def test_location_order_does_not_matter():
    expected = gold(intent="COMPARISON", operation="COMPARE",
                    locations=["loc:gangtok", "loc:namchi"], variables=["HUMIDITY"])
    got = response(intent=Intent.COMPARISON, operation=Operation.COMPARE,
                   locations=[NAMCHI, GANGTOK], variables=[Variable.HUMIDITY])
    assert score(expected, got)[0]["exact"] is True


def test_language_is_scored_but_not_part_of_exact():
    fields, _ = score(WEATHER, response(language="hi", locations=[GANGTOK],
                                        variables=[Variable.TEMPERATURE]))
    assert fields["language"] is False
    assert fields["exact"] is True


def test_out_of_domain_is_judged_on_status_alone():
    expected = gold(status="out_of_domain", intent="OUT_OF_DOMAIN", operation=None)
    right = response(status=Status.OUT_OF_DOMAIN, intent=Intent.OUT_OF_DOMAIN)
    assert score(expected, right) == ({"status": True, "language": True, "exact": True}, None)
    missed = response(locations=[GANGTOK], variables=[Variable.TEMPERATURE])
    assert score(expected, missed)[1] == "ood_missed"


@pytest.mark.parametrize(
    "actual, category",
    [
        (response(status=Status.OUT_OF_DOMAIN, intent=Intent.OUT_OF_DOMAIN), "false_rejection"),
        (response(status=Status.NEEDS_CLARIFICATION, locations=[GANGTOK],
                  variables=[Variable.TEMPERATURE],
                  clarification=Clarification(reason="low_confidence",
                                              message_key="unclear_request")), "low_confidence"),
        (response(intent=Intent.GEOLOCATION_QUERY, locations=[GANGTOK],
                  variables=[Variable.TEMPERATURE]), "intent_confusion"),
        (response(status=Status.NEEDS_CLARIFICATION, locations=[GANGTOK],
                  warnings=["unresolved_env_variable:cold"],
                  clarification=Clarification(reason="missing_required_field",
                                              message_key="missing_variables")),
         "unknown_or_unresolved_entity"),
        (response(locations=[NAMCHI], variables=[Variable.TEMPERATURE]),
         "entity_missed_or_wrong"),
        (response(locations=[GANGTOK], variables=[Variable.TEMPERATURE],
                  time_period=TimePeriod(type=TimeType.CURRENT)), "time"),
        (response(operation=Operation.FORECAST, locations=[GANGTOK],
                  variables=[Variable.TEMPERATURE]), "operation"),
    ],
)
def test_first_cause_of_failure(actual, category):
    fields, found = score(WEATHER, actual)
    assert fields["exact"] is False
    assert found == category
    assert found in CATEGORIES


def test_earlier_cause_wins_over_later_ones():
    # Wrong intent AND wrong place AND wrong time: blamed on the intent.
    actual = response(intent=Intent.GEOLOCATION_QUERY, locations=[NAMCHI],
                      time_period=TimePeriod(type=TimeType.CURRENT))
    assert score(WEATHER, actual)[1] == "intent_confusion"


def test_aggregate_per_language():
    rows = [
        {"language": "en", "fields": {"exact": True, "intent": True}, "category": None},
        {"language": "en", "fields": {"exact": False, "intent": False},
         "category": "intent_confusion"},
        {"language": "ne", "fields": {"exact": False, "intent": True}, "category": "time"},
    ]
    report = aggregate(rows)
    assert report["all"]["n"] == 3
    assert report["all"]["fields"]["exact"] == pytest.approx(1 / 3)
    assert report["en"]["fields"]["intent"] == 0.5
    assert report["ne"]["errors"] == {"time": 1}
    assert "hi" not in report


# --- expectations derived from generated rows ---------------------------------------

@pytest.fixture(scope="module")
def test_rows():
    return read_jsonl(SETTINGS.paths.data_dir / "test" / "test.jsonl")


@pytest.fixture(scope="module")
def all_rows(test_rows):
    data_dir = SETTINGS.paths.data_dir
    return test_rows + read_jsonl(data_dir / "train.jsonl") + read_jsonl(data_dir / "val.jsonl")


def expected_for(rows, group_id):
    row = next(r for r in rows if r.group_id == group_id)
    return row, expected_from_record(row, ONTOLOGY, SETTINGS.decision)


def test_expected_fields_come_from_the_labels(test_rows):
    row = next(r for r in test_rows
               if r.intent not in (Intent.OUT_OF_DOMAIN, Intent.SCENARIO_ANALYSIS)
               and any(e.type.value == "LOCATION" for e in r.entities))
    expected = expected_from_record(row, ONTOLOGY, SETTINGS.decision)
    places = {e.normalized for e in row.entities if e.type.value == "LOCATION"}
    assert expected["locations"] == places
    assert expected["intent"] == row.intent.value
    assert expected["operation"] == row.operation.value


def test_out_of_domain_rows_expect_rejection(test_rows):
    row = next(r for r in test_rows if r.intent is Intent.OUT_OF_DOMAIN)
    expected = expected_from_record(row, ONTOLOGY, SETTINGS.decision)
    assert expected["status"] == "out_of_domain"
    assert "operation" not in expected


def test_expected_status_follows_the_validator(all_rows):
    # A fragment template has no location slot, so a clarification is expected.
    _, fragment = expected_for(all_rows, "weather.followup_fragment")
    assert fragment["status"] == "needs_clarification"
    # "Which areas have high flood risk?" needs no location.
    _, ranking = expected_for(all_rows, "risk.which_areas")
    assert ranking["status"] == "ok"
    # A trend template without a time expects the documented default.
    row, trend = expected_for(all_rows, "trend.show")
    assert trend["status"] == "ok"
    assert trend["time_period"] == {
        "type": "relative_past", "value": SETTINGS.decision.default_trend_years,
        "unit": TimeUnit.YEAR.value,
    }


def test_scenario_rows_compare_amount_and_direction_only(all_rows):
    row, expected = expected_for(all_rows, "scenario.increase_basic")
    assert set(expected["scenario_amount"]) == {"change", "unit", "direction"}
    assert expected["scenario_amount"]["direction"] == "increase"


def test_both_gold_sets_load_and_cover_every_status():
    for name in ("gold.yaml", "gold_v2.yaml"):
        records = load_gold(SETTINGS.paths.data_dir / "test" / name, ONTOLOGY)
        assert len(records) == 51
        assert {r.expected.status for r in records} == set(Status)


# --- real-user-style set and decision summary ---------------------------------------

def test_realistic_set_loads_and_is_not_in_the_generated_data():
    from backend.nlp.dataset.records import load_realistic

    data_dir = SETTINGS.paths.data_dir
    records = load_realistic(data_dir / "test" / "realistic.yaml", ONTOLOGY)
    assert len(records) == 58
    assert sum(r.scored for r in records) == 54
    assert {r.language for r in records} == set(Language)
    assert len({r.id for r in records}) == len(records)
    # Unsupported input is present but excluded from scoring.
    assert {r.phenomenon for r in records if not r.scored} == {
        "multi_intent", "ambiguous", "romanised"}

    generated = set()
    for name in ("train.jsonl", "val.jsonl", "test/test.jsonl"):
        generated |= {r.text for r in read_jsonl(data_dir / name)}
    gold = set()
    for name in ("gold.yaml", "gold_v2.yaml"):
        gold |= {g.text for g in load_gold(data_dir / "test" / name, ONTOLOGY)}
    for record in records:
        assert record.text not in generated, record.id
        assert record.text not in gold, record.id


def test_decision_summary_separates_rejection_asking_and_wrong_answers():
    from backend.nlp.evaluation.end_to_end import decision_summary

    def row(language, expected_status, actual_status, expected_intent="WEATHER_QUERY",
            actual_intent="WEATHER_QUERY", clarification=None):
        return {"language": language, "clarification": clarification,
                "expected": {"status": expected_status, "intent": expected_intent},
                "actual": {"status": actual_status, "intent": actual_intent}}

    rows = [
        row("en", "out_of_domain", "out_of_domain"),
        row("en", "out_of_domain", "ok"),                       # off-topic answered
        row("hi", "ok", "out_of_domain"),                       # real query rejected
        row("hi", "ok", "needs_clarification", clarification="low_confidence"),
        row("hi", "ok", "ok"),
        row("hi", "ok", "ok", actual_intent="COMPARISON"),      # answered, wrong intent
    ]
    summary = decision_summary(rows)
    assert summary["en"]["off_topic_rejected"] == 0.5
    assert summary["en"]["off_topic_answered"] == 0.5
    assert summary["en"]["real_rejected"] is None               # no real English rows
    assert summary["hi"]["real_rejected"] == 0.25
    assert summary["hi"]["real_asked_low_confidence"] == 0.25
    assert summary["hi"]["answered_with_wrong_intent"] == 0.5
    assert "ne" not in summary
