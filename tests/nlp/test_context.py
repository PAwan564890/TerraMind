import pytest

from backend.core import load_settings
from backend.nlp.context import (
    ContextResolver,
    ConversationManager,
    InMemorySessionStore,
    TurnParse,
    is_fragment,
)
from backend.nlp.context.dialogues import load_dialogues, run_dialogues
from backend.nlp.ontology import get_ontology
from backend.nlp.query.enums import Disaster, Intent, Language, TimeType, TimeUnit, Variable
from backend.nlp.query.schema import TimePeriod

SETTINGS = load_settings()
CONFIG = SETTINGS.context
ONTOLOGY = get_ontology()
GANGTOK = ONTOLOGY.location_ref("loc:gangtok")
NAMCHI = ONTOLOGY.location_ref("loc:namchi")
FIVE_YEARS = TimePeriod(type=TimeType.RELATIVE_PAST, value=5, unit=TimeUnit.YEAR)


def turn(intent=Intent.WEATHER_QUERY, language=Language.EN, **slots):
    return TurnParse(text="x", language=language, intent=intent, **slots)


def spans_of(text, *entities):
    return [(text.index(e), text.index(e) + len(e)) for e in entities]


# --- fragment detection ----------------------------------------------------------

@pytest.mark.parametrize(
    "text, entities",
    [
        ("What about rainfall?", ["rainfall"]),
        ("And the temperature?", ["temperature"]),
        ("Gangtok", ["Gangtok"]),
        ("What about tomorrow?", ["tomorrow"]),
        ("rainfall in Gangtok", ["rainfall", "Gangtok"]),
        ("और बारिश?", ["बारिश"]),
        ("तापमान के बारे में क्या?", ["तापमान"]),
        ("मंगन में", ["मंगन"]),
        ("अनि वर्षा?", ["वर्षा"]),
        ("नाम्चीमा नि?", ["नाम्ची"]),
        ("गान्तोकमा?", ["गान्तोक"]),
    ],
)
def test_entity_only_queries_are_fragments(text, entities):
    assert is_fragment(text, spans_of(text, *entities)) is True


@pytest.mark.parametrize(
    "text, entities",
    [
        ("What is the temperature in Gangtok?", ["temperature", "Gangtok"]),
        ("Show the rainfall trend in Gangtok", ["rainfall", "Gangtok"]),
        ("Compare rainfall in Gangtok and Namchi", ["rainfall", "Gangtok", "Namchi"]),
        ("भोलिको अवस्था कस्तो हुन्छ?", ["भोलि"]),
        ("गंगटोक में बारिश का रुझान दिखाओ", ["गंगटोक", "बारिश"]),
        ("Why is vegetation declining?", ["vegetation"]),
    ],
)
def test_queries_with_their_own_meaning_are_not_fragments(text, entities):
    assert is_fragment(text, spans_of(text, *entities)) is False


def test_no_entity_means_no_fragment():
    assert is_fragment("What about it?", []) is False


# --- the test dialogues ------------------------------------------------------------

def test_all_dialogues_resolve_as_expected():
    dialogues = load_dialogues(SETTINGS.paths.data_dir / "test" / "dialogues.yaml")
    report = run_dialogues(dialogues, ONTOLOGY, CONFIG)
    assert report["failures"] == []
    assert report["dialogues"] >= 18


# --- rules not covered by the dialogues ----------------------------------------------

def test_without_a_session_nothing_is_remembered():
    manager = ConversationManager(CONFIG)
    manager.process(None, turn(locations=[GANGTOK], variables=[Variable.TEMPERATURE]))
    resolved = manager.process(None, turn(variables=[Variable.HUMIDITY], is_fragment=True))
    assert resolved.locations == []
    assert resolved.context_used == []


def test_sessions_are_independent():
    manager = ConversationManager(CONFIG)
    manager.process("a", turn(locations=[GANGTOK], variables=[Variable.TEMPERATURE]), now=0)
    manager.process("b", turn(locations=[NAMCHI], variables=[Variable.TEMPERATURE]), now=0)
    resolved = manager.process("a", turn(variables=[Variable.HUMIDITY], is_fragment=True), now=1)
    assert resolved.locations == [GANGTOK]


def test_a_slot_expires_after_too_many_turns():
    manager = ConversationManager(CONFIG)
    manager.process("s", turn(locations=[GANGTOK], variables=[Variable.TEMPERATURE]), now=0)
    # Follow-ups keep changing the variable but never restate the place.
    for i in range(CONFIG.max_slot_age_turns):
        resolved = manager.process("s", turn(variables=[Variable.HUMIDITY], is_fragment=True),
                                   now=i)
        assert resolved.locations == [GANGTOK]  # still within the limit
    resolved = manager.process("s", turn(variables=[Variable.HUMIDITY], is_fragment=True), now=9)
    assert resolved.locations == []
    assert "locations" not in resolved.context_used


def test_restating_a_slot_resets_its_age():
    manager = ConversationManager(CONFIG)
    for i in range(CONFIG.max_slot_age_turns * 2):
        manager.process("s", turn(locations=[GANGTOK], variables=[Variable.TEMPERATURE]), now=i)
    resolved = manager.process("s", turn(variables=[Variable.HUMIDITY], is_fragment=True), now=99)
    assert resolved.locations == [GANGTOK]


def test_conversation_is_forgotten_after_idle_time():
    manager = ConversationManager(CONFIG)
    manager.process("s", turn(locations=[GANGTOK], variables=[Variable.TEMPERATURE]), now=0)
    late = CONFIG.max_idle_seconds + 1
    resolved = manager.process("s", turn(variables=[Variable.HUMIDITY], is_fragment=True),
                               now=late)
    assert resolved.locations == []


def test_store_drops_the_least_recently_used_session():
    config = CONFIG.model_copy(update={"max_sessions": 2})
    store = InMemorySessionStore(config)
    manager = ConversationManager(config, store)
    for session in ("a", "b"):
        manager.process(session, turn(locations=[GANGTOK]), now=0)
    manager.process("a", turn(locations=[GANGTOK]), now=1)   # "a" is now the most recent
    manager.process("c", turn(locations=[GANGTOK]), now=2)   # evicts "b"
    assert len(store) == 2
    assert store.get("b", now=2) is None
    assert store.get("a", now=2) is not None


def test_previous_language_is_available_for_detection_fallback():
    manager = ConversationManager(CONFIG)
    assert manager.language_of("s", now=0) is None
    assert manager.language_of(None) is None
    manager.process("s", turn(language=Language.NE, locations=[GANGTOK]), now=0)
    assert manager.language_of("s", now=1) is Language.NE


def test_stored_state_is_not_mutated_by_a_later_turn():
    resolver = ContextResolver(CONFIG)
    first = turn(locations=[GANGTOK], variables=[Variable.TEMPERATURE])
    state = resolver.update(None, first, resolver.resolve(first, None), now=0)
    snapshot = state.model_copy(deep=True)
    second = turn(locations=[NAMCHI], variables=[Variable.HUMIDITY])
    resolver.update(state, second, resolver.resolve(second, state), now=1)
    assert state == snapshot


def test_explicit_slots_always_win_over_context():
    manager = ConversationManager(CONFIG)
    manager.process("s", turn(Intent.CLIMATE_TREND, locations=[GANGTOK],
                              variables=[Variable.PRECIPITATION], time_period=FIVE_YEARS), now=0)
    resolved = manager.process("s", turn(Intent.DISASTER_RISK, locations=[NAMCHI],
                                         disasters=[Disaster.FLOOD]), now=1)
    assert resolved.locations == [NAMCHI]
    assert resolved.variables == []
    assert resolved.time_period is None
    assert resolved.context_used == []


def test_complete_risk_question_does_not_inherit_a_location():
    # "Which areas have high landslide risk?" asks about everywhere; the
    # place from an earlier question must not narrow it.
    manager = ConversationManager(CONFIG)
    manager.process("s", turn(locations=[GANGTOK], variables=[Variable.TEMPERATURE]), now=0)
    resolved = manager.process("s", turn(Intent.DISASTER_RISK, disasters=[Disaster.LANDSLIDE]),
                               now=1)
    assert resolved.locations == []
