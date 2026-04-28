"""
ComplianceAuditLog — append-only audit trail for tenant-scoped compliance
admin actions (CritFix-B NEW-1, compliance-side).

Why a separate model from URIP's AuditLog?
------------------------------------------
- The Compliance Service has its own database (compliance_db on port 5434)
  and own SQLAlchemy Base — there is no shared audit_log table.
- The existing `auditor_activity_log` (models/auditor.py) is for *external
  auditor* sessions only — it is NOT the right place for tenant admin
  actions like vendor mutations or policy publishes.
- Cross-service event-bus emit (shared/events) is intentionally out of
  scope for this fix — keep the audit row co-located with the data it
  audits so a single DB transaction can guarantee atomicity.

Tenant-id is NOT NULL on purpose: every state-changing compliance action
MUST be tied to a tenant.  Super-admin/cross-tenant administrative
actions are not modelled here yet (compliance has no super-admin concept).
"""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import String, DateTime, Index, Text
from sqlalchemy.orm import Mapped, mapped_column

from compliance_backend.database import Base


class ComplianceAuditLog(Base):
    """
    Append-only audit row for compliance-side state changes.

    Fields
    ------
    id              opaque uuid pk
    tenant_id       NOT NULL — the tenant the mutation affects
    user_id         the actor (sub claim from JWT) — string because
                    compliance auth.py stores user ids as raw JWT subs
    action          short verb e.g. "vendor_created" / "policy_published"
    resource_type   "vendor" | "policy" | "control_run" | "evidence" | ...
    resource_id     opaque resource id (str — may be uuid, framework code,
                    or null for batch ops like score snapshots)
    details_json    JSON blob (stored as TEXT for SQLite compatibility) —
                    free-form payload (changes diff, count, etc.)
    created_at      auto, UTC
    """

    __tablename__ = "compliance_audit_logs"
    __table_args__ = (
        Index("idx_compliance_audit_logs_tenant_id", "tenant_id"),
        Index("idx_compliance_audit_logs_action", "action"),
    )

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    # nullable=False — every audit row MUST be tenant-stamped (NEW-1).
    # M7 (Codex MED-003 + Kimi MED-010) — standardised on String(36) UUID form.
    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False)
    user_id: Mapped[str] = mapped_column(String(128), nullable=False)
    action: Mapped[str] = mapped_column(String(64), nullable=False)
    resource_type: Mapped[str] = mapped_column(String(64), nullable=False)
    resource_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    details_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
