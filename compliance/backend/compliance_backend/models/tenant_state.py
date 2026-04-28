"""
Tenant-side server state for control rule evaluation — CRIT-006 fix.

These tables exist so the control-engine NEVER trusts caller-supplied inputs.
A tenant-admin (or background sync from URIP) populates these tables; control
rules read from them. The `POST /controls/{id}/run` endpoint must derive its
rule inputs ONLY from these tables — never from the request body.

Tables:
  tenant_config
    Per-tenant settings dictionary used by control rules
    (e.g. {"mfa_enabled": true, "mfa_enforcement": "all_users"}).
    Mirrors URIP's `Tenant.settings` column when running INTEGRATED mode;
    in STANDALONE mode the compliance admin populates it directly.

  connector_pull
    Latest cached pull from each (tenant, connector) source.
    The control engine reads `connector_pull` rows and assembles them into
    the connector_data dict passed to rule.check(). The connector orchestrator
    (out of scope here) is responsible for refreshing rows on a schedule.

Both tables are append-or-upsert by (tenant_id, ...). The control engine
merges them into a server-derived `tenant_config`/`connector_data` snapshot
that NO request body can influence.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import String, DateTime, JSON, UniqueConstraint, Index
from sqlalchemy.orm import Mapped, mapped_column

from compliance_backend.database import Base


def _uuid_pk() -> Mapped[str]:
    return mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )


class TenantConfig(Base):
    """
    Server-side tenant configuration consumed by control rules.

    Exactly one row per tenant. Settings is a free-form JSON dict — same shape
    that used to be supplied (insecurely) via `tenant_config` in the request
    body. The compliance admin manages this server-side; the rule engine
    NEVER accepts any caller override.
    """
    __tablename__ = "tenant_config"

    id: Mapped[str] = _uuid_pk()
    # M7 (Codex MED-003 + Kimi MED-010) — standardised on String(36) UUID form.
    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False, unique=True, index=True)
    settings: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=lambda: datetime.now(timezone.utc)
    )

    __table_args__ = (
        UniqueConstraint("tenant_id", name="uq_tenant_config_tenant"),
    )

    def __repr__(self) -> str:
        return f"<TenantConfig tenant={self.tenant_id} keys={list((self.settings or {}).keys())}>"


class ConnectorPull(Base):
    """
    Latest connector pull cached per (tenant, connector_kind) pair.

    The control engine reads all rows for a tenant and assembles them into
    a `connector_data` dict keyed by `connector_kind` (e.g. "aws_iam").
    Caller cannot inject — the engine only reads from this table.
    """
    __tablename__ = "connector_pull"

    id: Mapped[str] = _uuid_pk()
    # M7 (Codex MED-003 + Kimi MED-010) — standardised on String(36) UUID form.
    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    connector_kind: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    pulled_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=lambda: datetime.now(timezone.utc)
    )

    __table_args__ = (
        UniqueConstraint("tenant_id", "connector_kind", name="uq_connector_pull_tenant_kind"),
        Index("ix_connector_pull_tenant_kind", "tenant_id", "connector_kind"),
    )

    def __repr__(self) -> str:
        return f"<ConnectorPull tenant={self.tenant_id} kind={self.connector_kind}>"
