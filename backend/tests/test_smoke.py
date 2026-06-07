"""Smoke tests — verify the FastAPI app starts and the health endpoint responds."""

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_returns_ok() -> None:
    """The /health endpoint must return HTTP 200 with status 'ok'."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["service"] == "cairnbooks-api"


def test_openapi_schema_available() -> None:
    """The OpenAPI schema must be reachable (docs are generated correctly)."""
    response = client.get("/openapi.json")
    assert response.status_code == 200
    schema = response.json()
    assert schema["info"]["title"] == "CairnBooks API"
