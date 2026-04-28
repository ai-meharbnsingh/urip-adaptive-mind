"""
Asset Criticality Service
Auto-assigns tier from asset name keywords + manual override support.

Tier 1 (Critical):  +1.0 bonus — business-critical, revenue/safety impact
Tier 2 (High):      +0.5 bonus — customer-facing, perimeter, OT
Tier 3 (Medium):    +0.0 bonus — internal tools, workstations
Tier 4 (Low):       -0.5 bonus — test/dev, isolated, replaceable

P1.4 — Tenant-configurable asset taxonomy
-----------------------------------------
This service now reads keyword patterns from the per-tenant
`tenant_asset_taxonomy` table.  When the current request has a bound
TenantContext AND that tenant has at least one taxonomy row, those
keywords are used.  When the tenant has zero rows OR no TenantContext
is bound (e.g. simulator, scoring unit tests), the legacy
`tier_keywords.json` is used as the transition default.

Two entry points
----------------
- `classify_asset(asset_name) -> int`        — sync, signature unchanged.
  Reads from the in-process per-tenant cache.  Cold cache → legacy fallback.
  This preserves backwards compatibility for every existing caller
  (simulator, exploitability_service, scoring tests).

- `await classify_asset_async(db, asset_name) -> int` — async.  Loads the
  tenant's taxonomy from the DB (warming the cache as a side effect),
  then classifies.  New code paths that want guaranteed per-tenant
  behaviour should use this.

- `await preload_tenant_taxonomy(db) -> None` — explicit cache-warm.
  Routers / dependencies can call this immediately after auth so any
  subsequent sync `classify_asset` call sees per-tenant keywords.

Cache
-----
In-process LRU-by-TTL.  Keyed by tenant_id (UUID).  Each entry stores the
list of compiled regex patterns per tier and a timestamp.  Default TTL
is 5 minutes (configurable via _CACHE_TTL_SECONDS).  Cache is invalidated
explicitly by the admin router on every mutation
(`invalidate_tenant_cache(tenant_id)`).
"""
from __future__ import annotations

import json
import logging
import re
import time
import uuid
from pathlib import Path
from typing import Iterable

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.middleware.tenant import TenantContext
from backend.services.scoring_config import TIER_BONUS

logger = logging.getLogger(__name__)

# ─── Hardcoded fallback keywords (transition default) ─────────
# Kept identical to the previous shipping behaviour so existing tests
# and tenants without a customised taxonomy keep getting the same tiers.
_FALLBACK_KEYWORDS: dict[int, list[str]] = {
    1: [
        r"\bsap\b", r"\berp\b", r"\bprd\b", r"\bprod\b",
        r"payment", r"domain.?admin", r"root.?aws", r"\bpam\b", r"\bvault\b",
        r"\bsso\b", r"\bokta\b", r"\bldap\b",
        r"\bhmi\b", r"\bscada\b", r"\bplc\b", r"\bics\b",  # OT/ICS = Tier 1 for manufacturing
        r"\bot\b", r"armis",                                 # RE-specific: OT is safety-critical
        r"finance", r"core.?switch", r"domain.?controller",
    ],
    2: [
        r"dealer", r"\bvpn\b", r"firewall", r"\bwaf\b",
        r"load.?balancer", r"e-?commerce", r"mobile.?app",
        r"\bcrm\b", r"salesforce", r"\bapi\b", r"portal",
        r"\brtu\b", r"conveyor", r"compressor", r"welding",  # OT secondary devices
        r"assembly", r"paint.?shop", r"engine.?test",
        r"\bcdn\b", r"\bids\b", r"\bips\b", r"proxy",
        r"email", r"\bsmtp\b", r"\bdns\b",
    ],
    4: [
        r"\btest\b", r"\bdev\b", r"\blab\b", r"\bstaging\b",
        r"sandbox", r"\bkiosk\b", r"showroom", r"\bpoc\b",
        r"demo", r"temp", r"backup",
    ],
    # Tier 3 is the default — no keywords needed
}

# ─── Load keywords from JSON config (fallback to hardcoded) ───
_TIER_KEYWORDS_JSON = Path(__file__).resolve().parent.parent / "config" / "tier_keywords.json"


def _load_legacy_tier_keywords() -> dict[int, list[str]]:
    """Load tier keywords from JSON config file, falling back to hardcoded defaults."""
    try:
        with open(_TIER_KEYWORDS_JSON) as f:
            raw = json.load(f)
        # JSON keys are strings — convert to int
        loaded = {int(k): v for k, v in raw.items()}
        logger.info("Loaded tier keywords from %s", _TIER_KEYWORDS_JSON)
        return loaded
    except (FileNotFoundError, json.JSONDecodeError, ValueError) as exc:
        logger.warning(
            "Could not load tier keywords from %s (%s), using hardcoded fallback",
            _TIER_KEYWORDS_JSON,
            exc,
        )
        return _FALLBACK_KEYWORDS


# Legacy keywords (used as transition default) — loaded once at module import
LEGACY_TIER_KEYWORDS: dict[int, list[str]] = _load_legacy_tier_keywords()

# Backwards-compat alias — older code referenced TIER_KEYWORDS at module level.
TIER_KEYWORDS: dict[int, list[str]] = LEGACY_TIER_KEYWORDS

# Pre-compiled legacy patterns for performance
_LEGACY_COMPILED: dict[int, list[re.Pattern]] = {
    tier: [re.compile(p, re.IGNORECASE) for p in patterns]
    for tier, patterns in LEGACY_TIER_KEYWORDS.items()
}


# ─── Per-tenant cache ─────────────────────────────────────────
# Each cache entry is (compiled_keywords_dict_or_None, timestamp_seconds).
# A value of None means "tenant has zero rows — use legacy fallback".
_CACHE_TTL_SECONDS = 300  # 5 minutes
_tenant_cache: dict[uuid.UUID, tuple[dict[int, list[re.Pattern]] | None, float]] = {}


def _is_cache_fresh(ts: float) -> bool:
    return (time.monotonic() - ts) < _CACHE_TTL_SECONDS


def _compile_patterns(patterns_per_tier: dict[int, list[str]]) -> dict[int, list[re.Pattern]]:
    """Compile a mapping of {tier_int: [regex_str, ...]} into compiled patterns."""
    return {
        tier: [re.compile(p, re.IGNORECASE) for p in patterns]
        for tier, patterns in patterns_per_tier.items()
    }


def _classify_with(asset_name: str, compiled: dict[int, list[re.Pattern]]) -> int:
    """Run priority-ordered classification against a compiled pattern map."""
    if not asset_name:
        return 3
    # Priority order: Tier 1 → Tier 4 → Tier 2 → default 3.
    # (Tier 1 wins over Tier 4 even when the name contains both, e.g. "SAP Test Server".)
    for tier in (1, 4, 2):
        for pattern in compiled.get(tier, ()):
            if pattern.search(asset_name):
                return tier
    return 3


def invalidate_tenant_cache(tenant_id: uuid.UUID | None = None) -> None:
    """
    Drop the cached taxonomy entry for one tenant (or all tenants if None).

    Routers MUST call this on every mutation (POST / PATCH / DELETE / bulk
    import / import-defaults) so the next classify_asset call for that
    tenant reflects the change immediately.
    """
    global _tenant_cache
    if tenant_id is None:
        _tenant_cache = {}
    else:
        _tenant_cache.pop(tenant_id, None)


def _tier_code_to_int(code: str) -> int:
    # Local import to avoid hard cross-module coupling at module load time.
    from backend.models.asset_taxonomy import TIER_CODE_TO_INT
    return TIER_CODE_TO_INT[code]


async def _fetch_tenant_keywords_from_db(
    db: AsyncSession, tenant_id: uuid.UUID
) -> dict[int, list[str]]:
    """
    Fetch all live (non-soft-deleted) taxonomy rows for a tenant and group
    them by integer tier.  Returns an empty dict if the tenant has no rows.
    """
    # Local import — keeps import graph clean and lets test setup register
    # the model on demand.
    from backend.models.asset_taxonomy import TenantAssetTaxonomy

    result = await db.execute(
        select(TenantAssetTaxonomy.tier_code, TenantAssetTaxonomy.keyword).where(
            TenantAssetTaxonomy.tenant_id == tenant_id,
            TenantAssetTaxonomy.deleted_at.is_(None),
        )
    )
    grouped: dict[int, list[str]] = {}
    for tier_code, keyword in result.all():
        try:
            tier_int = _tier_code_to_int(tier_code)
        except KeyError:
            logger.warning(
                "Unknown tier_code %r in tenant_asset_taxonomy (tenant=%s) — skipping",
                tier_code,
                tenant_id,
            )
            continue
        grouped.setdefault(tier_int, []).append(keyword)
    return grouped


async def preload_tenant_taxonomy(db: AsyncSession, tenant_id: uuid.UUID | None = None) -> None:
    """
    Warm the per-tenant cache.  Pass an explicit tenant_id, or omit to use
    the current TenantContext.  Safe to call repeatedly.
    """
    if tenant_id is None:
        tenant_id = TenantContext.get_or_none()
    if tenant_id is None:
        return  # nothing to warm — sync path will use legacy fallback

    grouped = await _fetch_tenant_keywords_from_db(db, tenant_id)
    if grouped:
        _tenant_cache[tenant_id] = (_compile_patterns(grouped), time.monotonic())
    else:
        # Empty marker — tells the sync path: use legacy fallback for this tenant.
        _tenant_cache[tenant_id] = (None, time.monotonic())


def classify_asset(asset_name: str) -> int:
    """
    Auto-classify asset into tier 1-4 based on name keywords.

    Lookup order
    ------------
    1. If a TenantContext is bound AND there is a fresh cache entry with
       per-tenant keywords → use those.
    2. Otherwise (no context, no cache, or empty-marker entry) → use the
       legacy `tier_keywords.json` fallback.

    Returns tier number (1-4), default 3.
    """
    tenant_id = TenantContext.get_or_none()
    if tenant_id is not None:
        entry = _tenant_cache.get(tenant_id)
        if entry is not None:
            compiled, ts = entry
            if _is_cache_fresh(ts) and compiled is not None:
                return _classify_with(asset_name, compiled)
    return _classify_with(asset_name, _LEGACY_COMPILED)


async def classify_asset_async(db: AsyncSession, asset_name: str) -> int:
    """
    Async classifier that guarantees per-tenant taxonomy is consulted.

    Loads (and caches) the tenant's taxonomy on first call.  If the tenant
    has zero rows, falls back to the legacy keyword set.
    """
    tenant_id = TenantContext.get_or_none()
    if tenant_id is None:
        # No tenant bound — pure fallback path (e.g., scheduled jobs).
        return _classify_with(asset_name, _LEGACY_COMPILED)

    entry = _tenant_cache.get(tenant_id)
    if entry is None or not _is_cache_fresh(entry[1]):
        await preload_tenant_taxonomy(db, tenant_id=tenant_id)
        entry = _tenant_cache.get(tenant_id)

    if entry is not None:
        compiled, _ts = entry
        if compiled is not None:
            return _classify_with(asset_name, compiled)

    return _classify_with(asset_name, _LEGACY_COMPILED)


def get_asset_bonus(tier: int) -> float:
    """Get the additive bonus for a given tier."""
    return TIER_BONUS.get(tier, 0.0)


def classify_and_get_bonus(asset_name: str) -> tuple[int, float]:
    """Convenience: returns (tier, bonus) for an asset name (sync path)."""
    tier = classify_asset(asset_name)
    return tier, get_asset_bonus(tier)


# ─── Test/diagnostic helpers ──────────────────────────────────


def _peek_cache(tenant_id: uuid.UUID) -> tuple[dict[int, list[re.Pattern]] | None, float] | None:
    """Return the raw cache entry for a tenant (test introspection only)."""
    return _tenant_cache.get(tenant_id)


def _legacy_keyword_strings() -> dict[int, list[str]]:
    """Return the legacy tier→keywords map (used by import-defaults endpoint)."""
    # Return a deep copy so callers cannot mutate the module-level dict.
    return {tier: list(patterns) for tier, patterns in LEGACY_TIER_KEYWORDS.items()}


def _all_tier_codes_from_legacy() -> Iterable[tuple[str, str]]:
    """Yield (tier_code, keyword) pairs from the legacy JSON for seeding."""
    from backend.models.asset_taxonomy import TIER_INT_TO_CODE
    for tier_int, patterns in LEGACY_TIER_KEYWORDS.items():
        code = TIER_INT_TO_CODE.get(tier_int)
        if code is None:
            continue
        for kw in patterns:
            yield code, kw
