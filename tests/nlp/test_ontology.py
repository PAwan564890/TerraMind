import shutil

import pytest

from backend.core import load_settings
from backend.nlp.ontology import OntologyError, get_ontology, load_ontology, normalize_alias
from backend.nlp.query.enums import Disaster, LocationType, RiskTarget, Variable

ONTOLOGY_DIR = load_settings().paths.ontology_dir


@pytest.fixture
def ontology():
    return get_ontology()


@pytest.fixture
def ontology_copy(tmp_path):
    """A writable copy of the real ontology, for tests that break it on purpose."""
    target = tmp_path / "ontology"
    shutil.copytree(ONTOLOGY_DIR, target)
    return target


def test_every_enum_member_has_an_entry(ontology):
    assert set(ontology.variables) == set(Variable)
    assert set(ontology.disasters) == set(Disaster)


@pytest.mark.parametrize("text", ["rain", "Rainfall", "precipitation", "बारिश", "वर्षा", "झरी"])
def test_precipitation_aliases_in_three_languages(ontology, text):
    assert ontology.lookup_variable(text) is Variable.PRECIPITATION


@pytest.mark.parametrize("text", ["Gangtok", "gangtok", "गंगटोक", "गान्तोक"])
def test_gangtok_spellings_resolve_to_one_id(ontology, text):
    ref = ontology.lookup_location(text)
    assert ref.id == "loc:gangtok"
    assert ref.name == "Gangtok"
    assert ref.type is LocationType.TOWN
    assert ref.parent == "loc:gangtok_district"


def test_old_district_name_resolves_to_renamed_district(ontology):
    assert ontology.lookup_location("North Sikkim").id == "loc:mangan_district"
    assert ontology.lookup_location("उत्तर सिक्किम").id == "loc:mangan_district"


def test_town_and_district_with_same_name_are_distinct(ontology):
    assert ontology.lookup_location("Gangtok").type is LocationType.TOWN
    assert ontology.lookup_location("Gangtok district").type is LocationType.DISTRICT


def test_disaster_lookup_and_risk_target(ontology):
    assert ontology.lookup_disaster("बाढ़") is Disaster.FLOOD
    assert ontology.lookup_disaster("पहिरो") is Disaster.LANDSLIDE
    assert ontology.risk_target(Disaster.FLOOD) is RiskTarget.FLOOD_RISK
    assert ontology.risk_target(Disaster.EARTHQUAKE) is None


def test_lookups_do_not_cross_types(ontology):
    assert ontology.lookup_variable("flood") is None
    assert ontology.lookup_disaster("rainfall") is None
    assert ontology.lookup_location("rainfall") is None


def test_unknown_text_returns_none(ontology):
    assert ontology.lookup_variable("cricket") is None
    assert ontology.lookup_location("Paris") is None


def test_every_location_parent_exists(ontology):
    for loc_id, entry in ontology.locations.items():
        assert entry.parent is None or entry.parent in ontology.locations, loc_id


def test_normalize_alias_unifies_unicode_forms():
    # U+095D (precomposed DDHA+nukta) vs U+0922 U+093C (letter + combining nukta).
    assert normalize_alias("बाढ़") == normalize_alias("बाढ़")
    assert normalize_alias("  Wind   Speed ") == "wind speed"


def test_ambiguous_alias_is_rejected(ontology_copy):
    path = ontology_copy / "disasters.yaml"
    text = path.read_text(encoding="utf-8").replace("en: [flood, ", "en: [rain, flood, ")
    path.write_text(text, encoding="utf-8")
    with pytest.raises(OntologyError, match="Ambiguous"):
        load_ontology(ontology_copy)


def test_missing_enum_entry_is_rejected(ontology_copy):
    path = ontology_copy / "variables.yaml"
    text = path.read_text(encoding="utf-8").replace("SLOPE:", "SLOPEE:")
    path.write_text(text, encoding="utf-8")
    with pytest.raises(OntologyError, match="SLOPE"):
        load_ontology(ontology_copy)


def test_unknown_parent_is_rejected(ontology_copy):
    path = ontology_copy / "locations.yaml"
    text = path.read_text(encoding="utf-8").replace(
        "parent: loc:pakyong_district", "parent: loc:nowhere"
    )
    path.write_text(text, encoding="utf-8")
    with pytest.raises(OntologyError, match="unknown parent"):
        load_ontology(ontology_copy)


def test_missing_file_is_rejected(tmp_path):
    with pytest.raises(OntologyError, match="not found"):
        load_ontology(tmp_path)
