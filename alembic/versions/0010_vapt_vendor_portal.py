"""VAPT Vendor Portal — vendors, invitations, submissions tables.

Revision ID: 0010_vapt_vendor_portal
Revises: 0009_cspm_module
Created: 2026-04-27

Tables created:
  - vapt_vendors             : per-tenant VAPT vendors
  - vapt_vendor_invitations  : SHA-256-hashed invitation tokens
  - vapt_submissions         : findings submitted by vendors (auto-link to risks)
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0010_vapt_vendor_portal"
down_revision = "0009_cspm_module"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name

    uuid_type = postgresql.UUID(as_uuid=True) if dialect == "postgresql" else sa.CHAR(32)

    # ─── vapt_vendors ────────────────────────────────────────────
    op.create_table(
        "vapt_vendors",
        sa.Column("id", uuid_type, nullable=False),
        sa.Column("tenant_id", uuid_type, nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("contact_name", sa.String(255), nullable=True),
        sa.Column("contact_email", sa.String(255), nullable=False),
        sa.Column("organization", sa.String(255), nullable=True),
        sa.Column(
            "status",
            sa.String(20),
            nullable=False,
            server_default="active",
        ),
        sa.Column("invited_by_user_id", uuid_type, nullable=False),
        sa.Column("invited_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["invited_by_user_id"], ["users.id"]),
    )
    op.create_index("idx_vapt_vendors_tenant_id", "vapt_vendors", ["tenant_id"])
    op.create_index("idx_vapt_vendors_status", "vapt_vendors", ["status"])
    op.create_index("idx_vapt_vendors_email", "vapt_vendors", ["contact_email"])

    # ─── vapt_vendor_invitations ─────────────────────────────────
    op.create_table(
        "vapt_vendor_invitations",
        sa.Column("id", uuid_type, nullable=False),
        sa.Column("vapt_vendor_id", uuid_type, nullable=False),
        sa.Column(
            "invitation_token_hash", sa.String(64), nullable=False, unique=True
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("invited_by_user_id", uuid_type, nullable=False),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["vapt_vendor_id"], ["vapt_vendors.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["invited_by_user_id"], ["users.id"]),
    )
    op.create_index(
        "idx_vapt_invites_vendor", "vapt_vendor_invitations", ["vapt_vendor_id"]
    )
    op.create_index(
        "idx_vapt_invites_hash",
        "vapt_vendor_invitations",
        ["invitation_token_hash"],
    )

    # ─── vapt_submissions ────────────────────────────────────────
    op.create_table(
        "vapt_submissions",
        sa.Column("id", uuid_type, nullable=False),
        sa.Column("vapt_vendor_id", uuid_type, nullable=False),
        sa.Column("tenant_id", uuid_type, nullable=False),
        sa.Column("finding_title", sa.String(500), nullable=False),
        sa.Column("cve_id", sa.String(30), nullable=True),
        sa.Column("cvss_score", sa.Numeric(3, 1), nullable=False),
        sa.Column("severity", sa.String(10), nullable=False),
        sa.Column("affected_asset_hostname", sa.String(255), nullable=True),
        sa.Column("affected_asset_ip", sa.String(45), nullable=True),
        sa.Column("exploit_maturity", sa.String(20), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("remediation_recommendation", sa.Text(), nullable=True),
        sa.Column("evidence_storage_uri", sa.String(1024), nullable=True),
        sa.Column("evidence_filename", sa.String(500), nullable=True),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "status",
            sa.String(20),
            nullable=False,
            server_default="submitted",
        ),
        sa.Column("risk_record_id", uuid_type, nullable=True),
        sa.Column(
            "retest_requested_at", sa.DateTime(timezone=True), nullable=True
        ),
        sa.Column("retest_requested_by_user_id", uuid_type, nullable=True),
        sa.Column(
            "retest_completed_at", sa.DateTime(timezone=True), nullable=True
        ),
        sa.Column("retest_result", sa.String(10), nullable=True),
        sa.Column("retest_evidence_uri", sa.String(1024), nullable=True),
        sa.Column("retest_notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["vapt_vendor_id"], ["vapt_vendors.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["risk_record_id"], ["risks.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(["retest_requested_by_user_id"], ["users.id"]),
    )
    op.create_index("idx_vapt_subs_tenant", "vapt_submissions", ["tenant_id"])
    op.create_index(
        "idx_vapt_subs_vendor", "vapt_submissions", ["vapt_vendor_id"]
    )
    op.create_index("idx_vapt_subs_status", "vapt_submissions", ["status"])
    op.create_index("idx_vapt_subs_severity", "vapt_submissions", ["severity"])
    op.create_index("idx_vapt_subs_risk", "vapt_submissions", ["risk_record_id"])


def downgrade() -> None:
    op.drop_index("idx_vapt_subs_risk", table_name="vapt_submissions")
    op.drop_index("idx_vapt_subs_severity", table_name="vapt_submissions")
    op.drop_index("idx_vapt_subs_status", table_name="vapt_submissions")
    op.drop_index("idx_vapt_subs_vendor", table_name="vapt_submissions")
    op.drop_index("idx_vapt_subs_tenant", table_name="vapt_submissions")
    op.drop_table("vapt_submissions")

    op.drop_index(
        "idx_vapt_invites_hash", table_name="vapt_vendor_invitations"
    )
    op.drop_index(
        "idx_vapt_invites_vendor", table_name="vapt_vendor_invitations"
    )
    op.drop_table("vapt_vendor_invitations")

    op.drop_index("idx_vapt_vendors_email", table_name="vapt_vendors")
    op.drop_index("idx_vapt_vendors_status", table_name="vapt_vendors")
    op.drop_index("idx_vapt_vendors_tenant_id", table_name="vapt_vendors")
    op.drop_table("vapt_vendors")
