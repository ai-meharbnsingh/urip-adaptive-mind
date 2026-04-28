"""Add tenant_subscriptions table and is_super_admin flag on users.

Revision ID: 0002_tenant_subscriptions
Revises: 0001_multi_tenant_foundation
Create Date: 2026-04-27

Changes
-------
1. Add `is_super_admin` boolean column to `users` table (default false).
2. Create `tenant_subscriptions` table with:
   - id UUID PK
   - tenant_id FK → tenants.id (RESTRICT)
   - module_code VARCHAR(20) — one of CORE/VM/EDR/NETWORK/IDENTITY/COLLAB/ITSM/DAST/DLP/COMPLIANCE
   - is_enabled BOOLEAN (default true)
   - billing_tier VARCHAR(20) — TRIAL/STANDARD/PREMIUM
   - started_at TIMESTAMPTZ
   - expires_at TIMESTAMPTZ nullable
   - UNIQUE(tenant_id, module_code) — one row per tenant+module pair

P1.10 Pricing decision
----------------------
No separate billing table is created.  `billing_tier` + `started_at` + `expires_at`
on TenantSubscription is sufficient for pricing-tier enforcement and trial expiry.
When a full billing system (Stripe/Chargebee) is integrated, invoices/billing_events
can reference tenant_subscriptions.id without any schema change here.
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "0002_tenant_subscriptions"
down_revision = "0001_multi_tenant_foundation"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ------------------------------------------------------------------
    # 1. Add is_super_admin to users
    # ------------------------------------------------------------------
    op.add_column(
        "users",
        sa.Column(
            "is_super_admin",
            sa.Boolean(),
            nullable=False,
            server_default="false",
        ),
    )

    # ------------------------------------------------------------------
    # 2. Create tenant_subscriptions table
    # ------------------------------------------------------------------
    op.create_table(
        "tenant_subscriptions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", UUID(as_uuid=True), nullable=False),
        sa.Column("module_code", sa.String(20), nullable=False),
        sa.Column("is_enabled", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("billing_tier", sa.String(20), nullable=False, server_default="TRIAL"),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.id"],
            name="fk_tenant_subscriptions_tenant_id",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint("tenant_id", "module_code", name="uq_tenant_module"),
    )
    op.create_index(
        "idx_tenant_subscriptions_tenant_id",
        "tenant_subscriptions",
        ["tenant_id"],
    )


def downgrade() -> None:
    op.drop_index("idx_tenant_subscriptions_tenant_id", table_name="tenant_subscriptions")
    op.drop_table("tenant_subscriptions")
    op.drop_column("users", "is_super_admin")
