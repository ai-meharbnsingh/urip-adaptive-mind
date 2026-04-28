"""
VAPT Vendor Portal — vendor-facing endpoints. P33a §6.5.

All endpoints (except /accept) require a vapt_vendor JWT verified by
backend.middleware.vapt_vendor_auth.require_vapt_vendor.

Endpoints
---------
  POST  /api/vapt-vendor/invitations/accept           — public (token IS the credential)
  GET   /api/vapt-vendor/profile                      — own vendor profile
  POST  /api/vapt-vendor/submissions                  — submit a finding (multipart)
  GET   /api/vapt-vendor/submissions                  — list own submissions
  GET   /api/vapt-vendor/submissions/{id}             — own submission detail
  POST  /api/vapt-vendor/submissions/{id}/retest-response — re-test pass/fail (multipart)
  GET   /api/vapt-vendor/notifications                — re-test requests, etc.

The submission pipeline (POST /submissions) is the load-bearing path: it
delegates to VaptVendorService.submit_finding which auto-creates the URIP
Risk record and fires async EPSS/KEV enrichment, exactly like /api/risks.
"""
from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Request,
    UploadFile,
    status,
)
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from backend.middleware.vapt_vendor_auth import (
    VaptVendorContext,
    log_vapt_vendor_action,
    require_vapt_vendor,
)
from backend.models.audit_log import AuditLog
from backend.models.risk import Risk
from backend.models.vapt_vendor import VaptSubmission, VaptVendor
from backend.routers._upload_guards import read_and_validate_upload
from backend.schemas.vapt_vendor import (
    VaptInvitationAccept,
    VaptInvitationAcceptResponse,
    VaptRetestResponse,
    VaptSubmissionListResponse,
    VaptSubmissionOut,
    VaptVendorNotification,
    VaptVendorNotificationListResponse,
    VaptVendorOut,
    VaptVendorProfile,
)
from backend.services.vapt_vendor_service import VaptVendorService

router = APIRouter()


# Storage root for vendor-uploaded evidence. Override via env var
# URIP_VAPT_EVIDENCE_DIR. Per-tenant subdirs are created on demand.
_DEFAULT_EVIDENCE_DIR = Path(
    os.environ.get("URIP_VAPT_EVIDENCE_DIR", "/tmp/urip_vapt_evidence")
)


def _store_evidence(
    *, tenant_id: uuid.UUID, body: bytes, safe_filename: str
) -> str:
    """
    Persist evidence bytes to the local filesystem under
    ``{evidence_dir}/{tenant_id}/{safe_filename}`` and return a URI string.

    Returns the file:// URI. In a cloud deployment this can be swapped for
    S3/Azure Blob; the rest of the pipeline only knows the URI.
    """
    base = _DEFAULT_EVIDENCE_DIR / str(tenant_id)
    base.mkdir(parents=True, exist_ok=True)
    target = base / safe_filename
    with open(target, "wb") as fh:
        fh.write(body)
    return f"file://{target.resolve()}"


# ---------------------------------------------------------------------------
#  Mappers
# ---------------------------------------------------------------------------

def _vendor_to_out(v: VaptVendor) -> VaptVendorOut:
    return VaptVendorOut(
        id=str(v.id),
        name=v.name,
        contact_email=v.contact_email,
        contact_name=v.contact_name,
        organization=v.organization,
        status=v.status,
        invited_at=v.invited_at,
        last_login_at=v.last_login_at,
    )


async def _submission_to_out(
    s: VaptSubmission, db: AsyncSession
) -> VaptSubmissionOut:
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


# ---------------------------------------------------------------------------
#  Public: invitation accept
# ---------------------------------------------------------------------------

@router.post(
    "/vapt-vendor/invitations/accept",
    response_model=VaptInvitationAcceptResponse,
)
async def accept_vapt_invitation(
    body: VaptInvitationAccept,
    db: AsyncSession = Depends(get_db),
) -> VaptInvitationAcceptResponse:
    """
    Public — exchange an invitation token for a vendor JWT.

    Returns 401 on any failure (we don't distinguish causes to avoid
    leaking info to brute-force probes); 409 on already-redeemed tokens.
    """
    svc = VaptVendorService(db=db)
    result = await svc.accept_invitation(body.token)
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invitation token is invalid or expired.",
        )
    if result == VaptVendorService.ALREADY_ACCEPTED:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Invitation token has already been redeemed.",
        )
    vendor, jwt_token, expires_at = result

    db.add(AuditLog(
        user_id=None,
        action="vapt_invitation_accepted",
        resource_type="vapt_vendor",
        resource_id=vendor.id,
        details={"vendor_email": vendor.contact_email},
        tenant_id=vendor.tenant_id,
    ))
    await db.commit()

    return VaptInvitationAcceptResponse(
        vapt_vendor_jwt=jwt_token,
        expires_at=expires_at,
        vendor=_vendor_to_out(vendor),
    )


# ---------------------------------------------------------------------------
#  Profile
# ---------------------------------------------------------------------------

@router.get("/vapt-vendor/profile", response_model=VaptVendorProfile)
async def get_vapt_vendor_profile(
    db: AsyncSession = Depends(get_db),
    vendor: VaptVendorContext = Depends(require_vapt_vendor),
) -> VaptVendorProfile:
    svc = VaptVendorService(db=db)
    v = await svc.get_active_vendor_by_id(vendor.vendor_id)
    if v is None:
        raise HTTPException(status_code=404, detail="Vendor not found")
    return VaptVendorProfile(
        id=str(v.id),
        name=v.name,
        contact_email=v.contact_email,
        contact_name=v.contact_name,
        organization=v.organization,
        status=v.status,
        tenant_id=str(v.tenant_id),
        invited_at=v.invited_at,
        last_login_at=v.last_login_at,
    )


# ---------------------------------------------------------------------------
#  Submissions
# ---------------------------------------------------------------------------

@router.post(
    "/vapt-vendor/submissions",
    response_model=VaptSubmissionOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_vapt_submission(
    request: Request,
    finding_title: str = Form(...),
    cvss_score: float = Form(...),
    severity: str = Form(...),
    cve_id: Optional[str] = Form(default=None),
    affected_asset_hostname: Optional[str] = Form(default=None),
    affected_asset_ip: Optional[str] = Form(default=None),
    exploit_maturity: Optional[str] = Form(default=None),
    description: Optional[str] = Form(default=None),
    remediation_recommendation: Optional[str] = Form(default=None),
    evidence: Optional[UploadFile] = File(default=None),
    db: AsyncSession = Depends(get_db),
    vendor: VaptVendorContext = Depends(require_vapt_vendor),
) -> VaptSubmissionOut:
    """
    Vendor submits a finding.

    Pipeline:
      1. Validate input (Pydantic-style validation here for free-text fields)
      2. Validate the uploaded evidence file via _upload_guards
      3. Save the file under {evidence_dir}/{tenant_id}/{safe_filename}
      4. Call VaptVendorService.submit_finding which:
            a. Creates VaptSubmission row
            b. Creates a URIP Risk row (composite_score, sla_deadline)
            c. Cross-links submission ↔ risk
            d. Audit log entry
            e. Schedules async enrich_risk (EPSS + KEV + remediation)
      5. Activity log via log_vapt_vendor_action
      6. Commit the transaction (single atomic unit)
    """
    # Pre-validate via the Pydantic-shaped helper (re-uses the same checks)
    from backend.schemas.vapt_vendor import VaptSubmissionCreate
    try:
        validated = VaptSubmissionCreate(
            finding_title=finding_title,
            cve_id=cve_id if cve_id else None,
            cvss_score=cvss_score,
            severity=severity,
            affected_asset_hostname=affected_asset_hostname,
            affected_asset_ip=affected_asset_ip,
            exploit_maturity=exploit_maturity,
            description=description,
            remediation_recommendation=remediation_recommendation,
        )
    except Exception as exc:  # pydantic ValidationError -> 422
        raise HTTPException(status_code=422, detail=str(exc))

    evidence_uri: Optional[str] = None
    evidence_filename: Optional[str] = None
    if evidence is not None and evidence.filename:
        body, safe_name, original = await read_and_validate_upload(evidence)
        evidence_uri = _store_evidence(
            tenant_id=vendor.tenant_id, body=body, safe_filename=safe_name
        )
        evidence_filename = original

    svc = VaptVendorService(db=db)
    # We need the actual VaptVendor row for source labelling
    vendor_row = await svc.get_active_vendor_by_id(vendor.vendor_id)
    if vendor_row is None:
        raise HTTPException(status_code=401, detail="Vendor revoked.")

    created = await svc.submit_finding(
        vendor=vendor_row,
        finding_title=validated.finding_title,
        cvss_score=validated.cvss_score,
        severity=validated.severity,
        cve_id=validated.cve_id,
        affected_asset_hostname=validated.affected_asset_hostname,
        affected_asset_ip=validated.affected_asset_ip,
        exploit_maturity=validated.exploit_maturity,
        description=validated.description,
        remediation_recommendation=validated.remediation_recommendation,
        evidence_storage_uri=evidence_uri,
        evidence_filename=evidence_filename,
    )

    await log_vapt_vendor_action(
        db,
        vendor,
        action="vapt_submission_uploaded",
        target_type="vapt_submission",
        target_id=created.submission.id,
        request=request,
        extra_details={"finding_title": validated.finding_title},
    )

    await db.commit()
    return await _submission_to_out(created.submission, db)


@router.get(
    "/vapt-vendor/submissions", response_model=VaptSubmissionListResponse
)
async def list_my_submissions(
    sub_status: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    vendor: VaptVendorContext = Depends(require_vapt_vendor),
) -> VaptSubmissionListResponse:
    svc = VaptVendorService(db=db)
    rows = await svc.list_vendor_submissions(vendor.vendor_id, status=sub_status)
    items = [await _submission_to_out(s, db) for s in rows]
    return VaptSubmissionListResponse(items=items, total=len(items))


@router.get(
    "/vapt-vendor/submissions/{submission_id}",
    response_model=VaptSubmissionOut,
)
async def get_my_submission(
    submission_id: str,
    db: AsyncSession = Depends(get_db),
    vendor: VaptVendorContext = Depends(require_vapt_vendor),
) -> VaptSubmissionOut:
    try:
        sid = uuid.UUID(submission_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Submission not found")

    svc = VaptVendorService(db=db)
    sub = await svc.get_submission_for_vendor(
        submission_id=sid, vendor_id=vendor.vendor_id
    )
    if sub is None:
        raise HTTPException(status_code=404, detail="Submission not found")
    return await _submission_to_out(sub, db)


@router.post(
    "/vapt-vendor/submissions/{submission_id}/retest-response",
    response_model=VaptSubmissionOut,
)
async def submit_retest_response(
    submission_id: str,
    request: Request,
    result: str = Form(...),
    notes: Optional[str] = Form(default=None),
    evidence: Optional[UploadFile] = File(default=None),
    db: AsyncSession = Depends(get_db),
    vendor: VaptVendorContext = Depends(require_vapt_vendor),
) -> VaptSubmissionOut:
    """
    Vendor uploads a re-test result. Multipart: result + notes + evidence file.
    Pass auto-closes the linked URIP Risk.
    """
    try:
        sid = uuid.UUID(submission_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Submission not found")

    # Validate result up-front
    try:
        validated = VaptRetestResponse(result=result, notes=notes)
    except Exception as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    svc = VaptVendorService(db=db)
    sub = await svc.get_submission_for_vendor(
        submission_id=sid, vendor_id=vendor.vendor_id
    )
    if sub is None:
        raise HTTPException(status_code=404, detail="Submission not found")

    evidence_uri: Optional[str] = None
    if evidence is not None and evidence.filename:
        body, safe_name, _ = await read_and_validate_upload(evidence)
        evidence_uri = _store_evidence(
            tenant_id=vendor.tenant_id, body=body, safe_filename=safe_name
        )

    try:
        updated = await svc.vendor_retest_response(
            submission=sub,
            result=validated.result,
            evidence_uri=evidence_uri,
            notes=validated.notes,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    await log_vapt_vendor_action(
        db,
        vendor,
        action="vapt_retest_submitted",
        target_type="vapt_submission",
        target_id=updated.id,
        request=request,
        extra_details={"result": validated.result},
    )
    await db.commit()
    return await _submission_to_out(updated, db)


# ---------------------------------------------------------------------------
#  Notifications
# ---------------------------------------------------------------------------

@router.get(
    "/vapt-vendor/notifications",
    response_model=VaptVendorNotificationListResponse,
)
async def list_my_notifications(
    db: AsyncSession = Depends(get_db),
    vendor: VaptVendorContext = Depends(require_vapt_vendor),
) -> VaptVendorNotificationListResponse:
    """
    Return submissions awaiting vendor action — currently only
    status='retest_requested'. The vendor's dashboard polls this.
    """
    svc = VaptVendorService(db=db)
    rows = await svc.list_vendor_submissions(
        vendor.vendor_id, status="retest_requested"
    )

    notifications: list[VaptVendorNotification] = []
    for s in rows:
        risk_label: Optional[str] = None
        if s.risk_record_id is not None:
            rr = await db.execute(
                select(Risk.risk_id).where(Risk.id == s.risk_record_id)
            )
            risk_label = rr.scalar_one_or_none()
        notifications.append(VaptVendorNotification(
            submission_id=str(s.id),
            finding_title=s.finding_title,
            risk_id_label=risk_label,
            requested_at=s.retest_requested_at or s.submitted_at,
        ))

    return VaptVendorNotificationListResponse(
        items=notifications, total=len(notifications)
    )
