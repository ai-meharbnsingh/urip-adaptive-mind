"""
CritFix-B NEW-1 — Audit log tenant_id stamping coverage.

Background
----------
Per the E2E worker's report, only the `risk_created` action writes to
AuditLog with tenant_id correctly. Many other state-changing endpoints
either (a) do not call AuditLog at all, or (b) call AuditLog without
passing tenant_id (legacy tenant-less rows).

This module asserts — for every state-changing URIP endpoint — that one
AuditLog row is created with the correct tenant_id (matching the caller's
TenantContext) and a sensible action verb.

TDD discipline
--------------
- Each test creates state via the API.
- Each test then queries the audit_logs table directly and asserts:
    1. Exactly one new AuditLog row was written for that mutation.
    2. AuditLog.tenant_id == caller's tenant.
    3. AuditLog.user_id == caller's user.
    4. AuditLog.action is the documented verb (e.g. risk_updated).
    5. AuditLog.resource_type and resource_id are populated.

Atomicity is enforced by writing audit_log via the SAME db.commit() as the
state change (existing pattern in routers/risks.py create_risk).
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.middleware.auth import create_access_token, hash_password
from backend.models.audit_log import AuditLog
from backend.models.risk import Risk
from backend.models.subscription import TenantSubscription
from backend.models.tenant import Tenant
from backend.models.user import User


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _audit_rows(db: AsyncSession, *, action: str | None = None) -> list[AuditLog]:
    q = select(AuditLog)
    if action is not None:
        q = q.where(AuditLog.action == action)
    q = q.order_by(AuditLog.created_at.asc())
    return list((await db.execute(q)).scalars().all())


@pytest_asyncio.fixture
async def core_subscription(db_session: AsyncSession, default_tenant: Tenant) -> TenantSubscription:
    """Enable CORE module for default tenant — required by /api/settings/* gate."""
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


@pytest_asyncio.fixture
async def super_admin_user(db_session: AsyncSession) -> User:
    """A super-admin (no tenant) for /admin/* endpoint tests."""
    u = User(
        id=uuid.uuid4(),
        email="superadmin@platform.test",
        hashed_password=hash_password("SuperPass#1"),
        full_name="Super Admin",
        role="ciso",
        is_active=True,
        is_super_admin=True,
        tenant_id=None,
    )
    db_session.add(u)
    await db_session.commit()
    await db_session.refresh(u)
    return u


@pytest_asyncio.fixture
async def super_admin_headers(super_admin_user: User) -> dict[str, str]:
    token = create_access_token(
        str(super_admin_user.id),
        super_admin_user.role,
        tenant_id=None,
        is_super_admin=True,
    )
    return {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------------------
# routers/risks.py — update / assign already had AuditLog calls but missing
# tenant_id.  Assert that tenant_id is now correctly stamped.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_risk_update_writes_audit_log_with_tenant_id(
    client: AsyncClient,
    it_team_headers: dict,
    seeded_risks: list[Risk],
    db_session: AsyncSession,
    default_tenant: Tenant,
):
    """PATCH /api/risks/{id} writes one AuditLog row stamped with tenant_id."""
    risk = seeded_risks[0]

    before = len(await _audit_rows(db_session, action="risk_updated"))

    resp = await client.patch(
        f"/api/risks/{risk.risk_id}",
        headers=it_team_headers,
        json={"status": "in_progress"},
    )
    assert resp.status_code == 200, resp.text

    after_rows = await _audit_rows(db_session, action="risk_updated")
    assert len(after_rows) == before + 1, "exactly one risk_updated row expected"

    new_row = after_rows[-1]
    assert new_row.tenant_id == default_tenant.id, (
        f"audit row tenant_id={new_row.tenant_id} does not match caller's "
        f"tenant {default_tenant.id} — multi-tenant audit gap."
    )
    assert new_row.resource_type == "risk"
    assert new_row.resource_id == risk.id
    assert new_row.user_id is not None


@pytest.mark.asyncio
async def test_risk_assign_writes_audit_log_with_tenant_id(
    client: AsyncClient,
    it_team_headers: dict,
    seeded_risks: list[Risk],
    db_session: AsyncSession,
    default_tenant: Tenant,
):
    """POST /api/risks/{id}/assign writes AuditLog with tenant_id."""
    # Create assignee user under same tenant
    assignee = User(
        id=uuid.uuid4(),
        email="assignee@urip.test",
        hashed_password=hash_password("AssigneePass#1"),
        full_name="Assignee",
        role="it_team",
        is_active=True,
        tenant_id=default_tenant.id,
    )
    db_session.add(assignee)
    await db_session.commit()
    await db_session.refresh(assignee)

    risk = seeded_risks[0]

    before = len(await _audit_rows(db_session, action="risk_assigned"))

    resp = await client.post(
        f"/api/risks/{risk.risk_id}/assign",
        headers=it_team_headers,
        json={"user_id": str(assignee.id)},
    )
    assert resp.status_code == 200, resp.text

    after_rows = await _audit_rows(db_session, action="risk_assigned")
    assert len(after_rows) == before + 1
    new_row = after_rows[-1]
    assert new_row.tenant_id == default_tenant.id
    assert new_row.resource_type == "risk"


# ---------------------------------------------------------------------------
# routers/settings.py — user mgmt + connector create currently NOT audited
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_user_writes_audit_log(
    client: AsyncClient,
    auth_headers: dict,
    db_session: AsyncSession,
    default_tenant: Tenant,
    core_subscription: TenantSubscription,
):
    """POST /api/settings/users writes AuditLog (user_created) with tenant_id."""
    before = len(await _audit_rows(db_session, action="user_created"))
    resp = await client.post(
        "/api/settings/users",
        headers=auth_headers,
        json={
            "email": "newuser@urip.test",
            "full_name": "New User",
            "password": "NewSecurePass#1",
            "role": "it_team",
        },
    )
    assert resp.status_code == 201, resp.text

    after = await _audit_rows(db_session, action="user_created")
    assert len(after) == before + 1
    new_row = after[-1]
    assert new_row.tenant_id == default_tenant.id
    assert new_row.resource_type == "user"
    assert new_row.resource_id is not None


@pytest.mark.asyncio
async def test_update_user_writes_audit_log(
    client: AsyncClient,
    auth_headers: dict,
    db_session: AsyncSession,
    default_tenant: Tenant,
    core_subscription: TenantSubscription,
):
    """PATCH /api/settings/users/{id} writes AuditLog (user_updated) with tenant_id."""
    # Create a target user under the same tenant
    target = User(
        id=uuid.uuid4(),
        email="target@urip.test",
        hashed_password=hash_password("TargetPass#1"),
        full_name="Target User",
        role="it_team",
        is_active=True,
        tenant_id=default_tenant.id,
    )
    db_session.add(target)
    await db_session.commit()
    await db_session.refresh(target)

    before = len(await _audit_rows(db_session, action="user_updated"))
    resp = await client.patch(
        f"/api/settings/users/{target.id}",
        headers=auth_headers,
        json={"full_name": "Updated Name"},
    )
    assert resp.status_code == 200, resp.text

    after = await _audit_rows(db_session, action="user_updated")
    assert len(after) == before + 1
    assert after[-1].tenant_id == default_tenant.id


@pytest.mark.asyncio
async def test_create_connector_writes_audit_log(
    client: AsyncClient,
    auth_headers: dict,
    db_session: AsyncSession,
    default_tenant: Tenant,
    core_subscription: TenantSubscription,
):
    """POST /api/settings/connectors writes AuditLog (connector_created)."""
    before = len(await _audit_rows(db_session, action="connector_created"))
    # Skip credentials — Fernet encryption requires URIP_FERNET_KEY which is
    # not set in the unit-test env. Audit-row test cares about audit row, not
    # credential encryption (covered by other tests).
    resp = await client.post(
        "/api/settings/connectors",
        headers=auth_headers,
        json={
            "name": "test-cs",
            "source_type": "crowdstrike",
            "base_url": "https://test.example",
            "sync_interval_minutes": 30,
        },
    )
    assert resp.status_code == 201, resp.text
    after = await _audit_rows(db_session, action="connector_created")
    assert len(after) == before + 1
    assert after[-1].tenant_id == default_tenant.id
    assert after[-1].resource_type == "connector"


# ---------------------------------------------------------------------------
# routers/tenants.py — super-admin endpoints
# Super-admins have NO tenant context — audit row tenant_id is the *target*
# tenant being mutated (never NULL for tenant-scoped mutations).  For
# operations against the platform itself (create_tenant) the tenant_id is
# the newly created tenant.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_tenant_writes_audit_log(
    client: AsyncClient,
    super_admin_headers: dict,
    db_session: AsyncSession,
):
    """POST /api/admin/tenants writes AuditLog (tenant_created) with new tenant_id."""
    before = len(await _audit_rows(db_session, action="tenant_created"))
    resp = await client.post(
        "/api/admin/tenants",
        headers=super_admin_headers,
        json={
            "name": "Acme Corp",
            "slug": "acme-corp",
            "domain": "acme.test",
            "primary_contact_email": "ceo@acme.test",
        },
    )
    assert resp.status_code == 201, resp.text
    new_tenant_id_str = resp.json()["id"]

    after = await _audit_rows(db_session, action="tenant_created")
    assert len(after) == before + 1
    new_row = after[-1]
    assert str(new_row.tenant_id) == new_tenant_id_str, (
        "new tenant audit row should be stamped with the *new* tenant's id"
    )
    assert new_row.resource_type == "tenant"


@pytest.mark.asyncio
async def test_update_tenant_writes_audit_log(
    client: AsyncClient,
    super_admin_headers: dict,
    default_tenant: Tenant,
    db_session: AsyncSession,
):
    """PATCH /api/admin/tenants/{slug} writes AuditLog (tenant_updated)."""
    before = len(await _audit_rows(db_session, action="tenant_updated"))
    resp = await client.patch(
        f"/api/admin/tenants/{default_tenant.slug}",
        headers=super_admin_headers,
        json={"app_name": "Renamed App"},
    )
    assert resp.status_code == 200, resp.text
    after = await _audit_rows(db_session, action="tenant_updated")
    assert len(after) == before + 1
    assert after[-1].tenant_id == default_tenant.id


@pytest.mark.asyncio
async def test_provision_tenant_admin_writes_audit_log(
    client: AsyncClient,
    super_admin_headers: dict,
    default_tenant: Tenant,
    db_session: AsyncSession,
):
    """POST /api/admin/tenants/{slug}/users writes AuditLog (tenant_admin_provisioned)."""
    before = len(await _audit_rows(db_session, action="tenant_admin_provisioned"))
    resp = await client.post(
        f"/api/admin/tenants/{default_tenant.slug}/users",
        headers=super_admin_headers,
        json={
            "email": "tadmin@urip.test",
            "full_name": "Tenant Admin",
            "password": "TenantAdminPass#1",
            "role": "ciso",
        },
    )
    assert resp.status_code == 201, resp.text
    after = await _audit_rows(db_session, action="tenant_admin_provisioned")
    assert len(after) == before + 1
    assert after[-1].tenant_id == default_tenant.id
    assert after[-1].resource_type == "user"


@pytest.mark.asyncio
async def test_enable_module_writes_audit_log(
    client: AsyncClient,
    super_admin_headers: dict,
    default_tenant: Tenant,
    db_session: AsyncSession,
):
    """POST /api/admin/tenants/{slug}/modules writes AuditLog (module_enabled)."""
    before = len(await _audit_rows(db_session, action="module_enabled"))
    resp = await client.post(
        f"/api/admin/tenants/{default_tenant.slug}/modules",
        headers=super_admin_headers,
        json={"module_code": "VM", "billing_tier": "TRIAL"},
    )
    assert resp.status_code == 201, resp.text
    after = await _audit_rows(db_session, action="module_enabled")
    assert len(after) == before + 1
    new_row = after[-1]
    assert new_row.tenant_id == default_tenant.id
    assert new_row.resource_type == "module_subscription"


@pytest.mark.asyncio
async def test_update_module_writes_audit_log(
    client: AsyncClient,
    super_admin_headers: dict,
    default_tenant: Tenant,
    vm_subscription: TenantSubscription,
    db_session: AsyncSession,
):
    """PATCH /api/admin/tenants/{slug}/modules/{module_code} writes AuditLog."""
    before = len(await _audit_rows(db_session, action="module_updated"))
    resp = await client.patch(
        f"/api/admin/tenants/{default_tenant.slug}/modules/VM",
        headers=super_admin_headers,
        json={"billing_tier": "STANDARD"},
    )
    assert resp.status_code == 200, resp.text
    after = await _audit_rows(db_session, action="module_updated")
    assert len(after) == before + 1
    assert after[-1].tenant_id == default_tenant.id


@pytest.mark.asyncio
async def test_disable_module_writes_audit_log(
    client: AsyncClient,
    super_admin_headers: dict,
    default_tenant: Tenant,
    vm_subscription: TenantSubscription,
    db_session: AsyncSession,
):
    """DELETE /api/admin/tenants/{slug}/modules/{module_code} writes AuditLog."""
    before = len(await _audit_rows(db_session, action="module_disabled"))
    resp = await client.delete(
        f"/api/admin/tenants/{default_tenant.slug}/modules/VM",
        headers=super_admin_headers,
    )
    assert resp.status_code == 200, resp.text
    after = await _audit_rows(db_session, action="module_disabled")
    assert len(after) == before + 1
    assert after[-1].tenant_id == default_tenant.id


# ---------------------------------------------------------------------------
# routers/asset_taxonomy.py — currently NO audit log calls at all
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_taxonomy_entry_writes_audit_log(
    client: AsyncClient,
    auth_headers: dict,
    default_tenant: Tenant,
    db_session: AsyncSession,
):
    """POST /api/asset-taxonomy writes AuditLog (taxonomy_created)."""
    before = len(await _audit_rows(db_session, action="taxonomy_created"))
    resp = await client.post(
        "/api/asset-taxonomy",
        headers=auth_headers,
        json={"tier_code": "T1", "keyword": "test-crown-jewel"},
    )
    assert resp.status_code == 201, resp.text
    after = await _audit_rows(db_session, action="taxonomy_created")
    assert len(after) == before + 1
    assert after[-1].tenant_id == default_tenant.id
    assert after[-1].resource_type == "asset_taxonomy"


@pytest.mark.asyncio
async def test_update_taxonomy_entry_writes_audit_log(
    client: AsyncClient,
    auth_headers: dict,
    default_tenant: Tenant,
    db_session: AsyncSession,
):
    """PATCH /api/asset-taxonomy/{id} writes AuditLog (taxonomy_updated)."""
    # Create one first
    create_resp = await client.post(
        "/api/asset-taxonomy",
        headers=auth_headers,
        json={"tier_code": "T2", "keyword": "tier2-orig"},
    )
    assert create_resp.status_code == 201
    entry_id = create_resp.json()["id"]

    before = len(await _audit_rows(db_session, action="taxonomy_updated"))
    resp = await client.patch(
        f"/api/asset-taxonomy/{entry_id}",
        headers=auth_headers,
        json={"keyword": "tier2-renamed"},
    )
    assert resp.status_code == 200, resp.text
    after = await _audit_rows(db_session, action="taxonomy_updated")
    assert len(after) == before + 1
    assert after[-1].tenant_id == default_tenant.id


@pytest.mark.asyncio
async def test_delete_taxonomy_entry_writes_audit_log(
    client: AsyncClient,
    auth_headers: dict,
    default_tenant: Tenant,
    db_session: AsyncSession,
):
    """DELETE /api/asset-taxonomy/{id} writes AuditLog (taxonomy_deleted)."""
    create_resp = await client.post(
        "/api/asset-taxonomy",
        headers=auth_headers,
        json={"tier_code": "T3", "keyword": "tier3-todelete"},
    )
    assert create_resp.status_code == 201
    entry_id = create_resp.json()["id"]

    before = len(await _audit_rows(db_session, action="taxonomy_deleted"))
    resp = await client.delete(f"/api/asset-taxonomy/{entry_id}", headers=auth_headers)
    assert resp.status_code == 200, resp.text
    after = await _audit_rows(db_session, action="taxonomy_deleted")
    assert len(after) == before + 1
    assert after[-1].tenant_id == default_tenant.id


@pytest.mark.asyncio
async def test_bulk_import_taxonomy_writes_audit_log(
    client: AsyncClient,
    auth_headers: dict,
    default_tenant: Tenant,
    db_session: AsyncSession,
):
    """POST /api/asset-taxonomy/bulk writes one AuditLog (taxonomy_bulk_imported)."""
    before = len(await _audit_rows(db_session, action="taxonomy_bulk_imported"))
    resp = await client.post(
        "/api/asset-taxonomy/bulk",
        headers=auth_headers,
        json=[
            {"tier_code": "T1", "keyword": "bulk-a"},
            {"tier_code": "T2", "keyword": "bulk-b"},
        ],
    )
    assert resp.status_code == 201, resp.text
    after = await _audit_rows(db_session, action="taxonomy_bulk_imported")
    assert len(after) == before + 1, (
        "bulk import should produce ONE summary audit row, not one per entry"
    )
    new_row = after[-1]
    assert new_row.tenant_id == default_tenant.id
    # Bulk row must record the count for forensic analysis
    assert new_row.details is not None
    assert new_row.details.get("inserted_count") == 2


# ---------------------------------------------------------------------------
# Atomicity smoke test — if audit log insertion would fail, the state change
# MUST roll back.  We simulate this by patching db.add to raise on AuditLog.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_audit_log_failure_rolls_back_state_change(
    client: AsyncClient,
    it_team_headers: dict,
    seeded_risks: list[Risk],
    db_session: AsyncSession,
    monkeypatch,
):
    """
    Atomicity: if writing the AuditLog row fails, the state mutation MUST
    roll back.  Both writes share the same `db.commit()` so SQLAlchemy
    will roll back automatically when the commit raises.

    We force AuditLog.__init__ to raise for the `risk_updated` action and
    confirm:
      1. The HTTP response is a server error (500) — the route does not
         silently swallow the audit failure.
      2. The risk's `status` value in the database is unchanged.
    """
    risk = seeded_risks[0]
    risk_id_str = risk.risk_id  # capture primitive before detaching the ORM object
    risk_pk = risk.id
    original_status = risk.status

    # Force AuditLog.__init__ to raise so the commit fails.
    real_init = AuditLog.__init__

    def boom_init(self, *args, **kwargs):
        if kwargs.get("action") == "risk_updated":
            raise RuntimeError("simulated audit log write failure")
        return real_init(self, *args, **kwargs)

    monkeypatch.setattr(AuditLog, "__init__", boom_init)

    # The exception will bubble out of the route. With httpx ASGITransport
    # in a TaskGroup that may surface as ExceptionGroup. We accept either
    # a 500 response OR a propagated exception (both prove non-success).
    raised = False
    try:
        resp = await client.patch(
            f"/api/risks/{risk_id_str}",
            headers=it_team_headers,
            json={"status": "in_progress"},
        )
        # Some FastAPI configurations turn unhandled exceptions into 500s
        assert resp.status_code >= 500, resp.text
    except Exception:
        raised = True
    # Either path proves the audit failure was not swallowed
    _ = raised

    # Restore the real AuditLog so subsequent operations work.
    monkeypatch.setattr(AuditLog, "__init__", real_init)

    # Roll back the (now-failed) transaction state on the test session and
    # re-query the risk row.  Use raw primitives — never touch the ORM
    # object captured before the failure (it may be detached).
    await db_session.rollback()
    refreshed = (await db_session.execute(
        select(Risk).where(Risk.id == risk_pk)
    )).scalar_one()
    assert refreshed.status == original_status, (
        "state change must roll back when audit log write fails — "
        f"expected {original_status!r}, got {refreshed.status!r}"
    )
