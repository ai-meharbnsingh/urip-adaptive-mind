"""
AI Security models — Project_33a §13 LIVE (MVP scaffold, 13th license module).

Three tables:
    ai_models                     — model inventory (registry of every AI/ML model in use)
    ai_prompt_injection_events    — manual upload OR webhook ingest of detected attacks
    ai_governance_assessments     — periodic governance checks (ISO 42001 / EU AI Act / NIST AI RMF)

Honest depth note
-----------------
Real AI Security (Hidden Layer, Protect AI, Lakera) ships:
  - runtime model-firewall sidecars,
  - automated red-teaming + prompt-injection fuzzing,
  - training-data drift detection,
  - model file scanning (pickled-model malware).
This scaffold covers the inventory + governance surface so an enterprise
buyer sees the module exists and can start tracking models.  The runtime
firewall + scanner pieces are roadmap.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import JSON, UUID
from sqlalchemy.orm import Mapped, mapped_column

from backend.database import Base


PROVIDER_VALUES = {
    "openai",
    "anthropic",
    "azure-openai",
    "self-hosted",
    "google-vertex",
    "huggingface",
    "aws-bedrock",
    "other",
}

GOVERNANCE_FRAMEWORKS = {
    "ISO_42001",
    "EU_AI_ACT",
    "NIST_AI_RMF",
}


class AIModel(Base):
    """Inventory entry for one model (production deployment OR experimental)."""
    __tablename__ = "ai_models"
    __table_args__ = (
        Index("idx_ai_models_tenant", "tenant_id"),
        Index("idx_ai_models_provider", "tenant_id", "provider"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="RESTRICT"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    provider: Mapped[str] = mapped_column(String(40), nullable=False)
    purpose: Mapped[str | None] = mapped_column(Text, nullable=True)
    training_data_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    deployment_endpoints: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    risk_level: Mapped[str] = mapped_column(String(10), nullable=False, default="medium")  # critical|high|medium|low
    last_audited_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )


class PromptInjectionEvent(Base):
    """A single detected (or reported) prompt-injection attempt."""
    __tablename__ = "ai_prompt_injection_events"
    __table_args__ = (
        Index("idx_ai_pi_tenant", "tenant_id"),
        Index("idx_ai_pi_model", "ai_model_id"),
        Index("idx_ai_pi_severity", "tenant_id", "severity"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="RESTRICT"), nullable=False
    )
    ai_model_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("ai_models.id", ondelete="SET NULL"),
        nullable=True,
    )
    prompt_excerpt: Mapped[str] = mapped_column(Text, nullable=False)
    detection_source: Mapped[str] = mapped_column(String(40), nullable=False, default="manual_upload")  # manual_upload|webhook|sidecar
    severity: Mapped[str] = mapped_column(String(10), nullable=False, default="medium")
    blocked: Mapped[bool] = mapped_column(default=False)
    detected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    metadata_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)


class GovernanceAssessment(Base):
    """A point-in-time governance score for a model against a framework."""
    __tablename__ = "ai_governance_assessments"
    __table_args__ = (
        Index("idx_ai_gov_tenant", "tenant_id"),
        Index("idx_ai_gov_model", "ai_model_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="RESTRICT"), nullable=False
    )
    ai_model_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ai_models.id", ondelete="CASCADE"), nullable=False
    )
    framework: Mapped[str] = mapped_column(String(40), nullable=False)
    score: Mapped[int] = mapped_column(nullable=False, default=0)  # 0-100
    findings: Mapped[list[dict] | None] = mapped_column(JSON, nullable=True)
    assessed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
