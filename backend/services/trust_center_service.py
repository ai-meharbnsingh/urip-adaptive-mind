"""
trust_center_service — Project_33a Roadmap-2.

Mirrors auditor_service.py's invitation-token pattern:
    - random URL-safe token (256-bit entropy)
    - SHA-256 hashed before storage
    - plaintext lives only in the URL/email handed to the requester
    - explicit expires_at for time-bound access

Public flow:
    1. publish_document(tenant, doc)              admin
    2. request_access(tenant, doc_id, requester)  buyer  → status=pending
    3. (optional) sign_nda(request_id, signature) buyer  → nda_signed_at set
    4. approve_access(request_id, approver_id)    admin → mints + returns token
    5. download_document(token)                   buyer → streams file

Storage abstraction:
    `download_document` returns a small dataclass holding the file's storage URI
    and metadata; the router decides how to actually serve the bytes.  That
    keeps this service free of S3 / R2 / local-fs leakage.
"""
from __future__ import annotations

import hashlib
import logging
import secrets
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.trust_center import (
    DOC_TYPE_VALUES,
    TrustCenterAccessRequest,
    TrustCenterDocument,
)

logger = logging.getLogger(__name__)


DEFAULT_ACCESS_TTL_HOURS = 72  # buyers get 3 days from approve to download.


# --------------------------------------------------------------------------- #
# Helpers (pure)
# --------------------------------------------------------------------------- #
def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def generate_access_token() -> str:
    """URL-safe random token, ~256 bits of entropy."""
    return secrets.token_urlsafe(32)


def hash_access_token(raw: str) -> str:
    """SHA-256 hex digest — exactly the same shape as auditor_service.hash_invitation_token."""
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


# --------------------------------------------------------------------------- #
@dataclass
class GrantedAccess:
    """Result of approve_access — includes raw_token (only chance to read it)."""
    request: TrustCenterAccessRequest
    raw_token: str


@dataclass
class DownloadHandle:
    """Returned by download_document — router uses this to stream the file."""
    document: TrustCenterDocument
    request: TrustCenterAccessRequest
    file_storage_uri: str


# --------------------------------------------------------------------------- #
# 1. Admin: publish document
# --------------------------------------------------------------------------- #
async def publish_document(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    *,
    doc_type: str,
    title: str,
    file_storage_uri: str,
    description: str | None = None,
    valid_until: datetime | None = None,
    requires_nda: bool = True,
    is_published: bool = True,
) -> TrustCenterDocument:
    if doc_type not in DOC_TYPE_VALUES:
        raise ValueError(f"Invalid doc_type {doc_type!r}; allowed: {sorted(DOC_TYPE_VALUES)}")
    if not title or not file_storage_uri:
        raise ValueError("title and file_storage_uri required")
    doc = TrustCenterDocument(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        doc_type=doc_type,
        title=title,
        description=description,
        file_storage_uri=file_storage_uri,
        valid_until=valid_until,
        is_published=is_published,
        requires_nda=requires_nda,
    )
    db.add(doc)
    await db.flush()
    return doc


async def list_published_documents(
    db: AsyncSession, tenant_id: uuid.UUID
) -> list[TrustCenterDocument]:
    """Public landing page query — only published, not-expired docs."""
    now = _utcnow()
    q = await db.execute(
        select(TrustCenterDocument).where(
            TrustCenterDocument.tenant_id == tenant_id,
            TrustCenterDocument.is_published.is_(True),
        )
    )
    docs = list(q.scalars().all())
    out: list[TrustCenterDocument] = []
    for d in docs:
        valid_until = d.valid_until
        if valid_until is None:
            out.append(d)
            continue
        # SQLite (test backend) returns naive datetimes; assume UTC and compare.
        if valid_until.tzinfo is None:
            valid_until = valid_until.replace(tzinfo=timezone.utc)
        if valid_until > now:
            out.append(d)
    return out


# --------------------------------------------------------------------------- #
# 2. Public: buyer requests access
# --------------------------------------------------------------------------- #
async def request_access(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    doc_id: uuid.UUID,
    *,
    requester_email: str,
    requester_name: str | None = None,
    requester_company: str | None = None,
    requester_purpose: str | None = None,
) -> TrustCenterAccessRequest:
    if not requester_email or "@" not in requester_email:
        raise ValueError("Valid requester_email required")
    # Confirm the doc exists, is published, and belongs to this tenant.
    q = await db.execute(
        select(TrustCenterDocument).where(
            TrustCenterDocument.id == doc_id,
            TrustCenterDocument.tenant_id == tenant_id,
            TrustCenterDocument.is_published.is_(True),
        )
    )
    doc = q.scalar_one_or_none()
    if doc is None:
        raise ValueError("Document not found or not published")

    req = TrustCenterAccessRequest(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        requesting_doc_id=doc_id,
        requester_email=requester_email,
        requester_name=requester_name,
        requester_company=requester_company,
        requester_purpose=requester_purpose,
        status="pending",
    )
    db.add(req)
    await db.flush()
    return req


# --------------------------------------------------------------------------- #
# 3. Public: NDA signature
# --------------------------------------------------------------------------- #
async def sign_nda(
    db: AsyncSession,
    request_id: uuid.UUID,
    *,
    signature_text: str,
) -> Optional[TrustCenterAccessRequest]:
    """
    Buyer types their full name as electronic signature.

    Returns the updated row; None if request not found.  Idempotent — re-sign
    overwrites the timestamp/text but never demotes the request out of pending.
    """
    if not signature_text or not signature_text.strip():
        raise ValueError("signature_text required")
    q = await db.execute(
        select(TrustCenterAccessRequest).where(
            TrustCenterAccessRequest.id == request_id
        )
    )
    req = q.scalar_one_or_none()
    if req is None:
        return None
    req.nda_signed_at = _utcnow()
    req.nda_signature_text = signature_text.strip()
    await db.flush()
    return req


# --------------------------------------------------------------------------- #
# 4. Admin: approve access
# --------------------------------------------------------------------------- #
async def approve_access(
    db: AsyncSession,
    request_id: uuid.UUID,
    approved_by_user_id: uuid.UUID,
    *,
    ttl_hours: int = DEFAULT_ACCESS_TTL_HOURS,
) -> Optional[GrantedAccess]:
    """
    Approve a pending access request.

    Returns GrantedAccess (with raw_token — ONE TIME) on success.
    Returns None if the request doesn't exist.

    Raises ValueError if the request is in the wrong state (already
    approved/denied) OR if NDA was required but not signed.
    """
    q = await db.execute(
        select(TrustCenterAccessRequest).where(
            TrustCenterAccessRequest.id == request_id
        )
    )
    req = q.scalar_one_or_none()
    if req is None:
        return None
    if req.status != "pending":
        raise ValueError(f"Cannot approve request in state {req.status!r}")

    # Look up the doc to check NDA requirement.
    doc_q = await db.execute(
        select(TrustCenterDocument).where(TrustCenterDocument.id == req.requesting_doc_id)
    )
    doc = doc_q.scalar_one_or_none()
    if doc is None:
        raise ValueError("Underlying document no longer exists")
    if doc.requires_nda and req.nda_signed_at is None:
        raise ValueError("NDA required but not yet signed by requester")

    raw_token = generate_access_token()
    req.access_token_hash = hash_access_token(raw_token)
    req.granted_at = _utcnow()
    req.granted_by_user_id = approved_by_user_id
    req.expires_at = _utcnow() + timedelta(hours=ttl_hours)
    req.status = "approved"
    await db.flush()
    return GrantedAccess(request=req, raw_token=raw_token)


async def deny_access(
    db: AsyncSession,
    request_id: uuid.UUID,
    denied_by_user_id: uuid.UUID,
) -> Optional[TrustCenterAccessRequest]:
    q = await db.execute(
        select(TrustCenterAccessRequest).where(TrustCenterAccessRequest.id == request_id)
    )
    req = q.scalar_one_or_none()
    if req is None:
        return None
    if req.status != "pending":
        raise ValueError(f"Cannot deny request in state {req.status!r}")
    req.status = "denied"
    req.granted_by_user_id = denied_by_user_id
    await db.flush()
    return req


# --------------------------------------------------------------------------- #
# 5. Public: download document (token-gated)
# --------------------------------------------------------------------------- #
async def download_document(
    db: AsyncSession, raw_token: str, doc_id: uuid.UUID
) -> Optional[DownloadHandle]:
    """
    Validate the token + return a DownloadHandle the router can stream.

    Returns None if the token is invalid, expired, the request was denied,
    or the doc_id mismatch.
    """
    if not raw_token:
        return None
    token_hash = hash_access_token(raw_token)
    q = await db.execute(
        select(TrustCenterAccessRequest).where(
            TrustCenterAccessRequest.access_token_hash == token_hash
        )
    )
    req = q.scalar_one_or_none()
    if req is None:
        return None
    if req.status != "approved":
        return None
    expires_at = req.expires_at
    if expires_at is None:
        return None
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if expires_at < _utcnow():
        return None
    if req.requesting_doc_id != doc_id:
        return None

    doc_q = await db.execute(
        select(TrustCenterDocument).where(TrustCenterDocument.id == doc_id)
    )
    doc = doc_q.scalar_one_or_none()
    if doc is None or not doc.is_published:
        return None

    # Increment download count for audit / abuse detection.
    req.download_count = (req.download_count or 0) + 1
    await db.flush()
    return DownloadHandle(document=doc, request=req, file_storage_uri=doc.file_storage_uri)
