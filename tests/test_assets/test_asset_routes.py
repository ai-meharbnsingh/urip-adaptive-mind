"""
Asset REST endpoint tests.

Covers:
- GET /api/assets (pagination, filters, tenant isolation)
- GET /api/assets/categories (counts per category)
- GET /api/assets/{id} (with bundled risks)
- PATCH /api/assets/{id} (admin only, validation)
- GET /api/assets/{id}/risks
- GET /api/assets/{id}/timeline
- 401/403 for unauth and missing CORE module
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import AsyncGenerator

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from backend.main import app
from backend.middleware.auth import create_access_token, hash_password
from backend.models.asset import Asset
from backend.models.risk import Risk
from backend.models.subscription import TenantSubscription
from backend.models.tenant import Tenant
from backend.models.user import User


@pytest_asyncio.fixture
async def isolated_client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    async def _override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


async def _make_tenant_and_users(db: AsyncSession, slug: str, with_core: bool = True):
    tenant = Tenant(
        id=uuid.uuid4(),
        name=f"Tenant {slug}",
        slug=slug,
        domain=f"{slug}.test",
        is_active=True,
        settings={},
    )
    db.add(tenant)
    await db.commit()
    await db.refresh(tenant)

    if with_core:
        db.add(
            TenantSubscription(
                id=uuid.uuid4(),
                tenant_id=tenant.id,
                module_code="CORE",
                is_enabled=True,
                billing_tier="STANDARD",
                expires_at=None,
            )
        )

    admin = User(
        id=uuid.uuid4(),
        email=f"admin-{slug}@x.test",
        hashed_password=hash_password("Secure#Pass1"),
        full_name=f"Admin {slug}",
        role="ciso",
        team="Security",
        is_active=True,
        tenant_id=tenant.id,
    )
    it = User(
        id=uuid.uuid4(),
        email=f"it-{slug}@x.test",
        hashed_password=hash_password("Secure#Pass2"),
        full_name=f"IT {slug}",
        role="it_team",
        team="Infrastructure",
        is_active=True,
        tenant_id=tenant.id,
    )
    db.add_all([admin, it])
    await db.commit()
    await db.refresh(admin)
    await db.refresh(it)

    admin_tok = create_access_token(str(admin.id), admin.role, tenant_id=str(tenant.id))
    it_tok = create_access_token(str(it.id), it.role, tenant_id=str(tenant.id))
    return tenant, admin, it, {
        "admin": {"Authorization": f"Bearer {admin_tok}"},
        "it": {"Authorization": f"Bearer {it_tok}"},
    }


async def _seed_asset(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    *,
    hostname: str,
    fingerprint_key: str | None = None,
    device_category: str = "IT",
    asset_tier: str = "T2",
    owner_team: str | None = "Infrastructure",
    custom_tags: dict | None = None,
    device_type: str | None = "server",
    source_connectors: list[str] | None = None,
) -> Asset:
    fp = fingerprint_key or (hostname + "-fp").ljust(64, "z")[:64]
    a = Asset(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        fingerprint_key=fp,
        hostname=hostname,
        internal_ip="10.0.0.5",
        device_type=device_type,
        device_category=device_category,
        os_name="Linux",
        owner_team=owner_team,
        asset_tier=asset_tier,
        lifecycle_state="in_use",
        discovered_at=datetime.now(timezone.utc),
        last_seen=datetime.now(timezone.utc),
        source_connectors=source_connectors or ["tenable"],
        custom_tags=custom_tags or {},
    )
    db.add(a)
    await db.commit()
    await db.refresh(a)
    return a


# ─────────────────────────────────────────────────────────────────────────────
# Authorisation
# ─────────────────────────────────────────────────────────────────────────────


class TestAuthGate:
    async def test_unauthenticated_rejected(self, isolated_client: AsyncClient):
        r = await isolated_client.get("/api/assets")
        assert r.status_code in (401, 403)

    async def test_no_core_subscription_rejected(
        self, isolated_client: AsyncClient, db_session: AsyncSession
    ):
        tenant, _admin, _it, headers = await _make_tenant_and_users(
            db_session, "no-core", with_core=False
        )
        r = await isolated_client.get("/api/assets", headers=headers["it"])
        assert r.status_code == 403


# ─────────────────────────────────────────────────────────────────────────────
# GET /api/assets
# ─────────────────────────────────────────────────────────────────────────────


class TestListAssets:
    async def test_basic_list_paginated(
        self, isolated_client: AsyncClient, db_session: AsyncSession
    ):
        tenant, _admin, _it, headers = await _make_tenant_and_users(
            db_session, "list-basic"
        )
        for i in range(5):
            await _seed_asset(
                db_session,
                tenant.id,
                hostname=f"basic-{i}",
                fingerprint_key=f"basic-fp-{i}".ljust(64, "x")[:64],
            )

        r = await isolated_client.get(
            "/api/assets?limit=3", headers=headers["it"]
        )
        assert r.status_code == 200
        body = r.json()
        assert body["total"] == 5
        assert len(body["items"]) == 3
        assert body["limit"] == 3
        # Each item must include identification + classification
        first = body["items"][0]
        for k in (
            "id",
            "hostname",
            "device_category",
            "asset_tier",
            "lifecycle_state",
            "category",
        ):
            assert k in first

    async def test_filter_device_category(
        self, isolated_client: AsyncClient, db_session: AsyncSession
    ):
        tenant, _a, _i, headers = await _make_tenant_and_users(db_session, "fil-dc")
        await _seed_asset(
            db_session,
            tenant.id,
            hostname="it-h",
            fingerprint_key="it-fp".ljust(64, "x")[:64],
            device_category="IT",
        )
        await _seed_asset(
            db_session,
            tenant.id,
            hostname="ot-h",
            fingerprint_key="ot-fp".ljust(64, "x")[:64],
            device_category="OT",
        )

        r = await isolated_client.get(
            "/api/assets?device_category=IT", headers=headers["it"]
        )
        assert r.status_code == 200
        body = r.json()
        assert body["total"] == 1
        assert body["items"][0]["hostname"] == "it-h"

    async def test_filter_asset_tier(
        self, isolated_client: AsyncClient, db_session: AsyncSession
    ):
        tenant, _a, _i, headers = await _make_tenant_and_users(db_session, "fil-tier")
        await _seed_asset(
            db_session,
            tenant.id,
            hostname="t1-h",
            fingerprint_key="t1-fp".ljust(64, "x")[:64],
            asset_tier="T1",
        )
        await _seed_asset(
            db_session,
            tenant.id,
            hostname="t3-h",
            fingerprint_key="t3-fp".ljust(64, "x")[:64],
            asset_tier="T3",
        )
        r = await isolated_client.get(
            "/api/assets?asset_tier=T1", headers=headers["it"]
        )
        assert r.status_code == 200
        body = r.json()
        assert body["total"] == 1
        assert body["items"][0]["hostname"] == "t1-h"

    async def test_invalid_filter_rejected(
        self, isolated_client: AsyncClient, db_session: AsyncSession
    ):
        tenant, _a, _i, headers = await _make_tenant_and_users(
            db_session, "fil-bad"
        )
        r = await isolated_client.get(
            "/api/assets?device_category=BOGUS", headers=headers["it"]
        )
        assert r.status_code == 422

    async def test_tenant_isolation(
        self, isolated_client: AsyncClient, db_session: AsyncSession
    ):
        tenant_a, _, _, headers_a = await _make_tenant_and_users(
            db_session, "iso-r-a"
        )
        tenant_b, _, _, headers_b = await _make_tenant_and_users(
            db_session, "iso-r-b"
        )
        await _seed_asset(
            db_session,
            tenant_a.id,
            hostname="iso-a-h",
            fingerprint_key="iso-a-fp".ljust(64, "x")[:64],
        )
        await _seed_asset(
            db_session,
            tenant_b.id,
            hostname="iso-b-h",
            fingerprint_key="iso-b-fp".ljust(64, "x")[:64],
        )

        r_a = await isolated_client.get("/api/assets", headers=headers_a["it"])
        assert {i["hostname"] for i in r_a.json()["items"]} == {"iso-a-h"}

        r_b = await isolated_client.get("/api/assets", headers=headers_b["it"])
        assert {i["hostname"] for i in r_b.json()["items"]} == {"iso-b-h"}


# ─────────────────────────────────────────────────────────────────────────────
# GET /api/assets/categories
# ─────────────────────────────────────────────────────────────────────────────


class TestCategoriesEndpoint:
    async def test_returns_counts(
        self, isolated_client: AsyncClient, db_session: AsyncSession
    ):
        tenant, _a, _i, headers = await _make_tenant_and_users(
            db_session, "cat-cnt"
        )
        await _seed_asset(
            db_session,
            tenant.id,
            hostname="laptop1",
            fingerprint_key="lap1-fp".ljust(64, "x")[:64],
            device_type="laptop",
        )
        await _seed_asset(
            db_session,
            tenant.id,
            hostname="cloud1",
            fingerprint_key="cloud1-fp".ljust(64, "x")[:64],
            device_type="cloud_workload",
        )
        r = await isolated_client.get(
            "/api/assets/categories", headers=headers["it"]
        )
        assert r.status_code == 200
        body = r.json()
        assert body["counts"]["Devices"] == 1
        assert body["counts"]["Cloud Assets"] == 1
        assert body["total"] == 2


# ─────────────────────────────────────────────────────────────────────────────
# GET /api/assets/{id}
# ─────────────────────────────────────────────────────────────────────────────


class TestGetAssetDetail:
    async def test_includes_open_risks(
        self, isolated_client: AsyncClient, db_session: AsyncSession
    ):
        tenant, _a, _i, headers = await _make_tenant_and_users(
            db_session, "det-risk"
        )
        asset = await _seed_asset(
            db_session,
            tenant.id,
            hostname="det-h",
            fingerprint_key="det-fp".ljust(64, "x")[:64],
        )
        for sev, sc in (("critical", 9.5), ("high", 7.0)):
            db_session.add(
                Risk(
                    id=uuid.uuid4(),
                    risk_id=f"RISK-DET-{sev}",
                    finding=f"{sev} risk",
                    source="tenable",
                    domain="endpoint",
                    cvss_score=sc,
                    severity=sev,
                    asset="det-h",
                    owner_team="x",
                    status="open",
                    sla_deadline=datetime.now(timezone.utc),
                    tenant_id=tenant.id,
                    asset_id=asset.id,
                    composite_score=sc,
                )
            )
        await db_session.commit()

        r = await isolated_client.get(
            f"/api/assets/{asset.id}", headers=headers["it"]
        )
        assert r.status_code == 200
        body = r.json()
        assert body["asset"]["hostname"] == "det-h"
        assert body["risk_count"] == 2
        assert body["max_score"] == 9.5

    async def test_404_for_other_tenant_asset(
        self, isolated_client: AsyncClient, db_session: AsyncSession
    ):
        tenant_a, _, _, _ = await _make_tenant_and_users(db_session, "det-a")
        tenant_b, _, _, headers_b = await _make_tenant_and_users(
            db_session, "det-b"
        )
        asset_a = await _seed_asset(
            db_session,
            tenant_a.id,
            hostname="cross-h",
            fingerprint_key="cross-fp".ljust(64, "x")[:64],
        )
        r = await isolated_client.get(
            f"/api/assets/{asset_a.id}", headers=headers_b["it"]
        )
        assert r.status_code == 404

    async def test_invalid_uuid_returns_422(
        self, isolated_client: AsyncClient, db_session: AsyncSession
    ):
        _t, _a, _i, headers = await _make_tenant_and_users(db_session, "bad-id")
        r = await isolated_client.get(
            "/api/assets/not-a-uuid", headers=headers["it"]
        )
        assert r.status_code == 422


# ─────────────────────────────────────────────────────────────────────────────
# PATCH /api/assets/{id}
# ─────────────────────────────────────────────────────────────────────────────


class TestPatchAsset:
    async def test_admin_can_update_owner_and_tags(
        self, isolated_client: AsyncClient, db_session: AsyncSession
    ):
        tenant, _admin, _it, headers = await _make_tenant_and_users(
            db_session, "patch-ok"
        )
        asset = await _seed_asset(
            db_session,
            tenant.id,
            hostname="patch-h",
            fingerprint_key="patch-fp".ljust(64, "x")[:64],
        )
        r = await isolated_client.patch(
            f"/api/assets/{asset.id}",
            json={
                "owner_team": "AppSec",
                "custom_tags": {"env": "prod", "owner_email": "a@x.test"},
                "business_criticality": "critical",
                "notes": "Migrated from legacy.",
            },
            headers=headers["admin"],
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["owner_team"] == "AppSec"
        assert body["custom_tags"] == {
            "env": "prod",
            "owner_email": "a@x.test",
        }
        assert body["business_criticality"] == "critical"
        assert body["notes"] == "Migrated from legacy."

    async def test_non_admin_cannot_patch(
        self, isolated_client: AsyncClient, db_session: AsyncSession
    ):
        tenant, _admin, _it, headers = await _make_tenant_and_users(
            db_session, "patch-403"
        )
        asset = await _seed_asset(
            db_session,
            tenant.id,
            hostname="x",
            fingerprint_key="x-fp".ljust(64, "x")[:64],
        )
        r = await isolated_client.patch(
            f"/api/assets/{asset.id}",
            json={"owner_team": "AppSec"},
            headers=headers["it"],
        )
        assert r.status_code == 403

    async def test_invalid_business_criticality_rejected(
        self, isolated_client: AsyncClient, db_session: AsyncSession
    ):
        tenant, _admin, _it, headers = await _make_tenant_and_users(
            db_session, "patch-bad"
        )
        asset = await _seed_asset(
            db_session,
            tenant.id,
            hostname="x",
            fingerprint_key="bad-fp".ljust(64, "x")[:64],
        )
        r = await isolated_client.patch(
            f"/api/assets/{asset.id}",
            json={"business_criticality": "BOGUS"},
            headers=headers["admin"],
        )
        assert r.status_code == 422


# ─────────────────────────────────────────────────────────────────────────────
# GET /api/assets/{id}/risks
# ─────────────────────────────────────────────────────────────────────────────


class TestAssetRisks:
    async def test_lists_open_risks(
        self, isolated_client: AsyncClient, db_session: AsyncSession
    ):
        tenant, _a, _i, headers = await _make_tenant_and_users(
            db_session, "risks-ep"
        )
        asset = await _seed_asset(
            db_session,
            tenant.id,
            hostname="risks-h",
            fingerprint_key="risks-fp".ljust(64, "x")[:64],
        )
        for i in range(3):
            db_session.add(
                Risk(
                    id=uuid.uuid4(),
                    risk_id=f"RISK-EP-{i}",
                    finding=f"Risk {i}",
                    source="tenable",
                    domain="endpoint",
                    cvss_score=8.0,
                    severity="high",
                    asset="risks-h",
                    owner_team="x",
                    status="open",
                    sla_deadline=datetime.now(timezone.utc),
                    tenant_id=tenant.id,
                    asset_id=asset.id,
                    composite_score=8.0,
                )
            )
        await db_session.commit()

        r = await isolated_client.get(
            f"/api/assets/{asset.id}/risks", headers=headers["it"]
        )
        assert r.status_code == 200
        body = r.json()
        assert body["total"] == 3
        assert len(body["items"]) == 3


# ─────────────────────────────────────────────────────────────────────────────
# GET /api/assets/{id}/timeline
# ─────────────────────────────────────────────────────────────────────────────


class TestAssetTimeline:
    async def test_returns_chronological_events(
        self, isolated_client: AsyncClient, db_session: AsyncSession
    ):
        tenant, _a, _i, headers = await _make_tenant_and_users(
            db_session, "tl-ep"
        )
        asset = await _seed_asset(
            db_session,
            tenant.id,
            hostname="tl-h",
            fingerprint_key="tl-fp".ljust(64, "x")[:64],
        )
        db_session.add(
            Risk(
                id=uuid.uuid4(),
                risk_id="RISK-TL-A",
                finding="risk a",
                source="tenable",
                domain="endpoint",
                cvss_score=8.0,
                severity="high",
                asset="tl-h",
                owner_team="x",
                status="open",
                sla_deadline=datetime.now(timezone.utc),
                tenant_id=tenant.id,
                asset_id=asset.id,
                composite_score=8.0,
            )
        )
        await db_session.commit()

        r = await isolated_client.get(
            f"/api/assets/{asset.id}/timeline", headers=headers["it"]
        )
        assert r.status_code == 200
        body = r.json()
        assert body["total"] >= 2
        types = [e["event_type"] for e in body["items"]]
        assert "discovered" in types
        assert "risk_added" in types
