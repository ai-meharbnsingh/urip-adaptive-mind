"""
TDD tests for multi-tenant data model foundation.

Tests cover:
  - Tenant model creation and field validation
  - tenant_id FK on domain tables (risks, users, audit_logs,
    acceptance_requests, remediation_tasks)
  - Token embeds tenant_id claim
  - Tenant context extraction from JWT
  - Tenant-scoped query helper filters by tenant_id

Run BEFORE implementing to see all failures, then implement until green.
"""

import uuid
from datetime import datetime, timedelta, timezone

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

# conftest already monkey-patches pg_dialect; import order matters
from backend.models.tenant import Tenant  # NEW model — must exist
from backend.models.user import User
from backend.models.risk import Risk
from backend.models.audit_log import AuditLog
from backend.models.acceptance import AcceptanceRequest
from backend.models.remediation import RemediationTask
from backend.middleware.auth import create_access_token, decode_token


# ---------------------------------------------------------------------------
# Helper: create a Tenant row in DB
# ---------------------------------------------------------------------------

async def make_tenant(db: AsyncSession, *, slug: str, name: str, domain: str) -> Tenant:
    t = Tenant(
        id=uuid.uuid4(),
        name=name,
        slug=slug,
        domain=domain,
        is_active=True,
        settings={},
    )
    db.add(t)
    await db.commit()
    await db.refresh(t)
    return t


async def make_user(
    db: AsyncSession,
    *,
    email: str,
    tenant_id: uuid.UUID,
    role: str = "ciso",
) -> User:
    from backend.middleware.auth import hash_password
    u = User(
        id=uuid.uuid4(),
        email=email,
        hashed_password=hash_password("Pass@1234"),
        full_name="Test User",
        role=role,
        team="Security",
        is_active=True,
        tenant_id=tenant_id,  # NEW field
    )
    db.add(u)
    await db.commit()
    await db.refresh(u)
    return u


async def make_risk(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    risk_id: str,
    owner_user_id: uuid.UUID,
) -> Risk:
    now = datetime.now(timezone.utc)
    r = Risk(
        id=uuid.uuid4(),
        risk_id=risk_id,
        finding=f"Finding for {risk_id}",
        source="vapt",
        domain="network",
        cvss_score=7.5,
        severity="high",
        asset="server.test",
        owner_team="SecOps",
        status="open",
        sla_deadline=now + timedelta(days=7),
        tenant_id=tenant_id,  # NEW field
    )
    db.add(r)
    await db.commit()
    await db.refresh(r)
    return r


# ===========================================================================
# 1. Tenant model structure
# ===========================================================================


@pytest.mark.asyncio
async def test_tenant_model_can_be_created(db_session: AsyncSession):
    """Tenant row can be inserted with required fields."""
    t = await make_tenant(db_session, slug="acme", name="Acme Corp", domain="acme.com")

    result = await db_session.execute(select(Tenant).where(Tenant.slug == "acme"))
    fetched = result.scalar_one_or_none()

    assert fetched is not None
    assert fetched.name == "Acme Corp"
    assert fetched.domain == "acme.com"
    assert fetched.is_active is True
    assert isinstance(fetched.id, uuid.UUID)
    assert isinstance(fetched.created_at, datetime)


@pytest.mark.asyncio
async def test_tenant_slug_is_unique(db_session: AsyncSession):
    """Inserting two tenants with the same slug raises an integrity error."""
    from sqlalchemy.exc import IntegrityError

    await make_tenant(db_session, slug="duplicate", name="First", domain="first.com")

    with pytest.raises(IntegrityError):
        await make_tenant(db_session, slug="duplicate", name="Second", domain="second.com")


@pytest.mark.asyncio
async def test_tenant_settings_is_dict(db_session: AsyncSession):
    """Tenant.settings stores arbitrary JSON / dict."""
    t = Tenant(
        id=uuid.uuid4(),
        name="Branding Corp",
        slug="branding",
        domain="branding.io",
        is_active=True,
        settings={"primary_color": "#FF5733", "logo_url": "https://cdn.example.com/logo.png"},
    )
    db_session.add(t)
    await db_session.commit()
    await db_session.refresh(t)

    assert t.settings["primary_color"] == "#FF5733"
    assert t.settings["logo_url"] == "https://cdn.example.com/logo.png"


# ===========================================================================
# 2. Domain tables have tenant_id column
# ===========================================================================


@pytest.mark.asyncio
async def test_user_has_tenant_id(db_session: AsyncSession):
    """User model accepts and stores tenant_id."""
    t = await make_tenant(db_session, slug="usertest", name="UserTest", domain="usertest.com")
    u = await make_user(db_session, email="u1@usertest.com", tenant_id=t.id)

    assert u.tenant_id == t.id


@pytest.mark.asyncio
async def test_risk_has_tenant_id(db_session: AsyncSession):
    """Risk model accepts and stores tenant_id."""
    t = await make_tenant(db_session, slug="risktest", name="RiskTest", domain="risktest.com")
    u = await make_user(db_session, email="owner@risktest.com", tenant_id=t.id)
    r = await make_risk(db_session, tenant_id=t.id, risk_id="RISK-MT-001", owner_user_id=u.id)

    assert r.tenant_id == t.id


@pytest.mark.asyncio
async def test_audit_log_has_tenant_id(db_session: AsyncSession):
    """AuditLog model accepts and stores tenant_id."""
    t = await make_tenant(db_session, slug="auditmt", name="AuditTenant", domain="audit.mt")
    u = await make_user(db_session, email="auditor@audit.mt", tenant_id=t.id)

    log = AuditLog(
        id=uuid.uuid4(),
        user_id=u.id,
        action="risk_viewed",
        resource_type="risk",
        resource_id=uuid.uuid4(),
        tenant_id=t.id,  # NEW field
    )
    db_session.add(log)
    await db_session.commit()
    await db_session.refresh(log)

    assert log.tenant_id == t.id


@pytest.mark.asyncio
async def test_acceptance_has_tenant_id(db_session: AsyncSession):
    """AcceptanceRequest model accepts and stores tenant_id."""
    t = await make_tenant(db_session, slug="accmt", name="AccTenant", domain="acc.mt")
    u = await make_user(db_session, email="requester@acc.mt", tenant_id=t.id)
    r = await make_risk(db_session, tenant_id=t.id, risk_id="RISK-MT-002", owner_user_id=u.id)

    ar = AcceptanceRequest(
        id=uuid.uuid4(),
        risk_id=r.id,
        requested_by=u.id,
        justification="Business need",
        status="pending",
        review_period_days=90,
        tenant_id=t.id,  # NEW field
    )
    db_session.add(ar)
    await db_session.commit()
    await db_session.refresh(ar)

    assert ar.tenant_id == t.id


@pytest.mark.asyncio
async def test_remediation_has_tenant_id(db_session: AsyncSession):
    """RemediationTask model accepts and stores tenant_id."""
    t = await make_tenant(db_session, slug="remmt", name="RemTenant", domain="rem.mt")
    u = await make_user(db_session, email="remowner@rem.mt", tenant_id=t.id)
    r = await make_risk(db_session, tenant_id=t.id, risk_id="RISK-MT-003", owner_user_id=u.id)

    task = RemediationTask(
        id=uuid.uuid4(),
        risk_id=r.id,
        title="Patch the server",
        status="not_started",
        priority="high",
        tenant_id=t.id,  # NEW field
    )
    db_session.add(task)
    await db_session.commit()
    await db_session.refresh(task)

    assert task.tenant_id == t.id


# ===========================================================================
# 3. JWT now embeds tenant_id
# ===========================================================================


def test_create_access_token_embeds_tenant_id():
    """create_access_token must include tenant_id in the payload."""
    tenant_id = str(uuid.uuid4())
    token = create_access_token("user-123", "ciso", tenant_id=tenant_id)

    payload = decode_token(token)
    assert "tenant_id" in payload, "JWT payload must contain tenant_id"
    assert payload["tenant_id"] == tenant_id


def test_decode_token_returns_tenant_id():
    """decode_token returns the tenant_id claim embedded at creation."""
    tenant_id = str(uuid.uuid4())
    token = create_access_token("user-456", "it_team", tenant_id=tenant_id)

    payload = decode_token(token)
    assert payload["tenant_id"] == tenant_id
    assert payload["sub"] == "user-456"
    assert payload["role"] == "it_team"


# ===========================================================================
# 4. Tenant context middleware
# ===========================================================================


def test_tenant_context_var_set_and_get():
    """TenantContext can store and retrieve a tenant_id."""
    from backend.middleware.tenant import TenantContext

    tid = uuid.uuid4()
    TenantContext.set(tid)
    assert TenantContext.get() == tid


def test_tenant_context_var_is_none_when_not_set():
    """TenantContext returns None when no tenant has been set in this context."""
    from backend.middleware.tenant import _tenant_id_var, TenantContext

    # Reset the contextvar for this test (sync tests share the same context)
    token = _tenant_id_var.set(None)
    try:
        result = TenantContext.get_or_none()
        assert result is None
    finally:
        _tenant_id_var.reset(token)
