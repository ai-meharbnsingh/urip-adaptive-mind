"""
Tests for RiskAggregateService — compute correctness, persistence, idempotency,
trend query, and cache TTL behaviour.

INV-4: These tests execute actual service code against the in-memory SQLite DB.
INV-6: Test expectations are never changed to make tests pass.
"""
from __future__ import annotations

import json
import time
import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest

from backend.models.risk import Risk
from backend.models.risk_snapshot import RiskScoreSummary
from backend.models.tenant import Tenant
from backend.services import risk_aggregate_service as svc_module
from backend.services.risk_aggregate_service import RiskAggregateService


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_risk(
    tenant_id: uuid.UUID,
    severity: str = "high",
    status: str = "open",
    source: str = "crowdstrike",
    domain: str = "network",
    epss_score: float | None = None,
    in_kev_catalog: bool = False,
    composite_score: float | None = None,
    created_at: datetime | None = None,
    updated_at: datetime | None = None,
) -> Risk:
    now = datetime.now(timezone.utc)
    return Risk(
        id=uuid.uuid4(),
        risk_id=f"RISK-2026-{uuid.uuid4().hex[:6].upper()}",
        finding=f"Test finding {uuid.uuid4().hex[:4]}",
        source=source,
        domain=domain,
        cvss_score=7.5,
        severity=severity,
        asset="server.test",
        owner_team="Security",
        status=status,
        sla_deadline=now + timedelta(days=7),
        tenant_id=tenant_id,
        epss_score=epss_score,
        in_kev_catalog=in_kev_catalog,
        composite_score=composite_score,
        created_at=created_at or now,
        updated_at=updated_at or now,
    )


# ---------------------------------------------------------------------------
# compute_current_summary
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_compute_empty_tenant(db_session, default_tenant):
    """compute_current_summary on a tenant with no risks returns all-zero counts."""
    svc = RiskAggregateService(db_session)
    snap = await svc.compute_current_summary(default_tenant.id)

    assert snap.total_risks == 0
    assert snap.critical_count == 0
    assert snap.high_count == 0
    assert snap.exploit_active_count == 0
    assert snap.kev_active_count == 0
    assert snap.mean_ttr_hours is None
    assert snap.mean_composite_score is None


@pytest.mark.asyncio
async def test_compute_severity_counts(db_session, default_tenant):
    """Severity counts reflect actual DB rows."""
    tid = default_tenant.id
    risks = [
        _make_risk(tid, severity="critical"),
        _make_risk(tid, severity="critical"),
        _make_risk(tid, severity="high"),
        _make_risk(tid, severity="medium"),
        _make_risk(tid, severity="low"),
        _make_risk(tid, severity="low"),
    ]
    for r in risks:
        db_session.add(r)
    await db_session.commit()

    svc = RiskAggregateService(db_session)
    snap = await svc.compute_current_summary(tid)

    assert snap.total_risks == 6
    assert snap.critical_count == 2
    assert snap.high_count == 1
    assert snap.medium_count == 1
    assert snap.low_count == 2
    assert snap.info_count == 0


@pytest.mark.asyncio
async def test_compute_exploit_active_count(db_session, default_tenant):
    """exploit_active_count counts open risks with epss_score > 0.7."""
    tid = default_tenant.id
    # epss > 0.7, open — should be counted
    db_session.add(_make_risk(tid, epss_score=0.85, status="open"))
    db_session.add(_make_risk(tid, epss_score=0.90, status="open"))
    # epss > 0.7 but closed — should NOT be counted
    db_session.add(_make_risk(tid, epss_score=0.95, status="closed"))
    # epss < 0.7, open — should NOT be counted
    db_session.add(_make_risk(tid, epss_score=0.40, status="open"))
    # no epss, open — should NOT be counted
    db_session.add(_make_risk(tid, epss_score=None, status="open"))
    await db_session.commit()

    svc = RiskAggregateService(db_session)
    snap = await svc.compute_current_summary(tid)
    assert snap.exploit_active_count == 2


@pytest.mark.asyncio
async def test_compute_kev_active_count(db_session, default_tenant):
    """kev_active_count counts open risks with in_kev_catalog=True."""
    tid = default_tenant.id
    db_session.add(_make_risk(tid, in_kev_catalog=True, status="open"))
    db_session.add(_make_risk(tid, in_kev_catalog=True, status="open"))
    db_session.add(_make_risk(tid, in_kev_catalog=True, status="closed"))  # excluded
    db_session.add(_make_risk(tid, in_kev_catalog=False, status="open"))   # excluded
    await db_session.commit()

    svc = RiskAggregateService(db_session)
    snap = await svc.compute_current_summary(tid)
    assert snap.kev_active_count == 2


@pytest.mark.asyncio
async def test_compute_mean_ttr(db_session, default_tenant):
    """mean_ttr_hours is the average hours from created_at to updated_at for closed risks."""
    tid = default_tenant.id
    now = datetime.now(timezone.utc)

    # 24h TTR
    db_session.add(_make_risk(
        tid, status="closed",
        created_at=now - timedelta(hours=24),
        updated_at=now,
    ))
    # 48h TTR
    db_session.add(_make_risk(
        tid, status="closed",
        created_at=now - timedelta(hours=48),
        updated_at=now,
    ))
    # Open risk — excluded
    db_session.add(_make_risk(tid, status="open"))
    await db_session.commit()

    svc = RiskAggregateService(db_session)
    snap = await svc.compute_current_summary(tid)

    assert snap.mean_ttr_hours is not None
    assert abs(snap.mean_ttr_hours - 36.0) < 1.0  # (24 + 48) / 2 = 36


@pytest.mark.asyncio
async def test_compute_mean_composite_score(db_session, default_tenant):
    """mean_composite_score is the average composite_score of open risks with a score."""
    tid = default_tenant.id
    db_session.add(_make_risk(tid, status="open", composite_score=8.0))
    db_session.add(_make_risk(tid, status="open", composite_score=6.0))
    db_session.add(_make_risk(tid, status="open", composite_score=None))  # excluded
    db_session.add(_make_risk(tid, status="closed", composite_score=9.0))  # excluded
    await db_session.commit()

    svc = RiskAggregateService(db_session)
    snap = await svc.compute_current_summary(tid)

    assert snap.mean_composite_score is not None
    assert abs(snap.mean_composite_score - 7.0) < 0.1  # (8 + 6) / 2


@pytest.mark.asyncio
async def test_compute_top_sources_json(db_session, default_tenant):
    """top_sources_json lists up to 5 sources sorted by count desc."""
    tid = default_tenant.id
    for _ in range(3):
        db_session.add(_make_risk(tid, source="crowdstrike"))
    for _ in range(2):
        db_session.add(_make_risk(tid, source="easm"))
    db_session.add(_make_risk(tid, source="cnapp"))
    await db_session.commit()

    svc = RiskAggregateService(db_session)
    snap = await svc.compute_current_summary(tid)

    sources = json.loads(snap.top_sources_json)
    assert len(sources) <= 5
    # crowdstrike should be first (3 risks)
    assert sources[0]["source"] == "crowdstrike"
    assert sources[0]["count"] == 3


@pytest.mark.asyncio
async def test_compute_module_breakdown_json(db_session, default_tenant):
    """module_breakdown_json groups risks by domain."""
    tid = default_tenant.id
    for _ in range(4):
        db_session.add(_make_risk(tid, domain="network"))
    for _ in range(2):
        db_session.add(_make_risk(tid, domain="cloud"))
    await db_session.commit()

    svc = RiskAggregateService(db_session)
    snap = await svc.compute_current_summary(tid)

    breakdown = json.loads(snap.module_breakdown_json)
    assert breakdown["NETWORK"] == 4
    assert breakdown["CLOUD"] == 2


# ---------------------------------------------------------------------------
# write_snapshot — persistence and idempotency
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_write_snapshot_persists(db_session, default_tenant):
    """write_snapshot() adds a row to the DB."""
    from sqlalchemy import select
    svc = RiskAggregateService(db_session)
    snap = await svc.write_snapshot(default_tenant.id)
    await db_session.commit()
    await db_session.refresh(snap)

    result = (await db_session.execute(
        select(RiskScoreSummary).where(RiskScoreSummary.tenant_id == default_tenant.id)
    )).scalars().all()

    assert len(result) == 1
    assert result[0].id == snap.id


@pytest.mark.asyncio
async def test_write_snapshot_idempotent_within_minute(db_session, default_tenant):
    """Calling write_snapshot twice within the same minute returns the same row."""
    from sqlalchemy import select
    svc = RiskAggregateService(db_session)

    snap1 = await svc.write_snapshot(default_tenant.id)
    await db_session.commit()

    snap2 = await svc.write_snapshot(default_tenant.id)
    await db_session.commit()

    # Should return the same snapshot (same id)
    assert snap1.id == snap2.id

    # Only one row in DB
    rows = (await db_session.execute(
        select(RiskScoreSummary).where(RiskScoreSummary.tenant_id == default_tenant.id)
    )).scalars().all()
    assert len(rows) == 1


# ---------------------------------------------------------------------------
# write_snapshots_for_all_tenants
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_write_snapshots_for_all_tenants(db_session):
    """write_snapshots_for_all_tenants processes every active tenant."""
    from sqlalchemy import select

    t1 = Tenant(id=uuid.uuid4(), name="T1", slug="t1", domain="t1.test", is_active=True, settings={})
    t2 = Tenant(id=uuid.uuid4(), name="T2", slug="t2", domain="t2.test", is_active=True, settings={})
    t3 = Tenant(id=uuid.uuid4(), name="T3-inactive", slug="t3", domain="t3.test", is_active=False, settings={})
    db_session.add_all([t1, t2, t3])
    await db_session.commit()

    svc = RiskAggregateService(db_session)
    results = await svc.write_snapshots_for_all_tenants()

    # Should produce snapshots for t1 and t2 (active only); t3 is inactive
    tenant_ids = {r.tenant_id for r in results}
    assert t1.id in tenant_ids
    assert t2.id in tenant_ids
    assert t3.id not in tenant_ids


# ---------------------------------------------------------------------------
# get_trend
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_trend_returns_ordered_snapshots(db_session, default_tenant):
    """get_trend returns snapshots oldest-first within the days_back window."""
    tid = default_tenant.id
    now = datetime.now(timezone.utc)

    for days_ago in [10, 5, 1]:
        snap = RiskScoreSummary(
            tenant_id=tid,
            snapshot_at=now - timedelta(days=days_ago),
            total_risks=days_ago,
        )
        db_session.add(snap)
    await db_session.commit()

    svc = RiskAggregateService(db_session)
    trend = await svc.get_trend(tid, days_back=30)

    assert len(trend) == 3
    # Oldest first
    assert trend[0].total_risks == 10
    assert trend[1].total_risks == 5
    assert trend[2].total_risks == 1


@pytest.mark.asyncio
async def test_get_trend_respects_days_back(db_session, default_tenant):
    """Snapshots older than days_back are excluded."""
    tid = default_tenant.id
    now = datetime.now(timezone.utc)

    recent = RiskScoreSummary(tenant_id=tid, snapshot_at=now - timedelta(days=5), total_risks=5)
    old = RiskScoreSummary(tenant_id=tid, snapshot_at=now - timedelta(days=60), total_risks=60)
    db_session.add(recent)
    db_session.add(old)
    await db_session.commit()

    svc = RiskAggregateService(db_session)
    trend = await svc.get_trend(tid, days_back=30)

    assert len(trend) == 1
    assert trend[0].total_risks == 5


@pytest.mark.asyncio
async def test_get_trend_tenant_isolation(db_session, default_tenant):
    """Trend only returns snapshots belonging to the queried tenant."""
    tid = default_tenant.id
    other_tid = uuid.uuid4()
    now = datetime.now(timezone.utc)

    snap_mine = RiskScoreSummary(tenant_id=tid, snapshot_at=now, total_risks=10)
    snap_other = RiskScoreSummary(tenant_id=other_tid, snapshot_at=now, total_risks=99)
    db_session.add(snap_mine)
    db_session.add(snap_other)
    await db_session.commit()

    svc = RiskAggregateService(db_session)
    trend = await svc.get_trend(tid, days_back=1)

    assert len(trend) == 1
    assert trend[0].total_risks == 10


# ---------------------------------------------------------------------------
# Cache TTL
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_cache_populated_after_write(db_session, default_tenant):
    """After write_snapshot(), get_latest() should return cached value without extra DB hit."""
    tid = default_tenant.id

    # Clear cache state before test
    svc_module._cache_invalidate(tid)

    svc = RiskAggregateService(db_session)
    written = await svc.write_snapshot(tid)
    await db_session.commit()

    # Cache should now be warm — get_latest returns same id
    got = await svc.get_latest(tid)
    assert got is not None
    assert got.id == written.id


@pytest.mark.asyncio
async def test_cache_expires_after_ttl(db_session, default_tenant):
    """After TTL expires, get_latest() falls back to DB."""
    tid = default_tenant.id
    svc_module._cache_invalidate(tid)

    svc = RiskAggregateService(db_session)
    written = await svc.write_snapshot(tid)
    await db_session.commit()

    # Simulate cache expiry by back-dating the cache entry
    key = svc_module._cache_key(tid)
    old_snap, _ = svc_module._snapshot_cache[key]
    svc_module._snapshot_cache[key] = (old_snap, time.monotonic() - 1)  # already expired

    # get_latest should fall back to DB (still returns same snap because it's the only one)
    got = await svc.get_latest(tid)
    assert got is not None
    assert got.id == written.id


@pytest.mark.asyncio
async def test_cache_miss_returns_none_when_no_db_row(db_session, default_tenant):
    """get_latest returns None when no snapshot exists and cache is cold."""
    tid = default_tenant.id
    svc_module._cache_invalidate(tid)

    svc = RiskAggregateService(db_session)
    result = await svc.get_latest(tid)
    assert result is None
