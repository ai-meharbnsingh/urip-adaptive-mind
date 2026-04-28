"""
Risk Aggregate Service — cloud-side snapshot writer and trend reader.

PURPOSE (DELIVERY_ARCHITECTURE.md §7.4):
  The Hybrid-SaaS architecture keeps raw risk rows on the on-prem agent.  When
  the agent goes offline, the cloud dashboard would show nothing.  This service
  writes periodic aggregate snapshots (RiskScoreSummary rows) so the dashboard
  can always show the latest known posture and trend lines even during agent
  downtime.

MIRRORS:
  compliance/backend/compliance_backend/services/scoring_engine.py
  (write_daily_snapshot / write_snapshots_for_all_frameworks pattern)

CACHE:
  The latest snapshot per tenant is cached in-process with a 5-minute TTL.
  Dashboard GET /api/risk-summary reads from cache to avoid per-request DB
  round-trips.  Cache is invalidated on write_snapshot().

IDEMPOTENCY:
  write_snapshot() is idempotent within the same calendar minute: if a snapshot
  already exists for (tenant_id, minute-floor), it returns the existing row
  without inserting a duplicate.
"""
from __future__ import annotations

import json
import logging
import time
import uuid
from collections import Counter
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.risk import Risk
from backend.models.risk_snapshot import RiskScoreSummary
from backend.models.tenant import Tenant
from backend.services.risk_index_service import RiskIndexService

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# In-process snapshot cache  (tenant_id hex → (RiskScoreSummary, expire_ts))
# ---------------------------------------------------------------------------
_CACHE_TTL_SECONDS = 300  # 5 minutes
_snapshot_cache: dict[str, tuple[RiskScoreSummary, float]] = {}


def _cache_key(tenant_id: uuid.UUID) -> str:
    return str(tenant_id)


def _cache_get(tenant_id: uuid.UUID) -> Optional[RiskScoreSummary]:
    key = _cache_key(tenant_id)
    entry = _snapshot_cache.get(key)
    if entry is None:
        return None
    snap, expire_ts = entry
    if time.monotonic() > expire_ts:
        del _snapshot_cache[key]
        return None
    return snap


def _cache_set(tenant_id: uuid.UUID, snap: RiskScoreSummary) -> None:
    _snapshot_cache[_cache_key(tenant_id)] = (snap, time.monotonic() + _CACHE_TTL_SECONDS)


def _cache_invalidate(tenant_id: uuid.UUID) -> None:
    _snapshot_cache.pop(_cache_key(tenant_id), None)


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------

class RiskAggregateService:
    """Stateless service — pass DB session via constructor, same pattern as ScoringEngine."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    # ------------------------------------------------------------------ #
    #  Core computation                                                    #
    # ------------------------------------------------------------------ #

    async def compute_current_summary(self, tenant_id: uuid.UUID) -> RiskScoreSummary:
        """
        Calculate a live RiskScoreSummary from current Risk rows.

        Does NOT persist — call write_snapshot() to persist.
        """
        now = datetime.now(timezone.utc)

        # --- Severity counts (all statuses) ---
        sev_rows = (await self.db.execute(
            select(Risk.severity, func.count(Risk.id).label("cnt"))
            .where(Risk.tenant_id == tenant_id)
            .group_by(Risk.severity)
        )).all()
        sev_map: dict[str, int] = {row.severity: row.cnt for row in sev_rows}

        total_risks = sum(sev_map.values())
        critical_count = sev_map.get("critical", 0)
        high_count = sev_map.get("high", 0)
        medium_count = sev_map.get("medium", 0)
        low_count = sev_map.get("low", 0)
        info_count = sev_map.get("info", 0)

        # --- Exploitability (open risks only) ---
        exploit_q = await self.db.execute(
            select(func.count(Risk.id)).where(
                Risk.tenant_id == tenant_id,
                Risk.status == "open",
                Risk.epss_score > 0.7,
            )
        )
        exploit_active_count: int = exploit_q.scalar() or 0

        kev_q = await self.db.execute(
            select(func.count(Risk.id)).where(
                Risk.tenant_id == tenant_id,
                Risk.status == "open",
                Risk.in_kev_catalog.is_(True),
            )
        )
        kev_active_count: int = kev_q.scalar() or 0

        # --- Mean TTR over last 30 days (closed risks only) ---
        cutoff_30d = now - timedelta(days=30)
        ttr_rows = (await self.db.execute(
            select(Risk.created_at, Risk.updated_at)
            .where(
                Risk.tenant_id == tenant_id,
                Risk.status == "closed",
                Risk.updated_at >= cutoff_30d,
            )
        )).all()
        mean_ttr_hours: Optional[float] = None
        if ttr_rows:
            hours_list = [
                (row.updated_at - row.created_at).total_seconds() / 3600.0
                for row in ttr_rows
                if row.updated_at and row.created_at
                and row.updated_at >= row.created_at
            ]
            if hours_list:
                mean_ttr_hours = round(sum(hours_list) / len(hours_list), 2)

        # --- Mean composite_score (open risks with a score) ---
        score_q = await self.db.execute(
            select(func.avg(Risk.composite_score)).where(
                Risk.tenant_id == tenant_id,
                Risk.status == "open",
                Risk.composite_score.is_not(None),
            )
        )
        raw_avg = score_q.scalar()
        mean_composite_score: Optional[float] = round(float(raw_avg), 2) if raw_avg is not None else None

        # --- Top 5 sources by risk count ---
        src_rows = (await self.db.execute(
            select(Risk.source, func.count(Risk.id).label("cnt"))
            .where(Risk.tenant_id == tenant_id)
            .group_by(Risk.source)
            .order_by(func.count(Risk.id).desc())
            .limit(5)
        )).all()
        top_sources = [{"source": row.source, "count": row.cnt} for row in src_rows]
        top_sources_json = json.dumps(top_sources)

        # --- Module/domain breakdown ---
        domain_rows = (await self.db.execute(
            select(Risk.domain, func.count(Risk.id).label("cnt"))
            .where(Risk.tenant_id == tenant_id)
            .group_by(Risk.domain)
        )).all()
        # domain values map to module codes (best-effort — domains are set by connectors)
        module_breakdown = {row.domain.upper(): row.cnt for row in domain_rows}
        module_breakdown_json = json.dumps(module_breakdown)

        # --- TrendAI-style 0-100 Cyber Risk Index + sub-indexes + buckets ---
        # Computed via RiskIndexService so the snapshot always carries the
        # exact same numbers the dashboard endpoint returns.
        idx_svc = RiskIndexService(self.db)
        idx = await idx_svc.compute_risk_index_0_100(tenant_id)
        subs = await idx_svc.compute_subindexes(tenant_id)
        bk = await idx_svc.compute_domain_breakdown(tenant_id)

        snap = RiskScoreSummary(
            tenant_id=tenant_id,
            snapshot_at=now,
            total_risks=total_risks,
            critical_count=critical_count,
            high_count=high_count,
            medium_count=medium_count,
            low_count=low_count,
            info_count=info_count,
            exploit_active_count=exploit_active_count,
            kev_active_count=kev_active_count,
            mean_ttr_hours=mean_ttr_hours,
            mean_composite_score=mean_composite_score,
            top_sources_json=top_sources_json,
            module_breakdown_json=module_breakdown_json,
            # Cyber Risk Index 0-100
            index_0_100=idx.score,
            level=idx.level,
            subindex_exposure=subs.exposure.score,
            subindex_attack=subs.attack.score,
            subindex_security_config=subs.security_config.score,
            # Domain bucket counts
            domain_devices_count=bk.devices.total,
            domain_internet_facing_count=bk.internet_facing.total,
            domain_accounts_count=bk.accounts.total,
            domain_applications_count=bk.applications.total,
            domain_cloud_assets_count=bk.cloud_assets.total,
            # Per-bucket critical counts
            domain_devices_critical=bk.devices.critical_count,
            domain_internet_facing_critical=bk.internet_facing.critical_count,
            domain_accounts_critical=bk.accounts.critical_count,
            domain_applications_critical=bk.applications.critical_count,
            domain_cloud_assets_critical=bk.cloud_assets.critical_count,
        )
        return snap

    # ------------------------------------------------------------------ #
    #  Persist                                                             #
    # ------------------------------------------------------------------ #

    async def write_snapshot(self, tenant_id: uuid.UUID) -> RiskScoreSummary:
        """
        Compute + persist a snapshot for tenant_id.

        Idempotent within the same calendar minute: if a snapshot already exists
        for this tenant in the current minute, returns the existing row.

        Caller is responsible for committing the session (or use the helper
        which commits internally for the nightly batch).
        """
        now = datetime.now(timezone.utc)
        # Floor to minute for idempotency window
        minute_floor = now.replace(second=0, microsecond=0)
        minute_ceil = minute_floor + timedelta(minutes=1)

        existing = (await self.db.execute(
            select(RiskScoreSummary).where(
                RiskScoreSummary.tenant_id == tenant_id,
                RiskScoreSummary.snapshot_at >= minute_floor,
                RiskScoreSummary.snapshot_at < minute_ceil,
            ).limit(1)
        )).scalar_one_or_none()

        if existing is not None:
            logger.debug(
                "write_snapshot: idempotent — returning existing snapshot id=%s tenant=%s",
                existing.id, tenant_id,
            )
            _cache_set(tenant_id, existing)
            return existing

        snap = await self.compute_current_summary(tenant_id)
        self.db.add(snap)
        await self.db.flush()

        _cache_invalidate(tenant_id)
        _cache_set(tenant_id, snap)

        logger.info(
            "write_snapshot: persisted id=%s tenant=%s total=%d",
            snap.id, tenant_id, snap.total_risks,
        )
        return snap

    async def write_snapshots_for_all_tenants(self) -> list[RiskScoreSummary]:
        """
        Compute + persist snapshots for every active tenant.

        Used by the nightly/hourly batch job.  Each snapshot is committed
        individually so a failure on one tenant does not block others.
        """
        tenants = (await self.db.execute(
            select(Tenant).where(Tenant.is_active.is_(True))
        )).scalars().all()

        results: list[RiskScoreSummary] = []
        for tenant in tenants:
            try:
                snap = await self.write_snapshot(tenant.id)
                await self.db.commit()
                results.append(snap)
            except Exception:
                await self.db.rollback()
                logger.exception(
                    "write_snapshots_for_all_tenants: failed for tenant=%s", tenant.id
                )
        return results

    # ------------------------------------------------------------------ #
    #  Read                                                                #
    # ------------------------------------------------------------------ #

    async def get_latest(self, tenant_id: uuid.UUID) -> Optional[RiskScoreSummary]:
        """
        Return the most recent snapshot for tenant_id.

        Checks in-process cache first (5-minute TTL).  Falls back to DB if
        cache is cold or expired.
        """
        cached = _cache_get(tenant_id)
        if cached is not None:
            return cached

        row = (await self.db.execute(
            select(RiskScoreSummary)
            .where(RiskScoreSummary.tenant_id == tenant_id)
            .order_by(RiskScoreSummary.snapshot_at.desc())
            .limit(1)
        )).scalar_one_or_none()

        if row is not None:
            _cache_set(tenant_id, row)
        return row

    async def get_trend(
        self,
        tenant_id: uuid.UUID,
        days_back: int = 30,
    ) -> list[RiskScoreSummary]:
        """
        Return historical snapshots for the past `days_back` days, oldest first.
        """
        cutoff = datetime.now(timezone.utc) - timedelta(days=days_back)
        rows = (await self.db.execute(
            select(RiskScoreSummary)
            .where(
                and_(
                    RiskScoreSummary.tenant_id == tenant_id,
                    RiskScoreSummary.snapshot_at >= cutoff,
                )
            )
            .order_by(RiskScoreSummary.snapshot_at.asc())
        )).scalars().all()
        return list(rows)
