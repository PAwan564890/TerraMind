from datetime import date

import pytest

from backend.core import load_settings
from backend.nlp.normalization import EntityNormalizer, parse_change, parse_time
from backend.nlp.normalization.normalizer import stripped_variants
from backend.nlp.normalization.numbers import ascii_digits
from backend.nlp.ontology import get_ontology
from backend.nlp.query.enums import ChangeUnit, Disaster, EntityType, TimeType, TimeUnit, Variable

SETTINGS = load_settings()
NORMALIZER = EntityNormalizer(get_ontology(), SETTINGS.normalization)
LOCATION, VARIABLE, DISASTER = EntityType.LOCATION, EntityType.ENV_VARIABLE, EntityType.DISASTER


# --- locations, variables, disasters -----------------------------------------

@pytest.mark.parametrize("text", ["Gangtok", "gangtok", "गंगटोक", "गान्तोक"])
def test_exact_match(text):
    result = NORMALIZER.normalize(text, LOCATION)
    assert (result.canonical, result.method, result.confidence) == ("loc:gangtok", "exact", 1.0)
    assert result.value.name == "Gangtok"


@pytest.mark.parametrize(
    "text, expected",
    [
        ("गान्तोकमा", "loc:gangtok"),            # Nepali "in"
        ("गान्तोकको", "loc:gangtok"),            # Nepali "of"
        ("मङ्गनबाट", "loc:mangan"),              # Nepali "from"
        ("सोरेङ जिल्लाको", "loc:soreng_district"),
        ("गंगटोक में", "loc:gangtok"),           # Hindi postposition as a separate word
        ("Namchi's", "loc:namchi"),
        ("the Teesta river", "loc:teesta"),
        ("Gangtok?", "loc:gangtok"),
    ],
)
def test_endings_are_stripped(text, expected):
    result = NORMALIZER.normalize(text, LOCATION)
    assert (result.canonical, result.method) == (expected, "suffix")


def test_stripping_never_invents_a_match():
    # "नामची" ends in "ची", not in a case ending; nothing may be cut from it.
    assert NORMALIZER.normalize("नामची", LOCATION).method == "exact"
    assert stripped_variants("सिक्किम") == []


@pytest.mark.parametrize(
    "text, entity_type, expected",
    [
        ("Gangtokk", LOCATION, "loc:gangtok"),
        ("Gyalshng", LOCATION, "loc:gyalshing"),
        ("rainfal", VARIABLE, "PRECIPITATION"),
        ("temprature", VARIABLE, "TEMPERATURE"),
        ("landslde", DISASTER, "LANDSLIDE"),
    ],
)
def test_spelling_mistakes_are_matched_fuzzily(text, entity_type, expected):
    result = NORMALIZER.normalize(text, entity_type)
    assert (result.canonical, result.method) == (expected, "fuzzy")
    assert SETTINGS.normalization.fuzzy_threshold <= result.confidence < 1.0


@pytest.mark.parametrize("text", ["Paris", "Siliguri", "Namche", "Manang", "Lachin", "नाम्चे"])
def test_other_places_are_not_forced_onto_a_sikkim_place(text):
    result = NORMALIZER.normalize(text, LOCATION)
    assert result.resolved is False
    assert (result.canonical, result.method, result.confidence) == (None, "none", 0.0)


def test_short_strings_are_never_fuzzy_matched():
    assert NORMALIZER.normalize("ran", VARIABLE).resolved is False


def test_broken_ner_fragments_stay_unresolved():
    assert NORMALIZER.normalize("चेनमा", VARIABLE).resolved is False
    assert NORMALIZER.normalize("ला", LOCATION).resolved is False


def test_wrong_ner_type_between_variable_and_disaster_is_corrected():
    result = NORMALIZER.normalize("flood", VARIABLE)
    assert (result.type, result.value) == (DISASTER, Disaster.FLOOD)
    result = NORMALIZER.normalize("बारिश", DISASTER)
    assert (result.type, result.value) == (VARIABLE, Variable.PRECIPITATION)


def test_a_variable_word_is_not_resolved_as_a_location():
    assert NORMALIZER.normalize("rainfall", LOCATION).resolved is False


# --- time ---------------------------------------------------------------------

def period(text, context=""):
    parsed = parse_time(text, context, today=date(2026, 10, 5))
    return parsed.period if parsed else None


@pytest.mark.parametrize(
    "text, value, unit",
    [
        ("last five years", 5, TimeUnit.YEAR),
        ("past 10 years", 10, TimeUnit.YEAR),
        ("past ten years", 10, TimeUnit.YEAR),
        ("last decade", 10, TimeUnit.YEAR),
        ("last 3 months", 3, TimeUnit.MONTH),
        ("last year", 1, TimeUnit.YEAR),
        ("3 years ago", 3, TimeUnit.YEAR),
        ("yesterday", 1, TimeUnit.DAY),
        ("पिछले पांच सालों", 5, TimeUnit.YEAR),
        ("पिछले दस सालों में", 10, TimeUnit.YEAR),
        ("पिछले 30 दिनों", 30, TimeUnit.DAY),
        ("पिछले हफ्ते", 1, TimeUnit.WEEK),
        ("पिछले दशक", 10, TimeUnit.YEAR),
        ("पछिल्ला पाँच वर्ष", 5, TimeUnit.YEAR),
        ("पछिल्ला दस वर्षमा", 10, TimeUnit.YEAR),
        ("पछिल्ला १० वर्षको", 10, TimeUnit.YEAR),
        ("गत महिना", 1, TimeUnit.MONTH),
        ("हिजो", 1, TimeUnit.DAY),
    ],
)
def test_relative_past(text, value, unit):
    p = period(text)
    assert (p.type, p.value, p.unit) == (TimeType.RELATIVE_PAST, value, unit)


@pytest.mark.parametrize(
    "text, value, unit",
    [
        ("tomorrow", 1, TimeUnit.DAY),
        ("the day after tomorrow", 2, TimeUnit.DAY),
        ("next week", 1, TimeUnit.WEEK),
        ("next 3 days", 3, TimeUnit.DAY),
        ("अगले हफ्ते", 1, TimeUnit.WEEK),
        ("अगले तीन दिनों", 3, TimeUnit.DAY),
        ("भोलि", 1, TimeUnit.DAY),
        ("भोलिको", 1, TimeUnit.DAY),
        ("पर्सि", 2, TimeUnit.DAY),
        ("अर्को महिना", 1, TimeUnit.MONTH),
    ],
)
def test_relative_future(text, value, unit):
    p = period(text)
    assert (p.type, p.value, p.unit) == (TimeType.RELATIVE_FUTURE, value, unit)


@pytest.mark.parametrize(
    "text",
    ["today", "right now", "these days", "currently", "आज", "अभी", "आजकल", "इस समय",
     "अहिले", "आजभोलि", "हाल"],
)
def test_current(text):
    assert period(text).type is TimeType.CURRENT


@pytest.mark.parametrize(
    "text, start, end",
    [
        ("from 2015 to 2020", date(2015, 1, 1), date(2020, 12, 31)),
        ("between 2010 and 2020", date(2010, 1, 1), date(2020, 12, 31)),
        ("2015 through 2022", date(2015, 1, 1), date(2022, 12, 31)),
        ("2015-2020", date(2015, 1, 1), date(2020, 12, 31)),
        ("2015 से 2022 तक", date(2015, 1, 1), date(2022, 12, 31)),
        ("२०१० देखि २०२० सम्म", date(2010, 1, 1), date(2020, 12, 31)),
        ("in 2020", date(2020, 1, 1), date(2020, 12, 31)),
        ("since 2018", date(2018, 1, 1), date(2026, 10, 5)),
        ("2020 to 2015", date(2015, 1, 1), date(2020, 12, 31)),  # reversed years are reordered
    ],
)
def test_date_ranges(text, start, end):
    p = period(text)
    assert (p.type, p.start, p.end) == (TimeType.DATE_RANGE, start, end)


def test_hindi_kal_is_resolved_by_verb_tense():
    future = parse_time("कल", "कल नामची में बारिश होगी क्या?")
    assert (future.period.type, future.confidence) == (TimeType.RELATIVE_FUTURE, 1.0)
    past = parse_time("कल", "कल गंगटोक में कितनी बारिश हुई थी?")
    assert (past.period.type, past.confidence) == (TimeType.RELATIVE_PAST, 1.0)
    guess = parse_time("कल", "कल का मौसम")
    assert guess.period.type is TimeType.RELATIVE_FUTURE
    assert guess.confidence < 1.0


def test_kal_inside_another_word_is_not_tomorrow():
    assert period("आजकल").type is TimeType.CURRENT


def test_unknown_time_expression_returns_none():
    assert period("soonish") is None
    assert period("बारिश") is None


def test_devanagari_digits():
    assert ascii_digits("२०१५ देखि 2020") == "2015 देखि 2020"


# --- change -------------------------------------------------------------------

@pytest.mark.parametrize(
    "text, value, unit",
    [
        ("20%", 20, ChangeUnit.PERCENT),
        ("10 percent", 10, ChangeUnit.PERCENT),
        ("twenty percent", 20, ChangeUnit.PERCENT),
        ("15 फीसदी", 15, ChangeUnit.PERCENT),
        ("१० प्रतिशत", 10, ChangeUnit.PERCENT),
        ("20%ले", 20, ChangeUnit.PERCENT),
        ("2°C", 2, ChangeUnit.ABSOLUTE),
        ("1.5 degrees Celsius", 1.5, ChangeUnit.ABSOLUTE),
        ("3 डिग्रीले", 3, ChangeUnit.ABSOLUTE),
        ("२ डिग्री", 2, ChangeUnit.ABSOLUTE),
    ],
)
def test_change_values(text, value, unit):
    change = parse_change(text)
    assert (change.change, change.unit) == (value, unit)


@pytest.mark.parametrize("text", ["a lot", "20", "0%", "percent"])
def test_unparseable_change_returns_none(text):
    assert parse_change(text) is None


# --- through the normaliser ---------------------------------------------------

def test_time_and_change_canonical_strings():
    time = NORMALIZER.normalize("पछिल्ला पाँच वर्षको", EntityType.TIME)
    assert (time.canonical, time.method) == ("relative_past:5:year", "rule")
    assert NORMALIZER.normalize("from 2015 to 2020", EntityType.TIME).canonical == (
        "date_range:2015-01-01:2020-12-31"
    )
    assert NORMALIZER.normalize("today", EntityType.TIME).canonical == "current"
    change = NORMALIZER.normalize("20%", EntityType.CHANGE)
    assert (change.canonical, change.value.unit) == ("20:percent", ChangeUnit.PERCENT)
    assert NORMALIZER.normalize("1.5 degrees", EntityType.CHANGE).canonical == "1.5:absolute"


def test_unresolved_time_and_change():
    assert NORMALIZER.normalize("soonish", EntityType.TIME).resolved is False
    assert NORMALIZER.normalize("a lot", EntityType.CHANGE).resolved is False


# --- regressions: defects found on the second gold set (Phase 12) -----------------

def test_haal_inside_another_word_is_not_a_time():
    # "हालत" (condition) contains "हाल" (currently). A keyword must end at a
    # word end or a case ending.
    assert period("लाचुङमा वनस्पतिको हालत कस्तो छ?") is None
    assert period("कलकत्ता") is None            # contains "कल"
    # Case endings are still allowed after a keyword.
    assert period("भोलिको अवस्था").type is TimeType.RELATIVE_FUTURE
    assert period("हालसम्म").type is TimeType.CURRENT


def test_haal_means_currently_only_in_nepali():
    from backend.nlp.query.enums import Language

    hindi = "लाचुंग में वनस्पति का क्या हाल है?"       # "how is the vegetation"
    assert parse_time(hindi, hindi, language=Language.HI) is None
    nepali = "गान्तोकमा हाल तापक्रम कस्तो छ?"          # "currently"
    assert parse_time(nepali, nepali, language=Language.NE).period.type is TimeType.CURRENT
    # With no language given, every keyword applies (the documented default).
    assert parse_time("हाल").period.type is TimeType.CURRENT


def test_normaliser_passes_the_language_to_the_time_rules():
    from backend.nlp.query.enums import Language

    assert NORMALIZER.normalize("हाल", EntityType.TIME, language=Language.HI).resolved is False
    assert NORMALIZER.normalize("हाल", EntityType.TIME, language=Language.NE).canonical == "current"


# --- regressions: NER span drawn around more than one place ------------------------

@pytest.mark.parametrize(
    "span, expected",
    [
        ("मंगन नामची", ["loc:mangan", "loc:namchi"]),          # two names, no separator
        ("मङ्गन नाम्ची", ["loc:mangan", "loc:namchi"]),
        ("लाचेन वरपर", ["loc:lachen"]),                         # name + "around"
        ("पेलिङ वरपरका", ["loc:pelling"]),
        ("around Lachen", ["loc:lachen"]),
        ("Gangtok and Namchi", ["loc:gangtok", "loc:namchi"]),
        ("North Sikkim और South Sikkim", ["loc:mangan_district", "loc:namchi_district"]),
        ("नाम्चीमा र गान्तोकमा", ["loc:namchi", "loc:gangtok"]),  # endings stripped per part
    ],
)
def test_places_inside_one_span_are_recovered(span, expected):
    assert NORMALIZER.normalize(span, LOCATION).resolved is False   # whole span: no match
    parts = NORMALIZER.split_locations(span)
    assert [r.canonical for _, _, r in parts] == expected
    for start, end, resolution in parts:
        assert resolution.method in ("exact", "suffix")
        assert span[start:end].strip()


@pytest.mark.parametrize("span", ["Siliguri Gangtok", "Darjeeling and Gangtok", "Gangtok rn",
                                  "सिलीगुड़ी गंगटोक", "Paris", "Gangtokk Namchi"])
def test_a_span_with_an_unexplained_word_is_not_split(span):
    # Dropping the unknown part silently would answer a different question
    # from the one asked, so the whole span stays unresolved.
    assert NORMALIZER.split_locations(span) is None


def test_longest_place_name_wins_when_splitting():
    parts = NORMALIZER.split_locations("near Gangtok district")
    assert [r.canonical for _, _, r in parts] == ["loc:gangtok_district"]
