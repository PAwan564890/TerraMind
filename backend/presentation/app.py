"""Add presentation routes without modifying the original production API.

Opt-in demo: TERRAMIND_DEMO=1 uvicorn backend.presentation.app:app --port 8000
The production /nlp/analyze never falls back to demo rules.
"""
import os
import threading
from typing import Literal
from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, Field
from backend.api.app import AnalyzeBody, create_app as create_nlp_app
from backend.environment.provider import LOCATIONS
from backend.environment.schema import EnvironmentResponse
from backend.environment.service import retrieve_query
from backend.nlp.preprocessing import InvalidQueryError
from backend.nlp.query.schema import AnalyzeResponse, StructuredQuery
from backend.presentation.demo import DemoAnalyzer
from backend.genai.context import ContextStore
from backend.genai.schema import Explanation, Language
from backend.genai.service import ExplanationService


class EnvironmentBody(BaseModel):
    model_config = ConfigDict(extra='forbid')
    query: StructuredQuery
    source_mode: Literal['live', 'snapshot'] = 'live'


class SessionBody(EnvironmentBody):
    session_id: str = Field(min_length=1, max_length=64, pattern=r'^[A-Za-z0-9_-]+$')
    language: Language = 'en'


class ExplainBody(BaseModel):
    model_config = ConfigDict(extra='forbid')
    session_id: str = Field(min_length=1, max_length=64, pattern=r'^[A-Za-z0-9_-]+$')
    context_id: str = Field(min_length=32, max_length=64, pattern=r'^[A-Za-z0-9_-]+$')
    language: Language = 'en'
    question: str = Field(min_length=1, max_length=500)


class SessionResponse(BaseModel):
    environment: EnvironmentResponse
    context_id: str | None
    explanation: Explanation


def create_app(pipeline=None, demo_enabled: bool | None = None, provider=None,
               explanation_service=None, context_store=None):
    enabled = os.environ.get('TERRAMIND_DEMO') == '1' if demo_enabled is None else demo_enabled
    app = create_nlp_app(pipeline)
    app.title = 'TerraMind Academic Prototype'
    demo = DemoAnalyzer() if enabled else None
    lock = threading.Lock()
    contexts = context_store if context_store is not None else ContextStore()
    genai = explanation_service if explanation_service is not None else ExplanationService()

    def explain_safely(context, language, question='Summarize these environmental results.'):
        try:
            return genai.explain(context, language, question)
        except Exception:  # Optional generation must never hide retrieved data.
            return Explanation(status='unavailable', language=language,
                message='AI explanation failed; environmental results remain available.')

    @app.get('/system')
    def system():
        return {'genai': {'configured': genai.client.config.configured,
                          'provider': genai.client.config.provider,
                          'generation': 'LLM-selected facts; validated multilingual templates',
                          'context_ttl_seconds': contexts.ttl},
                'demo_enabled': enabled, 'demo_endpoint': '/demo/analyze' if enabled else None,
                'production_endpoint': '/nlp/analyze', 'data_sources': ['live', 'snapshot'],
                'towns': {k: v[0] for k, v in LOCATIONS.items()},
                'limitations': ['Rule demo is not trained inference; demo confidence is unmeasured.',
                    'Weather data are model/reanalysis grid estimates, not station observations.',
                    'No disaster predictions, causal explanations or validated climate trends.',
                    'Three town points; no district or state averages. One process; no authentication.']}

    @app.post('/demo/analyze', response_model=AnalyzeResponse)
    def analyze_demo(body: AnalyzeBody):
        if demo is None:
            raise HTTPException(404, detail='Demo is disabled. Explicitly set TERRAMIND_DEMO=1 to enable.')
        try:
            with lock:
                return demo.analyze(body.query, body.session_id)
        except InvalidQueryError as error:
            raise HTTPException(422, detail={'code': error.code, 'message': str(error)}) from error

    @app.post('/environment/query', response_model=EnvironmentResponse)
    def environment(body: EnvironmentBody):
        return retrieve_query(body.query, source_mode=body.source_mode, provider=provider)

    @app.post('/environment/session', response_model=SessionResponse)
    def environment_session(body: SessionBody):
        environment = retrieve_query(body.query, source_mode=body.source_mode, provider=provider)
        token = contexts.save(body.session_id, environment, body.source_mode)
        explanation = explain_safely(contexts.get(token, body.session_id) if token else None, body.language)
        return SessionResponse(environment=environment, context_id=token, explanation=explanation)

    @app.post('/genai/explain', response_model=Explanation)
    def explain(body: ExplainBody):
        return explain_safely(contexts.get(body.context_id, body.session_id), body.language, body.question)

    return app


app = create_app()
