"""
seeders/simulators/sim_models.py — supplementary data models for simulator-only domains.

These models cover compliance domains (incidents, assets, access reviews) that do
not yet have canonical models in compliance_backend.models. They are placed here so:

  1. The simulator package owns its synthetic-data schema autonomously
     (Opus-A's deliverable does not block on Opus-C delivering canonical models).
  2. The same Base.metadata picks them up — they create real tables alongside
     the canonical ones at create_all() time.
  3. When Opus-C delivers canonical incident/asset/access_review models,
     this file should be deleted (use mv to _trash/) and the simulators
     re-pointed at the canonical model imports.

Status — TBD models (will be promoted to compliance_backend.models/* later):
  Incident                 — security incident lifecycle
  Asset                    — IT asset inventory
  AccessReviewCampaign     — quarterly access review batch
  AccessReviewDecision     — per-user keep/revoke verdict
"""
from __future__ import annotations

import uuid
from datetime import datetime, date
from typing import Optional, List

from sqlalchemy import (
    String,
    Text,
    Date,
    DateTime,
    ForeignKey,
    JSON,
    Integer,
    CheckConstraint,
    Index,
    Boolean,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from compliance_backend.database import Base


def _uuid_pk() -> Mapped[str]:
    return mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )


# ─────────────────────────────────────────────────────────────────────────────
# Incident — security incident lifecycle (NIST IR 800-61 phases)
# ─────────────────────────────────────────────────────────────────────────────

INCIDENT_SEVERITY_VALUES = ("low", "medium", "high", "critical")
INCIDENT_STATUS_VALUES = (
    "detected",
    "triaged",
    "contained",
    "eradicated",
    "recovered",
    "closed",
)
INCIDENT_CATEGORY_VALUES = (
    "phishing",
    "malware",
    "ransomware",
    "insider_threat",
    "data_loss",
    "ddos",
    "credential_compromise",
    "misconfiguration",
    "third_party",
    "physical",
)


class Incident(Base):
    """
    A security incident tracked through its full lifecycle.

    Lifecycle phases follow NIST SP 800-61r2:
      detected → triaged → contained → eradicated → recovered → closed

    severity drives SLA: critical=1h triage, high=4h, medium=24h, low=72h.
    rca_summary and lessons_learned populate after closure.
    """

    __tablename__ = "sim_incidents"

    id: Mapped[str] = _uuid_pk()
    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)  # M7 (Codex MED-003 + Kimi MED-010)
    incident_number: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str] = mapped_column(String(40), nullable=False)
    severity: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="detected")
    detected_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    triaged_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    contained_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    eradicated_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    recovered_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    closed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    assigned_to: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    affected_assets: Mapped[Optional[list]] = mapped_column(JSON, nullable=True, default=list)
    rca_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    lessons_learned: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    sla_breached: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    __table_args__ = (
        CheckConstraint(
            f"severity IN {INCIDENT_SEVERITY_VALUES}",
            name="ck_incident_severity",
        ),
        CheckConstraint(
            f"status IN {INCIDENT_STATUS_VALUES}",
            name="ck_incident_status",
        ),
        CheckConstraint(
            f"category IN {INCIDENT_CATEGORY_VALUES}",
            name="ck_incident_category",
        ),
        Index("ix_incident_tenant_status", "tenant_id", "status"),
    )

    def __repr__(self) -> str:
        return f"<Incident {self.incident_number} sev={self.severity} status={self.status}>"


# ─────────────────────────────────────────────────────────────────────────────
# Asset — IT asset inventory
# ─────────────────────────────────────────────────────────────────────────────

ASSET_TYPE_VALUES = (
    "laptop",
    "desktop",
    "server",
    "cloud_workload",
    "mobile",
    "network_device",
    "saas_app",
    "container",
)
ASSET_CLASSIFICATION_VALUES = ("public", "internal", "confidential", "restricted")
ASSET_LIFECYCLE_VALUES = (
    "in_procurement",
    "in_stock",
    "deployed",
    "in_repair",
    "retired",
    "destroyed",
)


class Asset(Base):
    """
    A discoverable IT asset for a tenant.

    Mirrors what a CMDB / asset-discovery connector (e.g. ManageEngine EC,
    Tenable, Lansweeper) would report. Owner_user_id is a free string today
    but should FK to URIP user table once unified.
    """

    __tablename__ = "sim_assets"

    id: Mapped[str] = _uuid_pk()
    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)  # M7 (Codex MED-003 + Kimi MED-010)
    asset_tag: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    asset_type: Mapped[str] = mapped_column(String(40), nullable=False)
    classification: Mapped[str] = mapped_column(String(20), nullable=False)
    lifecycle_state: Mapped[str] = mapped_column(String(30), nullable=False, default="deployed")
    owner_user_id: Mapped[str] = mapped_column(String(255), nullable=False)
    location: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    operating_system: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    ip_address: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    mac_address: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    serial_number: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    discovered_by: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=lambda: datetime.utcnow()
    )
    metadata_json: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    __table_args__ = (
        CheckConstraint(
            f"asset_type IN {ASSET_TYPE_VALUES}",
            name="ck_asset_type",
        ),
        CheckConstraint(
            f"classification IN {ASSET_CLASSIFICATION_VALUES}",
            name="ck_asset_classification",
        ),
        CheckConstraint(
            f"lifecycle_state IN {ASSET_LIFECYCLE_VALUES}",
            name="ck_asset_lifecycle",
        ),
        Index("ix_asset_tenant_type", "tenant_id", "asset_type"),
    )

    def __repr__(self) -> str:
        return f"<Asset {self.asset_tag} type={self.asset_type}>"


# ─────────────────────────────────────────────────────────────────────────────
# Access Review Campaigns + per-user decisions
# ─────────────────────────────────────────────────────────────────────────────

CAMPAIGN_STATUS_VALUES = ("planned", "in_progress", "completed", "cancelled")
DECISION_VALUES = ("keep", "revoke", "modify", "pending")


class AccessReviewCampaign(Base):
    """
    A quarterly access-review campaign for a tenant.

    Each campaign covers a defined scope (system_name + role_filter)
    and produces N AccessReviewDecision records — one per (user, entitlement).
    """

    __tablename__ = "sim_access_review_campaigns"

    id: Mapped[str] = _uuid_pk()
    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)  # M7 (Codex MED-003 + Kimi MED-010)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    system_name: Mapped[str] = mapped_column(String(100), nullable=False)
    period_label: Mapped[str] = mapped_column(String(20), nullable=False)  # e.g. "2026-Q1"
    started_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    due_at: Mapped[date] = mapped_column(Date, nullable=False)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="planned")
    reviewer_user_id: Mapped[str] = mapped_column(String(255), nullable=False)

    decisions: Mapped[List["AccessReviewDecision"]] = relationship(
        "AccessReviewDecision",
        back_populates="campaign",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        CheckConstraint(
            f"status IN {CAMPAIGN_STATUS_VALUES}",
            name="ck_campaign_status",
        ),
        Index("ix_access_review_tenant_period", "tenant_id", "period_label"),
    )


class AccessReviewDecision(Base):
    """A single keep/revoke verdict for a (user, entitlement) pair within a campaign."""

    __tablename__ = "sim_access_review_decisions"

    id: Mapped[str] = _uuid_pk()
    campaign_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("sim_access_review_campaigns.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    target_user_id: Mapped[str] = mapped_column(String(255), nullable=False)
    target_user_email: Mapped[str] = mapped_column(String(320), nullable=False)
    entitlement: Mapped[str] = mapped_column(String(255), nullable=False)
    decision: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    decided_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    decided_by_user_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    justification: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    campaign: Mapped["AccessReviewCampaign"] = relationship(
        "AccessReviewCampaign", back_populates="decisions"
    )

    __table_args__ = (
        CheckConstraint(
            f"decision IN {DECISION_VALUES}",
            name="ck_decision_value",
        ),
    )
