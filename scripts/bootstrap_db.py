#!/usr/bin/env python3
"""
scripts/bootstrap_db.py — Bring a fresh Postgres database to the current
URIP schema in one shot.

Why this exists
---------------
The project has TWO schema-creation paths:

1. ``Base.metadata.create_all(engine)`` — creates the canonical SQLAlchemy
   schema from `backend/models/`.
2. ``alembic upgrade head`` — applies INCREMENTAL alterations (multi-tenant
   foundation, CSPM module, VAPT vendor portal, …) on top of #1.

Migration 0001 (``0001_multi_tenant_foundation``) ALTERs existing tables to
add ``tenant_id`` columns. Running ``alembic upgrade head`` on a totally
empty DB therefore fails because the tables 0001 wants to alter don't exist
yet.

This script runs the supported sequence:

    1. create all tables from models (idempotent — checkfirst=True)
    2. ``alembic stamp head`` so alembic considers itself current
    3. (optional) seed default tenant + admin via bootstrap_dev

Usage
-----
    URIP_DEV_ADMIN_PASSWORD='strong-password' \\
    DATABASE_URL='postgresql+asyncpg://urip:...@db:5432/urip' \\
    python -m scripts.bootstrap_db [--with-seed]

In Docker:
    docker exec -w /app -e PYTHONPATH=/app urip-adaptive-mind-app-1 \\
        /opt/venv/bin/python /app/scripts/bootstrap_db.py --with-seed
"""
from __future__ import annotations

import argparse
import asyncio
import sys


def _ensure_pythonpath() -> None:
    """Allow running as ``python scripts/bootstrap_db.py`` from project root."""
    import os
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if project_root not in sys.path:
        sys.path.insert(0, project_root)


_ensure_pythonpath()


async def _create_all() -> None:
    """Create every table defined under backend.models (idempotent)."""
    # Force every model to register on Base.metadata before create_all.
    from backend.database import Base, engine
    import backend.models  # noqa: F401 — packages __init__ imports all models
    # Belt-and-braces: import a model that is sometimes skipped on a fresh
    # clone (the subscription module isn't always re-exported by some
    # snapshots of backend/models/__init__.py).
    try:
        from backend.models.subscription import TenantSubscription  # noqa: F401
    except ImportError:
        pass

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


def _alembic_stamp_head() -> None:
    """Mark the alembic version table as fully migrated.

    We don't actually run alembic upgrade because migration 0001 is an
    in-place ALTER on tables that create_all just produced — running it
    would attempt to add tenant_id columns that already exist.
    """
    from alembic import command
    from alembic.config import Config

    cfg = Config("alembic.ini")
    command.stamp(cfg, "head")


def _run_seed() -> None:
    """Run scripts/bootstrap_dev.py to create default tenant + admin."""
    # Importable form is awkward (uses asyncio internally); fork instead.
    import subprocess
    subprocess.run(
        [sys.executable, "scripts/bootstrap_dev.py"],
        check=True,
        cwd=".",
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Bootstrap URIP database")
    parser.add_argument(
        "--with-seed",
        action="store_true",
        help="Also run scripts/bootstrap_dev.py to create default tenant + admin",
    )
    args = parser.parse_args()

    print("[bootstrap_db] step 1/3 — Base.metadata.create_all() …")
    asyncio.run(_create_all())
    print("[bootstrap_db] step 1/3 — done")

    print("[bootstrap_db] step 2/3 — alembic stamp head …")
    _alembic_stamp_head()
    print("[bootstrap_db] step 2/3 — done")

    if args.with_seed:
        print("[bootstrap_db] step 3/3 — bootstrap_dev seed …")
        _run_seed()
        print("[bootstrap_db] step 3/3 — done")
    else:
        print("[bootstrap_db] step 3/3 — skipped (no --with-seed)")

    print("[bootstrap_db] OK — schema ready, alembic stamped at head")
    return 0


if __name__ == "__main__":
    sys.exit(main())
