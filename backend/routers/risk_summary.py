"""
Risk Summary Router — REST endpoints for the Risk Aggregate Snapshot model.

Endpoints:
  GET  /api/risk-summary          — latest snapshot for current tenant (cached 5 min)
  GET  /api/risk-summary/trend    — historical snapshots (default: 30 days)
  POST /api/risk-summary/snapshot — manually trigger snapshot (ciso / admin only)

All endpoints:
  - Require authenticated user (JWT) via get_current_user.
  - Are scoped to the current tenant via TenantContext (set by get_current_user).
  - Never accept tenant_id from the request body — tenant comes from JWT only.
  - Require the VM module subscription (same gate as /api/risks).
"""
from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from backend.middleware.auth import get_current_user
from backend.middleware.module_gate import require_module
from backend.middleware.rbac import role_required
from backend.middleware.tenant import TenantContext
from backend.models.risk_snapshot import RiskScoreSummary
from backend.models.user import User
from backend.services.risk_aggregate_service import RiskAggregateService

router = APIRouter(dependencies=[Depends(require_module("VM"))])


# ---------------------------------------------------------------------------
# Response serialiser
# ---------------------------------------------------------------------------

def _snap_to_dict(snap: RiskScoreSummary) -> dict[str, Any]:
    """Serialise a RiskScoreSummary to a JSON-friendly dict."""
    top_sources = json.loads(snap.top_sources_json) if snap.top_sources_json else []
    module_breakdown = json.loads(snap.module_breakdown_json) if snap.module_breakdown_json else {}
    return {
        "id": str(snap.id),
        "tenant_id": str(snap.tenant_id),
        "snapshot_at": snap.snapshot_at.isoformat() if snap.snapshot_at else None,
        "total_risks": snap.total_risks,
        "critical_count": snap.critical_count,
        "high_count": snap.high_count,
        "medium_count": snap.medium_count,
        "low_count": snap.low_count,
        "info_count": snap.info_count,
        "exploit_active_count": snap.exploit_active_count,
        "kev_active_count": snap.kev_active_count,
        "mean_ttr_hours": snap.mean_ttr_hours,
        "mean_composite_score": snap.mean_composite_score,
        "top_sources": top_sources,
        "module_breakdown": module_breakdown,
        "created_at": snap.created_at.isoformat() if snap.created_at else None,
    }


# ---------------------------------------------------------------------------
# GET /api/risk-summary  — latest snapshot
# ---------------------------------------------------------------------------

@router.get("")
async def get_latest_risk_summary(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """
    Return the most recent RiskScoreSummary for the current tenant.

    Response is served from a 5-minute in-process cache.  When no snapshot
    exists yet (e.g. freshly onboarded tenant), returns 404 with a clear message.
    """
    tenant_id = TenantContext.get()
    svc = RiskAggregateService(db)
    snap = await svc.get_latest(tenant_id)
    if snap is None:
        raise HTTPException(
            status_code=404,
            detail=(
                "No risk summary snapshot found for this tenant. "
                "Trigger a snapshot via POST /api/risk-summary/snapshot."
            ),
        )
    return _snap_to_dict(snap)


# ---------------------------------------------------------------------------
# GET /api/risk-summary/trend  — historical snapshots
# ---------------------------------------------------------------------------

@router.get("/trend")
async def get_risk_summary_trend(
    days: int = Query(default=30, ge=1, le=365, description="Number of days of history to return"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[dict[str, Any]]:
    """
    Return historical RiskScoreSummary snapshots for the current tenant.

    Snapshots are ordered oldest-first.  Use `days` query param (1–365).
    """
    tenant_id = TenantContext.get()
    svc = RiskAggregateService(db)
    snaps = await svc.get_trend(tenant_id, days_back=days)
    return [_snap_to_dict(s) for s in snaps]


# ---------------------------------------------------------------------------
# POST /api/risk-summary/snapshot  — manual trigger (admin / ciso only)
# ---------------------------------------------------------------------------

@router.post("/snapshot", status_code=201)
async def trigger_snapshot(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(role_required("ciso")),
) -> dict[str, Any]:
    """
    Manually compute and persist a RiskScoreSummary for the current tenant.

    Restricted to users with role ciso or higher (ciso, executive, board).
    Idempotent within the same calendar minute — safe to call repeatedly.
    """
    tenant_id = TenantContext.get()
    svc = RiskAggregateService(db)
    snap = await svc.write_snapshot(tenant_id)
    await db.commit()
    await db.refresh(snap)
    return _snap_to_dict(snap)
