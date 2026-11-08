"""HTTP API for the NLP subsystem.

Run from the project root:
    uvicorn backend.api.app:app --port 8000

Endpoints:
    POST /nlp/analyze   query in, structured query out
    GET  /health        is the service up, and are the models loaded?

Status codes:
    200  the query was analysed. This includes `needs_clarification` and
         `out_of_domain`: those are valid results, not errors.
    422  the request itself is unusable (missing field, empty or oversized query)
    503  the models are not loaded
"""

import logging
import threading
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field

from backend.core import load_settings, setup_logging
from backend.nlp.pipeline import NlpPipeline
from backend.nlp.preprocessing import InvalidQueryError
from backend.nlp.query.schema import AnalyzeResponse

log = logging.getLogger("terramind.api")

# Hard cap on the raw request, checked before any processing. The meaningful
# limit (input.max_query_chars) is applied after normalisation.
_MAX_RAW_CHARS = 4000


class AnalyzeBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query: str = Field(min_length=1, max_length=_MAX_RAW_CHARS)
    # Opaque conversation id chosen by the client. It carries no identity.
    session_id: str | None = Field(default=None, min_length=1, max_length=64,
                                   pattern=r"^[A-Za-z0-9_-]+$")


class Health(BaseModel):
    status: str
    models_loaded: bool
    detail: str | None = None


def create_app(pipeline: NlpPipeline | None = None) -> FastAPI:
    """Build the application.

    With no argument, the pipeline is loaded from the config when the server
    starts. Tests pass a ready-made pipeline so no model files are needed.
    """

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.pipeline = pipeline
        app.state.load_error = None
        if pipeline is None:
            setup_logging()
            try:
                # Models are loaded once here, not per request.
                app.state.pipeline = NlpPipeline.from_settings(load_settings())
                log.info("models loaded")
            except Exception as error:  # noqa: BLE001 - reported through /health
                # Start anyway, so /health can say what is missing.
                app.state.load_error = f"{type(error).__name__}: {error}"
                log.error("could not load models: %s", app.state.load_error)
        yield

    app = FastAPI(title="TerraMind NLP", version="0.1.0", lifespan=lifespan)
    # The conversation store is a plain dictionary and the models are not
    # built for concurrent calls; one query at a time keeps both safe.
    lock = threading.Lock()

    @app.get("/health", response_model=Health)
    def health(request: Request) -> Health:
        state = request.app.state
        if state.pipeline is not None:
            return Health(status="ok", models_loaded=True)
        return Health(status="degraded", models_loaded=False, detail=state.load_error)

    @app.post("/nlp/analyze", response_model=AnalyzeResponse)
    def analyze(body: AnalyzeBody, request: Request) -> AnalyzeResponse:
        active = request.app.state.pipeline
        if active is None:
            raise HTTPException(status_code=503, detail={
                "code": "models_not_loaded",
                "message": "The NLP models are not loaded. See GET /health.",
            })

        started = time.perf_counter()
        try:
            with lock:
                response = active.analyze(body.query, session_id=body.session_id)
        except InvalidQueryError as error:
            raise HTTPException(status_code=422, detail={
                "code": error.code, "message": str(error),
            }) from error

        # The query text is deliberately not logged: it is user input and may
        # contain anything. It appears only at DEBUG level, for development.
        log.info("analyze language=%s intent=%s status=%s ms=%.0f",
                 response.language.code.value, response.intent.label.value,
                 response.status.value, (time.perf_counter() - started) * 1000)
        log.debug("query=%r", body.query)
        return response

    return app


app = create_app()
