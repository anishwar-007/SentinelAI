"""Alembic env for SentinelAI Platform Postgres installations.

This env intentionally does **not** import the reference runtime. Fresh customer
databases that only need Platform tables can point Alembic here. Deployments that
also host demo document tables should use
``examples/reference_runtime/db/migrations`` instead (see docs/architecture.md).
"""

from __future__ import annotations

import asyncio
import os
from logging.config import fileConfig

from alembic import context
from dotenv import load_dotenv
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from sentinelai_platform.persistence.postgres.base import Base
from sentinelai_platform.persistence.postgres.models_execution import (  # noqa: F401
    ExecutionModel,
)
from sentinelai_platform.persistence.postgres.models_snapshot import (  # noqa: F401
    ExecutionSnapshotModel,
)
from sentinelai_platform.persistence.postgres.models_span import SpanModel  # noqa: F401
from sentinelai_platform.persistence.postgres.models_trace import TraceModel  # noqa: F401
from sentinelai_platform.persistence.postgres.url import prepare_database_url

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def get_database_config() -> tuple[str, dict[str, object]]:
    load_dotenv()
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise RuntimeError("DATABASE_URL is not set.")
    return prepare_database_url(database_url)


def run_migrations_offline() -> None:
    url, _ = get_database_config()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def execute_migrations(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    url, connect_args = get_database_config()
    configuration = config.get_section(config.config_ini_section) or {}
    configuration["sqlalchemy.url"] = url
    connectable = async_engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
        connect_args=connect_args,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(execute_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
