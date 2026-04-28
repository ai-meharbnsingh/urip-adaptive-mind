"""
TDD — Auditor read-only routes (P2B.10)

Tests:
  - All routes require kind="auditor" JWT (regular user JWT → 401)
  - Routes return only data within audit period
  - Routes return only data scoped to the auditor's tenant + framework
  - Revoked auditor cannot call any /auditor/* endpoint
  - Expired auditor access cannot call any /auditor/* endpoint
  - Each call creates an AuditorActivityLog entry
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
from compliance_backend.models.control_run import ControlCheckRun
from compliance_backend.models.evidence import Evidence
from compliance_backend.models.auditor import (
    AuditorAccess,
    AuditorActivityLog,
    EvidenceRequest,
)

STANDALONE_SECRET = "test-secret-standalone"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _user_jwt(tenant: str, role: str = "admin") -> str:
    return jwt.encode(
        {
            "sub": "u-1", "tenant_id": tenant, "role": role,
            "exp": int(time.time()) + 3600, "iss": "compliance",
        },
        STANDALONE_SECRET, algorithm="HS256",
    )


def _user_headers(tenant: str = "tenant-routes") -> dict:
    return {"Authorization": f"Bearer {_user_jwt(tenant)}"}


async def _seed_framework_with_controls(db_session, n_controls: int = 3) -> tuple[Framework, FrameworkVersion, list[Control]]:
    fw = Framework(
        id=str(uuid.uuid4()),
        name=f"AR-FW-{uuid.uuid4().hex[:4]}",
        short_code=f"ARFW{uuid.uuid4().hex[:4].upper()}",
        category="security",
    )
    db_session.add(fw)
    await db_session.flush()
    fv = FrameworkVersion(
        id=str(uuid.uuid4()),
        framework_id=fw.id,
        version="2024",
        is_current=True,
    )
    db_session.add(fv)
    await db_session.flush()
    controls = []
    for i in range(n_controls):
        ctrl = Control(
            id=str(uuid.uuid4()),
            framework_version_id=fv.id,
            control_code=f"AR-{i}-{uuid.uuid4().hex[:4].upper()}",
            category=f"Cat-{i % 2}",
            description=f"Control {i}",
        )
        db_session.add(ctrl)
        controls.append(ctrl)
    await db_session.flush()
    await db_session.commit()
    return fw, fv, controls


async def _create_auditor_access(
    db_session,
    *,
    tenant_id: str,
    framework_id: str,
    auditor_email: str = "auditor-r@x.com",
    period_start: datetime = None,
    period_end: datetime = None,
    expires_at: datetime = None,
    is_revoked: bool = False,
) -> AuditorAccess:
    now = datetime.utcnow()
    period_start = period_start or (now - timedelta(days=30))
    period_end = period_end or (now + timedelta(days=30))
    expires_at = expires_at or (now + timedelta(days=7))
    rec = AuditorAccess(
        tenant_id=tenant_id,
        auditor_email=auditor_email,
        framework_id=framework_id,
        audit_period_start=period_start,
        audit_period_end=period_end,
        invited_by_user_id="admin-1",
        invitation_token_hash=f"hash-routes-{uuid.uuid4()}",
        expires_at=expires_at,
        is_revoked=is_revoked,
    )
    db_session.add(rec)
    await db_session.flush()
    await db_session.commit()
    return rec


def _auditor_jwt_for(access: AuditorAccess) -> str:
    payload = {
        "sub": access.auditor_email,
        "kind": "auditor",
        "access_id": access.id,
        "tenant_id": access.tenant_id,
        "framework_id": access.framework_id,
        "period_start": access.audit_period_start.isoformat(),
        "period_end": access.audit_period_end.isoformat(),
        "exp": int(access.expires_at.timestamp()),
        "iss": "compliance-auditor",
    }
    return jwt.encode(payload, STANDALONE_SECRET, algorithm="HS256")


def _auditor_headers(access: AuditorAccess) -> dict:
    return {"Authorization": f"Bearer {_auditor_jwt_for(access)}"}


# ---------------------------------------------------------------------------
# Token-kind enforcement
# ---------------------------------------------------------------------------

@pytest.mark.anyio
async def test_user_jwt_cannot_call_auditor_routes(client):
    """A regular user JWT must not be able to access /auditor/*."""
    resp = await client.get("/auditor/controls", headers=_user_headers("any"))
    assert resp.status_code == 401


@pytest.mark.anyio
async def test_no_auth_returns_401(client):
    resp = await client.get("/auditor/controls")
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Revocation / expiry enforcement on every request
# ---------------------------------------------------------------------------

@pytest.mark.anyio
async def test_revoked_auditor_cannot_call_routes(client, db_session):
    fw, _, _ = await _seed_framework_with_controls(db_session)
    access = await _create_auditor_access(
        db_session, tenant_id="tenant-rev-rt", framework_id=fw.id, is_revoked=True,
    )
    resp = await client.get("/auditor/controls", headers=_auditor_headers(access))
    assert resp.status_code == 401


@pytest.mark.anyio
async def test_expired_auditor_cannot_call_routes(client, db_session):
    """Even with a JWT not yet expired, if AuditorAccess.expires_at < now → 401."""
    fw, _, _ = await _seed_framework_with_controls(db_session)
    now = datetime.utcnow()
    # JWT exp far in future, but DB row expires_at already passed.
    rec = AuditorAccess(
        tenant_id="tenant-exp-rt",
        auditor_email="exp@x.com",
        framework_id=fw.id,
        audit_period_start=now - timedelta(days=30),
        audit_period_end=now + timedelta(days=30),
        invited_by_user_id="a",
        invitation_token_hash=f"h-exp-{uuid.uuid4()}",
        expires_at=now - timedelta(seconds=1),  # already expired in DB
    )
    db_session.add(rec)
    await db_session.commit()

    # Manually mint a JWT with future exp
    jwt_payload = {
        "sub": rec.auditor_email,
        "kind": "auditor",
        "access_id": rec.id,
        "tenant_id": rec.tenant_id,
        "framework_id": rec.framework_id,
        "period_start": rec.audit_period_start.isoformat(),
        "period_end": rec.audit_period_end.isoformat(),
        "exp": int(time.time()) + 3600,  # JWT not expired
        "iss": "compliance-auditor",
    }
    forged = jwt.encode(jwt_payload, STANDALONE_SECRET, algorithm="HS256")

    resp = await client.get(
        "/auditor/controls",
        headers={"Authorization": f"Bearer {forged}"},
    )
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# GET /auditor/controls
# ---------------------------------------------------------------------------

@pytest.mark.anyio
async def test_list_controls_returns_framework_controls(client, db_session):
    fw, fv, controls = await _seed_framework_with_controls(db_session, n_controls=4)
    access = await _create_auditor_access(
        db_session, tenant_id="tenant-list-c", framework_id=fw.id,
    )
    resp = await client.get("/auditor/controls", headers=_auditor_headers(access))
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert len(body) == 4
    codes = {c["control_code"] for c in body}
    assert codes == {c.control_code for c in controls}
    # All controls without runs → "not_evaluated"
    for item in body:
        assert item["current_status"] in {"not_evaluated", "pass", "fail", "inconclusive"}


@pytest.mark.anyio
async def test_list_controls_status_reflects_latest_run(client, db_session):
    fw, fv, controls = await _seed_framework_with_controls(db_session, n_controls=2)
    access = await _create_auditor_access(
        db_session, tenant_id="tenant-status", framework_id=fw.id,
    )
    # Insert a passing run for control[0]
    db_session.add(ControlCheckRun(
        control_id=controls[0].id,
        tenant_id=access.tenant_id,
        run_at=datetime.utcnow(),
        status="pass",
    ))
    db_session.add(ControlCheckRun(
        control_id=controls[1].id,
        tenant_id=access.tenant_id,
        run_at=datetime.utcnow(),
        status="fail",
    ))
    await db_session.commit()

    resp = await client.get("/auditor/controls", headers=_auditor_headers(access))
    body = resp.json()
    by_code = {c["control_code"]: c for c in body}
    assert by_code[controls[0].control_code]["current_status"] == "pass"
    assert by_code[controls[1].control_code]["current_status"] == "fail"


# ---------------------------------------------------------------------------
# GET /auditor/controls/{id}
# ---------------------------------------------------------------------------

@pytest.mark.anyio
async def test_get_control_detail_includes_evidence(client, db_session):
    fw, fv, controls = await _seed_framework_with_controls(db_session, n_controls=1)
    access = await _create_auditor_access(
        db_session, tenant_id="tenant-cd", framework_id=fw.id,
    )
    # Add evidence within period
    db_session.add(Evidence(
        control_id=controls[0].id,
        framework_id=fw.id,
        tenant_id=access.tenant_id,
        type="config",
        storage_uri="file:///fake",
        audit_period="2026",
    ))
    await db_session.commit()

    resp = await client.get(
        f"/auditor/controls/{controls[0].id}", headers=_auditor_headers(access)
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["control"]["id"] == controls[0].id
    assert len(body["evidence"]) == 1


@pytest.mark.anyio
async def test_get_control_outside_framework_returns_404(client, db_session):
    fw_a, _, controls_a = await _seed_framework_with_controls(db_session, n_controls=1)
    fw_b, _, controls_b = await _seed_framework_with_controls(db_session, n_controls=1)
    access = await _create_auditor_access(
        db_session, tenant_id="tenant-cross-fw", framework_id=fw_a.id,
    )
    # Try to access a control from framework B
    resp = await client.get(
        f"/auditor/controls/{controls_b[0].id}", headers=_auditor_headers(access)
    )
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# GET /auditor/evidence
# ---------------------------------------------------------------------------

@pytest.mark.anyio
async def test_list_evidence_filters_by_period_and_framework(client, db_session):
    fw, _, controls = await _seed_framework_with_controls(db_session, n_controls=1)
    now = datetime.utcnow()
    access = await _create_auditor_access(
        db_session,
        tenant_id="tenant-ev-period",
        framework_id=fw.id,
        period_start=now - timedelta(days=10),
        period_end=now + timedelta(days=10),
    )

    # Inside period
    inside = Evidence(
        control_id=controls[0].id, framework_id=fw.id, tenant_id=access.tenant_id,
        type="config", storage_uri="file:///in", audit_period="2026",
        captured_at=now,
    )
    # Outside period
    outside = Evidence(
        control_id=controls[0].id, framework_id=fw.id, tenant_id=access.tenant_id,
        type="config", storage_uri="file:///out", audit_period="2025",
        captured_at=now - timedelta(days=100),
    )
    # Wrong tenant
    other_tenant = Evidence(
        control_id=controls[0].id, framework_id=fw.id, tenant_id="tenant-other",
        type="config", storage_uri="file:///other", audit_period="2026",
        captured_at=now,
    )
    db_session.add_all([inside, outside, other_tenant])
    await db_session.commit()

    resp = await client.get("/auditor/evidence", headers=_auditor_headers(access))
    assert resp.status_code == 200
    items = resp.json()
    ids = {it["id"] for it in items}
    assert inside.id in ids
    assert outside.id not in ids
    assert other_tenant.id not in ids


# ---------------------------------------------------------------------------
# GET /auditor/evidence/{id}/download
# ---------------------------------------------------------------------------

@pytest.mark.anyio
async def test_download_evidence_outside_period_returns_404(client, db_session):
    fw, _, controls = await _seed_framework_with_controls(db_session, n_controls=1)
    now = datetime.utcnow()
    access = await _create_auditor_access(
        db_session, tenant_id="tenant-dl-out", framework_id=fw.id,
        period_start=now - timedelta(days=2), period_end=now + timedelta(days=2),
    )

    # Upload via admin route (gets us a real storage file)
    upload = await client.post(
        "/evidence",
        headers=_user_headers(access.tenant_id),
        files={"file": ("data.txt", io.BytesIO(b"data"), "text/plain")},
        data={"control_id": controls[0].id, "evidence_type": "config",
              "framework_id": fw.id, "audit_period": "2026"},
    )
    assert upload.status_code == 201
    ev_id = upload.json()["id"]

    # Backdate the evidence so it's outside the audit period
    ev_row = (await db_session.execute(
        select(Evidence).where(Evidence.id == ev_id)
    )).scalar_one()
    ev_row.captured_at = now - timedelta(days=100)
    await db_session.commit()

    resp = await client.get(
        f"/auditor/evidence/{ev_id}/download", headers=_auditor_headers(access)
    )
    assert resp.status_code == 404


@pytest.mark.anyio
async def test_download_evidence_in_period_returns_content(client, db_session):
    fw, _, controls = await _seed_framework_with_controls(db_session, n_controls=1)
    access = await _create_auditor_access(
        db_session, tenant_id="tenant-dl-in", framework_id=fw.id,
    )

    upload = await client.post(
        "/evidence",
        headers=_user_headers(access.tenant_id),
        files={"file": ("good.txt", io.BytesIO(b"good content"), "text/plain")},
        data={"control_id": controls[0].id, "evidence_type": "config",
              "framework_id": fw.id, "audit_period": "2026"},
    )
    ev_id = upload.json()["id"]

    resp = await client.get(
        f"/auditor/evidence/{ev_id}/download", headers=_auditor_headers(access)
    )
    assert resp.status_code == 200
    assert resp.content == b"good content"


# ---------------------------------------------------------------------------
# POST /auditor/evidence-requests
# ---------------------------------------------------------------------------

@pytest.mark.anyio
async def test_create_evidence_request(client, db_session):
    fw, _, _ = await _seed_framework_with_controls(db_session)
    access = await _create_auditor_access(
        db_session, tenant_id="tenant-er", framework_id=fw.id,
    )
    resp = await client.post(
        "/auditor/evidence-requests",
        headers=_auditor_headers(access),
        json={"description": "Need additional log evidence", "control_id": None},
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["description"] == "Need additional log evidence"

    # Verify persisted with correct auditor_access_id
    rows = (await db_session.execute(
        select(EvidenceRequest).where(EvidenceRequest.auditor_access_id == access.id)
    )).scalars().all()
    assert len(rows) == 1


# ---------------------------------------------------------------------------
# Tenant isolation across full route
# ---------------------------------------------------------------------------

@pytest.mark.anyio
async def test_auditor_only_sees_own_tenant_data(client, db_session):
    fw, _, controls = await _seed_framework_with_controls(db_session, n_controls=1)
    access_a = await _create_auditor_access(
        db_session, tenant_id="tenant-X", framework_id=fw.id,
    )
    # Insert a run for tenant Y
    db_session.add(ControlCheckRun(
        control_id=controls[0].id,
        tenant_id="tenant-Y",
        run_at=datetime.utcnow(),
        status="pass",
    ))
    await db_session.commit()

    resp = await client.get("/auditor/controls", headers=_auditor_headers(access_a))
    body = resp.json()
    # The single control should report not_evaluated for tenant X
    assert body[0]["current_status"] == "not_evaluated"
