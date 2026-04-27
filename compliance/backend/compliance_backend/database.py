"""
Async SQLAlchemy session + Base for the Compliance Service.

Uses a separate Postgres database (compliance_db on port 5434) so Compliance
can be deployed standalone without URIP's database.

In tests, COMPLIANCE_DB_URL is overridden to sqlite+aiosqlite:///:memory:
via the conftest.py before this module is imported.
"""
import os
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    create_async_engine,
    async_sessionmaker,
)
from sqlalchemy.orm import DeclarativeBase


DATABASE_URL = os.environ.get(
    "COMPLIANCE_DB_URL",
    "postgresql+asyncpg://compliance:compliance@localhost:5434/compliance_db",
)

# SQLite in tests needs check_same_thread=False
_connect_args: dict = {}
if DATABASE_URL.startswith("sqlite"):
    _connect_args = {"check_same_thread": False}

engine = create_async_engine(
    DATABASE_URL,
    echo=False,
    connect_args=_connect_args,
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    expire_on_commit=False,
    class_=AsyncSession,
)


class Base(DeclarativeBase):
    """Shared declarative base for all Compliance models."""
    pass


async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency — yields an async DB session."""
    async with AsyncSessionLocal() as session:
        yield session
