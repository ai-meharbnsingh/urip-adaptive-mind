"""
P1.2 — Tenant onboarding API tests.

Covers:
- POST /api/admin/tenants — create tenant (happy path)
- POST /api/admin/tenants — slug uniqueness enforcement (409)
- POST /api/admin/tenants — non-super-admin receives 403
- GET  /api/admin/tenants — list tenants (super-admin only)
- GET  /api/admin/tenants/{slug} — tenant detail
- PATCH /api/admin/tenants/{slug} — update white-label settings
- POST /api/admin/tenants/{slug}/users — provision tenant admin user
"""

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from backend.middleware.auth import create_access_token, hash_password
from backend.models.tenant import Tenant
from backend.models.user import User


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def super_admin_headers(db_session: AsyncSession) -> dict:
    """This is intentionally NOT async — we schedule the user creation in the
    session via pytest_asyncio, but we create the headers synchronously using
    a pre-computed UUID so the token can be built without awaiting DB I/O.

    Actually we DO need async for DB. Use pytest_asyncio.
    """
    ...


# We use pytest_asyncio for async fixtures within this file.
import pytest_asyncio


@pytest_asyncio.fixture
async def super_admin_user(db_session: AsyncSession, default_tenant: Tenant) -> User:
    """Create a super_admin user for test calls."""
    user = User(
        id=uuid.uuid4(),
        email="superadmin@urip.platform",
        hashed_password=hash_password("SuperSecret#1"),
        full_name="Platform Admin",
        role="ciso",
        is_active=True,
        is_super_admin=True,
        tenant_id=None,  # super-admin has no tenant
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


# ---------------------------------------------------------------------------
# Tests — POST /api/admin/tenants
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_tenant_happy_path(client: AsyncClient, super_admin_headers: dict):
    """Super-admin can create a new tenant."""
    resp = await client.post(
        "/api/admin/tenants",
        json={
            "name": "Acme Corp",
            "slug": "acme",
            "domain": "acme.com",
            "primary_contact_email": "cto@acme.com",
        },
        headers=super_admin_headers,
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["slug"] == "acme"
    assert body["name"] == "Acme Corp"
    assert body["domain"] == "acme.com"
    assert body["is_active"] is True
    assert body["settings"]["primary_contact_email"] == "cto@acme.com"
    assert "id" in body
    assert "created_at" in body


@pytest.mark.asyncio
async def test_create_tenant_slug_uniqueness(client: AsyncClient, super_admin_headers: dict):
    """Creating a second tenant with the same slug returns 409."""
    payload = {"name": "Foo Inc", "slug": "foo-inc", "domain": "foo.com"}

    resp1 = await client.post("/api/admin/tenants", json=payload, headers=super_admin_headers)
    assert resp1.status_code == 201

    resp2 = await client.post("/api/admin/tenants", json=payload, headers=super_admin_headers)
    assert resp2.status_code == 409
    assert "already exists" in resp2.json()["detail"]


@pytest.mark.asyncio
async def test_create_tenant_requires_super_admin(client: AsyncClient, auth_headers: dict):
    """A normal (non-super-admin) user receives 403."""
    resp = await client.post(
        "/api/admin/tenants",
        json={"name": "Should Fail", "slug": "should-fail", "domain": "fail.com"},
        headers=auth_headers,
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_create_tenant_invalid_slug(client: AsyncClient, super_admin_headers: dict):
    """Slug with uppercase or spaces is rejected by Pydantic validation (422)."""
    resp = await client.post(
        "/api/admin/tenants",
        json={"name": "Bad Slug", "slug": "Bad Slug!", "domain": "bad.com"},
        headers=super_admin_headers,
    )
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# Tests — GET /api/admin/tenants
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_tenants(client: AsyncClient, super_admin_headers: dict, default_tenant: Tenant):
    """Super-admin can list all tenants. The default_tenant is present."""
    resp = await client.get("/api/admin/tenants", headers=super_admin_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert isinstance(body, list)
    slugs = [t["slug"] for t in body]
    assert default_tenant.slug in slugs


@pytest.mark.asyncio
async def test_list_tenants_requires_super_admin(client: AsyncClient, auth_headers: dict):
    """Non-super-admin cannot list tenants."""
    resp = await client.get("/api/admin/tenants", headers=auth_headers)
    assert resp.status_code == 403


# ---------------------------------------------------------------------------
# Tests — GET /api/admin/tenants/{slug}
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_tenant_detail(client: AsyncClient, super_admin_headers: dict, default_tenant: Tenant):
    """Super-admin can retrieve tenant detail by slug."""
    resp = await client.get(f"/api/admin/tenants/{default_tenant.slug}", headers=super_admin_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["slug"] == default_tenant.slug
    assert body["name"] == default_tenant.name


@pytest.mark.asyncio
async def test_get_tenant_not_found(client: AsyncClient, super_admin_headers: dict):
    """Non-existent slug returns 404."""
    resp = await client.get("/api/admin/tenants/does-not-exist", headers=super_admin_headers)
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Tests — PATCH /api/admin/tenants/{slug}
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_update_tenant_white_label(client: AsyncClient, super_admin_headers: dict, default_tenant: Tenant):
    """Super-admin can update white-label settings."""
    resp = await client.patch(
        f"/api/admin/tenants/{default_tenant.slug}",
        json={
            "logo_url": "https://cdn.acme.com/logo.png",
            "primary_color": "#FF5733",
            "app_name": "Acme Security Hub",
        },
        headers=super_admin_headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["settings"]["logo_url"] == "https://cdn.acme.com/logo.png"
    assert body["settings"]["primary_color"] == "#FF5733"
    assert body["settings"]["app_name"] == "Acme Security Hub"


@pytest.mark.asyncio
async def test_deactivate_tenant(client: AsyncClient, super_admin_headers: dict, default_tenant: Tenant):
    """Super-admin can deactivate a tenant."""
    resp = await client.patch(
        f"/api/admin/tenants/{default_tenant.slug}",
        json={"is_active": False},
        headers=super_admin_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["is_active"] is False


# ---------------------------------------------------------------------------
# Tests — POST /api/admin/tenants/{slug}/users
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_provision_tenant_admin_user(client: AsyncClient, super_admin_headers: dict, default_tenant: Tenant):
    """Super-admin can bootstrap a tenant admin user; receives a token."""
    resp = await client.post(
        f"/api/admin/tenants/{default_tenant.slug}/users",
        json={
            "email": "newadmin@urip.test",
            "full_name": "New Admin",
            "password": "Secure#Pass123",
            "role": "ciso",
        },
        headers=super_admin_headers,
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["email"] == "newadmin@urip.test"
    assert body["role"] == "ciso"
    assert body["tenant_slug"] == default_tenant.slug
    assert "access_token" in body
    assert body["token_type"] == "Bearer"


@pytest.mark.asyncio
async def test_provision_tenant_admin_user_duplicate_email(
    client: AsyncClient, super_admin_headers: dict, default_tenant: Tenant
):
    """Provisioning a user with a duplicate email returns 409."""
    payload = {
        "email": "duplicate@urip.test",
        "full_name": "First User",
        "password": "Secure#Pass123",
    }
    resp1 = await client.post(
        f"/api/admin/tenants/{default_tenant.slug}/users", json=payload, headers=super_admin_headers
    )
    assert resp1.status_code == 201

    resp2 = await client.post(
        f"/api/admin/tenants/{default_tenant.slug}/users", json=payload, headers=super_admin_headers
    )
    assert resp2.status_code == 409


@pytest.mark.asyncio
async def test_provision_tenant_user_invalid_role(
    client: AsyncClient, super_admin_headers: dict, default_tenant: Tenant
):
    """Provisioning with an invalid role returns 422."""
    resp = await client.post(
        f"/api/admin/tenants/{default_tenant.slug}/users",
        json={
            "email": "badrole@urip.test",
            "full_name": "Bad Role User",
            "password": "Secure#Pass123",
            "role": "superstar",
        },
        headers=super_admin_headers,
    )
    assert resp.status_code == 422