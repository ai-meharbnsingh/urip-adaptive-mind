"""
backend/models/agent_ingest.py — Hybrid-SaaS cloud-side models for Docker agent.

Phase 4 — Hybrid-SaaS delivery (DELIVERY_ARCHITECTURE.md §3, §7).

These tables live ONLY in the cloud database. They store metadata pushed from
on-prem Docker agents — NEVER raw findings.

Tables
------
- AgentRegistration      — one row per agent install (per tenant).  Holds the
                            HMAC-SHA256 hash of the shared secret used to verify
                            every subsequent payload.  Plain secret is delivered
                            ONCE in the /register response.
- RiskScoreSummary        — periodic aggregate snapshot pushed by agent so the
                            cloud dashboard remains useful when the agent goes
                            offline.  Contains COUNTS only — no IPs, no hostnames,
                            no usernames.
- ConnectorHealthSummary  — per-connector heartbeat health (status, last poll,
                            error count) so the admin UI can show "agent up,
                            tenable connector failing".
- DrilldownRequest        — short-lived request/response envelope for on-demand
                            raw-data retrieval.  Token expires in 60 s.  Response
                            payload is stored briefly only so the SSE listener
                            can forward it; cleared immediately after fulfilment
                            and never persisted long-term.

Security notes
--------------
- shared_secret is NEVER stored in plaintext — only its HMAC-SHA256 hash
  (deterministic, lookup-friendly).  The plaintext is returned exactly once
  during /register and the agent stores it in its own env / vault.
- DrilldownRequest.fulfilled_payload_temp is intentionally `Text` (JSON string)
  with a TTL contract enforced by the router: it is wiped to NULL after the
  SSE stream forwards it OR after the row expires (whichever first).
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSON, UUID
from sqlalchemy.orm import Mapped, mapped_column

from backend.database import Base

# RiskScoreSummary is defined in risk_snapshot — import here so any code that
# imports `from backend.models.agent_ingest import RiskScoreSummary` keeps working.
from backend.models.risk_snapshot import RiskScoreSummary  # noqa: F401 — re-export


# ─────────────────────────────────────────────────────────────────────────────
# AgentRegistration
# ─────────────────────────────────────────────────────────────────────────────


class AgentRegistration(Base):
    """One row per (tenant, agent install).  Tracks last_seen + shared_secret_hash."""

    __tablename__ = "agent_registrations"
    __table_args__ = (
        Index("idx_agent_reg_tenant_id", "tenant_id"),
        Index("idx_agent_reg_last_seen", "last_seen"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
    )
    agent_version: Mapped[str] = mapped_column(String(32), nullable=False)
    capabilities: Mapped[dict] = mapped_column(
        JSON, nullable=False, default=dict, server_default="{}"
    )
    # HMAC-SHA256 hex digest of the shared_secret.  Used to look up + verify
    # incoming agent payloads.  Plaintext is returned ONCE at /register time.
    shared_secret_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    registered_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    last_seen: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    # Last connector_health JSON pushed via /heartbeat.  Cached here so the
    # admin dashboard can render agent status without a separate table read.
    connector_health: Mapped[dict] = mapped_column(
        JSON, nullable=False, default=dict, server_default="{}"
    )


# ─────────────────────────────────────────────────────────────────────────────
# RiskScoreSummary  — see backend/models/risk_snapshot.py.  We deliberately
# DO NOT redefine that table here; the agent_ingest router writes to the
# existing RiskScoreSummary model.  This keeps ONE source of truth for the
# cloud-side dashboard cache.  See DELIVERY_ARCHITECTURE.md §7.4.
# ─────────────────────────────────────────────────────────────────────────────


# ─────────────────────────────────────────────────────────────────────────────
# ConnectorHealthSummary  — per (tenant, connector) status cache
# ─────────────────────────────────────────────────────────────────────────────


class ConnectorHealthSummary(Base):
    """One row per (tenant, connector) — overwritten on each heartbeat."""

    __tablename__ = "connector_health_summaries"
    __table_args__ = (
        Index("idx_chs_tenant_conn", "tenant_id", "connector_name", unique=True),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
    )
    connector_name: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)  # ok | degraded | error
    last_poll_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    error_count_24h: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )


# ─────────────────────────────────────────────────────────────────────────────
# DrilldownRequest  — one-time-token raw-data fetch envelope
# ─────────────────────────────────────────────────────────────────────────────


class DrilldownRequest(Base):
    """
    Short-lived (60 s) request/response envelope.

    Lifecycle
    ---------
    1. Frontend POSTs /agent-ingest/drilldown-request with risk_id (or whatever
       drill-down identifier).  Cloud creates a row with a one-time token, then
       opens an SSE stream keyed by that token to the user's browser.
    2. The on-prem agent's drilldown_responder polls
       /agent-ingest/pending-requests (HMAC-authed), picks up the row, fetches
       raw data from its local DB, then POSTs back to
       /agent-ingest/drilldown-response/{token}.
    3. Cloud writes the payload into fulfilled_payload_temp + sets fulfilled_at,
       then the SSE stream forwards the payload to the user and immediately
       NULLs the column.  Token is invalidated.
    4. Tokens older than expires_at are rejected and may be GC'd.
    """

    __tablename__ = "drilldown_requests"
    __table_args__ = (
        Index("idx_drilldown_token", "token", unique=True),
        Index("idx_drilldown_tenant", "tenant_id"),
        Index("idx_drilldown_pending", "tenant_id", "fulfilled_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
    )
    requested_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    request_type: Mapped[str] = mapped_column(String(64), nullable=False)
    request_payload: Mapped[dict] = mapped_column(
        JSON, nullable=False, default=dict, server_default="{}"
    )
    # Cryptographically random one-time token (64 hex chars = 32 bytes).
    token: Mapped[str] = mapped_column(String(128), nullable=False)
    # Temporary holding cell for the raw payload between agent fulfilment and
    # SSE forward.  CONTRACT: must be NULL after forward; never persisted long-term.
    fulfilled_payload_temp: Mapped[str | None] = mapped_column(Text, nullable=True)
    requested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    fulfilled_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
