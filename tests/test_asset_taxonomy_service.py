"""
P1.4 — asset_criticality_service refactor tests.

Covers:
- Tenant with zero keywords → falls back to legacy JSON.
- Tenant with keywords → uses tenant keywords (legacy JSON ignored).
- Cache invalidation on update (mutation invalidates → next call refetches).
- Cross-tenant isolation: classify() under tenant A's context returns
  tenant A's classification, not tenant B's.
- preload_tenant_taxonomy() warms the sync path.
- classify_asset_async() guarantees a DB lookup on cold cache.
- TTL expiry triggers a refresh.
- No TenantContext bound → uses legacy JSON.
- Backwards compat: existing legacy classifications still pass.
"""
from __future__ import annotations

import time
import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from backend.middleware.tenant import TenantContext, _tenant_id_var
from backend.models.asset_taxonomy import TenantAssetTaxonomy
from backend.models.tenant import Tenant
from backend.services import asset_criticality_service as svc


# ─────────────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────────────


@pytest.fixture
def reset_tenant_context_and_cache():
    """Reset both TenantContext and the per-tenant cache before/after each test."""
    svc.invalidate_tenant_cache()  # wipe all
    token = _tenant_id_var.set(None)
    yield
    _tenant_id_var.reset(token)
    svc.invalidate_tenant_cache()  # wipe all again


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


async def _seed_keyword(
    db: AsyncSession, tenant_id: uuid.UUID, tier_code: str, keyword: str
) -> TenantAssetTaxonomy:
    row = TenantAssetTaxonomy(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        tier_code=tier_code,
        keyword=keyword,
    )
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return row


# ─────────────────────────────────────────────────────────────────────────────
# Backwards-compat: legacy JSON classifications still work
# ─────────────────────────────────────────────────────────────────────────────


class TestLegacyFallbackUnchanged:
    """
    The sync classify_asset() must keep returning the SAME tier numbers it
    did before P1.4 when no tenant context is bound.  This protects every
    existing caller (simulator, exploitability_service, scoring tests).
    """

    def test_tier1_keywords_still_match(self, reset_tenant_context_and_cache):
        assert svc.classify_asset("SAP ERP Production SAP-PRD-01") == 1
        assert svc.classify_asset("Chennai Plant HMI Controller") == 1
        assert svc.classify_asset("Paint Shop PLC PLC-PAINT-03") == 1

    def test_tier2_keywords_still_match(self, reset_tenant_context_and_cache):
        assert svc.classify_asset("Dealer Portal") == 2
        assert svc.classify_asset("VPN Gateway Primary") == 2

    def test_tier3_default(self, reset_tenant_context_and_cache):
        assert svc.classify_asset("Marketing MacBook") == 3
        assert svc.classify_asset("Some Random Asset") == 3
        assert svc.classify_asset("") == 3

    def test_tier4_keywords_still_match(self, reset_tenant_context_and_cache):
        assert svc.classify_asset("Test Server QA-01") == 4
        assert svc.classify_asset("Showroom Kiosk") == 4

    def test_tier1_priority_over_tier4(self, reset_tenant_context_and_cache):
        assert svc.classify_asset("SAP Test Server") == 1


# ─────────────────────────────────────────────────────────────────────────────
# Per-tenant taxonomy via async path
# ─────────────────────────────────────────────────────────────────────────────


class TestPerTenantTaxonomy:
    async def test_zero_keywords_falls_back_to_legacy(
        self, db_session: AsyncSession, reset_tenant_context_and_cache
    ):
        """A tenant with zero rows uses the legacy JSON keywords."""
        tenant = await _make_tenant(db_session, "empty-tenant")
        TenantContext.set(tenant.id)

        # SAP is in legacy Tier 1 — it should still classify as 1.
        tier = await svc.classify_asset_async(db_session, "SAP-PRD-01")
        assert tier == 1

        # And a generic name remains Tier 3.
        tier_default = await svc.classify_asset_async(db_session, "Random Workstation")
        assert tier_default == 3

    async def test_tenant_keywords_override_legacy(
        self, db_session: AsyncSession, reset_tenant_context_and_cache
    ):
        """When a tenant has its own keywords, the legacy JSON is ignored."""
        tenant = await _make_tenant(db_session, "custom-tenant")
        TenantContext.set(tenant.id)

        # Configure: only "marketing" is Tier 1 for this tenant.  SAP is NOT
        # in this tenant's taxonomy, so it must fall through to default.
        await _seed_keyword(db_session, tenant.id, "T1", "marketing")

        tier = await svc.classify_asset_async(db_session, "Marketing Asset")
        assert tier == 1

        # SAP is not in tenant's own keywords — it must NOT be Tier 1.
        # (legacy JSON is ignored once tenant has its own rows.)
        tier_sap = await svc.classify_asset_async(db_session, "SAP-PRD-01")
        assert tier_sap == 3  # default since "marketing" alone doesn't match

    async def test_tenant_with_keywords_per_multiple_tiers(
        self, db_session: AsyncSession, reset_tenant_context_and_cache
    ):
        tenant = await _make_tenant(db_session, "multi-tier")
        TenantContext.set(tenant.id)

        await _seed_keyword(db_session, tenant.id, "T1", "core-router")
        await _seed_keyword(db_session, tenant.id, "T2", "branch-fw")
        await _seed_keyword(db_session, tenant.id, "T4", "sandbox-vm")

        assert await svc.classify_asset_async(db_session, "core-router-01") == 1
        assert await svc.classify_asset_async(db_session, "branch-fw-mum") == 2
        assert await svc.classify_asset_async(db_session, "sandbox-vm-test") == 4
        assert await svc.classify_asset_async(db_session, "office-laptop") == 3


# ─────────────────────────────────────────────────────────────────────────────
# Cache behaviour
# ─────────────────────────────────────────────────────────────────────────────


class TestTaxonomyCache:
    async def test_first_call_populates_cache(
        self, db_session: AsyncSession, reset_tenant_context_and_cache
    ):
        tenant = await _make_tenant(db_session, "cache-pop")
        TenantContext.set(tenant.id)
        await _seed_keyword(db_session, tenant.id, "T1", "alpha-svc")

        assert svc._peek_cache(tenant.id) is None
        await svc.classify_asset_async(db_session, "anything")
        entry = svc._peek_cache(tenant.id)
        assert entry is not None
        compiled, _ts = entry
        assert compiled is not None
        assert 1 in compiled

    async def test_invalidation_drops_entry(
        self, db_session: AsyncSession, reset_tenant_context_and_cache
    ):
        tenant = await _make_tenant(db_session, "cache-inv")
        TenantContext.set(tenant.id)
        await _seed_keyword(db_session, tenant.id, "T1", "kw1")

        await svc.preload_tenant_taxonomy(db_session)
        assert svc._peek_cache(tenant.id) is not None

        svc.invalidate_tenant_cache(tenant.id)
        assert svc._peek_cache(tenant.id) is None

    async def test_mutation_then_invalidation_reflects_new_keywords(
        self, db_session: AsyncSession, reset_tenant_context_and_cache
    ):
        """
        Sequence: warm cache → simulate router adding a keyword + invalidating
        cache → next async call refreshes and sees the new keyword.
        """
        tenant = await _make_tenant(db_session, "mut-inv")
        TenantContext.set(tenant.id)

        # Initial: no keywords.  Cache marker = None (legacy fallback).
        await svc.preload_tenant_taxonomy(db_session)
        compiled_first, _ = svc._peek_cache(tenant.id)
        assert compiled_first is None

        # Simulate POST: add a row + invalidate (this is what the router does).
        await _seed_keyword(db_session, tenant.id, "T1", "newkw")
        svc.invalidate_tenant_cache(tenant.id)

        # Next call must refetch from DB and see the new keyword.
        tier = await svc.classify_asset_async(db_session, "newkw-server")
        assert tier == 1

    async def test_ttl_expiry_triggers_refresh(
        self, db_session: AsyncSession, reset_tenant_context_and_cache, monkeypatch
    ):
        """
        Force-age the cache entry past TTL — the next classify_asset_async()
        must refetch from DB.
        """
        tenant = await _make_tenant(db_session, "ttl-test")
        TenantContext.set(tenant.id)
        await _seed_keyword(db_session, tenant.id, "T1", "initial-kw")

        await svc.preload_tenant_taxonomy(db_session)
        compiled_old, ts_old = svc._peek_cache(tenant.id)
        assert compiled_old is not None

        # Manually rewrite the entry's timestamp to the distant past.
        svc._tenant_cache[tenant.id] = (compiled_old, ts_old - (svc._CACHE_TTL_SECONDS + 10))

        # Add a new keyword to the DB (do NOT invalidate — TTL must do it).
        await _seed_keyword(db_session, tenant.id, "T2", "after-ttl-kw")

        # async call should refetch and now see both keywords.
        tier = await svc.classify_asset_async(db_session, "after-ttl-kw-server")
        assert tier == 2

    def test_invalidate_all_with_no_arg_clears_everything(
        self, reset_tenant_context_and_cache
    ):
        a, b = uuid.uuid4(), uuid.uuid4()
        svc._tenant_cache[a] = (None, time.monotonic())
        svc._tenant_cache[b] = (None, time.monotonic())
        svc.invalidate_tenant_cache()  # all
        assert svc._peek_cache(a) is None
        assert svc._peek_cache(b) is None


# ─────────────────────────────────────────────────────────────────────────────
# Cross-tenant isolation
# ─────────────────────────────────────────────────────────────────────────────


class TestCrossTenantClassificationIsolation:
    async def test_tenant_a_keywords_do_not_leak_to_tenant_b(
        self, db_session: AsyncSession, reset_tenant_context_and_cache
    ):
        tenant_a = await _make_tenant(db_session, "iso-class-a")
        tenant_b = await _make_tenant(db_session, "iso-class-b")

        # Tenant A says "alpha-special" is Tier 1.  Tenant B has no rows.
        await _seed_keyword(db_session, tenant_a.id, "T1", "alpha-special")

        # Under tenant A's context: alpha-special is Tier 1.
        TenantContext.set(tenant_a.id)
        assert await svc.classify_asset_async(db_session, "alpha-special-host") == 1

        # Under tenant B's context: tenant B has zero rows → legacy fallback,
        # which doesn't know about "alpha-special" → default Tier 3.
        TenantContext.set(tenant_b.id)
        assert await svc.classify_asset_async(db_session, "alpha-special-host") == 3

    async def test_sync_classify_uses_currently_bound_tenant_cache(
        self, db_session: AsyncSession, reset_tenant_context_and_cache
    ):
        """
        After preloading two tenants, sync classify_asset() under each
        tenant's context returns that tenant's classification.
        """
        tenant_a = await _make_tenant(db_session, "iso-sync-a")
        tenant_b = await _make_tenant(db_session, "iso-sync-b")

        await _seed_keyword(db_session, tenant_a.id, "T1", "only-in-a")
        await _seed_keyword(db_session, tenant_b.id, "T1", "only-in-b")

        # Warm both caches.
        TenantContext.set(tenant_a.id)
        await svc.preload_tenant_taxonomy(db_session)
        TenantContext.set(tenant_b.id)
        await svc.preload_tenant_taxonomy(db_session)

        TenantContext.set(tenant_a.id)
        assert svc.classify_asset("only-in-a-server") == 1
        # "only-in-b" does not match A's keywords → A defaults to Tier 3.
        assert svc.classify_asset("only-in-b-server") == 3

        TenantContext.set(tenant_b.id)
        assert svc.classify_asset("only-in-b-server") == 1
        assert svc.classify_asset("only-in-a-server") == 3


# ─────────────────────────────────────────────────────────────────────────────
# Soft-delete semantics
# ─────────────────────────────────────────────────────────────────────────────


class TestSoftDeleteRespected:
    async def test_soft_deleted_keyword_is_ignored(
        self, db_session: AsyncSession, reset_tenant_context_and_cache
    ):
        from datetime import datetime, timezone
        tenant = await _make_tenant(db_session, "soft-del-svc")
        TenantContext.set(tenant.id)

        live = await _seed_keyword(db_session, tenant.id, "T1", "live-kw")
        dead = await _seed_keyword(db_session, tenant.id, "T1", "dead-kw")
        dead.deleted_at = datetime.now(timezone.utc)
        await db_session.commit()

        # invalidate so next async call refetches.
        svc.invalidate_tenant_cache(tenant.id)

        # Live keyword still classifies.
        assert await svc.classify_asset_async(db_session, "live-kw-host") == 1
        # Dead keyword is ignored → default Tier 3.
        assert await svc.classify_asset_async(db_session, "dead-kw-host") == 3
