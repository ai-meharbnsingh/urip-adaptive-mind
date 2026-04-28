import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Index, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import JSON, UUID
from sqlalchemy.orm import Mapped, mapped_column

from backend.database import Base


class Risk(Base):
    __tablename__ = "risks"
    __table_args__ = (
        Index("idx_risks_severity_status", "severity", "status"),
        Index("idx_risks_source", "source"),
        Index("idx_risks_domain", "domain"),
        Index("idx_risks_composite_score", "composite_score"),
        Index("idx_risks_tenant_id", "tenant_id"),
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
    # Project_33a Roadmap-1: bidirectional ticketing.
    # `ticket_id` is provider-agnostic — Jira "URIP-42" or ServiceNow
    # "INC0010234" — and `ticket_provider` records which provider created it
    # so webhooks / pollers know how to look it up later.
    ticket_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    ticket_provider: Mapped[str | None] = mapped_column(String(20), nullable=True)
    cve_id: Mapped[str | None] = mapped_column(String(30), nullable=True)
    # Exploitability Intelligence fields
    epss_score: Mapped[float | None] = mapped_column(Numeric(6, 5), nullable=True)
    epss_percentile: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)
    in_kev_catalog: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    exploit_status: Mapped[str | None] = mapped_column(String(15), nullable=True)  # none, poc, active, weaponized
    # Asset criticality
    asset_tier: Mapped[int | None] = mapped_column(Integer, nullable=True)  # 1=Critical, 2=High, 3=Medium, 4=Low
    composite_score: Mapped[float | None] = mapped_column(Numeric(4, 1), nullable=True)
    # Universal Intelligence Engine (v3 §3.4–§4.1)
    fingerprint_key: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    sources_attributed: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list, server_default="[]")
    advisory_status: Mapped[str | None] = mapped_column(
        Enum("valid", "patch_available", "expired", "redundant", name="advisory_status_enum"),
        nullable=True,
    )
    remediation_steps: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list, server_default="[]")
    # M6 (Gemini HIGH-G5 → MEDIUM, Kimi MED-011) — tenant_id is now NOT NULL.
    # All Risk rows MUST belong to a tenant — there is no concept of an
    # "untenanted" risk in URIP.  The application layer always stamps tenant_id
    # via TenantContext.get() on insert; this constraint catches any future
    # code path that forgets.
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="RESTRICT"),
        nullable=False,
    )
    # P33a — Asset model integration. Links each Risk to its first-class
    # Asset row.  Nullable so existing rows are not broken; new ingest path
    # populates this via asset_service.upsert_asset().  ondelete="SET NULL"
    # because deleting an Asset (rare, admin-only) should not cascade to
    # historical risks — they keep the asset hostname string in `asset` for
    # audit purposes.
    asset_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("assets.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
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
