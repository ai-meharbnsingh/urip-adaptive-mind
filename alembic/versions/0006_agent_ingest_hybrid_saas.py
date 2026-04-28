"""Phase 4 Hybrid-SaaS — agent ingest tables + tenant.license_key.

Revision ID: 0006_agent_ingest_hybrid_saas
Revises: 0005_risk_score_summaries
Create Date: 2026-04-27

Adds the cloud-side cache tables required for the Hybrid-SaaS Docker agent
(see DELIVERY_ARCHITECTURE.md §3, §7).  Tables:

  - agent_registrations
  - connector_health_summaries
  - drilldown_requests

NOTE: risk_score_summaries already exists (created in 0005_risk_score_summaries).
The agent_ingest router writes to that same table — single source of truth.

Also adds `tenants.license_key` column — gap identified during Phase 4
build.  License keys are issued by the cloud and presented by the agent at
first-boot to /api/agent-ingest/register.
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0006_agent_ingest_hybrid_saas"
down_revision = "0005_risk_score_summaries"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ------------------------------------------------------------------
    # 1. tenants.license_key
    # ------------------------------------------------------------------
    op.add_column(
        "tenants",
        sa.Column("license_key", sa.String(128), nullable=True),
    )
    op.create_index(
        "ix_tenants_license_key", "tenants", ["license_key"], unique=True
    )

    # ------------------------------------------------------------------
    # 2. agent_registrations
    # ------------------------------------------------------------------
    op.create_table(
        "agent_registrations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("agent_version", sa.String(32), nullable=False),
        sa.Column(
            "capabilities",
            postgresql.JSON(),
            nullable=False,
            server_default="{}",
        ),
        sa.Column("shared_secret_hash", sa.String(64), nullable=False),
        sa.Column(
            "registered_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "last_seen",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "connector_health",
            postgresql.JSON(),
            nullable=False,
            server_default="{}",
        ),
    )
    op.create_index(
        "idx_agent_reg_tenant_id", "agent_registrations", ["tenant_id"]
    )
    op.create_index(
        "idx_agent_reg_last_seen", "agent_registrations", ["last_seen"]
    )

    # ------------------------------------------------------------------
    # 3. connector_health_summaries
    # ------------------------------------------------------------------
    op.create_table(
        "connector_health_summaries",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("connector_name", sa.String(50), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("last_poll_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "error_count_24h", sa.Integer, nullable=False, server_default="0"
        ),
        sa.Column("last_error", sa.Text, nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index(
        "idx_chs_tenant_conn",
        "connector_health_summaries",
        ["tenant_id", "connector_name"],
        unique=True,
    )

    # ------------------------------------------------------------------
    # 4. drilldown_requests
    # ------------------------------------------------------------------
    op.create_table(
        "drilldown_requests",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "requested_by_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("request_type", sa.String(64), nullable=False),
        sa.Column(
            "request_payload",
            postgresql.JSON(),
            nullable=False,
            server_default="{}",
        ),
        sa.Column("token", sa.String(128), nullable=False),
        sa.Column("fulfilled_payload_temp", sa.Text, nullable=True),
        sa.Column(
            "requested_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("fulfilled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "idx_drilldown_token", "drilldown_requests", ["token"], unique=True
    )
    op.create_index(
        "idx_drilldown_tenant", "drilldown_requests", ["tenant_id"]
    )
    op.create_index(
        "idx_drilldown_pending",
        "drilldown_requests",
        ["tenant_id", "fulfilled_at"],
    )


def downgrade() -> None:
    op.drop_index("idx_drilldown_pending", table_name="drilldown_requests")
    op.drop_index("idx_drilldown_tenant", table_name="drilldown_requests")
    op.drop_index("idx_drilldown_token", table_name="drilldown_requests")
    op.drop_table("drilldown_requests")

    op.drop_index(
        "idx_chs_tenant_conn", table_name="connector_health_summaries"
    )
    op.drop_table("connector_health_summaries")

    op.drop_index("idx_agent_reg_last_seen", table_name="agent_registrations")
    op.drop_index("idx_agent_reg_tenant_id", table_name="agent_registrations")
    op.drop_table("agent_registrations")

    op.drop_index("ix_tenants_license_key", table_name="tenants")
    op.drop_column("tenants", "license_key")
