"""
Auditor Portal models — P2B.10

Tables:
  auditor_access         — invitation/access record bound to (tenant, framework, audit-period)
                           External auditors do NOT live in URIP's user table — they're
                           identified solely via signed invitation tokens. The token is
                           stored hashed (never in plaintext) so a DB read does not yield
                           a usable bearer credential.
  evidence_requests      — auditor-initiated requests for additional evidence; tenant
                           admins fulfil them by linking an Evidence record.
  auditor_activity_log   — append-only trail of every auditor action; surfaced to tenant
                           admins via /admin/auditor-activity.

Design notes:
  - UUIDs stored as String(36) for SQLite/Postgres portability (matches framework.py pattern).
  - Time-bound enforcement (expires_at + is_revoked) is checked in middleware on every
    auditor request — not at persistence time — so admins can revoke instantly without
    DB cleanup.
  - invitation_token_hash is SHA-256 of the opaque random secret embedded in the
    invitation URL; matches pattern used by GitHub/Slack invitation links.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import String, Text, Boolean, DateTime, ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column

from compliance_backend.database import Base


def _uuid_pk() -> Mapped[str]:
    return mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )


class AuditorAccess(Base):
    """
    Time-bound, single-framework access grant for an external auditor.

    Created by a tenant admin via POST /auditor-invitations.
    Accepted by the auditor via POST /auditor-invitations/accept (exchanges token
    for an auditor JWT scoped to (tenant, framework, audit period)).

    Lifecycle:
      created        → is_revoked=False, accepted_at=None
      accepted       → is_revoked=False, accepted_at=<now>
      revoked        → is_revoked=True   (admin action, irreversible)
      expired        → expires_at < now()  (enforced at request time)
    """
    __tablename__ = "auditor_access"

    id: Mapped[str] = _uuid_pk()
    # M7 (Codex MED-003 + Kimi MED-010) — standardised on String(36) UUID form.
    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    auditor_email: Mapped[str] = mapped_column(String(320), nullable=False, index=True)
    # Framework the auditor may inspect — single framework per invitation by design.
    # If an auditor needs to review multiple frameworks, the admin issues multiple invitations.
    framework_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    # Audit period boundaries — auditor sees only data captured within this window.
    audit_period_start: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    audit_period_end: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    # Which tenant admin issued the invitation (for accountability).
    invited_by_user_id: Mapped[str] = mapped_column(String(255), nullable=False)
    # SHA-256 of the opaque secret embedded in the invitation URL.
    # NEVER store the plaintext token — the URL itself is the only place it lives.
    invitation_token_hash: Mapped[str] = mapped_column(String(128), nullable=False, unique=True)
    # When the auditor first redeemed the invitation (NULL if unaccepted).
    accepted_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    # Hard expiry — even if not revoked, requests after this are denied.
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    is_revoked: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=lambda: datetime.now(timezone.utc)
    )

    __table_args__ = (
        Index("ix_auditor_access_tenant_framework", "tenant_id", "framework_id"),
    )

    def __repr__(self) -> str:
        return (
            f"<AuditorAccess id={self.id} tenant={self.tenant_id} "
            f"email={self.auditor_email} fw={self.framework_id}>"
        )


class EvidenceRequest(Base):
    """
    Auditor-initiated request for additional evidence.

    Surfaced to tenant admins in their dashboard. Admin fulfils by uploading
    new evidence (or linking an existing record) and writes the resulting
    Evidence.id into fulfillment_evidence_id.

    Note: control_id is nullable — auditor may request evidence about a topic
    that doesn't map cleanly to a single control (e.g. "show me your last DR test").
    """
    __tablename__ = "evidence_requests"

    id: Mapped[str] = _uuid_pk()
    auditor_access_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("auditor_access.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    control_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True, index=True)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    requested_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=lambda: datetime.now(timezone.utc)
    )
    fulfilled_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    fulfilled_by_user_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    # FK to Evidence — declared as plain String(36) (no FK constraint at DB layer)
    # because Evidence rows may be hard-deleted while we want history preserved.
    fulfillment_evidence_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)

    def __repr__(self) -> str:
        return (
            f"<EvidenceRequest id={self.id} access={self.auditor_access_id} "
            f"fulfilled={self.fulfilled_at is not None}>"
        )


class AuditorActivityLog(Base):
    """
    Append-only audit trail of every auditor action.

    Recorded by middleware around each /auditor/* route — the auditor cannot
    suppress it (auditor JWT has no write permissions on this table).

    target_type / target_id are nullable for actions like "list controls"
    that have no single target.
    """
    __tablename__ = "auditor_activity_log"

    id: Mapped[str] = _uuid_pk()
    # M7 (Codex MED-003 + Kimi MED-010) — standardised on String(36) UUID form.
    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    auditor_access_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    auditor_email: Mapped[str] = mapped_column(String(320), nullable=False)
    # Verb describing the action — e.g. "list_controls", "download_evidence",
    # "view_policy", "request_evidence".
    action: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    target_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    target_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    accessed_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=lambda: datetime.now(timezone.utc), index=True
    )
    ip_address: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)

    __table_args__ = (
        Index("ix_auditor_activity_tenant_time", "tenant_id", "accessed_at"),
    )

    def __repr__(self) -> str:
        return (
            f"<AuditorActivityLog id={self.id} action={self.action} "
            f"target={self.target_type}/{self.target_id}>"
        )
