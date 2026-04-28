"""CSPM Module — Cloud Security Posture Management tables.

Revision ID: 0009_cspm_module
Revises: 0008_audit_fix_medium
Created: 2026-04-27

Tables created:
  - cspm_frameworks      : CIS/AWS/Azure/GCP framework definitions
  - cspm_controls        : Individual controls within a framework
  - cspm_check_results   : Per-tenant, per-control evaluation results
  - cspm_score_snapshots : Historical compliance score per cloud provider
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0009_cspm_module"
down_revision = "0008_audit_fix_medium"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name

    # Use UUID type on PostgreSQL, CHAR(32) on SQLite for compatibility
    uuid_type = postgresql.UUID(as_uuid=True) if dialect == "postgresql" else sa.CHAR(32)
    json_type = postgresql.JSON() if dialect == "postgresql" else sa.Text()

    # cspm_frameworks
    op.create_table(
        "cspm_frameworks",
        sa.Column("id", uuid_type, nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("cloud_provider", sa.String(20), nullable=False),
        sa.Column("version", sa.String(20), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_cspm_frameworks_provider", "cspm_frameworks", ["cloud_provider"])

    # cspm_controls
    op.create_table(
        "cspm_controls",
        sa.Column("id", uuid_type, nullable=False),
        sa.Column("framework_id", uuid_type, nullable=False),
        sa.Column("control_code", sa.String(50), nullable=False, index=True),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("severity", sa.String(10), nullable=False),
        sa.Column("rule_function", sa.String(100), nullable=True),
        sa.Column("affected_services", json_type, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["framework_id"], ["cspm_frameworks.id"], ondelete="CASCADE"),
    )
    op.create_index("idx_cspm_controls_framework", "cspm_controls", ["framework_id"])
    op.create_index("idx_cspm_controls_severity", "cspm_controls", ["severity"])
    op.create_index("idx_cspm_controls_rule", "cspm_controls", ["rule_function"])

    # cspm_check_results
    op.create_table(
        "cspm_check_results",
        sa.Column("id", uuid_type, nullable=False),
        sa.Column("tenant_id", uuid_type, nullable=False),
        sa.Column("control_id", uuid_type, nullable=False),
        sa.Column("cloud_account_id", sa.String(100), nullable=True),
        sa.Column("status", sa.String(15), nullable=False),
        sa.Column("evidence_json", json_type, nullable=True),
        sa.Column("run_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("failing_resource_ids", json_type, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["control_id"], ["cspm_controls.id"], ondelete="CASCADE"),
    )
    op.create_index("idx_cspm_results_tenant", "cspm_check_results", ["tenant_id"])
    op.create_index("idx_cspm_results_control", "cspm_check_results", ["control_id"])
    op.create_index("idx_cspm_results_status", "cspm_check_results", ["status"])
    op.create_index("idx_cspm_results_run_at", "cspm_check_results", ["run_at"])

    # cspm_score_snapshots
    op.create_table(
        "cspm_score_snapshots",
        sa.Column("id", uuid_type, nullable=False),
        sa.Column("tenant_id", uuid_type, nullable=False),
        sa.Column("cloud_provider", sa.String(20), nullable=False),
        sa.Column("snapshot_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("score", sa.Numeric(5, 2), nullable=False),
        sa.Column("pass_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("fail_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("inconclusive_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="RESTRICT"),
    )
    op.create_index("idx_cspm_snapshots_tenant_provider", "cspm_score_snapshots", ["tenant_id", "cloud_provider"])
    op.create_index("idx_cspm_snapshots_at", "cspm_score_snapshots", ["snapshot_at"])


def downgrade() -> None:
    op.drop_table("cspm_score_snapshots")
    op.drop_table("cspm_check_results")
    op.drop_table("cspm_controls")
    op.drop_table("cspm_frameworks")
