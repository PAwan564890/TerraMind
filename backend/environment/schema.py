"""Response contract: provenance is mandatory; missing values remain null."""
from datetime import date, datetime
from typing import Literal
from pydantic import BaseModel, Field
from backend.nlp.query.schema import StructuredQuery


class DailyRow(BaseModel):
    date: date
    temperature_mean_c: float | None = None
    temperature_min_c: float | None = None
    temperature_max_c: float | None = None
    precipitation_mm: float | None = None
    rainfall_mm: float | None = None


class WeatherResult(BaseModel):
    location_id: str
    location_name: str
    requested_latitude: float
    requested_longitude: float
    grid_latitude: float
    grid_longitude: float
    start: date
    end: date
    timezone: str = 'Asia/Kolkata'
    data_kind: Literal['reanalysis', 'weather_model', 'illustrative_sample']
    source: str
    source_url: str
    attribution: str
    license_url: str = 'https://creativecommons.org/licenses/by/4.0/'
    retrieved_at: datetime
    current: dict | None = None
    daily: list[DailyRow]
    summary: dict
    warnings: list[str] = Field(default_factory=list)


class EnvironmentResponse(BaseModel):
    status: Literal['ok', 'needs_clarification', 'unavailable']
    message: str | None = None
    query: StructuredQuery
    results: list[WeatherResult] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
