"""Explicit bounded routing. It never fabricates or replaces trained predictions."""
import re
from types import SimpleNamespace
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field
from backend.genai.facts import KEYS, compile_facts
from backend.genai.questions import select_facts
from backend.environment.registry import active_towns
from backend.environment.measurements import enabled as measurements_enabled
from backend.presentation.knowledge import Knowledge, knowledge_answer, key_of


class RouteBody(BaseModel):
    model_config = ConfigDict(extra='forbid')
    question: str = Field(min_length=1,max_length=4000)
    language: Literal['auto','en','hi','ne'] = 'auto'
    session_id: str = Field(min_length=1,max_length=64,pattern=r'^[A-Za-z0-9_-]+$')
    context_id: str | None = Field(default=None,min_length=32,max_length=64,pattern=r'^[A-Za-z0-9_-]+$')


class RouteResponse(BaseModel):
    category: Literal['environment','general_knowledge','contextual','unsupported','clarification']
    message: str
    knowledge: Knowledge | None = None


def route_question(body, contexts):
    knowledge = knowledge_answer(body.question,body.language)
    if knowledge:
        return RouteResponse(category='general_knowledge',message=knowledge.label,knowledge=knowledge)
    key = key_of(body.question)
    # This catalogue identifies supported formulations without supplying values.
    if select_facts(body.question,[SimpleNamespace(metric=m) for m in KEYS]):
        context = contexts.get(body.context_id,body.session_id) if body.context_id else None
        if context is None:
            return RouteResponse(category='clarification',message='Stored context is missing, expired or replaced. Submit a new environmental query with a town, variable and period.')
        facts,_ = compile_facts(context)
        if not select_facts(body.question,facts):
            return RouteResponse(category='unsupported',message='This session lacks the requested metric or complete, comparable town coverage. Submit a new supported environmental query.')
        return RouteResponse(category='contextual',message='Use the existing validated environmental session; no new retrieval.')
    if re.search(r'\b(?:predict|exact time|next|tomorrow).*\b(?:earthquake|landslide)\b',key):
        return RouteResponse(category='unsupported',message='TerraMind cannot predict earthquake or landslide timing. It supports descriptive temperature and rainfall results, not hazard forecasts.')
    blocked = [name for name in ('gyalshing','pakyong','rangpo','singtam','ravangla','pelling','jorethang','soreng','delhi','kathmandu') if 'loc:'+name not in active_towns()]
    if any(re.search(r'(?<![\wऀ-ॿ])'+name+r'(?![\wऀ-ॿ])',key) for name in blocked):
        return RouteResponse(category='unsupported',message='This location is not connected to verified retrieval. Choose supported town points from /locations; no district or state averages.')
    terms = r'wind direction|gusts?|pressure|snowfall|cloud cover|air quality|ndvi|soil moisture|हिमपात|दिशा'
    if not measurements_enabled(): terms += r'|humidity|wind(?: speed)?|आर्द्रता|हावा|हवा'
    if re.search(r'(?<![\wऀ-ॿ])(?:'+terms+r')(?![\wऀ-ॿ])',key):
        return RouteResponse(category='unsupported',message='That measurement is not connected. Choose air temperature, rainfall or total precipitation; no measurement is silently substituted.')
    if re.search(r'\b(?:gangtok|namchi|mangan)\s+or\s+(?:gangtok|namchi|mangan)\b',key):
        return RouteResponse(category='clarification',message='Choose one town, or explicitly ask to compare two towns for the same period.')
    return RouteResponse(category='environment',message='Continue through the selected trained NLP or explicitly labelled rule demonstration. Missing or unsupported fields must be clarified; no inference fallback.')
