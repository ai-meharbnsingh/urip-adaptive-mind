"""
WORKFLOW 9 — Module subscription enforcement.

Covers:
  1. A tenant has CORE only (no VM module).
  2. GET /api/risks → 403 from the module gate (require_module("VM")).
  3. Super-admin enables the VM module.
  4. Next GET /api/risks → 200.
  5. Super-admin DISABLES the VM module (soft, is_enabled=False).
  6. Next GET /api/risks → 403 again.
  7. Existing risks remain in the DB (we direct-queried via the same admin
     headers + the now-disabled module is just inaccessible — the row count
     can be checked via super-admin paths if needed).

The test exercises the public super-admin module-management endpoints:
  POST   /api/admin/tenants/{slug}/modules
  DELETE /api/admin/tenants/{slug}/modules/{module_code}
  GET    /api/tenants/{slug}/modules
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.risk import Risk


@pytest.mark.asyncio
async def test_workflow_09_module_gate_enforced_end_to_end(
    client: AsyncClient,
    db_session: AsyncSession,
    tenant_factory,
    enable_module,
    disable_module,
    make_user_in_tenant,
    super_admin_headers: dict,
):
    onboarding = await tenant_factory(slug="mg-e2e")
    slug = onboarding["slug"]
    tenant_id = onboarding["tenant_id"]
    admin_headers = onboarding["admin_headers"]

    # Pre-flight: no VM module yet → 403
    r = await client.get("/api/risks", headers=admin_headers)
    assert r.status_code == 403, (
        f"With no VM subscription, /api/risks must be 403. Got {r.status_code}: {r.text}"
    )

    # 3) Enable VM
    enabled = await enable_module(slug, "VM")
    assert enabled is not None
    assert enabled["is_enabled"] is True

    # 4) Now /api/risks → 200
    r = await client.get("/api/risks", headers=admin_headers)
    assert r.status_code == 200, r.text
    assert r.json()["total"] == 0  # no risks yet

    # Seed one risk so we can later prove the row was preserved across disable
    _, it_headers = await make_user_in_tenant(tenant_id, role="it_team")
    create_resp = await client.post(
        "/api/risks",
        json={
            "finding": "Pre-disable risk",
            "description": "Should survive disable",
            "source": "vapt",
            "domain": "network",
            "cvss_score": 6.5,
            "severity": "medium",
            "asset": "mg-host-01",
            "owner_team": "SecOps",
            "composite_score": 6.5,
            "in_kev_catalog": False,
            "exploit_status": "none",
            "epss_score": 0.05,
        },
        headers=it_headers,
    )
    assert create_resp.status_code == 201, create_resp.text
    pre_disable_risk_id = create_resp.json()["risk_id"]

    # 5) Disable VM
    disabled = await disable_module(slug, "VM")
    assert disabled is not None
    assert disabled["subscription"]["is_enabled"] is False

    # 6) /api/risks → 403 again
    r = await client.get("/api/risks", headers=admin_headers)
    assert r.status_code == 403, (
        f"After disable, /api/risks must be 403. Got {r.status_code}: {r.text}"
    )

    # IT-team user is also gated
    r = await client.get("/api/risks", headers=it_headers)
    assert r.status_code == 403

    # 7) The previously-created risk still exists in the DB (preserved
    #    across module disable — soft disable preserves data).  We confirm
    #    via direct DB read since the API itself is now gated.
    db_check = await db_session.execute(
        select(Risk).where(
            Risk.tenant_id == tenant_id, Risk.risk_id == pre_disable_risk_id
        )
    )
    surviving = db_check.scalar_one_or_none()
    assert surviving is not None, (
        "Disabling the VM module must NOT delete underlying Risk rows."
    )
    assert surviving.status == "open"

    # The subscription row also persists with is_enabled=False — listed via
    # GET /tenants/{slug}/modules
    list_modules = await client.get(
        f"/api/tenants/{slug}/modules", headers=admin_headers
    )
    assert list_modules.status_code == 200
    vm_rows = [m for m in list_modules.json() if m["module_code"] == "VM"]
    assert len(vm_rows) == 1
    assert vm_rows[0]["is_enabled"] is False

    # Re-enabling restores access
    re_enabled = await enable_module(slug, "VM")
    # If the module already exists disabled, enable_module re-enables it:
    # since our endpoint is POST + the existing record was disabled, the
    # router re-enables and returns 201 → enabled is not None.
    assert re_enabled is not None
    assert re_enabled["is_enabled"] is True
    r = await client.get("/api/risks", headers=admin_headers)
    assert r.status_code == 200
    assert any(item["risk_id"] == pre_disable_risk_id for item in r.json()["items"])


@pytest.mark.asyncio
async def test_workflow_09_super_admin_bypasses_module_gate(
    client: AsyncClient,
    db_session: AsyncSession,
    tenant_factory,
    super_admin_user,
):
    """
    A real super-admin (User.is_super_admin=True in DB) is exempt from the
    module gate — see backend/middleware/module_gate.py:
        if current_user.is_super_admin:
            return current_user

    Note: bypass requires the LOADED User row to have is_super_admin=True;
    the JWT claim alone is not sufficient because get_current_user() reloads
    the row from the DB.  We therefore mint a token bound to the
    super_admin_user fixture (which set is_super_admin=True at insert time)
    AND embed tenant_id in the JWT so TenantContext can be set.
    """
    from backend.middleware.auth import create_access_token

    onboarding = await tenant_factory(slug="mg-superbypass")
    # NO module enabled — but super-admin should still be allowed.
    super_token = create_access_token(
        user_id=str(super_admin_user.id),
        role=super_admin_user.role,
        tenant_id=str(onboarding["tenant_id"]),
        is_super_admin=True,
    )
    headers = {"Authorization": f"Bearer {super_token}"}
    r = await client.get("/api/risks", headers=headers)
    assert r.status_code == 200, (
        f"Super-admin must bypass module gate; got {r.status_code} {r.text}"
    )
