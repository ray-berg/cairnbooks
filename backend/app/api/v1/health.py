"""Health-check endpoint.

GET /api/v1/health  →  200 {"status": "ok"}

This endpoint is intentionally lightweight and has no database dependency so
that a load balancer / orchestrator can probe it before the DB is ready.
"""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(tags=["health"])


class HealthResponse(BaseModel):
    status: str


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Health check",
    description="Returns 200 OK when the application process is running.",
)
async def health_check() -> HealthResponse:
    return HealthResponse(status="ok")
