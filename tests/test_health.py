"""Tests for the /health endpoint."""

from starlette.testclient import TestClient

from cairnbooks.app import create_app


def test_health_returns_ok() -> None:
    """GET /health must return {status: ok} with HTTP 200."""
    client = TestClient(create_app())
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
