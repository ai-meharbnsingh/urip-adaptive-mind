"""
Compliance score API — P2B.11.

Endpoints:
  GET  /compliance-score                          — current scores across all frameworks
  GET  /compliance-score/{framework_short_code}   — drill-down: score + per-category +
                                                     failing controls
  GET  /compliance-score/{framework_short_code}/trend?days=30
  POST /compliance-score/snapshot     (admin)     — manually trigger snapshot
"""
from __future__ import annotations

from typing import Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from compliance_backend.database import get_async_session
from compliance_backend.middleware.auth import require_auth
from compliance_backend.middleware.tenant import require_tenant
from compliance_backend.models.framework import Framework
from compliance_backend.services.audit_writer import write_audit
from compliance_backend.services.scoring_engine import ScoringEngine

router = APIRouter(prefix="/compliance-score", tags=["compliance-score"])


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class FrameworkScoreOut(BaseModel):
    framework_id: str
    framework_short_code: Optional[str]
    score: float
    pass_count: int
    fail_count: int
    inconclusive_count: int
    total_controls: int
    total_applicable: int
    as_of: str


class CategoryBreakdownOut(BaseModel):
    category: str
    pass_count: int
    fail_count: int
    inconclusive_count: int
    score: float


class FrameworkScoreDetail(BaseModel):
    summary: FrameworkScoreOut
    categories: List[CategoryBreakdownOut]
    failing_control_ids: List[str]


class TrendPoint(BaseModel):
    date: str
    score: float


class TrendOut(BaseModel):
    framework_short_code: str
    days: int
    points: List[TrendPoint]


class SnapshotOut(BaseModel):
    snapshots_written: int
    framework_short_codes: List[str]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _require_admin(claims: dict) -> None:
    # CRIT-008 — see compliance_backend.middleware.auth.require_compliance_admin
    from compliance_backend.middleware.auth import require_compliance_admin

    require_compliance_admin(claims)


def _to_score_out(s) -> FrameworkScoreOut:
    return FrameworkScoreOut(
        framework_id=s.framework_id,
        framework_short_code=s.framework_short_code,
        score=s.score,
        pass_count=s.pass_count,
        fail_count=s.fail_count,
        inconclusive_count=s.inconclusive_count,
        total_controls=s.total_controls,
        total_applicable=s.total_applicable,
        as_of=s.as_of.isoformat(),
    )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("", response_model=Dict[str, FrameworkScoreOut])
async def all_scores(
    _claims: dict = Depends(require_auth),
    tenant_id: str = Depends(require_tenant),
    session: AsyncSession = Depends(get_async_session),
) -> Dict[str, FrameworkScoreOut]:
    engine = ScoringEngine(db=session)
    scores = await engine.calculate_all_frameworks(tenant_id=tenant_id)
    return {short: _to_score_out(s) for short, s in scores.items()}


@router.get("/snapshot")  # GET form so docs are easy to navigate; real trigger is POST below
async def _placeholder_snapshot_get():
    raise HTTPException(
        status_code=status.HTTP_405_METHOD_NOT_ALLOWED,
        detail="Use POST /compliance-score/snapshot to trigger a snapshot.",
    )


@router.post("/snapshot", response_model=SnapshotOut, status_code=status.HTTP_201_CREATED)
async def trigger_snapshot(
    claims: dict = Depends(require_auth),
    tenant_id: str = Depends(require_tenant),
    session: AsyncSession = Depends(get_async_session),
) -> SnapshotOut:
    """Manually trigger a snapshot for every framework for this tenant. Admin-only."""
    _require_admin(claims)
    engine = ScoringEngine(db=session)
    snaps = await engine.write_snapshots_for_all_frameworks(tenant_id=tenant_id)
    await write_audit(
        session,
        tenant_id=tenant_id,
        user_id=claims.get("sub", "unknown"),
        action="compliance_score_snapshot_triggered",
        resource_type="score_snapshot",
        resource_id=None,
        details={"snapshots_written": len(snaps)},
    )
    await session.commit()

    # Resolve short codes (best-effort)
    short_codes: List[str] = []
    for snap in snaps:
        fw = (await session.execute(
            select(Framework).where(Framework.id == snap.framework_id)
        )).scalar_one_or_none()
        if fw:
            short_codes.append(fw.short_code)
    return SnapshotOut(
        snapshots_written=len(snaps),
        framework_short_codes=short_codes,
    )


@router.get("/{framework_short_code}", response_model=FrameworkScoreDetail)
async def framework_detail(
    framework_short_code: str,
    _claims: dict = Depends(require_auth),
    tenant_id: str = Depends(require_tenant),
    session: AsyncSession = Depends(get_async_session),
) -> FrameworkScoreDetail:
    fw = (await session.execute(
        select(Framework).where(Framework.short_code == framework_short_code.upper())
    )).scalar_one_or_none()
    if fw is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Framework '{framework_short_code}' not found.",
        )

    engine = ScoringEngine(db=session)
    summary = await engine.calculate_framework_score(
        tenant_id=tenant_id, framework_id=fw.id,
    )
    categories = await engine.category_breakdown(
        tenant_id=tenant_id, framework_id=fw.id,
    )

    return FrameworkScoreDetail(
        summary=_to_score_out(summary),
        categories=[
            CategoryBreakdownOut(
                category=c.category,
                pass_count=c.pass_count,
                fail_count=c.fail_count,
                inconclusive_count=c.inconclusive_count,
                score=c.score,
            )
            for c in categories
        ],
        failing_control_ids=summary.failing_control_ids,
    )


@router.get("/{framework_short_code}/trend", response_model=TrendOut)
async def framework_trend(
    framework_short_code: str,
    days: int = Query(30, ge=1, le=365),
    _claims: dict = Depends(require_auth),
    tenant_id: str = Depends(require_tenant),
    session: AsyncSession = Depends(get_async_session),
) -> TrendOut:
    fw = (await session.execute(
        select(Framework).where(Framework.short_code == framework_short_code.upper())
    )).scalar_one_or_none()
    if fw is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Framework '{framework_short_code}' not found.",
        )

    engine = ScoringEngine(db=session)
    pairs = await engine.compliance_trend(
        tenant_id=tenant_id, framework_id=fw.id, days_back=days,
    )
    return TrendOut(
        framework_short_code=fw.short_code,
        days=days,
        points=[TrendPoint(date=d, score=s) for d, s in pairs],
    )
