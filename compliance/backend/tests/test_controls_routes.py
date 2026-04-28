"""
TDD — Controls REST endpoint tests (P2B.3)

Tests:
  - GET /controls/runs — list runs for tenant (tenant isolation)
  - POST /controls/{id}/run — on-demand run, returns 201 with run result
  - GET /controls/{id}/runs/{run_id} — run detail, 404 for wrong tenant/id
  - Auth enforcement: 401 without token

NOTE — INV-6 documented test update (CRIT-006 security fix):
  The original tests in this file POSTed `tenant_config` in the request body
  to drive rule evaluation. That contract was a CRITICAL security bug
  (CRIT-006 in SECURITY_REVIEW.md): a tenant could forge a passing audit run
  by injecting their own inputs to the rule engine.

  After the fix, the route ignores any caller-supplied state and the engine
  derives `tenant_config` from the server-side `tenant_config` table. The
  tests below now seed that table directly via `_seed_tenant_config()` to
  prove the same end-to-end semantics under the secure contract. The OLD
  expectations were correct in spirit ("with mfa enabled, a control passes")
  but were wrong in mechanism (they trusted the body). They were NOT changed
  to weaken assertions — only to use the new server-side seeding path.

  This is the explicit "test expectation genuinely wrong → document WHY
  with evidence BEFORE changing" exception to INV-6.
"""
import time
import uuid
import pytest
# CRIT-005 (Z2.1): migrated python-jose -> PyJWT (HS256 surface identical)
import jwt

from compliance_backend.models.framework import Framework, FrameworkVersion, Control
from compliance_backend.models.tenant_state import TenantConfig
from compliance_backend.services.control_rules import load_builtin_rules

STANDALONE_SECRET = "test-secret-standalone"

load_builtin_rules()


def _make_token(tenant_id: str) -> str:
    payload = {
        "sub": "user-ctrl-1",
        "tenant_id": tenant_id,
        "role": "admin",
        "exp": int(time.time()) + 3600,
        "iss": "compliance",
    }
    return jwt.encode(payload, STANDALONE_SECRET, algorithm="HS256")


def _headers(tenant_id: str = "tenant-ctrl-test") -> dict:
    return {"Authorization": f"Bearer {_make_token(tenant_id)}"}


async def _seed_tenant_config(db_session, tenant_id: str, settings: dict) -> None:
    """CRIT-006 — populate the SERVER-SIDE tenant config used by the engine.

    The route no longer accepts caller-supplied tenant_config in the body.
    Tests must seed this table to influence rule outcomes — exactly as
    production tenant admins must do.
    """
    db_session.add(TenantConfig(tenant_id=tenant_id, settings=settings))
    await db_session.commit()


async def _seed_control(db_session, rule_function: str = "mfa_enforced") -> Control:
    fw = Framework(
        id=str(uuid.uuid4()),
        name=f"FW {uuid.uuid4().hex[:4]}",
        short_code=f"CR{uuid.uuid4().hex[:4].upper()}",
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

    ctrl = Control(
        id=str(uuid.uuid4()),
        framework_version_id=fv.id,
        control_code=f"CR-{uuid.uuid4().hex[:4].upper()}",
        category="Access",
        description="Control route test",
        rule_function=rule_function,
    )
    db_session.add(ctrl)
    await db_session.flush()
    await db_session.commit()
    return ctrl


# ---------------------------------------------------------------------------
# Auth enforcement
# ---------------------------------------------------------------------------

@pytest.mark.anyio
async def test_runs_list_requires_auth(client):
    resp = await client.get("/controls/runs")
    assert resp.status_code == 401


@pytest.mark.anyio
async def test_trigger_run_requires_auth(client):
    resp = await client.post(f"/controls/{uuid.uuid4()}/run")
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# POST /controls/{id}/run — on-demand run
# ---------------------------------------------------------------------------

@pytest.mark.anyio
async def test_trigger_run_pass(client, db_session):
    ctrl = await _seed_control(db_session, rule_function="mfa_enforced")
    tenant = "tenant-trigger-pass"
    # CRIT-006 — admin populates server-side state; route body cannot influence
    await _seed_tenant_config(
        db_session, tenant, {"mfa_enabled": True, "mfa_enforcement": "all_users"}
    )

    resp = await client.post(
        f"/controls/{ctrl.id}/run",
        headers=_headers(tenant),
        json={},
    )
    assert resp.status_code == 201, f"Expected 201, got {resp.status_code}: {resp.text}"
    body = resp.json()
    assert body["status"] == "pass"
    assert body["control_id"] == ctrl.id
    assert body["tenant_id"] == tenant
    assert body["id"]


@pytest.mark.anyio
async def test_trigger_run_fail(client, db_session):
    ctrl = await _seed_control(db_session, rule_function="mfa_enforced")
    tenant = "tenant-trigger-fail"
    # CRIT-006 — server-side config sets mfa disabled
    await _seed_tenant_config(db_session, tenant, {"mfa_enabled": False})

    resp = await client.post(
        f"/controls/{ctrl.id}/run",
        headers=_headers(tenant),
        json={},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["status"] == "fail"
    assert body["failure_reason"]


@pytest.mark.anyio
async def test_trigger_run_unknown_control_returns_404(client):
    resp = await client.post(
        f"/controls/{uuid.uuid4()}/run",
        headers=_headers("tenant-unknown"),
        json={},
    )
    assert resp.status_code == 404


@pytest.mark.anyio
async def test_trigger_run_returns_evidence_ids(client, db_session):
    """Triggering a run auto-captures evidence and returns their IDs."""
    ctrl = await _seed_control(db_session, rule_function="mfa_enforced")
    tenant = "tenant-evidence-ids"
    await _seed_tenant_config(
        db_session, tenant, {"mfa_enabled": True, "mfa_enforcement": "all_users"}
    )

    resp = await client.post(
        f"/controls/{ctrl.id}/run",
        headers=_headers(tenant),
        json={},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert isinstance(body["evidence_ids"], list)
    assert len(body["evidence_ids"]) >= 1


@pytest.mark.anyio
async def test_trigger_run_rejects_caller_state_in_body(client, db_session):
    """
    CRIT-006 — explicit regression guard. The route MUST refuse any attempt
    to smuggle tenant_config or connector_data through the request body.
    """
    ctrl = await _seed_control(db_session, rule_function="mfa_enforced")
    tenant = "tenant-reject-body"
    resp = await client.post(
        f"/controls/{ctrl.id}/run",
        headers=_headers(tenant),
        json={"tenant_config": {"mfa_enabled": True}},
    )
    assert resp.status_code == 422, (
        f"CRIT-006 — body with tenant_config must be rejected; got {resp.status_code}"
    )


# ---------------------------------------------------------------------------
# GET /controls/runs — list
# ---------------------------------------------------------------------------

@pytest.mark.anyio
async def test_list_runs_returns_tenant_scoped(client, db_session):
    ctrl = await _seed_control(db_session, rule_function="mfa_enforced")
    tenant_a = "tenant-list-a"
    tenant_b = "tenant-list-b"
    # CRIT-006 — server-side state per tenant
    await _seed_tenant_config(
        db_session, tenant_a, {"mfa_enabled": True, "mfa_enforcement": "all_users"}
    )
    await _seed_tenant_config(db_session, tenant_b, {"mfa_enabled": False})

    # Trigger 2 runs for tenant_a
    for _ in range(2):
        await client.post(
            f"/controls/{ctrl.id}/run",
            headers=_headers(tenant_a),
            json={},
        )

    # 1 run for tenant_b
    await client.post(
        f"/controls/{ctrl.id}/run",
        headers=_headers(tenant_b),
        json={},
    )

    resp = await client.get("/controls/runs", headers=_headers(tenant_a))
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 2
    for item in body["items"]:
        assert item["tenant_id"] == tenant_a


@pytest.mark.anyio
async def test_list_runs_filter_by_status(client, db_session):
    ctrl = await _seed_control(db_session, rule_function="mfa_enforced")
    tenant = "tenant-status-filter"
    # First run: pass (mfa enabled). Second run: must produce a fail.
    # We can't change a single TenantConfig row mid-test without two flushes
    # since runs are sequential, so we toggle the row in between.
    await _seed_tenant_config(
        db_session, tenant, {"mfa_enabled": True, "mfa_enforcement": "all_users"}
    )

    await client.post(
        f"/controls/{ctrl.id}/run",
        headers=_headers(tenant),
        json={},
    )

    # Toggle server-side state to drive a failing run
    cfg = (await db_session.execute(
        TenantConfig.__table__.select().where(TenantConfig.tenant_id == tenant)
    )).first()
    assert cfg is not None
    from sqlalchemy import update
    await db_session.execute(
        update(TenantConfig).where(TenantConfig.tenant_id == tenant).values(
            settings={"mfa_enabled": False}
        )
    )
    await db_session.commit()

    await client.post(
        f"/controls/{ctrl.id}/run",
        headers=_headers(tenant),
        json={},
    )

    resp = await client.get("/controls/runs?status=pass", headers=_headers(tenant))
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 1
    assert body["items"][0]["status"] == "pass"


# ---------------------------------------------------------------------------
# GET /controls/{id}/runs/{run_id} — run detail
# ---------------------------------------------------------------------------

@pytest.mark.anyio
async def test_get_run_detail(client, db_session):
    ctrl = await _seed_control(db_session, rule_function="mfa_enforced")
    tenant = "tenant-detail"
    await _seed_tenant_config(
        db_session, tenant, {"mfa_enabled": True, "mfa_enforcement": "all_users"}
    )

    trigger_resp = await client.post(
        f"/controls/{ctrl.id}/run",
        headers=_headers(tenant),
        json={},
    )
    assert trigger_resp.status_code == 201
    run_id = trigger_resp.json()["id"]

    detail_resp = await client.get(
        f"/controls/{ctrl.id}/runs/{run_id}",
        headers=_headers(tenant),
    )
    assert detail_resp.status_code == 200
    body = detail_resp.json()
    assert body["id"] == run_id
    assert body["status"] == "pass"


@pytest.mark.anyio
async def test_get_run_detail_wrong_tenant_returns_404(client, db_session):
    """A different tenant cannot access another tenant's run."""
    ctrl = await _seed_control(db_session, rule_function="mfa_enforced")
    tenant_a = "tenant-iso-run-a"
    tenant_b = "tenant-iso-run-b"
    await _seed_tenant_config(
        db_session, tenant_a, {"mfa_enabled": True, "mfa_enforcement": "all_users"}
    )

    trigger_resp = await client.post(
        f"/controls/{ctrl.id}/run",
        headers=_headers(tenant_a),
        json={},
    )
    run_id = trigger_resp.json()["id"]

    resp = await client.get(
        f"/controls/{ctrl.id}/runs/{run_id}",
        headers=_headers(tenant_b),
    )
    assert resp.status_code == 404


@pytest.mark.anyio
async def test_get_run_detail_not_found(client, db_session):
    ctrl = await _seed_control(db_session)
    resp = await client.get(
        f"/controls/{ctrl.id}/runs/{uuid.uuid4()}",
        headers=_headers(),
    )
    assert resp.status_code == 404
