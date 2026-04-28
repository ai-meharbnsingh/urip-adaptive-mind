"""
TDD tests — compliance_score_simulator.

Verifies:
  - Generates 90 days of daily ComplianceScoreSnapshot records.
  - Per (tenant, framework) pair.
  - Scores trend upward (65% → 87%) over the window.
  - pass_count + fail_count = total_applicable.
  - Tenant isolation; idempotent.
"""
from __future__ import annotations

from datetime import datetime, timedelta

import pytest
from sqlalchemy import select, func

from compliance_backend.models.framework import Framework
from compliance_backend.models.score_snapshot import ComplianceScoreSnapshot
from compliance_backend.seeders.soc2 import seed_soc2
from compliance_backend.seeders.iso27001 import seed_iso27001
from compliance_backend.seeders.simulators.compliance_score_simulator import (
    simulate_compliance_score_history,
)


@pytest.mark.anyio
async def test_simulator_creates_snapshots(db_session):
    await seed_soc2(db_session)
    await seed_iso27001(db_session)
    summary = await simulate_compliance_score_history(
        db_session, tenant_id="sim-tenant-a", days=90, seed=42
    )
    assert summary["snapshots"] >= 90 * 2  # 90 days × 2 frameworks


@pytest.mark.anyio
async def test_score_trends_upward(db_session):
    await seed_soc2(db_session)
    await simulate_compliance_score_history(
        db_session, tenant_id="sim-tenant-a", days=90, seed=42
    )
    fw = (await db_session.execute(
        select(Framework).where(Framework.short_code == "SOC2")
    )).scalars().first()

    snaps = (await db_session.execute(
        select(ComplianceScoreSnapshot).where(
            ComplianceScoreSnapshot.tenant_id == "sim-tenant-a",
            ComplianceScoreSnapshot.framework_id == fw.id,
        ).order_by(ComplianceScoreSnapshot.snapshot_date.asc())
    )).scalars().all()
    assert len(snaps) >= 90

    earliest_score = snaps[0].score
    latest_score = snaps[-1].score
    # Trend: latest should be at least 10 points higher than earliest
    assert latest_score - earliest_score >= 10, (
        f"expected upward trend, got {earliest_score:.1f} → {latest_score:.1f}"
    )
    # Earliest should be ~65, latest ~87
    assert 55 <= earliest_score <= 75
    assert 80 <= latest_score <= 95


@pytest.mark.anyio
async def test_counts_internally_consistent(db_session):
    await seed_soc2(db_session)
    await simulate_compliance_score_history(
        db_session, tenant_id="sim-tenant-a", days=30, seed=42
    )
    snaps = (await db_session.execute(
        select(ComplianceScoreSnapshot).where(
            ComplianceScoreSnapshot.tenant_id == "sim-tenant-a"
        ).limit(20)
    )).scalars().all()
    for s in snaps:
        assert s.pass_count + s.fail_count == s.total_applicable, (
            f"counts mismatch: pass={s.pass_count} + fail={s.fail_count} != total={s.total_applicable}"
        )


@pytest.mark.anyio
async def test_one_snapshot_per_day_per_framework(db_session):
    await seed_soc2(db_session)
    await simulate_compliance_score_history(
        db_session, tenant_id="sim-tenant-a", days=30, seed=42
    )
    fw = (await db_session.execute(
        select(Framework).where(Framework.short_code == "SOC2")
    )).scalars().first()
    snaps = (await db_session.execute(
        select(ComplianceScoreSnapshot).where(
            ComplianceScoreSnapshot.tenant_id == "sim-tenant-a",
            ComplianceScoreSnapshot.framework_id == fw.id,
        )
    )).scalars().all()
    days = {s.snapshot_date.date() for s in snaps}
    assert len(days) == len(snaps), "duplicate days for same framework"


@pytest.mark.anyio
async def test_tenant_isolation(db_session):
    await seed_soc2(db_session)
    await simulate_compliance_score_history(
        db_session, tenant_id="sim-tenant-a", days=30, seed=42
    )
    await simulate_compliance_score_history(
        db_session, tenant_id="sim-tenant-b", days=30, seed=42
    )
    a = (await db_session.execute(
        select(func.count()).select_from(ComplianceScoreSnapshot).where(
            ComplianceScoreSnapshot.tenant_id == "sim-tenant-a"
        )
    )).scalar()
    b = (await db_session.execute(
        select(func.count()).select_from(ComplianceScoreSnapshot).where(
            ComplianceScoreSnapshot.tenant_id == "sim-tenant-b"
        )
    )).scalar()
    assert a > 0 and b > 0
    assert a == b  # same seed, same framework count


@pytest.mark.anyio
async def test_idempotent_rerun(db_session):
    await seed_soc2(db_session)
    await simulate_compliance_score_history(
        db_session, tenant_id="sim-tenant-a", days=30, seed=42
    )
    first = (await db_session.execute(
        select(func.count()).select_from(ComplianceScoreSnapshot).where(
            ComplianceScoreSnapshot.tenant_id == "sim-tenant-a"
        )
    )).scalar()
    await simulate_compliance_score_history(
        db_session, tenant_id="sim-tenant-a", days=30, seed=42
    )
    second = (await db_session.execute(
        select(func.count()).select_from(ComplianceScoreSnapshot).where(
            ComplianceScoreSnapshot.tenant_id == "sim-tenant-a"
        )
    )).scalar()
    assert first == second
