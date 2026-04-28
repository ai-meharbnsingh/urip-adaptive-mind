"""
ControlCheckRun — P2B.3

Tracks the result of each automated control check run.

Design notes:
  - evidence_ids: JSON-stored list of Evidence record IDs collected during this run.
  - status: pass | fail | inconclusive
  - failure_reason: human-readable explanation when status != "pass"
  - UUID stored as String(36) for SQLite test compatibility (same pattern as framework.py)
"""
import uuid
from datetime import datetime
from typing import Optional, List

from sqlalchemy import String, Text, DateTime, ForeignKey, JSON
from sqlalchemy.orm import Mapped, mapped_column

from compliance_backend.database import Base


class ControlCheckRun(Base):
    """
    One execution of an automated control check for a given tenant.

    A new record is created each time the control engine runs a control rule.
    The evidence_ids list is populated by evidence_service after auto-collection.
    """
    __tablename__ = "control_check_runs"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    control_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("controls.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # M7 (Codex MED-003 + Kimi MED-010) — standardised on String(36) UUID form.
    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    run_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=lambda: datetime.utcnow()
    )
    # pass | fail | inconclusive
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    # JSON list of Evidence record IDs captured during this run
    evidence_ids: Mapped[Optional[List[str]]] = mapped_column(JSON, nullable=True, default=list)
    failure_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    def __repr__(self) -> str:
        return (
            f"<ControlCheckRun id={self.id} control={self.control_id} "
            f"tenant={self.tenant_id} status={self.status}>"
        )
