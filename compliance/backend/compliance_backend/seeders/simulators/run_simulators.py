"""
run_simulators — master orchestrator for the compliance demo simulators.

Usage:
    python -m compliance_backend.seeders.simulators.run_simulators \\
        --tenant-slug=adverb-demo

    python -m compliance_backend.seeders.simulators.run_simulators \\
        --tenant-slug=adverb-demo --reset

Dependency order (each step is idempotent on its own; --reset clears first):
    1. framework seeders (run_all)
    2. tenant policies (created here, since simulators reference them)
    3. control_run_simulator
    4. evidence_simulator       (writes real files)
    5. policy_ack_simulator     (depends on policies)
    6. vendor_response_simulator
    7. asset_simulator
    8. incident_simulator
    9. access_review_simulator
   10. auditor_activity_simulator (depends on framework + evidence + policies)
   11. compliance_score_simulator (depends on frameworks + controls)

Reset behavior (INV-0: NO `rm`):
    --reset moves all simulator-written rows for the tenant to *_archive_<ts>
    tables via INSERT ... SELECT, then DELETE them. No DROP TABLE, no rm.
    The archive tables persist as a recovery path.

Idempotency:
    Without --reset, re-running is a no-op for any simulator that finds
    existing rows for the tenant (each simulator implements its own
    skip_if_existing check).
"""
from __future__ import annotations

import argparse
import asyncio
import os
import sys
import uuid
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

# Framework seeders
from compliance_backend.seeders.soc2 import seed_soc2
from compliance_backend.seeders.iso27001 import seed_iso27001
from compliance_backend.seeders.gdpr import seed_gdpr
from compliance_backend.seeders.hipaa import seed_hipaa
from compliance_backend.seeders.pci_dss import seed_pci_dss
from compliance_backend.seeders.india_dpdp import seed_india_dpdp
from compliance_backend.seeders.nist_csf import seed_nist_csf
from compliance_backend.seeders.cross_mappings import seed_cross_mappings

# Simulators
from compliance_backend.seeders.simulators.control_run_simulator import (
    simulate_control_runs,
)
from compliance_backend.seeders.simulators.policy_ack_simulator import (
    simulate_policy_acknowledgments,
)
from compliance_backend.seeders.simulators.vendor_response_simulator import (
    simulate_vendor_data,
)
from compliance_backend.seeders.simulators.evidence_simulator import (
    simulate_evidence,
)
from compliance_backend.seeders.simulators.incident_simulator import (
    simulate_incidents,
)
from compliance_backend.seeders.simulators.asset_simulator import (
    simulate_assets,
)
from compliance_backend.seeders.simulators.access_review_simulator import (
    simulate_access_reviews,
)
from compliance_backend.seeders.simulators.auditor_activity_simulator import (
    simulate_auditor_activity,
)
from compliance_backend.seeders.simulators.compliance_score_simulator import (
    simulate_compliance_score_history,
)

# Models needed for setup
from compliance_backend.database import Base
from compliance_backend.models.framework import Framework
from compliance_backend.models.policy import Policy, PolicyVersion
from compliance_backend.seeders.policy_templates import (
    get_policy_templates,
)
from compliance_backend.seeders.simulators._common import (
    make_rng,
    stable_uuid,
    now_utc,
)
from sqlalchemy import select


# Tables that simulators write to — used by --reset (INV-0: archive, never drop)
SIMULATOR_TABLES = [
    "control_check_runs",
    "evidence",
    "policy_acknowledgments",
    "vendor_documents",
    "vendor_questionnaires",
    "vendor_risk_scores",
    "vendors",
    "auditor_activity_log",
    "auditor_access",
    "compliance_score_snapshots",
    "sim_incidents",
    "sim_assets",
    "sim_access_review_decisions",
    "sim_access_review_campaigns",
]


async def _seed_tenant_policies(
    session: AsyncSession, tenant_id: str, seed: int = 42
) -> int:
    """
    Seed a few realistic policies for the tenant so the policy_ack simulator
    has something to acknowledge.
    """
    rng = make_rng(seed)
    existing = (await session.execute(
        select(Policy).where(Policy.tenant_id == tenant_id).limit(1)
    )).scalars().first()
    if existing:
        return 0

    templates = get_policy_templates()
    created = 0
    inviter = stable_uuid(tenant_id, "policy_owner", "ciso")

    for t in templates[:5]:  # First 5 templates
        policy = Policy(
            id=stable_uuid(tenant_id, "policy", t["name"]),
            tenant_id=tenant_id,
            name=t["name"],
            owner_user_id=inviter,
            is_active=True,
        )
        session.add(policy)
        await session.flush()

        # Old version (1) and current version (2)
        old_v = PolicyVersion(
            id=stable_uuid(tenant_id, "version", t["name"], "1"),
            policy_id=policy.id,
            version_number=1,
            content=f"# {t['name']} v1 — legacy version superseded.\n\n{t.get('content', '')[:500]}",
            published_at=now_utc() - timedelta(days=365 + rng.randint(0, 60)),
            published_by_user_id=inviter,
        )
        session.add(old_v)

        cur_v = PolicyVersion(
            id=stable_uuid(tenant_id, "version", t["name"], "2"),
            policy_id=policy.id,
            version_number=2,
            content=t.get("content", f"# {t['name']} v2\n"),
            published_at=now_utc() - timedelta(days=rng.randint(45, 120)),
            published_by_user_id=inviter,
            change_summary="Annual review — updated to align with 2026 SOC 2 + ISO 27001 reaudit.",
        )
        session.add(cur_v)
        await session.flush()

        policy.current_version_id = cur_v.id
        created += 1

    await session.flush()
    return created


async def _archive_then_clear_tenant_data(
    session: AsyncSession, tenant_id: str
) -> dict[str, int]:
    """
    Archive simulator-written rows for the tenant to *_archive_<ts> tables
    then DELETE the originals. NEVER `rm`, NEVER DROP TABLE.

    SQLite + Postgres both support CREATE TABLE AS SELECT.
    """
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    archived: dict[str, int] = {}

    for table in SIMULATOR_TABLES:
        # Determine tenant-id column name — most use "tenant_id"; some use FK paths
        try:
            archive_table = f"{table}_archive_{timestamp}"

            # Check if rows exist for this tenant
            try:
                row_check = await session.execute(
                    text(f"SELECT COUNT(*) FROM {table} WHERE tenant_id = :tid"),
                    {"tid": tenant_id},
                )
                count = row_check.scalar()
            except Exception:
                # Table may not have direct tenant_id (e.g. sim_access_review_decisions
                # references campaign which has tenant_id). Skip — handled separately.
                count = 0

            if count and count > 0:
                # Archive
                await session.execute(text(
                    f"CREATE TABLE {archive_table} AS "
                    f"SELECT * FROM {table} WHERE tenant_id = :tid"
                ), {"tid": tenant_id})
                # Delete (soft "rm" via archive)
                await session.execute(text(
                    f"DELETE FROM {table} WHERE tenant_id = :tid"
                ), {"tid": tenant_id})
                archived[table] = count
        except Exception as exc:
            # Table doesn't exist yet, or no tenant_id column — skip
            pass

    # Special-case: sim_access_review_decisions inherits tenant via campaign
    try:
        cnt = (await session.execute(text(
            "SELECT COUNT(*) FROM sim_access_review_decisions d "
            "WHERE d.campaign_id IN ("
            "  SELECT id FROM sim_access_review_campaigns WHERE tenant_id = :tid"
            ")"
        ), {"tid": tenant_id})).scalar()
        if cnt and cnt > 0:
            await session.execute(text(
                f"CREATE TABLE sim_access_review_decisions_archive_{timestamp} AS "
                "SELECT d.* FROM sim_access_review_decisions d "
                "WHERE d.campaign_id IN ("
                "  SELECT id FROM sim_access_review_campaigns WHERE tenant_id = :tid"
                ")"
            ), {"tid": tenant_id})
            await session.execute(text(
                "DELETE FROM sim_access_review_decisions "
                "WHERE campaign_id IN ("
                "  SELECT id FROM sim_access_review_campaigns WHERE tenant_id = :tid"
                ")"
            ), {"tid": tenant_id})
            archived["sim_access_review_decisions"] = cnt
    except Exception:
        pass

    await session.commit()
    return archived


async def run_all(
    *,
    tenant_id: str,
    db_url: Optional[str] = None,
    reset: bool = False,
    seed: int = 42,
    skip_framework_seed: bool = False,
    verbose: bool = True,
) -> dict[str, dict]:
    """
    Run all simulators for a tenant.

    Returns a dict {step_name: summary_dict}.
    """
    db_url = db_url or os.environ.get(
        "COMPLIANCE_DB_URL",
        "postgresql+asyncpg://compliance:compliance@localhost:5434/compliance_db",
    )
    connect_args = {"check_same_thread": False} if db_url.startswith("sqlite") else {}
    engine = create_async_engine(db_url, echo=False, connect_args=connect_args)
    factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

    # Ensure all model tables exist (incl. simulator-only sim_* tables)
    import compliance_backend.models.control_run  # noqa: F401
    import compliance_backend.models.evidence  # noqa: F401
    import compliance_backend.models.auditor  # noqa: F401
    import compliance_backend.models.score_snapshot  # noqa: F401
    import compliance_backend.seeders.simulators.sim_models  # noqa: F401

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    results: dict[str, dict] = {}

    async with factory() as session:
        if reset:
            if verbose:
                print(f"[reset] Archiving + clearing simulator data for tenant={tenant_id}")
            archived = await _archive_then_clear_tenant_data(session, tenant_id)
            results["__reset_archived"] = archived
            if verbose:
                for t, n in archived.items():
                    print(f"  - {t}: archived {n} rows")

        if not skip_framework_seed:
            if verbose:
                print("[1] Seeding frameworks (SOC2/ISO27001/GDPR/HIPAA/PCI/DPDP/NIST)…")
            await seed_soc2(session)
            await seed_iso27001(session)
            await seed_gdpr(session)
            await seed_hipaa(session)
            await seed_pci_dss(session)
            await seed_india_dpdp(session)
            await seed_nist_csf(session)
            await seed_cross_mappings(session)
            await session.commit()

        if verbose:
            print(f"[2] Seeding tenant policies (tenant={tenant_id})…")
        policy_count = await _seed_tenant_policies(session, tenant_id, seed=seed)
        await session.commit()
        results["policies"] = {"seeded": policy_count}

        if verbose:
            print("[3] control_run_simulator…")
        results["control_runs"] = await simulate_control_runs(
            session, tenant_id=tenant_id, days=90, seed=seed
        )
        await session.commit()

        if verbose:
            print("[4] evidence_simulator (writing real files)…")
        results["evidence"] = await simulate_evidence(
            session, tenant_id=tenant_id, per_control=2, seed=seed
        )
        await session.commit()

        if verbose:
            print("[5] policy_ack_simulator…")
        results["policy_acks"] = await simulate_policy_acknowledgments(
            session, tenant_id=tenant_id, employee_count=80, seed=seed
        )
        await session.commit()

        if verbose:
            print("[6] vendor_response_simulator…")
        results["vendors"] = await simulate_vendor_data(
            session, tenant_id=tenant_id, vendor_count=18, seed=seed
        )
        await session.commit()

        if verbose:
            print("[7] asset_simulator…")
        results["assets"] = await simulate_assets(
            session, tenant_id=tenant_id, count=120, seed=seed
        )
        await session.commit()

        if verbose:
            print("[8] incident_simulator…")
        results["incidents"] = await simulate_incidents(
            session, tenant_id=tenant_id, count=30, seed=seed
        )
        await session.commit()

        if verbose:
            print("[9] access_review_simulator…")
        results["access_reviews"] = await simulate_access_reviews(
            session, tenant_id=tenant_id, quarters_back=4, users_per_campaign=25, seed=seed
        )
        await session.commit()

        # Auditor activity needs a framework_id
        soc2_fw = (await session.execute(
            select(Framework).where(Framework.short_code == "SOC2")
        )).scalars().first()
        if soc2_fw:
            if verbose:
                print("[10] auditor_activity_simulator (SOC 2)…")
            results["auditor_activity"] = await simulate_auditor_activity(
                session, tenant_id=tenant_id, framework_id=soc2_fw.id, n_auditors=4, seed=seed
            )
            await session.commit()

        if verbose:
            print("[11] compliance_score_simulator (90 days)…")
        results["score_history"] = await simulate_compliance_score_history(
            session, tenant_id=tenant_id, days=90, seed=seed
        )
        await session.commit()

    await engine.dispose()
    return results


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Run all compliance demo simulators for a tenant."
    )
    p.add_argument(
        "--tenant-slug",
        "--tenant",
        dest="tenant_id",
        required=True,
        help="Target tenant identifier (slug or UUID).",
    )
    p.add_argument(
        "--db-url",
        default=None,
        help="Override COMPLIANCE_DB_URL (e.g. sqlite+aiosqlite:///./demo.db).",
    )
    p.add_argument(
        "--reset",
        action="store_true",
        help="Archive + clear existing simulator data for the tenant first (INV-0 safe — uses CREATE TABLE AS, never DROP).",
    )
    p.add_argument(
        "--seed",
        type=int,
        default=42,
        help="RNG seed for deterministic output (default 42).",
    )
    p.add_argument(
        "--skip-framework-seed",
        action="store_true",
        help="Skip framework seeders (assume already loaded).",
    )
    p.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress progress output.",
    )
    return p.parse_args()


def main() -> int:
    args = _parse_args()
    results = asyncio.run(
        run_all(
            tenant_id=args.tenant_id,
            db_url=args.db_url,
            reset=args.reset,
            seed=args.seed,
            skip_framework_seed=args.skip_framework_seed,
            verbose=not args.quiet,
        )
    )

    if not args.quiet:
        print("\n" + "=" * 60)
        print(f"Demo bootstrap complete for tenant={args.tenant_id}")
        print("=" * 60)
        for step, summary in results.items():
            if step == "__reset_archived":
                continue
            print(f"  {step:25s} → {summary}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
