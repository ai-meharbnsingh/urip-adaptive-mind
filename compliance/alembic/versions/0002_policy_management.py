"""Policy Management data model

Creates:
  - policies
  - policy_versions
  - policy_acknowledgments

Revision ID: 0002_policy_management
Revises: 0001
Create Date: 2026-04-27
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

# revision identifiers
revision: str = "0002_policy_management"
down_revision: str = "0001"
branch_labels: str | tuple[str, ...] | None = None
depends_on: str | tuple[str, ...] | None = None


def upgrade() -> None:
    # ── policies (without FK first to resolve circular dependency) ──────────
    op.create_table(
        "policies",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("owner_user_id", sa.String(36), nullable=False),
        sa.Column("current_version_id", sa.String(36), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.text("true")),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
    )
    op.create_index("ix_policies_tenant_id", "policies", ["tenant_id"])

    # ── policy_versions ────────────────────────────────────────────────────
    op.create_table(
        "policy_versions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "policy_id",
            sa.String(36),
            sa.ForeignKey("policies.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("version_number", sa.Integer, nullable=False),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("published_by_user_id", sa.String(36), nullable=True),
        sa.Column("change_summary", sa.Text, nullable=True),
    )
    op.create_index("ix_policy_versions_policy_id", "policy_versions", ["policy_id"])

    # Add circular FK now that policy_versions exists
    op.create_foreign_key(
        "fk_policies_current_version",
        "policies",
        "policy_versions",
        ["current_version_id"],
        ["id"],
        ondelete="SET NULL",
    )

    # ── policy_acknowledgments ─────────────────────────────────────────────
    op.create_table(
        "policy_acknowledgments",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "policy_version_id",
            sa.String(36),
            sa.ForeignKey("policy_versions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("user_id", sa.String(36), nullable=False),
        sa.Column("tenant_id", sa.String(36), nullable=False),
        sa.Column(
            "acknowledged_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column("signature", sa.String(500), nullable=False),
    )
    op.create_unique_constraint(
        "uq_ack_version_user",
        "policy_acknowledgments",
        ["policy_version_id", "user_id"],
    )
    op.create_index("ix_policy_ack_tenant_id", "policy_acknowledgments", ["tenant_id"])


def downgrade() -> None:
    op.drop_table("policy_acknowledgments")
    op.drop_constraint("fk_policies_current_version", "policies", type_="foreignkey")
    op.drop_table("policy_versions")
    op.drop_table("policies")
