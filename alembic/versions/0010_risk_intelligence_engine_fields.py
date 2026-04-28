"""URIP Intelligence Engine — Risk universal fields (fingerprint, advisory status, remediation).

Revision ID: 0010_risk_intelligence_engine_fields
Revises: 0009_cspm_module
Created: 2026-04-27
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0010_risk_intelligence_engine_fields"
down_revision = "0009_cspm_module"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name

    json_type = postgresql.JSON() if dialect == "postgresql" else sa.Text()

    # Advisory status enum: on PostgreSQL create a named enum type; on SQLite
    # use a plain string.
    if dialect == "postgresql":
        advisory_status_type = sa.Enum(
            "valid",
            "patch_available",
            "expired",
            "redundant",
            name="advisory_status_enum",
        )
        advisory_status_type.create(bind, checkfirst=True)
    else:
        advisory_status_type = sa.String(20)

    op.add_column("risks", sa.Column("fingerprint_key", sa.String(64), nullable=True))
    op.create_index("idx_risks_fingerprint_key", "risks", ["fingerprint_key"])

    op.add_column(
        "risks",
        sa.Column("sources_attributed", json_type, nullable=False, server_default="[]"),
    )
    op.add_column(
        "risks",
        sa.Column("advisory_status", advisory_status_type, nullable=True),
    )
    op.add_column(
        "risks",
        sa.Column("remediation_steps", json_type, nullable=False, server_default="[]"),
    )


def downgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name

    op.drop_column("risks", "remediation_steps")
    op.drop_column("risks", "advisory_status")
    op.drop_column("risks", "sources_attributed")
    op.drop_index("idx_risks_fingerprint_key", table_name="risks")
    op.drop_column("risks", "fingerprint_key")

    if dialect == "postgresql":
        sa.Enum(name="advisory_status_enum").drop(bind, checkfirst=True)

