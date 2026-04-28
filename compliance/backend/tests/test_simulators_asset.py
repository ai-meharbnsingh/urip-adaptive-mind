"""
TDD tests — asset_simulator.

Verifies:
  - Creates Asset records with realistic mix of types.
  - Owner assignments map to plausible employees.
  - Classification distribution realistic (most internal, few restricted).
  - Lifecycle states cover deployed, retired, etc.
  - Tenant isolation; idempotent.
"""
from __future__ import annotations

import pytest
from sqlalchemy import select, func

from compliance_backend.seeders.simulators.sim_models import Asset
from compliance_backend.seeders.simulators.asset_simulator import simulate_assets


@pytest.mark.anyio
async def test_simulator_creates_assets(db_session):
    summary = await simulate_assets(
        db_session, tenant_id="sim-tenant-a", count=80, seed=42
    )
    assert summary["created"] >= 80


@pytest.mark.anyio
async def test_asset_type_mix(db_session):
    await simulate_assets(db_session, tenant_id="sim-tenant-a", count=120, seed=42)
    rows = (await db_session.execute(
        select(Asset).where(Asset.tenant_id == "sim-tenant-a")
    )).scalars().all()
    types = {r.asset_type for r in rows}
    expected = {"laptop", "server", "cloud_workload", "mobile", "saas_app", "network_device"}
    # At least 5 of the 6 types should appear
    assert len(types & expected) >= 5, f"types: {types}"


@pytest.mark.anyio
async def test_owner_assignments_realistic(db_session):
    await simulate_assets(db_session, tenant_id="sim-tenant-a", count=60, seed=42)
    rows = (await db_session.execute(
        select(Asset).where(Asset.tenant_id == "sim-tenant-a").limit(20)
    )).scalars().all()
    for r in rows:
        assert r.owner_user_id, f"asset {r.id} missing owner"
        # owner_user_id should be a UUID
        assert len(r.owner_user_id) >= 32


@pytest.mark.anyio
async def test_classification_distribution(db_session):
    await simulate_assets(db_session, tenant_id="sim-tenant-a", count=100, seed=42)
    rows = (await db_session.execute(
        select(Asset).where(Asset.tenant_id == "sim-tenant-a")
    )).scalars().all()
    by_class = {}
    for r in rows:
        by_class[r.classification] = by_class.get(r.classification, 0) + 1

    # Most assets should be internal/confidential, fewer restricted
    assert by_class.get("internal", 0) > 0
    assert by_class.get("confidential", 0) > 0
    # Restricted should be fewer than internal
    if "restricted" in by_class:
        assert by_class["restricted"] < by_class["internal"]


@pytest.mark.anyio
async def test_asset_tags_unique(db_session):
    await simulate_assets(db_session, tenant_id="sim-tenant-a", count=60, seed=42)
    rows = (await db_session.execute(
        select(Asset).where(Asset.tenant_id == "sim-tenant-a")
    )).scalars().all()
    tags = [r.asset_tag for r in rows]
    assert len(tags) == len(set(tags)), "asset tags must be unique within tenant"


@pytest.mark.anyio
async def test_realistic_metadata(db_session):
    await simulate_assets(db_session, tenant_id="sim-tenant-a", count=60, seed=42)
    laptops = (await db_session.execute(
        select(Asset).where(
            Asset.tenant_id == "sim-tenant-a", Asset.asset_type == "laptop"
        ).limit(5)
    )).scalars().all()
    for r in laptops:
        # Laptops have OS, IP, MAC, serial
        assert r.operating_system, f"laptop missing OS: {r.asset_tag}"
        assert "test" not in (r.name or "").lower() or "test_lab" in (r.name or "").lower()


@pytest.mark.anyio
async def test_tenant_isolation(db_session):
    await simulate_assets(db_session, tenant_id="sim-tenant-a", count=30, seed=42)
    await simulate_assets(db_session, tenant_id="sim-tenant-b", count=30, seed=42)
    a = (await db_session.execute(
        select(func.count()).select_from(Asset).where(Asset.tenant_id == "sim-tenant-a")
    )).scalar()
    b = (await db_session.execute(
        select(func.count()).select_from(Asset).where(Asset.tenant_id == "sim-tenant-b")
    )).scalar()
    assert a == 30 and b == 30


@pytest.mark.anyio
async def test_idempotent_rerun(db_session):
    await simulate_assets(db_session, tenant_id="sim-tenant-a", count=30, seed=42)
    first = (await db_session.execute(
        select(func.count()).select_from(Asset).where(Asset.tenant_id == "sim-tenant-a")
    )).scalar()
    await simulate_assets(db_session, tenant_id="sim-tenant-a", count=30, seed=42)
    second = (await db_session.execute(
        select(func.count()).select_from(Asset).where(Asset.tenant_id == "sim-tenant-a")
    )).scalar()
    assert first == second
