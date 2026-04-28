"""CritFix-B NEW-1 — audit_logs.tenant_id backfill flag for legacy rows.

Revision ID: 0007_audit_log_tenant_backfill
Revises: 0006_agent_ingest_hybrid_saas
Create Date: 2026-04-27

Background
----------
Pre-CritFix, several state-changing endpoints wrote AuditLog rows without
setting `tenant_id` (NULL).  Those legacy rows have no tenant scope and
must NOT be returned by tenant-scoped queries.

This migration is intentionally minimal:
  - We do NOT delete legacy rows (forensic value).
  - We add an index on tenant_id (already added in 0001 — no-op here).
  - We log a warning for any rows where tenant_id IS NULL so DBAs know
    legacy data exists.

The query helper `audit_log_tenant_scoped()` (added in
backend/services/tenant_query.py — TBD if needed) excludes such rows.
For now the existing `apply_tenant_filter(query, AuditLog)` already
emits `WHERE tenant_id = :tid` which excludes NULL automatically.

Why no DELETE?
- Audit trails are append-only by definition.  Even legacy un-attributable
  rows tell you "an action happened pre-fix" — useful in a forensic
  investigation.

Down-revision: this migration is a no-op on downgrade (purely metadata).
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0007_audit_log_tenant_backfill"
down_revision = "0006_agent_ingest_hybrid_saas"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """
    Idempotent — safe to re-run.  We:
      1. Surface the count of legacy un-attributable rows via a NOTICE.
      2. (No row mutation — see module docstring.)
    """
    bind = op.get_bind()
    # Count legacy rows.  Wrapped in a try in case the table doesn't exist
    # yet on a brand-new DB.
    try:
        legacy_count = bind.execute(
            sa.text("SELECT COUNT(*) FROM audit_logs WHERE tenant_id IS NULL")
        ).scalar() or 0
        if legacy_count > 0:
            # Emit a Postgres NOTICE so the operator sees it during migrate.
            bind.execute(
                sa.text(
                    "DO $$ BEGIN RAISE NOTICE "
                    "'CritFix-B NEW-1: % audit_logs rows have tenant_id IS NULL "
                    "(legacy pre-fix). They are EXCLUDED from tenant-scoped queries.', "
                    f"{legacy_count}; END $$;"
                )
            )
    except Exception:
        # Table not present on this DB — nothing to backfill.
        pass


def downgrade() -> None:
    # Nothing to undo — this migration only emits a notice.
    pass
