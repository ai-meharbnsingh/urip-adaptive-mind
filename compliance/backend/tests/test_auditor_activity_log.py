"""
TDD — Auditor activity logging (P2B.10).

Verifies:
  - Every auditor action writes an AuditorActivityLog row
  - Admin sees the log via /admin/auditor-activity, filtered by tenant
  - Other tenants do not see another tenant's log entries
"""
from __future__ import annotations

import io
import time
import uuid
from datetime import datetime, timedelta

import pytest
# CRIT-005 (Z2.1): migrated python-jose -> PyJWT (HS256 surface identical)
import jwt
from sqlalchemy import select

from compliance_backend.models.framework import Framework, FrameworkVersion, Control
from compliance_backend.models.auditor import AuditorAccess, AuditorActivityLog

STANDALONE_SECRET = "test-secret-standalone"


def _user_jwt(tenant: str, role: str = "admin") -> str:
    return jwt.encode(
        {
            "sub": "u-al-1", "tenant_id": tenant, "role": role,
            "exp": int(time.time()) + 3600, "iss": "compliance",
        },
        STANDALONE_SECRET, algorithm="HS256",
    )


def _user_headers(tenant: str) -> dict:
    return {"Authorization": f"Bearer {_user_jwt(tenant)}"}


def _aud_headers(access: AuditorAccess) -> dict:
    payload = {
        "sub": access.auditor_email, "kind": "auditor",
        "access_id": access.id, "tenant_id": access.tenant_id,
        "framework_id": access.framework_id,
        "period_start": access.audit_period_start.isoformat(),
        "period_end": access.audit_period_end.isoformat(),
        "exp": int(access.expires_at.timestamp()),
        "iss": "compliance-auditor",
    }
    return {"Authorization": f"Bearer {jwt.encode(payload, STANDALONE_SECRET, algorithm='HS256')}"}


async def _seed(db_session, tenant_id: str) -> tuple[Framework, Control, AuditorAccess]:
    fw = Framework(
        id=str(uuid.uuid4()), name=f"AL-{uuid.uuid4().hex[:4]}",
        short_code=f"AL{uuid.uuid4().hex[:4].upper()}", category="security",
    )
    db_session.add(fw)
    await db_session.flush()
    fv = FrameworkVersion(id=str(uuid.uuid4()), framework_id=fw.id, version="2024", is_current=True)
    db_session.add(fv)
    await db_session.flush()
    ctrl = Control(
        id=str(uuid.uuid4()), framework_version_id=fv.id,
        control_code=f"AL-{uuid.uuid4().hex[:4].upper()}",
        category="AL", description="al ctrl",
    )
    db_session.add(ctrl)
    await db_session.flush()
    now = datetime.utcnow()
    access = AuditorAccess(
        tenant_id=tenant_id, auditor_email="log@x.com", framework_id=fw.id,
        audit_period_start=now - timedelta(days=10),
        audit_period_end=now + timedelta(days=10),
        invited_by_user_id="admin-1",
        invitation_token_hash=f"al-h-{uuid.uuid4()}",
        expires_at=now + timedelta(days=10),
    )
    db_session.add(access)
    await db_session.commit()
    return fw, ctrl, access


# ---------------------------------------------------------------------------
# Each auditor action creates a log entry
# ---------------------------------------------------------------------------

@pytest.mark.anyio
async def test_list_controls_logs_action(client, db_session):
    tenant = f"tenant-al-listc-{uuid.uuid4().hex[:6]}"
    _, _, access = await _seed(db_session, tenant)

    await client.get("/auditor/controls", headers=_aud_headers(access))

    rows = (await db_session.execute(
        select(AuditorActivityLog).where(AuditorActivityLog.tenant_id == tenant)
    )).scalars().all()
    assert len(rows) == 1
    assert rows[0].action == "list_controls"
    assert rows[0].auditor_access_id == access.id


@pytest.mark.anyio
async def test_view_control_logs_target_id(client, db_session):
    tenant = f"tenant-al-viewc-{uuid.uuid4().hex[:6]}"
    _, ctrl, access = await _seed(db_session, tenant)

    await client.get(
        f"/auditor/controls/{ctrl.id}", headers=_aud_headers(access),
    )
    rows = (await db_session.execute(
        select(AuditorActivityLog).where(AuditorActivityLog.tenant_id == tenant)
    )).scalars().all()
    assert len(rows) == 1
    assert rows[0].action == "view_control"
    assert rows[0].target_id == ctrl.id
    assert rows[0].target_type == "control"


@pytest.mark.anyio
async def test_request_evidence_logs_action(client, db_session):
    tenant = f"tenant-al-req-{uuid.uuid4().hex[:6]}"
    _, ctrl, access = await _seed(db_session, tenant)

    await client.post(
        "/auditor/evidence-requests",
        headers=_aud_headers(access),
        json={"description": "X", "control_id": ctrl.id},
    )
    rows = (await db_session.execute(
        select(AuditorActivityLog).where(AuditorActivityLog.tenant_id == tenant)
    )).scalars().all()
    assert len(rows) == 1
    assert rows[0].action == "request_evidence"
    assert rows[0].target_type == "evidence_request"


# ---------------------------------------------------------------------------
# /admin/auditor-activity
# ---------------------------------------------------------------------------

@pytest.mark.anyio
async def test_admin_can_view_activity_log(client, db_session):
    tenant = f"tenant-al-adminview-{uuid.uuid4().hex[:6]}"
    _, _, access = await _seed(db_session, tenant)

    await client.get("/auditor/controls", headers=_aud_headers(access))
    await client.get("/auditor/evidence", headers=_aud_headers(access))

    resp = await client.get(
        "/admin/auditor-activity", headers=_user_headers(tenant),
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    actions = {r["action"] for r in body}
    assert "list_controls" in actions
    assert "list_evidence" in actions


@pytest.mark.anyio
async def test_admin_activity_is_tenant_scoped(client, db_session):
    tenant_a = f"tenant-al-A-{uuid.uuid4().hex[:6]}"
    tenant_b = f"tenant-al-B-{uuid.uuid4().hex[:6]}"
    _, _, access_a = await _seed(db_session, tenant_a)
    _, _, access_b = await _seed(db_session, tenant_b)

    await client.get("/auditor/controls", headers=_aud_headers(access_a))
    await client.get("/auditor/controls", headers=_aud_headers(access_b))

    resp_a = await client.get(
        "/admin/auditor-activity", headers=_user_headers(tenant_a),
    )
    rows_a = resp_a.json()
    assert all(r["tenant_id"] == tenant_a for r in rows_a)


@pytest.mark.anyio
async def test_admin_activity_requires_admin_role(client, db_session):
    tenant = f"tenant-al-role-{uuid.uuid4().hex[:6]}"
    _, _, access = await _seed(db_session, tenant)

    headers = {"Authorization": f"Bearer {_user_jwt(tenant, role='viewer')}"}
    resp = await client.get("/admin/auditor-activity", headers=headers)
    assert resp.status_code == 403


# ---------------------------------------------------------------------------
# /admin/auditor-activity/heatmap
# ---------------------------------------------------------------------------
@pytest.mark.anyio
async def test_heatmap_returns_30_day_window_with_zero_filled(client, db_session):
    tenant = f"tenant-al-hm-{uuid.uuid4().hex[:6]}"
    _, _, access = await _seed(db_session, tenant)
    await client.get("/auditor/controls", headers=_aud_headers(access))

    resp = await client.get("/admin/auditor-activity/heatmap", headers=_user_headers(tenant))
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["days_window"] == 30
    assert len(body["days"]) == 30
    # Sum of per-day counts equals total
    assert sum(d["count"] for d in body["days"]) == body["total_actions"]
    # Latest day has at least one action (we just hit /auditor/controls).
    today = body["days"][-1]
    assert today["count"] >= 1
    assert today["actions"].get("list_controls", 0) >= 1


@pytest.mark.anyio
async def test_heatmap_respects_days_param(client, db_session):
    tenant = f"tenant-al-hm2-{uuid.uuid4().hex[:6]}"
    await _seed(db_session, tenant)

    resp = await client.get(
        "/admin/auditor-activity/heatmap?days=7", headers=_user_headers(tenant),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["days_window"] == 7
    assert len(body["days"]) == 7


@pytest.mark.anyio
async def test_heatmap_admin_role_required(client, db_session):
    tenant = f"tenant-al-hm3-{uuid.uuid4().hex[:6]}"
    await _seed(db_session, tenant)
    headers = {"Authorization": f"Bearer {_user_jwt(tenant, role='viewer')}"}
    resp = await client.get("/admin/auditor-activity/heatmap", headers=headers)
    assert resp.status_code == 403
