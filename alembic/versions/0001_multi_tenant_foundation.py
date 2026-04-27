"""Multi-tenant foundation: add tenants table and tenant_id FK to all domain tables.

Revision ID: 0001_multi_tenant_foundation
Revises: (none — first migration)
Create Date: 2026-04-27

Migration strategy
------------------
1. Create `tenants` table.
2. Insert a default "Royal Enfield" tenant so that existing rows can be backfilled.
3. Add `tenant_id` as NULLABLE to each domain table (required to backfill existing rows).
4. Backfill all existing rows to the Royal Enfield tenant.
5. Set `tenant_id NOT NULL` on all domain tables.
6. Add FK constraints with ondelete=RESTRICT.
7. Add performance indexes on tenant_id.

Downgrade
---------
Drops tenant_id from all tables and drops the tenants table.
Existing data is preserved; downgrade does not restore the backfill.
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSON
import uuid

# Revision identifiers
revision = "0001_multi_tenant_foundation"
down_revision = None
branch_labels = None
depends_on = None

# Fixed UUID for the default Royal Enfield tenant
# This must match the seed script / any existing session data.
ROYALENFIELD_TENANT_ID = "00000000-0000-0000-0000-000000000001"


def upgrade() -> None:
    # ------------------------------------------------------------------
    # 1. Create tenants table
    # ------------------------------------------------------------------
    op.create_table(
        "tenants",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("slug", sa.String(100), nullable=False),
        sa.Column("domain", sa.String(255), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("settings", JSON(), nullable=False, server_default="{}"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index("ix_tenants_slug", "tenants", ["slug"], unique=True)

    # ------------------------------------------------------------------
    # 2. Insert default Royal Enfield tenant
    # ------------------------------------------------------------------
    op.execute(
        f"""
        INSERT INTO tenants (id, name, slug, domain, is_active, settings, created_at)
        VALUES (
            '{ROYALENFIELD_TENANT_ID}',
            'Royal Enfield',
            'royalenfield',
            'royalenfield.com',
            true,
            '{{}}',
            now()
        )
        """
    )

    # ------------------------------------------------------------------
    # 3. Add tenant_id columns (nullable first for backfill)
    # ------------------------------------------------------------------
    domain_tables = [
        "users",
        "risks",
        "audit_logs",
        "acceptance_requests",
        "remediation_tasks",
        "connector_configs",
    ]

    for table in domain_tables:
        op.add_column(
            table,
            sa.Column("tenant_id", UUID(as_uuid=True), nullable=True),
        )

    # ------------------------------------------------------------------
    # 4. Backfill all existing rows to the Royal Enfield tenant
    # ------------------------------------------------------------------
    for table in domain_tables:
        op.execute(
            f"UPDATE {table} SET tenant_id = '{ROYALENFIELD_TENANT_ID}' WHERE tenant_id IS NULL"
        )

    # ------------------------------------------------------------------
    # 5. Make tenant_id NOT NULL
    # ------------------------------------------------------------------
    for table in domain_tables:
        op.alter_column(table, "tenant_id", nullable=False)

    # ------------------------------------------------------------------
    # 6. Add FK constraints
    # ------------------------------------------------------------------
    for table in domain_tables:
        op.create_foreign_key(
            f"fk_{table}_tenant_id",
            table,
            "tenants",
            ["tenant_id"],
            ["id"],
            ondelete="RESTRICT",
        )

    # ------------------------------------------------------------------
    # 7. Add performance indexes
    # ------------------------------------------------------------------
    index_map = {
        "users": "idx_users_tenant_id",
        "risks": "idx_risks_tenant_id",
        "audit_logs": "idx_audit_logs_tenant_id",
        "acceptance_requests": "idx_acceptance_tenant_id",
        "remediation_tasks": "idx_remediation_tenant_id",
        "connector_configs": "idx_connector_configs_tenant_id",
    }
    for table, idx_name in index_map.items():
        op.create_index(idx_name, table, ["tenant_id"])


def downgrade() -> None:
    """
    Reverse the migration.

    WARNING: This drops tenant_id from all tables and removes the tenants table.
    Existing data is not split back — downgrade is safe to run in development only.
    """
    domain_tables = [
        "users",
        "risks",
        "audit_logs",
        "acceptance_requests",
        "remediation_tasks",
        "connector_configs",
    ]

    # Drop FKs and indexes first
    index_map = {
        "users": "idx_users_tenant_id",
        "risks": "idx_risks_tenant_id",
        "audit_logs": "idx_audit_logs_tenant_id",
        "acceptance_requests": "idx_acceptance_tenant_id",
        "remediation_tasks": "idx_remediation_tenant_id",
        "connector_configs": "idx_connector_configs_tenant_id",
    }

    for table, idx_name in index_map.items():
        op.drop_index(idx_name, table_name=table)
        op.drop_constraint(f"fk_{table}_tenant_id", table, type_="foreignkey")
        op.drop_column(table, "tenant_id")

    op.drop_index("ix_tenants_slug", table_name="tenants")
    op.drop_table("tenants")
