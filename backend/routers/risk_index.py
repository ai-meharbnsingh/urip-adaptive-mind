"""
Cyber Risk Index Router — TrendAI-style /api/risk-index endpoints.

Endpoints
---------
  GET  /api/risk-index                       — top-strip dashboard payload (KPI)
  GET  /api/risk-index/trend?days=N          — historical 0-100 + sub-index trend
  GET  /api/risk-index/subindexes/{name}     — drill-down per sub-index
                                                (name in: exposure, attack, security_config)
  GET  /api/risk-index/domains/{name}        — drill-down per domain bucket
                                                (name in: devices, internet_facing,
                                                 accounts, applications, cloud_assets)

All endpoints
-------------
- Require an authenticated user (JWT) via get_current_user.
- Are scoped to the current tenant via TenantContext.
- Are gated by ``require_module("CORE")`` — the Cyber Risk Index is part of
  the core dashboard offering.
- Never accept a tenant_id from the body / query — tenant comes from the JWT.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from backend.middleware.auth import get_current_user
from backend.middleware.module_gate import require_module
from backend.middleware.tenant import TenantContext
from backend.models.risk_snapshot import RiskScoreSummary
from backend.models.user import User
from backend.schemas.risk_index import (
    DomainBreakdownOut,
    DomainBucketOut,
    DomainDetailOut,
    RiskIndexDashboardOut,
    RiskIndexTrendPointOut,
    SubindexDetailOut,
    SubindexOut,
    SubindexesOut,
    TopRiskOut,
)
from backend.services.risk_index_service import (
    DOMAIN_NAMES,
    SUBINDEX_NAMES,
    DomainBreakdown,
    DomainBucket,
    RiskIndex,
    RiskIndexService,
    Subindex,
    Subindexes,
    TopRisk,
)


router = APIRouter(dependencies=[Depends(require_module("CORE"))])


# ─────────────────────────────────────────────────────────────────────────────
# Serialiser helpers
# ─────────────────────────────────────────────────────────────────────────────

def _subindex_to_out(s: Subindex) -> SubindexOut:
    return SubindexOut(
        score=s.score, level=s.level, contributing_count=s.contributing_count,
    )


def _subindexes_to_out(s: Subindexes) -> SubindexesOut:
    return SubindexesOut(
        exposure=_subindex_to_out(s.exposure),
        attack=_subindex_to_out(s.attack),
        security_config=_subindex_to_out(s.security_config),
    )


def _bucket_to_out(b: DomainBucket) -> DomainBucketOut:
    return DomainBucketOut(
        name=b.name,
        total=b.total,
        critical_count=b.critical_count,
        high_count=b.high_count,
        mean_score=b.mean_score,
        level=b.level,
    )


def _breakdown_to_out(bk: DomainBreakdown) -> DomainBreakdownOut:
    return DomainBreakdownOut(
        devices=_bucket_to_out(bk.devices),
        internet_facing=_bucket_to_out(bk.internet_facing),
        accounts=_bucket_to_out(bk.accounts),
        applications=_bucket_to_out(bk.applications),
        cloud_assets=_bucket_to_out(bk.cloud_assets),
    )


def _toprisks_to_out(rows: list[TopRisk]) -> list[TopRiskOut]:
    return [
        TopRiskOut(
            risk_id=r.risk_id,
            finding=r.finding,
            source=r.source,
            severity=r.severity,
            composite_score=r.composite_score,
            asset=r.asset,
            domain=r.domain,
        )
        for r in rows
    ]


# ─────────────────────────────────────────────────────────────────────────────
# GET /api/risk-index — top-strip
# ─────────────────────────────────────────────────────────────────────────────

@router.get("", response_model=RiskIndexDashboardOut)
async def get_risk_index(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> RiskIndexDashboardOut:
    """
    Single-shot dashboard payload:
      - 0-100 score + level + color
      - 3 sub-indexes
      - 5 domain bucket counts

    Frontend renders this directly into the top KPI strip.
    """
    tenant_id = TenantContext.get()
    svc = RiskIndexService(db)

    idx: RiskIndex = await svc.compute_risk_index_0_100(tenant_id)
    subs: Subindexes = await svc.compute_subindexes(tenant_id)
    bk: DomainBreakdown = await svc.compute_domain_breakdown(tenant_id)

    return RiskIndexDashboardOut(
        score=idx.score,
        level=idx.level,
        color_code=idx.color_code,
        subindexes=_subindexes_to_out(subs),
        domains=_breakdown_to_out(bk),
    )


# ─────────────────────────────────────────────────────────────────────────────
# GET /api/risk-index/trend
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/trend", response_model=list[RiskIndexTrendPointOut])
async def get_risk_index_trend(
    days: int = Query(default=30, ge=1, le=365),
    compare: str | None = Query(
        default=None,
        description="Optional comparison series: 'industry' | 'none'.  "
                    "Industry comparison is informational; same trend payload is "
                    "returned with an industry_avg field per point when present.",
    ),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[dict[str, Any]]:
    """
    Historical trend of 0-100 index + sub-indexes for the current tenant.

    Reads from ``risk_score_summaries``.  Each row already carries the
    derived 0-100 fields (set by RiskAggregateService.write_snapshot).
    """
    tenant_id = TenantContext.get()
    cutoff = datetime.now().astimezone() - _days(days)

    rows = (await db.execute(
        select(RiskScoreSummary).where(
            and_(
                RiskScoreSummary.tenant_id == tenant_id,
                RiskScoreSummary.snapshot_at >= cutoff,
            )
        ).order_by(RiskScoreSummary.snapshot_at.asc())
    )).scalars().all()

    out: list[dict[str, Any]] = []
    for r in rows:
        out.append({
            "snapshot_at": r.snapshot_at.isoformat() if r.snapshot_at else None,
            "index_0_100": r.index_0_100,
            "level": r.level,
            "subindex_exposure": r.subindex_exposure,
            "subindex_attack": r.subindex_attack,
            "subindex_security_config": r.subindex_security_config,
            "domain_devices_count": r.domain_devices_count,
            "domain_internet_facing_count": r.domain_internet_facing_count,
            "domain_accounts_count": r.domain_accounts_count,
            "domain_applications_count": r.domain_applications_count,
            "domain_cloud_assets_count": r.domain_cloud_assets_count,
        })
    return out


def _days(n: int):
    """Return a timedelta of n days (split out for readability + testability)."""
    from datetime import timedelta
    return timedelta(days=n)


# ─────────────────────────────────────────────────────────────────────────────
# GET /api/risk-index/subindexes/{name}
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/subindexes/{name}", response_model=SubindexDetailOut)
async def get_subindex_detail(
    name: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> SubindexDetailOut:
    """
    Drill-down detail for a single sub-index.  Returns the score + top 10
    contributing risks (highest composite_score first).
    """
    if name not in SUBINDEX_NAMES:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown sub-index '{name}'. "
                   f"Allowed: {', '.join(SUBINDEX_NAMES)}.",
        )

    tenant_id = TenantContext.get()
    svc = RiskIndexService(db)
    subs: Subindexes = await svc.compute_subindexes(tenant_id)
    sub: Subindex = getattr(subs, name)
    top = await svc.top_risks_for_subindex(tenant_id, name, limit=10)  # type: ignore[arg-type]

    return SubindexDetailOut(
        name=name,
        score=sub.score,
        level=sub.level,
        contributing_count=sub.contributing_count,
        top_risks=_toprisks_to_out(top),
    )


# ─────────────────────────────────────────────────────────────────────────────
# GET /api/risk-index/domains/{name}
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/domains/{name}", response_model=DomainDetailOut)
async def get_domain_detail(
    name: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> DomainDetailOut:
    """
    Drill-down detail for one of the 5 domain buckets.
    """
    if name not in DOMAIN_NAMES:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown domain '{name}'. "
                   f"Allowed: {', '.join(DOMAIN_NAMES)}.",
        )

    tenant_id = TenantContext.get()
    svc = RiskIndexService(db)
    bk: DomainBreakdown = await svc.compute_domain_breakdown(tenant_id)
    bucket: DomainBucket = getattr(bk, name)
    top = await svc.top_risks_for_domain(tenant_id, name, limit=10)  # type: ignore[arg-type]

    return DomainDetailOut(
        name=name,
        total=bucket.total,
        critical_count=bucket.critical_count,
        high_count=bucket.high_count,
        mean_score=bucket.mean_score,
        level=bucket.level,
        top_risks=_toprisks_to_out(top),
    )
