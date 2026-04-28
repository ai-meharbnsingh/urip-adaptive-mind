"""
backend/models/asset.py

Asset model — first-class entity for the URIP cross-domain inventory
(MASTER_BLUEPRINT.md §6b.1, TrendAI parity).

Design decisions
----------------
- Tenant-scoped via tenant_id (FK + index). Every query MUST go through
  apply_tenant_filter() — see backend.services.tenant_query.
- Identity is a SHA-256 fingerprint of (MAC + hostname + canonical IP) —
  the same scheme already used by backend.services.asset_fingerprint_service
  for risk de-duplication. The same fingerprint binds an Asset row to all
  Risk rows seen on it.
- Mutually-exclusive lifecycle states: in_use / decommissioned / lost /
  under_review.  A decommissioned asset stays in the table forever as an
  audit trail — connectors that re-discover it will resurrect it via
  upsert_asset().
- (tenant_id, fingerprint_key) is the natural upsert key.  We add an
  explicit index there because connectors hammer that read path.
- (tenant_id, device_category, asset_tier) is the dashboard widget index.
- custom_tags is a JSON dict (not list) so the UI can store key=value
  pairs (e.g., "owner_email": "alice@x.test", "cost_center": "FIN-42").
- source_connectors is a JSON list of connector slugs that have ever seen
  this asset — used to render "discovered by Tenable + Armis + ServiceNow"
  in the UI and for the categorize_asset() heuristic.
- asset_risk_score is float 0-10 (mirrors Risk.composite_score scale) —
  computed as max() of open risks on this asset by
  asset_service.compute_asset_risk_score().
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, Float, ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import JSON, UUID
from sqlalchemy.orm import Mapped, mapped_column

from backend.database import Base


# Allowed enum-style string values — kept here as module-level tuples so
# routers, services, and tests have one source of truth.
DEVICE_CATEGORIES: tuple[str, ...] = ("IT", "OT", "IoT", "SaaS")
ASSET_TIERS: tuple[str, ...] = ("T1", "T2", "T3", "T4")
LIFECYCLE_STATES: tuple[str, ...] = (
    "in_use",
    "decommissioned",
    "lost",
    "under_review",
)
BUSINESS_CRITICALITY_VALUES: tuple[str, ...] = ("critical", "high", "medium", "low")

# High-level asset categories used by the UI inventory grid + dashboard
# widgets.  Derived from device_type / source_connectors by
# asset_service.categorize_asset().
ASSET_CATEGORIES: tuple[str, ...] = (
    "Devices",
    "Internet-Facing Assets",
    "Accounts",
    "Applications",
    "Cloud Assets",
    "API Collections",
)


class Asset(Base):
    """
    A unique discovered asset — laptop, server, cloud workload, SaaS account,
    API collection, etc.  Each row is unique within (tenant_id, fingerprint_key).
    """

    __tablename__ = "assets"
    __table_args__ = (
        # Hot path: connector upsert lookup by fingerprint
        Index("idx_assets_tenant_fingerprint", "tenant_id", "fingerprint_key"),
        # Dashboard widget queries: category counts, tier breakdown
        Index(
            "idx_assets_tenant_category_tier",
            "tenant_id",
            "device_category",
            "asset_tier",
        ),
        # Tenant-scoped lifecycle filter
        Index("idx_assets_tenant_lifecycle", "tenant_id", "lifecycle_state"),
    )

    # ── Primary key + tenancy ─────────────────────────────────────────
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    fingerprint_key: Mapped[str] = mapped_column(String(64), nullable=False, index=True)

    # ── Identification ────────────────────────────────────────────────
    hostname: Mapped[str | None] = mapped_column(String(255), nullable=True)
    internal_ip: Mapped[str | None] = mapped_column(String(45), nullable=True)
    external_ip: Mapped[str | None] = mapped_column(String(45), nullable=True)
    mac_address: Mapped[str | None] = mapped_column(String(32), nullable=True)

    # ── Classification ────────────────────────────────────────────────
    # device_type: laptop / desktop / server / cloud_workload / mobile /
    # iot / api / saas_account
    device_type: Mapped[str | None] = mapped_column(String(40), nullable=True)
    # device_category: IT / OT / IoT / SaaS
    device_category: Mapped[str | None] = mapped_column(String(10), nullable=True)
    os_name: Mapped[str | None] = mapped_column(String(64), nullable=True)
    os_version: Mapped[str | None] = mapped_column(String(64), nullable=True)

    # ── Organisational ────────────────────────────────────────────────
    endpoint_group: Mapped[str | None] = mapped_column(String(100), nullable=True)
    asset_group: Mapped[str | None] = mapped_column(String(100), nullable=True)
    last_user: Mapped[str | None] = mapped_column(String(255), nullable=True)
    owner_team: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # ── Risk ──────────────────────────────────────────────────────────
    # T1=Critical, T2=High, T3=Medium, T4=Low.  Mirrors asset_taxonomy tier_code.
    asset_tier: Mapped[str | None] = mapped_column(String(2), nullable=True)
    business_criticality: Mapped[str | None] = mapped_column(String(10), nullable=True)
    asset_risk_score: Mapped[float | None] = mapped_column(Float, nullable=True)

    # ── Lifecycle ─────────────────────────────────────────────────────
    lifecycle_state: Mapped[str] = mapped_column(
        String(20), nullable=False, default="in_use", server_default="in_use"
    )
    discovered_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    last_seen: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    source_connectors: Mapped[list[str]] = mapped_column(
        JSON, nullable=False, default=list, server_default="[]"
    )

    # ── Custom + audit ────────────────────────────────────────────────
    custom_tags: Mapped[dict] = mapped_column(
        JSON, nullable=False, default=dict, server_default="{}"
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    def __repr__(self) -> str:  # pragma: no cover — diagnostic only
        return (
            f"<Asset id={self.id} tenant={self.tenant_id} "
            f"hostname={self.hostname!r} fp={self.fingerprint_key[:8]}…>"
        )
