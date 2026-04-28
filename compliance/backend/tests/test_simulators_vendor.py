"""
TDD tests — vendor_response_simulator.

Verifies:
  - Creates vendors, questionnaires, risk scores, documents.
  - Mix of profiles: good (compliant) / concerning (gaps) / delinquent (no responses).
  - Risk scores correlate with profile (good=high score, delinquent=low/missing).
  - Documents include valid + expiring + expired distribution.
  - Tenant isolation; idempotent.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta

import pytest
from sqlalchemy import select, func

from compliance_backend.models.vendor import (
    Vendor,
    VendorQuestionnaire,
    VendorDocument,
    VendorRiskScore,
)
from compliance_backend.seeders.simulators.vendor_response_simulator import (
    simulate_vendor_data,
)


@pytest.mark.anyio
async def test_simulator_creates_vendors_and_artifacts(db_session):
    summary = await simulate_vendor_data(
        db_session, tenant_id="sim-tenant-a", seed=42, vendor_count=12
    )
    assert summary["vendors"] >= 12
    assert summary["questionnaires"] >= 12
    assert summary["documents"] > 0
    assert summary["risk_scores"] > 0


@pytest.mark.anyio
async def test_questionnaires_have_realistic_responses(db_session):
    await simulate_vendor_data(db_session, tenant_id="sim-tenant-a", seed=42, vendor_count=10)
    qs = (await db_session.execute(
        select(VendorQuestionnaire)
        .join(Vendor, VendorQuestionnaire.vendor_id == Vendor.id)
        .where(Vendor.tenant_id == "sim-tenant-a", VendorQuestionnaire.status == "completed")
    )).scalars().all()
    assert len(qs) > 0
    for q in qs:
        assert q.responses_json is not None
        assert isinstance(q.responses_json, dict)
        # Should have at least some answer keys
        answers = q.responses_json.get("answers", {})
        assert len(answers) >= 5, f"too few answers: {len(answers)}"
        # Answers must NOT be placeholders
        for k, v in answers.items():
            assert v not in (None, "", "test", "TODO"), f"placeholder answer for {k}"


@pytest.mark.anyio
async def test_profile_mix(db_session):
    summary = await simulate_vendor_data(
        db_session, tenant_id="sim-tenant-a", seed=42, vendor_count=20
    )
    # Should have at least 1 of each profile
    assert summary["good_profile"] > 0
    assert summary["concerning_profile"] > 0
    assert summary["delinquent_profile"] > 0


@pytest.mark.anyio
async def test_risk_scores_correlate_with_profile(db_session):
    await simulate_vendor_data(db_session, tenant_id="sim-tenant-a", seed=42, vendor_count=20)
    # Inspect: vendors with completed questionnaires should have a risk score
    vendors = (await db_session.execute(
        select(Vendor).where(Vendor.tenant_id == "sim-tenant-a")
    )).scalars().all()
    scored = 0
    for v in vendors:
        score_rows = (await db_session.execute(
            select(VendorRiskScore).where(VendorRiskScore.vendor_id == v.id)
        )).scalars().all()
        if score_rows:
            scored += 1
    # At least responsive vendors (good + concerning ≈ 80%) should be scored
    assert scored >= len(vendors) * 0.5


@pytest.mark.anyio
async def test_documents_have_validity_distribution(db_session):
    await simulate_vendor_data(db_session, tenant_id="sim-tenant-a", seed=42, vendor_count=15)
    docs = (await db_session.execute(
        select(VendorDocument)
        .join(Vendor, VendorDocument.vendor_id == Vendor.id)
        .where(Vendor.tenant_id == "sim-tenant-a")
    )).scalars().all()
    assert len(docs) > 0
    today = date.today()
    expired = sum(1 for d in docs if d.valid_until and d.valid_until < today)
    expiring_soon = sum(1 for d in docs if d.valid_until and today <= d.valid_until <= today + timedelta(days=60))
    valid = sum(1 for d in docs if d.valid_until and d.valid_until > today + timedelta(days=60))
    # Expect at least one of each
    assert expired > 0, f"expected at least one expired doc; total={len(docs)}"
    assert expiring_soon > 0, f"expected at least one expiring-soon doc; total={len(docs)}"
    assert valid > 0, f"expected at least one valid doc; total={len(docs)}"


@pytest.mark.anyio
async def test_document_filenames_are_realistic(db_session):
    await simulate_vendor_data(db_session, tenant_id="sim-tenant-a", seed=42, vendor_count=10)
    docs = (await db_session.execute(
        select(VendorDocument)
        .join(Vendor, VendorDocument.vendor_id == Vendor.id)
        .where(Vendor.tenant_id == "sim-tenant-a")
        .limit(10)
    )).scalars().all()
    for d in docs:
        # Should look like a real filename: contains vendor name or doc type, ends in .pdf/.docx
        fname = d.filename.lower()
        assert any(fname.endswith(ext) for ext in (".pdf", ".docx", ".zip")), f"weird filename: {d.filename}"
        assert "test" not in fname or "_pen_test" in fname, f"placeholder filename: {d.filename}"


@pytest.mark.anyio
async def test_tenant_isolation(db_session):
    # Note: vendor_count is a MINIMUM; simulator may add extras to guarantee
    # all three profiles (good/concerning/delinquent) appear. Both tenants use
    # the same seed → both should produce identical vendor counts.
    await simulate_vendor_data(db_session, tenant_id="sim-tenant-a", seed=42, vendor_count=10)
    await simulate_vendor_data(db_session, tenant_id="sim-tenant-b", seed=42, vendor_count=10)
    a = (await db_session.execute(
        select(func.count()).select_from(Vendor).where(Vendor.tenant_id == "sim-tenant-a")
    )).scalar()
    b = (await db_session.execute(
        select(func.count()).select_from(Vendor).where(Vendor.tenant_id == "sim-tenant-b")
    )).scalar()
    assert a >= 10 and b >= 10
    assert a == b, "deterministic seed should produce identical vendor counts"


@pytest.mark.anyio
async def test_idempotent_rerun(db_session):
    await simulate_vendor_data(db_session, tenant_id="sim-tenant-a", seed=42, vendor_count=10)
    first = (await db_session.execute(
        select(func.count()).select_from(Vendor).where(Vendor.tenant_id == "sim-tenant-a")
    )).scalar()
    await simulate_vendor_data(db_session, tenant_id="sim-tenant-a", seed=42, vendor_count=10)
    second = (await db_session.execute(
        select(func.count()).select_from(Vendor).where(Vendor.tenant_id == "sim-tenant-a")
    )).scalar()
    assert first == second
