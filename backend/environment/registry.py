"""Traceable vetted points; no runtime geocoding or client-uploaded coordinates."""
import json
import os
from collections.abc import Mapping
from pathlib import Path
from pydantic import BaseModel, ConfigDict, Field, model_validator


class Town(BaseModel):
    model_config = ConfigDict(extra='forbid',frozen=True)
    id: str = Field(pattern=r'^loc:[a-z_]+$')
    name: str
    latitude: float = Field(ge=26,le=29)
    longitude: float = Field(ge=87,le=90)
    country_code: str
    admin1: str
    admin2: str | None
    parent: str
    aliases: dict[str,list[str]]
    geonames_id: int = Field(gt=0)
    feature_code: str
    source_url: str
    attribution: str
    verified_at: str
    legacy: bool

    @model_validator(mode='after')
    def region(self):
        if self.country_code!='IN' or self.admin1!='Sikkim' or not self.feature_code.startswith('PPL'):
            raise ValueError('Registry entries must identify Sikkim populated places.')
        if not self.source_url.startswith('https://geocoding-api.open-meteo.com/v1/search?'):
            raise ValueError('Untrusted registry source')
        return self


TOWNS = tuple(Town.model_validate(row) for row in json.loads(Path(__file__).with_name('locations.json').read_text(encoding='utf-8')))
if len({t.id for t in TOWNS})!=len(TOWNS):
    raise ValueError('Duplicate registry IDs')


def extended_enabled():
    return os.environ.get('TERRAMIND_EXTENDED_LOCATIONS')=='1'


def active_towns():
    return {t.id:t for t in TOWNS if t.legacy or extended_enabled()}


class LocationMapping(Mapping):
    """Compatibility view for existing consumers of LOCATIONS tuples."""
    def __iter__(self):return iter(active_towns())
    def __len__(self):return len(active_towns())
    def __getitem__(self,key):
        t=active_towns()[key]
        return t.name,t.latitude,t.longitude


LOCATIONS = LocationMapping()
