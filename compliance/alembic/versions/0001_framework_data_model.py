"""Framework data model — initial migration

Creates:
  - frameworks
  - framework_versions
  - controls
  - framework_control_mappings

Revision ID: 0001
Revises: (none)
Create Date: 2026-04-27
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

# revision identifiers
revision: str = "0001"
down_revision: str | None = None
branch_labels: str | tuple[str, ...] | None = None
depends_on: str | tuple[str, ...] | None = None


def upgrade() -> None:
    # ── frameworks ─────────────────────────────────────────────────────────
    op.create_table(
        "frameworks",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("short_code", sa.String(50), nullable=False),
        sa.Column("category", sa.String(50), nullable=False, server_default="security"),
        sa.Column("description", sa.Text, nullable=True),
    )
    op.create_index("ix_frameworks_short_code", "frameworks", ["short_code"], unique=True)

    # ── framework_versions ─────────────────────────────────────────────────
    op.create_table(
        "framework_versions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "framework_id",
            sa.String(36),
            sa.ForeignKey("frameworks.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("version", sa.String(50), nullable=False),
        sa.Column("effective_date", sa.Date, nullable=True),
        sa.Column("is_current", sa.Boolean, nullable=False, server_default=sa.text("true")),
    )
    op.create_unique_constraint(
        "uq_framework_version", "framework_versions", ["framework_id", "version"]
    )
    op.create_index("ix_framework_versions_framework_id", "framework_versions", ["framework_id"])

    # ── controls ───────────────────────────────────────────────────────────
    op.create_table(
        "controls",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "framework_version_id",
            sa.String(36),
            sa.ForeignKey("framework_versions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("control_code", sa.String(50), nullable=False),
        sa.Column("category", sa.String(100), nullable=False),
        sa.Column("title", sa.String(500), nullable=True),
        sa.Column("description", sa.Text, nullable=False),
        sa.Column("rule_function", sa.String(255), nullable=True),
    )
    op.create_unique_constraint(
        "uq_control_code_in_version", "controls", ["framework_version_id", "control_code"]
    )
    op.create_index("ix_controls_framework_version_id", "controls", ["framework_version_id"])
    op.create_index("ix_controls_category", "controls", ["category"])

    # ── framework_control_mappings ─────────────────────────────────────────
    op.create_table(
        "framework_control_mappings",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "source_control_id",
            sa.String(36),
            sa.ForeignKey("controls.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "target_control_id",
            sa.String(36),
            sa.ForeignKey("controls.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("mapping_type", sa.String(20), nullable=False, server_default="equivalent"),
    )
    op.create_unique_constraint(
        "uq_control_mapping",
        "framework_control_mappings",
        ["source_control_id", "target_control_id"],
    )
    op.create_index(
        "ix_fcm_source",
        "framework_control_mappings",
        ["source_control_id"],
    )
    op.create_index(
        "ix_fcm_target",
        "framework_control_mappings",
        ["target_control_id"],
    )


def downgrade() -> None:
    op.drop_table("framework_control_mappings")
    op.drop_table("controls")
    op.drop_table("framework_versions")
    op.drop_table("frameworks")
