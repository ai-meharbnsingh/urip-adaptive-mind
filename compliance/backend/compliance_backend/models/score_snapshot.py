"""
ComplianceScoreSnapshot — P2B.11

Daily per-tenant per-framework score snapshot table used for trend analysis.

Design notes:
  - One row per (tenant_id, framework_id, snapshot_date) — UI-friendly grain.
  - score is stored as Float (0–100) to allow fractional values
    (e.g. 17/20 = 85.0; 5/7 = 71.43).
  - inconclusive_count is recorded for debugging but is NOT in the score
    denominator (see scoring_engine.calculate_framework_score).
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import String, Float, Integer, DateTime, Index, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from compliance_backend.database import Base


class ComplianceScoreSnapshot(Base):
    """
    A single point-in-time score for one (tenant, framework) pair.

    Written either:
      - by the nightly snapshot job (services/scoring_engine.write_daily_snapshot)
      - manually via POST /compliance-score/snapshot
    """
    __tablename__ = "compliance_score_snapshots"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    # M7 (Codex MED-003 + Kimi MED-010) — standardised on String(36) UUID form.
    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    framework_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    # Datetime not Date — multiple snapshots per day are allowed (manual triggers);
    # the trend query buckets per calendar day on the read side.
    snapshot_date: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=lambda: datetime.now(timezone.utc), index=True
    )
    score: Mapped[float] = mapped_column(Float, nullable=False)
    pass_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    fail_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    inconclusive_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # Denominator used for score calculation — pass + fail (NOT inconclusive)
    total_applicable: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    __table_args__ = (
        Index(
            "ix_score_snapshot_tenant_fw_date",
            "tenant_id",
            "framework_id",
            "snapshot_date",
        ),
    )

    def __repr__(self) -> str:
        return (
            f"<ComplianceScoreSnapshot tenant={self.tenant_id} fw={self.framework_id} "
            f"date={self.snapshot_date} score={self.score}>"
        )
