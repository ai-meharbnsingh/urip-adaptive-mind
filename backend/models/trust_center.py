"""
Trust Center models — Project_33a Roadmap-2 (URIP_Blueprint v3 §6 footnote
"Trust Center / SafeBase-equivalent — public-facing security portal customers
expose to their own buyers").

Two tables, both per-tenant:

    trust_center_documents      — what the tenant publishes
    trust_center_access_requests — buyer requests + NDA + time-bound tokens

Mirrors the auditor_service pattern:
  - SHA-256 hashing of access_token before storage (plaintext lives ONLY in
    the URL handed to the requester)
  - explicit `expires_at` to enforce time-bound access
  - `is_published` on the document so admins can stage docs before going live
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from backend.database import Base


# Allowed doc_type values (string-based to keep enum migration overhead low).
DOC_TYPE_VALUES = {
    "SOC2_REPORT",
    "ISO_CERT",
    "PEN_TEST_SUMMARY",
    "SECURITY_QUESTIONNAIRE_PREFILLED",
    "POLICY",
    "OTHER",
}


class TrustCenterDocument(Base):
    """
    A document the tenant publishes on their Trust Center.

    `requires_nda=True` blocks download until the requester signs an NDA via
    the public flow.  `is_published=False` keeps the document hidden from the
    public landing page — admin staging.
    """
    __tablename__ = "trust_center_documents"
    __table_args__ = (
        Index("idx_trust_docs_tenant", "tenant_id"),
        Index("idx_trust_docs_published", "tenant_id", "is_published"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="RESTRICT"),
        nullable=False,
    )
    doc_type: Mapped[str] = mapped_column(String(40), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    file_storage_uri: Mapped[str] = mapped_column(String(1024), nullable=False)
    valid_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    is_published: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    requires_nda: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )


class TrustCenterAccessRequest(Base):
    """
    A buyer's request for access to a TrustCenterDocument.

    Workflow:
        pending  → buyer submitted request (and NDA if required)
        approved → tenant admin approved; access_token_hash is now valid
        denied   → tenant admin denied; access_token_hash is empty
    """
    __tablename__ = "trust_center_access_requests"
    __table_args__ = (
        Index("idx_trust_reqs_tenant", "tenant_id"),
        Index("idx_trust_reqs_status", "status"),
        Index("idx_trust_reqs_token_hash", "access_token_hash"),
        Index("idx_trust_reqs_doc", "requesting_doc_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="RESTRICT"),
        nullable=False,
    )
    requesting_doc_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("trust_center_documents.id", ondelete="RESTRICT"),
        nullable=False,
    )
    requester_email: Mapped[str] = mapped_column(String(255), nullable=False)
    requester_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    requester_company: Mapped[str | None] = mapped_column(String(255), nullable=True)
    requester_purpose: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending", server_default="pending")
    nda_signed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    nda_signature_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    granted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    granted_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # SHA-256 hash of the random token sent in the access URL.  Empty until granted.
    access_token_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    download_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
