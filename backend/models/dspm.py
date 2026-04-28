"""
DSPM (Data Security Posture Management) models — Project_33a §13 LIVE
roadmap promotion (MVP scaffold depth — see honest caveat).

Two tables:
    data_assets              — discovered data stores (DB, file system, S3, SaaS)
    sensitive_discoveries    — per-asset sensitive-data findings (PII, PHI, secrets)
    data_access_paths        — who/what can reach a data asset (identity → asset edges)

The scan service ingests from existing connectors (cloud_assets from CSPM +
collaboration tools).  Field shapes mirror the URIP convention:
  - `tenant_id` on every row
  - explicit `created_at` / `updated_at`
  - `JSON` for variable-shape lists (sensitive_data_types, tags, evidence)

This is SCAFFOLD-grade — i.e. enough surface area for a customer to see
"DSPM module is here" but the ML classifier, real cross-store data-flow
graph, and shadow-data discovery engine are roadmap (see §13).
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import JSON, UUID
from sqlalchemy.orm import Mapped, mapped_column

from backend.database import Base


# Allowed store_type values (kept as a frozen set so router/service can validate).
STORE_TYPE_VALUES = {
    "database",
    "file_system",
    "object_storage",
    "saas",
}

# Allowed data_classification values — Public < Internal < Confidential < Restricted.
DATA_CLASSIFICATION_VALUES = {
    "public",
    "internal",
    "confidential",
    "restricted",
}


class DataAsset(Base):
    """
    A single data store (a database, a bucket, a SaaS workspace, a file share).

    `sensitive_data_types` is a JSON list of strings — e.g. ["pii", "phi",
    "pci", "secrets"].  Free-form so connectors can populate any taxonomy
    they support.
    """
    __tablename__ = "dspm_data_assets"
    __table_args__ = (
        Index("idx_dspm_assets_tenant", "tenant_id"),
        Index("idx_dspm_assets_tenant_store", "tenant_id", "store_type"),
        Index("idx_dspm_assets_tenant_class", "tenant_id", "data_classification"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="RESTRICT"), nullable=False
    )
    store_type: Mapped[str] = mapped_column(String(20), nullable=False)
    location: Mapped[str] = mapped_column(String(500), nullable=False)
    data_classification: Mapped[str] = mapped_column(String(20), nullable=False, default="internal")
    sensitive_data_types: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    owner: Mapped[str | None] = mapped_column(String(255), nullable=True)
    last_scanned_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )


class SensitiveDataDiscovery(Base):
    """
    A single sensitive-data hit on a data asset.

    Example: "table users.ssn detected as PII (123 sample rows)".

    `evidence` is a JSON blob with the connector-specific payload (sample
    rows, regex matches, ML confidence score, etc.) — purposely loose so
    new classifiers can be added without a schema migration.
    """
    __tablename__ = "dspm_sensitive_discoveries"
    __table_args__ = (
        Index("idx_dspm_disc_tenant", "tenant_id"),
        Index("idx_dspm_disc_asset", "data_asset_id"),
        Index("idx_dspm_disc_severity", "tenant_id", "severity"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="RESTRICT"), nullable=False
    )
    data_asset_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("dspm_data_assets.id", ondelete="CASCADE"),
        nullable=False,
    )
    sensitive_type: Mapped[str] = mapped_column(String(40), nullable=False)
    severity: Mapped[str] = mapped_column(String(10), nullable=False, default="medium")
    sample_count: Mapped[int | None] = mapped_column(nullable=True)
    evidence: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    detected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )


class DataAccessPath(Base):
    """
    A single (identity → data asset) edge with its access type.

    Used by the access-paths endpoint to answer: "who can read SSNs?".
    """
    __tablename__ = "dspm_access_paths"
    __table_args__ = (
        Index("idx_dspm_path_tenant", "tenant_id"),
        Index("idx_dspm_path_asset", "data_asset_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="RESTRICT"), nullable=False
    )
    data_asset_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("dspm_data_assets.id", ondelete="CASCADE"),
        nullable=False,
    )
    identity: Mapped[str] = mapped_column(String(255), nullable=False)
    identity_type: Mapped[str] = mapped_column(String(20), nullable=False, default="user")  # user|group|role|service
    access_type: Mapped[str] = mapped_column(String(20), nullable=False, default="read")  # read|write|admin
    granted_via: Mapped[str | None] = mapped_column(String(255), nullable=True)  # e.g. "iam_policy:abc"
    last_evaluated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
