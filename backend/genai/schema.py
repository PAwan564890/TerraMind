"""Only typed grounded claims cross the trust boundary; free prose is forbidden."""
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, StrictBool, StrictStr

Language = Literal['en','hi','ne']


class StrictModel(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)


class Claim(StrictModel):
    fact_id: StrictStr
    value: StrictStr
    unit: Literal['°C','mm']
    location_ids: list[StrictStr] = Field(min_length=1, max_length=2)
    start: StrictStr
    end: StrictStr
    source_ids: list[StrictStr] = Field(min_length=1, max_length=2)


class Plan(StrictModel):
    language: Language
    answerable: StrictBool
    claims: list[Claim] = Field(max_length=12)


class Fact(Claim):
    metric: str
    location_names: list[str]
    coverage: str


class Source(StrictModel):
    id: str
    name: str
    url: str
    attribution: str
    data_kind: str
    retrieved_at: str
    source_mode: Literal['live','snapshot']


class Explanation(BaseModel):
    status: Literal['ok','disabled','unavailable','rejected','no_context','unsupported']
    message: str
    language: Language
    text: str | None = None
    claims: list[Fact] = Field(default_factory=list)
    sources: list[Source] = Field(default_factory=list)
    provider: str | None = None
    model: str | None = None
