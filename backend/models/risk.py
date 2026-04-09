import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Index, Numeric, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from backend.database import Base


class Risk(Base):
    __tablename__ = "risks"
    __table_args__ = (
        Index("idx_risks_severity_status", "severity", "status"),
        Index("idx_risks_source", "source"),
        Index("idx_risks_domain", "domain"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    risk_id: Mapped[str] = mapped_column(String(20), unique=True, nullable=False, index=True)
    finding: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    source: Mapped[str] = mapped_column(String(30), nullable=False)
    domain: Mapped[str] = mapped_column(String(20), nullable=False)
    cvss_score: Mapped[float] = mapped_column(Numeric(3, 1), nullable=False)
    severity: Mapped[str] = mapped_column(String(10), nullable=False)  # critical, high, medium, low
    asset: Mapped[str] = mapped_column(String(255), nullable=False)
    owner_team: Mapped[str] = mapped_column(String(100), nullable=False)
    assigned_to: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    status: Mapped[str] = mapped_column(String(15), nullable=False, default="open")
    sla_deadline: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    jira_ticket: Mapped[str | None] = mapped_column(String(50), nullable=True)
    cve_id: Mapped[str | None] = mapped_column(String(30), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )


class RiskHistory(Base):
    __tablename__ = "risk_history"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    risk_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("risks.id"), nullable=False, index=True)
    field_changed: Mapped[str] = mapped_column(String(50), nullable=False)
    old_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    new_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    changed_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
