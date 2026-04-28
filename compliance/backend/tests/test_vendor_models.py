"""
TDD — vendor/third-party risk SQLAlchemy model tests (P2B.7).

Focus:
  - Creation
  - Relationship wiring (FK intent)
  - Tenant isolation fields exist + are queryable
  - Enum-like constraints (criticality/status/document_type)
"""
from __future__ import annotations

from datetime import datetime, date

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

# Import ensures tables are registered on Base.metadata before create_all (engine fixture).
from compliance_backend.models.vendor import (
    Vendor,
    VendorQuestionnaire,
    VendorDocument,
    VendorRiskScore,
)


@pytest.mark.anyio
async def test_vendor_create_and_query_by_tenant(db_session):
    v = Vendor(
        tenant_id="tenant-a",
        name="Acme Cloud",
        criticality="high",
        contact_email="security@acme.example",
        contact_name="Alice",
        status="active",
        onboarded_at=datetime.utcnow(),
        next_review_at=date.today(),
    )
    db_session.add(v)
    await db_session.commit()

    result = await db_session.execute(
        select(Vendor).where(Vendor.tenant_id == "tenant-a", Vendor.name == "Acme Cloud")
    )
    fetched = result.scalars().first()
    assert fetched is not None
    assert fetched.id is not None
    assert fetched.criticality == "high"


@pytest.mark.anyio
async def test_vendor_relationships_questionnaire_document_score(db_session):
    v = Vendor(
        tenant_id="tenant-a",
        name="Example Vendor",
        criticality="medium",
        contact_email=None,
        contact_name=None,
        status="under_review",
    )
    db_session.add(v)
    await db_session.flush()

    q = VendorQuestionnaire(
        vendor_id=v.id,
        template_name="SOC 2 Vendor Questionnaire",
        status="pending",
        responses_json=None,
    )
    d = VendorDocument(
        vendor_id=v.id,
        document_type="CONTRACT",
        filename="contract.pdf",
        storage_uri="file:///tmp/contract.pdf",
        valid_from=None,
        valid_until=None,
        uploaded_by_user_id="user-1",
    )
    s = VendorRiskScore(
        vendor_id=v.id,
        score=42,
        factors_json={"base": 25},
    )

    db_session.add_all([q, d, s])
    await db_session.commit()

    # Relationship intent: querying back via vendor_id works
    q2 = (await db_session.execute(select(VendorQuestionnaire).where(VendorQuestionnaire.vendor_id == v.id))).scalars().all()
    d2 = (await db_session.execute(select(VendorDocument).where(VendorDocument.vendor_id == v.id))).scalars().all()
    s2 = (await db_session.execute(select(VendorRiskScore).where(VendorRiskScore.vendor_id == v.id))).scalars().all()

    assert len(q2) == 1
    assert len(d2) == 1
    assert len(s2) == 1


@pytest.mark.anyio
async def test_vendor_criticality_check_constraint_rejects_invalid(db_session):
    v = Vendor(
        tenant_id="tenant-a",
        name="Bad Vendor",
        criticality="super_critical",  # invalid
        status="active",
    )
    db_session.add(v)
    with pytest.raises(IntegrityError):
        await db_session.commit()


@pytest.mark.anyio
async def test_vendor_document_type_check_constraint_rejects_invalid(db_session):
    v = Vendor(tenant_id="tenant-a", name="Doc Vendor", criticality="low", status="active")
    db_session.add(v)
    await db_session.flush()

    d = VendorDocument(
        vendor_id=v.id,
        document_type="NOT_A_REAL_TYPE",
        filename="x.txt",
        storage_uri="file:///tmp/x.txt",
        uploaded_by_user_id="user-1",
    )
    db_session.add(d)
    with pytest.raises(IntegrityError):
        await db_session.commit()

