"""Control runs and evidence tables — P2B.3 + P2B.4

Creates:
  - control_check_runs
  - evidence

Revision ID: 0002
Revises: 0001
Create Date: 2026-04-27
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

# revision identifiers
revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | tuple[str, ...] | None = None
depends_on: str | tuple[str, ...] | None = None


def upgrade() -> None:
    # ── control_check_runs ─────────────────────────────────────────────────
    op.create_table(
        "control_check_runs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "control_id",
            sa.String(36),
            sa.ForeignKey("controls.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("tenant_id", sa.String(255), nullable=False),
        sa.Column("run_at", sa.DateTime, nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("evidence_ids", sa.JSON, nullable=True),
        sa.Column("failure_reason", sa.Text, nullable=True),
    )
    op.create_index("ix_control_check_runs_control_id", "control_check_runs", ["control_id"])
    op.create_index("ix_control_check_runs_tenant_id", "control_check_runs", ["tenant_id"])
    op.create_index(
        "ix_control_check_runs_tenant_control",
        "control_check_runs",
        ["tenant_id", "control_id"],
    )

    # ── evidence ───────────────────────────────────────────────────────────
    op.create_table(
        "evidence",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "control_id",
            sa.String(36),
            sa.ForeignKey("controls.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("framework_id", sa.String(36), nullable=True),
        sa.Column("tenant_id", sa.String(255), nullable=False),
        sa.Column("type", sa.String(50), nullable=False),
        sa.Column("storage_uri", sa.Text, nullable=False),
        sa.Column("audit_period", sa.String(50), nullable=False),
        sa.Column("captured_at", sa.DateTime, nullable=False),
        sa.Column("captured_by", sa.String(255), nullable=False, server_default="system"),
        sa.Column("metadata_json", sa.JSON, nullable=True),
    )
    op.create_index("ix_evidence_control_id", "evidence", ["control_id"])
    op.create_index("ix_evidence_tenant_id", "evidence", ["tenant_id"])
    op.create_index("ix_evidence_framework_id", "evidence", ["framework_id"])
    op.create_index(
        "ix_evidence_tenant_period",
        "evidence",
        ["tenant_id", "audit_period"],
    )


def downgrade() -> None:
    op.drop_table("evidence")
    op.drop_table("control_check_runs")
