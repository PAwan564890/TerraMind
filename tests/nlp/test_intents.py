from backend.nlp.query.enums import AnswerKind, Intent, Operation
from backend.nlp.query.intents import INTENT_PRECEDENCE, INTENT_SPECS, derive_answer_kind
from backend.nlp.query.schema import StructuredQuery


def test_every_in_domain_intent_has_a_spec():
    assert set(INTENT_SPECS) == set(Intent) - {Intent.OUT_OF_DOMAIN}


def test_default_operation_is_allowed():
    for intent, spec in INTENT_SPECS.items():
        assert spec.default_operation in spec.allowed_operations, intent


def test_required_fields_exist_on_the_schema():
    fields = set(StructuredQuery.model_fields)
    for intent, spec in INTENT_SPECS.items():
        for group in spec.required:
            assert group <= fields, intent


def test_precedence_lists_only_real_intents():
    assert INTENT_PRECEDENCE == (Intent.SCENARIO_ANALYSIS, Intent.COMPARISON)


def test_answer_kind_for_every_allowed_combination():
    for intent, spec in INTENT_SPECS.items():
        for operation in spec.allowed_operations:
            assert isinstance(derive_answer_kind(intent, operation), AnswerKind)


def test_answer_kind_distinguishes_the_four_scientific_kinds():
    assert derive_answer_kind(Intent.WEATHER_QUERY, Operation.LOOKUP) is AnswerKind.OBSERVATION
    assert derive_answer_kind(Intent.CLIMATE_TREND, Operation.TREND) is AnswerKind.ANALYSIS
    assert derive_answer_kind(Intent.WEATHER_QUERY, Operation.FORECAST) is AnswerKind.PREDICTION
    assert derive_answer_kind(Intent.SCENARIO_ANALYSIS, Operation.SCENARIO) is AnswerKind.SCENARIO
    # Risk is a model output even when the question sounds like a lookup.
    assert derive_answer_kind(Intent.DISASTER_RISK, Operation.LOOKUP) is AnswerKind.PREDICTION
