"""
WORKFLOW 8 — Connector lifecycle (URIP side).

Covers:
  1. Super-admin enables a connector for a tenant by storing encrypted
     credentials in the CredentialsVault.
  2. The scheduler tick fires (we drive it directly in the test process).
  3. The simulator connector produces findings.
  4. Findings normalize to URIPRiskRecord shape.
  5. URIPRiskRecord rows are persisted as Risks via the public POST /api/risks
     API (this is the layer the connector framework hands off to in
     production — there is no direct DB writer in the framework today).
  6. The risks land in the tenant's risk register and are visible via
     GET /api/risks.
  7. Connector health check returns ok.

Notes / honesty:
  - The connector framework's `ConnectorScheduler.tick()` returns a list of
    URIPRiskRecord objects but does NOT itself persist them.  Persistence is
    handled by the API layer (POST /api/risks).  This test wires those two
    halves together explicitly so the end-to-end behaviour is exercised.
  - EPSS / KEV / MITRE enrichment in production runs in a background task on
    the API side (see backend/services/exploitability_service.py); we do NOT
    exercise that branch because it requires real network access and would
    flake the suite.  Instead we supply pre-computed composite_score values
    so the API short-circuits enrichment.  Documented limitation.
"""

from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient

from connectors.base.scheduler import ConnectorScheduler
from connectors.base.credentials_vault import CredentialsVault


@pytest.mark.asyncio
async def test_workflow_08_connector_tick_produces_risks(
    client: AsyncClient,
    tenant_factory,
    enable_module,
    make_user_in_tenant,
):
    # ── Set up tenant with VM + admin + IT user ─────────────────────────────
    onboarding = await tenant_factory(slug="conn-e2e")
    tenant_slug = onboarding["slug"]
    tenant_id = onboarding["tenant_id"]
    await enable_module(tenant_slug, "VM")

    _, it_headers = await make_user_in_tenant(tenant_id, role="it_team")

    # ── 1) Super-admin "enables" the simulator connector by storing creds ───
    #     The credentials are simulator-no-op but the encryption round-trip
    #     proves the vault contract holds for the tenant.
    fernet_key = "z3eP-yQXM_8OMQfxENLO0bX2KdoH5b_PQ8XohMJsgcw="
    vault = CredentialsVault(fernet_key=fernet_key)
    vault.store_in_memory(
        tenant_id=str(tenant_id),
        connector_name="simulator",
        credentials={"tenant_id": str(tenant_id), "api_key": "n/a"},
    )
    decrypted = vault.retrieve_from_memory(str(tenant_id), "simulator")
    assert decrypted is not None
    assert decrypted["tenant_id"] == str(tenant_id)

    # Make sure the simulator connector's @register_connector side-effect ran
    import connectors.simulator_connector  # noqa: F401

    # ── 2 & 3) Drive one scheduler tick ────────────────────────────────────
    scheduler = ConnectorScheduler()
    tenant_config = {
        "tenant_id": str(tenant_id),
        "enabled_connectors": ["simulator"],
        "connector_credentials": {"simulator": decrypted},
    }
    records = await scheduler.tick(tenant_config)
    assert isinstance(records, list)
    assert len(records) > 0, "simulator should yield ≥1 finding per tick"

    # ── 4) Each record is a normalized URIPRiskRecord — confirm fields ─────
    for rec in records:
        assert rec.finding
        assert rec.source in {
            "crowdstrike", "easm", "cnapp", "armis", "vapt",
            "threat_intel", "cert_in", "bug_bounty", "soc",
        }
        assert rec.severity in {"critical", "high", "medium", "low"}
        assert isinstance(rec.cvss_score, (int, float))

    # ── 5) Persist the records via the public API (matches production) ─────
    persisted = []
    for rec in records:
        payload = {
            "finding": rec.finding,
            "description": rec.description or rec.finding,
            "source": rec.source,
            "domain": rec.domain,
            "cvss_score": float(rec.cvss_score),
            "severity": rec.severity,
            "asset": rec.asset,
            "owner_team": rec.owner_team,
            "cve_id": rec.cve_id,
            # Pre-compute exploitability fields so the API skips the async
            # enrichment task (which would call out to EPSS / KEV).
            "composite_score": float(rec.cvss_score),
            "in_kev_catalog": bool(rec.in_kev_catalog),
            "exploit_status": rec.exploit_status or "none",
            "epss_score": rec.epss_score if rec.epss_score is not None else 0.05,
        }
        resp = await client.post("/api/risks", json=payload, headers=it_headers)
        assert resp.status_code == 201, (
            f"POST /api/risks (connector-fed) → {resp.status_code} {resp.text}"
        )
        persisted.append(resp.json())

    # ── 6) Risks land in the tenant's register ─────────────────────────────
    list_resp = await client.get("/api/risks", headers=it_headers)
    assert list_resp.status_code == 200
    body = list_resp.json()
    assert body["total"] == len(persisted)

    # Each persisted risk_id is in the listing
    listed_ids = {r["risk_id"] for r in body["items"]}
    assert listed_ids == {r["risk_id"] for r in persisted}

    # ── 7) Connector health check is ok ────────────────────────────────────
    from connectors.base.registry import _global_registry

    factory = _global_registry.get("simulator")
    instance = factory()
    health = instance.health_check()
    assert health.status == "ok"
    assert health.connector_name == "simulator"


@pytest.mark.asyncio
async def test_workflow_08_unknown_connector_logged_skipped(
    tenant_factory,
):
    """If a tenant_config lists a connector that isn't registered, the
    scheduler logs and continues — it does NOT raise (so a bad config in
    one tenant cannot DoS the scheduler for everyone)."""
    onboarding = await tenant_factory(slug="conn-bad-cfg")
    scheduler = ConnectorScheduler()

    records = await scheduler.tick({
        "tenant_id": str(onboarding["tenant_id"]),
        "enabled_connectors": ["does-not-exist"],
        "connector_credentials": {},
    })
    assert records == []
