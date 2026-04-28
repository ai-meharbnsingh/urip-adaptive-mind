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
# Optional third-party deps: some connector tests patch boto3 directly but the
# library may not be installed in lightweight test environments.
# Provide a tiny stub so import-time wiring succeeds.
# ---------------------------------------------------------------------------
import sys
import types
import os

if "boto3" not in sys.modules:
    boto3_stub = types.ModuleType("boto3")

    def _missing_boto3_client(*args, **kwargs):  # pragma: no cover
        raise RuntimeError("boto3 is not installed (test stub in use)")

    boto3_stub.client = _missing_boto3_client  # type: ignore[attr-defined]
    sys.modules["boto3"] = boto3_stub

if "botocore" not in sys.modules:
    botocore_stub = types.ModuleType("botocore")
    botocore_exceptions = types.ModuleType("botocore.exceptions")

    class ClientError(Exception):
        pass

    class NoCredentialsError(Exception):
        pass

    botocore_exceptions.ClientError = ClientError  # type: ignore[attr-defined]
    botocore_exceptions.NoCredentialsError = NoCredentialsError  # type: ignore[attr-defined]
    botocore_stub.exceptions = botocore_exceptions  # type: ignore[attr-defined]

    sys.modules["botocore"] = botocore_stub
    sys.modules["botocore.exceptions"] = botocore_exceptions

# Public-source connectors may perform real network connectivity checks at
# authenticate() time. Tests run in an offline sandbox; stub these checks.
try:  # pragma: no cover
    from connectors.cert_in.api_client import CertInAPIClient

    def _validate_connectivity_test_stub(self) -> bool:  # type: ignore[no-redef]
        """
        Offline-safe connectivity check for tests:
        - still issues a GET so respx-based tests can assert it was called
        - never fails the authenticate() path when the sandbox has no network
        """
        import httpx
        try:
            resp = self._client.get(f"{self.base_url}/s2cMainServlet")
            resp.raise_for_status()
        except httpx.HTTPStatusError:
            return False
        except Exception:
            return True
        return True

    CertInAPIClient.validate_connectivity = _validate_connectivity_test_stub  # type: ignore[assignment]
except Exception:
    pass

# ---------------------------------------------------------------------------
# SQLite does not understand the PostgreSQL UUID or JSON dialect types.
# We swap them for generic types BEFORE any model metadata is built.
# ---------------------------------------------------------------------------
import sqlalchemy.dialects.postgresql as pg_dialect
from sqlalchemy import Text
from sqlalchemy.types import TypeDecorator, CHAR


import json as _json


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


class SQLiteJSON(TypeDecorator):
    """Store JSON-serializable values (dict/list/etc.) as TEXT in SQLite."""

    impl = Text
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        return _json.dumps(value)

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        return _json.loads(value)


# Monkey-patch the PostgreSQL types so models compile against SQLite
pg_dialect.UUID = SQLiteUUID  # type: ignore[attr-defined]
pg_dialect.JSON = SQLiteJSON  # type: ignore[attr-defined]

# NOW import the app and models (they rely on patched types)
from backend.database import Base, get_db  # noqa: E402
from backend.main import app  # noqa: E402
from backend.middleware.auth import create_access_token, hash_password  # noqa: E402
from backend.models.tenant import Tenant  # noqa: E402 — must be imported so tenants table is in Base.metadata
from backend.models.user import User  # noqa: E402
from backend.models.risk import Risk  # noqa: E402
from backend.models.subscription import TenantSubscription  # noqa: E402 — registers tenant_subscriptions table in Base.metadata

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
# Ensure service-layer helpers that open their own sessions via
# backend.database.async_session (e.g. exploitability_service, de-dup services)
# use the test engine instead of the real DATABASE_URL.
# ---------------------------------------------------------------------------
import backend.database as _backend_database  # noqa: E402

_backend_database.async_session = TestSessionLocal


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _reset_rate_limiter_between_tests():
    """
    Reset HIGH-009 in-memory rate limiter buckets between tests.

    Prevents cross-test coupling where one test's /api/auth/login calls
    cause unrelated tests to receive 429s.
    """
    try:
        from backend.middleware.rate_limit import limiter
        limiter.limiter.storage.reset()
        yield
        limiter.limiter.storage.reset()
    except Exception:
        yield


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

    # Reset rate-limiter buckets for every new client instance (defensive
    # against cross-test coupling when tests issue many /api/auth/login calls).
    try:
        from backend.middleware.rate_limit import limiter

        limiter.limiter.storage.reset()
    except Exception:
        pass

    app.dependency_overrides[get_db] = _override_get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def default_tenant(db_session: AsyncSession) -> "Tenant":
    """
    Create a default 'urip-test' tenant used by all existing fixtures.

    This is the backward-compat tenant that ensures pre-multi-tenant tests
    continue to work.  All existing users and risks are created under this tenant.
    """
    t = Tenant(
        id=uuid.uuid4(),
        name="URIP Test Tenant",
        slug="urip-test",
        domain="urip.test",
        is_active=True,
        settings={},
    )
    db_session.add(t)
    await db_session.commit()
    await db_session.refresh(t)
    return t


@pytest_asyncio.fixture
async def auth_headers(
    db_session: AsyncSession,
    default_tenant: "Tenant",
    core_subscription: "TenantSubscription",
    vm_subscription: "TenantSubscription",
) -> dict[str, str]:
    """Create a CISO user and return Authorization headers with a valid JWT."""
    user = User(
        id=uuid.uuid4(),
        email="ciso@urip.test",
        hashed_password=hash_password("Secure#Pass1"),
        full_name="Test CISO",
        role="ciso",
        team="Security",
        is_active=True,
        tenant_id=default_tenant.id,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)

    token = create_access_token(str(user.id), user.role, tenant_id=str(default_tenant.id))
    return {"Authorization": f"Bearer {token}"}


@pytest_asyncio.fixture
async def it_team_headers(
    db_session: AsyncSession,
    default_tenant: "Tenant",
    core_subscription: "TenantSubscription",
    vm_subscription: "TenantSubscription",
) -> dict[str, str]:
    """Create an IT-team user and return Authorization headers."""
    user = User(
        id=uuid.uuid4(),
        email="itlead@urip.test",
        hashed_password=hash_password("Secure#Pass2"),
        full_name="IT Lead",
        role="it_team",
        team="Infrastructure",
        is_active=True,
        tenant_id=default_tenant.id,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)

    token = create_access_token(str(user.id), user.role, tenant_id=str(default_tenant.id))
    return {"Authorization": f"Bearer {token}"}


@pytest_asyncio.fixture
async def core_subscription(db_session: AsyncSession, default_tenant: "Tenant") -> "TenantSubscription":
    """
    Enable CORE module for default_tenant.

    Many routers (dashboard, reports, audit_log, settings) are CORE-gated.
    """
    sub = TenantSubscription(
        id=uuid.uuid4(),
        tenant_id=default_tenant.id,
        module_code="CORE",
        is_enabled=True,
        billing_tier="STANDARD",
        expires_at=None,
    )
    db_session.add(sub)
    await db_session.commit()
    await db_session.refresh(sub)
    return sub

@pytest_asyncio.fixture
async def vm_subscription(db_session: AsyncSession, default_tenant: "Tenant") -> "TenantSubscription":
    """Enable VM module for default_tenant. Required because list_risks is gated on require_module("VM")."""
    sub = TenantSubscription(
        id=uuid.uuid4(),
        tenant_id=default_tenant.id,
        module_code="VM",
        is_enabled=True,
        billing_tier="STANDARD",
    )
    db_session.add(sub)
    await db_session.commit()
    await db_session.refresh(sub)
    return sub


@pytest_asyncio.fixture
async def seeded_risks(db_session: AsyncSession, auth_headers: dict, default_tenant: "Tenant", vm_subscription: "TenantSubscription") -> list[Risk]:
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
            tenant_id=default_tenant.id,
        )
        db_session.add(risk)
        risks.append(risk)

    await db_session.commit()
    for r in risks:
        await db_session.refresh(r)

    return risks
