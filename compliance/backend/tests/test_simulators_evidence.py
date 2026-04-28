"""
TDD tests — evidence_simulator.

Verifies:
  - Creates Evidence rows for controls.
  - Real placeholder files written to filesystem storage.
  - File contents are non-trivial (config JSON, ticket export JSON, log CSV).
  - Mix of types: screenshot/config/log/ticket/document.
  - metadata_json populated with realistic content.
  - Tenant isolation; idempotent.
"""
from __future__ import annotations

import json
import os
import pytest
from pathlib import Path
from sqlalchemy import select, func

from compliance_backend.models.evidence import Evidence
from compliance_backend.models.framework import Control
from compliance_backend.seeders.soc2 import seed_soc2
from compliance_backend.seeders.simulators.evidence_simulator import (
    simulate_evidence,
)


@pytest.mark.anyio
async def test_simulator_creates_evidence(db_session):
    await seed_soc2(db_session)
    summary = await simulate_evidence(
        db_session, tenant_id="sim-tenant-a", per_control=2, seed=42
    )
    assert summary["created"] > 0


@pytest.mark.anyio
async def test_evidence_types_diverse(db_session):
    await seed_soc2(db_session)
    await simulate_evidence(db_session, tenant_id="sim-tenant-a", per_control=3, seed=42)
    rows = (await db_session.execute(
        select(Evidence).where(Evidence.tenant_id == "sim-tenant-a")
    )).scalars().all()
    types = {r.type for r in rows}
    expected = {"screenshot", "config", "log", "ticket", "document"}
    # Should have at least 3 of the 5 types in any reasonable sample
    assert len(types & expected) >= 3, f"types observed: {types}"


@pytest.mark.anyio
async def test_real_files_written(db_session, tmp_path):
    # Override storage base dir
    os.environ["EVIDENCE_STORAGE_BASE_DIR"] = str(tmp_path)
    await seed_soc2(db_session)
    await simulate_evidence(db_session, tenant_id="sim-tenant-a", per_control=1, seed=42)

    rows = (await db_session.execute(
        select(Evidence).where(Evidence.tenant_id == "sim-tenant-a").limit(10)
    )).scalars().all()
    assert len(rows) > 0

    file_uri_rows = [r for r in rows if r.storage_uri.startswith("file://")]
    assert len(file_uri_rows) > 0
    for r in file_uri_rows[:5]:
        path = Path(r.storage_uri.replace("file://", ""))
        assert path.exists(), f"file does not exist: {path}"
        content = path.read_bytes()
        assert len(content) > 50, f"file too small: {len(content)} bytes"
        # No placeholder
        assert b"lorem ipsum" not in content.lower()
        assert b"todo" not in content.lower() or b"todo by" in content.lower()


@pytest.mark.anyio
async def test_metadata_realistic(db_session):
    await seed_soc2(db_session)
    await simulate_evidence(db_session, tenant_id="sim-tenant-a", per_control=2, seed=42)
    rows = (await db_session.execute(
        select(Evidence).where(Evidence.tenant_id == "sim-tenant-a").limit(20)
    )).scalars().all()
    assert len(rows) > 0
    for r in rows:
        assert r.metadata_json is not None, f"evidence {r.id} missing metadata"
        assert isinstance(r.metadata_json, dict)
        # Each metadata entry should have a 'source' field
        assert "source" in r.metadata_json or "tool" in r.metadata_json or "system" in r.metadata_json


@pytest.mark.anyio
async def test_audit_period_format(db_session):
    await seed_soc2(db_session)
    await simulate_evidence(db_session, tenant_id="sim-tenant-a", per_control=1, seed=42)
    rows = (await db_session.execute(
        select(Evidence).where(Evidence.tenant_id == "sim-tenant-a").limit(5)
    )).scalars().all()
    for r in rows:
        # audit_period should be e.g. "2026" or "2026-Q1" or "2026-H1"
        assert r.audit_period
        assert any(s in r.audit_period for s in ["202", "Q1", "Q2", "Q3", "Q4", "H1", "H2"])


@pytest.mark.anyio
async def test_tenant_isolation(db_session):
    await seed_soc2(db_session)
    await simulate_evidence(db_session, tenant_id="sim-tenant-a", per_control=1, seed=42)
    await simulate_evidence(db_session, tenant_id="sim-tenant-b", per_control=1, seed=42)
    a = (await db_session.execute(
        select(func.count()).select_from(Evidence).where(Evidence.tenant_id == "sim-tenant-a")
    )).scalar()
    b = (await db_session.execute(
        select(func.count()).select_from(Evidence).where(Evidence.tenant_id == "sim-tenant-b")
    )).scalar()
    assert a > 0 and b > 0


@pytest.mark.anyio
async def test_idempotent_rerun(db_session):
    await seed_soc2(db_session)
    await simulate_evidence(db_session, tenant_id="sim-tenant-a", per_control=1, seed=42)
    first = (await db_session.execute(
        select(func.count()).select_from(Evidence).where(Evidence.tenant_id == "sim-tenant-a")
    )).scalar()
    await simulate_evidence(db_session, tenant_id="sim-tenant-a", per_control=1, seed=42)
    second = (await db_session.execute(
        select(func.count()).select_from(Evidence).where(Evidence.tenant_id == "sim-tenant-a")
    )).scalar()
    assert first == second
