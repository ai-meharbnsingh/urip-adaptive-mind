import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from backend.middleware.auth import get_current_user
from backend.middleware.rbac import role_required
from backend.models.acceptance import AcceptanceRequest
from backend.models.audit_log import AuditLog
from backend.models.risk import Risk, RiskHistory
from backend.models.user import User
from backend.schemas.acceptance import AcceptanceAction, AcceptanceCreate, AcceptanceRead
from backend.services.threat_intel_service import get_apt_for_cve

router = APIRouter()


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


@router.get("")
async def list_acceptance_requests(
    status: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = select(AcceptanceRequest)
    if status:
        query = query.where(AcceptanceRequest.status == status.lower())
    query = query.order_by(AcceptanceRequest.created_at.desc())

    result = await db.execute(query)
    requests = result.scalars().all()

    # Enrich with risk details
    enriched = []
    for a in requests:
        risk_result = await db.execute(select(Risk).where(Risk.id == a.risk_id))
        risk = risk_result.scalar_one_or_none()

        requester_result = await db.execute(select(User).where(User.id == a.requested_by))
        requester = requester_result.scalar_one_or_none()

        enriched.append({
            **acceptance_to_read(a).model_dump(),
            "risk_detail": {
                "risk_id": risk.risk_id if risk else None,
                "finding": risk.finding if risk else None,
                "cvss_score": float(risk.cvss_score) if risk else None,
                "severity": risk.severity if risk else None,
                "asset": risk.asset if risk else None,
                "domain": risk.domain if risk else None,
            } if risk else None,
            "requester_name": requester.full_name if requester else None,
            "requester_team": requester.team if requester else None,
        })

    return enriched


@router.post("")
async def create_acceptance_request(
    data: AcceptanceCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(role_required("it_team")),
):
    # Find risk by risk_id string
    result = await db.execute(select(Risk).where(Risk.risk_id == data.risk_id))
    risk = result.scalar_one_or_none()
    if not risk:
        raise HTTPException(status_code=404, detail="Risk not found")

    # Check if already exists
    existing = await db.execute(
        select(AcceptanceRequest).where(AcceptanceRequest.risk_id == risk.id)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Acceptance request already exists for this risk")

    recommendation = (
        f"Auto-generated: Review compensating controls for {risk.finding}. "
        f"CVSS {risk.cvss_score} ({risk.severity}). Re-review in 90 days."
    )

    # Add APT warning if CVE has known threat actor associations
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
    )
    db.add(ar)

    db.add(AuditLog(
        user_id=current_user.id,
        action="acceptance_requested",
        resource_type="acceptance",
        resource_id=ar.id,
        details={"risk_id": data.risk_id},
    ))

    await db.commit()
    await db.refresh(ar)
    return acceptance_to_read(ar)


@router.post("/{acceptance_id}/approve")
async def approve_acceptance(
    acceptance_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(role_required("ciso")),
):
    result = await db.execute(
        select(AcceptanceRequest).where(AcceptanceRequest.id == uuid.UUID(acceptance_id))
    )
    ar = result.scalar_one_or_none()
    if not ar:
        raise HTTPException(status_code=404, detail="Acceptance request not found")

    ar.status = "approved"
    ar.reviewed_by = current_user.id
    ar.review_date = datetime.now(timezone.utc)

    # Update risk status to accepted
    risk_result = await db.execute(select(Risk).where(Risk.id == ar.risk_id))
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
    ))

    await db.commit()
    return {"status": "approved", "acceptance_id": str(ar.id)}


@router.post("/{acceptance_id}/reject")
async def reject_acceptance(
    acceptance_id: str,
    data: AcceptanceAction,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(role_required("ciso")),
):
    result = await db.execute(
        select(AcceptanceRequest).where(AcceptanceRequest.id == uuid.UUID(acceptance_id))
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
    ))

    await db.commit()
    return {"status": "rejected", "acceptance_id": str(ar.id)}
