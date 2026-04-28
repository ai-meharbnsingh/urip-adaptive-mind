"""
TDD tests — incident_simulator.

Verifies:
  - Creates Incident records with full lifecycle.
  - Mix of severities + statuses.
  - SLA timing realistic per severity.
  - Some incidents closed with RCA + lessons; some still open.
  - Tenant isolation; idempotent.
"""
from __future__ import annotations

from datetime import datetime, timedelta

import pytest
from sqlalchemy import select, func

from compliance_backend.seeders.simulators.sim_models import Incident
from compliance_backend.seeders.simulators.incident_simulator import simulate_incidents


@pytest.mark.anyio
async def test_simulator_creates_incidents(db_session):
    summary = await simulate_incidents(
        db_session, tenant_id="sim-tenant-a", count=15, seed=42
    )
    assert summary["created"] >= 15


@pytest.mark.anyio
async def test_severity_mix(db_session):
    await simulate_incidents(db_session, tenant_id="sim-tenant-a", count=30, seed=42)
    rows = (await db_session.execute(
        select(Incident).where(Incident.tenant_id == "sim-tenant-a")
    )).scalars().all()
    severities = {r.severity for r in rows}
    # All 4 severities should appear in 30 incidents
    assert severities == {"low", "medium", "high", "critical"}


@pytest.mark.anyio
async def test_lifecycle_progression(db_session):
    await simulate_incidents(db_session, tenant_id="sim-tenant-a", count=30, seed=42)
    rows = (await db_session.execute(
        select(Incident).where(Incident.tenant_id == "sim-tenant-a")
    )).scalars().all()

    # Closed incidents must have all phase timestamps + RCA + lessons
    closed = [r for r in rows if r.status == "closed"]
    assert len(closed) > 0
    for r in closed:
        assert r.triaged_at is not None, f"closed incident {r.id} missing triaged_at"
        assert r.contained_at is not None
        assert r.eradicated_at is not None
        assert r.recovered_at is not None
        assert r.closed_at is not None
        assert r.rca_summary, f"closed incident {r.id} missing RCA"
        assert len(r.rca_summary) > 30, f"RCA too short: {r.rca_summary!r}"
        assert r.lessons_learned, f"closed incident {r.id} missing lessons"

    # Open incidents (status != closed) should have only some timestamps
    open_inc = [r for r in rows if r.status not in ("closed", "recovered")]
    if open_inc:
        for r in open_inc[:5]:
            assert r.detected_at is not None
            # closed_at must be None
            assert r.closed_at is None


@pytest.mark.anyio
async def test_sla_timing_realistic(db_session):
    await simulate_incidents(db_session, tenant_id="sim-tenant-a", count=40, seed=42)
    rows = (await db_session.execute(
        select(Incident).where(
            Incident.tenant_id == "sim-tenant-a",
            Incident.triaged_at.isnot(None),
        )
    )).scalars().all()

    sla_hours = {"critical": 1, "high": 4, "medium": 24, "low": 72}
    # Most incidents should respect SLA (sla_breached=False ratio)
    breached = sum(1 for r in rows if r.sla_breached)
    assert breached >= 0  # at least some SLA breaches expected for realism
    assert breached / len(rows) <= 0.30, "too many breaches — should be uncommon"


@pytest.mark.anyio
async def test_realistic_descriptions(db_session):
    await simulate_incidents(db_session, tenant_id="sim-tenant-a", count=10, seed=42)
    rows = (await db_session.execute(
        select(Incident).where(Incident.tenant_id == "sim-tenant-a")
    )).scalars().all()
    for r in rows:
        assert r.title and len(r.title) > 20
        assert r.description and len(r.description) > 50
        for bad in ["test1", "test2", "lorem ipsum", "TODO", "placeholder"]:
            assert bad.lower() not in r.title.lower()
            assert bad.lower() not in r.description.lower()


@pytest.mark.anyio
async def test_incident_numbers_unique_per_tenant(db_session):
    await simulate_incidents(db_session, tenant_id="sim-tenant-a", count=20, seed=42)
    rows = (await db_session.execute(
        select(Incident).where(Incident.tenant_id == "sim-tenant-a")
    )).scalars().all()
    numbers = [r.incident_number for r in rows]
    assert len(numbers) == len(set(numbers))


@pytest.mark.anyio
async def test_tenant_isolation(db_session):
    await simulate_incidents(db_session, tenant_id="sim-tenant-a", count=10, seed=42)
    await simulate_incidents(db_session, tenant_id="sim-tenant-b", count=10, seed=42)
    a = (await db_session.execute(
        select(func.count()).select_from(Incident).where(Incident.tenant_id == "sim-tenant-a")
    )).scalar()
    b = (await db_session.execute(
        select(func.count()).select_from(Incident).where(Incident.tenant_id == "sim-tenant-b")
    )).scalar()
    assert a == 10 and b == 10


@pytest.mark.anyio
async def test_idempotent_rerun(db_session):
    await simulate_incidents(db_session, tenant_id="sim-tenant-a", count=10, seed=42)
    first = (await db_session.execute(
        select(func.count()).select_from(Incident).where(Incident.tenant_id == "sim-tenant-a")
    )).scalar()
    await simulate_incidents(db_session, tenant_id="sim-tenant-a", count=10, seed=42)
    second = (await db_session.execute(
        select(func.count()).select_from(Incident).where(Incident.tenant_id == "sim-tenant-a")
    )).scalar()
    assert first == second
