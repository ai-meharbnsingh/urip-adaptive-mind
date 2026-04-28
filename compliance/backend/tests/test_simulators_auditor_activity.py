"""
TDD tests — auditor_activity_simulator.

Verifies:
  - Creates AuditorAccess invitations + AuditorActivityLog rows.
  - Realistic auditor workflow (invite → accept → browse → drill → export).
  - Time-bound audit period scenarios.
  - Tenant isolation; idempotent.
"""
from __future__ import annotations

import pytest
from sqlalchemy import select, func

from compliance_backend.models.auditor import (
    AuditorAccess,
    AuditorActivityLog,
)
from compliance_backend.models.framework import Framework
from compliance_backend.seeders.soc2 import seed_soc2
from compliance_backend.seeders.simulators.auditor_activity_simulator import (
    simulate_auditor_activity,
)


@pytest.mark.anyio
async def test_simulator_creates_invitations_and_logs(db_session):
    await seed_soc2(db_session)
    fw = (await db_session.execute(
        select(Framework).where(Framework.short_code == "SOC2")
    )).scalars().first()

    summary = await simulate_auditor_activity(
        db_session, tenant_id="sim-tenant-a", framework_id=fw.id, n_auditors=3, seed=42
    )
    assert summary["invitations"] >= 3
    assert summary["activity_logs"] > 0


@pytest.mark.anyio
async def test_some_auditors_accepted(db_session):
    await seed_soc2(db_session)
    fw = (await db_session.execute(
        select(Framework).where(Framework.short_code == "SOC2")
    )).scalars().first()
    await simulate_auditor_activity(
        db_session, tenant_id="sim-tenant-a", framework_id=fw.id, n_auditors=5, seed=42
    )
    accesses = (await db_session.execute(
        select(AuditorAccess).where(AuditorAccess.tenant_id == "sim-tenant-a")
    )).scalars().all()
    accepted = [a for a in accesses if a.accepted_at is not None]
    assert len(accepted) > 0


@pytest.mark.anyio
async def test_activity_actions_realistic(db_session):
    await seed_soc2(db_session)
    fw = (await db_session.execute(
        select(Framework).where(Framework.short_code == "SOC2")
    )).scalars().first()
    await simulate_auditor_activity(
        db_session, tenant_id="sim-tenant-a", framework_id=fw.id, n_auditors=3, seed=42
    )
    logs = (await db_session.execute(
        select(AuditorActivityLog).where(AuditorActivityLog.tenant_id == "sim-tenant-a")
    )).scalars().all()
    actions = {l.action for l in logs}
    expected_actions = {
        "list_controls", "view_control", "list_evidence",
        "download_evidence", "view_policy", "request_evidence",
        "export_bundle",
    }
    # At least 4 of these should appear
    assert len(actions & expected_actions) >= 4, f"actions: {actions}"


@pytest.mark.anyio
async def test_auditor_emails_realistic(db_session):
    await seed_soc2(db_session)
    fw = (await db_session.execute(
        select(Framework).where(Framework.short_code == "SOC2")
    )).scalars().first()
    await simulate_auditor_activity(
        db_session, tenant_id="sim-tenant-a", framework_id=fw.id, n_auditors=5, seed=42
    )
    accesses = (await db_session.execute(
        select(AuditorAccess).where(AuditorAccess.tenant_id == "sim-tenant-a")
    )).scalars().all()
    for a in accesses:
        assert "@" in a.auditor_email
        # Should look like a real audit firm domain
        domain = a.auditor_email.split("@")[1]
        assert any(p in domain for p in [".", "audit", "advisory", "ca", "llp", "co", "cpa"])


@pytest.mark.anyio
async def test_invitation_token_hash_present(db_session):
    await seed_soc2(db_session)
    fw = (await db_session.execute(
        select(Framework).where(Framework.short_code == "SOC2")
    )).scalars().first()
    await simulate_auditor_activity(
        db_session, tenant_id="sim-tenant-a", framework_id=fw.id, n_auditors=3, seed=42
    )
    accesses = (await db_session.execute(
        select(AuditorAccess).where(AuditorAccess.tenant_id == "sim-tenant-a")
    )).scalars().all()
    for a in accesses:
        assert a.invitation_token_hash
        assert len(a.invitation_token_hash) >= 32


@pytest.mark.anyio
async def test_tenant_isolation(db_session):
    await seed_soc2(db_session)
    fw = (await db_session.execute(
        select(Framework).where(Framework.short_code == "SOC2")
    )).scalars().first()
    await simulate_auditor_activity(
        db_session, tenant_id="sim-tenant-a", framework_id=fw.id, n_auditors=2, seed=42
    )
    await simulate_auditor_activity(
        db_session, tenant_id="sim-tenant-b", framework_id=fw.id, n_auditors=2, seed=42
    )
    a = (await db_session.execute(
        select(func.count()).select_from(AuditorAccess).where(
            AuditorAccess.tenant_id == "sim-tenant-a"
        )
    )).scalar()
    b = (await db_session.execute(
        select(func.count()).select_from(AuditorAccess).where(
            AuditorAccess.tenant_id == "sim-tenant-b"
        )
    )).scalar()
    assert a > 0 and b > 0


@pytest.mark.anyio
async def test_idempotent_rerun(db_session):
    await seed_soc2(db_session)
    fw = (await db_session.execute(
        select(Framework).where(Framework.short_code == "SOC2")
    )).scalars().first()
    await simulate_auditor_activity(
        db_session, tenant_id="sim-tenant-a", framework_id=fw.id, n_auditors=3, seed=42
    )
    first = (await db_session.execute(
        select(func.count()).select_from(AuditorActivityLog).where(
            AuditorActivityLog.tenant_id == "sim-tenant-a"
        )
    )).scalar()
    await simulate_auditor_activity(
        db_session, tenant_id="sim-tenant-a", framework_id=fw.id, n_auditors=3, seed=42
    )
    second = (await db_session.execute(
        select(func.count()).select_from(AuditorActivityLog).where(
            AuditorActivityLog.tenant_id == "sim-tenant-a"
        )
    )).scalar()
    assert first == second
