"""Auditor portal + compliance scoring — P2B.10 + P2B.11

Creates:
  - auditor_access
  - evidence_requests
  - auditor_activity_log
  - compliance_score_snapshots

Also serves as a MERGE revision resolving the three parallel "0002" heads
(control_runs_and_evidence, policy_management, vendor_risk) created by
parallel agent workstreams. After this revision the alembic chain is
linear: 0001 → {0002 heads} → 0003.

Revision ID: 0003
Revises: 0002 (control_runs_and_evidence), 0002_policy_management, 0002_vendor_risk
Create Date: 2026-04-27

Notes for operators:
  Because the three 0002 files all declare revision="0002", alembic will
  refuse to upgrade past them as written. Before applying this migration
  the operator MUST renumber the duplicate revision identifiers (suggested:
  0002a/0002b/0002c) and update down_revision pointers. This file then
  ties them together via a tuple in down_revision.

  All columns use String(36) for UUID portability across SQLite (tests) and
  Postgres (prod) — same convention as 0001.
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

# revision identifiers
revision: str = "0003"
# Merge head — depends on all three 0002 branches.
# Operators: rename duplicate "0002" revs to 0002a/0002b/0002c and update this tuple.
down_revision: tuple[str, ...] | str = (
    "0002",  # control_runs_and_evidence
    "0002_policy_management",  # policy
    "0002_vendor_risk",  # vendor
)
branch_labels: str | tuple[str, ...] | None = None
depends_on: str | tuple[str, ...] | None = None


def upgrade() -> None:
    # ── auditor_access ─────────────────────────────────────────────────────
    op.create_table(
        "auditor_access",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(255), nullable=False),
        sa.Column("auditor_email", sa.String(320), nullable=False),
        sa.Column("framework_id", sa.String(36), nullable=False),
        sa.Column("audit_period_start", sa.DateTime, nullable=False),
        sa.Column("audit_period_end", sa.DateTime, nullable=False),
        sa.Column("invited_by_user_id", sa.String(255), nullable=False),
        sa.Column("invitation_token_hash", sa.String(128), nullable=False),
        sa.Column("accepted_at", sa.DateTime, nullable=True),
        sa.Column("expires_at", sa.DateTime, nullable=False),
        sa.Column("is_revoked", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime, nullable=False),
    )
    op.create_unique_constraint(
        "uq_auditor_access_token_hash", "auditor_access", ["invitation_token_hash"]
    )
    op.create_index("ix_auditor_access_tenant_id", "auditor_access", ["tenant_id"])
    op.create_index("ix_auditor_access_auditor_email", "auditor_access", ["auditor_email"])
    op.create_index("ix_auditor_access_framework_id", "auditor_access", ["framework_id"])
    op.create_index(
        "ix_auditor_access_tenant_framework",
        "auditor_access",
        ["tenant_id", "framework_id"],
    )

    # ── evidence_requests ──────────────────────────────────────────────────
    op.create_table(
        "evidence_requests",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "auditor_access_id",
            sa.String(36),
            sa.ForeignKey("auditor_access.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("control_id", sa.String(36), nullable=True),
        sa.Column("description", sa.Text, nullable=False),
        sa.Column("requested_at", sa.DateTime, nullable=False),
        sa.Column("fulfilled_at", sa.DateTime, nullable=True),
        sa.Column("fulfilled_by_user_id", sa.String(255), nullable=True),
        sa.Column("fulfillment_evidence_id", sa.String(36), nullable=True),
    )
    op.create_index(
        "ix_evidence_requests_auditor_access_id",
        "evidence_requests",
        ["auditor_access_id"],
    )
    op.create_index(
        "ix_evidence_requests_control_id", "evidence_requests", ["control_id"]
    )

    # ── auditor_activity_log ───────────────────────────────────────────────
    op.create_table(
        "auditor_activity_log",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(255), nullable=False),
        sa.Column("auditor_access_id", sa.String(36), nullable=False),
        sa.Column("auditor_email", sa.String(320), nullable=False),
        sa.Column("action", sa.String(64), nullable=False),
        sa.Column("target_type", sa.String(50), nullable=True),
        sa.Column("target_id", sa.String(64), nullable=True),
        sa.Column("accessed_at", sa.DateTime, nullable=False),
        sa.Column("ip_address", sa.String(64), nullable=True),
    )
    op.create_index(
        "ix_auditor_activity_log_tenant_id", "auditor_activity_log", ["tenant_id"]
    )
    op.create_index(
        "ix_auditor_activity_log_action", "auditor_activity_log", ["action"]
    )
    op.create_index(
        "ix_auditor_activity_log_accessed_at",
        "auditor_activity_log",
        ["accessed_at"],
    )
    op.create_index(
        "ix_auditor_activity_log_aa_id", "auditor_activity_log", ["auditor_access_id"]
    )
    op.create_index(
        "ix_auditor_activity_tenant_time",
        "auditor_activity_log",
        ["tenant_id", "accessed_at"],
    )

    # ── compliance_score_snapshots ─────────────────────────────────────────
    op.create_table(
        "compliance_score_snapshots",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(255), nullable=False),
        sa.Column("framework_id", sa.String(36), nullable=False),
        sa.Column("snapshot_date", sa.DateTime, nullable=False),
        sa.Column("score", sa.Float, nullable=False),
        sa.Column("pass_count", sa.Integer, nullable=False, server_default=sa.text("0")),
        sa.Column("fail_count", sa.Integer, nullable=False, server_default=sa.text("0")),
        sa.Column("inconclusive_count", sa.Integer, nullable=False, server_default=sa.text("0")),
        sa.Column("total_applicable", sa.Integer, nullable=False, server_default=sa.text("0")),
    )
    op.create_index(
        "ix_compliance_score_snapshots_tenant_id",
        "compliance_score_snapshots",
        ["tenant_id"],
    )
    op.create_index(
        "ix_compliance_score_snapshots_framework_id",
        "compliance_score_snapshots",
        ["framework_id"],
    )
    op.create_index(
        "ix_compliance_score_snapshots_snapshot_date",
        "compliance_score_snapshots",
        ["snapshot_date"],
    )
    op.create_index(
        "ix_score_snapshot_tenant_fw_date",
        "compliance_score_snapshots",
        ["tenant_id", "framework_id", "snapshot_date"],
    )


def downgrade() -> None:
    op.drop_table("compliance_score_snapshots")
    op.drop_table("auditor_activity_log")
    op.drop_table("evidence_requests")
    op.drop_table("auditor_access")
