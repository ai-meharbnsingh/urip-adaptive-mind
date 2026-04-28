"""
CSPM (Cloud Security Posture Management) data models.

Tables:
  - cspm_frameworks    : CIS/AWS/Azure/GCP framework definitions
  - cspm_controls      : Individual controls within a framework
  - cspm_check_results : Per-tenant, per-control evaluation results
  - cspm_score_snapshots : Historical compliance score per cloud provider
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Index, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import JSON, UUID
from sqlalchemy.orm import Mapped, mapped_column

from backend.database import Base


class CspmFramework(Base):
    __tablename__ = "cspm_frameworks"
    __table_args__ = (
        Index("idx_cspm_frameworks_provider", "cloud_provider"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    cloud_provider: Mapped[str] = mapped_column(String(20), nullable=False)  # aws, azure, gcp
    version: Mapped[str] = mapped_column(String(20), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )


class CspmControl(Base):
    __tablename__ = "cspm_controls"
    __table_args__ = (
        Index("idx_cspm_controls_framework", "framework_id"),
        Index("idx_cspm_controls_severity", "severity"),
        Index("idx_cspm_controls_rule", "rule_function"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    framework_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("cspm_frameworks.id", ondelete="CASCADE"), nullable=False
    )
    control_code: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    severity: Mapped[str] = mapped_column(String(10), nullable=False)  # critical, high, medium, low
    rule_function: Mapped[str | None] = mapped_column(String(100), nullable=True)
    affected_services: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )


class CspmCheckResult(Base):
    __tablename__ = "cspm_check_results"
    __table_args__ = (
        Index("idx_cspm_results_tenant", "tenant_id"),
        Index("idx_cspm_results_control", "control_id"),
        Index("idx_cspm_results_status", "status"),
        Index("idx_cspm_results_run_at", "run_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="RESTRICT"), nullable=False
    )
    control_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("cspm_controls.id", ondelete="CASCADE"), nullable=False
    )
    cloud_account_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    status: Mapped[str] = mapped_column(String(15), nullable=False)  # pass, fail, inconclusive
    evidence_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    run_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    failing_resource_ids: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )


class CspmScoreSnapshot(Base):
    __tablename__ = "cspm_score_snapshots"
    __table_args__ = (
        Index("idx_cspm_snapshots_tenant_provider", "tenant_id", "cloud_provider"),
        Index("idx_cspm_snapshots_at", "snapshot_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="RESTRICT"), nullable=False
    )
    cloud_provider: Mapped[str] = mapped_column(String(20), nullable=False)
    snapshot_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    score: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False)
    pass_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    fail_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    inconclusive_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
