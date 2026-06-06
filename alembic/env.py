"""Alembic environment for CairnBooks.

Uses the SQLAlchemy asyncpg engine (matching the application runtime) via the
standard asyncio bridge so the same ORM models and connection pool settings are
shared between the app and migrations.

Running migrations
------------------
From the repository root (where ``alembic.ini`` lives):

    # Apply all pending migrations to the database
    alembic upgrade head

    # Roll back one migration
    alembic downgrade -1

    # Show current applied revision
    alembic current

    # Generate an empty migration stub
    alembic revision -m "describe_change_here"

    # Auto-generate a migration from ORM model changes
    alembic revision --autogenerate -m "describe_change_here"

Environment variables
---------------------
DATABASE_URL
    Full SQLAlchemy URL, e.g.
    ``postgresql+asyncpg://cairnbooks:cairnbooks@db:5432/cairnbooks``.
    Overrides the ``sqlalchemy.url`` value in ``alembic.ini``.
"""

from __future__ import annotations

import asyncio
import os
from logging.config import fileConfig

from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from alembic import context

# ---------------------------------------------------------------------------
# Alembic Config object — provides access to the alembic.ini values
# ---------------------------------------------------------------------------
config = context.config

# Configure Python logging from the [loggers]/[handlers]/[formatters] sections
# in alembic.ini.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# ---------------------------------------------------------------------------
# Override sqlalchemy.url with DATABASE_URL environment variable when present.
# This is the primary mechanism used by Docker Compose and CI/CD.
# ---------------------------------------------------------------------------
_db_url = os.environ.get("DATABASE_URL")
if _db_url:
    config.set_main_option("sqlalchemy.url", _db_url)

# ---------------------------------------------------------------------------
# Import the shared DeclarativeBase so Alembic autogenerate can detect schema
# changes from ORM models.  All domain model modules must be imported
# (directly or transitively) before target_metadata is read.
# ---------------------------------------------------------------------------
from cairnbooks.db import Base  # noqa: E402

# As domain model modules are added, import them here so autogenerate picks up
# their table definitions.  For example:
#
#   from cairnbooks.domain.accounts import models  # noqa: F401
#   from cairnbooks.domain.ledger import models    # noqa: F401

target_metadata = Base.metadata


# ---------------------------------------------------------------------------
# Offline mode — emit SQL to stdout without a live database connection
# ---------------------------------------------------------------------------
def run_migrations_offline() -> None:
    """Generate SQL migration script without connecting to the database.

    Useful for reviewing changes before applying them, or for DBAs who apply
    SQL scripts manually.
    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


# ---------------------------------------------------------------------------
# Online mode — connect to the database and apply migrations
# ---------------------------------------------------------------------------
def do_run_migrations(connection: Connection) -> None:
    """Execute migrations within a synchronous connection context."""
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """Create an async engine and run migrations via the asyncio bridge."""
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


def run_migrations_online() -> None:
    """Entry point for online (connected) migration execution."""
    asyncio.run(run_async_migrations())


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
