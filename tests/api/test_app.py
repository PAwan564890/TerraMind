"""API tests. The pipeline uses the stand-in classifier and NER from the
pipeline tests, so no trained model is needed."""

import logging

import pytest
from fastapi.testclient import TestClient

from backend.api.app import create_app
from backend.core import load_settings
from backend.nlp.context import ConversationManager
from backend.nlp.normalization import EntityNormalizer
from backend.nlp.ontology import get_ontology
from backend.nlp.pipeline import NlpPipeline
from backend.nlp.query.schema import AnalyzeResponse
from tests.nlp.test_pipeline import DictionaryRecognizer, KeywordClassifier, detector  # noqa: F401

SETTINGS = load_settings()
ONTOLOGY = get_ontology()


@pytest.fixture
def client(detector):  # noqa: F811
    pipeline = NlpPipeline(
        settings=SETTINGS, ontology=ONTOLOGY, detector=detector,
        classifier=KeywordClassifier(), recognizer=DictionaryRecognizer(),
        normalizer=EntityNormalizer(ONTOLOGY, SETTINGS.normalization),
        conversations=ConversationManager(SETTINGS.context),
    )
    with TestClient(create_app(pipeline)) as test_client:
        yield test_client


def post(client, **body):
    return client.post("/nlp/analyze", json=body)


def test_health(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "models_loaded": True, "detail": None}


def test_analyze_returns_the_documented_contract(client):
    response = post(client, query="गंगटोक में बारिश का रुझान क्या है?")
    assert response.status_code == 200
    data = response.json()
    assert set(data) == {"language", "intent", "entities", "structured_query", "status",
                         "clarification", "warnings", "needs_clarification"}
    assert data["language"]["code"] == "hi"
    assert data["intent"]["label"] == "CLIMATE_TREND"
    assert data["status"] == "ok"
    assert data["needs_clarification"] is False
    assert [(e["text"], e["type"], e["normalized"]) for e in data["entities"]] == [
        ("गंगटोक", "LOCATION", "loc:gangtok"),
        ("बारिश", "ENV_VARIABLE", "PRECIPITATION"),
    ]
    query = data["structured_query"]
    assert query["schema_version"] == "1.0"
    assert query["operation"] == "TREND"
    assert query["locations"][0]["id"] == "loc:gangtok"
    assert query["variables"] == ["PRECIPITATION"]
    # The response validates against the schema it claims to follow.
    AnalyzeResponse.model_validate(data)


def test_clarification_is_a_200(client):
    response = post(client, query="What is the temperature?")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "needs_clarification"
    assert data["needs_clarification"] is True
    assert data["clarification"]["message_key"] == "missing_locations"


def test_out_of_domain_is_a_200(client):
    response = post(client, query="Who won yesterday's cricket match?")
    assert response.status_code == 200
    assert response.json()["status"] == "out_of_domain"
    assert response.json()["structured_query"] is None


def test_session_carries_context_between_requests(client):
    post(client, query="What is the temperature in Gangtok?", session_id="abc-123")
    followup = post(client, query="और बारिश?", session_id="abc-123").json()
    assert followup["structured_query"]["locations"][0]["id"] == "loc:gangtok"
    assert sorted(followup["structured_query"]["context_used"]) == ["intent", "locations"]
    # A different session knows nothing about it.
    other = post(client, query="और बारिश?", session_id="someone-else").json()
    assert other["structured_query"]["locations"] == []


def test_without_session_id_there_is_no_memory(client):
    post(client, query="What is the temperature in Gangtok?")
    assert post(client, query="What about rainfall?").json()["status"] == "needs_clarification"


@pytest.mark.parametrize(
    "body",
    [
        {},                                             # no query
        {"query": ""},                                  # empty
        {"query": 123},                                 # wrong type
        {"query": "rain", "unexpected": True},          # unknown field
        {"query": "rain", "session_id": ""},            # empty session id
        {"query": "rain", "session_id": "has spaces"},  # illegal characters
        {"query": "rain", "session_id": "x" * 65},      # too long
        {"query": "x" * 4001},                          # over the raw cap
    ],
)
def test_malformed_requests_are_422(client, body):
    assert client.post("/nlp/analyze", json=body).status_code == 422


@pytest.mark.parametrize(
    "query, code",
    [
        ("   \n\t ", "empty"),
        ("???", "no_content"),
        ("rain " * 200, "too_long"),
    ],
)
def test_unusable_queries_are_422_with_a_code(client, query, code):
    response = post(client, query=query)
    assert response.status_code == 422
    assert response.json()["detail"]["code"] == code


def test_not_json_is_422(client):
    response = client.post("/nlp/analyze", content="not json",
                           headers={"Content-Type": "application/json"})
    assert response.status_code == 422


def test_wrong_method_and_unknown_path(client):
    assert client.get("/nlp/analyze").status_code == 405
    assert client.get("/nope").status_code == 404


def test_query_text_is_not_logged_at_info_level(client, caplog):
    secret = "What is the rainfall in Gangtok near my house at 12 Example Road?"
    with caplog.at_level(logging.INFO, logger="terramind.api"):
        post(client, query=secret)
    messages = [record.getMessage() for record in caplog.records]
    assert any("status=" in message for message in messages)
    assert not any("Example Road" in message for message in messages)


def test_service_without_models_reports_503(monkeypatch):
    def broken(_settings):
        raise FileNotFoundError("models/intent/dev/summary.json not found")

    monkeypatch.setattr(NlpPipeline, "from_settings", staticmethod(broken))
    with TestClient(create_app()) as bare:
        health = bare.get("/health")
        assert health.status_code == 200
        assert health.json()["models_loaded"] is False
        assert "summary.json" in health.json()["detail"]
        response = bare.post("/nlp/analyze", json={"query": "rain in Gangtok"})
        assert response.status_code == 503
        assert response.json()["detail"]["code"] == "models_not_loaded"
