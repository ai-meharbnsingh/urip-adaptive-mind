"""
WORKFLOW 4 — URIP risk resolved → compliance re-evaluation (cross-service).

End-to-end shape:
  1. A URIP risk is created and linked to a Compliance control (we encode
     the control_id in the risk's `asset` field — the same convention used
     by workflow 3 until a dedicated `linked_control_id` column exists).
  2. The risk is marked resolved (acceptance approved → status="accepted").
  3. URIP WOULD emit a `urip.risk.resolved` event on the shared bus.
  4. Compliance subscriber receives the event and triggers a new control
     run for the linked control with a passing config.
  5. The new control run returns status="pass".
  6. The framework score recalculates upward (was 0% before the resolution,
     becomes 100% after).

Honesty / scope notes:
  Same as workflow 3 — the publisher / subscriber are NOT yet wired in
  source code today.  This test exercises the schema contract + the round-
  trip behaviour: emit RiskResolvedPayload, parse it on the compliance
  side, run the control again, observe the score change.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy import select

from compliance_backend.models.framework import Framework, FrameworkVersion, Control
from compliance_backend.models.tenant_state import TenantConfig
from compliance_backend.services.scoring_engine import ScoringEngine
from compliance_backend.services.control_rules import load_builtin_rules

from shared.events.topics import (
    TOPIC_RISK_RESOLVED,
    RiskResolvedPayload,
)

from backend.middleware.auth import create_access_token, hash_password
from backend.middleware.tenant import TenantContext
from backend.models.subscription import TenantSubscription
from backend.models.tenant import Tenant
from backend.models.user import User


def _comp_admin_headers(jwt_factory, tenant_id: str) -> dict:
    return {"Authorization": f"Bearer {jwt_factory(tenant_id, role='admin')}"}


@pytest.mark.asyncio
async def test_workflow_04_risk_resolved_triggers_re_evaluation(
    compliance_client,
    compliance_session,
    urip_client,
    urip_session,
    make_compliance_jwt,
    event_bus,
):
    load_builtin_rules()
    tenant_id = "wf4-tenant"
    h_comp = _comp_admin_headers(make_compliance_jwt, tenant_id)

    # ── Compliance: framework + ONE control wired to mfa_enforced ──────────
    fw = Framework(
        id=str(uuid.uuid4()),
        name="WF4 FW",
        short_code=f"WF4{uuid.uuid4().hex[:4].upper()}",
        category="security",
    )
    fv = FrameworkVersion(
        id=str(uuid.uuid4()),
        framework_id=fw.id,
        version="2024",
        is_current=True,
    )
    ctrl = Control(
        id=str(uuid.uuid4()),
        framework_version_id=fv.id,
        control_code="WF4-CC",
        category="Access",
        description="MFA control under WF4",
        rule_function="mfa_enforced",
    )
    compliance_session.add_all([fw, fv, ctrl])
    await compliance_session.flush()

    # CRIT-006 — control engine no longer accepts caller-supplied tenant_config.
    # Seed mfa_enabled=False in the server-side tenant_config so the first
    # run deterministically fails. Later we'll update this row to flip to True.
    tenant_cfg = TenantConfig(tenant_id=tenant_id, settings={"mfa_enabled": False})
    compliance_session.add(tenant_cfg)
    await compliance_session.commit()

    # Make the control fail first → score = 0% so we can observe it climb.
    bad_run = await compliance_client.post(
        f"/controls/{ctrl.id}/run",
        json={},
        headers=h_comp,
    )
    assert bad_run.status_code == 201
    assert bad_run.json()["status"] == "fail"

    # Pre-state score: 0/(0+1)=0 (1 failing control, 0 passing)
    score_before = await compliance_client.get(
        f"/compliance-score/{fw.short_code}", headers=h_comp
    )
    assert score_before.status_code == 200
    pre = score_before.json()["summary"]
    assert pre["score"] == 0.0
    assert pre["fail_count"] == 1

    # ── URIP: tenant + risk linked to the control via asset field ──────────
    urip_tenant_uuid = uuid.uuid5(uuid.NAMESPACE_DNS, tenant_id)
    urip_tenant = Tenant(
        id=urip_tenant_uuid,
        name="WF4 URIP",
        slug="wf4-urip",
        domain="wf4-urip.example.com",
        is_active=True,
        settings={},
    )
    urip_user = User(
        id=uuid.uuid4(),
        email="wf4-it@wf4-urip.example.com",
        hashed_password=hash_password("WF4#Pass1"),
        full_name="WF4 IT",
        role="ciso",  # ciso so we can also approve acceptance
        is_active=True,
        tenant_id=urip_tenant_uuid,
    )
    urip_session.add_all([
        urip_tenant,
        urip_user,
        TenantSubscription(
            id=uuid.uuid4(),
            tenant_id=urip_tenant_uuid,
            module_code="VM",
            is_enabled=True,
            billing_tier="STANDARD",
        ),
    ])
    await urip_session.commit()
    urip_token = create_access_token(
        str(urip_user.id), urip_user.role, tenant_id=str(urip_tenant_uuid)
    )
    urip_h = {"Authorization": f"Bearer {urip_token}"}

    # IT user (separate role) for risk creation + acceptance request
    it_user = User(
        id=uuid.uuid4(),
        email="wf4-itteam@wf4-urip.example.com",
        hashed_password=hash_password("WF4#IT1"),
        full_name="WF4 IT Team",
        role="it_team",
        is_active=True,
        tenant_id=urip_tenant_uuid,
    )
    urip_session.add(it_user)
    await urip_session.commit()
    it_h = {
        "Authorization": (
            f"Bearer {create_access_token(str(it_user.id), 'it_team', tenant_id=str(urip_tenant_uuid))}"
        )
    }

    create_risk = await urip_client.post(
        "/api/risks",
        json={
            "finding": "MFA off — auto-derived from compliance",
            "description": f"Linked to control {ctrl.id}",
            "source": "threat_intel",
            "domain": "identity",
            "cvss_score": 8.0,
            "severity": "high",
            "asset": f"control:{ctrl.id}",
            "owner_team": "Security",
            "composite_score": 8.0,
            "in_kev_catalog": False,
            "exploit_status": "none",
            "epss_score": 0.05,
        },
        headers=it_h,
    )
    assert create_risk.status_code == 201, create_risk.text
    risk_id = create_risk.json()["risk_id"]

    # ── Resolve the risk via the acceptance flow ───────────────────────────
    accept = await urip_client.post(
        "/api/acceptance",
        json={
            "risk_id": risk_id,
            "justification": "Admin enabled MFA on the IdP — control will pass on next run.",
            "compensating_controls": ["MFA enabled in IdP for all users"],
            "residual_risk": "Low",
        },
        headers=it_h,
    )
    assert accept.status_code == 201, accept.text
    acceptance_id = accept.json()["id"]

    approve = await urip_client.post(
        f"/api/acceptance/{acceptance_id}/approve", headers=urip_h
    )
    assert approve.status_code == 200, approve.text
    assert approve.json()["status"] == "approved"

    # ── Emit the cross-service "risk resolved" event ───────────────────────
    payload = RiskResolvedPayload(
        risk_id=risk_id,
        tenant_id=tenant_id,
        resolved_by=str(urip_user.id),
        resolved_at=datetime.now(timezone.utc).isoformat(),
        resolution="accepted",
    )
    await event_bus.publish(TOPIC_RISK_RESOLVED, payload.model_dump())

    # ── Simulate the compliance subscriber: re-run the linked control with
    #     a passing config (admin verified MFA is now on). ────────────────
    received = RiskResolvedPayload(**event_bus.published_to(TOPIC_RISK_RESOLVED)[0])
    assert received.tenant_id == tenant_id

    # Subscriber would parse the linked control out of the risk record.
    # We've encoded it in the risk asset; in production this would be a
    # dedicated FK column (linked_control_id).
    risk_detail = await urip_client.get(f"/api/risks/{risk_id}", headers=urip_h)
    assert risk_detail.status_code == 200
    asset = risk_detail.json()["risk"]["asset"]
    assert asset.startswith("control:")
    linked_control_id = asset.split("control:", 1)[1]
    assert linked_control_id == ctrl.id

    # CRIT-006 — admin flips the server-side tenant_config to mfa_enabled=True
    # before the subscriber re-runs the control. The route body remains empty.
    tenant_cfg.settings = {"mfa_enabled": True, "mfa_enforcement": "all_users"}
    await compliance_session.commit()

    # Subscriber re-runs the control with the now-correct config
    rerun = await compliance_client.post(
        f"/controls/{linked_control_id}/run",
        json={},
        headers=h_comp,
    )
    assert rerun.status_code == 201, rerun.text
    assert rerun.json()["status"] == "pass", rerun.text

    # ── Score climbs from 0 → 100 ──────────────────────────────────────────
    score_after = await compliance_client.get(
        f"/compliance-score/{fw.short_code}", headers=h_comp
    )
    assert score_after.status_code == 200
    post = score_after.json()["summary"]
    assert post["score"] == 100.0
    assert post["pass_count"] == 1
    assert post["fail_count"] == 0


@pytest.mark.asyncio
async def test_workflow_04_resolved_payload_round_trips(event_bus):
    payload = RiskResolvedPayload(
        risk_id="RISK-2026-0001",
        tenant_id="t1",
        resolved_by="user-1",
        resolved_at=datetime.now(timezone.utc).isoformat(),
        resolution="accepted",
    )
    raw = payload.model_dump()
    queue = event_bus.subscribe(TOPIC_RISK_RESOLVED)
    await event_bus.publish(TOPIC_RISK_RESOLVED, raw)
    received_raw = await queue.get()
    received = RiskResolvedPayload(**received_raw)
    assert received.risk_id == payload.risk_id
    assert received.resolution == "accepted"
