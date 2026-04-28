"""
Admin view of auditor activity — P2B.10.

Lets tenant admins audit what their external auditors have been looking at.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from compliance_backend.database import get_async_session
from compliance_backend.middleware.auth import require_auth
from compliance_backend.middleware.tenant import require_tenant
from compliance_backend.models.auditor import AuditorActivityLog

router = APIRouter(prefix="/admin/auditor-activity", tags=["admin"])


class AuditorActivityOut(BaseModel):
    id: str
    tenant_id: str
    auditor_access_id: str
    auditor_email: str
    action: str
    target_type: Optional[str]
    target_id: Optional[str]
    accessed_at: str
    ip_address: Optional[str]


def _require_admin(claims: dict) -> None:
    # CRIT-008 — see compliance_backend.middleware.auth.require_compliance_admin
    from compliance_backend.middleware.auth import require_compliance_admin

    require_compliance_admin(claims)


@router.get("", response_model=List[AuditorActivityOut])
async def list_activity(
    auditor_access_id: Optional[str] = Query(None),
    action: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=500),
    claims: dict = Depends(require_auth),
    tenant_id: str = Depends(require_tenant),
    session: AsyncSession = Depends(get_async_session),
) -> List[AuditorActivityOut]:
    _require_admin(claims)
    filters = [AuditorActivityLog.tenant_id == tenant_id]
    if auditor_access_id:
        filters.append(AuditorActivityLog.auditor_access_id == auditor_access_id)
    if action:
        filters.append(AuditorActivityLog.action == action)

    rows = (await session.execute(
        select(AuditorActivityLog)
        .where(and_(*filters))
        .order_by(AuditorActivityLog.accessed_at.desc())
        .limit(limit)
    )).scalars().all()

    return [
        AuditorActivityOut(
            id=r.id,
            tenant_id=r.tenant_id,
            auditor_access_id=r.auditor_access_id,
            auditor_email=r.auditor_email,
            action=r.action,
            target_type=r.target_type,
            target_id=r.target_id,
            accessed_at=r.accessed_at.isoformat(),
            ip_address=r.ip_address,
        )
        for r in rows
    ]


# --------------------------------------------------------------------------- #
# Calendar heatmap aggregation — last N days, one entry per UTC day with the
# count + the action breakdown so the UI can render a coloured calendar grid.
# --------------------------------------------------------------------------- #
class HeatmapDay(BaseModel):
    date: str  # YYYY-MM-DD (UTC)
    count: int
    actions: Dict[str, int]


class HeatmapResponse(BaseModel):
    days_window: int
    total_actions: int
    days: List[HeatmapDay]


@router.get("/heatmap", response_model=HeatmapResponse)
async def auditor_activity_heatmap(
    days: int = Query(30, ge=1, le=365),
    auditor_access_id: Optional[str] = Query(None),
    claims: dict = Depends(require_auth),
    tenant_id: str = Depends(require_tenant),
    session: AsyncSession = Depends(get_async_session),
) -> HeatmapResponse:
    """Return a calendar heatmap over the last `days` UTC days.

    Days with zero activity are still emitted (count=0) so the front-end can
    render a complete grid without back-filling.
    """
    _require_admin(claims)

    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=days - 1)
    start_of_day = datetime(cutoff.year, cutoff.month, cutoff.day, tzinfo=timezone.utc)

    filters = [
        AuditorActivityLog.tenant_id == tenant_id,
        AuditorActivityLog.accessed_at >= start_of_day,
    ]
    if auditor_access_id:
        filters.append(AuditorActivityLog.auditor_access_id == auditor_access_id)

    rows = (await session.execute(
        select(AuditorActivityLog).where(and_(*filters))
    )).scalars().all()

    per_day: Dict[str, Counter[str]] = defaultdict(Counter)
    for r in rows:
        ts = r.accessed_at
        if ts is None:
            continue
        # Some backends return naive datetimes; assume UTC.
        if getattr(ts, "tzinfo", None) is None:
            ts = ts.replace(tzinfo=timezone.utc)
        key = ts.astimezone(timezone.utc).strftime("%Y-%m-%d")
        per_day[key][r.action or "unknown"] += 1

    out_days: list[HeatmapDay] = []
    for offset in range(days):
        day_dt = start_of_day + timedelta(days=offset)
        key = day_dt.strftime("%Y-%m-%d")
        actions = per_day.get(key, Counter())
        out_days.append(
            HeatmapDay(
                date=key,
                count=int(sum(actions.values())),
                actions={k: int(v) for k, v in actions.items()},
            )
        )

    return HeatmapResponse(
        days_window=days,
        total_actions=int(sum(d.count for d in out_days)),
        days=out_days,
    )
