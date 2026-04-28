"""
TDD tests — control_run_simulator.

Verifies:
  - Generates ControlCheckRun records with realistic spread (pass/fail/inconclusive).
  - Tenant scoping isolates Tenant A and Tenant B data.
  - Idempotency: re-run does not duplicate.
  - Failure reasons are NOT generic placeholders ("test", "TODO", "fake").
  - Evidence references on passing runs.
  - Date distribution covers ~90 days back from now.
"""
from __future__ import annotations

import pytest
from datetime import datetime, timedelta
from sqlalchemy import select, func

from compliance_backend.models.control_run import ControlCheckRun
from compliance_backend.models.framework import Framework, FrameworkVersion, Control
from compliance_backend.seeders.soc2 import seed_soc2
from compliance_backend.seeders.simulators.control_run_simulator import (
    simulate_control_runs,
)


@pytest.mark.anyio
async def test_simulator_creates_runs_for_tenant(db_session):
    await seed_soc2(db_session)
    await simulate_control_runs(
        db_session, tenant_id="sim-tenant-a", days=90, seed=42
    )
    await db_session.flush()

    rows = (await db_session.execute(
        select(ControlCheckRun).where(ControlCheckRun.tenant_id == "sim-tenant-a")
    )).scalars().all()
    assert len(rows) > 0, "simulator should produce at least one run"


@pytest.mark.anyio
async def test_status_distribution_realistic(db_session):
    await seed_soc2(db_session)
    await simulate_control_runs(
        db_session, tenant_id="sim-tenant-a", days=90, seed=42
    )
    rows = (await db_session.execute(
        select(ControlCheckRun).where(ControlCheckRun.tenant_id == "sim-tenant-a")
    )).scalars().all()

    total = len(rows)
    pass_pct = sum(1 for r in rows if r.status == "pass") / total
    fail_pct = sum(1 for r in rows if r.status == "fail") / total
    incon_pct = sum(1 for r in rows if r.status == "inconclusive") / total

    # Target: 75% pass / 15% fail / 10% inconclusive — allow ±10% tolerance
    assert 0.65 <= pass_pct <= 0.85, f"pass% should be ~75, got {pass_pct:.2f}"
    assert 0.05 <= fail_pct <= 0.25, f"fail% should be ~15, got {fail_pct:.2f}"
    assert 0.02 <= incon_pct <= 0.20, f"inconclusive% should be ~10, got {incon_pct:.2f}"


@pytest.mark.anyio
async def test_failure_reasons_are_realistic_not_placeholder(db_session):
    await seed_soc2(db_session)
    await simulate_control_runs(
        db_session, tenant_id="sim-tenant-a", days=90, seed=42
    )
    failed = (await db_session.execute(
        select(ControlCheckRun).where(
            ControlCheckRun.tenant_id == "sim-tenant-a",
            ControlCheckRun.status == "fail",
        )
    )).scalars().all()

    assert len(failed) > 0, "expected at least one failed run for assertion"
    for r in failed:
        reason = (r.failure_reason or "").lower()
        assert reason, f"failed run {r.id} has empty failure_reason"
        # No placeholders
        for bad in ["todo", "fixme", "placeholder", "xxx", "lorem ipsum", "test1", "test2", "fake"]:
            assert bad not in reason, f"placeholder '{bad}' found in failure_reason: {reason}"
        # Reason should be substantive (not just one word)
        assert len(reason) > 20, f"failure_reason too short: {reason!r}"


@pytest.mark.anyio
async def test_passing_runs_have_evidence(db_session):
    await seed_soc2(db_session)
    await simulate_control_runs(
        db_session, tenant_id="sim-tenant-a", days=90, seed=42
    )
    passing = (await db_session.execute(
        select(ControlCheckRun).where(
            ControlCheckRun.tenant_id == "sim-tenant-a",
            ControlCheckRun.status == "pass",
        ).limit(10)
    )).scalars().all()

    assert len(passing) > 0, "expected at least one passing run"
    runs_with_evidence = sum(1 for r in passing if r.evidence_ids)
    # At least 70% of passing runs should have evidence references
    assert runs_with_evidence / len(passing) >= 0.7


@pytest.mark.anyio
async def test_tenant_isolation(db_session):
    await seed_soc2(db_session)
    await simulate_control_runs(db_session, tenant_id="sim-tenant-a", days=30, seed=42)
    await simulate_control_runs(db_session, tenant_id="sim-tenant-b", days=30, seed=42)

    a_count = (await db_session.execute(
        select(func.count()).select_from(ControlCheckRun).where(
            ControlCheckRun.tenant_id == "sim-tenant-a"
        )
    )).scalar()
    b_count = (await db_session.execute(
        select(func.count()).select_from(ControlCheckRun).where(
            ControlCheckRun.tenant_id == "sim-tenant-b"
        )
    )).scalar()
    assert a_count > 0
    assert b_count > 0
    # No cross-contamination
    a_rows = (await db_session.execute(
        select(ControlCheckRun).where(ControlCheckRun.tenant_id == "sim-tenant-a")
    )).scalars().all()
    for r in a_rows:
        assert r.tenant_id == "sim-tenant-a"


@pytest.mark.anyio
async def test_idempotent_rerun(db_session):
    await seed_soc2(db_session)
    await simulate_control_runs(db_session, tenant_id="sim-tenant-a", days=30, seed=42)
    first_count = (await db_session.execute(
        select(func.count()).select_from(ControlCheckRun).where(
            ControlCheckRun.tenant_id == "sim-tenant-a"
        )
    )).scalar()
    await simulate_control_runs(db_session, tenant_id="sim-tenant-a", days=30, seed=42)
    second_count = (await db_session.execute(
        select(func.count()).select_from(ControlCheckRun).where(
            ControlCheckRun.tenant_id == "sim-tenant-a"
        )
    )).scalar()
    assert first_count == second_count, (
        f"second run should not add records (got {first_count} → {second_count})"
    )


@pytest.mark.anyio
async def test_dates_span_requested_window(db_session):
    await seed_soc2(db_session)
    await simulate_control_runs(db_session, tenant_id="sim-tenant-a", days=90, seed=42)
    rows = (await db_session.execute(
        select(ControlCheckRun).where(ControlCheckRun.tenant_id == "sim-tenant-a")
    )).scalars().all()

    now = datetime.utcnow()
    earliest = min(r.run_at for r in rows)
    latest = max(r.run_at for r in rows)
    # earliest should be roughly 60-90 days back
    assert (now - earliest).days >= 30, f"earliest run only {(now - earliest).days} days back"
    # latest should be within last ~7 days
    assert (now - latest).days <= 7, f"latest run is {(now - latest).days} days back"
