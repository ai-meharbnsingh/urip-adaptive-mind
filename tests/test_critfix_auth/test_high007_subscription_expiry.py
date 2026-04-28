"""
HIGH-007: TenantSubscription.expires_at must be enforced in module gate.

Vulnerability:
- Module gate only checked `is_enabled=True` and ignored `expires_at`.
- A tenant whose paid subscription expired weeks ago still had access until an
  admin manually flipped is_enabled.

Required behaviour:
- Subscription is "active" iff is_enabled AND (expires_at IS NULL OR expires_at > now()).
- Both require_module and require_any_module must apply this rule.
"""

import uuid
from datetime import datetime, timedelta, timezone

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from backend.middleware.auth import create_access_token, hash_password
from backend.models.subscription import TenantSubscription
from backend.models.tenant import Tenant
from backend.models.user import User


async def _tenant(db: AsyncSession, slug: str) -> Tenant:
    t = Tenant(
        id=uuid.uuid4(),
        name=f"Tenant {slug}",
        slug=slug,
        domain=f"{slug}.example.com",
        is_active=True,
        settings={},
    )
    db.add(t)
    await db.commit()
    await db.refresh(t)
    return t


async def _user(db: AsyncSession, tenant: Tenant) -> User:
    u = User(
        id=uuid.uuid4(),
        email=f"u-{tenant.slug}@{tenant.domain}",
        hashed_password=hash_password("Pa55word#3!"),
        full_name=f"User {tenant.slug}",
        role="ciso",
        is_active=True,
        is_super_admin=False,
        tenant_id=tenant.id,
    )
    db.add(u)
    await db.commit()
    await db.refresh(u)
    return u


def _hdr(user: User, tenant: Tenant) -> dict:
    token = create_access_token(str(user.id), user.role, tenant_id=str(tenant.id))
    return {"Authorization": f"Bearer {token}"}


@pytest_asyncio.fixture
async def expired_vm_tenant(db_session: AsyncSession) -> Tenant:
    t = await _tenant(db_session, "expired-vm")
    db_session.add(TenantSubscription(
        id=uuid.uuid4(),
        tenant_id=t.id,
        module_code="VM",
        is_enabled=True,
        billing_tier="STANDARD",
        expires_at=datetime.now(timezone.utc) - timedelta(days=10),  # expired 10 days ago
    ))
    db_session.add(TenantSubscription(
        id=uuid.uuid4(),
        tenant_id=t.id,
        module_code="CORE",
        is_enabled=True,
        billing_tier="STANDARD",
        expires_at=None,  # CORE is fine
    ))
    await db_session.commit()
    return t


@pytest_asyncio.fixture
async def expired_vm_user(db_session: AsyncSession, expired_vm_tenant: Tenant) -> User:
    return await _user(db_session, expired_vm_tenant)


@pytest_asyncio.fixture
async def expired_vm_headers(expired_vm_user: User, expired_vm_tenant: Tenant) -> dict:
    return _hdr(expired_vm_user, expired_vm_tenant)


@pytest_asyncio.fixture
async def future_vm_tenant(db_session: AsyncSession) -> Tenant:
    t = await _tenant(db_session, "future-vm")
    db_session.add(TenantSubscription(
        id=uuid.uuid4(),
        tenant_id=t.id,
        module_code="VM",
        is_enabled=True,
        billing_tier="STANDARD",
        expires_at=datetime.now(timezone.utc) + timedelta(days=30),  # expires in 30 days
    ))
    await db_session.commit()
    return t


@pytest_asyncio.fixture
async def future_vm_user(db_session: AsyncSession, future_vm_tenant: Tenant) -> User:
    return await _user(db_session, future_vm_tenant)


@pytest_asyncio.fixture
async def future_vm_headers(future_vm_user: User, future_vm_tenant: Tenant) -> dict:
    return _hdr(future_vm_user, future_vm_tenant)


@pytest.mark.asyncio
async def test_expired_subscription_blocks_module_gate(
    client: AsyncClient,
    expired_vm_headers: dict,
):
    """A tenant whose VM subscription expired in the past must be blocked (403)."""
    resp = await client.get("/api/risks", headers=expired_vm_headers)
    assert resp.status_code == 403, f"expected 403, got {resp.status_code}: {resp.text}"


@pytest.mark.asyncio
async def test_future_expiry_subscription_allows_access(
    client: AsyncClient,
    future_vm_headers: dict,
):
    """A subscription with expires_at in the future is still valid."""
    resp = await client.get("/api/risks", headers=future_vm_headers)
    assert resp.status_code != 403, (
        f"future-expiry subscription should not 403: {resp.status_code} {resp.text[:200]}"
    )


@pytest.mark.asyncio
async def test_null_expiry_subscription_allows_access(
    client: AsyncClient,
    db_session: AsyncSession,
):
    """A subscription with expires_at = NULL (perpetual) is always valid."""
    t = await _tenant(db_session, "perpetual-vm")
    db_session.add(TenantSubscription(
        id=uuid.uuid4(),
        tenant_id=t.id,
        module_code="VM",
        is_enabled=True,
        billing_tier="PREMIUM",
        expires_at=None,
    ))
    await db_session.commit()
    user = await _user(db_session, t)
    resp = await client.get("/api/risks", headers=_hdr(user, t))
    assert resp.status_code != 403, resp.text


@pytest.mark.asyncio
async def test_expired_subscription_blocks_any_module_helper(
    client: AsyncClient,
    db_session: AsyncSession,
):
    """require_any_module must also honour expires_at."""
    t = await _tenant(db_session, "expired-edr")
    # Only EDR (one of the threat-intel set), and it expired
    db_session.add(TenantSubscription(
        id=uuid.uuid4(),
        tenant_id=t.id,
        module_code="EDR",
        is_enabled=True,
        billing_tier="STANDARD",
        expires_at=datetime.now(timezone.utc) - timedelta(days=1),
    ))
    await db_session.commit()
    user = await _user(db_session, t)
    resp = await client.get("/api/threat-intel/pulses", headers=_hdr(user, t))
    assert resp.status_code == 403, (
        f"expired EDR should block require_any_module: {resp.status_code} {resp.text[:200]}"
    )
