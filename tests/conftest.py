"""
Shared fixtures for URIP test suite.

Uses SQLite (aiosqlite) instead of PostgreSQL for fast, isolated tests.
Overrides the FastAPI `get_db` dependency so every request hits the test DB.
"""

import uuid
from datetime import datetime, timedelta, timezone
from typing import AsyncGenerator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

# ---------------------------------------------------------------------------
# SQLite does not understand the PostgreSQL UUID or JSON dialect types.
# We swap them for generic types BEFORE any model metadata is built.
# ---------------------------------------------------------------------------
import sqlalchemy.dialects.postgresql as pg_dialect
from sqlalchemy import Text
from sqlalchemy.types import TypeDecorator, CHAR


class SQLiteUUID(TypeDecorator):
    """Store UUID as a 32-char hex string in SQLite."""

    impl = CHAR(32)
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        if isinstance(value, uuid.UUID):
            return value.hex
        return uuid.UUID(value).hex

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        return uuid.UUID(value)


# Monkey-patch the PostgreSQL types so models compile against SQLite
pg_dialect.UUID = SQLiteUUID  # type: ignore[attr-defined]
pg_dialect.JSON = Text  # type: ignore[attr-defined]

# NOW import the app and models (they rely on patched types)
from backend.database import Base, get_db  # noqa: E402
from backend.main import app  # noqa: E402
from backend.middleware.auth import create_access_token, hash_password  # noqa: E402
from backend.models.user import User  # noqa: E402
from backend.models.risk import Risk  # noqa: E402

# ---------------------------------------------------------------------------
# Engine & session factory (in-memory SQLite, shared across a single test)
# ---------------------------------------------------------------------------
TEST_DATABASE_URL = "sqlite+aiosqlite://"

engine = create_async_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestSessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """Create all tables, yield a session, then drop everything."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with TestSessionLocal() as session:
        yield session

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """Provide an httpx AsyncClient wired to the FastAPI app with test DB."""

    async def _override_get_db() -> AsyncGenerator[AsyncSession, None]:
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def auth_headers(db_session: AsyncSession) -> dict[str, str]:
    """Create a CISO user and return Authorization headers with a valid JWT."""
    user = User(
        id=uuid.uuid4(),
        email="ciso@urip.test",
        hashed_password=hash_password("Secure#Pass1"),
        full_name="Test CISO",
        role="ciso",
        team="Security",
        is_active=True,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)

    token = create_access_token(str(user.id), user.role)
    return {"Authorization": f"Bearer {token}"}


@pytest_asyncio.fixture
async def it_team_headers(db_session: AsyncSession) -> dict[str, str]:
    """Create an IT-team user and return Authorization headers."""
    user = User(
        id=uuid.uuid4(),
        email="itlead@urip.test",
        hashed_password=hash_password("Secure#Pass2"),
        full_name="IT Lead",
        role="it_team",
        team="Infrastructure",
        is_active=True,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)

    token = create_access_token(str(user.id), user.role)
    return {"Authorization": f"Bearer {token}"}


@pytest_asyncio.fixture
async def seeded_risks(db_session: AsyncSession, auth_headers: dict) -> list[Risk]:
    """Insert 10 test risks with varying severities and return them."""
    severities = ["critical", "critical", "high", "high", "high",
                   "medium", "medium", "medium", "low", "low"]
    sources = ["crowdstrike", "easm", "cnapp", "armis", "vapt",
               "threat_intel", "cert_in", "bug_bounty", "soc", "crowdstrike"]
    domains = ["network", "cloud", "application", "iot", "network",
               "cloud", "application", "iot", "network", "cloud"]
    cvss_scores = [9.8, 9.1, 8.5, 7.9, 7.2, 6.1, 5.5, 4.8, 3.2, 2.1]

    now = datetime.now(timezone.utc)
    risks: list[Risk] = []

    for i in range(10):
        risk = Risk(
            id=uuid.uuid4(),
            risk_id=f"RISK-2026-{i + 1:03d}",
            finding=f"Test vulnerability #{i + 1}",
            description=f"Description for test risk {i + 1}",
            source=sources[i],
            domain=domains[i],
            cvss_score=cvss_scores[i],
            severity=severities[i],
            asset=f"server-{i + 1:02d}.urip.test",
            owner_team="Infrastructure" if i % 2 == 0 else "AppSec",
            status="open",
            sla_deadline=now + timedelta(days=7 + i),
            cve_id=f"CVE-2026-{1000 + i}" if i < 5 else None,
        )
        db_session.add(risk)
        risks.append(risk)

    await db_session.commit()
    for r in risks:
        await db_session.refresh(r)

    return risks
