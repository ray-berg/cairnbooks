"""SQLAlchemy 2.0 async engine and session factory.

The async engine is created once at startup (via the lifespan hook in
:mod:`app.main`) and torn down at shutdown.  Individual request sessions are
managed through :func:`get_db`, a FastAPI dependency that yields a session and
auto-commits or rolls back depending on whether an exception was raised.

Multi-tenancy note
------------------
When tenant isolation is wired up, replace :class:`AsyncSession` with a
``TenantSession`` subclass that sets ``app.current_organization_id`` on every
execute call (see architecture doc §6.3).
"""

from __future__ import annotations

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.config import settings

# ---------------------------------------------------------------------------
# Engine — created at module import time; use init_db() to (re)connect.
# ---------------------------------------------------------------------------
_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def init_db() -> None:
    """Create the async engine and session factory.

    Call this once during application startup (e.g. inside the lifespan
    context manager in :mod:`app.main`).
    """
    global _engine, _session_factory

    _engine = create_async_engine(
        settings.database_url,
        echo=settings.is_development,  # SQL logging in dev
        pool_pre_ping=True,            # reconnect on stale connections
        pool_size=10,
        max_overflow=20,
    )
    _session_factory = async_sessionmaker(
        bind=_engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
        autocommit=False,
    )


async def close_db() -> None:
    """Dispose the engine.  Call during application shutdown."""
    global _engine
    if _engine is not None:
        await _engine.dispose()
        _engine = None


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency that yields an :class:`AsyncSession`.

    The session is committed on clean exit and rolled back on any exception.

    Example::

        @router.get("/accounts")
        async def list_accounts(db: AsyncSession = Depends(get_db)):
            ...
    """
    if _session_factory is None:
        raise RuntimeError(
            "Database not initialised.  "
            "Ensure init_db() is called during application startup."
        )
    async with _session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


# ---------------------------------------------------------------------------
# Declarative base — shared by all ORM model classes
# ---------------------------------------------------------------------------

class Base(DeclarativeBase):
    """Base class for all SQLAlchemy ORM models."""
