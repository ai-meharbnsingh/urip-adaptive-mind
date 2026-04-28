"""Vendor / Third-Party Risk data model — migration

Creates:
  - vendors
  - vendor_questionnaires
  - vendor_documents
  - vendor_risk_scores

Revision ID: 0002_vendor_risk
Revises: 0001
Create Date: 2026-04-27
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision: str = "0002_vendor_risk"
down_revision: str | None = "0001"
branch_labels: str | tuple[str, ...] | None = None
depends_on: str | tuple[str, ...] | None = None


def upgrade() -> None:
    # ── vendors ────────────────────────────────────────────────────────────
    op.create_table(
        "vendors",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(255), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("criticality", sa.String(20), nullable=False),
        sa.Column("contact_email", sa.String(255), nullable=True),
        sa.Column("contact_name", sa.String(255), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        sa.Column("onboarded_at", sa.DateTime, nullable=False),
        sa.Column("next_review_at", sa.Date, nullable=False),
        sa.CheckConstraint(
            "criticality IN ('low','medium','high','critical')",
            name="ck_vendor_criticality",
        ),
        sa.CheckConstraint(
            "status IN ('active','under_review','terminated')",
            name="ck_vendor_status",
        ),
    )
    op.create_index("ix_vendors_tenant_id", "vendors", ["tenant_id"])

    # ── vendor_questionnaires ──────────────────────────────────────────────
    op.create_table(
        "vendor_questionnaires",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "vendor_id",
            sa.String(36),
            sa.ForeignKey("vendors.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("template_name", sa.String(255), nullable=False),
        sa.Column("sent_at", sa.DateTime, nullable=False),
        sa.Column("due_at", sa.Date, nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("responses_json", sa.JSON, nullable=True),
        sa.CheckConstraint(
            "status IN ('pending','in_progress','completed')",
            name="ck_vendor_questionnaire_status",
        ),
    )
    op.create_index("ix_vendor_questionnaires_vendor_id", "vendor_questionnaires", ["vendor_id"])

    # ── vendor_documents ───────────────────────────────────────────────────
    op.create_table(
        "vendor_documents",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "vendor_id",
            sa.String(36),
            sa.ForeignKey("vendors.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("document_type", sa.String(30), nullable=False),
        sa.Column("filename", sa.String(500), nullable=False),
        sa.Column("storage_uri", sa.Text, nullable=False),
        sa.Column("valid_from", sa.Date, nullable=True),
        sa.Column("valid_until", sa.Date, nullable=True),
        sa.Column("uploaded_at", sa.DateTime, nullable=False),
        sa.Column("uploaded_by_user_id", sa.String(255), nullable=False),
        sa.CheckConstraint(
            "document_type IN ('DPA','BAA','ISO_CERT','SOC2_REPORT','CONTRACT','INSURANCE','OTHER')",
            name="ck_vendor_document_type",
        ),
    )
    op.create_index("ix_vendor_documents_vendor_id", "vendor_documents", ["vendor_id"])
    op.create_index("ix_vendor_documents_valid_until", "vendor_documents", ["valid_until"])

    # ── vendor_risk_scores ────────────────────────────────────────────────
    op.create_table(
        "vendor_risk_scores",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "vendor_id",
            sa.String(36),
            sa.ForeignKey("vendors.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("score", sa.Integer, nullable=False),
        sa.Column("calculated_at", sa.DateTime, nullable=False),
        sa.Column("factors_json", sa.JSON, nullable=True),
        sa.CheckConstraint("score >= 0 AND score <= 100", name="ck_vendor_risk_score_range"),
    )
    op.create_index("ix_vendor_risk_scores_vendor_id", "vendor_risk_scores", ["vendor_id"])


def downgrade() -> None:
    op.drop_table("vendor_risk_scores")
    op.drop_table("vendor_documents")
    op.drop_table("vendor_questionnaires")
    op.drop_table("vendors")

