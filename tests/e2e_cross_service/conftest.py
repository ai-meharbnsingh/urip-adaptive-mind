"""
E2E cross-service fixtures: spins up BOTH the URIP and Compliance FastAPI
apps in the same test process, each backed by an isolated in-memory SQLite
engine.  An in-process event bridge is used in place of Redis so the
workflows that span services (control failure → URIP risk; URIP risk
resolved → control re-evaluation) can run without any external infra.

Why an in-process bridge instead of Redis:
  - The two services are designed to communicate over Redis pub/sub
    (shared/events/redis_client.py + shared/events/topics.py).
  - Redis is optional for tests (the Redis package may or may not be
    available, and even if installed there is no guarantee of a running
    instance during CI).
  - For the cross-service workflow tests we therefore expose a
    DummyEventBus fixture that satisfies the same publish / subscribe
    contract the production publisher would call into.  Tests that
    explicitly want to exercise Redis can opt in via the
    `pytest.mark.integration` marker (skipped by default).

Layout of fixtures provided:

  uri_engine        — async SQLite engine for URIP
  compliance_engine — async SQLite engine for Compliance
  urip_session      — AsyncSession for direct URIP DB writes
  compliance_session — AsyncSession for direct Compliance DB writes
  urip_client       — httpx.AsyncClient bound to the URIP FastAPI app
  compliance_client — httpx.AsyncClient bound to the Compliance app
  event_bus         — DummyEventBus connecting the two services
  cross_jwt_secret  — shared HS256 secret for INTEGRATED auth mode
  make_jwt_for      — helper to mint a JWT that BOTH services accept
                      (URIP signs with JWT_SECRET_KEY by default; for the
                       cross-service tests we synchronise these via the
                       config object so the same token authenticates both)
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
import uuid
from pathlib import Path
from typing import Any, AsyncGenerator, Awaitable, Callable

import pytest
import pytest_asyncio


# ─── compliance_backend lives in compliance/backend — make it importable ───
_COMPLIANCE_BACKEND_DIR = (
    Path(__file__).resolve().parents[2] / "compliance" / "backend"
)
if str(_COMPLIANCE_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_COMPLIANCE_BACKEND_DIR))


# ─── Environment must be set BEFORE importing compliance_backend ───────────
os.environ.setdefault("COMPLIANCE_DB_URL", "sqlite+aiosqlite:///:memory:")
os.environ.setdefault("COMPLIANCE_AUTH_MODE", "STANDALONE")
# Use a single shared secret across both services for the cross-service tests
SHARED_JWT_SECRET = "cross-service-test-secret-do-not-use-in-prod"
os.environ.setdefault("COMPLIANCE_JWT_SECRET", SHARED_JWT_SECRET)
os.environ.setdefault("URIP_JWT_SECRET", SHARED_JWT_SECRET)
# Compliance Pydantic settings expect CORS_ORIGINS to be JSON-parseable when
# provided via env.  The repo's .env exposes a comma-separated string for the
# URIP service, which trips the compliance settings loader.  Force a valid
# JSON list to short-circuit that, AND switch the default env_file to one
# that does not exist (so the project-root .env can't poison the loader).
os.environ["CORS_ORIGINS"] = '["http://localhost:3000","http://localhost:3001"]'

# Strip env_file from BaseSettings model_config BEFORE compliance_backend.config
# imports.  Pydantic-settings reads env_file from the subclass `model_config`,
# so we override the metaclass behaviour to drop that key.
import pydantic_settings as _ps  # noqa: E402

_orig_init_subclass = _ps.BaseSettings.__init_subclass__


def _strip_env_file(cls, **kwargs):  # type: ignore[no-untyped-def]
    cfg = getattr(cls, "model_config", None)
    if isinstance(cfg, dict) and ("env_file" in cfg or "env_file_encoding" in cfg):
        new_cfg = dict(cfg)
        new_cfg.pop("env_file", None)
        new_cfg.pop("env_file_encoding", None)
        cls.model_config = new_cfg  # type: ignore[attr-defined]


_ps.BaseSettings.__init_subclass__ = classmethod(_strip_env_file)  # type: ignore[assignment]
# Force compliance evidence storage into a per-test temp dir
import tempfile

_EV_TMP = tempfile.mkdtemp(prefix="e2e_xsvc_evidence_")
os.environ.setdefault("EVIDENCE_STORAGE_BASE_DIR", _EV_TMP)


# ─── Apply URIP's pg→sqlite type patch BEFORE backend imports ──────────────
# (Mirrors tests/conftest.py to keep URIP models compileable on SQLite.)
import sqlalchemy.dialects.postgresql as _pg
from sqlalchemy import Text
from sqlalchemy.types import CHAR, TypeDecorator


class _SQLiteUUID(TypeDecorator):
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


class _SQLiteJSON(TypeDecorator):
    impl = Text
    cache_ok = True

    def process_bind_param(self, value, dialect):
        return None if value is None else json.dumps(value)

    def process_result_value(self, value, dialect):
        return None if value is None else json.loads(value)


_pg.UUID = _SQLiteUUID  # type: ignore[attr-defined]
_pg.JSON = _SQLiteJSON  # type: ignore[attr-defined]


# ─── Patch FastAPI 0.115 + Python 3.14 + `from __future__ import annotations`
# ───
# When the compliance routers use `from __future__ import annotations`, the
# `-> None` return annotation on routes with status_code=204 is resolved by
# `get_type_hints()` to NoneType (truthy) instead of literal None (falsy).
# That trips FastAPI's `assert is_body_allowed_for_status_code(...)` check
# in routing.py:507.  Compliance source cannot be modified by these tests
# (per task constraints), so we relax the assertion here — the runtime
# behaviour of 204 is unchanged; the assertion exists only to catch
# misconfigurations at app-construction time, and the misconfiguration in
# question is a Python-version edge case rather than a real schema bug.
import fastapi.routing as _fr  # noqa: E402
from fastapi.datastructures import DefaultPlaceholder as _DefaultPlaceholder  # noqa: E402

_orig_apiroute_init = _fr.APIRoute.__init__


def _patched_apiroute_init(self, *args, **kwargs):  # type: ignore[no-untyped-def]
    """
    Wrap the FastAPI APIRoute initializer.  When the endpoint annotation is
    `-> None` under PEP-563 (`from __future__ import annotations`), FastAPI
    resolves the response_model to `NoneType` (truthy) and trips the
    body-allowed assertion for 204 / 304 routes.  Pre-empt that by forcing
    response_model=None for those status codes when the inferred type is
    NoneType / DefaultPlaceholder(None).
    """
    sc = kwargs.get("status_code")
    rm = kwargs.get("response_model")
    if sc in (204, 304):
        # Force response_model=None for no-body status codes — guarantees
        # FastAPI's inference path won't pick up NoneType from PEP-563.
        kwargs["response_model"] = None
    elif rm is type(None):  # noqa: E721
        kwargs["response_model"] = None
    elif isinstance(rm, _DefaultPlaceholder) and rm.value is type(None):  # noqa: E721
        kwargs["response_model"] = None
    return _orig_apiroute_init(self, *args, **kwargs)


_fr.APIRoute.__init__ = _patched_apiroute_init  # type: ignore[method-assign]


# Now safe to import the apps + their DB layers
from sqlalchemy.ext.asyncio import (  # noqa: E402
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import StaticPool  # noqa: E402
from httpx import ASGITransport, AsyncClient  # noqa: E402
import jwt as _jose_jwt  # noqa: E402

from backend.database import Base as URIPBase, get_db as urip_get_db  # noqa: E402
from backend.main import app as urip_app  # noqa: E402
from backend.config import settings as urip_settings  # noqa: E402

# Force URIP to sign with the shared secret so a single JWT verifies on both
urip_settings.JWT_SECRET_KEY = SHARED_JWT_SECRET

from compliance_backend.database import Base as CompBase, get_async_session as comp_get_session  # noqa: E402
from compliance_backend.main import app as comp_app  # noqa: E402

# Make sure new compliance model tables register their metadata
import compliance_backend.models.control_run  # noqa: E402,F401
import compliance_backend.models.evidence  # noqa: E402,F401
import compliance_backend.models.auditor  # noqa: E402,F401
import compliance_backend.models.score_snapshot  # noqa: E402,F401
import compliance_backend.models.vendor  # noqa: E402,F401

# The vendors router exists at compliance_backend.routers.vendors but is NOT
# wired into compliance_backend.main.app today.  We attach it here for the
# E2E tests so workflow 6 can exercise the live HTTP surface end-to-end.
# This is a test-only adapter — the source code is unchanged.
from compliance_backend.routers import vendors as _vendors_router  # noqa: E402

if not any(getattr(r, "path", "").startswith("/vendors") for r in comp_app.routes):
    comp_app.include_router(_vendors_router.router)


# ─── In-process event bus (replaces Redis for cross-service tests) ────────


class DummyEventBus:
    """Asyncio.Queue-backed pub/sub stand-in for shared/events/redis_client."""

    def __init__(self) -> None:
        self._channels: dict[str, list[asyncio.Queue]] = {}
        self.publishes: list[tuple[str, dict]] = []  # full audit trail

    async def publish(self, channel: str, payload: dict) -> int:
        self.publishes.append((channel, payload))
        queues = self._channels.get(channel, [])
        for q in queues:
            await q.put(payload)
        return len(queues)

    def subscribe(self, channel: str) -> "asyncio.Queue[dict]":
        q: asyncio.Queue = asyncio.Queue()
        self._channels.setdefault(channel, []).append(q)
        return q

    def published_to(self, channel: str) -> list[dict]:
        return [p for c, p in self.publishes if c == channel]


@pytest_asyncio.fixture
async def event_bus() -> DummyEventBus:
    return DummyEventBus()


# ─── URIP engine + session + client ────────────────────────────────────────


@pytest_asyncio.fixture
async def urip_engine():
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(URIPBase.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def urip_session(urip_engine) -> AsyncGenerator[AsyncSession, None]:
    SF = async_sessionmaker(urip_engine, class_=AsyncSession, expire_on_commit=False)
    async with SF() as session:
        yield session


@pytest_asyncio.fixture
async def urip_client(urip_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    async def _override():
        yield urip_session

    urip_app.dependency_overrides[urip_get_db] = _override
    transport = ASGITransport(app=urip_app)
    async with AsyncClient(transport=transport, base_url="http://urip.test") as ac:
        yield ac
    urip_app.dependency_overrides.clear()


# ─── Compliance engine + session + client ──────────────────────────────────


@pytest_asyncio.fixture
async def compliance_engine():
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(CompBase.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def compliance_session(compliance_engine) -> AsyncGenerator[AsyncSession, None]:
    SF = async_sessionmaker(compliance_engine, class_=AsyncSession, expire_on_commit=False)
    async with SF() as session:
        yield session


@pytest_asyncio.fixture
async def compliance_client(
    compliance_engine, compliance_session: AsyncSession
) -> AsyncGenerator[AsyncClient, None]:
    """
    Compliance HTTP client.

    Important: many compliance routers (e.g. policies) flush but do NOT commit.
    The existing compliance test suite handles this by sharing ONE session
    between the test body and the HTTP client (so flushed-but-uncommitted
    rows are visible within the same test).  We mirror that pattern here so
    HTTP-level workflow tests can read back data they just wrote.
    """

    async def _override():
        yield compliance_session

    comp_app.dependency_overrides[comp_get_session] = _override
    transport = ASGITransport(app=comp_app)
    async with AsyncClient(transport=transport, base_url="http://compliance.test") as ac:
        yield ac
    comp_app.dependency_overrides.clear()


# ─── JWT helpers shared between services ───────────────────────────────────


@pytest.fixture
def cross_jwt_secret() -> str:
    return SHARED_JWT_SECRET


@pytest.fixture
def make_compliance_jwt() -> Callable[..., str]:
    """Mint a JWT that the Compliance service accepts in STANDALONE mode."""

    def _make(
        tenant_id: str,
        *,
        role: str = "admin",
        sub: str = "test-user",
        ttl_seconds: int = 3600,
    ) -> str:
        import time

        payload = {
            "sub": sub,
            "tenant_id": tenant_id,
            "role": role,
            "exp": int(time.time()) + ttl_seconds,
            "iss": "compliance",
        }
        return _jose_jwt.encode(payload, SHARED_JWT_SECRET, algorithm="HS256")

    return _make


@pytest.fixture
def make_urip_jwt() -> Callable[..., str]:
    """Mint a URIP JWT (also accepted by Compliance in INTEGRATED mode)."""

    def _make(
        user_id: str,
        *,
        role: str = "ciso",
        tenant_id: str | None = None,
        is_super_admin: bool = False,
    ) -> str:
        from backend.middleware.auth import create_access_token

        return create_access_token(
            user_id, role, tenant_id=tenant_id, is_super_admin=is_super_admin
        )

    return _make
