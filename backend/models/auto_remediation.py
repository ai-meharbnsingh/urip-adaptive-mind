"""
Auto-Remediation execution audit log — Project_33a Roadmap-3.

Stores the FULL audit trail for every auto-remediation attempt:
  - which executor ran (CrowdStrike RTR, Ansible, Fortinet, CyberArk)
  - implication check result (services_affected, expected_downtime_minutes)
  - before / after state snapshots
  - retest result (was the original detection still firing post-fix?)
  - approver_user_id (who clicked Execute) — NULL if pre-approved by tenant
    config (force=True for whitelisted categories like ssl_expired).

Every execution gets an immutable row.  This is the table that proves to
auditors that auto-remediation has been controlled, with humans in the loop
on anything risky.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSON, UUID
from sqlalchemy.orm import Mapped, mapped_column

from backend.database import Base


class AutoRemediationExecution(Base):
    __tablename__ = "auto_remediation_executions"
    __table_args__ = (
        Index("idx_auto_rem_tenant", "tenant_id"),
        Index("idx_auto_rem_risk", "risk_id"),
        Index("idx_auto_rem_status", "status"),
        Index("idx_auto_rem_executor", "executor_name"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="RESTRICT"),
        nullable=False,
    )
    risk_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("risks.id"), nullable=False
    )
    executor_name: Mapped[str] = mapped_column(String(40), nullable=False)
    # pending | dry_run | succeeded | failed | rolled_back
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="pending", server_default="pending"
    )
    dry_run: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")

    # Implication check fields
    services_affected: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    expected_downtime_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    rollback_plan: Mapped[str | None] = mapped_column(Text, nullable=True)

    # State capture
    before_state: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    after_state: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    retest_passed: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    retest_details: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    # Approval
    approver_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    auto_approved: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )

    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
