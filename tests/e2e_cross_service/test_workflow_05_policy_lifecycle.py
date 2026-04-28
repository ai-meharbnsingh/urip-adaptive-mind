"""
WORKFLOW 5 — Policy lifecycle (Compliance service).

Covers:
  1. Admin creates a policy via POST /policies (auto-publishes v1).
  2. Three "employees" acknowledge v1 — POST /policies/{id}/acknowledge.
  3. Admin publishes v2 via POST /policies/{id}/versions.
  4. After v2 publication, the pending-acks list for each of the three
     employees grows by 1 (their previous v1 acknowledgment does not count
     for v2).
  5. Two of three employees acknowledge v2 → their pending list shrinks back.
  6. The third employee's pending list still contains the policy.
  7. A policy with `expires_at` within the next 30 days is surfaced via
     GET /policies/expiring.

Tests use the compliance_client + make_compliance_jwt fixtures from the
package conftest.  All operations are tenant-scoped.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest


def _admin_headers(jwt_factory, tenant_id: str = "policy-tenant") -> dict:
    return {"Authorization": f"Bearer {jwt_factory(tenant_id, role='admin')}"}


def _user_headers(jwt_factory, user_id: str, tenant_id: str = "policy-tenant") -> dict:
    return {
        "Authorization": f"Bearer {jwt_factory(tenant_id, role='employee', sub=user_id)}"
    }


@pytest.mark.asyncio
async def test_workflow_05_policy_versioning_and_acknowledgments(
    compliance_client, make_compliance_jwt
):
    tenant_id = "policy-tenant-e2e"
    admin_h = _admin_headers(make_compliance_jwt, tenant_id)

    # ── 1) Admin creates a policy with an initial v1 ───────────────────────
    create_resp = await compliance_client.post(
        "/policies",
        json={
            "name": "Acceptable Use Policy",
            "content": "v1 — be reasonable.",
        },
        headers=admin_h,
    )
    assert create_resp.status_code == 201, create_resp.text
    policy = create_resp.json()
    policy_id = policy["id"]
    assert policy["current_version"]["version_number"] == 1

    # ── 2) Three employees acknowledge v1 ──────────────────────────────────
    employees = ["alice@e2e", "bob@e2e", "carol@e2e"]
    for emp in employees:
        ack = await compliance_client.post(
            f"/policies/{policy_id}/acknowledge",
            json={"signature": f"signed-by-{emp}"},
            headers=_user_headers(make_compliance_jwt, emp, tenant_id),
        )
        assert ack.status_code == 200, ack.text
        ack_body = ack.json()
        assert ack_body["user_id"] == emp
        assert ack_body["tenant_id"] == tenant_id

    # Each employee's pending list now does NOT include this policy
    for emp in employees:
        pending = await compliance_client.get(
            "/policies/pending",
            headers=_user_headers(make_compliance_jwt, emp, tenant_id),
        )
        assert pending.status_code == 200
        assert all(p["id"] != policy_id for p in pending.json()), (
            f"Employee {emp} should NOT have policy {policy_id} pending after ack"
        )

    # ── 3) Admin publishes a new version v2 ────────────────────────────────
    v2_resp = await compliance_client.post(
        f"/policies/{policy_id}/versions",
        json={
            "content": "v2 — be MORE reasonable; AI usage section added.",
            "change_summary": "Add AI usage clause",
        },
        headers=admin_h,
    )
    assert v2_resp.status_code == 200, v2_resp.text
    assert v2_resp.json()["version_number"] == 2

    # ── 4) ALL three employees now have the policy pending again ───────────
    for emp in employees:
        pending = await compliance_client.get(
            "/policies/pending",
            headers=_user_headers(make_compliance_jwt, emp, tenant_id),
        )
        assert pending.status_code == 200
        pending_ids = {p["id"] for p in pending.json()}
        assert policy_id in pending_ids, (
            f"After v2 publish, employee {emp} should see policy pending re-ack; "
            f"got {pending_ids}"
        )

    # ── 5) Two of three re-acknowledge v2 ──────────────────────────────────
    for emp in employees[:2]:
        ack = await compliance_client.post(
            f"/policies/{policy_id}/acknowledge",
            json={"signature": f"signed-{emp}-v2"},
            headers=_user_headers(make_compliance_jwt, emp, tenant_id),
        )
        assert ack.status_code == 200

    # ── 6) The third employee still sees it pending ────────────────────────
    laggard = employees[2]
    pending_laggard = await compliance_client.get(
        "/policies/pending",
        headers=_user_headers(make_compliance_jwt, laggard, tenant_id),
    )
    assert pending_laggard.status_code == 200
    laggard_ids = {p["id"] for p in pending_laggard.json()}
    assert policy_id in laggard_ids, (
        f"Laggard {laggard} should still have policy pending; got {laggard_ids}"
    )

    # The two who acknowledged should have empty pending for this policy
    for emp in employees[:2]:
        pending = await compliance_client.get(
            "/policies/pending",
            headers=_user_headers(make_compliance_jwt, emp, tenant_id),
        )
        assert pending.status_code == 200
        assert all(p["id"] != policy_id for p in pending.json())


@pytest.mark.asyncio
async def test_workflow_05_expiring_policy_surfaced(
    compliance_client, make_compliance_jwt
):
    tenant_id = "policy-expiry-tenant"
    admin_h = _admin_headers(make_compliance_jwt, tenant_id)

    # Policy that expires in 14 days (< 30-day window)
    soon = (datetime.now(timezone.utc) + timedelta(days=14)).isoformat()
    create = await compliance_client.post(
        "/policies",
        json={
            "name": "Soon-to-Expire Policy",
            "content": "Will expire shortly",
            "expires_at": soon,
        },
        headers=admin_h,
    )
    assert create.status_code == 201, create.text
    soon_id = create.json()["id"]

    # Policy that expires in 200 days (> 30-day window)
    far = (datetime.now(timezone.utc) + timedelta(days=200)).isoformat()
    create2 = await compliance_client.post(
        "/policies",
        json={
            "name": "Long-Lived Policy",
            "content": "Will not expire soon",
            "expires_at": far,
        },
        headers=admin_h,
    )
    assert create2.status_code == 201
    far_id = create2.json()["id"]

    # GET /policies/expiring → only the 14-day one
    expiring = await compliance_client.get("/policies/expiring", headers=admin_h)
    assert expiring.status_code == 200, expiring.text
    expiring_ids = {p["id"] for p in expiring.json()}
    assert soon_id in expiring_ids, (
        f"14-day-out policy should be in expiring; got {expiring_ids}"
    )
    assert far_id not in expiring_ids, (
        f"200-day-out policy should NOT be in expiring; got {expiring_ids}"
    )


@pytest.mark.asyncio
async def test_workflow_05_policy_isolation_between_tenants(
    compliance_client, make_compliance_jwt
):
    """A policy created by tenant X must not appear in tenant Y's lists."""
    admin_x = _admin_headers(make_compliance_jwt, "policy-iso-x")
    admin_y = _admin_headers(make_compliance_jwt, "policy-iso-y")

    create_x = await compliance_client.post(
        "/policies",
        json={"name": "X policy", "content": "x"},
        headers=admin_x,
    )
    assert create_x.status_code == 201
    pid_x = create_x.json()["id"]

    list_y = await compliance_client.get("/policies", headers=admin_y)
    assert list_y.status_code == 200
    assert pid_x not in {p["id"] for p in list_y.json()}, (
        "Policy from tenant X leaked into tenant Y's list"
    )

    # Direct fetch by id from Y → 404
    get_y = await compliance_client.get(f"/policies/{pid_x}", headers=admin_y)
    assert get_y.status_code == 404, (
        f"Direct GET of X's policy from Y must 404; got {get_y.status_code}"
    )
