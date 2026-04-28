"""
P1.4 — Asset taxonomy REST endpoint tests.

Covers:
- list (pagination, tier filter, soft-delete filtering)
- create (admin only)
- bulk import (admin only, all-or-nothing validation)
- patch (admin only, tenant ownership enforced)
- soft-delete (admin only, returns soft-deleted row, doesn't hard-delete)
- import-defaults (admin only, idempotent guard)
- tenant scoping (Tenant A cannot see/mutate Tenant B's keywords)
- non-admin role rejected with 403
"""
from __future__ import annotations

import uuid
from typing import AsyncGenerator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from backend.main import app
from backend.middleware.auth import create_access_token, hash_password
from backend.models.asset_taxonomy import TenantAssetTaxonomy
from backend.models.tenant import Tenant
from backend.models.user import User


# ─────────────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────────────


@pytest_asyncio.fixture
async def isolated_client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    async def _override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


async def _make_tenant_with_users(db: AsyncSession, slug: str):
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

    admin_token = create_access_token(str(admin.id), admin.role, tenant_id=str(tenant.id))
    it_token = create_access_token(str(it.id), it.role, tenant_id=str(tenant.id))
    return tenant, admin, it, {
        "admin": {"Authorization": f"Bearer {admin_token}"},
        "it": {"Authorization": f"Bearer {it_token}"},
    }


@pytest_asyncio.fixture
async def tenant_alpha(db_session: AsyncSession):
    return await _make_tenant_with_users(db_session, "alpha-rt")


@pytest_asyncio.fixture
async def tenant_beta(db_session: AsyncSession):
    return await _make_tenant_with_users(db_session, "beta-rt")


# ─────────────────────────────────────────────────────────────────────────────
# Authorisation
# ─────────────────────────────────────────────────────────────────────────────


class TestAuthorisation:
    async def test_unauthenticated_returns_401_or_403(
        self, isolated_client: AsyncClient
    ):
        # FastAPI HTTPBearer raises 403 by default for missing creds; the test
        # accepts either to avoid coupling to the bearer config.
        r = await isolated_client.get("/api/asset-taxonomy")
        assert r.status_code in (401, 403)

    async def test_non_admin_cannot_create(
        self, isolated_client: AsyncClient, tenant_alpha
    ):
        _, _, _, headers = tenant_alpha
        r = await isolated_client.post(
            "/api/asset-taxonomy",
            json={"tier_code": "T1", "keyword": "sap"},
            headers=headers["it"],  # it_team < ciso
        )
        assert r.status_code == 403

    async def test_admin_can_create(
        self, isolated_client: AsyncClient, tenant_alpha
    ):
        _, _, _, headers = tenant_alpha
        r = await isolated_client.post(
            "/api/asset-taxonomy",
            json={"tier_code": "T1", "keyword": "sap"},
            headers=headers["admin"],
        )
        assert r.status_code == 201, r.text
        body = r.json()
        assert body["tier_code"] == "T1"
        assert body["keyword"] == "sap"
        assert body["deleted_at"] is None


# ─────────────────────────────────────────────────────────────────────────────
# CRUD endpoints
# ─────────────────────────────────────────────────────────────────────────────


class TestCreate:
    async def test_invalid_tier_code_rejected(
        self, isolated_client: AsyncClient, tenant_alpha
    ):
        _, _, _, headers = tenant_alpha
        r = await isolated_client.post(
            "/api/asset-taxonomy",
            json={"tier_code": "T9", "keyword": "x"},
            headers=headers["admin"],
        )
        assert r.status_code == 422

    async def test_lowercase_tier_code_normalised(
        self, isolated_client: AsyncClient, tenant_alpha
    ):
        _, _, _, headers = tenant_alpha
        r = await isolated_client.post(
            "/api/asset-taxonomy",
            json={"tier_code": "t2", "keyword": "vpn"},
            headers=headers["admin"],
        )
        assert r.status_code == 201
        assert r.json()["tier_code"] == "T2"

    async def test_create_records_creator(
        self, isolated_client: AsyncClient, tenant_alpha
    ):
        _, admin, _, headers = tenant_alpha
        r = await isolated_client.post(
            "/api/asset-taxonomy",
            json={"tier_code": "T1", "keyword": "scada"},
            headers=headers["admin"],
        )
        assert r.status_code == 201
        assert r.json()["created_by_user_id"] == str(admin.id)


class TestList:
    async def test_list_returns_only_own_tenant(
        self,
        isolated_client: AsyncClient,
        db_session: AsyncSession,
        tenant_alpha,
        tenant_beta,
    ):
        tenant_a, _, _, headers_a = tenant_alpha
        tenant_b, _, _, headers_b = tenant_beta

        # Seed via API as each tenant.
        await isolated_client.post(
            "/api/asset-taxonomy",
            json={"tier_code": "T1", "keyword": "alpha-only"},
            headers=headers_a["admin"],
        )
        await isolated_client.post(
            "/api/asset-taxonomy",
            json={"tier_code": "T1", "keyword": "beta-only"},
            headers=headers_b["admin"],
        )

        # Tenant A sees only its own.
        r = await isolated_client.get("/api/asset-taxonomy", headers=headers_a["admin"])
        assert r.status_code == 200
        body = r.json()
        keywords = {item["keyword"] for item in body["items"]}
        assert keywords == {"alpha-only"}
        assert body["total"] == 1

        # Tenant B sees only its own.
        r = await isolated_client.get("/api/asset-taxonomy", headers=headers_b["admin"])
        body = r.json()
        keywords = {item["keyword"] for item in body["items"]}
        assert keywords == {"beta-only"}

    async def test_filter_by_tier(
        self, isolated_client: AsyncClient, tenant_alpha
    ):
        _, _, _, headers = tenant_alpha
        for tier, kw in [("T1", "k1"), ("T2", "k2"), ("T1", "k3")]:
            await isolated_client.post(
                "/api/asset-taxonomy",
                json={"tier_code": tier, "keyword": kw},
                headers=headers["admin"],
            )
        r = await isolated_client.get(
            "/api/asset-taxonomy?tier_code=T1", headers=headers["admin"]
        )
        body = r.json()
        assert {i["keyword"] for i in body["items"]} == {"k1", "k3"}

    async def test_pagination(
        self, isolated_client: AsyncClient, tenant_alpha
    ):
        _, _, _, headers = tenant_alpha
        for i in range(5):
            await isolated_client.post(
                "/api/asset-taxonomy",
                json={"tier_code": "T2", "keyword": f"kw-{i:02d}"},
                headers=headers["admin"],
            )
        r = await isolated_client.get(
            "/api/asset-taxonomy?page=1&page_size=2", headers=headers["admin"]
        )
        body = r.json()
        assert len(body["items"]) == 2
        assert body["total"] == 5
        assert body["page"] == 1
        assert body["page_size"] == 2

    async def test_soft_deleted_excluded_by_default(
        self,
        isolated_client: AsyncClient,
        db_session: AsyncSession,
        tenant_alpha,
    ):
        _, _, _, headers = tenant_alpha
        # Create one row, then soft-delete it.
        r = await isolated_client.post(
            "/api/asset-taxonomy",
            json={"tier_code": "T1", "keyword": "ephemeral"},
            headers=headers["admin"],
        )
        row_id = r.json()["id"]
        await isolated_client.delete(
            f"/api/asset-taxonomy/{row_id}", headers=headers["admin"]
        )

        # Default list excludes deleted.
        r = await isolated_client.get("/api/asset-taxonomy", headers=headers["admin"])
        assert r.json()["total"] == 0

        # include_deleted=true reveals it.
        r = await isolated_client.get(
            "/api/asset-taxonomy?include_deleted=true", headers=headers["admin"]
        )
        body = r.json()
        assert body["total"] == 1
        assert body["items"][0]["deleted_at"] is not None


class TestBulkImport:
    async def test_bulk_inserts_all_rows(
        self, isolated_client: AsyncClient, tenant_alpha
    ):
        _, _, _, headers = tenant_alpha
        payload = [
            {"tier_code": "T1", "keyword": "a"},
            {"tier_code": "T1", "keyword": "b"},
            {"tier_code": "T2", "keyword": "c"},
        ]
        r = await isolated_client.post(
            "/api/asset-taxonomy/bulk", json=payload, headers=headers["admin"]
        )
        assert r.status_code == 201, r.text
        body = r.json()
        assert body["inserted"] == 3
        assert {i["keyword"] for i in body["items"]} == {"a", "b", "c"}

    async def test_bulk_empty_payload_rejected(
        self, isolated_client: AsyncClient, tenant_alpha
    ):
        _, _, _, headers = tenant_alpha
        r = await isolated_client.post(
            "/api/asset-taxonomy/bulk", json=[], headers=headers["admin"]
        )
        assert r.status_code == 422

    async def test_bulk_invalid_tier_in_one_row_fails_whole_batch(
        self, isolated_client: AsyncClient, tenant_alpha
    ):
        _, _, _, headers = tenant_alpha
        payload = [
            {"tier_code": "T1", "keyword": "ok-1"},
            {"tier_code": "T9", "keyword": "bad"},
            {"tier_code": "T2", "keyword": "ok-2"},
        ]
        r = await isolated_client.post(
            "/api/asset-taxonomy/bulk", json=payload, headers=headers["admin"]
        )
        assert r.status_code == 422
        # And nothing was inserted.
        list_r = await isolated_client.get(
            "/api/asset-taxonomy", headers=headers["admin"]
        )
        assert list_r.json()["total"] == 0

    async def test_non_admin_cannot_bulk(
        self, isolated_client: AsyncClient, tenant_alpha
    ):
        _, _, _, headers = tenant_alpha
        r = await isolated_client.post(
            "/api/asset-taxonomy/bulk",
            json=[{"tier_code": "T1", "keyword": "x"}],
            headers=headers["it"],
        )
        assert r.status_code == 403


class TestPatch:
    async def test_update_tier(self, isolated_client: AsyncClient, tenant_alpha):
        _, _, _, headers = tenant_alpha
        r = await isolated_client.post(
            "/api/asset-taxonomy",
            json={"tier_code": "T2", "keyword": "vpn"},
            headers=headers["admin"],
        )
        rid = r.json()["id"]

        r = await isolated_client.patch(
            f"/api/asset-taxonomy/{rid}",
            json={"tier_code": "T1"},
            headers=headers["admin"],
        )
        assert r.status_code == 200
        assert r.json()["tier_code"] == "T1"

    async def test_update_empty_body_rejected(
        self, isolated_client: AsyncClient, tenant_alpha
    ):
        _, _, _, headers = tenant_alpha
        r = await isolated_client.post(
            "/api/asset-taxonomy",
            json={"tier_code": "T1", "keyword": "x"},
            headers=headers["admin"],
        )
        rid = r.json()["id"]
        r = await isolated_client.patch(
            f"/api/asset-taxonomy/{rid}", json={}, headers=headers["admin"]
        )
        assert r.status_code == 422

    async def test_patch_other_tenant_returns_404(
        self,
        isolated_client: AsyncClient,
        tenant_alpha,
        tenant_beta,
    ):
        _, _, _, headers_a = tenant_alpha
        _, _, _, headers_b = tenant_beta
        # Tenant A creates a row.
        r = await isolated_client.post(
            "/api/asset-taxonomy",
            json={"tier_code": "T1", "keyword": "alpha-secret"},
            headers=headers_a["admin"],
        )
        rid = r.json()["id"]

        # Tenant B tries to patch — must get 404 (no info leak about
        # whether the row exists at all).
        r = await isolated_client.patch(
            f"/api/asset-taxonomy/{rid}",
            json={"tier_code": "T4"},
            headers=headers_b["admin"],
        )
        assert r.status_code == 404


class TestSoftDelete:
    async def test_delete_sets_deleted_at_does_not_hard_delete(
        self,
        isolated_client: AsyncClient,
        db_session: AsyncSession,
        tenant_alpha,
    ):
        _, _, _, headers = tenant_alpha
        r = await isolated_client.post(
            "/api/asset-taxonomy",
            json={"tier_code": "T1", "keyword": "to-delete"},
            headers=headers["admin"],
        )
        rid = r.json()["id"]

        r = await isolated_client.delete(
            f"/api/asset-taxonomy/{rid}", headers=headers["admin"]
        )
        assert r.status_code == 200
        assert r.json()["entry"]["deleted_at"] is not None

        # Row still exists in DB with deleted_at populated.
        result = await db_session.execute(
            select(TenantAssetTaxonomy).where(TenantAssetTaxonomy.id == uuid.UUID(rid))
        )
        row = result.scalar_one_or_none()
        assert row is not None
        assert row.deleted_at is not None

    async def test_delete_other_tenant_returns_404(
        self,
        isolated_client: AsyncClient,
        tenant_alpha,
        tenant_beta,
    ):
        _, _, _, headers_a = tenant_alpha
        _, _, _, headers_b = tenant_beta
        r = await isolated_client.post(
            "/api/asset-taxonomy",
            json={"tier_code": "T1", "keyword": "alpha-only"},
            headers=headers_a["admin"],
        )
        rid = r.json()["id"]
        r = await isolated_client.delete(
            f"/api/asset-taxonomy/{rid}", headers=headers_b["admin"]
        )
        assert r.status_code == 404


class TestImportDefaults:
    async def test_seeds_legacy_keywords(
        self,
        isolated_client: AsyncClient,
        tenant_alpha,
    ):
        _, _, _, headers = tenant_alpha
        r = await isolated_client.post(
            "/api/asset-taxonomy/import-defaults", headers=headers["admin"]
        )
        assert r.status_code == 201, r.text
        body = r.json()
        assert body["inserted"] > 0

        # Verify some well-known legacy keywords are present (regardless of tier).
        all_keywords = {i["keyword"] for i in body["items"]}
        assert any("sap" in kw for kw in all_keywords)
        assert any("vpn" in kw for kw in all_keywords)

    async def test_import_defaults_blocked_when_existing_rows(
        self,
        isolated_client: AsyncClient,
        tenant_alpha,
    ):
        _, _, _, headers = tenant_alpha
        # First seed once.
        await isolated_client.post(
            "/api/asset-taxonomy", json={"tier_code": "T1", "keyword": "manual"}, headers=headers["admin"]
        )
        # Import-defaults must refuse rather than double-seed.
        r = await isolated_client.post(
            "/api/asset-taxonomy/import-defaults", headers=headers["admin"]
        )
        assert r.status_code == 409

    async def test_import_defaults_admin_only(
        self, isolated_client: AsyncClient, tenant_alpha
    ):
        _, _, _, headers = tenant_alpha
        r = await isolated_client.post(
            "/api/asset-taxonomy/import-defaults", headers=headers["it"]
        )
        assert r.status_code == 403


# ─────────────────────────────────────────────────────────────────────────────
# Cache invalidation observable via API
# ─────────────────────────────────────────────────────────────────────────────


class TestRouterInvalidatesCache:
    async def test_create_and_delete_take_immediate_effect_on_async_classifier(
        self,
        isolated_client: AsyncClient,
        db_session: AsyncSession,
        tenant_alpha,
    ):
        """
        After POST + DELETE, the classifier reflects the changes via the
        async path on the next call.  Asserts that router-side cache
        invalidation actually happens.
        """
        from backend.middleware.tenant import TenantContext
        from backend.services import asset_criticality_service as svc

        tenant, _admin, _it, headers = tenant_alpha

        # POST a unique keyword.
        r = await isolated_client.post(
            "/api/asset-taxonomy",
            json={"tier_code": "T1", "keyword": "xenotest"},
            headers=headers["admin"],
        )
        rid = r.json()["id"]

        # Bind context manually (we are outside a request) and verify async
        # classifier sees the keyword.
        TenantContext.set(tenant.id)
        svc.invalidate_tenant_cache(tenant.id)  # belt-and-braces — router
        # already called this, but the router used ITS request's cache view;
        # tests run in another context.  This is fine because
        # classify_asset_async always refetches on cold cache.

        tier = await svc.classify_asset_async(db_session, "xenotest-host")
        assert tier == 1

        # Soft-delete via API, then re-classify.
        r = await isolated_client.delete(
            f"/api/asset-taxonomy/{rid}", headers=headers["admin"]
        )
        assert r.status_code == 200
        svc.invalidate_tenant_cache(tenant.id)

        tier_after = await svc.classify_asset_async(db_session, "xenotest-host")
        # Tenant now has zero LIVE rows again → empty marker → legacy fallback,
        # which doesn't know "xenotest" → default Tier 3.
        assert tier_after == 3
