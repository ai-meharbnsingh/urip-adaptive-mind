"""
VAPT Vendor Portal models — P33a.6.5 (URIP_Blueprint v3 §6.5).

Three tables:
  vapt_vendors            — registered VAPT vendors per tenant
  vapt_vendor_invitations — invitation tokens (SHA-256 hashed before storage)
  vapt_submissions        — vulnerability findings submitted by vendors

Design echoes compliance_backend.models.auditor:
  - invitation_token_hash stores ONLY the SHA-256 of the plaintext token
  - the plaintext token lives only in the URL handed to the vendor (one-shot)
  - tenant_id is mandatory on every row that holds vendor data, mirroring
    URIP's existing multi-tenant invariant (Risk.tenant_id NOT NULL).

Each VaptSubmission auto-creates a Risk record post-insert via the
vapt_vendor_service.submit_finding() pipeline; the FK risk_record_id closes
the loop so the vendor can see "your finding became RISK-2026-XXXX".
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Index, Numeric, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from backend.database import Base


class VaptVendor(Base):
    """
    A VAPT (vendor or pentest firm) authorised to submit findings to a tenant.

    A vendor:
      - belongs to exactly ONE tenant (tenant_id NOT NULL)
      - may go through several invitation cycles (multiple VaptVendorInvitation
        rows tied via FK), but only the most recent active one matters
      - has status field for admin-driven enable/disable; a status of
        'suspended' blocks JWT verification at the middleware layer even if
        the JWT is still inside its validity window
    """
    __tablename__ = "vapt_vendors"
    __table_args__ = (
        Index("idx_vapt_vendors_tenant_id", "tenant_id"),
        Index("idx_vapt_vendors_status", "status"),
        Index("idx_vapt_vendors_email", "contact_email"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="RESTRICT"),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    contact_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    contact_email: Mapped[str] = mapped_column(String(255), nullable=False)
    organization: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # active | suspended
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="active", server_default="active"
    )
    invited_by_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    invited_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    last_login_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )


class VaptVendorInvitation(Base):
    """Invitation token row — hashed at rest, plaintext shown only at create-time."""
    __tablename__ = "vapt_vendor_invitations"
    __table_args__ = (
        Index("idx_vapt_invites_vendor", "vapt_vendor_id"),
        Index("idx_vapt_invites_hash", "invitation_token_hash"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    vapt_vendor_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("vapt_vendors.id", ondelete="CASCADE"),
        nullable=False,
    )
    invitation_token_hash: Mapped[str] = mapped_column(
        String(64), nullable=False, unique=True
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    invited_by_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    accepted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )


class VaptSubmission(Base):
    """
    A vulnerability finding submitted by a VAPT vendor.

    Lifecycle (status):
      submitted        → finding just received, URIP enrichment still running
      triaged          → enrichment done, IT team notified
      in_progress      → IT team working on remediation
      fixed            → IT team marked fixed, awaiting vendor re-test
      retest_requested → admin requested vendor re-test (vendor sees alert)
      retest_pass      → vendor re-tested and confirmed remediation works
      retest_fail      → vendor re-tested and remediation failed → back to in_progress
      closed           → finalised (auto on retest_pass)

    risk_record_id links to the auto-created URIP Risk row, so vendors can
    see the unified composite score / EPSS / KEV enrichment that URIP applied
    on top of their finding.
    """
    __tablename__ = "vapt_submissions"
    __table_args__ = (
        Index("idx_vapt_subs_tenant", "tenant_id"),
        Index("idx_vapt_subs_vendor", "vapt_vendor_id"),
        Index("idx_vapt_subs_status", "status"),
        Index("idx_vapt_subs_severity", "severity"),
        Index("idx_vapt_subs_risk", "risk_record_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    vapt_vendor_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("vapt_vendors.id", ondelete="RESTRICT"),
        nullable=False,
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="RESTRICT"),
        nullable=False,
    )

    # Finding fields
    finding_title: Mapped[str] = mapped_column(String(500), nullable=False)
    cve_id: Mapped[str | None] = mapped_column(String(30), nullable=True)
    cvss_score: Mapped[float] = mapped_column(Numeric(3, 1), nullable=False)
    severity: Mapped[str] = mapped_column(String(10), nullable=False)
    affected_asset_hostname: Mapped[str | None] = mapped_column(
        String(255), nullable=True
    )
    affected_asset_ip: Mapped[str | None] = mapped_column(String(45), nullable=True)
    # poc | functional | weaponized
    exploit_maturity: Mapped[str | None] = mapped_column(String(20), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    remediation_recommendation: Mapped[str | None] = mapped_column(Text, nullable=True)
    evidence_storage_uri: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    evidence_filename: Mapped[str | None] = mapped_column(String(500), nullable=True)

    submitted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="submitted", server_default="submitted"
    )

    # Cross-reference to URIP risk register row (created by submit_finding pipeline)
    risk_record_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("risks.id", ondelete="SET NULL"), nullable=True
    )

    # Re-test workflow
    retest_requested_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    retest_requested_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    retest_completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    # pass | fail | None
    retest_result: Mapped[str | None] = mapped_column(String(10), nullable=True)
    retest_evidence_uri: Mapped[str | None] = mapped_column(
        String(1024), nullable=True
    )
    retest_notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
