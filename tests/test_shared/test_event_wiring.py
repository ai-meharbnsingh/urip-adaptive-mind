"""
Bidirectional event-bus wiring tests.

Verifies:
  - urip.risk.created      published when a Risk is inserted
  - urip.risk.resolved     published when a Risk transitions to resolved/closed
  - compliance.control.failed → URIP subscriber creates a linked risk row
  - compliance.policy.expiring → URIP subscriber records a notification

The bus is the in-process singleton from shared.events.bus.  Production wiring
(Redis) just attaches a Redis mirror client; the contract here is the same.
"""
from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timezone

import pytest
import pytest_asyncio

from shared.events import (
    TOPIC_CONTROL_FAILED,
    TOPIC_POLICY_EXPIRING,
    TOPIC_RISK_CREATED,
    TOPIC_RISK_RESOLVED,
    get_event_bus,
    reset_event_bus,
)
from shared.events.topics import (
    ControlFailedPayload,
    PolicyExpiringPayload,
    RiskCreatedPayload,
    RiskResolvedPayload,
)


@pytest.fixture(autouse=True)
def _clean_bus():
    reset_event_bus()
    yield
    reset_event_bus()


# -------------------- 1) URIP publishes risk.created -------------------- #
@pytest.mark.asyncio
async def test_urip_publishes_risk_created_on_insert(
    client, db_session, default_tenant, auth_headers
):
    bus = get_event_bus()

    risk_payload = {
        "finding": "wired-event-test",
        "description": "test risk",
        "source": "tenable",
        "domain": "vuln",
        "cvss_score": 7.5,
        "severity": "high",
        "asset": "host-1",
        "owner_team": "IT",
        "composite_score": 7.0,
        "in_kev_catalog": False,
        "exploit_status": "none",
        "epss_score": 0.05,
    }
    resp = await client.post("/api/risks", json=risk_payload, headers=auth_headers)
    assert resp.status_code == 201, resp.text

    # Allow scheduled subscribers (none here) to settle.
    await asyncio.sleep(0)

    history = bus.history(TOPIC_RISK_CREATED)
    assert len(history) >= 1, f"Expected at least 1 risk.created event, got {history}"
    last = history[-1]
    parsed = RiskCreatedPayload(**last)  # round-trips through pydantic
    assert parsed.finding == "wired-event-test"
    assert parsed.tenant_id == str(default_tenant.id)


# -------------------- 2) URIP publishes risk.resolved on status change -------------------- #
@pytest.mark.asyncio
async def test_urip_publishes_risk_resolved_on_status_transition(
    client, db_session, default_tenant, auth_headers
):
    # Create risk first.
    create_resp = await client.post(
        "/api/risks",
        json={
            "finding": "resolve-me",
            "description": "tx",
            "source": "tenable",
            "domain": "vuln",
            "cvss_score": 5.0,
            "severity": "medium",
            "asset": "host-2",
            "owner_team": "IT",
            "composite_score": 5.0,
            "in_kev_catalog": False,
            "exploit_status": "none",
            "epss_score": 0.01,
        },
        headers=auth_headers,
    )
    assert create_resp.status_code == 201, create_resp.text
    risk_id = create_resp.json()["risk_id"]

    bus = get_event_bus()
    bus.reset()  # clear created event noise

    upd = await client.patch(
        f"/api/risks/{risk_id}",
        json={"status": "resolved"},
        headers=auth_headers,
    )
    assert upd.status_code == 200, upd.text
    await asyncio.sleep(0)

    history = bus.history(TOPIC_RISK_RESOLVED)
    assert len(history) >= 1
    parsed = RiskResolvedPayload(**history[-1])
    assert parsed.tenant_id == str(default_tenant.id)
    assert parsed.resolution in ("resolved", "closed")


# -------------------- 3) URIP subscriber consumes compliance.control.failed -------------------- #
@pytest.mark.asyncio
async def test_urip_subscriber_records_control_failure_event():
    """
    The URIP-side subscriber must accept the control-failed payload and stash a
    notification for the unified panel.  The notification list lives on the bus
    and is consumed by the dashboard endpoint.
    """
    from backend.services.event_subscribers import (
        register_urip_subscribers,
        get_compliance_notifications,
    )

    bus = get_event_bus()
    register_urip_subscribers(bus)

    payload = ControlFailedPayload(
        control_id=str(uuid.uuid4()),
        tenant_id="tenant-abc",
        control_name="MFA enforced",
        framework="SOC2",
        failed_at=datetime.now(timezone.utc).isoformat(),
        details="mfa_enabled is False",
    ).model_dump()

    fired = await bus.publish(TOPIC_CONTROL_FAILED, payload)
    assert fired >= 1, "URIP subscriber must be registered for control_failed"

    # Allow async subscribers to run if they spawn tasks.
    await asyncio.sleep(0)

    notes = await get_compliance_notifications("tenant-abc")
    assert any(n["topic"] == TOPIC_CONTROL_FAILED for n in notes), notes


@pytest.mark.asyncio
async def test_urip_subscriber_records_policy_expiring_event():
    from backend.services.event_subscribers import (
        register_urip_subscribers,
        get_compliance_notifications,
    )

    bus = get_event_bus()
    register_urip_subscribers(bus)

    payload = PolicyExpiringPayload(
        policy_id=str(uuid.uuid4()),
        tenant_id="tenant-abc",
        policy_name="Acceptable Use",
        expires_at=datetime.now(timezone.utc).isoformat(),
        days_remaining=10,
    ).model_dump()
    await bus.publish(TOPIC_POLICY_EXPIRING, payload)
    await asyncio.sleep(0)

    notes = await get_compliance_notifications("tenant-abc")
    assert any(n["topic"] == TOPIC_POLICY_EXPIRING for n in notes)


# -------------------- 4) End-to-end: control_failed → linked risk created in URIP -------------------- #
@pytest.mark.asyncio
async def test_compliance_control_failed_creates_linked_risk_in_urip(
    client, db_session, default_tenant, auth_headers
):
    """
    With the auto-link toggle enabled on the tenant, a compliance control
    failure event causes URIP to insert a risk row whose `asset` encodes the
    failing control_id.  This mirrors the behaviour the e2e workflow_03 test
    asserts but exercises the actual subscriber, not a hand-written shim.
    """
    from backend.services.event_subscribers import register_urip_subscribers

    # Enable the toggle on the default tenant.
    default_tenant.settings = {**(default_tenant.settings or {}), "compliance_link_auto_create_risk": True}
    await db_session.commit()

    bus = get_event_bus()
    register_urip_subscribers(bus)

    control_id = str(uuid.uuid4())
    payload = ControlFailedPayload(
        control_id=control_id,
        tenant_id=str(default_tenant.id),
        control_name="MFA on Admin Accounts",
        framework="SOC2",
        failed_at=datetime.now(timezone.utc).isoformat(),
        details="mfa_enabled=False",
    ).model_dump()
    await bus.publish(TOPIC_CONTROL_FAILED, payload)

    # Subscriber spawns an async task; wait a tick for completion.
    for _ in range(20):
        await asyncio.sleep(0.05)
        list_resp = await client.get("/api/risks", headers=auth_headers)
        if list_resp.status_code == 200:
            findings = [r["finding"] for r in list_resp.json().get("items", [])]
            if any("MFA on Admin Accounts" in f for f in findings):
                break
    else:
        pytest.fail("Subscriber did not create a linked risk in time")

    # The created risk's asset should encode the control_id (linkage).
    matching = [
        r for r in list_resp.json()["items"]
        if "MFA on Admin Accounts" in r.get("finding", "")
    ]
    assert matching, list_resp.json()
    assert control_id in matching[0]["asset"]
