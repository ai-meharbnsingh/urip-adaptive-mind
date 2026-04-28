"""Add tenant_asset_taxonomy table for P1.4 tenant-configurable asset taxonomy.

Revision ID: 0004_tenant_asset_taxonomy
Revises: 0003_tenant_connector_credentials
Create Date: 2026-04-27

Changes
-------
1. Create `tenant_asset_taxonomy` table:
   - id (UUID PK)
   - tenant_id (UUID FK → tenants.id CASCADE)
   - tier_code (VARCHAR 2)  — one of T1/T2/T3/T4
   - keyword (VARCHAR 500)  — regex pattern (case-insensitive at lookup time)
   - asset_type (VARCHAR 100, nullable) — optional scope (future use)
   - created_by_user_id (UUID FK → users.id ON DELETE SET NULL, nullable)
   - created_at / updated_at (TIMESTAMPTZ)
   - deleted_at (TIMESTAMPTZ, nullable) — soft-delete marker
   - Indexes:
       idx_tat_tenant_id          (tenant_id)
       idx_tat_tenant_tier        (tenant_id, tier_code)
       idx_tat_deleted_at         (deleted_at)

Rationale
---------
Separate table rather than a JSONB array on tenants.settings:
- Bulk imports of hundreds of patterns must not bloat every tenant settings read.
- Need indexes on (tenant_id, tier_code, deleted_at) for fast lookup.
- Soft-delete with a column is cleaner than JSON array manipulation.
- Future audit trail on `created_by_user_id` is trivial here, awkward in JSON.

Backwards compat
----------------
The legacy backend/config/tier_keywords.json file remains in place and is
used as the transition default whenever a tenant has zero rows in this
table.  Tenants opt-in to per-tenant taxonomy by calling
POST /api/asset-taxonomy/import-defaults (or by adding keywords directly).
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers
revision = "0004_tenant_asset_taxonomy"
down_revision = "0003_tenant_connector_credentials"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "tenant_asset_taxonomy",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("tier_code", sa.String(2), nullable=False),
        sa.Column("keyword", sa.String(500), nullable=False),
        sa.Column("asset_type", sa.String(100), nullable=True),
        sa.Column(
            "created_by_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "deleted_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )

    op.create_index(
        "idx_tat_tenant_id",
        "tenant_asset_taxonomy",
        ["tenant_id"],
    )
    op.create_index(
        "idx_tat_tenant_tier",
        "tenant_asset_taxonomy",
        ["tenant_id", "tier_code"],
    )
    op.create_index(
        "idx_tat_deleted_at",
        "tenant_asset_taxonomy",
        ["deleted_at"],
    )


def downgrade() -> None:
    op.drop_index("idx_tat_deleted_at", table_name="tenant_asset_taxonomy")
    op.drop_index("idx_tat_tenant_tier", table_name="tenant_asset_taxonomy")
    op.drop_index("idx_tat_tenant_id", table_name="tenant_asset_taxonomy")
    op.drop_table("tenant_asset_taxonomy")
