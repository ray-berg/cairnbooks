"""SQLAlchemy 2.0 async engine, session factory, and FastAPI session dependency.

The async engine is initialised once at application startup (via the
``lifespan`` context manager in the main ASGI entry-point) and torn down at
shutdown.  Individual request-scoped sessions are obtained through
:func:`get_db`, a FastAPI dependency that yields an :class:`AsyncSession` and
automatically commits on clean exit or rolls back on any exception.

Usage
-----
Wire the lifespan in your FastAPI app::

    from contextlib import asynccontextmanager
    from fastapi import FastAPI
    from cairnbooks.db import init_db, close_db

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        init_db()
        yield
        await close_db()

    app = FastAPI(lifespan=lifespan)

Inject the session into route handlers::

    from fastapi import Depends
    from sqlalchemy.ext.asyncio import AsyncSession
    from cairnbooks.db import get_db

    @router.get("/accounts")
    async def list_accounts(db: AsyncSession = Depends(get_db)):
        ...
"""

from __future__ import annotations

import os
from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

# ---------------------------------------------------------------------------
# Database URL
# ---------------------------------------------------------------------------
# Reads DATABASE_URL from the environment; falls back to a local dev default.
# The URL must use the asyncpg driver:
#   postgresql+asyncpg://user:password@host:port/database
_DEFAULT_DATABASE_URL = "postgresql+asyncpg://cairnbooks:cairnbooks@localhost:5432/cairnbooks"
DATABASE_URL: str = os.environ.get("DATABASE_URL", _DEFAULT_DATABASE_URL)

# ---------------------------------------------------------------------------
# Engine and session factory — lazily created by init_db()
# ---------------------------------------------------------------------------
_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def init_db(database_url: str | None = None) -> None:
    """Create the async engine and session factory.

    Call once during application startup (inside the ASGI lifespan handler).

    Args:
        database_url: Override the URL for this call (e.g. in tests).  Defaults
            to the module-level :data:`DATABASE_URL`.
    """
    global _engine, _session_factory

    url = database_url or DATABASE_URL
    _engine = create_async_engine(
        url,
        echo=os.environ.get("ENV", "production") == "development",
        pool_pre_ping=True,  # reconnect on stale idle connections
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
    """Dispose the engine connection pool.

    Call during application shutdown (inside the ASGI lifespan handler).
    """
    global _engine
    if _engine is not None:
        await _engine.dispose()
        _engine = None


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency — yields a request-scoped :class:`AsyncSession`.

    The session is committed automatically on clean exit and rolled back if
    any exception propagates out of the route handler.

    Raises:
        RuntimeError: If :func:`init_db` has not been called yet.
    """
    if _session_factory is None:
        raise RuntimeError(
            "Database not initialised — call init_db() during application startup."
        )
    async with _session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


# ---------------------------------------------------------------------------
# Declarative base — all ORM model classes inherit from this
# ---------------------------------------------------------------------------


class Base(DeclarativeBase):
    """Shared declarative base for all CairnBooks ORM models.

    Import and subclass this in every domain model module so that Alembic
    autogenerate can detect schema changes::

        from cairnbooks.db import Base

        class Account(Base):
            __tablename__ = "accounts"
            ...
    """
