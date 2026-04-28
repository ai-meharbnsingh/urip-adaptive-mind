"""
TDD tests — backend/routers/connectors.py

Covers the new /api/connectors top-level router that the frontend
connector-wizard.js calls (FV-1 spec).

Endpoints under test:
  - GET    /api/connectors                       — list types + per-tenant config status
  - GET    /api/connectors/{name}                — connector schema for the wizard
  - POST   /api/connectors/{name}/configure      — store encrypted credentials
  - POST   /api/connectors/{name}/test           — test connection (uses simulator backend)
  - DELETE /api/connectors/{name}                — remove credentials
  - POST   /api/connectors/{name}/run-now        — trigger immediate poll (admin only)
  - GET    /api/connectors/{name}/health         — connector health summary
  - GET    /api/connectors/{name}/findings       — recent findings for tenant

The simulator + extended_simulator are used as the "known-good" backend for the
test-connection tests (no real API calls).
"""
from __future__ import annotations

import os
import uuid

# Set Fernet key BEFORE backend imports.
os.environ.setdefault(
    "URIP_FERNET_KEY",
    "M3JKpUVOfx1nPLQYMRrxnVZsJq3cJ5vXq7bOe6jfXok=",
)
os.environ.setdefault("DISABLE_CONNECTOR_SCHEDULER", "true")

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select


# ─────────────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture
def simulator_credentials() -> dict:
    """Credentials accepted by the simulator connector (no real auth)."""
    return {"tenant_id": "test-tenant", "note": "simulator-no-auth-needed"}


# ─────────────────────────────────────────────────────────────────────────────
# GET /api/connectors — list all registered + per-tenant config status
# ─────────────────────────────────────────────────────────────────────────────

class TestListConnectors:
    @pytest.mark.anyio
    async def test_list_returns_all_registered_connectors(
        self, client, auth_headers
    ):
        # include_dev=true so the simulator + extended_simulator (dev-only
        # connectors) show up alongside production ones.
        resp = await client.get(
            "/api/connectors?include_dev=true", headers=auth_headers
        )
        assert resp.status_code == 200, resp.text

        body = resp.json()
        assert "items" in body, f"Missing 'items' key: {body}"
        assert "total" in body, f"Missing 'total' key: {body}"

        names = {item["name"] for item in body["items"]}
        # All 9 production + simulator connectors must show up
        for expected in (
            "tenable", "sentinelone", "zscaler", "netskope",
            "ms_entra", "manageengine_sdp", "cloudsek",
            "simulator", "extended_simulator",
        ):
            assert expected in names, f"Missing connector '{expected}' in list"

    @pytest.mark.anyio
    async def test_list_supports_pagination(self, client, auth_headers):
        resp = await client.get(
            "/api/connectors?include_dev=true&limit=3&offset=0",
            headers=auth_headers,
        )
        assert resp.status_code == 200
        body = resp.json()
        assert len(body["items"]) == 3
        assert body["total"] >= 9

    @pytest.mark.anyio
    async def test_list_marks_unconfigured_by_default(
        self, client, auth_headers
    ):
        resp = await client.get(
            "/api/connectors?include_dev=true", headers=auth_headers
        )
        body = resp.json()
        # Fresh tenant → none configured
        for item in body["items"]:
            assert item["configured"] is False

    @pytest.mark.anyio
    async def test_list_requires_authentication(self, client):
        resp = await client.get("/api/connectors")
        assert resp.status_code in (401, 403)


# ─────────────────────────────────────────────────────────────────────────────
# GET /api/connectors/{name} — schema
# ─────────────────────────────────────────────────────────────────────────────

class TestGetConnectorSchema:
    @pytest.mark.anyio
    async def test_returns_schema_with_fields(self, client, auth_headers):
        resp = await client.get(
            "/api/connectors/tenable", headers=auth_headers
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["name"] == "tenable"
        assert "fields" in body, f"Schema missing 'fields': {body}"
        # Tenable schema must declare its credential fields
        field_names = {f["name"] for f in body["fields"]}
        assert "access_key" in field_names
        assert "secret_key" in field_names

    @pytest.mark.anyio
    async def test_unknown_connector_returns_404(self, client, auth_headers):
        resp = await client.get(
            "/api/connectors/no_such_connector", headers=auth_headers
        )
        assert resp.status_code == 404


# ─────────────────────────────────────────────────────────────────────────────
# POST /api/connectors/{name}/configure — encrypted credential storage
# ─────────────────────────────────────────────────────────────────────────────

class TestConfigureConnector:
    @pytest.mark.anyio
    async def test_configure_persists_encrypted_blob(
        self, client, db_session, auth_headers, default_tenant, simulator_credentials
    ):
        from backend.models.tenant_connector_credential import (
            TenantConnectorCredential,
        )

        resp = await client.post(
            "/api/connectors/simulator/configure",
            headers=auth_headers,
            json={"credentials": simulator_credentials},
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["status"] == "configured"
        assert body["connector"] == "simulator"

        # Row exists in DB and blob is bytes (encrypted)
        rows = (
            await db_session.execute(
                select(TenantConnectorCredential).where(
                    TenantConnectorCredential.tenant_id == default_tenant.id,
                    TenantConnectorCredential.connector_name == "simulator",
                )
            )
        ).scalars().all()
        assert len(rows) == 1
        assert isinstance(rows[0].encrypted_blob, bytes)
        # Plaintext must not appear in the blob
        assert b"simulator-no-auth-needed" not in rows[0].encrypted_blob

    @pytest.mark.anyio
    async def test_configure_is_upsert(
        self, client, db_session, auth_headers, default_tenant, simulator_credentials
    ):
        from backend.models.tenant_connector_credential import (
            TenantConnectorCredential,
        )

        await client.post(
            "/api/connectors/simulator/configure",
            headers=auth_headers,
            json={"credentials": simulator_credentials},
        )
        # Second configure with new creds — should replace, not error
        resp = await client.post(
            "/api/connectors/simulator/configure",
            headers=auth_headers,
            json={"credentials": {"tenant_id": "test-tenant", "v": "2"}},
        )
        assert resp.status_code == 200

        rows = (
            await db_session.execute(
                select(TenantConnectorCredential).where(
                    TenantConnectorCredential.tenant_id == default_tenant.id,
                    TenantConnectorCredential.connector_name == "simulator",
                )
            )
        ).scalars().all()
        assert len(rows) == 1, "configure must upsert, not insert duplicates"

    @pytest.mark.anyio
    async def test_configure_unknown_connector_returns_404(
        self, client, auth_headers
    ):
        resp = await client.post(
            "/api/connectors/no_such_one/configure",
            headers=auth_headers,
            json={"credentials": {}},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_configure_requires_admin_role(
        self, client, it_team_headers, simulator_credentials
    ):
        resp = await client.post(
            "/api/connectors/simulator/configure",
            headers=it_team_headers,
            json={"credentials": simulator_credentials},
        )
        # IT team is below ciso → forbidden
        assert resp.status_code == 403


# ─────────────────────────────────────────────────────────────────────────────
# POST /api/connectors/{name}/test — connection test
# ─────────────────────────────────────────────────────────────────────────────

class TestTestConnection:
    @pytest.mark.anyio
    async def test_test_returns_success_for_simulator(
        self, client, auth_headers, simulator_credentials
    ):
        # Pass credentials inline (don't require pre-configure)
        resp = await client.post(
            "/api/connectors/simulator/test",
            headers=auth_headers,
            json={"credentials": simulator_credentials},
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["success"] is True
        # Sample data: simulator should expose at least one finding sample
        assert "sample" in body
        assert isinstance(body["sample"], list)

    @pytest.mark.anyio
    async def test_test_uses_stored_creds_when_no_body(
        self, client, auth_headers, simulator_credentials
    ):
        # First configure
        await client.post(
            "/api/connectors/simulator/configure",
            headers=auth_headers,
            json={"credentials": simulator_credentials},
        )
        # Then test without a body — it must reuse stored credentials
        resp = await client.post(
            "/api/connectors/simulator/test", headers=auth_headers
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["success"] is True

    @pytest.mark.anyio
    async def test_test_unknown_connector_returns_404(
        self, client, auth_headers
    ):
        resp = await client.post(
            "/api/connectors/nope/test",
            headers=auth_headers,
            json={"credentials": {}},
        )
        assert resp.status_code == 404


# ─────────────────────────────────────────────────────────────────────────────
# DELETE /api/connectors/{name}
# ─────────────────────────────────────────────────────────────────────────────

class TestDeleteConnector:
    @pytest.mark.anyio
    async def test_delete_removes_credentials(
        self, client, db_session, auth_headers, default_tenant, simulator_credentials
    ):
        from backend.models.tenant_connector_credential import (
            TenantConnectorCredential,
        )

        await client.post(
            "/api/connectors/simulator/configure",
            headers=auth_headers,
            json={"credentials": simulator_credentials},
        )
        resp = await client.delete(
            "/api/connectors/simulator", headers=auth_headers
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["status"] == "removed"

        rows = (
            await db_session.execute(
                select(TenantConnectorCredential).where(
                    TenantConnectorCredential.tenant_id == default_tenant.id,
                    TenantConnectorCredential.connector_name == "simulator",
                )
            )
        ).scalars().all()
        assert len(rows) == 0

    @pytest.mark.anyio
    async def test_delete_unconfigured_returns_404(self, client, auth_headers):
        resp = await client.delete(
            "/api/connectors/simulator", headers=auth_headers
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_requires_admin_role(
        self, client, it_team_headers
    ):
        resp = await client.delete(
            "/api/connectors/simulator", headers=it_team_headers
        )
        assert resp.status_code == 403


# ─────────────────────────────────────────────────────────────────────────────
# POST /api/connectors/{name}/run-now
# ─────────────────────────────────────────────────────────────────────────────

class TestRunNow:
    @pytest.mark.anyio
    async def test_run_now_executes_tick_and_returns_count(
        self, client, auth_headers, simulator_credentials
    ):
        await client.post(
            "/api/connectors/simulator/configure",
            headers=auth_headers,
            json={"credentials": simulator_credentials},
        )
        resp = await client.post(
            "/api/connectors/simulator/run-now", headers=auth_headers
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["status"] == "ok"
        # Simulator returns 5–15 findings — must be >= 1
        assert body["records_ingested"] >= 1

    @pytest.mark.anyio
    async def test_run_now_persists_findings_as_risks(
        self, client, db_session, auth_headers, default_tenant, simulator_credentials
    ):
        from backend.models.risk import Risk

        await client.post(
            "/api/connectors/simulator/configure",
            headers=auth_headers,
            json={"credentials": simulator_credentials},
        )
        await client.post(
            "/api/connectors/simulator/run-now", headers=auth_headers
        )

        rows = (
            await db_session.execute(
                select(Risk).where(Risk.tenant_id == default_tenant.id)
            )
        ).scalars().all()
        assert len(rows) >= 1, "run-now must persist findings as Risk rows"

    @pytest.mark.anyio
    async def test_run_now_requires_admin_role(
        self, client, it_team_headers
    ):
        resp = await client.post(
            "/api/connectors/simulator/run-now", headers=it_team_headers
        )
        assert resp.status_code == 403

    @pytest.mark.anyio
    async def test_run_now_unconfigured_returns_400(
        self, client, auth_headers
    ):
        # No credentials stored → can't run
        resp = await client.post(
            "/api/connectors/simulator/run-now", headers=auth_headers
        )
        assert resp.status_code == 400


# ─────────────────────────────────────────────────────────────────────────────
# GET /api/connectors/{name}/health
# ─────────────────────────────────────────────────────────────────────────────

class TestHealthEndpoint:
    @pytest.mark.anyio
    async def test_health_returns_status_for_known_connector(
        self, client, auth_headers
    ):
        resp = await client.get(
            "/api/connectors/simulator/health", headers=auth_headers
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["connector_name"] == "simulator"
        assert body["status"] in ("ok", "degraded", "error", "unknown")
        assert "error_count" in body

    @pytest.mark.anyio
    async def test_health_unknown_connector_returns_404(
        self, client, auth_headers
    ):
        resp = await client.get(
            "/api/connectors/nope/health", headers=auth_headers
        )
        assert resp.status_code == 404


# ─────────────────────────────────────────────────────────────────────────────
# GET /api/connectors/{name}/findings
# ─────────────────────────────────────────────────────────────────────────────

class TestFindingsEndpoint:
    @pytest.mark.anyio
    async def test_findings_returns_data_after_run_now(
        self, client, auth_headers, simulator_credentials
    ):
        await client.post(
            "/api/connectors/simulator/configure",
            headers=auth_headers,
            json={"credentials": simulator_credentials},
        )
        await client.post(
            "/api/connectors/simulator/run-now", headers=auth_headers
        )

        resp = await client.get(
            "/api/connectors/simulator/findings?limit=5",
            headers=auth_headers,
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert "items" in body
        assert len(body["items"]) >= 1

    @pytest.mark.anyio
    async def test_findings_respects_limit_param(
        self, client, auth_headers, simulator_credentials
    ):
        await client.post(
            "/api/connectors/simulator/configure",
            headers=auth_headers,
            json={"credentials": simulator_credentials},
        )
        # Run multiple times to seed enough rows
        for _ in range(3):
            await client.post(
                "/api/connectors/simulator/run-now", headers=auth_headers
            )

        resp = await client.get(
            "/api/connectors/simulator/findings?limit=2",
            headers=auth_headers,
        )
        body = resp.json()
        assert len(body["items"]) <= 2

    @pytest.mark.anyio
    async def test_findings_is_tenant_scoped(
        self,
        client,
        db_session,
        auth_headers,
        default_tenant,
        simulator_credentials,
    ):
        """A tenant cannot see another tenant's findings."""
        from backend.models.risk import Risk
        from backend.models.tenant import Tenant

        # Create a second tenant + risk under it
        other_tenant = Tenant(
            id=uuid.uuid4(),
            name="Other Tenant",
            slug="other-tenant",
            domain="other.test",
            is_active=True,
            settings={},
        )
        db_session.add(other_tenant)
        await db_session.commit()

        other_risk = Risk(
            id=uuid.uuid4(),
            risk_id="RISK-OTHER-001",
            finding="Other tenant finding",
            description="should not appear",
            source="simulator",
            domain="endpoint",
            cvss_score=9.0,
            severity="critical",
            asset="other-asset",
            owner_team="other",
            status="open",
            sla_deadline=datetime.now(timezone.utc) + timedelta(days=7),
            tenant_id=other_tenant.id,
        )
        db_session.add(other_risk)
        await db_session.commit()

        # Default tenant queries findings — must NOT see the other tenant's risk
        resp = await client.get(
            "/api/connectors/simulator/findings?limit=50",
            headers=auth_headers,
        )
        assert resp.status_code == 200
        body = resp.json()
        for item in body["items"]:
            assert item.get("finding") != "Other tenant finding"
