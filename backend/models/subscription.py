"""
TenantSubscription — module subscription registry for URIP multi-tenant platform.

Design decisions
----------------
P1.10 (Subscription Pricing): billing_tier + started_at + expires_at on this model
is sufficient for pricing tracking at this stage.  No separate billing table is
created.  Rationale: we need tier-gating and expiry enforcement; a dedicated billing
table adds FK complexity with no extra data.  When a proper billing system (Stripe,
Chargebee) is integrated, a new `invoices` / `billing_events` table can reference
tenant_subscriptions.id without any schema change here.

Module codes
------------
CORE        — always enabled; covers auth, risk register, audit log, dashboard
VM          — Vulnerability Management (Tenable / Qualys / Rapid7)
EDR         — Endpoint Detection & Response (SentinelOne / CrowdStrike)
NETWORK     — Network / CASB / SASE (Zscaler / Netskope / Palo Alto)
IDENTITY    — Identity & Access Management (MS Entra / Okta / Google Workspace)
COLLAB      — Collaboration (SharePoint / Teams / Slack / Confluence)
ITSM        — IT Service Management (ServiceNow / Jira / ManageEngine SDP)
DAST        — Dynamic App Sec Testing (Burpsuite / OWASP ZAP / Acunetix)
DLP         — Data Loss Prevention (GTB / Forcepoint / Symantec DLP)
COMPLIANCE  — Compliance & Audit-Readiness (SOC 2, ISO 27001, GDPR, HIPAA, PCI DSS)

Billing tiers
-------------
TRIAL       — time-limited free evaluation (expires_at set on creation)
STANDARD    — paid, base feature set
PREMIUM     — paid, all features + priority support
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from backend.database import Base


MODULE_CODES = {
    "CORE",
    "VM",
    "EDR",
    "NETWORK",
    "IDENTITY",
    "COLLAB",
    "ITSM",
    "DAST",
    "DLP",
    "COMPLIANCE",
    "CSPM",
    # Project_33a roadmap scaffold modules (MVP scaffold depth — see §13)
    "DSPM",            # 12th license module — Data Security Posture Management
    "AI_SECURITY",     # 13th license module — AI/ML model inventory + governance
    "ZTNA",            # 14th license module — Zero Trust Network Access posture
    "ATTACK_PATH",     # 15th license module — Attack path graph engine
    "RISK_QUANT",      # 16th license module — FAIR-based cyber risk quantification
}

BILLING_TIERS = {"TRIAL", "STANDARD", "PREMIUM"}


class TenantSubscription(Base):
    """
    One row per (tenant, module) pair.

    is_enabled=False means the module is soft-disabled (audit trail preserved).
    Hard-delete is prohibited; use PATCH to set is_enabled=false instead.
    """

    __tablename__ = "tenant_subscriptions"
    __table_args__ = (
        UniqueConstraint("tenant_id", "module_code", name="uq_tenant_module"),
        Index("idx_tenant_subscriptions_tenant_id", "tenant_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="RESTRICT"),
        nullable=False,
    )
    # One of MODULE_CODES — enforced at application layer (Pydantic) for SQLite compat
    module_code: Mapped[str] = mapped_column(String(20), nullable=False)
    is_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    # One of BILLING_TIERS — enforced at application layer
    billing_tier: Mapped[str] = mapped_column(String(20), nullable=False, default="TRIAL")
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    # None = unlimited / no expiry  (STANDARD / PREMIUM subscriptions typically)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
