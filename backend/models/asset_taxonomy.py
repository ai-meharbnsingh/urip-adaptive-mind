"""
backend/models/asset_taxonomy.py

P1.4: Tenant-configurable asset taxonomy.

Each row associates one regex keyword pattern with a tier code (T1-T4) for a
specific tenant.  Replaces the hardcoded Royal-Enfield-flavoured
`tier_keywords.json` with per-tenant configurability while preserving the
legacy JSON as the transition default (used only when a tenant has zero
keywords loaded).

Design decisions
----------------
- Separate table (NOT JSONB on tenants.settings) because:
    * scales to bulk imports (hundreds of patterns per tenant) without
      bloating every tenant settings read,
    * supports proper indexes on (tenant_id, tier_code, deleted_at),
    * soft-delete column lets us preserve audit trail of removed keywords,
    * future-friendly: admin UI can show created_by_user_id, created_at,
      etc. without parsing JSON.
- One tenant can own MANY keywords per tier (no uniqueness across keyword
  text — duplicates are surfaced in the UI, not blocked at DB level, because
  near-duplicates like "\\bsap\\b" vs "sap" are both legitimate patterns).
- `tier_code` is the canonical T1/T2/T3/T4 string (not int) so the API
  contract is stable across SDKs and matches the way tiers appear in the
  product UI.
- `asset_type` is optional; null means "matches any asset type".  Reserved
  for future per-asset-type scoping (e.g., a SCADA-specific keyword that
  should only be considered when the asset_type is OT/ICS).
- `deleted_at` is the soft-delete marker; queries always filter
  `deleted_at IS NULL` unless explicitly fetching history.
- `created_by_user_id` is nullable because seeded defaults (from
  import-defaults endpoint) are not attributable to a single human.

FK behaviour
------------
- `tenant_id`  → tenants.id ON DELETE CASCADE — when a tenant is deleted,
  all their taxonomy rows go with it.  (Consistent with
  tenant_connector_credentials.)
- `created_by_user_id` → users.id ON DELETE SET NULL — preserve the row
  even if the user account is later removed.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Index, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from backend.database import Base

# Allowed tier codes — matches the integer tiers (1-4) used elsewhere in the
# scoring engine.  Kept as a module-level constant so routers / schemas can
# import the same source of truth.
TIER_CODES: tuple[str, ...] = ("T1", "T2", "T3", "T4")

# Mapping helpers — keeps the rest of the codebase using ints.
TIER_CODE_TO_INT: dict[str, int] = {"T1": 1, "T2": 2, "T3": 3, "T4": 4}
TIER_INT_TO_CODE: dict[int, str] = {v: k for k, v in TIER_CODE_TO_INT.items()}


class TenantAssetTaxonomy(Base):
    """One row = one keyword pattern assigned to a tier for a tenant."""

    __tablename__ = "tenant_asset_taxonomy"
    __table_args__ = (
        # Hot path: "give me all live keywords for tenant X" — covered by both
        # tenant_id and (tenant_id, tier_code) lookups.
        Index("idx_tat_tenant_id", "tenant_id"),
        Index("idx_tat_tenant_tier", "tenant_id", "tier_code"),
        # Soft-delete index — the lookup helper always filters deleted_at IS NULL.
        Index("idx_tat_deleted_at", "deleted_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
    )
    tier_code: Mapped[str] = mapped_column(String(2), nullable=False)
    keyword: Mapped[str] = mapped_column(String(500), nullable=False)
    asset_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        default=None,
    )

    def __repr__(self) -> str:  # pragma: no cover — diagnostic only
        live = "" if self.deleted_at is None else " DELETED"
        return (
            f"<TenantAssetTaxonomy {self.tier_code} "
            f"tenant={self.tenant_id} kw={self.keyword!r}{live}>"
        )
