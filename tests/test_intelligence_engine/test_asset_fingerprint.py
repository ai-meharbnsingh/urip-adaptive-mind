import uuid
from types import SimpleNamespace

import pytest


def test_compute_asset_fingerprint_is_case_insensitive_and_ip_canonicalized():
    from backend.services.asset_fingerprint_service import compute_asset_fingerprint

    fp1 = compute_asset_fingerprint(
        mac="AA:BB:CC:DD:EE:FF",
        hostname="SAP-PRD-01",
        ip="2001:0db8:0000:0000:0000:0000:0000:0001",
    )
    fp2 = compute_asset_fingerprint(
        mac="aa:bb:cc:dd:ee:ff",
        hostname="sap-prd-01",
        ip="2001:db8::1",
    )
    assert fp1 == fp2
    assert len(fp1) == 64


@pytest.mark.asyncio
async def test_find_existing_risk_returns_none_on_no_match(db_session, default_tenant):
    from backend.models.risk import Risk
    from backend.services.asset_fingerprint_service import find_existing_risk

    r = Risk(
        risk_id="RISK-2026-AAAA",
        finding="Test",
        description=None,
        source="crowdstrike",
        domain="network",
        cvss_score=9.0,
        severity="critical",
        asset="SAP-PRD-01",
        owner_team="IT",
        status="open",
        sla_deadline=__import__("datetime").datetime.now(__import__("datetime").timezone.utc),
        cve_id="CVE-2021-44228",
        tenant_id=default_tenant.id,
        fingerprint_key="deadbeef" * 8,
        sources_attributed=["crowdstrike"],
    )
    db_session.add(r)
    await db_session.commit()

    # Pass the test session in explicitly. Without ``db=``, find_existing_risk
    # opens a fresh session via backend.database.async_session — but the
    # fingerprint_service captured that binding at import time (before the
    # test conftest replaced it with the SQLite session factory), so it would
    # try to connect to the real Postgres URL on port 5433 and time out.
    # Per INV-6, we don't change the assertion; we wire the fixture
    # correctly. All production callers (connector_runner, advisory service)
    # already pass ``db=db`` — the in-test path now matches.
    found = await find_existing_risk(
        tenant_id=default_tenant.id,
        fingerprint="00" * 32,
        cve_id="CVE-2021-44228",
        db=db_session,
    )
    assert found is None


@pytest.mark.asyncio
async def test_merge_risk_keeps_higher_score_and_attributes_sources(db_session, default_tenant):
    from backend.models.risk import Risk
    from backend.services.asset_fingerprint_service import merge_risk

    existing = Risk(
        risk_id="RISK-2026-BBBB",
        finding="Existing",
        description=None,
        source="crowdstrike",
        domain="network",
        cvss_score=7.0,
        severity="high",
        asset="SAP-PRD-01",
        owner_team="IT",
        status="open",
        sla_deadline=__import__("datetime").datetime.now(__import__("datetime").timezone.utc),
        cve_id="CVE-2021-44228",
        tenant_id=default_tenant.id,
        composite_score=5.0,
        fingerprint_key="11" * 32,
        sources_attributed=["crowdstrike"],
        remediation_steps=["Restart service"],
    )
    db_session.add(existing)
    await db_session.commit()

    new_finding = SimpleNamespace(
        source="vapt",
        composite_score=7.0,
        remediation_steps=["Apply patch"],
    )
    merged = merge_risk(existing, new_finding)

    assert float(merged.composite_score) == 7.0
    assert set(merged.sources_attributed) == {"crowdstrike", "vapt"}
    assert set(merged.remediation_steps) == {"Restart service", "Apply patch"}

