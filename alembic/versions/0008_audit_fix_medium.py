"""AUDIT-FIX MEDIUM — M6 (risks.tenant_id NOT NULL) + M9 (audit_logs REVOKE).

Revision ID: 0008_audit_fix_medium
Revises: 0007_audit_log_tenant_backfill
Created: 2026-04-27

Background
----------
M6 / Gemini HIGH-G5 (→ MEDIUM) / Kimi MED-011 — `risks.tenant_id` was kept
nullable for backwards compat during the multi-tenant rollout (alembic
0001).  Backfill is complete (every legacy row was attributed to the
Royal Enfield default tenant).  We now enforce NOT NULL at the database
layer so any new code path that forgets to stamp the tenant gets caught
at INSERT time, not later when the cross-tenant query silently misses
the row.

  Caveat (per CritFix-B / migration 0007 decision):
  - audit_logs LEGACY rows where tenant_id IS NULL are KEPT for forensic
    value; this migration does NOT alter audit_logs.tenant_id.  The
    documented behaviour is that tenant-scoped queries already exclude
    NULL via apply_tenant_filter (WHERE tenant_id = :tid).

M9 / Kimi MED-009 — defence-in-depth REVOKE UPDATE/DELETE on audit_logs.
Best-effort: only runs on PostgreSQL, iterates conventional app role
names.  SQLite test runs are no-ops.

Migration steps for risks.tenant_id NOT NULL:
  1. Backfill any orphan rows (tenant_id IS NULL) to a sentinel "legacy"
     tenant created in 0001.  We use the Royal Enfield UUID
     '00000000-0000-0000-0000-000000000001' (matches the seed).
  2. ALTER COLUMN tenant_id SET NOT NULL.
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0008_audit_fix_medium"
down_revision = "0007_audit_log_tenant_backfill"
branch_labels = None
depends_on = None


LEGACY_TENANT_ID = "00000000-0000-0000-0000-000000000001"


def upgrade() -> None:
    bind = op.get_bind()

    # ---------------------------------------------------------------- #
    # M6 — risks.tenant_id NOT NULL.
    # ---------------------------------------------------------------- #
    if bind.dialect.name == "postgresql":
        try:
            # 1. Backfill any orphans to the legacy Royal Enfield tenant.
            op.execute(
                sa.text(
                    "UPDATE risks SET tenant_id = :tid "
                    "WHERE tenant_id IS NULL"
                ).bindparams(tid=LEGACY_TENANT_ID)
            )
            # 2. Tighten the column.
            op.alter_column(
                "risks", "tenant_id", existing_type=sa.dialects.postgresql.UUID(),
                nullable=False,
            )
        except Exception:
            # Some installs may not have the risks table yet (greenfield).
            pass

    # ---------------------------------------------------------------- #
    # M9 — REVOKE UPDATE/DELETE on audit_logs from non-superuser roles.
    # ---------------------------------------------------------------- #
    if bind.dialect.name == "postgresql":
        for role in ("urip", "compliance", "compliance_app", "app", "PUBLIC"):
            try:
                op.execute(sa.text(
                    f"REVOKE UPDATE, DELETE ON audit_logs FROM {role}"
                ))
            except Exception:
                continue


def downgrade() -> None:
    """Restore nullable risks.tenant_id; do NOT re-grant UPDATE/DELETE."""
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        try:
            op.alter_column(
                "risks", "tenant_id", existing_type=sa.dialects.postgresql.UUID(),
                nullable=True,
            )
        except Exception:
            pass
