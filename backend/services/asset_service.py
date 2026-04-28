"""
backend/services/asset_service.py

First-class Asset service — connector ingest path, REST API support,
dashboard widgets.

All functions are tenant-scoped via the explicit `tenant_id` parameter.
Routers must pass TenantContext.get(); service functions never call
TenantContext directly so they can be reused from background jobs / tests
without binding a fake context.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.asset import (
    ASSET_CATEGORIES,
    ASSET_TIERS,
    BUSINESS_CRITICALITY_VALUES,
    DEVICE_CATEGORIES,
    LIFECYCLE_STATES,
    Asset,
)
from backend.models.risk import Risk
from backend.services.asset_fingerprint_service import compute_asset_fingerprint


# ─────────────────────────────────────────────────────────────────────────────
# Category derivation
# ─────────────────────────────────────────────────────────────────────────────

# Map device_type → high-level UI category.  This is the primary signal —
# source_connectors only kicks in when device_type is unknown.
_DEVICE_TYPE_TO_CATEGORY: dict[str, str] = {
    "laptop": "Devices",
    "desktop": "Devices",
    "server": "Devices",
    "mobile": "Devices",
    "iot": "Devices",
    "cloud_workload": "Cloud Assets",
    "saas_account": "Accounts",
    "api": "API Collections",
}

# Connector-slug fallback used when device_type is missing.  Match against
# any connector in source_connectors (lowercased).
_CONNECTOR_SLUG_TO_CATEGORY: list[tuple[tuple[str, ...], str]] = [
    # Cloud workload connectors
    (("aws_cspm", "azure_cspm", "gcp_cspm", "cnapp", "wiz", "prismacloud"),
     "Cloud Assets"),
    # External-facing / EASM
    (("easm", "cert_in", "certin", "cloudsek"), "Internet-Facing Assets"),
    # Identity / accounts
    (("ms_entra", "okta", "cyberark_pam", "ldap"), "Accounts"),
    # Apps
    (("m365_collab", "burp_enterprise", "veracode", "checkmarx"),
     "Applications"),
    # APIs
    (("postman", "salt", "noname"), "API Collections"),
]


def categorize_asset(asset: Asset) -> str:
    """
    Return the high-level UI category for an Asset.

    Priority:
    1. device_type lookup
    2. source_connectors heuristic
    3. fallback "Devices"
    """
    if asset.device_type:
        cat = _DEVICE_TYPE_TO_CATEGORY.get(asset.device_type.lower())
        if cat:
            return cat

    sources = {(s or "").lower() for s in (asset.source_connectors or [])}
    if sources:
        for slugs, category in _CONNECTOR_SLUG_TO_CATEGORY:
            if sources.intersection(slugs):
                return category

    return "Devices"


# ─────────────────────────────────────────────────────────────────────────────
# Upsert
# ─────────────────────────────────────────────────────────────────────────────


@dataclass
class _AssetIdentity:
    mac: str | None
    hostname: str | None
    internal_ip: str | None
    external_ip: str | None


def _extract_identity(raw_data: dict[str, Any]) -> _AssetIdentity:
    """Pull MAC / hostname / IPs from a connector's raw_data dict."""
    return _AssetIdentity(
        mac=raw_data.get("mac")
        or raw_data.get("mac_address")
        or raw_data.get("macAddress"),
        hostname=raw_data.get("hostname")
        or raw_data.get("host")
        or raw_data.get("device_name")
        or raw_data.get("asset_name")
        or raw_data.get("asset"),
        internal_ip=raw_data.get("internal_ip")
        or raw_data.get("ip")
        or raw_data.get("ip_address")
        or raw_data.get("ipAddress"),
        external_ip=raw_data.get("external_ip") or raw_data.get("public_ip"),
    )


def _normalise_device_category(raw: Any) -> str | None:
    if raw is None:
        return None
    s = str(raw).strip()
    if not s:
        return None
    # Accept exact matches, or common-case variations.
    upper = s.upper()
    if upper == "IT":
        return "IT"
    if upper == "OT":
        return "OT"
    if upper == "IOT":
        return "IoT"
    if upper == "SAAS":
        return "SaaS"
    if s in DEVICE_CATEGORIES:
        return s
    return None


def _normalise_tier(raw: Any) -> str | None:
    if raw is None:
        return None
    if isinstance(raw, int):
        return f"T{raw}" if 1 <= raw <= 4 else None
    s = str(raw).strip().upper()
    if s in ASSET_TIERS:
        return s
    if s in ("1", "2", "3", "4"):
        return f"T{s}"
    return None


def _normalise_criticality(raw: Any) -> str | None:
    if raw is None:
        return None
    s = str(raw).strip().lower()
    return s if s in BUSINESS_CRITICALITY_VALUES else None


def _normalise_lifecycle(raw: Any) -> str:
    if raw is None:
        return "in_use"
    s = str(raw).strip().lower()
    return s if s in LIFECYCLE_STATES else "in_use"


async def upsert_asset(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    raw_data: dict[str, Any],
    *,
    source_connector: str | None = None,
) -> Asset:
    """
    Upsert an Asset row.  Connectors call this after normalize() and before
    Risk persistence.

    De-dup key: (tenant_id, fingerprint_key) where fingerprint_key is the
    SHA-256 of MAC+hostname+canonical_IP (see asset_fingerprint_service).

    Side effects when an existing asset is found:
    - last_seen is bumped to now()
    - source_connector (if not already in the JSON list) is appended
    - lifecycle_state is reset to "in_use" (a re-discovered decommissioned
      asset is no longer decommissioned — log via custom_tags if needed)
    - empty fields on the existing row are filled in from raw_data; non-empty
      fields are NOT overwritten (last-write-wins is too noisy when several
      connectors disagree).

    Returns the Asset (already added to db, but NOT committed — caller owns
    transaction boundaries so the upsert + risk insert happen atomically).
    """
    identity = _extract_identity(raw_data)
    fp = compute_asset_fingerprint(
        mac=identity.mac,
        hostname=identity.hostname,
        ip=identity.internal_ip or identity.external_ip,
    )

    existing = await db.execute(
        select(Asset).where(
            Asset.tenant_id == tenant_id, Asset.fingerprint_key == fp
        )
    )
    asset = existing.scalar_one_or_none()

    now = datetime.now(timezone.utc)
    incoming_source = (source_connector or raw_data.get("source") or "").strip().lower()

    if asset is not None:
        # Update last_seen + source_connectors + fill empty fields.
        asset.last_seen = now
        if incoming_source:
            sources = list(asset.source_connectors or [])
            if incoming_source not in sources:
                sources.append(incoming_source)
                asset.source_connectors = sources
        # Fill empty (None) fields from raw_data — never overwrite non-empty.
        for col, val in (
            ("hostname", identity.hostname),
            ("internal_ip", identity.internal_ip),
            ("external_ip", identity.external_ip),
            ("mac_address", identity.mac),
            ("device_type", raw_data.get("device_type")),
            (
                "device_category",
                _normalise_device_category(raw_data.get("device_category")),
            ),
            ("os_name", raw_data.get("os_name") or raw_data.get("os")),
            ("os_version", raw_data.get("os_version")),
            ("endpoint_group", raw_data.get("endpoint_group")),
            ("asset_group", raw_data.get("asset_group")),
            ("last_user", raw_data.get("last_user")),
            ("owner_team", raw_data.get("owner_team")),
            ("asset_tier", _normalise_tier(raw_data.get("asset_tier"))),
            (
                "business_criticality",
                _normalise_criticality(raw_data.get("business_criticality")),
            ),
        ):
            if val and not getattr(asset, col):
                setattr(asset, col, val)

        # If a previously decommissioned asset is rediscovered, flip back to in_use.
        if asset.lifecycle_state in ("decommissioned", "lost"):
            asset.lifecycle_state = "in_use"

        return asset

    # Brand-new asset
    asset = Asset(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        fingerprint_key=fp,
        hostname=identity.hostname,
        internal_ip=identity.internal_ip,
        external_ip=identity.external_ip,
        mac_address=identity.mac,
        device_type=raw_data.get("device_type"),
        device_category=_normalise_device_category(raw_data.get("device_category")),
        os_name=raw_data.get("os_name") or raw_data.get("os"),
        os_version=raw_data.get("os_version"),
        endpoint_group=raw_data.get("endpoint_group"),
        asset_group=raw_data.get("asset_group"),
        last_user=raw_data.get("last_user"),
        owner_team=raw_data.get("owner_team"),
        asset_tier=_normalise_tier(raw_data.get("asset_tier")),
        business_criticality=_normalise_criticality(
            raw_data.get("business_criticality")
        ),
        lifecycle_state=_normalise_lifecycle(raw_data.get("lifecycle_state")),
        discovered_at=now,
        last_seen=now,
        source_connectors=[incoming_source] if incoming_source else [],
        custom_tags=raw_data.get("custom_tags") or {},
        notes=raw_data.get("notes"),
    )
    db.add(asset)
    return asset


# ─────────────────────────────────────────────────────────────────────────────
# Risk score computation
# ─────────────────────────────────────────────────────────────────────────────


async def compute_asset_risk_score(
    db: AsyncSession, asset: Asset
) -> float:
    """
    Return the asset's current risk score = max(composite_score) over all
    OPEN risks linked to this asset (via Risk.asset_id).

    Falls back to max(cvss_score) when composite_score is NULL on every
    open risk.  Returns 0.0 when no open risks exist.
    """
    # Prefer composite_score; fall back to cvss_score where composite is NULL.
    score_expr = func.coalesce(Risk.composite_score, Risk.cvss_score)
    result = await db.execute(
        select(func.max(score_expr)).where(
            Risk.asset_id == asset.id,
            Risk.tenant_id == asset.tenant_id,  # belt-and-braces tenant scope
            Risk.status == "open",
        )
    )
    val = result.scalar()
    return float(val) if val is not None else 0.0


async def refresh_asset_risk_score(
    db: AsyncSession, asset: Asset
) -> Asset:
    """Recompute and persist asset_risk_score on the asset row."""
    asset.asset_risk_score = await compute_asset_risk_score(db, asset)
    db.add(asset)
    return asset


# ─────────────────────────────────────────────────────────────────────────────
# Pagination + listing
# ─────────────────────────────────────────────────────────────────────────────


@dataclass
class AssetFilters:
    device_category: str | None = None
    asset_tier: str | None = None
    owner_team: str | None = None
    has_critical_risks: bool | None = None
    custom_tag: str | None = None  # "key=value" or just "key"
    search: str | None = None
    lifecycle_state: str | None = None
    category: str | None = None  # high-level UI category


async def list_assets_paginated(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    filters: AssetFilters,
    page: int = 1,
    limit: int = 20,
) -> tuple[list[Asset], int]:
    """
    Paginated tenant-scoped asset list.

    Filters supported:
      - device_category (exact match, e.g. "IT")
      - asset_tier (exact match, e.g. "T1")
      - owner_team (ILIKE substring)
      - has_critical_risks=True → asset_risk_score >= 9.0
      - custom_tag="key" or "key=value" (JSON containment best effort)
      - search → ILIKE on hostname / internal_ip / external_ip / last_user
      - lifecycle_state (exact match)
      - category (high-level UI category — derived, post-filter)

    Returns (rows, total).
    """
    page = max(page, 1)
    limit = max(min(limit, 200), 1)

    base = select(Asset).where(Asset.tenant_id == tenant_id)
    count_q = select(func.count()).select_from(Asset).where(
        Asset.tenant_id == tenant_id
    )

    if filters.device_category:
        norm = _normalise_device_category(filters.device_category)
        if norm:
            base = base.where(Asset.device_category == norm)
            count_q = count_q.where(Asset.device_category == norm)

    if filters.asset_tier:
        norm_t = _normalise_tier(filters.asset_tier)
        if norm_t:
            base = base.where(Asset.asset_tier == norm_t)
            count_q = count_q.where(Asset.asset_tier == norm_t)

    if filters.owner_team:
        like = f"%{filters.owner_team}%"
        base = base.where(Asset.owner_team.ilike(like))
        count_q = count_q.where(Asset.owner_team.ilike(like))

    if filters.has_critical_risks is True:
        base = base.where(Asset.asset_risk_score >= 9.0)
        count_q = count_q.where(Asset.asset_risk_score >= 9.0)
    elif filters.has_critical_risks is False:
        base = base.where(
            or_(Asset.asset_risk_score.is_(None), Asset.asset_risk_score < 9.0)
        )
        count_q = count_q.where(
            or_(Asset.asset_risk_score.is_(None), Asset.asset_risk_score < 9.0)
        )

    if filters.search:
        like = f"%{filters.search}%"
        search_pred = or_(
            Asset.hostname.ilike(like),
            Asset.internal_ip.ilike(like),
            Asset.external_ip.ilike(like),
            Asset.last_user.ilike(like),
            Asset.owner_team.ilike(like),
        )
        base = base.where(search_pred)
        count_q = count_q.where(search_pred)

    if filters.lifecycle_state:
        norm_l = _normalise_lifecycle(filters.lifecycle_state)
        base = base.where(Asset.lifecycle_state == norm_l)
        count_q = count_q.where(Asset.lifecycle_state == norm_l)

    # custom_tag filter — best-effort substring match in the serialised JSON.
    # Postgres jsonb has proper containment operators; SQLite (used in tests)
    # stores JSON as TEXT, so we do a LIKE.  This is a UX filter, not a
    # security boundary, so the looser match is acceptable.
    if filters.custom_tag:
        cast = func.cast(Asset.custom_tags, sa_text_type())
        like = f"%{filters.custom_tag}%"
        base = base.where(cast.ilike(like))
        count_q = count_q.where(cast.ilike(like))

    total = (await db.execute(count_q)).scalar() or 0

    base = base.order_by(Asset.last_seen.desc().nulls_last(), Asset.hostname.asc())
    base = base.offset((page - 1) * limit).limit(limit)
    rows = (await db.execute(base)).scalars().all()

    # category filter is derived post-query (cheap; rows are already paged).
    if filters.category:
        rows = [r for r in rows if categorize_asset(r) == filters.category]

    return list(rows), int(total)


def sa_text_type():
    """Return a SQL TEXT type usable with func.cast across dialects."""
    from sqlalchemy import Text
    return Text()


# ─────────────────────────────────────────────────────────────────────────────
# Single-asset bundles
# ─────────────────────────────────────────────────────────────────────────────


@dataclass
class AssetWithRisks:
    asset: Asset
    open_risks: list[Risk]
    risk_count: int
    max_score: float
    sources: list[str]


async def get_asset_with_risks(
    db: AsyncSession, tenant_id: uuid.UUID, asset_id: uuid.UUID
) -> AssetWithRisks | None:
    """Fetch a tenant-scoped asset with its open risks bundled."""
    asset_row = await db.execute(
        select(Asset).where(Asset.id == asset_id, Asset.tenant_id == tenant_id)
    )
    asset = asset_row.scalar_one_or_none()
    if asset is None:
        return None

    risks_row = await db.execute(
        select(Risk)
        .where(
            Risk.asset_id == asset.id,
            Risk.tenant_id == tenant_id,
            Risk.status == "open",
        )
        .order_by(
            func.coalesce(Risk.composite_score, Risk.cvss_score).desc(),
            Risk.created_at.desc(),
        )
    )
    open_risks = list(risks_row.scalars().all())

    max_score = 0.0
    sources_set: set[str] = set()
    for r in open_risks:
        score_val = (
            float(r.composite_score)
            if r.composite_score is not None
            else float(r.cvss_score) if r.cvss_score is not None else 0.0
        )
        if score_val > max_score:
            max_score = score_val
        if r.source:
            sources_set.add(r.source)
    return AssetWithRisks(
        asset=asset,
        open_risks=open_risks,
        risk_count=len(open_risks),
        max_score=max_score,
        sources=sorted(sources_set),
    )


# ─────────────────────────────────────────────────────────────────────────────
# Dashboard widgets
# ─────────────────────────────────────────────────────────────────────────────


async def count_by_category(
    db: AsyncSession, tenant_id: uuid.UUID
) -> dict[str, int]:
    """
    Return a dict mapping each high-level category → asset count.

    Categories not present in the data are returned with count 0 so the UI
    can render every widget bucket consistently.
    """
    result = await db.execute(
        select(Asset).where(Asset.tenant_id == tenant_id)
    )
    counts: dict[str, int] = {c: 0 for c in ASSET_CATEGORIES}
    for asset in result.scalars().all():
        cat = categorize_asset(asset)
        counts[cat] = counts.get(cat, 0) + 1
    return counts


# ─────────────────────────────────────────────────────────────────────────────
# Risk timeline events (audit trail surfacing)
# ─────────────────────────────────────────────────────────────────────────────


@dataclass
class TimelineEvent:
    event_type: str  # "discovered" | "risk_added" | "risk_resolved" | "ownership_changed"
    timestamp: datetime
    summary: str
    risk_id: str | None = None


async def get_asset_timeline(
    db: AsyncSession, tenant_id: uuid.UUID, asset_id: uuid.UUID
) -> list[TimelineEvent]:
    """
    Build a chronological event list for the asset:
    - 1 "discovered" event at asset.discovered_at
    - 1 "risk_added" per risk linked to the asset (Risk.created_at)
    - 1 "risk_resolved" per risk where status != 'open' (Risk.updated_at)
    """
    asset_row = await db.execute(
        select(Asset).where(Asset.id == asset_id, Asset.tenant_id == tenant_id)
    )
    asset = asset_row.scalar_one_or_none()
    if asset is None:
        return []

    events: list[TimelineEvent] = [
        TimelineEvent(
            event_type="discovered",
            timestamp=asset.discovered_at,
            summary=f"Asset discovered ({(asset.hostname or 'unknown')})",
        )
    ]

    risks = (
        await db.execute(
            select(Risk).where(
                Risk.asset_id == asset.id, Risk.tenant_id == tenant_id
            )
        )
    ).scalars().all()

    for r in risks:
        events.append(
            TimelineEvent(
                event_type="risk_added",
                timestamp=r.created_at,
                summary=f"{(r.severity or 'info').upper()} risk added: {r.finding}",
                risk_id=r.risk_id,
            )
        )
        if (r.status or "").lower() != "open":
            events.append(
                TimelineEvent(
                    event_type="risk_resolved",
                    timestamp=r.updated_at,
                    summary=f"Risk {r.risk_id} closed (status={r.status})",
                    risk_id=r.risk_id,
                )
            )

    events.sort(key=lambda e: e.timestamp or datetime.min.replace(tzinfo=timezone.utc))
    return events
