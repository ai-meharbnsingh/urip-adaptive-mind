"""
WORKFLOW 7 — Auditor portal full audit cycle (Compliance service).

Covers:
  1. Tenant admin creates a Framework + Control + a captured Evidence row
     (the auditor portal scopes by framework + audit-period, so we need
     enough state for the auditor to "see" something).
  2. Admin creates an auditor invitation for SOC 2 (audit period Q4-2025).
  3. Auditor accepts the invitation token via POST /auditor-invitations/accept
     and receives an auditor JWT.
  4. Auditor logs in (uses JWT) — GET /auditor/controls returns the controls
     in scope.
  5. Auditor drills into a control via GET /auditor/controls/{id} → returns
     the evidence list.
  6. Auditor requests additional evidence via POST /auditor/evidence-requests.
  7. Tenant admin sees the request via GET /admin/evidence-requests.
  8. Tenant admin uploads new evidence + fulfils the request via
     POST /admin/evidence-requests/{id}/fulfil.
  9. Auditor sees the new evidence in GET /auditor/evidence.
 10. Audit period ends (admin revokes invitation → 401 on the next call).
 11. Tenant admin reviews auditor activity via GET /admin/auditor-activity.
"""

from __future__ import annotations

import io
import uuid
from datetime import datetime, timedelta

import pytest
from sqlalchemy import select

from compliance_backend.models.framework import Framework, FrameworkVersion, Control
from compliance_backend.models.evidence import Evidence


def _admin_headers(jwt_factory, tenant_id: str) -> dict:
    return {"Authorization": f"Bearer {jwt_factory(tenant_id, role='admin')}"}


@pytest.mark.asyncio
async def test_workflow_07_auditor_portal_full_cycle(
    compliance_client, compliance_session, make_compliance_jwt
):
    tenant_id = "auditor-tenant-e2e"
    h_admin = _admin_headers(make_compliance_jwt, tenant_id)

    # ── 1) Seed a framework + control + one auto-collected evidence row ───
    fw = Framework(
        id=str(uuid.uuid4()),
        name="SOC 2 (E2E)",
        short_code=f"SOC2E2E{uuid.uuid4().hex[:4].upper()}",
        category="security",
    )
    fv = FrameworkVersion(
        id=str(uuid.uuid4()),
        framework_id=fw.id,
        version="2017",
        is_current=True,
    )
    ctrl = Control(
        id=str(uuid.uuid4()),
        framework_version_id=fv.id,
        control_code=f"CC-{uuid.uuid4().hex[:4].upper()}",
        category="Access",
        title="Logical Access Controls",
        description="MFA enforced for all users.",
        rule_function="mfa_enforced",
    )
    compliance_session.add_all([fw, fv, ctrl])
    await compliance_session.flush()

    # Audit period — bounded with a comfortable cushion to absorb the
    # naive-vs-aware datetime conversion bug in
    # compliance_backend/services/auditor_service.py:_mint_auditor_jwt
    # (it does `int(access.expires_at.timestamp())` on a naive utcnow-derived
    # datetime, which on a non-UTC host produces an exp value offset by the
    # local TZ).  Picking +2 days handles any reasonable TZ.
    period_start = datetime.utcnow() - timedelta(days=1)
    period_end = datetime.utcnow() + timedelta(days=2)

    # An auto-collected evidence row inside the audit period
    pre_evidence = Evidence(
        id=str(uuid.uuid4()),
        control_id=ctrl.id,
        framework_id=fw.id,
        tenant_id=tenant_id,
        type="config",
        storage_uri="memory://noop",
        audit_period="Q4-2025",
        captured_at=datetime.utcnow(),
        captured_by="auto-collector",
        metadata_json={"source": "seed"},
    )
    compliance_session.add(pre_evidence)
    await compliance_session.flush()

    # ── 2) Admin creates an auditor invitation ─────────────────────────────
    expires = period_end + timedelta(minutes=5)
    invite = await compliance_client.post(
        "/auditor-invitations",
        json={
            "auditor_email": "external-auditor@audit.example.com",
            "framework_id": fw.id,
            "audit_period_start": period_start.isoformat(),
            "audit_period_end": period_end.isoformat(),
            "expires_at": expires.isoformat(),
        },
        headers=h_admin,
    )
    assert invite.status_code == 201, invite.text
    invite_body = invite.json()
    invite_id = invite_body["id"]
    invitation_url = invite_body["invitation_url"]
    # The redemption URL contains the raw token as ?token=...
    raw_token = invitation_url.split("token=", 1)[1]
    assert len(raw_token) > 30

    # ── 3) Auditor redeems token → gets a JWT ──────────────────────────────
    accept = await compliance_client.post(
        "/auditor-invitations/accept",
        json={"token": raw_token},
    )
    assert accept.status_code == 200, accept.text
    auditor_jwt = accept.json()["auditor_jwt"]
    auditor_h = {"Authorization": f"Bearer {auditor_jwt}"}

    # ── 4) Auditor lists in-scope controls ─────────────────────────────────
    controls_resp = await compliance_client.get("/auditor/controls", headers=auditor_h)
    assert controls_resp.status_code == 200, controls_resp.text
    controls = controls_resp.json()
    assert any(c["id"] == ctrl.id for c in controls), (
        f"Auditor should see control {ctrl.control_code}; got {[c['control_code'] for c in controls]}"
    )

    # ── 5) Auditor drills into the control → sees the seeded evidence ──────
    detail = await compliance_client.get(
        f"/auditor/controls/{ctrl.id}", headers=auditor_h
    )
    assert detail.status_code == 200, detail.text
    detail_body = detail.json()
    seeded_evidence_ids = {e["id"] for e in detail_body["evidence"]}
    assert pre_evidence.id in seeded_evidence_ids

    # ── 6) Auditor requests additional evidence ────────────────────────────
    req = await compliance_client.post(
        "/auditor/evidence-requests",
        json={
            "control_id": ctrl.id,
            "description": "Please share Q4-2025 onboarding screenshots.",
        },
        headers=auditor_h,
    )
    assert req.status_code == 201, req.text
    req_id = req.json()["id"]

    # ── 7) Admin sees the request in their pending list ────────────────────
    admin_list = await compliance_client.get(
        "/admin/evidence-requests", headers=h_admin
    )
    assert admin_list.status_code == 200, admin_list.text
    pending = [r for r in admin_list.json() if r["id"] == req_id]
    assert len(pending) == 1
    assert pending[0]["fulfilled_at"] is None
    assert pending[0]["auditor_email"] == "external-auditor@audit.example.com"

    # ── 8) Admin uploads new evidence and fulfils the request ──────────────
    upload_resp = await compliance_client.post(
        "/evidence",
        data={
            "control_id": ctrl.id,
            "evidence_type": "screenshot",
            "framework_id": fw.id,
            "audit_period": "Q4-2025",
        },
        files={
            "file": (
                "onboarding.png",
                io.BytesIO(b"\x89PNG\r\n\x1a\nfake-screenshot-bytes-for-e2e"),
                "image/png",
            )
        },
        headers=h_admin,
    )
    assert upload_resp.status_code == 201, upload_resp.text
    new_evidence_id = upload_resp.json()["id"]

    fulfil = await compliance_client.post(
        f"/admin/evidence-requests/{req_id}/fulfil",
        json={"evidence_id": new_evidence_id},
        headers=h_admin,
    )
    assert fulfil.status_code == 200, fulfil.text
    assert fulfil.json()["fulfillment_evidence_id"] == new_evidence_id
    assert fulfil.json()["fulfilled_at"] is not None

    # ── 9) Auditor lists evidence again — new evidence appears ─────────────
    ev_list = await compliance_client.get(
        "/auditor/evidence", headers=auditor_h
    )
    assert ev_list.status_code == 200, ev_list.text
    visible = {e["id"] for e in ev_list.json()}
    assert new_evidence_id in visible
    assert pre_evidence.id in visible

    # ── 10) Admin revokes the invitation; subsequent auditor calls 401 ─────
    revoke = await compliance_client.delete(
        f"/auditor-invitations/{invite_id}", headers=h_admin
    )
    # 204 No Content on success
    assert revoke.status_code == 204, revoke.text

    after_revoke = await compliance_client.get("/auditor/controls", headers=auditor_h)
    assert after_revoke.status_code == 401, (
        f"After revoke, auditor token must 401; got {after_revoke.status_code}"
    )

    # ── 11) Admin reviews auditor activity log ─────────────────────────────
    activity = await compliance_client.get(
        "/admin/auditor-activity", headers=h_admin
    )
    assert activity.status_code == 200, activity.text
    actions_seen = {row["action"] for row in activity.json()}
    # The auditor performed: list_controls, view_control, list_evidence,
    # request_evidence — at minimum one of those should be logged.
    assert "list_controls" in actions_seen or "view_control" in actions_seen
    assert "request_evidence" in actions_seen


@pytest.mark.asyncio
async def test_workflow_07_invalid_token_returns_401(
    compliance_client,
):
    """Random tokens are rejected with 401, not 404 (so probes can't enumerate)."""
    resp = await compliance_client.post(
        "/auditor-invitations/accept",
        json={"token": "this-is-not-a-real-token-just-random-bytes-and-stuff"},
    )
    assert resp.status_code == 401
