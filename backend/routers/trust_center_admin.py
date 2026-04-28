"""
trust_center_admin — admin endpoints (auth required).

Tenant admins manage their published documents and review access requests.
All endpoints scope by `current_user.tenant_id` so two tenants can't see each
other's docs/requests even by guessing UUIDs.
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from backend.middleware.auth import get_current_user
from backend.models.audit_log import AuditLog
from backend.models.trust_center import (
    DOC_TYPE_VALUES,
    TrustCenterAccessRequest,
    TrustCenterDocument,
)
from backend.models.user import User
from backend.services.trust_center_service import (
    approve_access,
    deny_access,
    publish_document,
)

router = APIRouter()


# --------------------------------------------------------------------------- #
class PublishDocRequest(BaseModel):
    doc_type: str
    title: str = Field(min_length=1, max_length=255)
    description: str | None = None
    file_storage_uri: str = Field(min_length=1, max_length=1024)
    valid_until: datetime | None = None
    requires_nda: bool = True
    is_published: bool = True


class DocumentOut(BaseModel):
    id: str
    doc_type: str
    title: str
    description: str | None
    file_storage_uri: str
    valid_until: datetime | None
    is_published: bool
    requires_nda: bool

    @classmethod
    def from_model(cls, d: TrustCenterDocument) -> "DocumentOut":
        return cls(
            id=str(d.id),
            doc_type=d.doc_type,
            title=d.title,
            description=d.description,
            file_storage_uri=d.file_storage_uri,
            valid_until=d.valid_until,
            is_published=d.is_published,
            requires_nda=d.requires_nda,
        )


class AccessRequestOut(BaseModel):
    id: str
    requesting_doc_id: str
    requester_email: str
    requester_company: str | None
    status: str
    nda_signed_at: datetime | None
    granted_at: datetime | None
    expires_at: datetime | None
    download_count: int

    @classmethod
    def from_model(cls, r: TrustCenterAccessRequest) -> "AccessRequestOut":
        return cls(
            id=str(r.id),
            requesting_doc_id=str(r.requesting_doc_id),
            requester_email=r.requester_email,
            requester_company=r.requester_company,
            status=r.status,
            nda_signed_at=r.nda_signed_at,
            granted_at=r.granted_at,
            expires_at=r.expires_at,
            download_count=int(r.download_count or 0),
        )


class ApprovedAccessOut(BaseModel):
    request: AccessRequestOut
    # Plaintext token — ONLY shown on this response, never persisted.
    access_token: str


# --------------------------------------------------------------------------- #
def _require_tenant_admin(user: User) -> uuid.UUID:
    if user.role not in ("ciso", "admin", "tenant_admin", "super_admin"):
        raise HTTPException(status_code=403, detail="Trust Center admin role required")
    if user.tenant_id is None:
        raise HTTPException(status_code=400, detail="User has no tenant scope")
    return user.tenant_id


# --------------------------------------------------------------------------- #
# Documents
# --------------------------------------------------------------------------- #
@router.post("/documents", response_model=DocumentOut)
async def create_document(
    payload: PublishDocRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> DocumentOut:
    tenant_id = _require_tenant_admin(user)
    if payload.doc_type not in DOC_TYPE_VALUES:
        raise HTTPException(status_code=400, detail=f"Invalid doc_type {payload.doc_type!r}")
    doc = await publish_document(
        db,
        tenant_id,
        doc_type=payload.doc_type,
        title=payload.title,
        description=payload.description,
        file_storage_uri=payload.file_storage_uri,
        valid_until=payload.valid_until,
        requires_nda=payload.requires_nda,
        is_published=payload.is_published,
    )
    await db.commit()
    return DocumentOut.from_model(doc)


@router.get("/documents", response_model=list[DocumentOut])
async def list_documents(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[DocumentOut]:
    tenant_id = _require_tenant_admin(user)
    q = await db.execute(
        select(TrustCenterDocument).where(TrustCenterDocument.tenant_id == tenant_id)
    )
    return [DocumentOut.from_model(d) for d in q.scalars().all()]


@router.patch("/documents/{doc_id}", response_model=DocumentOut)
async def update_document(
    doc_id: uuid.UUID,
    payload: dict[str, Any],
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> DocumentOut:
    tenant_id = _require_tenant_admin(user)
    q = await db.execute(
        select(TrustCenterDocument).where(
            TrustCenterDocument.id == doc_id,
            TrustCenterDocument.tenant_id == tenant_id,
        )
    )
    doc = q.scalar_one_or_none()
    if doc is None:
        raise HTTPException(status_code=404, detail="Document not found")
    for field in ("title", "description", "is_published", "requires_nda", "valid_until"):
        if field in payload:
            setattr(doc, field, payload[field])
    await db.commit()
    return DocumentOut.from_model(doc)


# --------------------------------------------------------------------------- #
# Access requests
# --------------------------------------------------------------------------- #
@router.get("/access-requests", response_model=list[AccessRequestOut])
async def list_access_requests(
    status_filter: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[AccessRequestOut]:
    tenant_id = _require_tenant_admin(user)
    stmt = select(TrustCenterAccessRequest).where(
        TrustCenterAccessRequest.tenant_id == tenant_id
    )
    if status_filter:
        stmt = stmt.where(TrustCenterAccessRequest.status == status_filter)
    q = await db.execute(stmt)
    return [AccessRequestOut.from_model(r) for r in q.scalars().all()]


@router.post("/access-requests/{request_id}/approve", response_model=ApprovedAccessOut)
async def approve_request(
    request_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ApprovedAccessOut:
    tenant_id = _require_tenant_admin(user)
    q = await db.execute(
        select(TrustCenterAccessRequest).where(
            TrustCenterAccessRequest.id == request_id,
            TrustCenterAccessRequest.tenant_id == tenant_id,
        )
    )
    if q.scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail="Request not found")

    try:
        granted = await approve_access(db, request_id, user.id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    if granted is None:
        raise HTTPException(status_code=404, detail="Request not found")
    db.add(
        AuditLog(
            id=uuid.uuid4(),
            user_id=user.id,
            tenant_id=tenant_id,
            action="trust_center_approve_access",
            resource_type="trust_center_access_request",
            resource_id=granted.request.id,
            details={
                "doc_id": str(granted.request.requesting_doc_id),
                "requester_email": granted.request.requester_email,
                "expires_at": granted.request.expires_at.isoformat()
                if granted.request.expires_at
                else None,
            },
        )
    )
    await db.commit()
    return ApprovedAccessOut(
        request=AccessRequestOut.from_model(granted.request),
        access_token=granted.raw_token,
    )


@router.post("/access-requests/{request_id}/deny", response_model=AccessRequestOut)
async def deny_request(
    request_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> AccessRequestOut:
    tenant_id = _require_tenant_admin(user)
    q = await db.execute(
        select(TrustCenterAccessRequest).where(
            TrustCenterAccessRequest.id == request_id,
            TrustCenterAccessRequest.tenant_id == tenant_id,
        )
    )
    if q.scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail="Request not found")
    try:
        req = await deny_access(db, request_id, user.id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    if req is None:
        raise HTTPException(status_code=404, detail="Request not found")
    db.add(
        AuditLog(
            id=uuid.uuid4(),
            user_id=user.id,
            tenant_id=tenant_id,
            action="trust_center_deny_access",
            resource_type="trust_center_access_request",
            resource_id=req.id,
            details={
                "doc_id": str(req.requesting_doc_id),
                "requester_email": req.requester_email,
            },
        )
    )
    await db.commit()
    return AccessRequestOut.from_model(req)
