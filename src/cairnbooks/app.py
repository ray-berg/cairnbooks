"""FastAPI application factory for CairnBooks."""

from fastapi import FastAPI

from cairnbooks.api.health import router as health_router
from cairnbooks.api.item import router as item_router


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title="CairnBooks",
        description="Open-source double-entry accounting platform for small businesses",
        version="0.1.0",
    )

    app.include_router(health_router)
    app.include_router(item_router)

    return app


app = create_app()
