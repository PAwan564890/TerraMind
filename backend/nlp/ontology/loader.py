"""Loads the ontology YAML files, validates them, and builds alias indexes.

This phase supports EXACT alias lookup only. Suffix stripping (गान्तोकमा ->
गान्तोक), fuzzy matching and embedding fallback are added in Phase 7 on top
of the indexes built here.
"""

from functools import lru_cache
from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from backend.core import load_settings
from backend.nlp.preprocessing import lookup_key
from backend.nlp.query.enums import Disaster, Language, LocationType, RiskTarget, Variable
from backend.nlp.query.schema import LocationRef


class OntologyError(Exception):
    """Raised when an ontology file is missing, malformed or inconsistent."""


class _Entry(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class Aliases(_Entry):
    en: list[str] = Field(min_length=1)
    hi: list[str] = Field(min_length=1)
    ne: list[str] = Field(min_length=1)

    def by_language(self) -> dict[Language, list[str]]:
        return {Language.EN: self.en, Language.HI: self.hi, Language.NE: self.ne}

    def all(self) -> list[str]:
        return [*self.en, *self.hi, *self.ne]


class Descriptors(_Entry):
    """Words that imply a variable without naming it. Any language may be empty."""

    en: list[str] = Field(default_factory=list)
    hi: list[str] = Field(default_factory=list)
    ne: list[str] = Field(default_factory=list)

    def by_language(self) -> dict[Language, list[str]]:
        return {Language.EN: self.en, Language.HI: self.hi, Language.NE: self.ne}

    def all(self) -> list[str]:
        return [*self.en, *self.hi, *self.ne]


class VariableEntry(_Entry):
    unit: str
    aliases: Aliases
    descriptors: Descriptors = Descriptors()


class DisasterEntry(_Entry):
    risk_target: RiskTarget | None
    aliases: Aliases


class LocationEntry(_Entry):
    name: str
    type: LocationType
    parent: str | None
    aliases: Aliases


def normalize_alias(text: str) -> str:
    """Canonical form used as the lookup key (see preprocessing.lookup_key)."""
    return lookup_key(text)


def _read_yaml(path: Path) -> dict:
    if not path.is_file():
        raise OntologyError(f"Ontology file not found: {path}")
    with path.open(encoding="utf-8") as f:
        raw = yaml.safe_load(f)
    if not isinstance(raw, dict):
        raise OntologyError(f"Ontology file is empty or not a mapping: {path}")
    return raw


def _parse(path: Path, model: type[_Entry]) -> dict[str, _Entry]:
    try:
        return {key: model.model_validate(value) for key, value in _read_yaml(path).items()}
    except ValidationError as e:
        raise OntologyError(f"Invalid entry in {path}:\n{e}") from e


def _check_keys_match_enum(keys, enum, path: Path) -> None:
    expected = {member.value for member in enum}
    found = set(keys)
    if found != expected:
        raise OntologyError(
            f"{path.name} does not match {enum.__name__}: "
            f"missing {sorted(expected - found)}, unknown {sorted(found - expected)}"
        )


def _build_index(entries: dict[str, _Entry], index: dict[str, str], kind: str) -> None:
    """Add every alias of every entry to `index`, refusing ambiguous aliases."""
    for entry_id, entry in entries.items():
        descriptors = getattr(entry, "descriptors", None)
        for alias in [*entry.aliases.all(), *(descriptors.all() if descriptors else [])]:
            key = normalize_alias(alias)
            owner = index.setdefault(key, entry_id)
            if owner != entry_id:
                raise OntologyError(
                    f"Ambiguous {kind} alias '{alias}': used by both {owner} and {entry_id}"
                )


class Ontology:
    """Validated ontology with exact-match lookup."""

    def __init__(
        self,
        variables: dict[str, VariableEntry],
        disasters: dict[str, DisasterEntry],
        locations: dict[str, LocationEntry],
    ) -> None:
        self.variables = {Variable(k): v for k, v in variables.items()}
        self.disasters = {Disaster(k): v for k, v in disasters.items()}
        self.locations = locations

        for loc_id, entry in locations.items():
            if entry.parent is not None and entry.parent not in locations:
                raise OntologyError(f"{loc_id} has unknown parent {entry.parent}")

        # Variables and disasters share one index: a word must not mean both.
        self._concepts: dict[str, str] = {}
        _build_index(variables, self._concepts, "concept")
        _build_index(disasters, self._concepts, "concept")
        self._locations: dict[str, str] = {}
        _build_index(locations, self._locations, "location")

    @property
    def concept_index(self) -> dict[str, str]:
        """Lookup key -> variable or disaster ID, for every alias."""
        return self._concepts

    @property
    def location_index(self) -> dict[str, str]:
        """Lookup key -> location ID, for every alias."""
        return self._locations

    def lookup_variable(self, text: str) -> Variable | None:
        found = self._concepts.get(normalize_alias(text))
        return Variable(found) if found in Variable else None

    def lookup_disaster(self, text: str) -> Disaster | None:
        found = self._concepts.get(normalize_alias(text))
        return Disaster(found) if found in Disaster else None

    def lookup_location(self, text: str) -> LocationRef | None:
        loc_id = self._locations.get(normalize_alias(text))
        return self.location_ref(loc_id) if loc_id else None

    def location_ref(self, loc_id: str) -> LocationRef:
        entry = self.locations[loc_id]
        return LocationRef(id=loc_id, name=entry.name, type=entry.type, parent=entry.parent)

    def risk_target(self, disaster: Disaster) -> RiskTarget | None:
        return self.disasters[disaster].risk_target


def load_ontology(ontology_dir: Path) -> Ontology:
    """Load and validate the three ontology files from a directory."""
    var_path = ontology_dir / "variables.yaml"
    dis_path = ontology_dir / "disasters.yaml"
    loc_path = ontology_dir / "locations.yaml"

    variables = _parse(var_path, VariableEntry)
    disasters = _parse(dis_path, DisasterEntry)
    locations = _parse(loc_path, LocationEntry)

    _check_keys_match_enum(variables, Variable, var_path)
    _check_keys_match_enum(disasters, Disaster, dis_path)
    for loc_id in locations:
        if not loc_id.startswith("loc:"):
            raise OntologyError(f"Location id must start with 'loc:': {loc_id}")

    return Ontology(variables, disasters, locations)


@lru_cache(maxsize=1)
def get_ontology() -> Ontology:
    """The project ontology, loaded once per process from the configured path."""
    return load_ontology(load_settings().paths.ontology_dir)
