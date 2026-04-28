"""
WORKFLOW 3 — Compliance control failure → URIP risk (cross-service).

End-to-end shape:
  1. A tenant admin runs an mfa_enforced control via Compliance with a
     deliberately-bad config (mfa_enabled=False).
  2. The control returns status="fail" — verified via the public API.
  3. The compliance service WOULD emit a `compliance.control.failed` event
     on the shared bus (per shared/events/topics.py).
  4. A URIP-side subscriber WOULD consume the event and create a Risk row
     for the tenant linked to the failed control.
  5. The tenant admin sees the new risk via GET /api/risks on URIP.

Honesty / scope notes:

  * As of this codebase, NEITHER service has the publisher OR subscriber
    wired into its router/scheduler — `shared/events/topics.py` defines
    only the event schema constants.  See:
        compliance_backend/services/control_engine.py — TODO P2B.3.4
        backend/main.py                              — no subscriber
    What this test exercises is therefore the EVENT-CONTRACT: the
    Pydantic payload schema for `ControlFailedPayload` round-trips, and
    the URIP-side risk-creation API accepts the data the subscriber would
    hand it.  The test bridges the two services via DummyEventBus, which
    is the same shape as the future Redis-backed wiring.

  * If/when the production wiring lands (FastAPI background task on
    compliance + Redis subscriber on URIP), this test can switch the
    `event_bus` fixture from in-memory to a real Redis client without
    changing the test body — the contract is the same.
"""

from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy import select

from compliance_backend.models.framework import Framework, FrameworkVersion, Control
from compliance_backend.models.tenant_state import TenantConfig
from compliance_backend.services.control_rules import load_builtin_rules

from shared.events.topics import (
    TOPIC_CONTROL_FAILED,
    ControlFailedPayload,
)

from backend.middleware.auth import create_access_token, hash_password
from backend.models.tenant import Tenant
from backend.models.user import User
from backend.models.subscription import TenantSubscription
from backend.middleware.tenant import TenantContext


def _comp_admin_headers(jwt_factory, tenant_id: str) -> dict:
    return {"Authorization": f"Bearer {jwt_factory(tenant_id, role='admin')}"}


async def _seed_compliance_control(session) -> Control:
    """Create a Framework + FrameworkVersion + Control wired to mfa_enforced."""
    fw = Framework(
        id=str(uuid.uuid4()),
        name=f"FW {uuid.uuid4().hex[:4]}",
        short_code=f"X3FW{uuid.uuid4().hex[:4].upper()}",
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
        control_code=f"CC-{uuid.uuid4().hex[:4].upper()}",
        category="Access",
        description="MFA must be enforced",
        rule_function="mfa_enforced",
    )
    session.add_all([fw, fv, ctrl])
    await session.flush()
    return ctrl


async def _seed_urip_tenant_with_vm(urip_session) -> tuple[Tenant, User]:
    """Create a URIP Tenant + ciso user + VM module subscription."""
    tenant = Tenant(
        id=uuid.uuid4(),
        name="Cross-svc tenant",
        slug=f"xsvc-{uuid.uuid4().hex[:5]}",
        domain="xsvc.example.com",
        is_active=True,
        settings={},
    )
    urip_session.add(tenant)
    await urip_session.flush()
    user = User(
        id=uuid.uuid4(),
        email=f"cross-{uuid.uuid4().hex[:6]}@xsvc.example.com",
        hashed_password=hash_password("Cross#Pass1"),
        full_name="Cross Admin",
        role="ciso",
        is_active=True,
        tenant_id=tenant.id,
    )
    urip_session.add(user)
    urip_session.add(TenantSubscription(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        module_code="VM",
        is_enabled=True,
        billing_tier="STANDARD",
    ))
    await urip_session.flush()
    return tenant, user


@pytest.mark.asyncio
async def test_workflow_03_control_failure_creates_urip_risk(
    compliance_client,
    compliance_session,
    urip_client,
    urip_session,
    make_compliance_jwt,
    event_bus,
):
    load_builtin_rules()  # ensure mfa_enforced is registered

    # ── Set up Compliance side: tenant + control ───────────────────────────
    tenant_id = "xsvc-tenant"
    h = _comp_admin_headers(make_compliance_jwt, tenant_id)
    ctrl = await _seed_compliance_control(compliance_session)

    # ── Set up URIP side: matching tenant (use the same tenant_id literal) ─
    # The cross-service contract uses tenant_id strings.  URIP uses UUIDs
    # for tenant IDs and JWT claim "tenant_id" must be a UUID string.  We
    # therefore mint a URIP tenant whose UUID equals our compliance tenant
    # string (cast to UUID5 so it's deterministic).
    urip_tenant_uuid = uuid.uuid5(uuid.NAMESPACE_DNS, tenant_id)
    urip_tenant = Tenant(
        id=urip_tenant_uuid,
        name="Cross-svc URIP tenant",
        slug="xsvc-urip",
        domain="xsvc-urip.example.com",
        is_active=True,
        settings={},
    )
    urip_user = User(
        id=uuid.uuid4(),
        email="cross-it@xsvc-urip.example.com",
        hashed_password=hash_password("Cross#Pass1"),
        full_name="Cross IT",
        role="it_team",
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

    # ── 1) Trigger a deliberately-failing control on Compliance ────────────
    # CRIT-006 — control engine no longer accepts caller-supplied tenant_config.
    # The tenant admin must populate the server-side tenant_config table; the
    # rule engine reads ONLY from there. Seed mfa_enabled=False so the
    # mfa_enforced rule fails deterministically.
    compliance_session.add(
        TenantConfig(tenant_id=tenant_id, settings={"mfa_enabled": False})
    )
    await compliance_session.commit()

    fail_resp = await compliance_client.post(
        f"/controls/{ctrl.id}/run",
        json={},
        headers=h,
    )
    assert fail_resp.status_code == 201, fail_resp.text
    fail_body = fail_resp.json()
    assert fail_body["status"] == "fail"
    assert fail_body["failure_reason"]

    # ── 2) Build the cross-service event the publisher SHOULD emit ─────────
    # (Compliance does not emit yet — see module docstring.)
    payload = ControlFailedPayload(
        control_id=ctrl.id,
        tenant_id=tenant_id,
        control_name=ctrl.description or "MFA control",
        framework="X3FW",
        failed_at=datetime.now(timezone.utc).isoformat(),
        details=fail_body["failure_reason"],
    )
    receivers = await event_bus.publish(
        TOPIC_CONTROL_FAILED, payload.model_dump()
    )
    # Without a real subscriber there are zero receivers — that's fine,
    # the contract test is whether the URIP-side handler accepts the payload.
    assert receivers == 0
    assert event_bus.published_to(TOPIC_CONTROL_FAILED), (
        "Event must be recorded in the bus audit log"
    )

    # ── 3) Simulate the URIP-side subscriber: parse payload + POST risk ────
    sub_payload = ControlFailedPayload(
        **event_bus.published_to(TOPIC_CONTROL_FAILED)[0]
    )
    risk_payload = {
        "finding": f"Control failure: {sub_payload.control_name}",
        "description": (
            f"Auto-created from compliance control {sub_payload.control_id}: "
            f"{sub_payload.details}"
        ),
        "source": "threat_intel",  # pick a valid source enum value
        "domain": "identity",
        "cvss_score": 7.5,
        "severity": "high",
        "asset": f"control:{sub_payload.control_id}",
        "owner_team": "Compliance",
        "composite_score": 7.5,
        "in_kev_catalog": False,
        "exploit_status": "none",
        "epss_score": 0.10,
    }
    create_resp = await urip_client.post("/api/risks", json=risk_payload, headers=urip_h)
    assert create_resp.status_code == 201, create_resp.text
    created = create_resp.json()
    new_risk_id = created["risk_id"]
    # The risk's asset encodes the originating control_id — the "linkage"
    # the workflow asks for.  This is how the production subscriber
    # SHOULD propagate the link until a dedicated `linked_control_id`
    # column lands.
    assert sub_payload.control_id in created["asset"]

    # Reset TenantContext between requests (contextvars are bound per-task
    # in async land; an explicit set is defensive).
    TenantContext.set(urip_tenant_uuid)

    # ── 4) Tenant admin lists risks → sees the new one ─────────────────────
    list_resp = await urip_client.get("/api/risks", headers=urip_h)
    assert list_resp.status_code == 200, list_resp.text
    listed_ids = [r["risk_id"] for r in list_resp.json()["items"]]
    assert new_risk_id in listed_ids

    # ── 5) The risk is reachable individually ──────────────────────────────
    detail_resp = await urip_client.get(f"/api/risks/{new_risk_id}", headers=urip_h)
    assert detail_resp.status_code == 200
    risk_detail = detail_resp.json()["risk"]
    assert sub_payload.control_id in risk_detail["asset"]


@pytest.mark.asyncio
async def test_workflow_03_failed_payload_round_trips_through_bus(
    event_bus,
):
    """The Pydantic schema round-trips cleanly across the bus boundary."""
    payload = ControlFailedPayload(
        control_id=str(uuid.uuid4()),
        tenant_id="cross-tenant",
        control_name="Test Control",
        framework="SOC2",
        failed_at=datetime.now(timezone.utc).isoformat(),
        details="Synthetic failure for contract test",
    )
    raw = payload.model_dump()
    queue = event_bus.subscribe(TOPIC_CONTROL_FAILED)
    await event_bus.publish(TOPIC_CONTROL_FAILED, raw)
    received_raw = await asyncio.wait_for(queue.get(), timeout=2)
    received = ControlFailedPayload(**received_raw)
    assert received.control_id == payload.control_id
    assert received.tenant_id == payload.tenant_id
    assert received.framework == payload.framework
