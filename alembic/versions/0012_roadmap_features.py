"""Roadmap features — bidirectional ticketing, Trust Center, Auto-Remediation Phase 2.

Revision ID: 0012_roadmap_features
Revises: 0011_merge_vapt_intelligence
Created: 2026-04-27

Adds:
  - risks.ticket_id          (string, nullable, indexed)
  - risks.ticket_provider    (string, nullable)
  - trust_center_documents
  - trust_center_access_requests
  - auto_remediation_executions
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0012_roadmap_features"
down_revision = "0011_merge_vapt_intelligence"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name
    uuid_type = postgresql.UUID(as_uuid=True) if dialect == "postgresql" else sa.CHAR(32)
    json_type = postgresql.JSON if dialect == "postgresql" else sa.Text

    # ─── risks.ticket_id / ticket_provider ───
    op.add_column("risks", sa.Column("ticket_id", sa.String(64), nullable=True))
    op.add_column("risks", sa.Column("ticket_provider", sa.String(20), nullable=True))
    op.create_index("idx_risks_ticket_id", "risks", ["ticket_id"])

    # ─── trust_center_documents ───
    op.create_table(
        "trust_center_documents",
        sa.Column("id", uuid_type, nullable=False),
        sa.Column("tenant_id", uuid_type, nullable=False),
        sa.Column("doc_type", sa.String(40), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("file_storage_uri", sa.String(1024), nullable=False),
        sa.Column("valid_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_published", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("requires_nda", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="RESTRICT"),
    )
    op.create_index("idx_trust_docs_tenant", "trust_center_documents", ["tenant_id"])
    op.create_index(
        "idx_trust_docs_published", "trust_center_documents", ["tenant_id", "is_published"]
    )

    # ─── trust_center_access_requests ───
    op.create_table(
        "trust_center_access_requests",
        sa.Column("id", uuid_type, nullable=False),
        sa.Column("tenant_id", uuid_type, nullable=False),
        sa.Column("requesting_doc_id", uuid_type, nullable=False),
        sa.Column("requester_email", sa.String(255), nullable=False),
        sa.Column("requester_name", sa.String(255), nullable=True),
        sa.Column("requester_company", sa.String(255), nullable=True),
        sa.Column("requester_purpose", sa.Text, nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("nda_signed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("nda_signature_text", sa.Text, nullable=True),
        sa.Column("granted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("granted_by_user_id", uuid_type, nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("access_token_hash", sa.String(64), nullable=True),
        sa.Column("download_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["requesting_doc_id"], ["trust_center_documents.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(["granted_by_user_id"], ["users.id"]),
    )
    op.create_index("idx_trust_reqs_tenant", "trust_center_access_requests", ["tenant_id"])
    op.create_index("idx_trust_reqs_status", "trust_center_access_requests", ["status"])
    op.create_index("idx_trust_reqs_token_hash", "trust_center_access_requests", ["access_token_hash"])
    op.create_index("idx_trust_reqs_doc", "trust_center_access_requests", ["requesting_doc_id"])

    # ─── auto_remediation_executions ───
    op.create_table(
        "auto_remediation_executions",
        sa.Column("id", uuid_type, nullable=False),
        sa.Column("tenant_id", uuid_type, nullable=False),
        sa.Column("risk_id", uuid_type, nullable=False),
        sa.Column("executor_name", sa.String(40), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("dry_run", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("services_affected", json_type, nullable=True),
        sa.Column("expected_downtime_minutes", sa.Integer(), nullable=True),
        sa.Column("rollback_plan", sa.Text, nullable=True),
        sa.Column("before_state", json_type, nullable=True),
        sa.Column("after_state", json_type, nullable=True),
        sa.Column("retest_passed", sa.Boolean(), nullable=True),
        sa.Column("retest_details", json_type, nullable=True),
        sa.Column("approver_user_id", uuid_type, nullable=True),
        sa.Column("auto_approved", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("error_message", sa.Text, nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["risk_id"], ["risks.id"]),
        sa.ForeignKeyConstraint(["approver_user_id"], ["users.id"]),
    )
    op.create_index("idx_auto_rem_tenant", "auto_remediation_executions", ["tenant_id"])
    op.create_index("idx_auto_rem_risk", "auto_remediation_executions", ["risk_id"])
    op.create_index("idx_auto_rem_status", "auto_remediation_executions", ["status"])
    op.create_index("idx_auto_rem_executor", "auto_remediation_executions", ["executor_name"])


def downgrade() -> None:
    op.drop_index("idx_auto_rem_executor", table_name="auto_remediation_executions")
    op.drop_index("idx_auto_rem_status", table_name="auto_remediation_executions")
    op.drop_index("idx_auto_rem_risk", table_name="auto_remediation_executions")
    op.drop_index("idx_auto_rem_tenant", table_name="auto_remediation_executions")
    op.drop_table("auto_remediation_executions")

    op.drop_index("idx_trust_reqs_doc", table_name="trust_center_access_requests")
    op.drop_index("idx_trust_reqs_token_hash", table_name="trust_center_access_requests")
    op.drop_index("idx_trust_reqs_status", table_name="trust_center_access_requests")
    op.drop_index("idx_trust_reqs_tenant", table_name="trust_center_access_requests")
    op.drop_table("trust_center_access_requests")

    op.drop_index("idx_trust_docs_published", table_name="trust_center_documents")
    op.drop_index("idx_trust_docs_tenant", table_name="trust_center_documents")
    op.drop_table("trust_center_documents")

    op.drop_index("idx_risks_ticket_id", table_name="risks")
    op.drop_column("risks", "ticket_provider")
    op.drop_column("risks", "ticket_id")
