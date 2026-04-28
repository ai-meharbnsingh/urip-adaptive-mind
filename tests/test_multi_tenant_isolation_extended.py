"""
Extended multi-tenant isolation tests for dashboard + audit_log routers.

These are the highest-risk routers for cross-tenant data leakage:
  - dashboard: aggregates ALL risks — must only aggregate current tenant's risks
  - audit_log: shows ALL actions — must only show current tenant's audit entries

Protocol for each:
  (a) Seed two tenants (A and B) with data
  (b) Authenticate as Tenant A user
  (c) Query the endpoint
  (d) Assert only Tenant A data is returned
  (e) Assert Tenant B data is NOT present (no leak)
"""

import uuid
from datetime import datetime, timedelta, timezone

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

# conftest handles pg_dialect monkey-patch — import order matters
from backend.database import get_db
from backend.main import app
from backend.middleware.auth import create_access_token, hash_password
from backend.models.audit_log import AuditLog
from backend.models.remediation import RemediationTask
from backend.models.acceptance import AcceptanceRequest
from backend.models.subscription import TenantSubscription
from backend.models.tenant import Tenant
from backend.models.user import User
from backend.models.risk import Risk


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def ext_client(db_session: AsyncSession):
    """Client wired to the shared test DB session."""

    async def _override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def two_tenant_extended(db_session: AsyncSession):
    """
    Seed:
      - tenant_a with risks + audit_log entries + remediation tasks
      - tenant_b with risks + audit_log entries + remediation tasks
      - one ciso user per tenant, one it_team user per tenant
    Returns dict with all seeded objects.
    """
    now = datetime.now(timezone.utc)

    # --- Tenants ---
    tenant_a = Tenant(
        id=uuid.uuid4(),
        name="Tenant Alpha",
        slug="alpha-ext",
        domain="alpha.ext",
        is_active=True,
        settings={},
    )
    tenant_b = Tenant(
        id=uuid.uuid4(),
        name="Tenant Beta",
        slug="beta-ext",
        domain="beta.ext",
        is_active=True,
        settings={},
    )
    db_session.add_all([tenant_a, tenant_b])
    await db_session.flush()

    # --- Module subscriptions (CRIT-007) ---
    # Both tenants need CORE (dashboard, audit_log routers) and VM (remediation
    # router) so calls don't 403 at the module gate before reaching the actual
    # tenant-isolation logic under test.
    for t in (tenant_a, tenant_b):
        for code in ("CORE", "VM"):
            db_session.add(
                TenantSubscription(
                    id=uuid.uuid4(),
                    tenant_id=t.id,
                    module_code=code,
                    is_enabled=True,
                    billing_tier="STANDARD",
                )
            )
    await db_session.flush()

    # --- Users ---
    ciso_a = User(
        id=uuid.uuid4(),
        email="ciso@alpha.ext",
        hashed_password=hash_password("AlphaPass@1"),
        full_name="Alice Alpha CISO",
        role="ciso",
        team="SecOps",
        is_active=True,
        tenant_id=tenant_a.id,
    )
    it_a = User(
        id=uuid.uuid4(),
        email="it@alpha.ext",
        hashed_password=hash_password("AlphaIT@1"),
        full_name="Alpha IT",
        role="it_team",
        team="Infra",
        is_active=True,
        tenant_id=tenant_a.id,
    )
    ciso_b = User(
        id=uuid.uuid4(),
        email="ciso@beta.ext",
        hashed_password=hash_password("BetaPass@1"),
        full_name="Bob Beta CISO",
        role="ciso",
        team="SecOps",
        is_active=True,
        tenant_id=tenant_b.id,
    )
    it_b = User(
        id=uuid.uuid4(),
        email="it@beta.ext",
        hashed_password=hash_password("BetaIT@1"),
        full_name="Beta IT",
        role="it_team",
        team="Infra",
        is_active=True,
        tenant_id=tenant_b.id,
    )
    db_session.add_all([ciso_a, it_a, ciso_b, it_b])
    await db_session.flush()

    # --- Risks for Tenant A (3 risks: 2 open critical, 1 accepted) ---
    risks_a = []
    for i in range(3):
        r = Risk(
            id=uuid.uuid4(),
            risk_id=f"ALPHA-EXT-{i + 1:03d}",
            finding=f"Alpha extended finding #{i + 1}",
            source="vapt",
            domain="network",
            cvss_score=9.0,
            severity="critical",
            asset=f"alpha-server-{i + 1}",
            owner_team="Alpha SecOps",
            status="open" if i < 2 else "accepted",
            sla_deadline=now + timedelta(days=7),
            tenant_id=tenant_a.id,
        )
        db_session.add(r)
        risks_a.append(r)

    # --- Risks for Tenant B (2 risks: both open high) ---
    risks_b = []
    for i in range(2):
        r = Risk(
            id=uuid.uuid4(),
            risk_id=f"BETA-EXT-{i + 1:03d}",
            finding=f"Beta extended finding #{i + 1}",
            source="crowdstrike",
            domain="endpoint",
            cvss_score=7.5,
            severity="high",
            asset=f"beta-endpoint-{i + 1}",
            owner_team="Beta SecOps",
            status="open",
            sla_deadline=now + timedelta(days=3),
            tenant_id=tenant_b.id,
        )
        db_session.add(r)
        risks_b.append(r)

    await db_session.flush()

    # --- Audit logs for Tenant A (2 entries) ---
    audit_a = []
    for i in range(2):
        entry = AuditLog(
            id=uuid.uuid4(),
            user_id=ciso_a.id,
            action=f"alpha_action_{i + 1}",
            resource_type="risk",
            resource_id=risks_a[i].id,
            details={"info": f"alpha detail {i + 1}"},
            tenant_id=tenant_a.id,
        )
        db_session.add(entry)
        audit_a.append(entry)

    # --- Audit logs for Tenant B (3 entries) ---
    audit_b = []
    for i in range(3):
        entry = AuditLog(
            id=uuid.uuid4(),
            user_id=ciso_b.id,
            action=f"beta_action_{i + 1}",
            resource_type="risk",
            resource_id=risks_b[i % 2].id,
            details={"info": f"beta detail {i + 1}"},
            tenant_id=tenant_b.id,
        )
        db_session.add(entry)
        audit_b.append(entry)

    # --- Remediation tasks for Tenant A (1 task) ---
    rem_a = RemediationTask(
        id=uuid.uuid4(),
        risk_id=risks_a[0].id,
        title="Fix Alpha critical vuln",
        status="not_started",
        priority="high",
        tenant_id=tenant_a.id,
    )
    db_session.add(rem_a)

    # --- Remediation tasks for Tenant B (1 task) ---
    rem_b = RemediationTask(
        id=uuid.uuid4(),
        risk_id=risks_b[0].id,
        title="Patch Beta endpoint",
        status="not_started",
        priority="medium",
        tenant_id=tenant_b.id,
    )
    db_session.add(rem_b)

    await db_session.commit()

    # Refresh all
    for obj in [tenant_a, tenant_b, ciso_a, it_a, ciso_b, it_b] + risks_a + risks_b + audit_a + audit_b + [rem_a, rem_b]:
        await db_session.refresh(obj)

    return {
        "tenant_a": tenant_a,
        "tenant_b": tenant_b,
        "ciso_a": ciso_a,
        "it_a": it_a,
        "ciso_b": ciso_b,
        "it_b": it_b,
        "risks_a": risks_a,
        "risks_b": risks_b,
        "audit_a": audit_a,
        "audit_b": audit_b,
        "rem_a": rem_a,
        "rem_b": rem_b,
    }


# ===========================================================================
# DASHBOARD TESTS — highest-risk for cross-tenant aggregate leak
# ===========================================================================


@pytest.mark.asyncio
async def test_dashboard_kpis_scoped_to_tenant(ext_client, two_tenant_extended):
    """
    Dashboard KPIs must aggregate ONLY the current tenant's risks.

    Tenant A has 3 risks (2 open critical, 1 accepted).
    Tenant B has 2 open high risks.

    When Tenant A user queries /api/dashboard/kpis:
      - total_open must be 2 (not 4 = 2+2)
      - critical must be 2 (not 2+0=2, but the key is no Beta high bleeds in)
      - accepted must be 1 (not 0)
    """
    data = two_tenant_extended
    token = create_access_token(
        str(data["ciso_a"].id), data["ciso_a"].role, tenant_id=str(data["tenant_a"].id)
    )
    headers = {"Authorization": f"Bearer {token}"}

    resp = await ext_client.get("/api/dashboard/kpis", headers=headers)
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"

    body = resp.json()

    # Tenant A has 2 open risks, so total_open == 2 (not 4)
    assert body["total_open"] == 2, (
        f"Dashboard shows {body['total_open']} open risks — expected 2 (Tenant A only). "
        f"Cross-tenant leak suspected if > 2."
    )

    # Tenant A has 2 critical open risks
    assert body["critical"] == 2, (
        f"Expected 2 critical risks for Tenant A, got {body['critical']}"
    )

    # Tenant A has 1 accepted risk
    assert body["accepted"] == 1, (
        f"Expected 1 accepted risk for Tenant A, got {body['accepted']}"
    )

    # Tenant B has 0 critical (they're high), and 0 accepted — any non-zero bleed is a fail
    assert body.get("high", 0) == 0, (
        f"Tenant A has no high risks; high={body.get('high',0)} suggests Tenant B bleed"
    )


@pytest.mark.asyncio
async def test_dashboard_kpis_tenant_b_sees_own_data(ext_client, two_tenant_extended):
    """
    Symmetric check: Tenant B user sees only Tenant B's KPIs.
    Tenant B has 2 open high risks, 0 accepted.
    """
    data = two_tenant_extended
    token = create_access_token(
        str(data["ciso_b"].id), data["ciso_b"].role, tenant_id=str(data["tenant_b"].id)
    )
    headers = {"Authorization": f"Bearer {token}"}

    resp = await ext_client.get("/api/dashboard/kpis", headers=headers)
    assert resp.status_code == 200

    body = resp.json()

    # Tenant B has 2 open risks
    assert body["total_open"] == 2, (
        f"Expected 2 open risks for Tenant B, got {body['total_open']}"
    )

    # Tenant B has 0 accepted
    assert body["accepted"] == 0, (
        f"Expected 0 accepted for Tenant B, got {body['accepted']}"
    )

    # Tenant B has 0 critical (their risks are high severity)
    assert body["critical"] == 0, (
        f"Tenant B has no critical risks; critical={body['critical']} suggests Tenant A bleed"
    )

    # Tenant B has 2 high risks
    assert body["high"] == 2, (
        f"Expected 2 high risks for Tenant B, got {body['high']}"
    )


@pytest.mark.asyncio
async def test_dashboard_charts_by_domain_scoped_to_tenant(ext_client, two_tenant_extended):
    """
    /api/dashboard/charts/by-domain must return only Tenant A's domain breakdown.
    Tenant A risks are in 'network' domain.
    Tenant B risks are in 'endpoint' domain.
    Tenant A user must NOT see 'endpoint' in the chart.
    """
    data = two_tenant_extended
    token = create_access_token(
        str(data["ciso_a"].id), data["ciso_a"].role, tenant_id=str(data["tenant_a"].id)
    )
    headers = {"Authorization": f"Bearer {token}"}

    resp = await ext_client.get("/api/dashboard/charts/by-domain", headers=headers)
    assert resp.status_code == 200

    body = resp.json()
    labels = [lbl.lower() for lbl in body.get("labels", [])]

    # Tenant A has 'network' domain open risks
    assert "network" in labels, f"Expected 'network' in Tenant A dashboard labels, got {labels}"

    # Tenant B has 'endpoint' domain — must NOT appear for Tenant A
    assert "endpoint" not in labels, (
        f"'endpoint' (Tenant B domain) leaked into Tenant A dashboard: {labels}"
    )


# ===========================================================================
# AUDIT LOG TESTS — sensitive: shows actions taken by all users in a tenant
# ===========================================================================


@pytest.mark.asyncio
async def test_audit_log_scoped_to_tenant(ext_client, two_tenant_extended):
    """
    /api/audit-log must return only Tenant A's audit entries.

    Tenant A has 2 audit log entries (alpha_action_1, alpha_action_2).
    Tenant B has 3 audit log entries (beta_action_1, beta_action_2, beta_action_3).

    Tenant A user must see exactly 2 entries, none from Tenant B.
    """
    data = two_tenant_extended
    token = create_access_token(
        str(data["ciso_a"].id), data["ciso_a"].role, tenant_id=str(data["tenant_a"].id)
    )
    headers = {"Authorization": f"Bearer {token}"}

    resp = await ext_client.get("/api/audit-log", headers=headers)
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"

    body = resp.json()
    assert body["total"] == 2, (
        f"Expected 2 audit log entries for Tenant A, got {body['total']}. "
        f"Cross-tenant leak suspected if > 2."
    )

    actions = {item["action"] for item in body["items"]}

    # Must contain Tenant A actions
    assert "alpha_action_1" in actions, f"Missing alpha_action_1 from audit log: {actions}"
    assert "alpha_action_2" in actions, f"Missing alpha_action_2 from audit log: {actions}"

    # Must NOT contain Tenant B actions
    leaked_beta = {a for a in actions if a.startswith("beta_")}
    assert not leaked_beta, (
        f"Tenant B audit actions leaked to Tenant A: {leaked_beta}"
    )


@pytest.mark.asyncio
async def test_audit_log_tenant_b_sees_own_entries(ext_client, two_tenant_extended):
    """
    Symmetric: Tenant B user sees only their 3 audit log entries.
    """
    data = two_tenant_extended
    token = create_access_token(
        str(data["ciso_b"].id), data["ciso_b"].role, tenant_id=str(data["tenant_b"].id)
    )
    headers = {"Authorization": f"Bearer {token}"}

    resp = await ext_client.get("/api/audit-log", headers=headers)
    assert resp.status_code == 200

    body = resp.json()
    assert body["total"] == 3, (
        f"Expected 3 audit log entries for Tenant B, got {body['total']}"
    )

    actions = {item["action"] for item in body["items"]}

    # Must NOT contain Tenant A actions
    leaked_alpha = {a for a in actions if a.startswith("alpha_")}
    assert not leaked_alpha, (
        f"Tenant A audit actions leaked to Tenant B: {leaked_alpha}"
    )


# ===========================================================================
# REMEDIATION TESTS — scoped via risk's tenant_id through the join
# ===========================================================================


@pytest.mark.asyncio
async def test_remediation_scoped_to_tenant(ext_client, two_tenant_extended):
    """
    /api/remediation must return only Tenant A's remediation tasks.

    Tenant A has 1 task ("Fix Alpha critical vuln").
    Tenant B has 1 task ("Patch Beta endpoint").
    Tenant A user must see exactly 1 task, not Tenant B's.
    """
    data = two_tenant_extended
    token = create_access_token(
        str(data["ciso_a"].id), data["ciso_a"].role, tenant_id=str(data["tenant_a"].id)
    )
    headers = {"Authorization": f"Bearer {token}"}

    resp = await ext_client.get("/api/remediation", headers=headers)
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"

    body = resp.json()
    assert body["total"] == 1, (
        f"Expected 1 remediation task for Tenant A, got {body['total']}. "
        f"Cross-tenant leak suspected if > 1."
    )

    titles = [item["title"] for item in body["items"]]
    assert any("Alpha" in t for t in titles), f"Expected Alpha task in list: {titles}"
    assert not any("Beta" in t for t in titles), f"Beta task leaked: {titles}"


@pytest.mark.asyncio
async def test_remediation_tenant_b_sees_own_tasks(ext_client, two_tenant_extended):
    """Symmetric: Tenant B sees only their 1 remediation task."""
    data = two_tenant_extended
    token = create_access_token(
        str(data["ciso_b"].id), data["ciso_b"].role, tenant_id=str(data["tenant_b"].id)
    )
    headers = {"Authorization": f"Bearer {token}"}

    resp = await ext_client.get("/api/remediation", headers=headers)
    assert resp.status_code == 200

    body = resp.json()
    assert body["total"] == 1, (
        f"Expected 1 remediation task for Tenant B, got {body['total']}"
    )

    titles = [item["title"] for item in body["items"]]
    assert any("Beta" in t for t in titles), f"Expected Beta task: {titles}"
    assert not any("Alpha" in t for t in titles), f"Alpha task leaked: {titles}"
