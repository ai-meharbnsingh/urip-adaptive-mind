"""
VAPT Vendor Portal — admin (tenant CISO/IT) endpoints. P33a §6.5.

These endpoints are URIP-side; they require the existing get_current_user
dependency (regular User JWT). Vendors call /api/vapt-vendor/* (a separate
router) which uses the vapt_vendor JWT.

Endpoints
---------
  POST   /api/vapt-vendors                       — invite vendor
  GET    /api/vapt-vendors                       — list vendors
  GET    /api/vapt-vendors/{id}                  — vendor detail (incl. submission count)
  DELETE /api/vapt-vendors/{id}                  — revoke (suspend)
  GET    /api/vapt-submissions                   — list all tenant submissions
  GET    /api/vapt-submissions/{id}              — single submission detail (admin)
  POST   /api/vapt-submissions/{id}/request-retest — admin requests re-test
  GET    /api/vapt-submissions/{id}/activity     — submission audit history
"""
from __future__ import annotations

import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from backend.middleware.auth import get_current_user
from backend.middleware.rbac import role_required
from backend.middleware.scopes import require_scope
from backend.middleware.tenant import TenantContext
from backend.models.audit_log import AuditLog
from backend.models.risk import Risk
from backend.models.user import User
from backend.models.vapt_vendor import VaptSubmission, VaptVendor
from backend.schemas.vapt_vendor import (
    VaptRetestRequest,
    VaptSubmissionListResponse,
    VaptSubmissionOut,
    VaptVendorInviteCreate,
    VaptVendorListResponse,
    VaptVendorOut,
)
from backend.services.vapt_vendor_service import VaptVendorService


router = APIRouter()


# ---------------------------------------------------------------------------
#  Helpers
# ---------------------------------------------------------------------------

def _vendor_to_out(
    v: VaptVendor,
    *,
    submission_count: Optional[int] = None,
    invitation_url: Optional[str] = None,
) -> VaptVendorOut:
    return VaptVendorOut(
        id=str(v.id),
        name=v.name,
        contact_email=v.contact_email,
        contact_name=v.contact_name,
        organization=v.organization,
        status=v.status,
        invited_at=v.invited_at,
        last_login_at=v.last_login_at,
        submission_count=submission_count,
        invitation_url=invitation_url,
    )


async def _submission_to_out(
    s: VaptSubmission, db: AsyncSession
) -> VaptSubmissionOut:
    """Look up the linked Risk's risk_id (label) lazily so the admin sees
    'RISK-2026-XXXX' instead of an opaque UUID."""
    risk_label: Optional[str] = None
    if s.risk_record_id is not None:
        rr = await db.execute(
            select(Risk.risk_id).where(Risk.id == s.risk_record_id)
        )
        risk_label = rr.scalar_one_or_none()
    return VaptSubmissionOut(
        id=str(s.id),
        vapt_vendor_id=str(s.vapt_vendor_id),
        tenant_id=str(s.tenant_id),
        finding_title=s.finding_title,
        cve_id=s.cve_id,
        cvss_score=float(s.cvss_score),
        severity=s.severity,
        affected_asset_hostname=s.affected_asset_hostname,
        affected_asset_ip=s.affected_asset_ip,
        exploit_maturity=s.exploit_maturity,
        description=s.description,
        remediation_recommendation=s.remediation_recommendation,
        evidence_filename=s.evidence_filename,
        submitted_at=s.submitted_at,
        status=s.status,
        risk_record_id=str(s.risk_record_id) if s.risk_record_id else None,
        risk_id_label=risk_label,
        retest_requested_at=s.retest_requested_at,
        retest_completed_at=s.retest_completed_at,
        retest_result=s.retest_result,
    )


def _build_invitation_url(request: Request, raw_token: str) -> str:
    """Build the vendor portal redemption URL the admin can copy/email."""
    base = str(request.base_url).rstrip("/")
    return f"{base}/vapt-portal-login.html?token={raw_token}"


# ---------------------------------------------------------------------------
#  Vendor management
# ---------------------------------------------------------------------------

@router.post(
    "/vapt-vendors",
    response_model=VaptVendorOut,
    status_code=status.HTTP_201_CREATED,
)
async def invite_vapt_vendor(
    body: VaptVendorInviteCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(role_required("ciso")),
    _scope: User = Depends(require_scope("vapt:write")),
) -> VaptVendorOut:
    """
    Invite a new VAPT vendor. Returns the vendor row + one-shot invitation URL.

    Security notes:
      - role_required("ciso") gates this — only CISOs may invite vendors.
      - The raw token appears only in this 201 response. After this, it is
        gone (only its SHA-256 lives in the DB).
    """
    tenant_id = TenantContext.get()
    svc = VaptVendorService(db=db)

    created = await svc.invite_vendor(
        tenant_id=tenant_id,
        name=body.name,
        contact_email=str(body.contact_email),
        invited_by_user_id=current_user.id,
        contact_name=body.contact_name,
        organization=body.organization,
        ttl_days=body.ttl_days,
    )

    db.add(AuditLog(
        user_id=current_user.id,
        action="vapt_vendor_invited",
        resource_type="vapt_vendor",
        resource_id=created.vendor.id,
        details={
            "name": body.name,
            "contact_email": str(body.contact_email),
            "ttl_days": body.ttl_days,
        },
        tenant_id=tenant_id,
    ))
    await db.commit()
    await db.refresh(created.vendor)

    invitation_url = _build_invitation_url(request, created.raw_token)
    return _vendor_to_out(created.vendor, invitation_url=invitation_url)


@router.get("/vapt-vendors", response_model=VaptVendorListResponse)
async def list_vapt_vendors(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    only_active: bool = False,
    _scope: User = Depends(require_scope("vapt:read")),
) -> VaptVendorListResponse:
    """List vendors registered for this tenant (CISO + IT can read)."""
    tenant_id = TenantContext.get()
    svc = VaptVendorService(db=db)
    vendors = await svc.list_tenant_vendors(tenant_id, only_active=only_active)

    # Submission counts in one query
    counts: dict[uuid.UUID, int] = {}
    if vendors:
        result = await db.execute(
            select(
                VaptSubmission.vapt_vendor_id, func.count(VaptSubmission.id)
            )
            .where(VaptSubmission.tenant_id == tenant_id)
            .group_by(VaptSubmission.vapt_vendor_id)
        )
        for row in result.all():
            counts[row[0]] = int(row[1])

    items = [
        _vendor_to_out(v, submission_count=counts.get(v.id, 0))
        for v in vendors
    ]
    return VaptVendorListResponse(items=items, total=len(items))


@router.get("/vapt-vendors/{vendor_id}", response_model=VaptVendorOut)
async def get_vapt_vendor(
    vendor_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _scope: User = Depends(require_scope("vapt:read")),
) -> VaptVendorOut:
    tenant_id = TenantContext.get()
    try:
        vid = uuid.UUID(vendor_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Vendor not found")

    svc = VaptVendorService(db=db)
    vendor = await svc.get_vendor(vid, tenant_id)
    if vendor is None:
        raise HTTPException(status_code=404, detail="Vendor not found")

    count_result = await db.execute(
        select(func.count(VaptSubmission.id)).where(
            VaptSubmission.vapt_vendor_id == vid
        )
    )
    count = int(count_result.scalar() or 0)
    return _vendor_to_out(vendor, submission_count=count)


@router.delete(
    "/vapt-vendors/{vendor_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_model=None,
)
async def revoke_vapt_vendor(
    vendor_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(role_required("ciso")),
    _scope: User = Depends(require_scope("vapt:write")),
) -> None:
    """Suspend a vendor; their JWT will fail on next request."""
    tenant_id = TenantContext.get()
    try:
        vid = uuid.UUID(vendor_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Vendor not found")

    svc = VaptVendorService(db=db)
    ok = await svc.revoke_vendor(vid, tenant_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Vendor not found")

    db.add(AuditLog(
        user_id=current_user.id,
        action="vapt_vendor_revoked",
        resource_type="vapt_vendor",
        resource_id=vid,
        details={},
        tenant_id=tenant_id,
    ))
    await db.commit()


# ---------------------------------------------------------------------------
#  Submission management (admin)
# ---------------------------------------------------------------------------

@router.get("/vapt-submissions", response_model=VaptSubmissionListResponse)
async def list_vapt_submissions_admin(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    sub_status: Optional[str] = None,
    _scope: User = Depends(require_scope("vapt:read")),
) -> VaptSubmissionListResponse:
    """All submissions across the tenant (CISO + IT view)."""
    tenant_id = TenantContext.get()
    svc = VaptVendorService(db=db)
    rows = await svc.list_tenant_submissions(tenant_id, status=sub_status)
    items = [await _submission_to_out(s, db) for s in rows]
    return VaptSubmissionListResponse(items=items, total=len(items))


@router.get(
    "/vapt-submissions/{submission_id}", response_model=VaptSubmissionOut
)
async def get_vapt_submission_admin(
    submission_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _scope: User = Depends(require_scope("vapt:read")),
) -> VaptSubmissionOut:
    tenant_id = TenantContext.get()
    try:
        sid = uuid.UUID(submission_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Submission not found")
    svc = VaptVendorService(db=db)
    sub = await svc.get_submission_for_tenant(
        submission_id=sid, tenant_id=tenant_id
    )
    if sub is None:
        raise HTTPException(status_code=404, detail="Submission not found")
    return await _submission_to_out(sub, db)


@router.post(
    "/vapt-submissions/{submission_id}/request-retest",
    response_model=VaptSubmissionOut,
)
async def request_vapt_retest(
    submission_id: str,
    body: VaptRetestRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(role_required("it_team")),
    _scope: User = Depends(require_scope("vapt:write")),
) -> VaptSubmissionOut:
    """
    IT team has fixed the underlying risk and asks the vendor to verify.
    Persists status='retest_requested' + retest_requested_at.
    """
    tenant_id = TenantContext.get()
    try:
        sid = uuid.UUID(submission_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Submission not found")

    svc = VaptVendorService(db=db)
    try:
        sub = await svc.request_retest(
            submission_id=sid,
            tenant_id=tenant_id,
            requested_by_user_id=current_user.id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    if sub is None:
        raise HTTPException(status_code=404, detail="Submission not found")

    if body.note:
        # Stash the note in the audit log (we don't have a notes column on
        # the submission; the admin's text is metadata, not the canonical
        # finding).
        db.add(AuditLog(
            user_id=current_user.id,
            action="vapt_retest_note",
            resource_type="vapt_submission",
            resource_id=sub.id,
            details={"note": body.note},
            tenant_id=tenant_id,
        ))

    await db.commit()
    return await _submission_to_out(sub, db)


@router.get("/vapt-submissions/{submission_id}/activity")
async def get_vapt_submission_activity(
    submission_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _scope: User = Depends(require_scope("vapt:read")),
) -> dict:
    """Return audit log rows touching this submission (newest first)."""
    tenant_id = TenantContext.get()
    try:
        sid = uuid.UUID(submission_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Submission not found")

    svc = VaptVendorService(db=db)
    sub = await svc.get_submission_for_tenant(
        submission_id=sid, tenant_id=tenant_id
    )
    if sub is None:
        raise HTTPException(status_code=404, detail="Submission not found")

    result = await db.execute(
        select(AuditLog)
        .where(
            AuditLog.resource_type == "vapt_submission",
            AuditLog.resource_id == sid,
            AuditLog.tenant_id == tenant_id,
        )
        .order_by(AuditLog.created_at.desc())
    )
    rows = result.scalars().all()
    return {
        "submission_id": submission_id,
        "items": [
            {
                "action": r.action,
                "details": r.details,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in rows
        ],
    }
