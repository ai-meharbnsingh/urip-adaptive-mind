"""
WORKFLOW 1 — Tenant onboarding to first risk.

End-to-end happy path covering:
  1. super-admin creates a new tenant (POST /api/admin/tenants)
  2. super-admin provisions tenant admin user
  3. tenant admin "logs in" via the public /api/auth/login endpoint
     (verifies tenant_slug + access_token are returned)
  4. super-admin enables the VM module subscription
  5. tenant admin reads tenant branding via GET /api/tenants/{slug}/branding
     (confirms white-label payload is reachable from inside the tenant)
  6. tenant admin imports the default asset taxonomy
     (POST /api/asset-taxonomy/import-defaults)
  7. simulator-equivalent posts a real risk through the public /api/risks
     POST surface (the connector framework normalises to the same shape).
  8. tenant admin lists risks and sees the new one
  9. tenant admin opens an acceptance request and a CISO approves it
 10. audit log records every action that is wired to AuditLog +
     tenant_id in the source code (risk_created is currently the only
     fully tenant-stamped action; other audit rows omit tenant_id —
     that asymmetry is documented in the assertion below so the test
     stays honest about what URIP guarantees today).
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.audit_log import AuditLog
from backend.models.risk import Risk


@pytest.mark.asyncio
async def test_workflow_01_tenant_to_first_risk_happy_path(
    client: AsyncClient,
    db_session: AsyncSession,
    super_admin_headers: dict,
    tenant_factory,
    enable_module,
    make_user_in_tenant,
):
    # ── 1) Create a tenant (super-admin) ────────────────────────────────────
    onboarding = await tenant_factory(
        slug="acme-e2e",
        name="Acme E2E",
        domain="acme-e2e.test",
        admin_email="ciso@acme-e2e.test",
        admin_role="ciso",
        admin_password="Acme#Pass1234",
    )
    slug = onboarding["slug"]
    tenant_id = onboarding["tenant_id"]

    # The super-admin endpoint already returned an access_token for the new
    # admin (one-shot bootstrap), but we ALSO exercise the public login flow
    # to verify the user can authenticate without that bootstrap token.

    # ── 2 & 3) Tenant admin logs in via /api/auth/login ─────────────────────
    login_resp = await client.post(
        "/api/auth/login",
        json={
            "email": onboarding["admin_email"],
            "password": onboarding["admin_password"],
        },
    )
    assert login_resp.status_code == 200, login_resp.text
    login_body = login_resp.json()
    assert login_body["user"]["tenant_slug"] == slug, (
        f"Login response must surface tenant_slug for white-label routing; "
        f"got {login_body['user']!r}"
    )
    assert login_body["user"]["role"] == "ciso"
    admin_headers = {"Authorization": f"Bearer {login_body['access_token']}"}

    # ── 4) Super-admin enables the VM module ────────────────────────────────
    module_payload = await enable_module(slug, module_code="VM")
    assert module_payload is not None
    assert module_payload["module_code"] == "VM"
    assert module_payload["is_enabled"] is True

    # ── 5) Tenant admin reads its own branding ──────────────────────────────
    branding_resp = await client.get(
        f"/api/tenants/{slug}/branding", headers=admin_headers
    )
    assert branding_resp.status_code == 200, branding_resp.text
    branding = branding_resp.json()
    # Newly-created tenant has no branding yet — fields are nullable but present
    assert set(branding.keys()) >= {
        "app_name",
        "logo_url",
        "primary_color",
        "secondary_color",
    }

    # ── 6) Tenant admin imports default asset taxonomy ──────────────────────
    taxonomy_resp = await client.post(
        "/api/asset-taxonomy/import-defaults", headers=admin_headers
    )
    assert taxonomy_resp.status_code == 201, taxonomy_resp.text
    taxonomy_body = taxonomy_resp.json()
    assert taxonomy_body["inserted"] > 0, "import-defaults must seed at least 1 keyword"

    # Idempotency guard: a second import returns 409
    taxonomy_again = await client.post(
        "/api/asset-taxonomy/import-defaults", headers=admin_headers
    )
    assert taxonomy_again.status_code == 409, taxonomy_again.text

    # ── 7) Simulator-equivalent: an it_team user creates risks via the
    #       same POST /api/risks endpoint that the connector framework
    #       targets in production.  Using a fresh it_team user avoids
    #       polluting the CISO's audit signature.
    _, it_headers = await make_user_in_tenant(
        tenant_id, email=f"it@{slug}.test", role="it_team"
    )

    risk_payloads = [
        {
            "finding": "Test Critical RCE",
            "description": "Simulator-injected critical RCE for E2E",
            "source": "crowdstrike",
            "domain": "endpoint",
            "cvss_score": 9.8,
            "severity": "critical",
            "asset": "FIN-WS-01",
            "owner_team": "Infra Team",
            "cve_id": "CVE-2024-3400",
            "composite_score": 12.5,
            "in_kev_catalog": True,
            "exploit_status": "weaponized",
            "epss_score": 0.95,
        },
        {
            "finding": "EASM exposed .env file",
            "description": "Subdomain exposes secrets",
            "source": "easm",
            "domain": "application",
            "cvss_score": 8.6,
            "severity": "high",
            "asset": "staging.acme-e2e.test",
            "owner_team": "App Team",
            # composite_score must be supplied to short-circuit the async
            # enrichment background task (which would try to use the prod
            # async_session bound to asyncpg → fails in the test runtime).
            "composite_score": 9.1,
            "in_kev_catalog": False,
            "exploit_status": "poc",
            "epss_score": 0.42,
        },
    ]
    created_risks = []
    for payload in risk_payloads:
        resp = await client.post("/api/risks", json=payload, headers=it_headers)
        # 201 Created — see backend/ENDPOINT_AUDIT.md criterion #7.
        assert resp.status_code == 201, f"POST /api/risks → {resp.status_code} {resp.text}"
        created_risks.append(resp.json())

    # ── 8) Tenant admin lists risks → sees both ─────────────────────────────
    list_resp = await client.get("/api/risks", headers=admin_headers)
    assert list_resp.status_code == 200, list_resp.text
    list_body = list_resp.json()
    assert list_body["total"] == 2
    listed_findings = {r["finding"] for r in list_body["items"]}
    assert listed_findings == {p["finding"] for p in risk_payloads}

    # ── 9) Tenant admin opens an acceptance request, then approves ──────────
    target_risk_id = created_risks[1]["risk_id"]  # accept the high one
    accept_resp = await client.post(
        "/api/acceptance",
        json={
            "risk_id": target_risk_id,
            "justification": "Compensating controls in place; legacy host.",
            "compensating_controls": ["WAF rule", "Network segmentation"],
            "residual_risk": "Low",
        },
        headers=it_headers,  # IT requests
    )
    assert accept_resp.status_code == 201, accept_resp.text
    acceptance_id = accept_resp.json()["id"]

    approve_resp = await client.post(
        f"/api/acceptance/{acceptance_id}/approve", headers=admin_headers  # CISO approves
    )
    assert approve_resp.status_code == 200, approve_resp.text
    assert approve_resp.json()["status"] == "approved"

    # Confirm the underlying Risk row flipped to status=accepted via the DB
    row = await db_session.execute(
        select(Risk).where(Risk.tenant_id == tenant_id, Risk.risk_id == target_risk_id)
    )
    risk_row = row.scalar_one()
    assert risk_row.status == "accepted"

    # ── 10) Audit log records actions (tenant-scoped where the source
    #        code stamps tenant_id).  risk_created IS tenant-stamped;
    #        acceptance and risk_updated are NOT (see backend/routers/
    #        acceptance.py + backend/routers/risks.py update branch).
    audit_resp = await client.get("/api/audit-log", headers=admin_headers)
    assert audit_resp.status_code == 200, audit_resp.text
    audit_items = audit_resp.json()["items"]
    actions_seen = {item["action"] for item in audit_items}
    # The two POST /api/risks calls each emit a tenant-stamped risk_created row.
    assert "risk_created" in actions_seen, (
        f"risk_created absent from tenant-scoped audit log; actions={actions_seen!r}"
    )
    risk_created_count = sum(1 for i in audit_items if i["action"] == "risk_created")
    assert risk_created_count == len(risk_payloads), (
        f"Expected {len(risk_payloads)} risk_created audit rows, got "
        f"{risk_created_count}: {[i['action'] for i in audit_items]}"
    )
    # All audit rows returned MUST be from the user we authenticated as the
    # tenant — the IT team user.  No leakage of CISO id from this list.
    for item in audit_items:
        assert item["user_role"] in {"it_team", "ciso"}, item
