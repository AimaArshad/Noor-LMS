"""Alembic environment configured for async SQLAlchemy (asyncpg).

The database URL is resolved in this order:

1. ``alembic -x db_url=postgresql+asyncpg://...``  (handy for a test database)
2. ``DATABASE_URL`` from the app settings / ``.env``
"""

from __future__ import annotations

import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from app.core.config import settings
from app.models import Base  # importing the package registers ALL models on Base.metadata

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def get_url() -> str:
    """Return the database URL (``-x db_url=...`` overrides the settings)."""
    override = context.get_x_argument(as_dictionary=True).get("db_url")
    return override or settings.DATABASE_URL


def run_migrations_offline() -> None:
    """Generate SQL without a DB connection (``alembic upgrade head --sql``)."""
    context.configure(
        url=get_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    """Configure the context with a live (sync-facade) connection and migrate."""
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,  # detect column type changes
        # compare_server_default=True,  # enable if you want server-default drift detection
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """Create an async engine and run migrations inside ``run_sync``."""
    section = config.get_section(config.config_ini_section, {})
    section["sqlalchemy.url"] = get_url()  # set directly: avoids ini '%' interpolation issues

    connectable = async_engine_from_config(
        section,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,  # migrations are short-lived; no pooling
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


def run_migrations_online() -> None:
    """Entry point for online mode."""
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()