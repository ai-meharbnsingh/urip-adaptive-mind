"""Invite + accept + revoke flow at the service layer."""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import jwt as pyjwt
import pytest
from sqlalchemy import select

from backend.config import settings
from backend.models.vapt_vendor import VaptVendor, VaptVendorInvitation
from backend.services.vapt_vendor_service import (
    VAPT_JWT_AUDIENCE,
    VAPT_JWT_ISSUER,
    VAPT_JWT_TYPE,
    VaptVendorService,
    hash_invitation_token,
)


@pytest.mark.asyncio
async def test_invite_vendor_creates_vendor_and_invitation(
    db_session, default_tenant, auth_headers
):
    from backend.models.user import User
    res = await db_session.execute(
        select(User).where(User.email == "ciso@urip.test")
    )
    user = res.scalar_one()

    svc = VaptVendorService(db=db_session)
    created = await svc.invite_vendor(
        tenant_id=default_tenant.id,
        name="NewCo",
        contact_email="new@example.com",
        invited_by_user_id=user.id,
    )
    await db_session.commit()

    assert created.vendor.id is not None
    assert created.vendor.tenant_id == default_tenant.id
    assert created.vendor.status == "active"
    assert len(created.raw_token) > 30  # ~256 bits worth

    # Token is stored only as SHA-256
    assert created.invitation.invitation_token_hash == hash_invitation_token(
        created.raw_token
    )
    # Plaintext token is NOT in any persisted field
    assert created.raw_token != created.invitation.invitation_token_hash


@pytest.mark.asyncio
async def test_accept_invitation_returns_jwt(
    db_session, vapt_invitation
):
    raw_token, inv = vapt_invitation
    svc = VaptVendorService(db=db_session)

    result = await svc.accept_invitation(raw_token)
    assert result is not None
    assert result != svc.ALREADY_ACCEPTED
    vendor, jwt_token, expires_at = result

    # JWT decodes with the service's own validation
    claims = svc.decode_vendor_jwt(jwt_token)
    assert claims["type"] == VAPT_JWT_TYPE
    assert claims["vendor_id"] == str(vendor.id)
    assert claims["tenant_id"] == str(vendor.tenant_id)
    assert claims["iss"] == VAPT_JWT_ISSUER
    assert claims["aud"] == VAPT_JWT_AUDIENCE

    # accepted_at is now set
    await db_session.refresh(inv)
    assert inv.accepted_at is not None


@pytest.mark.asyncio
async def test_accept_invitation_invalid_token_returns_none(db_session):
    svc = VaptVendorService(db=db_session)
    result = await svc.accept_invitation("not-a-real-token")
    assert result is None


@pytest.mark.asyncio
async def test_accept_invitation_expired_returns_none(
    db_session, vapt_vendor
):
    """An expired invitation must reject regardless of token validity."""
    raw = "test-raw-token-1234567890"
    inv = VaptVendorInvitation(
        id=uuid.uuid4(),
        vapt_vendor_id=vapt_vendor.id,
        invitation_token_hash=hash_invitation_token(raw),
        # already expired
        expires_at=datetime.now(timezone.utc) - timedelta(seconds=10),
        invited_by_user_id=vapt_vendor.invited_by_user_id,
    )
    db_session.add(inv)
    await db_session.commit()

    svc = VaptVendorService(db=db_session)
    result = await svc.accept_invitation(raw)
    assert result is None


@pytest.mark.asyncio
async def test_accept_invitation_single_use(
    db_session, vapt_invitation
):
    raw_token, _ = vapt_invitation
    svc = VaptVendorService(db=db_session)

    first = await svc.accept_invitation(raw_token)
    assert first is not None
    assert first != svc.ALREADY_ACCEPTED
    await db_session.commit()

    # Second redemption returns the sentinel
    second = await svc.accept_invitation(raw_token)
    assert second == svc.ALREADY_ACCEPTED


@pytest.mark.asyncio
async def test_revoke_vendor_blocks_subsequent_calls(
    db_session, vapt_vendor
):
    svc = VaptVendorService(db=db_session)
    ok = await svc.revoke_vendor(vapt_vendor.id, vapt_vendor.tenant_id)
    assert ok is True
    await db_session.commit()

    # get_active_vendor_by_id should now return None
    refreshed = await svc.get_active_vendor_by_id(vapt_vendor.id)
    assert refreshed is None


@pytest.mark.asyncio
async def test_revoke_vendor_wrong_tenant_returns_false(
    db_session, vapt_vendor
):
    svc = VaptVendorService(db=db_session)
    fake_tenant = uuid.uuid4()
    ok = await svc.revoke_vendor(vapt_vendor.id, fake_tenant)
    assert ok is False


@pytest.mark.asyncio
async def test_jwt_signature_uses_jwt_secret_key(db_session, vapt_vendor):
    """JWT must be HS256-signed with the URIP JWT_SECRET_KEY (not Compliance secret)."""
    svc = VaptVendorService(db=db_session)
    expires = datetime.now(timezone.utc) + timedelta(hours=1)
    token = svc._mint_vendor_jwt(vendor=vapt_vendor, expires_at=expires)

    # Should decode under the URIP secret
    claims = pyjwt.decode(
        token,
        settings.JWT_SECRET_KEY,
        algorithms=["HS256"],
        audience=VAPT_JWT_AUDIENCE,
        issuer=VAPT_JWT_ISSUER,
    )
    assert claims["type"] == VAPT_JWT_TYPE

    # Should fail under a wrong secret
    with pytest.raises(pyjwt.PyJWTError):
        pyjwt.decode(
            token,
            "wrong-secret",
            algorithms=["HS256"],
            audience=VAPT_JWT_AUDIENCE,
            issuer=VAPT_JWT_ISSUER,
        )
