"""
Shared fixtures for the VAPT Vendor Portal test suite.

Re-uses the global tests/conftest.py engine + monkey-patched UUID/JSON types.
Adds:
  - vapt_vendor (active vendor row tied to default_tenant)
  - vapt_invitation (raw token + hashed row)
  - vapt_vendor_jwt (a valid vendor JWT scoped to vapt_vendor)
  - vapt_headers (Authorization headers using the vendor JWT)
"""
from __future__ import annotations

import os
import uuid
from datetime import datetime, timedelta, timezone

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

# tests/conftest.py monkey-patches dialect types BEFORE any model import.
# Importing it first guarantees that order regardless of pytest collection.
import tests.conftest  # noqa: F401  (side-effect: type patches)

from backend.models.vapt_vendor import (
    VaptSubmission,
    VaptVendor,
    VaptVendorInvitation,
)
from backend.services.vapt_vendor_service import (
    VaptVendorService,
    generate_invitation_token,
    hash_invitation_token,
)


# Disable async enrichment background task during tests by default — we don't
# want the test process making real HTTP calls to FIRST.org / CISA. Tests
# that want to verify the enrichment behaviour can monkeypatch it back.
@pytest.fixture(autouse=True)
def _disable_enrich_risk_in_tests(monkeypatch):
    async def _noop(*args, **kwargs):
        return None
    monkeypatch.setattr(
        "backend.services.exploitability_service.enrich_risk", _noop
    )
    monkeypatch.setattr(
        "backend.services.vapt_vendor_service.enrich_risk", _noop
    )
    # Set a dummy fernet key so any code path that tries to encrypt won't blow up
    if not os.environ.get("URIP_FERNET_KEY"):
        from cryptography.fernet import Fernet
        os.environ["URIP_FERNET_KEY"] = Fernet.generate_key().decode()


@pytest_asyncio.fixture
async def vapt_vendor(db_session: AsyncSession, default_tenant, auth_headers, it_team_headers):
    """
    Insert an active VAPT vendor for default_tenant.

    Depends on auth_headers (which inserts the CISO user) so we have a real
    invited_by_user_id; we look it up by email.
    """
    from sqlalchemy import select
    from backend.models.user import User

    res = await db_session.execute(
        select(User).where(User.email == "ciso@urip.test")
    )
    inviter = res.scalar_one()

    vendor = VaptVendor(
        id=uuid.uuid4(),
        tenant_id=default_tenant.id,
        name="Acme Pentesters",
        contact_name="Alice Vendor",
        contact_email="alice@acme-pentesters.test",
        organization="Acme Security Pvt Ltd",
        status="active",
        invited_by_user_id=inviter.id,
        invited_at=datetime.now(timezone.utc),
    )
    db_session.add(vendor)
    await db_session.commit()
    await db_session.refresh(vendor)
    return vendor


@pytest_asyncio.fixture
async def vapt_invitation(db_session: AsyncSession, vapt_vendor):
    """Create an invitation row + return (raw_token, invitation_row)."""
    raw = generate_invitation_token()
    inv = VaptVendorInvitation(
        id=uuid.uuid4(),
        vapt_vendor_id=vapt_vendor.id,
        invitation_token_hash=hash_invitation_token(raw),
        expires_at=datetime.now(timezone.utc) + timedelta(days=14),
        invited_by_user_id=vapt_vendor.invited_by_user_id,
    )
    db_session.add(inv)
    await db_session.commit()
    await db_session.refresh(inv)
    return raw, inv


@pytest_asyncio.fixture
async def vapt_vendor_jwt(db_session: AsyncSession, vapt_vendor):
    """Mint a valid VAPT vendor JWT for vapt_vendor."""
    svc = VaptVendorService(db=db_session)
    expires = datetime.now(timezone.utc) + timedelta(days=14)
    return svc._mint_vendor_jwt(vendor=vapt_vendor, expires_at=expires)


@pytest_asyncio.fixture
async def vapt_headers(vapt_vendor_jwt) -> dict[str, str]:
    return {"Authorization": f"Bearer {vapt_vendor_jwt}"}


@pytest_asyncio.fixture
async def second_tenant_vendor(db_session: AsyncSession):
    """A second tenant with its own vendor — used for cross-tenant isolation tests."""
    from backend.models.tenant import Tenant
    from backend.models.user import User
    from backend.middleware.auth import hash_password

    other_tenant = Tenant(
        id=uuid.uuid4(),
        name="Other Tenant",
        slug="other-tenant",
        domain="other.test",
        is_active=True,
        settings={},
    )
    db_session.add(other_tenant)
    await db_session.flush()

    other_user = User(
        id=uuid.uuid4(),
        email="ciso@other.test",
        hashed_password=hash_password("Pwd#Other1"),
        full_name="Other CISO",
        role="ciso",
        team="Sec",
        is_active=True,
        tenant_id=other_tenant.id,
    )
    db_session.add(other_user)
    await db_session.flush()

    other_vendor = VaptVendor(
        id=uuid.uuid4(),
        tenant_id=other_tenant.id,
        name="Other Pentesters",
        contact_email="bob@other.test",
        status="active",
        invited_by_user_id=other_user.id,
        invited_at=datetime.now(timezone.utc),
    )
    db_session.add(other_vendor)
    await db_session.commit()
    await db_session.refresh(other_vendor)
    return other_vendor
