"""
TDD — Evidence-request flow (P2B.10).

Auditor creates a request → admin sees pending requests → admin fulfils
by linking an Evidence record. Once fulfilled, the auditor's view shows
fulfillment metadata.
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
from compliance_backend.models.auditor import (
    AuditorAccess,
    EvidenceRequest,
)

STANDALONE_SECRET = "test-secret-standalone"


def _user_jwt(tenant: str, role: str = "admin") -> str:
    return jwt.encode(
        {
            "sub": "u-er-1", "tenant_id": tenant, "role": role,
            "exp": int(time.time()) + 3600, "iss": "compliance",
        },
        STANDALONE_SECRET, algorithm="HS256",
    )


def _user_headers(tenant: str = "tenant-er-flow") -> dict:
    return {"Authorization": f"Bearer {_user_jwt(tenant)}"}


def _auditor_jwt(access: AuditorAccess) -> str:
    return jwt.encode(
        {
            "sub": access.auditor_email, "kind": "auditor",
            "access_id": access.id, "tenant_id": access.tenant_id,
            "framework_id": access.framework_id,
            "period_start": access.audit_period_start.isoformat(),
            "period_end": access.audit_period_end.isoformat(),
            "exp": int(access.expires_at.timestamp()),
            "iss": "compliance-auditor",
        },
        STANDALONE_SECRET, algorithm="HS256",
    )


def _aud_headers(access: AuditorAccess) -> dict:
    return {"Authorization": f"Bearer {_auditor_jwt(access)}"}


async def _seed(db_session, tenant_suffix: str = "") -> tuple[Framework, Control, AuditorAccess]:
    tenant_id = f"tenant-er-{tenant_suffix or uuid.uuid4().hex[:6]}"
    fw = Framework(
        id=str(uuid.uuid4()),
        name=f"ER-{uuid.uuid4().hex[:4]}",
        short_code=f"ER{uuid.uuid4().hex[:4].upper()}",
        category="security",
    )
    db_session.add(fw)
    await db_session.flush()
    fv = FrameworkVersion(
        id=str(uuid.uuid4()), framework_id=fw.id, version="2024", is_current=True,
    )
    db_session.add(fv)
    await db_session.flush()
    ctrl = Control(
        id=str(uuid.uuid4()), framework_version_id=fv.id,
        control_code=f"ER-{uuid.uuid4().hex[:4].upper()}",
        category="ER", description="er ctrl",
    )
    db_session.add(ctrl)
    await db_session.flush()
    now = datetime.utcnow()
    access = AuditorAccess(
        tenant_id=tenant_id,
        auditor_email="er@x.com",
        framework_id=fw.id,
        audit_period_start=now - timedelta(days=10),
        audit_period_end=now + timedelta(days=10),
        invited_by_user_id="admin-1",
        invitation_token_hash=f"er-h-{uuid.uuid4()}",
        expires_at=now + timedelta(days=10),
    )
    db_session.add(access)
    await db_session.flush()
    await db_session.commit()
    return fw, ctrl, access


# ---------------------------------------------------------------------------
# Auditor → request → DB row exists
# ---------------------------------------------------------------------------

@pytest.mark.anyio
async def test_auditor_request_creates_pending_record(client, db_session):
    fw, ctrl, access = await _seed(db_session)
    resp = await client.post(
        "/auditor/evidence-requests",
        headers=_aud_headers(access),
        json={"description": "Show me Q1 logs", "control_id": ctrl.id},
    )
    assert resp.status_code == 201
    rows = (await db_session.execute(
        select(EvidenceRequest).where(EvidenceRequest.auditor_access_id == access.id)
    )).scalars().all()
    assert len(rows) == 1
    assert rows[0].fulfilled_at is None
    assert rows[0].fulfillment_evidence_id is None


# ---------------------------------------------------------------------------
# Admin sees the request via /admin/evidence-requests (list-only is enough for now)
# ---------------------------------------------------------------------------

@pytest.mark.anyio
async def test_admin_can_list_pending_requests(client, db_session):
    fw, ctrl, access = await _seed(db_session)
    # Auditor creates 2 requests
    for desc in ["Need A", "Need B"]:
        await client.post(
            "/auditor/evidence-requests",
            headers=_aud_headers(access),
            json={"description": desc, "control_id": ctrl.id},
        )

    resp = await client.get(
        "/admin/evidence-requests", headers=_user_headers(access.tenant_id),
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert len(body) == 2
    descs = {r["description"] for r in body}
    assert descs == {"Need A", "Need B"}


@pytest.mark.anyio
async def test_admin_list_requires_admin_role(client, db_session):
    fw, ctrl, access = await _seed(db_session)
    headers = {"Authorization": f"Bearer {_user_jwt(access.tenant_id, role='viewer')}"}
    resp = await client.get("/admin/evidence-requests", headers=headers)
    assert resp.status_code == 403


# ---------------------------------------------------------------------------
# Admin fulfilment marks fulfilled_at + fulfillment_evidence_id
# ---------------------------------------------------------------------------

@pytest.mark.anyio
async def test_admin_can_fulfil_request(client, db_session):
    fw, ctrl, access = await _seed(db_session)
    # Auditor creates request
    create_resp = await client.post(
        "/auditor/evidence-requests",
        headers=_aud_headers(access),
        json={"description": "Need this", "control_id": ctrl.id},
    )
    request_id = create_resp.json()["id"]

    # Admin uploads evidence (gets ev_id)
    upload = await client.post(
        "/evidence",
        headers=_user_headers(access.tenant_id),
        files={"file": ("doc.txt", io.BytesIO(b"data"), "text/plain")},
        data={"control_id": ctrl.id, "evidence_type": "document",
              "framework_id": fw.id, "audit_period": "2026"},
    )
    ev_id = upload.json()["id"]

    # Admin fulfils
    fulfil_resp = await client.post(
        f"/admin/evidence-requests/{request_id}/fulfil",
        headers=_user_headers(access.tenant_id),
        json={"evidence_id": ev_id},
    )
    assert fulfil_resp.status_code == 200, fulfil_resp.text

    # Verify
    rec = (await db_session.execute(
        select(EvidenceRequest).where(EvidenceRequest.id == request_id)
    )).scalar_one()
    assert rec.fulfilled_at is not None
    assert rec.fulfillment_evidence_id == ev_id


@pytest.mark.anyio
async def test_admin_cannot_fulfil_other_tenants_request(client, db_session):
    fw, ctrl, access = await _seed(db_session)
    create_resp = await client.post(
        "/auditor/evidence-requests",
        headers=_aud_headers(access),
        json={"description": "X", "control_id": ctrl.id},
    )
    request_id = create_resp.json()["id"]

    # Different tenant tries to fulfil
    resp = await client.post(
        f"/admin/evidence-requests/{request_id}/fulfil",
        headers=_user_headers("tenant-different"),
        json={"evidence_id": "fake"},
    )
    assert resp.status_code == 404
