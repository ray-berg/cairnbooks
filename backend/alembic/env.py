"""Alembic environment for CairnBooks backend.

Uses SQLAlchemy's async engine (asyncpg) to match the application runtime.
The database URL is taken from the DATABASE_URL environment variable when set,
falling back to the value in alembic.ini for local development.

Running migrations
------------------
From the ``backend/`` directory:

    # Apply all pending migrations
    alembic upgrade head

    # Generate a new (empty) migration
    alembic revision -m "describe_change_here"

    # Auto-generate a migration from model changes
    alembic revision --autogenerate -m "describe_change_here"

    # Show current revision
    alembic current
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
# Alembic Config — provides access to alembic.ini values
# ---------------------------------------------------------------------------
config = context.config

# Set up Python logging as specified in alembic.ini
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# ---------------------------------------------------------------------------
# Override sqlalchemy.url from DATABASE_URL environment variable.
# This allows docker-compose and CI to pass in the real connection string
# without editing alembic.ini.
# ---------------------------------------------------------------------------
_db_url = os.environ.get("DATABASE_URL")
if _db_url:
    config.set_main_option("sqlalchemy.url", _db_url)

# ---------------------------------------------------------------------------
# Import the shared DeclarativeBase so autogenerate can detect schema changes.
# All ORM models must be imported (directly or transitively) before
# target_metadata is read by Alembic.
# ---------------------------------------------------------------------------
from app.db.session import Base  # noqa: E402

# Import domain model modules here as they are created so autogenerate picks
# them up.  For example:
#   from app.domain.accounts import models  # noqa: F401
#   from app.domain.users import models  # noqa: F401
from app.domain import company  # noqa: F401

target_metadata = Base.metadata


# ---------------------------------------------------------------------------
# Offline migrations (generate SQL without a live DB connection)
# ---------------------------------------------------------------------------
def run_migrations_offline() -> None:
    """Emit migration SQL to stdout without connecting to the database.

    Useful for reviewing changes before applying them or for DBAs who
    apply SQL manually.
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
# Online migrations (connect and apply directly)
# ---------------------------------------------------------------------------
def do_run_migrations(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """Create an async engine and run migrations within a sync context."""
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    """Run migrations against a live database using the async engine."""
    asyncio.run(run_async_migrations())


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
