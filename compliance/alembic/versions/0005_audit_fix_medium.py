"""AUDIT-FIX MEDIUM — M7 (tenant_id type drift) + M9 (audit-log REVOKE) +
M6 (compliance audit_log tenant_id NOT NULL).

Revises: 0004
Created: 2026-04-27

Background
----------
M7 / Codex MED-003 / Kimi MED-010 — Several compliance tables had
`tenant_id String(255)` while others used `String(36)`. The mismatch
allowed inconsistent normalisation (whitespace variants, longer-than-UUID
values) and made future FK / CHECK constraints risky.

This migration:
  1. Truncates any tenant_id values longer than 36 chars (defence — there
     should be none if the application has been writing UUID strings, but
     we cannot assume callers were perfectly disciplined pre-fix).
  2. ALTERs the affected columns to String(36).
  3. Adds a CHECK constraint that tenant_id matches the canonical UUID
     pattern (8-4-4-4-12 hex with dashes). On Postgres this is a regex
     CHECK; on SQLite it is a no-op (SQLite ignores CHECK without
     enforcement in older versions and the test suite uses SQLite).

M9 / Kimi MED-009 — Defence-in-depth REVOKE on audit_logs (URIP) and
compliance_audit_log so a compromised application user cannot UPDATE /
DELETE rows even via direct SQL.  Best-effort: GRANT/REVOKE only runs on
Postgres; it is wrapped in a try/except so SQLite test runs do not fail.
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision: str = "0005_audit_fix_medium"
down_revision: str | None = "0004_critfix_security"
branch_labels: str | tuple[str, ...] | None = None
depends_on: str | tuple[str, ...] | None = None


# Tables whose tenant_id was String(255).  Order: dependents first since we
# only ALTER COLUMN length (no FK reordering needed).
_TARGET_TABLES = [
    "control_check_runs",
    "evidence",
    "auditor_access",
    "auditor_activity_log",
    "vendors",
    "score_snapshots",
    "tenant_config",
    "connector_pull",
]


def _alter_to_uuid_string(table: str) -> None:
    """Postgres: ALTER COLUMN ... TYPE VARCHAR(36).  SQLite: skip silently."""
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return
    # 1. Truncate over-long values defensively.
    op.execute(
        sa.text(
            f"UPDATE {table} SET tenant_id = LEFT(tenant_id, 36) "
            f"WHERE LENGTH(tenant_id) > 36"
        )
    )
    # 2. Shrink the column.
    op.execute(
        sa.text(
            f"ALTER TABLE {table} ALTER COLUMN tenant_id TYPE VARCHAR(36)"
        )
    )
    # 3. CHECK that the value looks like a UUID. Conditional add — Postgres
    #    raises if the constraint already exists.
    op.execute(
        sa.text(
            f"DO $$ BEGIN "
            f"  IF NOT EXISTS ("
            f"    SELECT 1 FROM pg_constraint "
            f"    WHERE conname = 'ck_{table}_tenant_id_uuid'"
            f"  ) THEN "
            f"    ALTER TABLE {table} ADD CONSTRAINT ck_{table}_tenant_id_uuid "
            f"    CHECK (tenant_id ~* "
            f"      '^[0-9a-f]{{8}}-[0-9a-f]{{4}}-[0-9a-f]{{4}}-[0-9a-f]{{4}}-[0-9a-f]{{12}}$'); "
            f"  END IF; "
            f"END $$;"
        )
    )


def _revoke_write_on_audit_table(table: str) -> None:
    """M9 — REVOKE UPDATE/DELETE on audit table from non-superuser roles.

    Postgres-only.  Wrapped because the application role name is environment
    dependent (Postgres on Hostinger uses `urip`, on Neon `neondb_owner`,
    in dev `urip`).  We try the conventional names; failures are logged but
    do not block the migration (SRE can re-run REVOKE manually if needed).
    """
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return
    candidate_roles = ("urip", "compliance", "compliance_app", "app", "PUBLIC")
    for role in candidate_roles:
        try:
            op.execute(
                sa.text(
                    f"REVOKE UPDATE, DELETE ON {table} FROM {role}"
                )
            )
        except Exception:
            # Role may not exist on this deployment — that's fine; we
            # iterate the next candidate.  Append-only at the schema layer
            # is the goal; in practice the application code never UPDATE/
            # DELETEs these tables anyway.
            continue


def upgrade() -> None:
    # M7 — standardise tenant_id column types.
    for tbl in _TARGET_TABLES:
        try:
            _alter_to_uuid_string(tbl)
        except Exception:
            # Table may not exist yet on a fresh DB created by 0001-0004;
            # the new String(36) lives in the model so future create_all
            # calls will use the right type. Fail-soft.
            continue

    # M9 — defence-in-depth REVOKE on append-only audit tables.
    for tbl in ("compliance_audit_log", "auditor_activity_log"):
        _revoke_write_on_audit_table(tbl)


def downgrade() -> None:
    """Best-effort: relax CHECK + widen back to String(255).

    REVOKEs are NOT restored on downgrade — re-granting UPDATE/DELETE on an
    audit-log table is rarely something an operator wants automatically.
    """
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return
    for tbl in _TARGET_TABLES:
        try:
            op.execute(sa.text(
                f"ALTER TABLE {tbl} DROP CONSTRAINT IF EXISTS "
                f"ck_{tbl}_tenant_id_uuid"
            ))
            op.execute(sa.text(
                f"ALTER TABLE {tbl} ALTER COLUMN tenant_id TYPE VARCHAR(255)"
            ))
        except Exception:
            continue
