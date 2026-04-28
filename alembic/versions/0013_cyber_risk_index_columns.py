"""Add 0-100 Cyber Risk Index + sub-index + domain-bucket columns to risk_score_summaries.

Revision ID: 0013_cyber_risk_index_columns
Revises: 0012_roadmap_features
Create Date: 2026-04-27

Purpose
-------
Project_33a — TrendAI-equivalent 0-100 Cyber Risk Index dashboard.

The existing risk_score_summaries table already stores 0-10 mean_composite_score
plus severity counts.  This migration ADDS supplementary fields so each snapshot
also captures:
  - Cyber Risk Index 0-100  (single number for the dashboard top-strip)
  - level                    (low | medium | high | critical)
  - 3 sub-indexes 0-100      (exposure | attack | security_config)
  - 5 domain bucket counts + per-bucket critical counts

The 0-10 fields (mean_composite_score, etc.) are LEFT INTACT — the new columns
are a derived view that supplements rather than replaces existing scoring.
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0013_cyber_risk_index_columns"
down_revision = "0012_roadmap_features"
branch_labels = None
depends_on = None


_TABLE = "risk_score_summaries"

_NEW_FLOAT_COLS = (
    "index_0_100",
    "subindex_exposure",
    "subindex_attack",
    "subindex_security_config",
)

_NEW_INT_COLS_WITH_DEFAULT_ZERO = (
    "domain_devices_count",
    "domain_internet_facing_count",
    "domain_accounts_count",
    "domain_applications_count",
    "domain_cloud_assets_count",
    "domain_devices_critical",
    "domain_internet_facing_critical",
    "domain_accounts_critical",
    "domain_applications_critical",
    "domain_cloud_assets_critical",
)


def upgrade() -> None:
    for col in _NEW_FLOAT_COLS:
        op.add_column(_TABLE, sa.Column(col, sa.Float(), nullable=True))

    op.add_column(_TABLE, sa.Column("level", sa.String(length=10), nullable=True))

    for col in _NEW_INT_COLS_WITH_DEFAULT_ZERO:
        op.add_column(
            _TABLE,
            sa.Column(col, sa.Integer(), nullable=False, server_default="0"),
        )


def downgrade() -> None:
    for col in _NEW_INT_COLS_WITH_DEFAULT_ZERO:
        op.drop_column(_TABLE, col)
    op.drop_column(_TABLE, "level")
    for col in _NEW_FLOAT_COLS:
        op.drop_column(_TABLE, col)
