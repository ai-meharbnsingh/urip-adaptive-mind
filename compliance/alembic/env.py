"""
Alembic async migration environment for the Compliance Service.

Uses async SQLAlchemy engine (asyncpg driver) to connect to compliance_db.
DB URL is read from COMPLIANCE_DB_URL env var, with a sensible default.

Run migrations:
    cd compliance/
    alembic upgrade head

Generate a new migration:
    alembic revision --autogenerate -m "describe change"
"""
import asyncio
import os
from logging.config import fileConfig

from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import create_async_engine

from alembic import context

# ---------------------------------------------------------------------------
# Alembic config object — access alembic.ini values
# ---------------------------------------------------------------------------
config = context.config

# Logging setup from alembic.ini
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# ---------------------------------------------------------------------------
# Import all models so autogenerate can detect them
# ---------------------------------------------------------------------------
# NOTE: we must manipulate sys.path before importing compliance_backend
import sys
from pathlib import Path

# compliance/alembic/ → compliance/backend/
_backend_dir = Path(__file__).parent.parent / "backend"
if str(_backend_dir) not in sys.path:
    sys.path.insert(0, str(_backend_dir))

from compliance_backend.database import Base  # noqa: E402

# Import all model modules so their tables are registered on Base.metadata
import compliance_backend.models.framework  # noqa: F401
import compliance_backend.models.policy  # noqa: F401

target_metadata = Base.metadata

# ---------------------------------------------------------------------------
# DB URL — prefer env var, fall back to alembic.ini sqlalchemy.url
# ---------------------------------------------------------------------------
DATABASE_URL = os.environ.get(
    "COMPLIANCE_DB_URL",
    config.get_main_option("sqlalchemy.url"),
)


def run_migrations_offline() -> None:
    """Run migrations in offline mode (no live DB connection)."""
    context.configure(
        url=DATABASE_URL,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """Run migrations using async engine."""
    connectable = create_async_engine(DATABASE_URL, poolclass=pool.NullPool)
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
