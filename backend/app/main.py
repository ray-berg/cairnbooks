"""CairnBooks — FastAPI application entrypoint.

This module defines the application factory (:func:`create_app`) and the
ASGI ``app`` object that Uvicorn / Gunicorn loads.

Startup / shutdown lifecycle
-----------------------------
Database engine initialisation and teardown are handled via the async
``lifespan`` context manager, which is the FastAPI-recommended approach
(replaces the deprecated ``on_event`` hooks).

Running locally
---------------
::

    uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

Or via the helper script defined in ``pyproject.toml``::

    python -m app.main
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1 import api_router
from app.config import settings
from app.db.session import close_db, init_db

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Lifespan
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan — startup and shutdown hooks."""
    # ---- startup ----
    logger.info("Starting CairnBooks API (env=%s)", settings.app_env)
    init_db()

    yield

    # ---- shutdown ----
    logger.info("Shutting down CairnBooks API")
    await close_db()


# ---------------------------------------------------------------------------
# Application factory
# ---------------------------------------------------------------------------

def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title="CairnBooks API",
        description=(
            "Open-source accounting and business-finance platform. "
            "API-first, double-entry bookkeeping, multi-tenant."
        ),
        version="0.1.0",
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        lifespan=lifespan,
    )

    # ------------------------------------------------------------------
    # Middleware
    # ------------------------------------------------------------------
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_hosts,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ------------------------------------------------------------------
    # Routers
    # ------------------------------------------------------------------
    app.include_router(api_router, prefix=settings.api_v1_prefix)

    return app


# ---------------------------------------------------------------------------
# ASGI entry point
# ---------------------------------------------------------------------------

app: FastAPI = create_app()


# ---------------------------------------------------------------------------
# Dev convenience — `python -m app.main`
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="debug" if settings.is_development else "info",
    )
