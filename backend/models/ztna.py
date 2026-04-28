"""
ZTNA (Zero Trust Network Access) models — Project_33a §13 LIVE
(MVP scaffold, 14th license module).

Three tables:
    ztna_policies            — declared per-app access policies
    ztna_access_decisions    — append-only audit log of allow/deny decisions
    ztna_posture_violations  — device-posture failures (encryption, OS patch,
                               EDR running, jailbreak, etc.)

URIP integrates with Zscaler ZPA, Cloudflare Access, Tailscale, Twingate
read-only (we don't sell ZTNA — we ingest posture from existing tools).
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import JSON, UUID
from sqlalchemy.orm import Mapped, mapped_column

from backend.database import Base


DECISION_VALUES = {"allow", "deny", "step_up"}
POSTURE_REQUIREMENT_VALUES = {
    "encryption_at_rest",
    "os_patched",
    "edr_running",
    "screen_lock",
    "no_jailbreak",
    "managed_device",
    "biometric_capable",
}


class ZTNAPolicy(Base):
    __tablename__ = "ztna_policies"
    __table_args__ = (
        Index("idx_ztna_pol_tenant", "tenant_id"),
        Index("idx_ztna_pol_app", "tenant_id", "target_app"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="RESTRICT"), nullable=False
    )
    policy_name: Mapped[str] = mapped_column(String(255), nullable=False)
    target_app: Mapped[str] = mapped_column(String(255), nullable=False)
    identity_required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    mfa_required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    device_posture_required: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    source_provider: Mapped[str | None] = mapped_column(String(40), nullable=True)  # zscaler-zpa|cloudflare-access|tailscale|twingate
    last_evaluated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )


class ZTNAAccessDecision(Base):
    __tablename__ = "ztna_access_decisions"
    __table_args__ = (
        Index("idx_ztna_dec_tenant", "tenant_id"),
        Index("idx_ztna_dec_policy", "policy_id"),
        Index("idx_ztna_dec_decided_at", "tenant_id", "decided_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="RESTRICT"), nullable=False
    )
    policy_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ztna_policies.id", ondelete="SET NULL"), nullable=True
    )
    user_identity: Mapped[str] = mapped_column(String(255), nullable=False)
    target_app: Mapped[str] = mapped_column(String(255), nullable=False)
    decision: Mapped[str] = mapped_column(String(20), nullable=False)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_ip: Mapped[str | None] = mapped_column(String(64), nullable=True)
    decided_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )


class ZTNAPostureViolation(Base):
    __tablename__ = "ztna_posture_violations"
    __table_args__ = (
        Index("idx_ztna_pv_tenant", "tenant_id"),
        Index("idx_ztna_pv_severity", "tenant_id", "severity"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="RESTRICT"), nullable=False
    )
    user_identity: Mapped[str] = mapped_column(String(255), nullable=False)
    device_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    failed_requirement: Mapped[str] = mapped_column(String(40), nullable=False)
    severity: Mapped[str] = mapped_column(String(10), nullable=False, default="medium")
    detected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    remediated: Mapped[bool] = mapped_column(Boolean, default=False)
