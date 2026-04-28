"""
End-to-end submission pipeline:
  vendor.submit_finding → VaptSubmission created → URIP Risk created and linked
  → background enrich_risk fired (mocked here to avoid real HTTP).
"""
from __future__ import annotations

import pytest
from sqlalchemy import select

from backend.models.risk import Risk
from backend.models.vapt_vendor import VaptSubmission
from backend.services.vapt_vendor_service import VaptVendorService


@pytest.mark.asyncio
async def test_submit_finding_creates_linked_risk(
    db_session, vapt_vendor
):
    svc = VaptVendorService(db=db_session)
    created = await svc.submit_finding(
        vendor=vapt_vendor,
        finding_title="SQL Injection",
        cvss_score=8.5,
        severity="high",
        cve_id="CVE-2023-99999",
        affected_asset_hostname="api.urip.test",
        affected_asset_ip="10.1.1.1",
        exploit_maturity="poc",
        description="App accepts ' OR 1=1 --",
        remediation_recommendation="Parameterised queries",
        schedule_enrichment=False,  # don't fire async task in test
    )
    await db_session.commit()

    # Both rows exist
    sub = created.submission
    risk = created.risk
    assert sub.id is not None
    assert risk.id is not None

    # Linkage
    assert sub.risk_record_id == risk.id

    # Risk fields
    assert risk.finding == "SQL Injection"
    assert risk.cve_id == "CVE-2023-99999"
    assert risk.severity == "high"
    assert float(risk.cvss_score) == 8.5
    assert risk.status == "open"
    assert risk.source.startswith("vapt_vendor:")
    assert risk.tenant_id == vapt_vendor.tenant_id
    assert risk.composite_score is not None

    # Risk got an SLA deadline
    assert risk.sla_deadline is not None


@pytest.mark.asyncio
async def test_submit_finding_no_cve_still_creates_risk(
    db_session, vapt_vendor
):
    svc = VaptVendorService(db=db_session)
    created = await svc.submit_finding(
        vendor=vapt_vendor,
        finding_title="Logic flaw",
        cvss_score=4.0,
        severity="medium",
        schedule_enrichment=False,
    )
    await db_session.commit()
    assert created.risk.cve_id is None
    # Composite is still computed (severity-default EPSS used)
    assert created.risk.composite_score is not None


@pytest.mark.asyncio
async def test_submit_finding_invalid_severity_raises(
    db_session, vapt_vendor
):
    svc = VaptVendorService(db=db_session)
    with pytest.raises(ValueError):
        await svc.submit_finding(
            vendor=vapt_vendor,
            finding_title="X",
            cvss_score=5.0,
            severity="not-a-thing",
            schedule_enrichment=False,
        )


@pytest.mark.asyncio
async def test_submit_finding_clamps_cvss_to_range(
    db_session, vapt_vendor
):
    """CVSS 12.0 → clamped to 10.0."""
    svc = VaptVendorService(db=db_session)
    created = await svc.submit_finding(
        vendor=vapt_vendor,
        finding_title="X",
        cvss_score=12.0,
        severity="critical",
        schedule_enrichment=False,
    )
    await db_session.commit()
    assert float(created.risk.cvss_score) == 10.0


@pytest.mark.asyncio
async def test_submit_finding_audit_log_written(
    db_session, vapt_vendor
):
    from backend.models.audit_log import AuditLog
    svc = VaptVendorService(db=db_session)
    created = await svc.submit_finding(
        vendor=vapt_vendor,
        finding_title="X",
        cvss_score=5.0,
        severity="medium",
        schedule_enrichment=False,
    )
    await db_session.commit()

    res = await db_session.execute(
        select(AuditLog).where(
            AuditLog.action == "vapt_submission_created",
            AuditLog.resource_id == created.submission.id,
        )
    )
    rows = res.scalars().all()
    assert len(rows) == 1
    assert rows[0].tenant_id == vapt_vendor.tenant_id
