"""
Tests for AUDIT-FIX MEDIUM worker — covers M1, M2, M4, M6, M10, M11, M12.

Each finding gets at least one targeted test that exercises the fix.
Compliance-side tests live alongside compliance/backend/tests/.
"""
from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timedelta, timezone

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession


# Local fixture: enable CORE module for default_tenant so the settings
# router does not 403 on its require_module("CORE") gate. We define it
# locally so this test file is robust to the conftest oscillating between
# revisions during a parallel-fix sprint.
@pytest_asyncio.fixture
async def core_subscription(db_session, default_tenant):
    from backend.models.subscription import TenantSubscription

    sub = TenantSubscription(
        id=uuid.uuid4(),
        tenant_id=default_tenant.id,
        module_code="CORE",
        is_enabled=True,
        billing_tier="STANDARD",
    )
    db_session.add(sub)
    await db_session.commit()
    await db_session.refresh(sub)
    return sub


# ---------------------------------------------------------------------------
# M1 — Password policy: min_length=12, max_length=72
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_m1_user_create_rejects_short_password(client: AsyncClient, auth_headers, core_subscription, db_session):
    """8-char password is now too short (min_length=12)."""
    payload = {
        "email": "shortpw@example.com",
        "full_name": "Short PW",
        "password": "short!12",  # 8 chars — below new min of 12
        "role": "ciso",
    }
    resp = await client.post("/api/settings/users", json=payload, headers=auth_headers)
    assert resp.status_code == 422, resp.text


@pytest.mark.asyncio
async def test_m1_user_create_rejects_long_password(client: AsyncClient, auth_headers, core_subscription, db_session):
    """73-char password is too long (above bcrypt 72-byte limit)."""
    payload = {
        "email": "longpw@example.com",
        "full_name": "Long PW",
        "password": "A" * 73,  # bcrypt would silently truncate
        "role": "ciso",
    }
    resp = await client.post("/api/settings/users", json=payload, headers=auth_headers)
    assert resp.status_code == 422, resp.text


@pytest.mark.asyncio
async def test_m1_user_create_accepts_12_char_password(client: AsyncClient, auth_headers, core_subscription, db_session):
    """12-char password is now exactly at the lower bound."""
    payload = {
        "email": "ok12pw@example.com",
        "full_name": "OK PW",
        "password": "Abcd1234!?#$",  # exactly 12 chars
        "role": "ciso",
    }
    resp = await client.post("/api/settings/users", json=payload, headers=auth_headers)
    # Accept any 2xx — the exact status code (200 vs 201) may vary across
    # router revisions; we only care that the password passed validation.
    assert 200 <= resp.status_code < 300, resp.text
    # Sanity: response should NOT be a 422 validation failure.
    assert resp.status_code != 422


# ---------------------------------------------------------------------------
# M2 — EmailStr on LoginRequest + UserCreate + TenantAdminUserCreate
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_m2_login_rejects_invalid_email_format(client: AsyncClient):
    """LoginRequest now uses EmailStr — malformed email → 422."""
    resp = await client.post(
        "/api/auth/login",
        json={"email": "not-an-email", "password": "Whatever#1234"},
    )
    assert resp.status_code == 422, resp.text


@pytest.mark.asyncio
async def test_m2_user_create_rejects_invalid_email(client: AsyncClient, auth_headers, core_subscription):
    """UserCreate now uses EmailStr — malformed email → 422."""
    resp = await client.post(
        "/api/settings/users",
        json={
            "email": "not-an-email",
            "full_name": "Bad",
            "password": "Abcd1234!?#$",
            "role": "ciso",
        },
        headers=auth_headers,
    )
    assert resp.status_code == 422, resp.text


# ---------------------------------------------------------------------------
# M4 — search/owner query length cap
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_m4_risks_list_rejects_overlong_search(client: AsyncClient, auth_headers, vm_subscription):
    """500-char search → 422 via Pydantic max_length=200."""
    long_search = "x" * 500
    resp = await client.get(
        f"/api/risks?search={long_search}",
        headers=auth_headers,
    )
    assert resp.status_code == 422, resp.text


@pytest.mark.asyncio
async def test_m4_risks_list_rejects_overlong_owner(client: AsyncClient, auth_headers, vm_subscription):
    """500-char owner → 422."""
    long_owner = "x" * 500
    resp = await client.get(
        f"/api/risks?owner={long_owner}",
        headers=auth_headers,
    )
    assert resp.status_code == 422, resp.text


@pytest.mark.asyncio
async def test_m4_risks_list_accepts_short_search(client: AsyncClient, auth_headers, vm_subscription):
    """100-char search is fine (well under cap)."""
    resp = await client.get(
        f"/api/risks?search={'x' * 100}",
        headers=auth_headers,
    )
    # auth_headers seeds CORE+VM but the test tenant has no risks in this test
    assert resp.status_code == 200, resp.text


# ---------------------------------------------------------------------------
# M11 — Pending drilldown queue starvation
# ---------------------------------------------------------------------------


def test_m11_pending_request_filter_at_sql_level():
    """
    Verify the production query in `list_pending_requests` filters
    `expires_at > now()` at the SQL level (BEFORE the LIMIT) so a backlog of
    expired rows cannot starve the 50-row response window.

    We inspect the query construction directly because the agent_ingest
    model is optional (only registered when the agent_ingest router is wired
    into the running app).
    """
    import inspect

    from backend.routers import agent_ingest

    src = inspect.getsource(agent_ingest.list_pending_requests)
    # The fix is: a `DrilldownRequest.expires_at > now` filter is added to the
    # WHERE clause BEFORE the .limit(50). Detect the SQLAlchemy column-level
    # comparison (the string form `DrilldownRequest.expires_at > now` is what
    # the source must contain).
    compact = "".join(src.split())
    assert "DrilldownRequest.expires_at>now" in compact, (
        "list_pending_requests must filter DrilldownRequest.expires_at > now() "
        "at SQL level (in the .where(...) clause)"
    )
    # The old python-side filter (inside the comprehension) must be gone —
    # otherwise the query still loads expired rows from disk.
    assert "ifr inrowsif_ensure_aware" not in compact, (
        "Python-side post-LIMIT filter still present"
    )


# ---------------------------------------------------------------------------
# M12 — URIP static mount must not serve dotfiles (/.vercel etc.)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_m12_dotfile_path_not_served(client: AsyncClient):
    """Requests to /.vercel/* must 404 even if the file exists on disk."""
    resp = await client.get("/.vercel/project.json")
    assert resp.status_code == 404, resp.text


@pytest.mark.asyncio
async def test_m12_dotgit_path_not_served(client: AsyncClient):
    """/.git/* must also 404."""
    resp = await client.get("/.git/config")
    assert resp.status_code == 404, resp.text


# ---------------------------------------------------------------------------
# M6 — tenant_id NOT NULL on Risk + AuditLog model side
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_m6_risk_tenant_id_required(db_session):
    """Risk model: tenant_id NULL must raise IntegrityError on commit."""
    from backend.models.risk import Risk
    from sqlalchemy.exc import IntegrityError

    # Create a risk with tenant_id=None — should now violate NOT NULL.
    r = Risk(
        risk_id="RISK-NULL-001",
        finding="No tenant",
        source="vapt",
        domain="network",
        cvss_score=5.0,
        severity="medium",
        asset="x.example",
        owner_team="t",
        sla_deadline=datetime.now(timezone.utc),
        tenant_id=None,
    )
    db_session.add(r)
    with pytest.raises(IntegrityError):
        await db_session.commit()
    await db_session.rollback()


# ---------------------------------------------------------------------------
# M10 — Rate limit fail-closed on storage error for /auth/login
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_m10_login_rate_limit_fails_closed_on_storage_error():
    """
    When the slowapi storage backend raises, the RateLimitMiddleware must
    FAIL-CLOSED for /api/auth/login (return 503) instead of fail-open
    (allow the request through). For non-auth routes the legacy fail-open
    behaviour is preserved (availability of the bulk of the API matters
    during a limiter outage; the auth bucket carries the security-critical
    brute-force protection on its own).

    We test the middleware in isolation because the simplified backend.main
    does not always install the limiter.
    """
    from starlette.applications import Starlette
    from starlette.routing import Route
    from starlette.responses import PlainTextResponse
    from starlette.testclient import TestClient

    from backend.middleware import rate_limit as rl

    # Force the underlying storage to raise.
    def _boom(*args, **kwargs):
        raise RuntimeError("simulated redis outage")

    rl.limiter.limiter.hit = _boom  # type: ignore[assignment]
    try:
        async def login_endpoint(request):
            return PlainTextResponse("ok", status_code=200)

        async def heartbeat(request):
            return PlainTextResponse("ok", status_code=200)

        app = Starlette(routes=[
            Route("/api/auth/login", login_endpoint, methods=["POST"]),
            Route("/api/some-write", heartbeat, methods=["POST"]),
        ])
        app.add_middleware(rl.RateLimitMiddleware)
        with TestClient(app) as c:
            # /api/auth/login MUST fail-closed (503) on storage error.
            resp = c.post("/api/auth/login", json={})
            assert resp.status_code == 503, resp.text
            # Non-auth routes preserve fail-open (200) for availability.
            resp_other = c.post("/api/some-write", json={})
            assert resp_other.status_code == 200, resp_other.text
    finally:
        # Restore real hit() — slowapi's MemoryStorage hit() is the default.
        rl.limiter = rl.Limiter(
            key_func=rl.real_client_ip,
            storage_uri=rl._DEFAULT_STORAGE,
            default_limits=[],
            headers_enabled=True,
        )
