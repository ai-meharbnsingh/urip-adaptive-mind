"""Model-level tests: rows insert + relationships behave."""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select

from backend.models.vapt_vendor import (
    VaptSubmission,
    VaptVendor,
    VaptVendorInvitation,
)


@pytest.mark.asyncio
async def test_vapt_vendor_row_inserts(db_session, default_tenant, auth_headers):
    """A VaptVendor row inserts and is queryable."""
    from backend.models.user import User
    res = await db_session.execute(
        select(User).where(User.email == "ciso@urip.test")
    )
    user = res.scalar_one()

    vendor = VaptVendor(
        id=uuid.uuid4(),
        tenant_id=default_tenant.id,
        name="TestCo",
        contact_email="t@test.test",
        invited_by_user_id=user.id,
        invited_at=datetime.now(timezone.utc),
    )
    db_session.add(vendor)
    await db_session.commit()

    found = await db_session.get(VaptVendor, vendor.id)
    assert found is not None
    assert found.name == "TestCo"
    assert found.status == "active"
    assert found.tenant_id == default_tenant.id


@pytest.mark.asyncio
async def test_vapt_invitation_row_inserts(
    db_session, default_tenant, auth_headers, vapt_vendor
):
    """An invitation row links to its vendor."""
    inv = VaptVendorInvitation(
        id=uuid.uuid4(),
        vapt_vendor_id=vapt_vendor.id,
        invitation_token_hash="a" * 64,
        expires_at=datetime.now(timezone.utc) + timedelta(days=7),
        invited_by_user_id=vapt_vendor.invited_by_user_id,
    )
    db_session.add(inv)
    await db_session.commit()

    found = await db_session.get(VaptVendorInvitation, inv.id)
    assert found is not None
    assert found.vapt_vendor_id == vapt_vendor.id
    assert found.accepted_at is None


@pytest.mark.asyncio
async def test_vapt_submission_row_inserts(
    db_session, default_tenant, vapt_vendor
):
    """A submission row links to vendor + tenant."""
    sub = VaptSubmission(
        id=uuid.uuid4(),
        vapt_vendor_id=vapt_vendor.id,
        tenant_id=default_tenant.id,
        finding_title="Test SQLi",
        cvss_score=8.5,
        severity="high",
        submitted_at=datetime.now(timezone.utc),
        status="submitted",
    )
    db_session.add(sub)
    await db_session.commit()

    found = await db_session.get(VaptSubmission, sub.id)
    assert found is not None
    assert found.tenant_id == default_tenant.id
    assert found.vapt_vendor_id == vapt_vendor.id
    assert float(found.cvss_score) == 8.5
    assert found.status == "submitted"
    assert found.risk_record_id is None  # not yet linked


@pytest.mark.asyncio
async def test_vapt_vendor_status_defaults_to_active(
    db_session, default_tenant, auth_headers
):
    """status default = 'active' (DB-side default)."""
    from backend.models.user import User
    res = await db_session.execute(
        select(User).where(User.email == "ciso@urip.test")
    )
    user = res.scalar_one()

    vendor = VaptVendor(
        id=uuid.uuid4(),
        tenant_id=default_tenant.id,
        name="Default Co",
        contact_email="default@test.test",
        invited_by_user_id=user.id,
        invited_at=datetime.now(timezone.utc),
    )
    db_session.add(vendor)
    await db_session.commit()
    await db_session.refresh(vendor)
    assert vendor.status == "active"


@pytest.mark.asyncio
async def test_vapt_submission_unique_per_vendor_tenant(
    db_session, default_tenant, vapt_vendor
):
    """Multiple submissions per vendor are allowed (no uniqueness on title)."""
    for i in range(3):
        sub = VaptSubmission(
            id=uuid.uuid4(),
            vapt_vendor_id=vapt_vendor.id,
            tenant_id=default_tenant.id,
            finding_title=f"Bug #{i}",
            cvss_score=5.0,
            severity="medium",
            submitted_at=datetime.now(timezone.utc),
            status="submitted",
        )
        db_session.add(sub)
    await db_session.commit()

    res = await db_session.execute(
        select(VaptSubmission).where(VaptSubmission.vapt_vendor_id == vapt_vendor.id)
    )
    rows = res.scalars().all()
    assert len(rows) == 3
