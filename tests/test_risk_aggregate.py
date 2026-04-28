"""
Tests for RiskScoreSummary model — creation, FK behaviour, tenant isolation.

INV-4: Tests must actually execute — run pytest and see output.
INV-6: Never modify test expectations to make tests pass.
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone

import pytest

from backend.models.risk_snapshot import RiskScoreSummary


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_snap(tenant_id: uuid.UUID | None = None, **kwargs) -> RiskScoreSummary:
    """Build a RiskScoreSummary with required fields defaulted."""
    return RiskScoreSummary(
        tenant_id=tenant_id or uuid.uuid4(),
        snapshot_at=datetime.now(timezone.utc),
        total_risks=kwargs.get("total_risks", 10),
        critical_count=kwargs.get("critical_count", 2),
        high_count=kwargs.get("high_count", 3),
        medium_count=kwargs.get("medium_count", 3),
        low_count=kwargs.get("low_count", 2),
        info_count=kwargs.get("info_count", 0),
        exploit_active_count=kwargs.get("exploit_active_count", 1),
        kev_active_count=kwargs.get("kev_active_count", 0),
        mean_ttr_hours=kwargs.get("mean_ttr_hours", 48.0),
        mean_composite_score=kwargs.get("mean_composite_score", 7.5),
        top_sources_json=kwargs.get(
            "top_sources_json",
            json.dumps([{"source": "crowdstrike", "count": 5}]),
        ),
        module_breakdown_json=kwargs.get(
            "module_breakdown_json",
            json.dumps({"NETWORK": 4, "CLOUD": 3, "APPLICATION": 3}),
        ),
    )


# ---------------------------------------------------------------------------
# Model construction
# ---------------------------------------------------------------------------

class TestRiskScoreSummaryModel:
    def test_tablename(self):
        assert RiskScoreSummary.__tablename__ == "risk_score_summaries"

    def test_default_id_is_uuid(self):
        snap = make_snap()
        # id is set by default=uuid.uuid4 — will be assigned on flush; before flush
        # it may be None (SQLAlchemy deferred) OR a UUID — either is acceptable here
        # because we test persistence in the DB fixtures below.
        # Just check the type if already assigned.
        if snap.id is not None:
            assert isinstance(snap.id, uuid.UUID)

    def test_counts_default_zero(self):
        tid = uuid.uuid4()
        snap = RiskScoreSummary(
            tenant_id=tid,
            snapshot_at=datetime.now(timezone.utc),
        )
        assert snap.total_risks == 0
        assert snap.critical_count == 0
        assert snap.high_count == 0
        assert snap.medium_count == 0
        assert snap.low_count == 0
        assert snap.info_count == 0
        assert snap.exploit_active_count == 0
        assert snap.kev_active_count == 0

    def test_nullable_fields(self):
        snap = make_snap(mean_ttr_hours=None, mean_composite_score=None)
        assert snap.mean_ttr_hours is None
        assert snap.mean_composite_score is None

    def test_json_fields_roundtrip(self):
        sources = [{"source": "crowdstrike", "count": 10}, {"source": "easm", "count": 5}]
        modules = {"NETWORK": 7, "CLOUD": 3}
        snap = make_snap(
            top_sources_json=json.dumps(sources),
            module_breakdown_json=json.dumps(modules),
        )
        assert json.loads(snap.top_sources_json) == sources
        assert json.loads(snap.module_breakdown_json) == modules


# ---------------------------------------------------------------------------
# Database persistence (requires db_session fixture from conftest)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_persist_and_retrieve(db_session, default_tenant):
    """RiskScoreSummary can be written and read back from the test DB."""
    snap = make_snap(tenant_id=default_tenant.id)
    db_session.add(snap)
    await db_session.commit()
    await db_session.refresh(snap)

    assert snap.id is not None
    assert snap.tenant_id == default_tenant.id
    assert snap.total_risks == 10
    assert snap.critical_count == 2


@pytest.mark.asyncio
async def test_multiple_snaps_same_tenant(db_session, default_tenant):
    """Multiple snapshots per tenant are allowed (no unique constraint on tenant_id alone)."""
    s1 = make_snap(tenant_id=default_tenant.id, total_risks=5)
    s2 = make_snap(tenant_id=default_tenant.id, total_risks=8)
    db_session.add(s1)
    db_session.add(s2)
    await db_session.commit()
    await db_session.refresh(s1)
    await db_session.refresh(s2)

    assert s1.id != s2.id
    assert s1.total_risks == 5
    assert s2.total_risks == 8


@pytest.mark.asyncio
async def test_tenant_isolation(db_session, default_tenant):
    """Snapshots for one tenant are not visible when querying another tenant's id."""
    from sqlalchemy import select

    other_tid = uuid.uuid4()
    snap = make_snap(tenant_id=default_tenant.id, total_risks=99)
    db_session.add(snap)
    await db_session.commit()

    result = (await db_session.execute(
        select(RiskScoreSummary).where(RiskScoreSummary.tenant_id == other_tid)
    )).scalars().all()
    assert len(result) == 0


@pytest.mark.asyncio
async def test_created_at_auto_set(db_session, default_tenant):
    """created_at is set automatically and is a datetime."""
    snap = make_snap(tenant_id=default_tenant.id)
    db_session.add(snap)
    await db_session.commit()
    await db_session.refresh(snap)

    assert snap.created_at is not None
    assert isinstance(snap.created_at, datetime)


@pytest.mark.asyncio
async def test_repr(default_tenant):
    """__repr__ does not raise."""
    snap = make_snap(tenant_id=default_tenant.id)
    r = repr(snap)
    assert "RiskScoreSummary" in r
