"""
Vendor / Third-Party Risk API — P2B.7

All endpoints require auth + tenant context.
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Optional, List

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Query,
    status,
    UploadFile,
    File,
    Form,
)
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from compliance_backend.database import get_async_session
from compliance_backend.middleware.auth import require_auth
from compliance_backend.middleware.tenant import require_tenant
from compliance_backend.models.vendor import Vendor, VendorQuestionnaire, VendorDocument, VendorRiskScore
from compliance_backend.routers._upload_guards import read_and_validate_upload
from compliance_backend.services.audit_writer import write_audit
from compliance_backend.services.vendor_risk import (
    register_vendor,
    send_questionnaire,
    record_response,
    upload_document,
    calculate_risk_score,
    list_expiring_documents,
)


router = APIRouter(prefix="/vendors", tags=["vendors"])


class VendorCreateIn(BaseModel):
    name: str
    criticality: str = Field(..., description="low|medium|high|critical")
    contact_email: Optional[str] = None
    contact_name: Optional[str] = None


class VendorUpdateIn(BaseModel):
    name: Optional[str] = None
    criticality: Optional[str] = None
    contact_email: Optional[str] = None
    contact_name: Optional[str] = None
    status: Optional[str] = None
    next_review_at: Optional[date] = None


class VendorOut(BaseModel):
    id: str
    tenant_id: str
    name: str
    criticality: str
    contact_email: Optional[str]
    contact_name: Optional[str]
    status: str
    onboarded_at: datetime
    next_review_at: date

    model_config = {"from_attributes": True}


class QuestionnaireCreateIn(BaseModel):
    template_name: str


class QuestionnaireRespondIn(BaseModel):
    responses: dict


class VendorQuestionnaireOut(BaseModel):
    id: str
    vendor_id: str
    template_name: str
    sent_at: datetime
    due_at: Optional[date]
    status: str
    responses_json: Optional[dict]

    model_config = {"from_attributes": True}


class VendorDocumentOut(BaseModel):
    """
    Vendor document response shape.

    L2 (CL-NEW-2): ``storage_uri`` is intentionally NOT exposed on the wire.
    Tests that need to verify storage-layer properties (filename sanitisation,
    byte persistence) must query the ``VendorDocument`` model row directly via
    the test ``db_session`` and read ``record.storage_uri`` from the DB — not
    from this response.
    """
    id: str
    vendor_id: str
    document_type: str
    filename: str
    valid_from: Optional[date]
    valid_until: Optional[date]
    uploaded_at: datetime
    uploaded_by_user_id: str

    model_config = {"from_attributes": True}


class VendorRiskScoreOut(BaseModel):
    id: str
    vendor_id: str
    score: int
    calculated_at: datetime
    factors_json: Optional[dict]

    model_config = {"from_attributes": True}


class ExpiringDocItemOut(BaseModel):
    document: VendorDocumentOut
    vendor_name: str
    priority: str


def _not_found() -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Vendor not found")


@router.get("/expiring-documents", response_model=List[ExpiringDocItemOut])
async def expiring_documents(
    days: int = Query(60, ge=1, le=365),
    session: AsyncSession = Depends(get_async_session),
    tenant_id: str = Depends(require_tenant),
) -> List[ExpiringDocItemOut]:
    items = await list_expiring_documents(session, tenant_id=tenant_id, days_ahead=days)
    return [
        ExpiringDocItemOut(
            document=VendorDocumentOut.model_validate(i["document"]),
            vendor_name=i["vendor_name"],
            priority=i["priority"],
        )
        for i in items
    ]


@router.post("", response_model=VendorOut)
async def create_vendor(
    payload: VendorCreateIn,
    session: AsyncSession = Depends(get_async_session),
    claims: dict = Depends(require_auth),
    tenant_id: str = Depends(require_tenant),
) -> VendorOut:
    vendor = await register_vendor(
        session,
        tenant_id=tenant_id,
        name=payload.name,
        criticality=payload.criticality,
        contact={"email": payload.contact_email, "name": payload.contact_name},
    )
    # Audit row staged in the same transaction as the vendor row — atomic.
    await write_audit(
        session,
        tenant_id=tenant_id,
        user_id=claims.get("sub", "unknown"),
        action="vendor_created",
        resource_type="vendor",
        resource_id=vendor.id,
        details={
            "name": payload.name,
            "criticality": payload.criticality,
        },
    )
    await session.commit()
    return VendorOut.model_validate(vendor)


@router.get("", response_model=List[VendorOut])
async def list_vendors(
    criticality: Optional[str] = Query(None),
    status_filter: Optional[str] = Query(None, alias="status"),
    session: AsyncSession = Depends(get_async_session),
    tenant_id: str = Depends(require_tenant),
) -> List[VendorOut]:
    q = select(Vendor).where(Vendor.tenant_id == tenant_id)
    if criticality:
        q = q.where(Vendor.criticality == criticality)
    if status_filter:
        q = q.where(Vendor.status == status_filter)
    vendors = (await session.execute(q.order_by(Vendor.name.asc()))).scalars().all()
    return [VendorOut.model_validate(v) for v in vendors]


@router.get("/{vendor_id}", response_model=VendorOut)
async def get_vendor(
    vendor_id: str,
    session: AsyncSession = Depends(get_async_session),
    tenant_id: str = Depends(require_tenant),
) -> VendorOut:
    v = (
        await session.execute(
            select(Vendor).where(Vendor.id == vendor_id, Vendor.tenant_id == tenant_id)
        )
    ).scalars().first()
    if not v:
        raise _not_found()
    return VendorOut.model_validate(v)


@router.patch("/{vendor_id}", response_model=VendorOut)
async def update_vendor(
    vendor_id: str,
    payload: VendorUpdateIn,
    session: AsyncSession = Depends(get_async_session),
    claims: dict = Depends(require_auth),
    tenant_id: str = Depends(require_tenant),
) -> VendorOut:
    v = (
        await session.execute(
            select(Vendor).where(Vendor.id == vendor_id, Vendor.tenant_id == tenant_id)
        )
    ).scalars().first()
    if not v:
        raise _not_found()

    changes = payload.model_dump(exclude_unset=True)
    for field, value in changes.items():
        setattr(v, field, value)

    await write_audit(
        session,
        tenant_id=tenant_id,
        user_id=claims.get("sub", "unknown"),
        action="vendor_updated",
        resource_type="vendor",
        resource_id=vendor_id,
        details={"changes": payload.model_dump(exclude_unset=True, mode="json")},
    )
    await session.commit()
    return VendorOut.model_validate(v)


@router.post("/{vendor_id}/questionnaires", response_model=VendorQuestionnaireOut)
async def create_questionnaire(
    vendor_id: str,
    payload: QuestionnaireCreateIn,
    session: AsyncSession = Depends(get_async_session),
    claims: dict = Depends(require_auth),
    tenant_id: str = Depends(require_tenant),
) -> VendorQuestionnaireOut:
    v = (
        await session.execute(
            select(Vendor).where(Vendor.id == vendor_id, Vendor.tenant_id == tenant_id)
        )
    ).scalars().first()
    if not v:
        raise _not_found()

    q = await send_questionnaire(session, vendor_id=vendor_id, template_name=payload.template_name)
    await write_audit(
        session,
        tenant_id=tenant_id,
        user_id=claims.get("sub", "unknown"),
        action="vendor_questionnaire_sent",
        resource_type="vendor_questionnaire",
        resource_id=q.id,
        details={"vendor_id": vendor_id, "template_name": payload.template_name},
    )
    await session.commit()
    return VendorQuestionnaireOut.model_validate(q)


@router.post("/{vendor_id}/questionnaires/{q_id}/respond", response_model=VendorQuestionnaireOut)
async def respond_questionnaire(
    vendor_id: str,
    q_id: str,
    payload: QuestionnaireRespondIn,
    session: AsyncSession = Depends(get_async_session),
    tenant_id: str = Depends(require_tenant),
) -> VendorQuestionnaireOut:
    # Enforce tenant + vendor ownership for questionnaire
    v = (
        await session.execute(
            select(Vendor).where(Vendor.id == vendor_id, Vendor.tenant_id == tenant_id)
        )
    ).scalars().first()
    if not v:
        raise _not_found()

    q = (
        await session.execute(
            select(VendorQuestionnaire).where(
                VendorQuestionnaire.id == q_id,
                VendorQuestionnaire.vendor_id == vendor_id,
            )
        )
    ).scalars().first()
    if not q:
        raise HTTPException(status_code=404, detail="Questionnaire not found")

    updated = await record_response(session, questionnaire_id=q_id, responses=payload.responses)
    # NB: claims is not yet a dependency on this endpoint — keep audit minimal
    # using vendor's tenant context which is authoritative.
    await session.commit()
    return VendorQuestionnaireOut.model_validate(updated)


@router.post("/{vendor_id}/documents", response_model=VendorDocumentOut)
async def upload_vendor_document(
    vendor_id: str,
    document_type: str = Form(...),
    valid_until: Optional[date] = Form(None),
    file: UploadFile = File(...),
    session: AsyncSession = Depends(get_async_session),
    claims: dict = Depends(require_auth),
    tenant_id: str = Depends(require_tenant),
) -> VendorDocumentOut:
    v = (
        await session.execute(
            select(Vendor).where(Vendor.id == vendor_id, Vendor.tenant_id == tenant_id)
        )
    ).scalars().first()
    if not v:
        raise _not_found()

    # HIGH-011 — size cap, content-type allowlist, filename sanitisation.
    content, safe_filename, _original = await read_and_validate_upload(file)

    # HIGH-002 fix: pass the actual content bytes through to the service so
    # they get persisted via the storage backend.  Previously the route
    # forwarded a fully-consumed UploadFile and the service silently wrote
    # a memory:// placeholder.
    doc = await upload_document(
        session,
        vendor_id=vendor_id,
        doc_type=document_type,
        file={"filename": safe_filename, "content": content},
        valid_until=valid_until,
        uploaded_by_user_id=claims.get("sub") or "unknown",
    )
    await write_audit(
        session,
        tenant_id=tenant_id,
        user_id=claims.get("sub", "unknown"),
        action="vendor_document_uploaded",
        resource_type="vendor_document",
        resource_id=doc.id,
        details={
            "vendor_id": vendor_id,
            "document_type": document_type,
            "filename": safe_filename,
            "size_bytes": len(content),
        },
    )
    await session.commit()
    return VendorDocumentOut.model_validate(doc)


@router.get("/{vendor_id}/documents", response_model=List[VendorDocumentOut])
async def list_vendor_documents(
    vendor_id: str,
    session: AsyncSession = Depends(get_async_session),
    tenant_id: str = Depends(require_tenant),
) -> List[VendorDocumentOut]:
    v = (
        await session.execute(
            select(Vendor).where(Vendor.id == vendor_id, Vendor.tenant_id == tenant_id)
        )
    ).scalars().first()
    if not v:
        raise _not_found()

    docs = (
        await session.execute(
            select(VendorDocument).where(VendorDocument.vendor_id == vendor_id).order_by(
                VendorDocument.uploaded_at.desc()
            )
        )
    ).scalars().all()
    return [VendorDocumentOut.model_validate(d) for d in docs]


@router.post("/{vendor_id}/calculate-score", response_model=VendorRiskScoreOut)
async def recompute_score(
    vendor_id: str,
    session: AsyncSession = Depends(get_async_session),
    claims: dict = Depends(require_auth),
    tenant_id: str = Depends(require_tenant),
) -> VendorRiskScoreOut:
    v = (
        await session.execute(
            select(Vendor).where(Vendor.id == vendor_id, Vendor.tenant_id == tenant_id)
        )
    ).scalars().first()
    if not v:
        raise _not_found()

    score = await calculate_risk_score(session, vendor_id=vendor_id)
    await write_audit(
        session,
        tenant_id=tenant_id,
        user_id=claims.get("sub", "unknown"),
        action="vendor_risk_score_recomputed",
        resource_type="vendor_risk_score",
        resource_id=score.id,
        details={"vendor_id": vendor_id, "score": score.score},
    )
    await session.commit()
    return VendorRiskScoreOut.model_validate(score)


@router.get("/{vendor_id}/score", response_model=VendorRiskScoreOut)
async def get_current_score(
    vendor_id: str,
    session: AsyncSession = Depends(get_async_session),
    tenant_id: str = Depends(require_tenant),
) -> VendorRiskScoreOut:
    v = (
        await session.execute(
            select(Vendor).where(Vendor.id == vendor_id, Vendor.tenant_id == tenant_id)
        )
    ).scalars().first()
    if not v:
        raise _not_found()

    score = (
        await session.execute(
            select(VendorRiskScore)
            .where(VendorRiskScore.vendor_id == vendor_id)
            .order_by(VendorRiskScore.calculated_at.desc())
            .limit(1)
        )
    ).scalars().first()
    if not score:
        raise HTTPException(status_code=404, detail="No risk score computed yet")
    return VendorRiskScoreOut.model_validate(score)
