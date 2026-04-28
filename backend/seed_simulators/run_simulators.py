"""
backend/seed_simulators/run_simulators.py — URIP-side demo bootstrap.

Run all URIP-side simulators for a tenant.

Usage:
    URIP_FERNET_KEY=$(python -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())') \
        python -m backend.seed_simulators.run_simulators --tenant-slug=acme-demo

    # Or against an existing slug:
    python -m backend.seed_simulators.run_simulators --tenant-slug=acme-demo --reset
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import os
import sys
import uuid
from typing import Optional

logger = logging.getLogger(__name__)

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine, AsyncSession

# Ensure SQLite-compatible types are imported for tests/dev DBs that aren't postgres
from backend.config import settings
from backend.database import Base
from backend.models.tenant import Tenant
from backend.models.user import User
from backend.models.tenant_connector_credential import TenantConnectorCredential
from backend.models.audit_log import AuditLog
from backend.seed_simulators.connector_credential_simulator import (
    simulate_connector_credentials,
)
from backend.seed_simulators.audit_log_activity_simulator import (
    simulate_audit_log_activity,
)


SIMULATOR_TABLES = [
    "audit_logs",
    "tenant_connector_credentials",
]


async def _archive_then_clear(session: AsyncSession, tenant_id: uuid.UUID) -> dict:
    """Archive simulator-written rows for the tenant, then DELETE. INV-0 safe."""
    from datetime import datetime, timezone
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    archived = {}
    for table in SIMULATOR_TABLES:
        try:
            cnt = (await session.execute(
                text(f"SELECT COUNT(*) FROM {table} WHERE tenant_id = :tid"),
                {"tid": str(tenant_id)},
            )).scalar()
            if cnt and cnt > 0:
                arc = f"{table}_archive_{timestamp}"
                await session.execute(text(
                    f"CREATE TABLE {arc} AS SELECT * FROM {table} WHERE tenant_id = :tid"
                ), {"tid": str(tenant_id)})
                await session.execute(text(
                    f"DELETE FROM {table} WHERE tenant_id = :tid"
                ), {"tid": str(tenant_id)})
                archived[table] = cnt
        except Exception as exc:
            logger.exception(
                "simulator reset/archive failed",
                extra={"connector": table, "tenant_id": str(tenant_id)},
            )
            continue
    await session.commit()
    return archived


async def _ensure_tenant(session: AsyncSession, slug: str) -> Tenant:
    """Find tenant by slug or create a fresh demo tenant."""
    existing = (await session.execute(
        select(Tenant).where(Tenant.slug == slug)
    )).scalars().first()
    if existing:
        return existing

    tenant = Tenant(
        id=uuid.uuid4(),
        name=f"Demo Tenant ({slug})",
        slug=slug,
        domain=f"{slug}.in",
        is_active=True,
        settings={"simulator_mode": "acme"},
    )
    session.add(tenant)
    await session.commit()
    await session.refresh(tenant)
    return tenant


async def run_all(
    *,
    tenant_slug: str,
    db_url: Optional[str] = None,
    reset: bool = False,
    seed: int = 42,
    days: int = 60,
    events_per_day: int = 25,
    verbose: bool = True,
) -> dict:
    """
    Bootstrap URIP-side demo data for a tenant.
    """
    db_url = db_url or settings.DATABASE_URL
    engine = create_async_engine(db_url, echo=False)
    factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

    # Make sure tables exist
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    results: dict = {}
    async with factory() as session:
        tenant = await _ensure_tenant(session, tenant_slug)
        results["tenant"] = {"id": str(tenant.id), "slug": tenant.slug, "name": tenant.name}

        if reset:
            if verbose:
                print(f"[reset] archiving + clearing URIP simulator data for tenant={tenant.slug}")
            archived = await _archive_then_clear(session, tenant.id)
            results["__reset_archived"] = archived
            for t, n in archived.items():
                if verbose:
                    print(f"  - {t}: archived {n}")

        if verbose:
            print(f"[1] connector_credential_simulator (tenant={tenant.slug})…")
        results["credentials"] = await simulate_connector_credentials(
            session, tenant_id=tenant.id, seed=seed
        )
        await session.commit()

        if verbose:
            print(f"[2] audit_log_activity_simulator (tenant={tenant.slug})…")
        results["audit_logs"] = await simulate_audit_log_activity(
            session, tenant_id=tenant.id, days=days, events_per_day=events_per_day, seed=seed
        )
        await session.commit()

    await engine.dispose()
    return results


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Run URIP-side demo simulators.")
    p.add_argument("--tenant-slug", "--slug", dest="tenant_slug", required=True,
                   help="Tenant slug (created if missing).")
    p.add_argument("--db-url", default=None,
                   help="Override DATABASE_URL (e.g. sqlite+aiosqlite:///./demo.db).")
    p.add_argument("--reset", action="store_true",
                   help="Archive + clear existing simulator data first (INV-0 safe).")
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--days", type=int, default=60)
    p.add_argument("--events-per-day", type=int, default=25)
    p.add_argument("--quiet", action="store_true")
    return p.parse_args()


def main() -> int:
    args = _parse_args()
    results = asyncio.run(run_all(
        tenant_slug=args.tenant_slug,
        db_url=args.db_url,
        reset=args.reset,
        seed=args.seed,
        days=args.days,
        events_per_day=args.events_per_day,
        verbose=not args.quiet,
    ))
    if not args.quiet:
        print("\n" + "=" * 60)
        print(f"URIP demo bootstrap complete for tenant={args.tenant_slug}")
        print("=" * 60)
        for step, summary in results.items():
            if step == "__reset_archived":
                continue
            print(f"  {step:25s} → {summary}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
