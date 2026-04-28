"""
Admin view of evidence requests — P2B.10.

Tenant admins use this to see what evidence their auditors have asked for and
to mark requests as fulfilled.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from compliance_backend.database import get_async_session
from compliance_backend.middleware.auth import require_auth
from compliance_backend.middleware.tenant import require_tenant
from compliance_backend.models.auditor import AuditorAccess, EvidenceRequest
from compliance_backend.services.audit_writer import write_audit

router = APIRouter(prefix="/admin/evidence-requests", tags=["admin"])


class EvidenceRequestAdminOut(BaseModel):
    id: str
    auditor_access_id: str
    auditor_email: str
    control_id: Optional[str]
    description: str
    requested_at: str
    fulfilled_at: Optional[str]
    fulfillment_evidence_id: Optional[str]
    fulfilled_by_user_id: Optional[str]


class FulfilRequest(BaseModel):
    evidence_id: str = Field(..., min_length=1)


def _require_admin(claims: dict) -> None:
    # CRIT-008 — see compliance_backend.middleware.auth.require_compliance_admin
    from compliance_backend.middleware.auth import require_compliance_admin

    require_compliance_admin(claims)


@router.get("", response_model=List[EvidenceRequestAdminOut])
async def list_requests(
    fulfilled: Optional[bool] = Query(None),
    claims: dict = Depends(require_auth),
    tenant_id: str = Depends(require_tenant),
    session: AsyncSession = Depends(get_async_session),
) -> List[EvidenceRequestAdminOut]:
    _require_admin(claims)
    # Join to AuditorAccess so we can filter by tenant
    rows = (await session.execute(
        select(EvidenceRequest, AuditorAccess)
        .join(AuditorAccess, AuditorAccess.id == EvidenceRequest.auditor_access_id)
        .where(AuditorAccess.tenant_id == tenant_id)
        .order_by(EvidenceRequest.requested_at.desc())
    )).all()

    out: List[EvidenceRequestAdminOut] = []
    for req, access in rows:
        if fulfilled is True and req.fulfilled_at is None:
            continue
        if fulfilled is False and req.fulfilled_at is not None:
            continue
        out.append(EvidenceRequestAdminOut(
            id=req.id,
            auditor_access_id=req.auditor_access_id,
            auditor_email=access.auditor_email,
            control_id=req.control_id,
            description=req.description,
            requested_at=req.requested_at.isoformat(),
            fulfilled_at=req.fulfilled_at.isoformat() if req.fulfilled_at else None,
            fulfillment_evidence_id=req.fulfillment_evidence_id,
            fulfilled_by_user_id=req.fulfilled_by_user_id,
        ))
    return out


@router.post("/{request_id}/fulfil", response_model=EvidenceRequestAdminOut)
async def fulfil_request(
    request_id: str,
    body: FulfilRequest,
    claims: dict = Depends(require_auth),
    tenant_id: str = Depends(require_tenant),
    session: AsyncSession = Depends(get_async_session),
) -> EvidenceRequestAdminOut:
    _require_admin(claims)
    # Look up request joined to access for tenant scoping
    row = (await session.execute(
        select(EvidenceRequest, AuditorAccess)
        .join(AuditorAccess, AuditorAccess.id == EvidenceRequest.auditor_access_id)
        .where(
            and_(
                EvidenceRequest.id == request_id,
                AuditorAccess.tenant_id == tenant_id,
            )
        )
    )).first()
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Evidence request not found.",
        )
    req, access = row
    # NEW-2 — naive UTC (matches DB column convention).
    req.fulfilled_at = datetime.now(timezone.utc).replace(tzinfo=None)
    req.fulfilled_by_user_id = claims.get("sub", "unknown")
    req.fulfillment_evidence_id = body.evidence_id
    await write_audit(
        session,
        tenant_id=tenant_id,
        user_id=claims.get("sub", "unknown"),
        action="evidence_request_fulfilled",
        resource_type="evidence_request",
        resource_id=req.id,
        details={"evidence_id": body.evidence_id},
    )
    await session.commit()

    return EvidenceRequestAdminOut(
        id=req.id,
        auditor_access_id=req.auditor_access_id,
        auditor_email=access.auditor_email,
        control_id=req.control_id,
        description=req.description,
        requested_at=req.requested_at.isoformat(),
        fulfilled_at=req.fulfilled_at.isoformat(),
        fulfillment_evidence_id=req.fulfillment_evidence_id,
        fulfilled_by_user_id=req.fulfilled_by_user_id,
    )
