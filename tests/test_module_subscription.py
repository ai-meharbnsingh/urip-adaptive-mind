"""
P1.3 — Module subscription registry tests.

Covers:
- POST /api/admin/tenants/{slug}/modules — enable module (happy path)
- POST /api/admin/tenants/{slug}/modules — duplicate module returns 409
- PATCH /api/admin/tenants/{slug}/modules/{code} — change tier / expires_at
- DELETE /api/admin/tenants/{slug}/modules/{code} — soft-disable (is_enabled=false)
- GET  /api/tenants/{slug}/modules — tenant admin sees own modules; 404 for cross-tenant
- Re-enabling a soft-disabled module via POST
- Invalid module_code / billing_tier validation (422)
"""

import uuid
from datetime import datetime, timezone, timedelta

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from backend.middleware.auth import create_access_token, hash_password
from backend.models.tenant import Tenant
from backend.models.user import User
from backend.models.subscription import TenantSubscription


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def super_admin_user(db_session: AsyncSession) -> User:
    user = User(
        id=uuid.uuid4(),
        email="superadmin@platform.io",
        hashed_password=hash_password("Admin#Pass1"),
        full_name="Platform SA",
        role="ciso",
        is_active=True,
        is_super_admin=True,
        tenant_id=None,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture
async def super_admin_headers(super_admin_user: User) -> dict:
    token = create_access_token(
        str(super_admin_user.id),
        super_admin_user.role,
        tenant_id=None,
        is_super_admin=True,
    )
    return {"Authorization": f"Bearer {token}"}


@pytest_asyncio.fixture
async def second_tenant(db_session: AsyncSession) -> Tenant:
    """A second tenant to test cross-tenant isolation."""
    t = Tenant(
        id=uuid.uuid4(),
        name="Beta Corp",
        slug="beta-corp",
        domain="beta.com",
        is_active=True,
        settings={},
    )
    db_session.add(t)
    await db_session.commit()
    await db_session.refresh(t)
    return t


# ---------------------------------------------------------------------------
# POST /api/admin/tenants/{slug}/modules — enable module
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_enable_module_happy_path(
    client: AsyncClient, super_admin_headers: dict, default_tenant: Tenant
):
    """Super-admin can enable the EDR module for a tenant."""
    resp = await client.post(
        f"/api/admin/tenants/{default_tenant.slug}/modules",
        json={"module_code": "EDR", "billing_tier": "TRIAL"},
        headers=super_admin_headers,
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["module_code"] == "EDR"
    assert body["is_enabled"] is True
    assert body["billing_tier"] == "TRIAL"
    assert "started_at" in body
    assert body["expires_at"] is None


@pytest.mark.asyncio
async def test_enable_module_all_valid_codes(
    client: AsyncClient, super_admin_headers: dict, default_tenant: Tenant
):
    """All 10 module codes are accepted."""
    codes = ["CORE", "VM", "EDR", "NETWORK", "IDENTITY", "COLLAB", "ITSM", "DAST", "DLP", "COMPLIANCE"]
    for code in codes:
        resp = await client.post(
            f"/api/admin/tenants/{default_tenant.slug}/modules",
            json={"module_code": code, "billing_tier": "STANDARD"},
            headers=super_admin_headers,
        )
        assert resp.status_code == 201, f"Failed for module {code}: {resp.text}"


@pytest.mark.asyncio
async def test_enable_module_with_expiry(
    client: AsyncClient, super_admin_headers: dict, default_tenant: Tenant
):
    """Trial module can have an expiry date."""
    expires = (datetime.now(timezone.utc) + timedelta(days=30)).isoformat()
    resp = await client.post(
        f"/api/admin/tenants/{default_tenant.slug}/modules",
        json={"module_code": "DLP", "billing_tier": "TRIAL", "expires_at": expires},
        headers=super_admin_headers,
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["expires_at"] is not None


@pytest.mark.asyncio
async def test_enable_module_duplicate_returns_409(
    client: AsyncClient, super_admin_headers: dict, default_tenant: Tenant
):
    """Enabling an already-enabled module returns 409."""
    payload = {"module_code": "ITSM", "billing_tier": "STANDARD"}

    resp1 = await client.post(
        f"/api/admin/tenants/{default_tenant.slug}/modules", json=payload, headers=super_admin_headers
    )
    assert resp1.status_code == 201

    resp2 = await client.post(
        f"/api/admin/tenants/{default_tenant.slug}/modules", json=payload, headers=super_admin_headers
    )
    assert resp2.status_code == 409
    assert "already enabled" in resp2.json()["detail"]


@pytest.mark.asyncio
async def test_enable_module_invalid_code(
    client: AsyncClient, super_admin_headers: dict, default_tenant: Tenant
):
    """Unknown module_code returns 422."""
    resp = await client.post(
        f"/api/admin/tenants/{default_tenant.slug}/modules",
        json={"module_code": "UNKNOWN_MODULE"},
        headers=super_admin_headers,
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_enable_module_invalid_tier(
    client: AsyncClient, super_admin_headers: dict, default_tenant: Tenant
):
    """Invalid billing_tier returns 422."""
    resp = await client.post(
        f"/api/admin/tenants/{default_tenant.slug}/modules",
        json={"module_code": "VM", "billing_tier": "FREEMIUM"},
        headers=super_admin_headers,
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_enable_module_requires_super_admin(
    client: AsyncClient, auth_headers: dict, default_tenant: Tenant
):
    """Normal users cannot enable modules."""
    resp = await client.post(
        f"/api/admin/tenants/{default_tenant.slug}/modules",
        json={"module_code": "VM"},
        headers=auth_headers,
    )
    assert resp.status_code == 403


# ---------------------------------------------------------------------------
# PATCH /api/admin/tenants/{slug}/modules/{code} — update subscription
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_update_module_tier(
    client: AsyncClient, super_admin_headers: dict, default_tenant: Tenant
):
    """Super-admin can upgrade a module from TRIAL to PREMIUM."""
    # Enable first
    await client.post(
        f"/api/admin/tenants/{default_tenant.slug}/modules",
        json={"module_code": "NETWORK", "billing_tier": "TRIAL"},
        headers=super_admin_headers,
    )

    resp = await client.patch(
        f"/api/admin/tenants/{default_tenant.slug}/modules/NETWORK",
        json={"billing_tier": "PREMIUM"},
        headers=super_admin_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["billing_tier"] == "PREMIUM"


@pytest.mark.asyncio
async def test_update_module_expires_at(
    client: AsyncClient, super_admin_headers: dict, default_tenant: Tenant
):
    """Super-admin can extend the expiry date of a subscription."""
    await client.post(
        f"/api/admin/tenants/{default_tenant.slug}/modules",
        json={"module_code": "IDENTITY", "billing_tier": "TRIAL"},
        headers=super_admin_headers,
    )

    new_expires = (datetime.now(timezone.utc) + timedelta(days=90)).isoformat()
    resp = await client.patch(
        f"/api/admin/tenants/{default_tenant.slug}/modules/IDENTITY",
        json={"expires_at": new_expires},
        headers=super_admin_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["expires_at"] is not None


@pytest.mark.asyncio
async def test_update_module_not_found(
    client: AsyncClient, super_admin_headers: dict, default_tenant: Tenant
):
    """Updating a non-existent subscription returns 404."""
    resp = await client.patch(
        f"/api/admin/tenants/{default_tenant.slug}/modules/DAST",
        json={"billing_tier": "PREMIUM"},
        headers=super_admin_headers,
    )
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# DELETE /api/admin/tenants/{slug}/modules/{code} — soft-disable
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_disable_module_soft_delete(
    client: AsyncClient, super_admin_headers: dict, default_tenant: Tenant
):
    """Disabling a module sets is_enabled=False but does NOT delete the row."""
    await client.post(
        f"/api/admin/tenants/{default_tenant.slug}/modules",
        json={"module_code": "COMPLIANCE", "billing_tier": "PREMIUM"},
        headers=super_admin_headers,
    )

    resp = await client.delete(
        f"/api/admin/tenants/{default_tenant.slug}/modules/COMPLIANCE",
        headers=super_admin_headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["subscription"]["is_enabled"] is False
    assert body["subscription"]["module_code"] == "COMPLIANCE"


@pytest.mark.asyncio
async def test_disable_module_already_disabled(
    client: AsyncClient, super_admin_headers: dict, default_tenant: Tenant
):
    """Disabling an already-disabled module returns 409."""
    await client.post(
        f"/api/admin/tenants/{default_tenant.slug}/modules",
        json={"module_code": "COLLAB"},
        headers=super_admin_headers,
    )
    await client.delete(
        f"/api/admin/tenants/{default_tenant.slug}/modules/COLLAB",
        headers=super_admin_headers,
    )
    resp = await client.delete(
        f"/api/admin/tenants/{default_tenant.slug}/modules/COLLAB",
        headers=super_admin_headers,
    )
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_reenable_disabled_module(
    client: AsyncClient, super_admin_headers: dict, default_tenant: Tenant
):
    """A soft-disabled module can be re-enabled via POST."""
    await client.post(
        f"/api/admin/tenants/{default_tenant.slug}/modules",
        json={"module_code": "DAST", "billing_tier": "TRIAL"},
        headers=super_admin_headers,
    )
    await client.delete(
        f"/api/admin/tenants/{default_tenant.slug}/modules/DAST",
        headers=super_admin_headers,
    )

    # Re-enable
    resp = await client.post(
        f"/api/admin/tenants/{default_tenant.slug}/modules",
        json={"module_code": "DAST", "billing_tier": "STANDARD"},
        headers=super_admin_headers,
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["is_enabled"] is True
    assert body["billing_tier"] == "STANDARD"


# ---------------------------------------------------------------------------
# GET /api/tenants/{slug}/modules
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_modules_tenant_admin(
    client: AsyncClient,
    super_admin_headers: dict,
    auth_headers: dict,
    default_tenant: Tenant,
):
    """Tenant admin can list their own tenant's modules."""
    # Enable some modules first
    for code in ["VM", "EDR"]:
        await client.post(
            f"/api/admin/tenants/{default_tenant.slug}/modules",
            json={"module_code": code, "billing_tier": "STANDARD"},
            headers=super_admin_headers,
        )

    resp = await client.get(
        f"/api/tenants/{default_tenant.slug}/modules",
        headers=auth_headers,  # normal ciso user of default_tenant
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert isinstance(body, list)
    codes = [m["module_code"] for m in body]
    assert "VM" in codes
    assert "EDR" in codes


@pytest.mark.asyncio
async def test_list_modules_cross_tenant_forbidden(
    client: AsyncClient,
    auth_headers: dict,
    second_tenant: Tenant,
):
    """A normal user cannot view another tenant's modules.

    Returns 404 (was 403) — see backend/ENDPOINT_AUDIT.md criterion #5.
    Cross-tenant access must NOT leak the existence of other tenant slugs.
    """
    resp = await client.get(
        f"/api/tenants/{second_tenant.slug}/modules",
        headers=auth_headers,
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_list_modules_super_admin_sees_any(
    client: AsyncClient,
    super_admin_headers: dict,
    second_tenant: Tenant,
):
    """Super-admin can list modules for any tenant."""
    resp = await client.get(
        f"/api/tenants/{second_tenant.slug}/modules",
        headers=super_admin_headers,
    )
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)