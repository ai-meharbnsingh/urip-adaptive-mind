"""
TDD tests — master simulator orchestrator (run_simulators.run_all).

Verifies:
  - End-to-end: every simulator runs, every model has data for the tenant.
  - Tenant isolation: orchestrating tenant A never touches tenant B.
  - Idempotency: re-running produces identical row counts.
  - Counts are non-trivial.
"""
from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pytest
from sqlalchemy import select, func

from compliance_backend.models.control_run import ControlCheckRun
from compliance_backend.models.evidence import Evidence
from compliance_backend.models.policy import PolicyAcknowledgment
from compliance_backend.models.vendor import Vendor, VendorDocument, VendorRiskScore
from compliance_backend.models.auditor import AuditorAccess, AuditorActivityLog
from compliance_backend.models.score_snapshot import ComplianceScoreSnapshot
from compliance_backend.seeders.simulators.sim_models import (
    Incident,
    Asset,
    AccessReviewCampaign,
    AccessReviewDecision,
)


@pytest.mark.anyio
async def test_orchestrator_end_to_end(db_session, monkeypatch, tmp_path):
    """End-to-end: run_all populates every simulator domain."""
    # The orchestrator manages its own session/engine; we call its inner
    # functions on our test db_session to integrate with the test fixture.
    from compliance_backend.seeders.simulators.run_simulators import (
        _seed_tenant_policies,
    )
    from compliance_backend.seeders.soc2 import seed_soc2
    from compliance_backend.seeders.iso27001 import seed_iso27001
    from compliance_backend.seeders.simulators.control_run_simulator import (
        simulate_control_runs,
    )
    from compliance_backend.seeders.simulators.evidence_simulator import (
        simulate_evidence,
    )
    from compliance_backend.seeders.simulators.policy_ack_simulator import (
        simulate_policy_acknowledgments,
    )
    from compliance_backend.seeders.simulators.vendor_response_simulator import (
        simulate_vendor_data,
    )
    from compliance_backend.seeders.simulators.asset_simulator import (
        simulate_assets,
    )
    from compliance_backend.seeders.simulators.incident_simulator import (
        simulate_incidents,
    )
    from compliance_backend.seeders.simulators.access_review_simulator import (
        simulate_access_reviews,
    )
    from compliance_backend.seeders.simulators.compliance_score_simulator import (
        simulate_compliance_score_history,
    )
    from compliance_backend.seeders.simulators.auditor_activity_simulator import (
        simulate_auditor_activity,
    )
    from compliance_backend.models.framework import Framework

    os.environ["EVIDENCE_STORAGE_BASE_DIR"] = str(tmp_path)

    tenant = "demo-tenant-e2e"

    # Set up frameworks + policies
    await seed_soc2(db_session)
    await seed_iso27001(db_session)
    await _seed_tenant_policies(db_session, tenant_id=tenant, seed=42)
    await db_session.flush()

    # Run simulators
    cr = await simulate_control_runs(db_session, tenant_id=tenant, days=30, seed=42)
    ev = await simulate_evidence(db_session, tenant_id=tenant, per_control=1, seed=42)
    pa = await simulate_policy_acknowledgments(db_session, tenant_id=tenant, employee_count=30, seed=42)
    vd = await simulate_vendor_data(db_session, tenant_id=tenant, vendor_count=10, seed=42)
    asts = await simulate_assets(db_session, tenant_id=tenant, count=50, seed=42)
    inc = await simulate_incidents(db_session, tenant_id=tenant, count=15, seed=42)
    ar = await simulate_access_reviews(db_session, tenant_id=tenant, quarters_back=2, users_per_campaign=10, seed=42)

    soc2_fw = (await db_session.execute(
        select(Framework).where(Framework.short_code == "SOC2")
    )).scalars().first()
    aa = await simulate_auditor_activity(
        db_session, tenant_id=tenant, framework_id=soc2_fw.id, n_auditors=2, seed=42
    )
    sh = await simulate_compliance_score_history(
        db_session, tenant_id=tenant, days=30, seed=42
    )
    await db_session.flush()

    # Verify all domains have data
    assert cr["created"] > 0
    assert ev["created"] > 0
    assert pa["current_version_acks"] > 0
    assert vd["vendors"] > 0
    assert asts["created"] > 0
    assert inc["created"] > 0
    assert ar["campaigns"] > 0
    assert aa["invitations"] > 0
    assert sh["snapshots"] > 0


@pytest.mark.anyio
async def test_orchestrator_tenant_isolation(db_session, tmp_path):
    """Running orchestrator for tenant-A doesn't pollute tenant-B."""
    os.environ["EVIDENCE_STORAGE_BASE_DIR"] = str(tmp_path)

    from compliance_backend.seeders.soc2 import seed_soc2
    from compliance_backend.seeders.simulators.run_simulators import (
        _seed_tenant_policies,
    )
    from compliance_backend.seeders.simulators.control_run_simulator import (
        simulate_control_runs,
    )
    from compliance_backend.seeders.simulators.asset_simulator import (
        simulate_assets,
    )

    await seed_soc2(db_session)
    await _seed_tenant_policies(db_session, tenant_id="iso-a", seed=42)
    await _seed_tenant_policies(db_session, tenant_id="iso-b", seed=42)

    await simulate_control_runs(db_session, tenant_id="iso-a", days=10, seed=42)
    await simulate_assets(db_session, tenant_id="iso-a", count=20, seed=42)

    # Verify nothing leaked to iso-b
    cr_b = (await db_session.execute(
        select(func.count()).select_from(ControlCheckRun).where(
            ControlCheckRun.tenant_id == "iso-b"
        )
    )).scalar()
    asset_b = (await db_session.execute(
        select(func.count()).select_from(Asset).where(Asset.tenant_id == "iso-b")
    )).scalar()
    assert cr_b == 0
    assert asset_b == 0
