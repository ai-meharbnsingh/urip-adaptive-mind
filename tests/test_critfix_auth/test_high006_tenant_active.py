"""
HIGH-006: tenant.is_active must be enforced in get_current_user.

Vulnerability:
- Tenant model has is_active flag, but get_current_user never read it.
- A deactivated tenant's users could keep calling the API until their JWT
  expired (default 8h).

Required behaviour:
- After loading the user, also load tenant; if tenant.is_active is False →
  403 with detail "Tenant suspended".
- Super-admin bypass still works (super-admin has tenant_id=None).
"""

import uuid

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from backend.middleware.auth import create_access_token, hash_password
from backend.models.subscription import TenantSubscription
from backend.models.tenant import Tenant
from backend.models.user import User


@pytest_asyncio.fixture
async def suspended_tenant(db_session: AsyncSession) -> Tenant:
    """An active tenant we then deactivate."""
    t = Tenant(
        id=uuid.uuid4(),
        name="To Be Suspended",
        slug="suspended-co",
        domain="suspended.example.com",
        is_active=True,  # starts active
        settings={},
    )
    db_session.add(t)
    # Give the tenant CORE so it would otherwise reach a CORE endpoint
    db_session.add(TenantSubscription(
        id=uuid.uuid4(),
        tenant_id=t.id,
        module_code="CORE",
        is_enabled=True,
        billing_tier="STANDARD",
    ))
    await db_session.commit()
    await db_session.refresh(t)
    return t


@pytest_asyncio.fixture
async def suspended_user(db_session: AsyncSession, suspended_tenant: Tenant) -> User:
    u = User(
        id=uuid.uuid4(),
        email="user@suspended.example.com",
        hashed_password=hash_password("Pa55word#1!"),
        full_name="Suspended User",
        role="ciso",
        is_active=True,
        is_super_admin=False,
        tenant_id=suspended_tenant.id,
    )
    db_session.add(u)
    await db_session.commit()
    await db_session.refresh(u)
    return u


@pytest_asyncio.fixture
async def suspended_headers(suspended_user: User, suspended_tenant: Tenant) -> dict:
    token = create_access_token(
        str(suspended_user.id),
        suspended_user.role,
        tenant_id=str(suspended_tenant.id),
    )
    return {"Authorization": f"Bearer {token}"}


@pytest_asyncio.fixture
async def super_admin_user(db_session: AsyncSession) -> User:
    u = User(
        id=uuid.uuid4(),
        email="super@platform.io",
        hashed_password=hash_password("Pa55word#2!"),
        full_name="Platform SA",
        role="ciso",
        is_active=True,
        is_super_admin=True,
        tenant_id=None,
    )
    db_session.add(u)
    await db_session.commit()
    await db_session.refresh(u)
    return u


@pytest_asyncio.fixture
async def super_admin_headers(super_admin_user: User) -> dict:
    token = create_access_token(
        str(super_admin_user.id),
        super_admin_user.role,
        tenant_id=None,
        is_super_admin=True,
    )
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_active_tenant_user_can_access(
    client: AsyncClient,
    suspended_headers: dict,
):
    """Sanity: while tenant is active, the user can hit a CORE endpoint."""
    resp = await client.get("/api/dashboard/kpis", headers=suspended_headers)
    assert resp.status_code != 403, resp.text
    # Could be 200 or 422 depending on data; not 403


@pytest.mark.asyncio
async def test_deactivated_tenant_user_gets_403(
    client: AsyncClient,
    db_session: AsyncSession,
    suspended_tenant: Tenant,
    suspended_headers: dict,
):
    """After deactivating the tenant, the same user request → 403 'Tenant suspended'."""
    # Reload + flip is_active=False
    suspended_tenant.is_active = False
    db_session.add(suspended_tenant)
    await db_session.commit()

    resp = await client.get("/api/dashboard/kpis", headers=suspended_headers)
    assert resp.status_code == 403, f"expected 403, got {resp.status_code}: {resp.text}"
    assert "tenant suspended" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_deactivated_tenant_blocks_all_endpoints(
    client: AsyncClient,
    db_session: AsyncSession,
    suspended_tenant: Tenant,
    suspended_headers: dict,
):
    """Deactivated tenant users are blocked on every endpoint that calls get_current_user."""
    suspended_tenant.is_active = False
    db_session.add(suspended_tenant)
    await db_session.commit()

    paths = [
        "/api/auth/me",
        "/api/dashboard/kpis",
        "/api/audit-log",
        "/api/settings/users",
        "/api/reports/scheduled",
    ]
    for path in paths:
        resp = await client.get(path, headers=suspended_headers)
        assert resp.status_code == 403, (
            f"{path} should be 403 for deactivated-tenant user; got {resp.status_code}: {resp.text[:200]}"
        )


@pytest.mark.asyncio
async def test_super_admin_unaffected_by_tenant_suspension(
    client: AsyncClient,
    db_session: AsyncSession,
    suspended_tenant: Tenant,
    super_admin_headers: dict,
):
    """Super-admin is not bound to any tenant → tenant suspension does not affect them."""
    suspended_tenant.is_active = False
    db_session.add(suspended_tenant)
    await db_session.commit()

    resp = await client.get("/api/auth/me", headers=super_admin_headers)
    assert resp.status_code == 200, f"super-admin blocked: {resp.text}"
