"""Closed vocabularies used across the NLP subsystem.

Every value a downstream tool can receive is listed here. Because these are
StrEnums, they serialise to plain strings in JSON ("PRECIPITATION") while
Python code gets autocompletion and typo protection.
"""

from enum import StrEnum


class Language(StrEnum):
    EN = "en"
    HI = "hi"
    NE = "ne"


class Intent(StrEnum):
    WEATHER_QUERY = "WEATHER_QUERY"
    CLIMATE_TREND = "CLIMATE_TREND"
    VEGETATION_ANALYSIS = "VEGETATION_ANALYSIS"
    DISASTER_RISK = "DISASTER_RISK"
    GEOLOCATION_QUERY = "GEOLOCATION_QUERY"
    COMPARISON = "COMPARISON"
    SCENARIO_ANALYSIS = "SCENARIO_ANALYSIS"
    GENERAL_ENVIRONMENT = "GENERAL_ENVIRONMENT"
    OUT_OF_DOMAIN = "OUT_OF_DOMAIN"


class Operation(StrEnum):
    """What to do with the data, independent of the topic."""

    LOOKUP = "LOOKUP"
    TREND = "TREND"
    COMPARE = "COMPARE"
    EXPLAIN = "EXPLAIN"
    RANK = "RANK"
    FORECAST = "FORECAST"
    SCENARIO = "SCENARIO"


class AnswerKind(StrEnum):
    """Scientific status of the expected answer."""

    OBSERVATION = "observation"
    ANALYSIS = "analysis"
    PREDICTION = "prediction"
    SCENARIO = "scenario"


class EntityType(StrEnum):
    """Labels the NER model predicts (BIO-tagged in Phase 6)."""

    LOCATION = "LOCATION"
    ENV_VARIABLE = "ENV_VARIABLE"
    DISASTER = "DISASTER"
    TIME = "TIME"
    CHANGE = "CHANGE"


class Variable(StrEnum):
    TEMPERATURE = "TEMPERATURE"
    PRECIPITATION = "PRECIPITATION"
    HUMIDITY = "HUMIDITY"
    WIND_SPEED = "WIND_SPEED"
    AIR_QUALITY = "AIR_QUALITY"
    NDVI = "NDVI"
    SOIL_MOISTURE = "SOIL_MOISTURE"
    LAND_COVER = "LAND_COVER"
    LAND_SURFACE_TEMPERATURE = "LAND_SURFACE_TEMPERATURE"
    ELEVATION = "ELEVATION"
    SLOPE = "SLOPE"


class Disaster(StrEnum):
    FLOOD = "FLOOD"
    LANDSLIDE = "LANDSLIDE"
    WILDFIRE = "WILDFIRE"
    EARTHQUAKE = "EARTHQUAKE"
    GLOF = "GLOF"
    CLOUDBURST = "CLOUDBURST"


class RiskTarget(StrEnum):
    FLOOD_RISK = "FLOOD_RISK"
    LANDSLIDE_RISK = "LANDSLIDE_RISK"
    WILDFIRE_RISK = "WILDFIRE_RISK"


class LocationType(StrEnum):
    STATE = "STATE"
    DISTRICT = "DISTRICT"
    TOWN = "TOWN"
    VILLAGE = "VILLAGE"
    RIVER = "RIVER"
    REGION = "REGION"


class TimeType(StrEnum):
    CURRENT = "current"
    RELATIVE_PAST = "relative_past"
    RELATIVE_FUTURE = "relative_future"
    DATE_RANGE = "date_range"


class TimeUnit(StrEnum):
    DAY = "day"
    WEEK = "week"
    MONTH = "month"
    YEAR = "year"


class ChangeUnit(StrEnum):
    PERCENT = "percent"
    ABSOLUTE = "absolute"


class Direction(StrEnum):
    INCREASE = "increase"
    DECREASE = "decrease"


class Status(StrEnum):
    """Routing decision for the orchestrator."""

    OK = "ok"
    NEEDS_CLARIFICATION = "needs_clarification"
    OUT_OF_DOMAIN = "out_of_domain"
