from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from backend.middleware.auth import get_current_user
from backend.middleware.module_gate import require_module
from backend.middleware.rbac import role_required
from backend.middleware.tenant import TenantContext
from backend.models.acceptance import AcceptanceRequest
from backend.models.audit_log import AuditLog
from backend.models.risk import Risk, RiskHistory
from backend.models.user import User
from backend.schemas.acceptance import (
    AcceptanceAction,
    AcceptanceActionResponse,
    AcceptanceCreate,
    AcceptanceListItem,
    AcceptanceRead,
    AcceptanceRiskDetail,
)
from backend.services.tenant_query import apply_tenant_filter
from backend.services.threat_intel_service import get_apt_for_cve
from backend.utils import parse_uuid

# CRIT-007 — acceptance shares the VM module with risks (an acceptance is
# always tied to a risk).  Router-level gate ensures every endpoint is covered.
router = APIRouter(dependencies=[Depends(require_module("VM"))])


def acceptance_to_read(a: AcceptanceRequest) -> AcceptanceRead:
    return AcceptanceRead(
        id=str(a.id),
        risk_id=str(a.risk_id),
        requested_by=str(a.requested_by),
        justification=a.justification,
        compensating_controls=a.compensating_controls,
        residual_risk=a.residual_risk,
        recommendation=a.recommendation,
        status=a.status,
        reviewed_by=str(a.reviewed_by) if a.reviewed_by else None,
        review_date=a.review_date,
        review_period_days=a.review_period_days,
        created_at=a.created_at,
    )


@router.get("", response_model=list[AcceptanceListItem])
async def list_acceptance_requests(
    status: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # Tenant-scoped — only return acceptance rows belonging to the caller's tenant
    query = select(AcceptanceRequest)
    query = apply_tenant_filter(query, AcceptanceRequest)
    if status:
        query = query.where(AcceptanceRequest.status == status.lower())
    query = query.order_by(AcceptanceRequest.created_at.desc())

    result = await db.execute(query)
    requests = result.scalars().all()

    if not requests:
        return []

    # Batch-fetch related risks (already tenant-scoped via FK chain) and users.
    #
    # H4 (Codex Apr 28 audit) — defence-in-depth tenant filter on the Risk and
    # User joins.  Mirrors the pattern in audit_log.py:86-89.  Even if a
    # corrupted acceptance row references a risk_id or user_id from another
    # tenant, the enrichment never loads the foreign row.
    risk_ids = [a.risk_id for a in requests]
    user_ids = [a.requested_by for a in requests]

    caller_tenant_id = TenantContext.get_or_none()

    risk_query = select(Risk).where(Risk.id.in_(risk_ids))
    if caller_tenant_id is not None and hasattr(Risk, "tenant_id"):
        risk_query = risk_query.where(Risk.tenant_id == caller_tenant_id)
    risk_result = await db.execute(risk_query)
    risks_map = {r.id: r for r in risk_result.scalars().all()}

    user_query = select(User).where(User.id.in_(user_ids))
    if caller_tenant_id is not None and hasattr(User, "tenant_id"):
        user_query = user_query.where(User.tenant_id == caller_tenant_id)
    user_result = await db.execute(user_query)
    users_map = {u.id: u for u in user_result.scalars().all()}

    enriched: list[AcceptanceListItem] = []
    for a in requests:
        risk = risks_map.get(a.risk_id)
        requester = users_map.get(a.requested_by)
        base = acceptance_to_read(a)
        item = AcceptanceListItem(
            **base.model_dump(),
            risk_detail=AcceptanceRiskDetail(
                risk_id=risk.risk_id if risk else None,
                finding=risk.finding if risk else None,
                cvss_score=float(risk.cvss_score) if risk else None,
                severity=risk.severity if risk else None,
                asset=risk.asset if risk else None,
                domain=risk.domain if risk else None,
            ) if risk else None,
            requester_name=requester.full_name if requester else None,
            requester_team=requester.team if requester else None,
        )
        enriched.append(item)

    return enriched


@router.get("/stats")
async def acceptance_stats(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Aggregate counts for the acceptance dashboard cards.

    Returns pending count, approvals in the current calendar month, and
    lifetime total of accepted requests — all tenant-scoped.
    """
    pending_q = apply_tenant_filter(
        select(func.count()).select_from(AcceptanceRequest), AcceptanceRequest,
    ).where(AcceptanceRequest.status == "pending")
    pending = (await db.execute(pending_q)).scalar() or 0

    total_q = apply_tenant_filter(
        select(func.count()).select_from(AcceptanceRequest), AcceptanceRequest,
    ).where(AcceptanceRequest.status == "approved")
    total_accepted = (await db.execute(total_q)).scalar() or 0

    now = datetime.now(timezone.utc)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    month_q = apply_tenant_filter(
        select(func.count()).select_from(AcceptanceRequest), AcceptanceRequest,
    ).where(
        AcceptanceRequest.status == "approved",
        AcceptanceRequest.review_date >= month_start,
    )
    approved_this_month = (await db.execute(month_q)).scalar() or 0

    return {
        "pending": int(pending),
        "approved_this_month": int(approved_this_month),
        "total_accepted": int(total_accepted),
    }


@router.get("/pending")
async def acceptance_pending(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Pending acceptance requests in the shape acceptance-workflow.html expects.

    Each item carries the human-readable risk fields the UI renders
    (risk_id label, severity, title/finding, requester full name, date).
    """
    query = apply_tenant_filter(
        select(AcceptanceRequest), AcceptanceRequest,
    ).where(AcceptanceRequest.status == "pending").order_by(
        AcceptanceRequest.created_at.desc(),
    )
    requests = (await db.execute(query)).scalars().all()
    if not requests:
        return {"items": []}

    risk_ids = [a.risk_id for a in requests]
    user_ids = [a.requested_by for a in requests]
    caller_tenant_id = TenantContext.get_or_none()

    risk_query = select(Risk).where(Risk.id.in_(risk_ids))
    if caller_tenant_id is not None and hasattr(Risk, "tenant_id"):
        risk_query = risk_query.where(Risk.tenant_id == caller_tenant_id)
    risks_map = {r.id: r for r in (await db.execute(risk_query)).scalars().all()}

    user_query = select(User).where(User.id.in_(user_ids))
    if caller_tenant_id is not None and hasattr(User, "tenant_id"):
        user_query = user_query.where(User.tenant_id == caller_tenant_id)
    users_map = {u.id: u for u in (await db.execute(user_query)).scalars().all()}

    items = []
    for a in requests:
        risk = risks_map.get(a.risk_id)
        user = users_map.get(a.requested_by)
        items.append({
            "id": str(a.id),
            "risk_id": risk.risk_id if risk else None,
            "severity": risk.severity if risk else None,
            "title": risk.finding if risk else None,
            "requested_by": user.full_name if user else None,
            "requested_date": a.created_at.isoformat() if a.created_at else None,
        })
    return {"items": items}


@router.get("/recent")
async def acceptance_recent(
    limit: int = Query(default=10, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Recently approved acceptance requests for the dashboard table."""
    query = apply_tenant_filter(
        select(AcceptanceRequest), AcceptanceRequest,
    ).where(AcceptanceRequest.status == "approved").order_by(
        AcceptanceRequest.review_date.desc(),
    ).limit(limit)
    requests = (await db.execute(query)).scalars().all()
    if not requests:
        return {"items": []}

    risk_ids = [a.risk_id for a in requests]
    reviewer_ids = [a.reviewed_by for a in requests if a.reviewed_by]
    caller_tenant_id = TenantContext.get_or_none()

    risk_query = select(Risk).where(Risk.id.in_(risk_ids))
    if caller_tenant_id is not None and hasattr(Risk, "tenant_id"):
        risk_query = risk_query.where(Risk.tenant_id == caller_tenant_id)
    risks_map = {r.id: r for r in (await db.execute(risk_query)).scalars().all()}

    users_map: dict = {}
    if reviewer_ids:
        user_query = select(User).where(User.id.in_(reviewer_ids))
        if caller_tenant_id is not None and hasattr(User, "tenant_id"):
            user_query = user_query.where(User.tenant_id == caller_tenant_id)
        users_map = {u.id: u for u in (await db.execute(user_query)).scalars().all()}

    items = []
    for a in requests:
        risk = risks_map.get(a.risk_id)
        reviewer = users_map.get(a.reviewed_by) if a.reviewed_by else None
        items.append({
            "risk_id": risk.risk_id if risk else None,
            "title": risk.finding if risk else None,
            "asset": risk.asset if risk else None,
            "accepted_by": reviewer.full_name if reviewer else None,
            "accepted_date": a.review_date.isoformat() if a.review_date else None,
            "review_period": a.review_period_days or 90,
        })
    return {"items": items}


@router.post("", response_model=AcceptanceRead, status_code=201)
async def create_acceptance_request(
    data: AcceptanceCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(role_required("it_team")),
):
    # Tenant-scope risk lookup — prevents cross-tenant acceptance creation
    result = await db.execute(
        select(Risk).where(
            Risk.risk_id == data.risk_id,
            Risk.tenant_id == TenantContext.get(),
        )
    )
    risk = result.scalar_one_or_none()
    if not risk:
        raise HTTPException(status_code=404, detail="Risk not found")

    # Check duplicate within the same tenant
    existing = await db.execute(
        select(AcceptanceRequest).where(
            AcceptanceRequest.risk_id == risk.id,
            AcceptanceRequest.tenant_id == TenantContext.get(),
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Acceptance request already exists for this risk")

    recommendation = (
        f"Auto-generated: Review compensating controls for {risk.finding}. "
        f"CVSS {risk.cvss_score} ({risk.severity}). Re-review in 90 days."
    )

    apt_groups = get_apt_for_cve(risk.cve_id) if risk.cve_id else []
    if apt_groups:
        group_names = ", ".join(g["name"] for g in apt_groups)
        all_sectors: list[str] = []
        for g in apt_groups:
            all_sectors.extend(g.get("sectors", []))
        unique_sectors = ", ".join(sorted(set(all_sectors)))
        recommendation += (
            f" WARNING: This CVE is known to be used by {group_names}"
            f" which target {unique_sectors}. Consider this before accepting."
        )

    ar = AcceptanceRequest(
        risk_id=risk.id,
        requested_by=current_user.id,
        justification=data.justification,
        compensating_controls=data.compensating_controls,
        residual_risk=data.residual_risk,
        recommendation=recommendation,
        status="pending",
        tenant_id=TenantContext.get(),
    )
    db.add(ar)

    db.add(AuditLog(
        user_id=current_user.id,
        action="acceptance_requested",
        resource_type="acceptance",
        resource_id=ar.id,
        details={"risk_id": data.risk_id},
        tenant_id=TenantContext.get(),
    ))

    await db.commit()
    await db.refresh(ar)
    return acceptance_to_read(ar)


@router.post("/{acceptance_id}/approve", response_model=AcceptanceActionResponse)
async def approve_acceptance(
    acceptance_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(role_required("ciso")),
):
    # Tenant-scope by joining tenant_id — cross-tenant approval impossible (404)
    result = await db.execute(
        select(AcceptanceRequest).where(
            AcceptanceRequest.id == parse_uuid(acceptance_id, "acceptance_id"),
            AcceptanceRequest.tenant_id == TenantContext.get(),
        )
    )
    ar = result.scalar_one_or_none()
    if not ar:
        raise HTTPException(status_code=404, detail="Acceptance request not found")

    ar.status = "approved"
    ar.reviewed_by = current_user.id
    ar.review_date = datetime.now(timezone.utc)

    risk_result = await db.execute(
        select(Risk).where(Risk.id == ar.risk_id, Risk.tenant_id == TenantContext.get())
    )
    risk = risk_result.scalar_one_or_none()
    if risk:
        db.add(RiskHistory(
            risk_id=risk.id,
            field_changed="status",
            old_value=risk.status,
            new_value="accepted",
            changed_by=current_user.id,
        ))
        risk.status = "accepted"

    db.add(AuditLog(
        user_id=current_user.id,
        action="acceptance_approved",
        resource_type="acceptance",
        resource_id=ar.id,
        details={"risk_id": str(ar.risk_id)},
        tenant_id=TenantContext.get(),
    ))

    await db.commit()
    return AcceptanceActionResponse(status="approved", acceptance_id=str(ar.id))


@router.post("/{acceptance_id}/reject", response_model=AcceptanceActionResponse)
async def reject_acceptance(
    acceptance_id: str,
    data: AcceptanceAction,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(role_required("ciso")),
):
    result = await db.execute(
        select(AcceptanceRequest).where(
            AcceptanceRequest.id == parse_uuid(acceptance_id, "acceptance_id"),
            AcceptanceRequest.tenant_id == TenantContext.get(),
        )
    )
    ar = result.scalar_one_or_none()
    if not ar:
        raise HTTPException(status_code=404, detail="Acceptance request not found")

    ar.status = "rejected"
    ar.reviewed_by = current_user.id
    ar.review_date = datetime.now(timezone.utc)

    db.add(AuditLog(
        user_id=current_user.id,
        action="acceptance_rejected",
        resource_type="acceptance",
        resource_id=ar.id,
        details={"reason": data.reason},
        tenant_id=TenantContext.get(),
    ))

    await db.commit()
    return AcceptanceActionResponse(status="rejected", acceptance_id=str(ar.id))
