"""
TDD — Compliance Scoring Engine (P2B.11).

Coverage:
  - Score formula: pass / (pass + fail), inconclusive excluded
  - Edge cases: zero applicable, all inconclusive, all pass, all fail
  - calculate_all_frameworks
  - category_breakdown
  - Snapshot writer
  - Trend query
  - Score-drop warning logged when delta > 10pp vs last snapshot
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timedelta

import pytest
from sqlalchemy import select

from compliance_backend.models.framework import Framework, FrameworkVersion, Control
from compliance_backend.models.control_run import ControlCheckRun
from compliance_backend.models.score_snapshot import ComplianceScoreSnapshot
from compliance_backend.services.scoring_engine import (
    ScoringEngine,
    SCORE_DROP_WARN_THRESHOLD,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _make_framework(db_session, n_controls: int = 4) -> tuple[Framework, list[Control]]:
    fw = Framework(
        id=str(uuid.uuid4()),
        name=f"SC-FW-{uuid.uuid4().hex[:4]}",
        short_code=f"SC{uuid.uuid4().hex[:4].upper()}",
        category="security",
    )
    db_session.add(fw)
    await db_session.flush()
    fv = FrameworkVersion(
        id=str(uuid.uuid4()), framework_id=fw.id, version="1", is_current=True,
    )
    db_session.add(fv)
    await db_session.flush()
    controls = []
    for i in range(n_controls):
        ctrl = Control(
            id=str(uuid.uuid4()),
            framework_version_id=fv.id,
            control_code=f"SC-{i}-{uuid.uuid4().hex[:4].upper()}",
            category=f"Cat-{i % 2}",
            description=f"Ctrl {i}",
        )
        db_session.add(ctrl)
        controls.append(ctrl)
    await db_session.flush()
    await db_session.commit()
    return fw, controls


async def _add_run(db_session, control_id: str, tenant_id: str, status: str, when=None):
    run = ControlCheckRun(
        control_id=control_id,
        tenant_id=tenant_id,
        run_at=when or datetime.utcnow(),
        status=status,
    )
    db_session.add(run)
    await db_session.flush()


# ---------------------------------------------------------------------------
# Score formula
# ---------------------------------------------------------------------------

@pytest.mark.anyio
async def test_score_all_pass(db_session):
    fw, controls = await _make_framework(db_session, n_controls=4)
    tenant = "tenant-allp"
    for c in controls:
        await _add_run(db_session, c.id, tenant, "pass")
    await db_session.commit()

    engine = ScoringEngine(db=db_session)
    result = await engine.calculate_framework_score(tenant, fw.id)
    assert result.pass_count == 4
    assert result.fail_count == 0
    assert result.inconclusive_count == 0
    assert result.score == 100.0


@pytest.mark.anyio
async def test_score_all_fail(db_session):
    fw, controls = await _make_framework(db_session, n_controls=3)
    tenant = "tenant-allf"
    for c in controls:
        await _add_run(db_session, c.id, tenant, "fail")
    await db_session.commit()

    engine = ScoringEngine(db=db_session)
    result = await engine.calculate_framework_score(tenant, fw.id)
    assert result.score == 0.0
    assert result.fail_count == 3


@pytest.mark.anyio
async def test_score_mixed_inconclusive_excluded_from_denominator(db_session):
    """3 pass + 1 fail + 2 inconclusive → 3/(3+1) = 75.0, not 3/6=50."""
    fw, controls = await _make_framework(db_session, n_controls=6)
    tenant = "tenant-mixed"
    for c in controls[:3]:
        await _add_run(db_session, c.id, tenant, "pass")
    await _add_run(db_session, controls[3].id, tenant, "fail")
    await _add_run(db_session, controls[4].id, tenant, "inconclusive")
    await _add_run(db_session, controls[5].id, tenant, "inconclusive")
    await db_session.commit()

    engine = ScoringEngine(db=db_session)
    result = await engine.calculate_framework_score(tenant, fw.id)
    assert result.pass_count == 3
    assert result.fail_count == 1
    assert result.inconclusive_count == 2
    assert result.total_applicable == 4
    assert result.score == 75.0


@pytest.mark.anyio
async def test_score_zero_applicable_returns_zero(db_session):
    """No controls evaluated yet → score = 0.0 (no signal)."""
    fw, controls = await _make_framework(db_session, n_controls=3)
    tenant = "tenant-zero-app"
    # No runs at all
    engine = ScoringEngine(db=db_session)
    result = await engine.calculate_framework_score(tenant, fw.id)
    assert result.score == 0.0
    assert result.inconclusive_count == 3
    assert result.total_applicable == 0


@pytest.mark.anyio
async def test_score_all_inconclusive_returns_zero(db_session):
    fw, controls = await _make_framework(db_session, n_controls=3)
    tenant = "tenant-allinc"
    for c in controls:
        await _add_run(db_session, c.id, tenant, "inconclusive")
    await db_session.commit()

    engine = ScoringEngine(db=db_session)
    result = await engine.calculate_framework_score(tenant, fw.id)
    assert result.score == 0.0
    assert result.inconclusive_count == 3
    assert result.total_applicable == 0


@pytest.mark.anyio
async def test_score_uses_most_recent_run(db_session):
    """Most recent run within as_of_date determines status."""
    fw, controls = await _make_framework(db_session, n_controls=1)
    tenant = "tenant-recent"
    now = datetime.utcnow()
    await _add_run(db_session, controls[0].id, tenant, "fail", when=now - timedelta(days=2))
    await _add_run(db_session, controls[0].id, tenant, "pass", when=now)
    await db_session.commit()

    engine = ScoringEngine(db=db_session)
    result = await engine.calculate_framework_score(tenant, fw.id)
    assert result.score == 100.0


@pytest.mark.anyio
async def test_score_respects_as_of_date(db_session):
    """If as_of is in the past, recent runs are ignored."""
    fw, controls = await _make_framework(db_session, n_controls=1)
    tenant = "tenant-asof"
    now = datetime.utcnow()
    await _add_run(db_session, controls[0].id, tenant, "fail", when=now - timedelta(days=10))
    await _add_run(db_session, controls[0].id, tenant, "pass", when=now)
    await db_session.commit()

    engine = ScoringEngine(db=db_session)
    # As of 5 days ago, the only run is the failing one
    result = await engine.calculate_framework_score(
        tenant, fw.id, as_of_date=now - timedelta(days=5),
    )
    assert result.score == 0.0


@pytest.mark.anyio
async def test_score_tenant_isolation(db_session):
    """Tenant A's runs do not affect tenant B's score."""
    fw, controls = await _make_framework(db_session, n_controls=1)
    await _add_run(db_session, controls[0].id, "tenant-iso-A", "pass")
    await _add_run(db_session, controls[0].id, "tenant-iso-B", "fail")
    await db_session.commit()

    engine = ScoringEngine(db=db_session)
    score_a = await engine.calculate_framework_score("tenant-iso-A", fw.id)
    score_b = await engine.calculate_framework_score("tenant-iso-B", fw.id)
    assert score_a.score == 100.0
    assert score_b.score == 0.0


@pytest.mark.anyio
async def test_score_failing_control_ids_populated(db_session):
    fw, controls = await _make_framework(db_session, n_controls=3)
    tenant = "tenant-failids"
    await _add_run(db_session, controls[0].id, tenant, "pass")
    await _add_run(db_session, controls[1].id, tenant, "fail")
    await _add_run(db_session, controls[2].id, tenant, "fail")
    await db_session.commit()

    engine = ScoringEngine(db=db_session)
    result = await engine.calculate_framework_score(tenant, fw.id)
    assert set(result.failing_control_ids) == {controls[1].id, controls[2].id}


# ---------------------------------------------------------------------------
# calculate_all_frameworks
# ---------------------------------------------------------------------------

@pytest.mark.anyio
async def test_calculate_all_frameworks_returns_each(db_session):
    fw_a, ctrls_a = await _make_framework(db_session, n_controls=2)
    fw_b, ctrls_b = await _make_framework(db_session, n_controls=2)
    tenant = f"tenant-all-fw-{uuid.uuid4().hex[:6]}"
    await _add_run(db_session, ctrls_a[0].id, tenant, "pass")
    await _add_run(db_session, ctrls_a[1].id, tenant, "fail")
    await _add_run(db_session, ctrls_b[0].id, tenant, "pass")
    await _add_run(db_session, ctrls_b[1].id, tenant, "pass")
    await db_session.commit()

    engine = ScoringEngine(db=db_session)
    scores = await engine.calculate_all_frameworks(tenant)
    assert fw_a.short_code in scores
    assert fw_b.short_code in scores
    assert scores[fw_a.short_code].score == 50.0
    assert scores[fw_b.short_code].score == 100.0


# ---------------------------------------------------------------------------
# Category breakdown
# ---------------------------------------------------------------------------

@pytest.mark.anyio
async def test_category_breakdown_groups_correctly(db_session):
    fw, controls = await _make_framework(db_session, n_controls=4)
    # controls[0,2] in Cat-0, controls[1,3] in Cat-1
    tenant = f"tenant-cat-{uuid.uuid4().hex[:6]}"
    await _add_run(db_session, controls[0].id, tenant, "pass")
    await _add_run(db_session, controls[2].id, tenant, "pass")
    await _add_run(db_session, controls[1].id, tenant, "fail")
    await _add_run(db_session, controls[3].id, tenant, "fail")
    await db_session.commit()

    engine = ScoringEngine(db=db_session)
    cats = await engine.category_breakdown(tenant, fw.id)
    by_cat = {c.category: c for c in cats}
    assert by_cat["Cat-0"].score == 100.0
    assert by_cat["Cat-1"].score == 0.0


# ---------------------------------------------------------------------------
# Snapshot writer + trend
# ---------------------------------------------------------------------------

@pytest.mark.anyio
async def test_write_daily_snapshot_persists(db_session):
    fw, controls = await _make_framework(db_session, n_controls=2)
    tenant = f"tenant-snap-write-{uuid.uuid4().hex[:6]}"
    await _add_run(db_session, controls[0].id, tenant, "pass")
    await _add_run(db_session, controls[1].id, tenant, "fail")
    await db_session.commit()

    engine = ScoringEngine(db=db_session)
    snap = await engine.write_daily_snapshot(tenant, fw.id)
    await db_session.commit()

    rows = (await db_session.execute(
        select(ComplianceScoreSnapshot).where(
            ComplianceScoreSnapshot.tenant_id == tenant,
        )
    )).scalars().all()
    assert len(rows) == 1
    assert rows[0].score == 50.0
    assert rows[0].pass_count == 1
    assert rows[0].fail_count == 1


@pytest.mark.anyio
async def test_trend_returns_chronological_pairs(db_session):
    fw, _ = await _make_framework(db_session, n_controls=1)
    tenant = f"tenant-trend-{uuid.uuid4().hex[:6]}"
    now = datetime.utcnow()
    for i, score in enumerate([50.0, 60.0, 70.0]):
        snap = ComplianceScoreSnapshot(
            tenant_id=tenant,
            framework_id=fw.id,
            snapshot_date=now - timedelta(days=3 - i),
            score=score,
            pass_count=int(score / 10),
            fail_count=10 - int(score / 10),
            inconclusive_count=0,
            total_applicable=10,
        )
        db_session.add(snap)
    await db_session.commit()

    engine = ScoringEngine(db=db_session)
    pairs = await engine.compliance_trend(tenant, fw.id, days_back=30)
    assert len(pairs) == 3
    scores = [p[1] for p in pairs]
    assert scores == [50.0, 60.0, 70.0]


@pytest.mark.anyio
async def test_trend_respects_days_back(db_session):
    fw, _ = await _make_framework(db_session, n_controls=1)
    tenant = f"tenant-trendwin-{uuid.uuid4().hex[:6]}"
    now = datetime.utcnow()
    # Snapshots at -1, -10, -50 days
    for d in [1, 10, 50]:
        snap = ComplianceScoreSnapshot(
            tenant_id=tenant,
            framework_id=fw.id,
            snapshot_date=now - timedelta(days=d),
            score=80.0, pass_count=8, fail_count=2,
            inconclusive_count=0, total_applicable=10,
        )
        db_session.add(snap)
    await db_session.commit()

    engine = ScoringEngine(db=db_session)
    pairs_30 = await engine.compliance_trend(tenant, fw.id, days_back=30)
    assert len(pairs_30) == 2  # -1d and -10d only


# ---------------------------------------------------------------------------
# Score-drop warning
# ---------------------------------------------------------------------------

@pytest.mark.anyio
async def test_score_drop_logs_warning(db_session, caplog):
    fw, controls = await _make_framework(db_session, n_controls=10)
    tenant = f"tenant-drop-{uuid.uuid4().hex[:6]}"
    # Previous snapshot at 90.0
    db_session.add(ComplianceScoreSnapshot(
        tenant_id=tenant, framework_id=fw.id,
        snapshot_date=datetime.utcnow() - timedelta(days=1),
        score=90.0, pass_count=9, fail_count=1, inconclusive_count=0,
        total_applicable=10,
    ))
    # Add runs so current score < 90 - 10 = 80
    for c in controls[:5]:
        await _add_run(db_session, c.id, tenant, "pass")
    for c in controls[5:]:
        await _add_run(db_session, c.id, tenant, "fail")
    await db_session.commit()

    engine = ScoringEngine(db=db_session)
    with caplog.at_level(logging.WARNING):
        result = await engine.calculate_framework_score(tenant, fw.id)
    assert result.score == 50.0
    assert any("dropped" in rec.message.lower() for rec in caplog.records)


@pytest.mark.anyio
async def test_minor_score_change_no_warning(db_session, caplog):
    fw, controls = await _make_framework(db_session, n_controls=10)
    tenant = f"tenant-stable-{uuid.uuid4().hex[:6]}"
    # Previous snapshot at 80.0
    db_session.add(ComplianceScoreSnapshot(
        tenant_id=tenant, framework_id=fw.id,
        snapshot_date=datetime.utcnow() - timedelta(days=1),
        score=80.0, pass_count=8, fail_count=2, inconclusive_count=0,
        total_applicable=10,
    ))
    # Current state: 7 pass / 3 fail = 70.0 — only a 10pp drop, NOT > threshold.
    for c in controls[:7]:
        await _add_run(db_session, c.id, tenant, "pass")
    for c in controls[7:]:
        await _add_run(db_session, c.id, tenant, "fail")
    await db_session.commit()

    engine = ScoringEngine(db=db_session)
    with caplog.at_level(logging.WARNING):
        await engine.calculate_framework_score(tenant, fw.id)
    # 80 - 70 = 10, NOT > 10 (threshold) → no warning
    drop_warnings = [r for r in caplog.records if "dropped" in r.message.lower()]
    assert len(drop_warnings) == 0


# ---------------------------------------------------------------------------
# Snapshots for all frameworks
# ---------------------------------------------------------------------------

@pytest.mark.anyio
async def test_write_snapshots_for_all_frameworks(db_session):
    fw_a, _ = await _make_framework(db_session, n_controls=1)
    fw_b, _ = await _make_framework(db_session, n_controls=1)
    tenant = f"tenant-allsnap-{uuid.uuid4().hex[:6]}"

    engine = ScoringEngine(db=db_session)
    snaps = await engine.write_snapshots_for_all_frameworks(tenant)
    await db_session.commit()
    # Each framework written
    fw_ids = {s.framework_id for s in snaps}
    assert fw_a.id in fw_ids
    assert fw_b.id in fw_ids
