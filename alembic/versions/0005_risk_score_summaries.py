"""Add risk_score_summaries table for per-tenant aggregate risk snapshots (§7.4).

Revision ID: 0005_risk_score_summaries
Revises: 0004_tenant_asset_taxonomy
Create Date: 2026-04-27

Purpose
-------
Cloud-side aggregate snapshot table.  Keeps the dashboard usable when the
on-prem agent is offline (DELIVERY_ARCHITECTURE.md §7.4 — RiskScoreSnapshot).

One row per (tenant_id, snapshot_at).  Written:
  - hourly by the nightly batch (write_snapshots_for_all_tenants)
  - on-demand via POST /api/risk-summary/snapshot

Columns
-------
  id                    UUID PK
  tenant_id             UUID FK → tenants.id RESTRICT (indexed)
  snapshot_at           TIMESTAMPTZ (indexed)
  total_risks           INTEGER
  critical_count        INTEGER
  high_count            INTEGER
  medium_count          INTEGER
  low_count             INTEGER
  info_count            INTEGER
  exploit_active_count  INTEGER  (epss > 0.7 AND status open)
  kev_active_count      INTEGER  (in_kev_catalog AND status open)
  mean_ttr_hours        FLOAT nullable (mean time-to-remediate last 30d)
  mean_composite_score  FLOAT nullable (mean composite_score of open risks)
  top_sources_json      TEXT nullable (JSON array of top-5 connectors)
  module_breakdown_json TEXT nullable (JSON object domain→count)
  created_at            TIMESTAMPTZ

Indexes
-------
  ix_risk_score_summary_tenant_at  (tenant_id, snapshot_at)  — composite for trend queries
  ix_rss_tenant_id                 (tenant_id)               — FK lookup
  ix_rss_snapshot_at               (snapshot_at)             — time-range scans
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0005_risk_score_summaries"
down_revision = "0004_tenant_asset_taxonomy"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "risk_score_summaries",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
        ),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "snapshot_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column("total_risks", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("critical_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("high_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("medium_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("low_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("info_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("exploit_active_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("kev_active_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("mean_ttr_hours", sa.Float(), nullable=True),
        sa.Column("mean_composite_score", sa.Float(), nullable=True),
        sa.Column("top_sources_json", sa.Text(), nullable=True),
        sa.Column("module_breakdown_json", sa.Text(), nullable=True),
        sa.Column(
            "extra_metrics",
            postgresql.JSON(astext_type=sa.Text()),
            nullable=False,
            server_default="{}",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )

    # Composite index — primary access pattern for trend queries
    op.create_index(
        "ix_risk_score_summary_tenant_at",
        "risk_score_summaries",
        ["tenant_id", "snapshot_at"],
    )
    # Individual indexes — FK lookups and time-range scans
    op.create_index(
        "ix_rss_tenant_id",
        "risk_score_summaries",
        ["tenant_id"],
    )
    op.create_index(
        "ix_rss_snapshot_at",
        "risk_score_summaries",
        ["snapshot_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_rss_snapshot_at", table_name="risk_score_summaries")
    op.drop_index("ix_rss_tenant_id", table_name="risk_score_summaries")
    op.drop_index("ix_risk_score_summary_tenant_at", table_name="risk_score_summaries")
    op.drop_table("risk_score_summaries")
