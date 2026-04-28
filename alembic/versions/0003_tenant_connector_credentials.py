"""Add tenant_connector_credentials table for P1.6 connector framework.

Revision ID: 0003_tenant_connector_credentials
Revises: 0002_tenant_subscriptions
Create Date: 2026-04-27

Changes
-------
1. Create `tenant_connector_credentials` table:
   - id (UUID PK)
   - tenant_id (UUID FK → tenants.id CASCADE)
   - connector_name (VARCHAR 50)
   - encrypted_blob (BYTEA / LargeBinary) — Fernet ciphertext of credentials dict
   - created_at / updated_at (TIMESTAMPTZ)
   - UNIQUE constraint on (tenant_id, connector_name)
   - Index on tenant_id

Rationale
---------
Separate table rather than adding encrypted_credentials to ConnectorConfig:
- ConnectorConfig stores connector configuration (URL, schedule, active flag).
- Credentials are a security-sensitive concern and rotate independently of config.
- Separation follows principle of least privilege — a service reading connector
  config should NOT automatically get access to credentials.
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers
revision = "0003_tenant_connector_credentials"
down_revision = "0002_tenant_subscriptions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "tenant_connector_credentials",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("connector_name", sa.String(50), nullable=False),
        sa.Column("encrypted_blob", sa.LargeBinary, nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
            nullable=False,
        ),
    )

    # Unique constraint: one credential set per (tenant, connector)
    op.create_unique_constraint(
        "uq_tenant_connector_cred",
        "tenant_connector_credentials",
        ["tenant_id", "connector_name"],
    )

    # Index for fast tenant-scoped lookups
    op.create_index(
        "idx_tcc_tenant_id",
        "tenant_connector_credentials",
        ["tenant_id"],
    )


def downgrade() -> None:
    op.drop_index("idx_tcc_tenant_id", table_name="tenant_connector_credentials")
    op.drop_constraint(
        "uq_tenant_connector_cred",
        "tenant_connector_credentials",
        type_="unique",
    )
    op.drop_table("tenant_connector_credentials")
