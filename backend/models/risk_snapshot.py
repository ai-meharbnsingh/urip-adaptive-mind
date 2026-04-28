"""
RiskScoreSummary — cloud-side aggregate snapshot of risk posture per tenant.

Design notes:
  - One row per (tenant_id, snapshot_at) — written every hour by the nightly
    batch and on-demand via POST /api/risk-summary/snapshot.
  - snapshot_at is a full datetime (not date) so multiple snaps per day are
    possible without conflict.  The trend query groups per day on the read side.
  - JSON columns (top_sources_json, module_breakdown_json) stored as TEXT in
    SQLite tests via the conftest monkey-patch.
  - This table is the cloud-side cache that keeps the dashboard showing useful
    data even when the on-prem agent is offline (ref: DELIVERY_ARCHITECTURE.md §7.4).

Mirrors ComplianceScoreSnapshot (compliance/backend/compliance_backend/models/score_snapshot.py)
with the columns adapted for risk aggregation.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import DateTime, Float, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID, JSON
from sqlalchemy.orm import Mapped, mapped_column

from backend.database import Base


class RiskScoreSummary(Base):
    """
    A single point-in-time aggregate snapshot for one tenant's risk posture.

    Written either:
      - by the nightly/hourly snapshot job (services/risk_aggregate_service.write_snapshot)
      - manually via POST /api/risk-summary/snapshot (admin-only)
    """

    __tablename__ = "risk_score_summaries"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
        index=True,
    )
    # Full datetime — allows multiple snapshots per day (manual triggers)
    snapshot_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        index=True,
    )

    # --- Risk counts ---
    total_risks: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    critical_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    high_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    medium_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    low_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    info_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # --- Exploitability intelligence ---
    # Risks with epss_score > 0.7 AND status open
    exploit_active_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # Risks with in_kev_catalog = True AND status open
    kev_active_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # --- Remediation velocity (last 30 days, NULL if no closed risks in window) ---
    mean_ttr_hours: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # --- Score ---
    # Mean composite_score of all open risks; NULL if no open risks with a score
    mean_composite_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # --- TrendAI-style 0-100 Cyber Risk Index ---
    # SUPPLEMENTS the existing 0-10 mean_composite_score.  The 0-100 number is
    # what the dashboard top-strip renders; the underlying 0-10 value is what
    # exploitability/aggregate services rely on.
    index_0_100: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    level: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)  # low|medium|high|critical

    # --- 3 Cyber Risk sub-indexes (0-100 each) ---
    subindex_exposure: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    subindex_attack: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    subindex_security_config: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # --- 5-bucket per-asset-type domain counts ---
    domain_devices_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    domain_internet_facing_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    domain_accounts_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    domain_applications_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    domain_cloud_assets_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")

    # Per-bucket critical counts (for the dashboard severity tags)
    domain_devices_critical: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    domain_internet_facing_critical: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    domain_accounts_critical: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    domain_applications_critical: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    domain_cloud_assets_critical: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")

    # --- Breakdown JSON blobs ---
    # e.g. [{"source": "crowdstrike", "count": 42}, ...]  top 5 by risk count
    top_sources_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    # e.g. {"VM": 10, "EDR": 5, "NETWORK": 3, ...}
    module_breakdown_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Free-form catch-all for additional metrics pushed by the on-prem agent
    # via POST /api/agent-ingest/metadata.  New agent fields appear here without
    # requiring a schema migration.
    extra_metrics: Mapped[dict] = mapped_column(
        JSON, nullable=False, default=dict, server_default="{}"
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    __table_args__ = (
        Index(
            "ix_risk_score_summary_tenant_at",
            "tenant_id",
            "snapshot_at",
        ),
    )

    def __init__(self, **kwargs):
        """
        Override __init__ to apply Python-side defaults for integer counters.

        SQLAlchemy's column `default=` is a *column-level INSERT default* that is
        applied when the unit-of-work generates an INSERT statement.  Until flush
        the attribute remains None.  By explicitly setting defaults here we ensure
        that code (and tests) that access attributes immediately after construction
        see 0 rather than None.
        """
        kwargs.setdefault("total_risks", 0)
        kwargs.setdefault("critical_count", 0)
        kwargs.setdefault("high_count", 0)
        kwargs.setdefault("medium_count", 0)
        kwargs.setdefault("low_count", 0)
        kwargs.setdefault("info_count", 0)
        kwargs.setdefault("exploit_active_count", 0)
        kwargs.setdefault("kev_active_count", 0)
        kwargs.setdefault("domain_devices_count", 0)
        kwargs.setdefault("domain_internet_facing_count", 0)
        kwargs.setdefault("domain_accounts_count", 0)
        kwargs.setdefault("domain_applications_count", 0)
        kwargs.setdefault("domain_cloud_assets_count", 0)
        kwargs.setdefault("domain_devices_critical", 0)
        kwargs.setdefault("domain_internet_facing_critical", 0)
        kwargs.setdefault("domain_accounts_critical", 0)
        kwargs.setdefault("domain_applications_critical", 0)
        kwargs.setdefault("domain_cloud_assets_critical", 0)
        kwargs.setdefault("extra_metrics", {})
        super().__init__(**kwargs)

    def __repr__(self) -> str:  # pragma: no cover
        return (
            f"<RiskScoreSummary tenant={self.tenant_id} "
            f"at={self.snapshot_at} total={self.total_risks}>"
        )
