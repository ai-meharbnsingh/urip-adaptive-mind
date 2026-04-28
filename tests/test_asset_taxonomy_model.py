"""
P1.4 — TenantAssetTaxonomy model tests.

Covers:
- Basic CRUD: insert, fetch, update, soft-delete.
- Tenant isolation: Tenant A's keywords are invisible to Tenant B's
  apply_tenant_filter()-scoped queries.
- Constants (TIER_CODES, TIER_CODE_TO_INT, TIER_INT_TO_CODE) are coherent.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

# Importing the model also registers its table in Base.metadata, which is
# required because conftest.py creates tables off Base.metadata.create_all.
from backend.models.asset_taxonomy import (
    TIER_CODE_TO_INT,
    TIER_CODES,
    TIER_INT_TO_CODE,
    TenantAssetTaxonomy,
)
from backend.models.tenant import Tenant
from backend.models.user import User
from backend.middleware.tenant import TenantContext, _tenant_id_var
from backend.services.tenant_query import apply_tenant_filter


# ─────────────────────────────────────────────────────────────────────────────
# Module-level constants
# ─────────────────────────────────────────────────────────────────────────────


class TestTaxonomyConstants:
    def test_tier_codes_are_t1_to_t4(self):
        assert TIER_CODES == ("T1", "T2", "T3", "T4")

    def test_tier_code_to_int_mapping(self):
        assert TIER_CODE_TO_INT == {"T1": 1, "T2": 2, "T3": 3, "T4": 4}

    def test_tier_int_to_code_is_inverse(self):
        for code, num in TIER_CODE_TO_INT.items():
            assert TIER_INT_TO_CODE[num] == code


# ─────────────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────────────


@pytest.fixture
def reset_tenant_context():
    """Reset TenantContext before/after each test that uses it."""
    token = _tenant_id_var.set(None)
    yield
    _tenant_id_var.reset(token)


async def _make_tenant(db: AsyncSession, slug: str) -> Tenant:
    t = Tenant(
        id=uuid.uuid4(),
        name=f"Tenant {slug}",
        slug=slug,
        domain=f"{slug}.test",
        is_active=True,
        settings={},
    )
    db.add(t)
    await db.commit()
    await db.refresh(t)
    return t


async def _make_user(db: AsyncSession, tenant_id: uuid.UUID, email: str) -> User:
    u = User(
        id=uuid.uuid4(),
        email=email,
        hashed_password="x" * 60,
        full_name=email,
        role="ciso",
        team="Security",
        is_active=True,
        tenant_id=tenant_id,
    )
    db.add(u)
    await db.commit()
    await db.refresh(u)
    return u


# ─────────────────────────────────────────────────────────────────────────────
# CRUD
# ─────────────────────────────────────────────────────────────────────────────


class TestTaxonomyCRUD:
    async def test_insert_and_fetch(self, db_session: AsyncSession):
        tenant = await _make_tenant(db_session, "alpha-crud")
        user = await _make_user(db_session, tenant.id, "alpha-ciso@x.test")

        row = TenantAssetTaxonomy(
            id=uuid.uuid4(),
            tenant_id=tenant.id,
            tier_code="T1",
            keyword=r"\bsap\b",
            asset_type=None,
            created_by_user_id=user.id,
        )
        db_session.add(row)
        await db_session.commit()
        await db_session.refresh(row)

        assert row.id is not None
        assert row.tier_code == "T1"
        assert row.keyword == r"\bsap\b"
        assert row.deleted_at is None
        assert row.created_at is not None

        fetched = (
            await db_session.execute(
                select(TenantAssetTaxonomy).where(TenantAssetTaxonomy.id == row.id)
            )
        ).scalar_one()
        assert fetched.id == row.id
        assert fetched.created_by_user_id == user.id

    async def test_soft_delete_marker(self, db_session: AsyncSession):
        tenant = await _make_tenant(db_session, "beta-soft")
        row = TenantAssetTaxonomy(
            id=uuid.uuid4(),
            tenant_id=tenant.id,
            tier_code="T2",
            keyword="firewall",
        )
        db_session.add(row)
        await db_session.commit()

        # Soft-delete
        row.deleted_at = datetime.now(timezone.utc)
        await db_session.commit()
        await db_session.refresh(row)

        assert row.deleted_at is not None

    async def test_asset_type_optional(self, db_session: AsyncSession):
        tenant = await _make_tenant(db_session, "asset-type-opt")
        row = TenantAssetTaxonomy(
            id=uuid.uuid4(),
            tenant_id=tenant.id,
            tier_code="T1",
            keyword="scada",
            asset_type=None,
        )
        db_session.add(row)
        await db_session.commit()
        await db_session.refresh(row)
        assert row.asset_type is None

    async def test_one_tenant_many_keywords_per_tier(self, db_session: AsyncSession):
        tenant = await _make_tenant(db_session, "many-keys")
        keywords = ["sap", "erp", "prd", "domain.?admin"]
        for kw in keywords:
            db_session.add(
                TenantAssetTaxonomy(
                    id=uuid.uuid4(),
                    tenant_id=tenant.id,
                    tier_code="T1",
                    keyword=kw,
                )
            )
        await db_session.commit()

        result = await db_session.execute(
            select(TenantAssetTaxonomy).where(
                TenantAssetTaxonomy.tenant_id == tenant.id,
                TenantAssetTaxonomy.tier_code == "T1",
            )
        )
        rows = result.scalars().all()
        assert {r.keyword for r in rows} == set(keywords)


# ─────────────────────────────────────────────────────────────────────────────
# Tenant isolation
# ─────────────────────────────────────────────────────────────────────────────


class TestTaxonomyTenantIsolation:
    async def test_apply_tenant_filter_excludes_other_tenant(
        self, db_session: AsyncSession, reset_tenant_context
    ):
        tenant_a = await _make_tenant(db_session, "iso-a")
        tenant_b = await _make_tenant(db_session, "iso-b")

        db_session.add(
            TenantAssetTaxonomy(
                id=uuid.uuid4(),
                tenant_id=tenant_a.id,
                tier_code="T1",
                keyword="sap-a",
            )
        )
        db_session.add(
            TenantAssetTaxonomy(
                id=uuid.uuid4(),
                tenant_id=tenant_b.id,
                tier_code="T1",
                keyword="sap-b",
            )
        )
        await db_session.commit()

        # Bind context to tenant A and run a tenant-filtered query.
        TenantContext.set(tenant_a.id)
        query = apply_tenant_filter(select(TenantAssetTaxonomy), TenantAssetTaxonomy)
        rows_a = (await db_session.execute(query)).scalars().all()
        assert {r.keyword for r in rows_a} == {"sap-a"}

        # Bind context to tenant B and re-query.
        TenantContext.set(tenant_b.id)
        query = apply_tenant_filter(select(TenantAssetTaxonomy), TenantAssetTaxonomy)
        rows_b = (await db_session.execute(query)).scalars().all()
        assert {r.keyword for r in rows_b} == {"sap-b"}

    async def test_apply_tenant_filter_raises_when_no_context(
        self, db_session: AsyncSession, reset_tenant_context
    ):
        # No TenantContext bound — apply_tenant_filter must refuse to leak.
        with pytest.raises(RuntimeError):
            apply_tenant_filter(select(TenantAssetTaxonomy), TenantAssetTaxonomy)
