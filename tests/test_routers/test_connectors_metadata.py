"""
TDD — backend/routers/connectors.py — Tool Catalog metadata endpoints.

P33-Z3: Verifies that GET /api/connectors returns full metadata for every
registered connector AND that GET /api/connectors/categories returns the
filter aggregates.

Endpoints under test
--------------------
  GET /api/connectors                         — rich Tool Catalog feed
  GET /api/connectors?category=VM             — filter by category
  GET /api/connectors?status=simulated        — filter by status
  GET /api/connectors/categories              — aggregates per filter chip

Per-tenant runtime fields (configured / last_poll_at / health_status /
error_count_24h) are pulled from connector_health_summaries (FV-3) +
tenant_connector_credentials, so the tests seed those tables directly.
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
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.middleware.auth import create_access_token, hash_password
from backend.models.agent_ingest import ConnectorHealthSummary
from backend.models.subscription import TenantSubscription
from backend.models.tenant import Tenant
from backend.models.tenant_connector_credential import TenantConnectorCredential
from backend.models.user import User


REAL_CONNECTORS = {
    "tenable",
    "sentinelone",
    "zscaler",
    "netskope",
    "ms_entra",
    "manageengine_sdp",
    "cloudsek",
    "simulator",
    "extended_simulator",
}


# ─────────────────────────────────────────────────────────────────────────────
# Registry isolation — pin global registry to the 9 "real" connectors that the
# Tool Catalog tests are written against.
#
# Why this fixture exists
# -----------------------
# The connector registry is a *global* state populated by class-decorator side
# effects at import time (`@register_connector("name")`).  When this test file
# is run in isolation, only the 9 connectors imported by ``backend.main`` are
# present in the registry.  When the full pytest suite runs, importing other
# test modules (e.g. tests/test_connectors/test_crowdstrike.py) loads *more*
# connector classes — each of which registers itself globally — and the
# registry grows beyond the 9 names this test was written against.
#
# That global-state pollution makes assertions like ``names == ["sentinelone"]``
# or ``by_cat["EDR"]["count"] == 1`` fail in batch even though they pass alone.
#
# Per INV-6, we don't relax the assertions; we restore deterministic state at
# the fixture layer.  The fixture snapshots the entire registry, removes any
# names not in REAL_CONNECTORS for the test body, then restores the full
# snapshot afterwards so other tests are unaffected.
# ─────────────────────────────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def _isolate_connector_registry():
    """Filter the global connector registry to REAL_CONNECTORS for each test."""
    from connectors.base.registry import _global_registry

    snapshot = dict(_global_registry._store)
    # Keep only the 9 baseline connectors during the test.
    pinned = {
        name: factory
        for name, factory in snapshot.items()
        if name in REAL_CONNECTORS
    }
    _global_registry._store = pinned
    try:
        yield
    finally:
        # Restore EVERY entry that existed before the test, including any new
        # registrations that may have happened during the test (defensive).
        restored = dict(snapshot)
        for k, v in _global_registry._store.items():
            restored.setdefault(k, v)
        _global_registry._store = restored


# ─────────────────────────────────────────────────────────────────────────────
# Fixtures — CORE module subscription is required by the router (require_module).
# ─────────────────────────────────────────────────────────────────────────────


@pytest_asyncio.fixture
async def core_subscription(
    db_session: AsyncSession, default_tenant: Tenant,
) -> TenantSubscription:
    """Enable CORE module so /api/connectors* isn't 403'd."""
    sub = TenantSubscription(
        id=uuid.uuid4(),
        tenant_id=default_tenant.id,
        module_code="CORE",
        is_enabled=True,
        billing_tier="STANDARD",
    )
    db_session.add(sub)
    await db_session.commit()
    await db_session.refresh(sub)
    return sub


@pytest_asyncio.fixture
async def second_tenant(db_session: AsyncSession) -> Tenant:
    """A second tenant for cross-tenant isolation tests."""
    t = Tenant(
        id=uuid.uuid4(),
        name="Tenant B",
        slug="tenant-b",
        domain="tenant-b.test",
        is_active=True,
        settings={},
    )
    db_session.add(t)
    # CORE subscription so the user's requests don't 403
    sub = TenantSubscription(
        id=uuid.uuid4(),
        tenant_id=t.id,
        module_code="CORE",
        is_enabled=True,
        billing_tier="STANDARD",
    )
    db_session.add(sub)
    await db_session.commit()
    await db_session.refresh(t)
    return t


@pytest_asyncio.fixture
async def second_tenant_headers(
    db_session: AsyncSession, second_tenant: Tenant,
) -> dict[str, str]:
    """Auth headers for a CISO scoped to the second tenant."""
    user = User(
        id=uuid.uuid4(),
        email="cisob@tenant-b.test",
        hashed_password=hash_password("Secure#PassB"),
        full_name="Tenant B CISO",
        role="ciso",
        team="Security",
        is_active=True,
        tenant_id=second_tenant.id,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)

    token = create_access_token(
        str(user.id), user.role, tenant_id=str(second_tenant.id),
    )
    return {"Authorization": f"Bearer {token}"}


# ─────────────────────────────────────────────────────────────────────────────
# GET /api/connectors — rich metadata feed
# ─────────────────────────────────────────────────────────────────────────────


class TestListConnectorsMetadata:
    @pytest.mark.anyio
    async def test_list_returns_metadata_for_every_connector(
        self, client, auth_headers, core_subscription,
    ):
        resp = await client.get("/api/connectors", headers=auth_headers)
        assert resp.status_code == 200, resp.text
        body = resp.json()

        names = {item["name"] for item in body["items"]}
        for expected in REAL_CONNECTORS:
            assert expected in names, f"Missing connector {expected!r}"

        # Spot-check Tenable's metadata is fully populated.
        tenable = next(i for i in body["items"] if i["name"] == "tenable")
        assert tenable["display_name"] == "Tenable Vulnerability Manager"
        assert tenable["category"] == "VM"
        assert tenable["status"] == "live"
        assert tenable["module_code"] == "VM"
        assert tenable["short_description"]
        assert tenable["vendor_docs_url"].startswith("https://")
        assert isinstance(tenable["credential_fields"], list)
        assert len(tenable["credential_fields"]) >= 2
        # Required field markers carry over
        sk_field = next(
            f for f in tenable["credential_fields"] if f["name"] == "secret_key"
        )
        assert sk_field["secret"] is True
        assert sk_field["required"] is True
        assert sk_field["type"] == "password"

    @pytest.mark.anyio
    async def test_list_includes_per_tenant_runtime_fields(
        self, client, auth_headers, core_subscription,
    ):
        resp = await client.get("/api/connectors", headers=auth_headers)
        assert resp.status_code == 200, resp.text
        item = resp.json()["items"][0]
        # Runtime fields exist in the response shape (not just static metadata).
        for key in ("configured", "last_poll_at", "health_status", "error_count_24h"):
            assert key in item, f"Catalog item missing runtime field {key!r}"
        # Fresh tenant: nothing configured, no health rows.
        for it in resp.json()["items"]:
            assert it["configured"] is False
            assert it["last_poll_at"] is None
            assert it["health_status"] is None
            assert it["error_count_24h"] == 0

    @pytest.mark.anyio
    async def test_list_filter_by_category(
        self, client, auth_headers, core_subscription,
    ):
        resp = await client.get(
            "/api/connectors?category=VM", headers=auth_headers,
        )
        assert resp.status_code == 200
        body = resp.json()
        names = [i["name"] for i in body["items"]]
        # Only Tenable is in VM among the 9 real connectors loaded.
        assert names == ["tenable"]
        assert body["total"] == 1

    @pytest.mark.anyio
    async def test_list_filter_by_category_case_insensitive(
        self, client, auth_headers, core_subscription,
    ):
        resp = await client.get(
            "/api/connectors?category=edr", headers=auth_headers,
        )
        assert resp.status_code == 200
        names = [i["name"] for i in resp.json()["items"]]
        assert names == ["sentinelone"]

    @pytest.mark.anyio
    async def test_list_filter_by_status(
        self, client, auth_headers, core_subscription,
    ):
        resp = await client.get(
            "/api/connectors?status=simulated", headers=auth_headers,
        )
        assert resp.status_code == 200
        body = resp.json()
        names = sorted(i["name"] for i in body["items"])
        assert names == ["extended_simulator", "simulator"]
        assert all(i["status"] == "simulated" for i in body["items"])

    @pytest.mark.anyio
    async def test_list_pagination_still_works(
        self, client, auth_headers, core_subscription,
    ):
        resp = await client.get(
            "/api/connectors?limit=3&offset=0", headers=auth_headers,
        )
        assert resp.status_code == 200
        body = resp.json()
        assert len(body["items"]) == 3
        assert body["total"] >= 9

    @pytest.mark.anyio
    async def test_list_reflects_health_summary(
        self,
        client,
        db_session,
        auth_headers,
        default_tenant,
        core_subscription,
    ):
        """When a ConnectorHealthSummary row exists, the API surfaces it."""
        now = datetime.now(timezone.utc)
        chs = ConnectorHealthSummary(
            id=uuid.uuid4(),
            tenant_id=default_tenant.id,
            connector_name="tenable",
            status="degraded",
            last_poll_at=now - timedelta(minutes=10),
            error_count_24h=4,
            last_error="rate limited",
        )
        db_session.add(chs)
        await db_session.commit()

        resp = await client.get("/api/connectors", headers=auth_headers)
        assert resp.status_code == 200
        tenable = next(
            i for i in resp.json()["items"] if i["name"] == "tenable"
        )
        assert tenable["health_status"] == "degraded"
        assert tenable["error_count_24h"] == 4
        assert tenable["last_poll_at"] is not None

    @pytest.mark.anyio
    async def test_list_reflects_configured_flag(
        self,
        client,
        db_session,
        auth_headers,
        default_tenant,
        core_subscription,
    ):
        """A row in tenant_connector_credentials → configured=True."""
        cred = TenantConnectorCredential(
            id=uuid.uuid4(),
            tenant_id=default_tenant.id,
            connector_name="simulator",
            encrypted_blob=b"fake-encrypted-bytes",
        )
        db_session.add(cred)
        await db_session.commit()

        resp = await client.get("/api/connectors", headers=auth_headers)
        items = {i["name"]: i for i in resp.json()["items"]}
        assert items["simulator"]["configured"] is True
        # All others remain unconfigured
        assert items["tenable"]["configured"] is False

    @pytest.mark.anyio
    async def test_list_cross_tenant_isolation(
        self,
        client,
        db_session,
        auth_headers,
        second_tenant_headers,
        default_tenant,
        second_tenant,
        core_subscription,
    ):
        """Tenant A configures simulator → Tenant B must NOT see it configured."""
        db_session.add(
            TenantConnectorCredential(
                id=uuid.uuid4(),
                tenant_id=default_tenant.id,
                connector_name="simulator",
                encrypted_blob=b"tenant-a-blob",
            )
        )
        # Also seed a health row for tenant A only.
        db_session.add(
            ConnectorHealthSummary(
                id=uuid.uuid4(),
                tenant_id=default_tenant.id,
                connector_name="simulator",
                status="ok",
                last_poll_at=datetime.now(timezone.utc),
                error_count_24h=0,
                last_error=None,
            )
        )
        await db_session.commit()

        # Tenant A sees configured=True + health
        resp_a = await client.get("/api/connectors", headers=auth_headers)
        sim_a = next(
            i for i in resp_a.json()["items"] if i["name"] == "simulator"
        )
        assert sim_a["configured"] is True
        assert sim_a["health_status"] == "ok"

        # Tenant B sees configured=False and no health
        resp_b = await client.get(
            "/api/connectors", headers=second_tenant_headers,
        )
        assert resp_b.status_code == 200
        sim_b = next(
            i for i in resp_b.json()["items"] if i["name"] == "simulator"
        )
        assert sim_b["configured"] is False
        assert sim_b["health_status"] is None
        assert sim_b["error_count_24h"] == 0

    @pytest.mark.anyio
    async def test_list_requires_authentication(self, client):
        """No JWT → 401/403."""
        resp = await client.get("/api/connectors")
        assert resp.status_code in (401, 403)

    @pytest.mark.anyio
    async def test_list_requires_core_module(
        self, client, db_session,
    ):
        """No CORE subscription on the user's tenant → 403."""
        # Build a fresh tenant + CISO user WITHOUT a CORE subscription.
        # We bypass the auth_headers fixture because pytest-asyncio's auto
        # mode appears to share fixture resolution across class tests, which
        # can pull `core_subscription` into auth_headers' dependency closure.
        t_no_core = Tenant(
            id=uuid.uuid4(),
            name="No-Core Tenant",
            slug="no-core",
            domain="no-core.test",
            is_active=True,
            settings={},
        )
        db_session.add(t_no_core)
        u = User(
            id=uuid.uuid4(),
            email="cisonc@no-core.test",
            hashed_password=hash_password("Secure#Pass1"),
            full_name="No-Core CISO",
            role="ciso",
            team="Security",
            is_active=True,
            tenant_id=t_no_core.id,
        )
        db_session.add(u)
        await db_session.commit()
        await db_session.refresh(u)
        token = create_access_token(
            str(u.id), u.role, tenant_id=str(t_no_core.id),
        )
        headers = {"Authorization": f"Bearer {token}"}

        resp = await client.get("/api/connectors", headers=headers)
        assert resp.status_code == 403, resp.text
        assert "CORE" in resp.text


# ─────────────────────────────────────────────────────────────────────────────
# GET /api/connectors/categories — filter aggregates
# ─────────────────────────────────────────────────────────────────────────────


class TestCategoriesAggregate:
    @pytest.mark.anyio
    async def test_categories_returns_distinct_with_counts(
        self, client, auth_headers, core_subscription,
    ):
        resp = await client.get(
            "/api/connectors/categories", headers=auth_headers,
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert "categories" in body
        assert body["total_categories"] == len(body["categories"])

        by_cat = {c["category"]: c for c in body["categories"]}
        # Spot-check expected categories from the 9 real connectors.
        assert by_cat["VM"]["count"] == 1
        assert by_cat["EDR"]["count"] == 1
        assert by_cat["NETWORK"]["count"] == 1
        assert by_cat["IDENTITY"]["count"] == 1
        assert by_cat["DLP"]["count"] == 1
        assert by_cat["ITSM"]["count"] == 1
        assert by_cat["EXTERNAL_THREAT"]["count"] == 1
        assert by_cat["SIMULATOR"]["count"] == 2

        # Fresh tenant — no connectors configured yet.
        for c in body["categories"]:
            assert c["configured_count"] == 0

    @pytest.mark.anyio
    async def test_categories_configured_count_per_tenant(
        self,
        client,
        db_session,
        auth_headers,
        default_tenant,
        core_subscription,
    ):
        """Configured connector → its category's configured_count increments."""
        db_session.add(
            TenantConnectorCredential(
                id=uuid.uuid4(),
                tenant_id=default_tenant.id,
                connector_name="tenable",
                encrypted_blob=b"blob",
            )
        )
        await db_session.commit()

        resp = await client.get(
            "/api/connectors/categories", headers=auth_headers,
        )
        by_cat = {c["category"]: c for c in resp.json()["categories"]}
        assert by_cat["VM"]["configured_count"] == 1
        # Other categories untouched
        assert by_cat["EDR"]["configured_count"] == 0

    @pytest.mark.anyio
    async def test_categories_requires_authentication(self, client):
        resp = await client.get("/api/connectors/categories")
        assert resp.status_code in (401, 403)
