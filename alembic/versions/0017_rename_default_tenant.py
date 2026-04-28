"""Rename the default tenant from "Royal Enfield" to a vendor-neutral string.

Kimi round-E LOW finding: alembic/versions/0001_multi_tenant_foundation.py
inserts a default tenant named "Royal Enfield" — leftover from the original
URIP demo customer. The genesis migration is immutable (editing it would
break alembic checksums on any DB that already ran 0001), so this new
migration UPDATEs the tenant row in place where it still has that name.

Idempotent: only updates if the row still exists with the legacy name; safe
to re-run; safe to skip on environments where the default tenant is already
renamed (e.g. prod tenants created via bootstrap_dev with a different name).

Revision ID: 0017_rename_default_tenant
Revises: 0016_auth_password_reset_mfa
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "0017_rename_default_tenant"
down_revision: str | None = "0016_auth_password_reset_mfa"
branch_labels: str | tuple[str, ...] | None = None
depends_on: str | tuple[str, ...] | None = None


def upgrade() -> None:
    """Rename the genesis tenant if it still carries the legacy name.

    Avoid the SQLAlchemy ``text()`` raw-SQL path here so we can pass the
    target name as a bound parameter — no string interpolation, no risk of
    SQL injection (defensive even though the value is hardcoded).
    """
    bind = op.get_bind()
    bind.execute(
        sa.text(
            "UPDATE tenants "
            "SET name = :new_name "
            "WHERE name = :old_name"
        ),
        {"new_name": "Default Tenant", "old_name": "Royal Enfield"},
    )


def downgrade() -> None:
    """Revert the rename. Symmetric and idempotent."""
    bind = op.get_bind()
    bind.execute(
        sa.text(
            "UPDATE tenants "
            "SET name = :old_name "
            "WHERE name = :new_name"
        ),
        {"new_name": "Default Tenant", "old_name": "Royal Enfield"},
    )
