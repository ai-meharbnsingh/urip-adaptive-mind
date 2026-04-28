"""
CRITICAL ISOLATION TEST: Tenant A user CANNOT see Tenant B's risks.

Protocol:
  (a) Seed two tenants (tenant_a, tenant_b)
  (b) Seed risks for each tenant
  (c) Authenticate as Tenant A user
  (d) GET /api/risks — assert only Tenant A risks returned
  (e) Direct fetch of Tenant B risk_id returns 404 (not 403 — no information leak)

This test MUST PASS before the multi-tenant implementation is considered complete.
"""

import uuid
from datetime import datetime, timedelta, timezone

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

# conftest handles pg_dialect monkey-patch — import order is critical
from backend.database import Base, get_db
from backend.main import app
from backend.middleware.auth import create_access_token, hash_password
from backend.models.tenant import Tenant
from backend.models.user import User
from backend.models.risk import Risk
from backend.models.subscription import TenantSubscription  # noqa: F401


# ---------------------------------------------------------------------------
# Isolation-specific fixtures (own session so we can control exactly what's in DB)
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def isolation_client(db_session: AsyncSession):
    """Client wired to the shared test DB session."""

    async def _override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def two_tenant_setup(db_session: AsyncSession):
    """
    Seed:
      - tenant_a with 3 risks
      - tenant_b with 2 risks
      - one user per tenant
    Returns dict with all objects.
    """
    now = datetime.now(timezone.utc)

    # --- Tenants ---
    tenant_a = Tenant(
        id=uuid.uuid4(),
        name="Tenant Alpha",
        slug="alpha",
        domain="alpha.com",
        is_active=True,
        settings={},
    )
    tenant_b = Tenant(
        id=uuid.uuid4(),
        name="Tenant Beta",
        slug="beta",
        domain="beta.com",
        is_active=True,
        settings={},
    )
    db_session.add_all([tenant_a, tenant_b])
    await db_session.flush()

    # --- Users ---
    user_a = User(
        id=uuid.uuid4(),
        email="alice@alpha.com",
        hashed_password=hash_password("AlicePass@1"),
        full_name="Alice Alpha",
        role="ciso",
        team="SecOps",
        is_active=True,
        tenant_id=tenant_a.id,
    )
    user_b = User(
        id=uuid.uuid4(),
        email="bob@beta.com",
        hashed_password=hash_password("BobPass@1"),
        full_name="Bob Beta",
        role="ciso",
        team="SecOps",
        is_active=True,
        tenant_id=tenant_b.id,
    )
    db_session.add_all([user_a, user_b])
    await db_session.flush()

    # --- Risks for Tenant A (3 risks) ---
    risks_a = []
    for i in range(3):
        r = Risk(
            id=uuid.uuid4(),
            risk_id=f"ALPHA-{i + 1:03d}",
            finding=f"Alpha finding #{i + 1}",
            source="vapt",
            domain="network",
            cvss_score=7.5,
            severity="high",
            asset=f"alpha-server-{i + 1}",
            owner_team="Alpha SecOps",
            status="open",
            sla_deadline=now + timedelta(days=7),
            tenant_id=tenant_a.id,
        )
        db_session.add(r)
        risks_a.append(r)

    # --- Risks for Tenant B (2 risks) ---
    risks_b = []
    for i in range(2):
        r = Risk(
            id=uuid.uuid4(),
            risk_id=f"BETA-{i + 1:03d}",
            finding=f"Beta finding #{i + 1}",
            source="crowdstrike",
            domain="endpoint",
            cvss_score=8.0,
            severity="critical",
            asset=f"beta-endpoint-{i + 1}",
            owner_team="Beta SecOps",
            status="open",
            sla_deadline=now + timedelta(days=3),
            tenant_id=tenant_b.id,
        )
        db_session.add(r)
        risks_b.append(r)

    # VM subscriptions required by @require_module("VM") gate on /api/risks
    for _t in [tenant_a, tenant_b]:
        db_session.add(TenantSubscription(
            id=uuid.uuid4(),
            tenant_id=_t.id,
            module_code="VM",
            is_enabled=True,
            billing_tier="STANDARD",
        ))
        await db_session.flush()

    await db_session.commit()

    # Refresh all objects
    for obj in [tenant_a, tenant_b, user_a, user_b] + risks_a + risks_b:
        await db_session.refresh(obj)

    return {
        "tenant_a": tenant_a,
        "tenant_b": tenant_b,
        "user_a": user_a,
        "user_b": user_b,
        "risks_a": risks_a,
        "risks_b": risks_b,
    }


# ===========================================================================
# Isolation tests
# ===========================================================================


@pytest.mark.asyncio
async def test_tenant_a_sees_only_own_risks(isolation_client: AsyncClient, two_tenant_setup):
    """
    (a,b) Two tenants seeded with risks.
    (c) Authenticate as Tenant A user.
    (d) GET /api/risks returns only Tenant A's 3 risks.
    """
    data = two_tenant_setup
    user_a = data["user_a"]
    tenant_a = data["tenant_a"]
    risks_a = data["risks_a"]
    risks_b = data["risks_b"]

    # Token for user_a (Tenant A)
    token = create_access_token(str(user_a.id), user_a.role, tenant_id=str(tenant_a.id))
    headers = {"Authorization": f"Bearer {token}"}

    resp = await isolation_client.get("/api/risks", headers=headers)
    assert resp.status_code == 200

    body = resp.json()
    returned_risk_ids = {item["risk_id"] for item in body["items"]}
    alpha_risk_ids = {r.risk_id for r in risks_a}
    beta_risk_ids = {r.risk_id for r in risks_b}

    # Must contain all Alpha risks
    assert alpha_risk_ids.issubset(returned_risk_ids), (
        f"Missing Alpha risks: {alpha_risk_ids - returned_risk_ids}"
    )

    # Must NOT contain any Beta risks
    assert returned_risk_ids.isdisjoint(beta_risk_ids), (
        f"Leaked Beta risks to Alpha user: {returned_risk_ids & beta_risk_ids}"
    )

    # Total must match exactly what was seeded for Tenant A
    assert body["total"] == len(risks_a), (
        f"Expected {len(risks_a)} risks for Tenant A, got {body['total']}"
    )


@pytest.mark.asyncio
async def test_tenant_a_gets_404_for_tenant_b_risk(isolation_client: AsyncClient, two_tenant_setup):
    """
    (e) GET /api/risks/{risk_id} for a Tenant B risk by a Tenant A user returns 404.
    This verifies no information leak (404 vs 403 — existence is not revealed).
    """
    data = two_tenant_setup
    user_a = data["user_a"]
    tenant_a = data["tenant_a"]
    risks_b = data["risks_b"]

    token = create_access_token(str(user_a.id), user_a.role, tenant_id=str(tenant_a.id))
    headers = {"Authorization": f"Bearer {token}"}

    # Try to access Tenant B's first risk by risk_id string
    beta_risk_id = risks_b[0].risk_id
    resp = await isolation_client.get(f"/api/risks/{beta_risk_id}", headers=headers)

    assert resp.status_code == 404, (
        f"Expected 404 (no information leak), got {resp.status_code}. "
        f"Tenant A should not know Tenant B's risk exists."
    )


@pytest.mark.asyncio
async def test_tenant_b_sees_only_own_risks(isolation_client: AsyncClient, two_tenant_setup):
    """Symmetric check — Tenant B user also only sees Tenant B's risks."""
    data = two_tenant_setup
    user_b = data["user_b"]
    tenant_b = data["tenant_b"]
    risks_a = data["risks_a"]
    risks_b = data["risks_b"]

    token = create_access_token(str(user_b.id), user_b.role, tenant_id=str(tenant_b.id))
    headers = {"Authorization": f"Bearer {token}"}

    resp = await isolation_client.get("/api/risks", headers=headers)
    assert resp.status_code == 200

    body = resp.json()
    returned_risk_ids = {item["risk_id"] for item in body["items"]}
    alpha_risk_ids = {r.risk_id for r in risks_a}
    beta_risk_ids = {r.risk_id for r in risks_b}

    assert beta_risk_ids.issubset(returned_risk_ids)
    assert returned_risk_ids.isdisjoint(alpha_risk_ids)
    assert body["total"] == len(risks_b)


@pytest.mark.asyncio
async def test_no_tenant_token_returns_401(isolation_client: AsyncClient, two_tenant_setup):
    """
    A JWT token without tenant_id claim is rejected at the auth layer.
    This prevents old (pre-migration) tokens from working post-launch.
    """
    # Manually craft a token without tenant_id (simulates pre-migration token)
    from backend.config import settings
    from datetime import timedelta
    import jwt as jose_jwt

    expire = datetime.now(timezone.utc) + timedelta(hours=1)
    payload_no_tenant = {
        "sub": str(uuid.uuid4()),
        "role": "ciso",
        "exp": expire,
        # NOTE: no tenant_id
    }
    token = jose_jwt.encode(payload_no_tenant, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)

    headers = {"Authorization": f"Bearer {token}"}
    resp = await isolation_client.get("/api/risks", headers=headers)

    # Must be rejected — no tenant context = no access
    assert resp.status_code in (401, 403), (
        f"Expected 401/403 for tenant-less token, got {resp.status_code}"
    )
