"""
Cyber Risk Quantification (FAIR Methodology) — Project_33a §13 LIVE
(MVP scaffold, 16th license module).

Two tables:
    fair_assumptions          — per-tenant configurable inputs
    fair_risk_assessments     — per-risk LEF × LM = ALE rows

FAIR (Factor Analysis of Information Risk) maps:
    Loss Event Frequency (LEF)  = annual number of incidents (events / yr)
    Loss Magnitude (LM)         = $ per incident (= primary loss + secondary loss)
    Annual Loss Exposure (ALE)  = LEF × LM  ($ / yr)

This is the canonical Open FAIR equation.  We store the inputs (LEF and
LM) and compute ALE; we do NOT compute LEF / LM ourselves — those come
from human judgement + tenant assumptions.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Index, Numeric, String, Text
from sqlalchemy.dialects.postgresql import JSON, UUID
from sqlalchemy.orm import Mapped, mapped_column

from backend.database import Base


class FAIRAssumptions(Base):
    """One row per tenant; latest wins (we keep history)."""
    __tablename__ = "fair_assumptions"
    __table_args__ = (
        Index("idx_fair_assum_tenant", "tenant_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="RESTRICT"), nullable=False
    )
    data_record_value_usd: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False, default=150.0)
    breach_response_cost_usd: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False, default=500_000.0)
    regulatory_fine_probability: Mapped[float] = mapped_column(nullable=False, default=0.30)  # 0..1
    regulatory_fine_amount_usd: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False, default=2_000_000.0)
    brand_damage_estimate_usd: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False, default=1_000_000.0)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )


class FAIRRiskAssessment(Base):
    """One row per (tenant, risk_id, computed_at) snapshot."""
    __tablename__ = "fair_risk_assessments"
    __table_args__ = (
        Index("idx_fair_assess_tenant", "tenant_id"),
        Index("idx_fair_assess_risk", "tenant_id", "risk_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="RESTRICT"), nullable=False
    )
    risk_id: Mapped[str] = mapped_column(String(64), nullable=False)  # match risks.risk_id
    risk_label: Mapped[str] = mapped_column(String(255), nullable=False)
    loss_event_frequency: Mapped[float] = mapped_column(nullable=False)  # events / year
    loss_magnitude_usd: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False)
    annual_loss_exposure_usd: Mapped[float] = mapped_column(Numeric(16, 2), nullable=False)
    components: Mapped[dict | None] = mapped_column(JSON, nullable=True)  # breakdown of LM
    computed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
