"""Tests for the health-check endpoint.

These tests use the ASGI test client from httpx/anyio and do NOT require a
running database — the health endpoint is intentionally dependency-free.
"""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.mark.anyio
async def test_health_returns_200() -> None:
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/api/v1/health")

    assert response.status_code == 200


@pytest.mark.anyio
async def test_health_returns_ok_status() -> None:
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/api/v1/health")

    data = response.json()
    assert data == {"status": "ok"}
