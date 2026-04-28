"""CRITFIX security migration — CRIT-006 + CRIT-009

Adds:
  - tenant_config       (CRIT-006: server-side tenant settings, never caller-supplied)
  - connector_pull      (CRIT-006: server-side cache of connector data)
  - evidence.content_sha256  (CRIT-009: integrity hash for tamper detection)

Notes for operators:
  - content_sha256 is added as NULLABLE so legacy evidence rows (created
    before this migration) can be back-filled out of band. New writes always
    populate it; reads warn (not error) on legacy NULL rows. Once a backfill
    job has populated all rows, a follow-up migration can ALTER COLUMN to
    NOT NULL.
  - tenant_config holds the dict that USED to be supplied via the request
    body of POST /controls/{id}/run. After this migration, the route ignores
    the body entirely (CRIT-006) and the engine reads from this table.

Revision ID: 0004_critfix_security
Revises: 0003
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# revision identifiers
revision: str = "0004_critfix_security"
down_revision: str | None = "0003"
branch_labels: str | tuple[str, ...] | None = None
depends_on: str | tuple[str, ...] | None = None


def upgrade() -> None:
    # ── CRIT-006 server-side state tables ──────────────────────────────────
    op.create_table(
        "tenant_config",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(255), nullable=False),
        sa.Column("settings", sa.JSON, nullable=False),
        sa.Column("updated_at", sa.DateTime, nullable=False),
        sa.UniqueConstraint("tenant_id", name="uq_tenant_config_tenant"),
    )
    op.create_index("ix_tenant_config_tenant_id", "tenant_config", ["tenant_id"])

    op.create_table(
        "connector_pull",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(255), nullable=False),
        sa.Column("connector_kind", sa.String(64), nullable=False),
        sa.Column("payload", sa.JSON, nullable=False),
        sa.Column("pulled_at", sa.DateTime, nullable=False),
        sa.UniqueConstraint(
            "tenant_id", "connector_kind", name="uq_connector_pull_tenant_kind"
        ),
    )
    op.create_index(
        "ix_connector_pull_tenant_id", "connector_pull", ["tenant_id"]
    )
    op.create_index(
        "ix_connector_pull_connector_kind", "connector_pull", ["connector_kind"]
    )
    op.create_index(
        "ix_connector_pull_tenant_kind",
        "connector_pull",
        ["tenant_id", "connector_kind"],
    )

    # ── CRIT-009 evidence integrity hash column ────────────────────────────
    # Nullable to permit legacy backfill; new writes always populate it.
    with op.batch_alter_table("evidence") as batch:
        batch.add_column(sa.Column("content_sha256", sa.String(64), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("evidence") as batch:
        batch.drop_column("content_sha256")

    op.drop_index("ix_connector_pull_tenant_kind", table_name="connector_pull")
    op.drop_index("ix_connector_pull_connector_kind", table_name="connector_pull")
    op.drop_index("ix_connector_pull_tenant_id", table_name="connector_pull")
    op.drop_table("connector_pull")

    op.drop_index("ix_tenant_config_tenant_id", table_name="tenant_config")
    op.drop_table("tenant_config")
