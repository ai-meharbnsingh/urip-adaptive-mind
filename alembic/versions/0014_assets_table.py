"""URIP first-class Asset model + risks.asset_id FK.

Revision ID: 0014_assets_table
Revises: 0013_cyber_risk_index_columns
Create Date: 2026-04-27

Purpose
-------
Project_33a — MASTER_BLUEPRINT.md §6b.1 (TrendAI parity).  The frontend
asset-inventory.html / asset-detail.html pages need a real /api/assets
endpoint; before this migration there was no `assets` table — the UI was
synthesizing pseudo-asset rows by aggregating risks.

What this migration does
------------------------
1. Creates the `assets` table with all identification, classification,
   organisational, risk, lifecycle, and audit fields.
2. Adds `risks.asset_id` (UUID, nullable, FK → assets.id, ON DELETE SET
   NULL).  Existing risk rows keep asset_id NULL until the backfill
   script (backend/seeders/backfill_assets.py) runs.
3. Indexes:
     - assets:  idx_assets_tenant_fingerprint, idx_assets_tenant_category_tier,
                idx_assets_tenant_lifecycle, plus the implicit tenant_id
                index from Column(index=True).
     - risks:   idx_risks_asset_id (single-column index on the new FK).
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "0014_assets_table"
down_revision = "0013_cyber_risk_index_columns"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name

    json_type = postgresql.JSON() if dialect == "postgresql" else sa.Text()

    op.create_table(
        "assets",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "tenant_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("fingerprint_key", sa.String(64), nullable=False),
        # Identification
        sa.Column("hostname", sa.String(255), nullable=True),
        sa.Column("internal_ip", sa.String(45), nullable=True),
        sa.Column("external_ip", sa.String(45), nullable=True),
        sa.Column("mac_address", sa.String(32), nullable=True),
        # Classification
        sa.Column("device_type", sa.String(40), nullable=True),
        sa.Column("device_category", sa.String(10), nullable=True),
        sa.Column("os_name", sa.String(64), nullable=True),
        sa.Column("os_version", sa.String(64), nullable=True),
        # Organisational
        sa.Column("endpoint_group", sa.String(100), nullable=True),
        sa.Column("asset_group", sa.String(100), nullable=True),
        sa.Column("last_user", sa.String(255), nullable=True),
        sa.Column("owner_team", sa.String(100), nullable=True),
        # Risk
        sa.Column("asset_tier", sa.String(2), nullable=True),
        sa.Column("business_criticality", sa.String(10), nullable=True),
        sa.Column("asset_risk_score", sa.Float(), nullable=True),
        # Lifecycle
        sa.Column(
            "lifecycle_state",
            sa.String(20),
            nullable=False,
            server_default="in_use",
        ),
        sa.Column("discovered_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "source_connectors",
            json_type,
            nullable=False,
            server_default="[]",
        ),
        # Custom + audit
        sa.Column("custom_tags", json_type, nullable=False, server_default="{}"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_index("ix_assets_tenant_id", "assets", ["tenant_id"])
    op.create_index("ix_assets_fingerprint_key", "assets", ["fingerprint_key"])
    op.create_index(
        "idx_assets_tenant_fingerprint",
        "assets",
        ["tenant_id", "fingerprint_key"],
    )
    op.create_index(
        "idx_assets_tenant_category_tier",
        "assets",
        ["tenant_id", "device_category", "asset_tier"],
    )
    op.create_index(
        "idx_assets_tenant_lifecycle",
        "assets",
        ["tenant_id", "lifecycle_state"],
    )

    # Add asset_id FK to risks table
    op.add_column(
        "risks",
        sa.Column(
            "asset_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            sa.ForeignKey("assets.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.create_index("idx_risks_asset_id", "risks", ["asset_id"])


def downgrade() -> None:
    op.drop_index("idx_risks_asset_id", table_name="risks")
    op.drop_column("risks", "asset_id")

    op.drop_index("idx_assets_tenant_lifecycle", table_name="assets")
    op.drop_index("idx_assets_tenant_category_tier", table_name="assets")
    op.drop_index("idx_assets_tenant_fingerprint", table_name="assets")
    op.drop_index("ix_assets_fingerprint_key", table_name="assets")
    op.drop_index("ix_assets_tenant_id", table_name="assets")

    op.drop_table("assets")
