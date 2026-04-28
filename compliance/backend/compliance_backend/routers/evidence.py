"""
Evidence API — P2B.4.

Endpoints:
  POST /evidence                                    — manual upload (multipart)
  GET  /evidence                                    — search / list (paginated)
  GET  /evidence/{id}                               — download single evidence content
  GET  /evidence/bundle?framework_id=X&audit_period=Y — download ZIP bundle

All endpoints require authentication. Tenant isolation enforced on every query.
"""
from typing import Optional

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    UploadFile,
    status,
)
from fastapi.responses import Response, StreamingResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from compliance_backend.database import get_async_session
from compliance_backend.middleware.auth import require_auth
from compliance_backend.middleware.tenant import require_tenant
from compliance_backend.routers._upload_guards import read_and_validate_upload
from compliance_backend.services.audit_writer import write_audit
from compliance_backend.services.evidence_service import EvidenceService

router = APIRouter(prefix="/evidence", tags=["evidence"])

VALID_EVIDENCE_TYPES = {"screenshot", "config", "log", "ticket", "document"}


# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------

class EvidenceOut(BaseModel):
    """
    Evidence response shape.

    L2 (CL-NEW-2): ``storage_uri`` is intentionally NOT exposed on the wire —
    deployment topology (file:// path, s3:// bucket name, internal mount points)
    is a deployment detail, not part of the API contract. Tests that need to
    verify storage-layer properties (filename sanitisation, byte persistence,
    UUID-prefix collision avoidance) must query the ``Evidence`` model row
    directly via the test ``db_session`` and read ``record.storage_uri`` from
    the DB — not from this response.
    """
    id: str
    control_id: str
    framework_id: Optional[str]
    tenant_id: str
    type: str
    audit_period: str
    captured_at: str
    captured_by: str
    metadata_json: Optional[dict]

    model_config = {"from_attributes": True}


class PaginatedEvidence(BaseModel):
    items: list[EvidenceOut]
    total: int
    page: int
    limit: int
    pages: int


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _ev_out(ev) -> EvidenceOut:
    return EvidenceOut(
        id=ev.id,
        control_id=ev.control_id,
        framework_id=ev.framework_id,
        tenant_id=ev.tenant_id,
        type=ev.type,
        audit_period=ev.audit_period,
        captured_at=ev.captured_at.isoformat(),
        captured_by=ev.captured_by,
        metadata_json=ev.metadata_json,
    )


# ---------------------------------------------------------------------------
# Endpoints — ORDER MATTERS: /bundle must be declared before /{id} so FastAPI
# doesn't try to match "bundle" as an evidence ID.
# ---------------------------------------------------------------------------

@router.get("/bundle")
async def download_bundle(
    framework_id: Optional[str] = Query(None),
    audit_period: Optional[str] = Query(None),
    tenant_id: str = Depends(require_tenant),
    session: AsyncSession = Depends(get_async_session),
) -> Response:
    """
    Download a ZIP bundle of all evidence for the tenant.

    Optionally filtered by framework_id and/or audit_period.
    Suitable for auditor handoff — bundle includes manifest.json.
    """
    svc = EvidenceService(db=session)
    bundle_bytes = await svc.export_evidence_bundle(
        tenant_id=tenant_id,
        framework_id=framework_id,
        audit_period=audit_period,
    )
    filename_parts = ["evidence_bundle"]
    if framework_id:
        filename_parts.append(framework_id)
    if audit_period:
        filename_parts.append(audit_period)
    filename = "_".join(filename_parts) + ".zip"

    return Response(
        content=bundle_bytes,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("", response_model=EvidenceOut, status_code=status.HTTP_201_CREATED)
async def upload_evidence(
    file: UploadFile = File(...),
    control_id: str = Form(...),
    evidence_type: str = Form(...),
    framework_id: Optional[str] = Form(None),
    audit_period: Optional[str] = Form(None),
    claims: dict = Depends(require_auth),
    tenant_id: str = Depends(require_tenant),
    session: AsyncSession = Depends(get_async_session),
) -> EvidenceOut:
    """
    Manual evidence upload (multipart/form-data).

    evidence_type must be one of: screenshot, config, log, ticket, document
    """
    if evidence_type not in VALID_EVIDENCE_TYPES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"evidence_type must be one of {sorted(VALID_EVIDENCE_TYPES)}",
        )

    # HIGH-011 — size cap, content-type allowlist, filename sanitisation
    content, safe_filename, _original_filename = await read_and_validate_upload(file)

    svc = EvidenceService(db=session)
    record = await svc.upload_manual_evidence(
        file_content=content,
        filename=safe_filename,
        control_id=control_id,
        tenant_id=tenant_id,
        evidence_type=evidence_type,
        framework_id=framework_id,
        audit_period=audit_period,
        uploaded_by=tenant_id,  # simplified: use tenant_id; real impl uses user_id from JWT
    )
    await write_audit(
        session,
        tenant_id=tenant_id,
        user_id=claims.get("sub", "unknown"),
        action="evidence_uploaded",
        resource_type="evidence",
        resource_id=record.id,
        details={
            "control_id": control_id,
            "evidence_type": evidence_type,
            "framework_id": framework_id,
            "filename": safe_filename,
            "size_bytes": len(content),
        },
    )
    await session.commit()
    return _ev_out(record)


@router.get("", response_model=PaginatedEvidence)
async def search_evidence(
    control_id: Optional[str] = Query(None),
    framework_id: Optional[str] = Query(None),
    evidence_type: Optional[str] = Query(None, alias="type"),
    audit_period: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    tenant_id: str = Depends(require_tenant),
    session: AsyncSession = Depends(get_async_session),
) -> PaginatedEvidence:
    """
    Search evidence for the authenticated tenant.

    All filters are optional. Results ordered by captured_at descending.
    """
    svc = EvidenceService(db=session)
    result = await svc.search_evidence(
        tenant_id=tenant_id,
        control_id=control_id,
        framework_id=framework_id,
        evidence_type=evidence_type,
        audit_period=audit_period,
        page=page,
        limit=limit,
    )
    return PaginatedEvidence(
        items=[_ev_out(ev) for ev in result["items"]],
        total=result["total"],
        page=result["page"],
        limit=result["limit"],
        pages=result["pages"],
    )


@router.get("/{evidence_id}")
async def download_evidence(
    evidence_id: str,
    tenant_id: str = Depends(require_tenant),
    session: AsyncSession = Depends(get_async_session),
) -> Response:
    """
    Download a single evidence artifact by ID.

    Returns raw bytes with appropriate Content-Type.
    Enforces tenant isolation.
    """
    svc = EvidenceService(db=session)
    record = await svc.get_evidence(evidence_id, tenant_id)
    if record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Evidence '{evidence_id}' not found.",
        )

    try:
        content = await svc.get_evidence_content(evidence_id, tenant_id)
    except FileNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Evidence artifact for '{evidence_id}' is missing from storage.",
        )
    except Exception as exc:
        # L3 (CL-NEW-3) — surface tamper events to the tenant as 409, not 500.
        # auditor.py already does this; tenant-side was missing.  Importing
        # inside the handler avoids a top-level cycle.
        from compliance_backend.services.evidence_service import EvidenceTamperError

        if isinstance(exc, EvidenceTamperError):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "Evidence integrity check failed — on-disk artifact does "
                    "not match the recorded hash. Notify the tenant admin."
                ),
            )
        raise

    # Guess content type from evidence type
    content_type_map = {
        "screenshot": "image/png",
        "config": "application/json",
        "log": "text/plain",
        "ticket": "application/json",
        "document": "application/octet-stream",
    }
    media_type = content_type_map.get(record.type, "application/octet-stream")

    return Response(
        content=content,
        media_type=media_type,
        headers={
            # X-Content-Type-Options nosniff (LOW-002 hardening) — prevents
            # client-side MIME sniffing tricks even though Content-Disposition
            # forces attachment download.
            "X-Content-Type-Options": "nosniff",
            "Content-Disposition": (
                f'attachment; filename="evidence_{evidence_id}_{record.type}.bin"'
            ),
        },
    )
