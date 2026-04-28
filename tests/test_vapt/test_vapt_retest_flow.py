"""Re-test workflow: admin requests → vendor responds → auto-close on pass."""
from __future__ import annotations

import pytest
from sqlalchemy import select

from backend.models.risk import Risk
from backend.services.vapt_vendor_service import VaptVendorService


async def _submit_and_get(db_session, vapt_vendor):
    svc = VaptVendorService(db=db_session)
    created = await svc.submit_finding(
        vendor=vapt_vendor,
        finding_title="X-Frame-Options missing",
        cvss_score=4.5,
        severity="medium",
        schedule_enrichment=False,
    )
    await db_session.commit()
    return svc, created.submission, created.risk


@pytest.mark.asyncio
async def test_request_retest_transitions_status(
    db_session, vapt_vendor, auth_headers
):
    from backend.models.user import User
    res = await db_session.execute(
        select(User).where(User.email == "ciso@urip.test")
    )
    user = res.scalar_one()

    svc, sub, _risk = await _submit_and_get(db_session, vapt_vendor)
    updated = await svc.request_retest(
        submission_id=sub.id,
        tenant_id=vapt_vendor.tenant_id,
        requested_by_user_id=user.id,
    )
    await db_session.commit()
    assert updated is not None
    assert updated.status == "retest_requested"
    assert updated.retest_requested_at is not None


@pytest.mark.asyncio
async def test_request_retest_wrong_tenant_returns_none(
    db_session, vapt_vendor, second_tenant_vendor
):
    """Admin from wrong tenant cannot trigger re-test on a foreign submission."""
    svc, sub, _risk = await _submit_and_get(db_session, vapt_vendor)
    other_tenant = second_tenant_vendor.tenant_id

    res = await svc.request_retest(
        submission_id=sub.id,
        tenant_id=other_tenant,
        requested_by_user_id=second_tenant_vendor.invited_by_user_id,
    )
    assert res is None


@pytest.mark.asyncio
async def test_vendor_retest_pass_closes_submission_and_risk(
    db_session, vapt_vendor, auth_headers
):
    from backend.models.user import User
    res = await db_session.execute(
        select(User).where(User.email == "ciso@urip.test")
    )
    user = res.scalar_one()

    svc, sub, risk = await _submit_and_get(db_session, vapt_vendor)
    sub = await svc.request_retest(
        submission_id=sub.id,
        tenant_id=vapt_vendor.tenant_id,
        requested_by_user_id=user.id,
    )
    await db_session.commit()

    updated = await svc.vendor_retest_response(
        submission=sub,
        result="pass",
        notes="Verified — fix is in place.",
    )
    await db_session.commit()

    assert updated.status == "closed"
    assert updated.retest_result == "pass"

    # Linked Risk auto-closes
    rrow = await db_session.execute(select(Risk).where(Risk.id == risk.id))
    fresh_risk = rrow.scalar_one()
    assert fresh_risk.status == "closed"


@pytest.mark.asyncio
async def test_vendor_retest_fail_reverts_status(
    db_session, vapt_vendor, auth_headers
):
    from backend.models.user import User
    res = await db_session.execute(
        select(User).where(User.email == "ciso@urip.test")
    )
    user = res.scalar_one()

    svc, sub, risk = await _submit_and_get(db_session, vapt_vendor)
    sub = await svc.request_retest(
        submission_id=sub.id,
        tenant_id=vapt_vendor.tenant_id,
        requested_by_user_id=user.id,
    )
    await db_session.commit()

    updated = await svc.vendor_retest_response(
        submission=sub, result="fail", notes="Still bypassable."
    )
    await db_session.commit()

    assert updated.status == "retest_fail"
    # Risk stays open
    rrow = await db_session.execute(select(Risk).where(Risk.id == risk.id))
    assert rrow.scalar_one().status == "open"


@pytest.mark.asyncio
async def test_retest_response_invalid_state_raises(
    db_session, vapt_vendor
):
    """Cannot retest-respond on a submission that is not in retest_requested."""
    svc, sub, _risk = await _submit_and_get(db_session, vapt_vendor)
    with pytest.raises(ValueError):
        await svc.vendor_retest_response(submission=sub, result="pass")


@pytest.mark.asyncio
async def test_retest_response_invalid_result_raises(
    db_session, vapt_vendor, auth_headers
):
    from backend.models.user import User
    res = await db_session.execute(
        select(User).where(User.email == "ciso@urip.test")
    )
    user = res.scalar_one()

    svc, sub, _risk = await _submit_and_get(db_session, vapt_vendor)
    sub = await svc.request_retest(
        submission_id=sub.id,
        tenant_id=vapt_vendor.tenant_id,
        requested_by_user_id=user.id,
    )
    with pytest.raises(ValueError):
        await svc.vendor_retest_response(submission=sub, result="maybe")
