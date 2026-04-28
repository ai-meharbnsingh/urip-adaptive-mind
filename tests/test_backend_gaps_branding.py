"""
GAP 3 — Public branding endpoint.
GAP 5 — secondary_color in TenantUpdate.
"""
import uuid

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from backend.middleware.auth import create_access_token, hash_password
from backend.models.tenant import Tenant
from backend.models.user import User


# ---------------------------------------------------------------------------
# Fixtures: two tenants + one user in tenant A + one super-admin
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def tenant_a(db_session: AsyncSession) -> Tenant:
    t = Tenant(
        id=uuid.uuid4(),
        name="Acme Corp",
        slug="acme",
        domain="acme.test",
        is_active=True,
        settings={
            "app_name": "Acme RiskPanel",
            "logo_url": "https://cdn.acme.test/logo.png",
            "primary_color": "#112233",
            "secondary_color": "#445566",
        },
    )
    db_session.add(t)
    await db_session.commit()
    await db_session.refresh(t)
    return t


@pytest_asyncio.fixture
async def tenant_b(db_session: AsyncSession) -> Tenant:
    t = Tenant(
        id=uuid.uuid4(),
        name="Beta Industries",
        slug="beta",
        domain="beta.test",
        is_active=True,
        settings={"app_name": "Beta RiskPanel"},
    )
    db_session.add(t)
    await db_session.commit()
    await db_session.refresh(t)
    return t


@pytest_asyncio.fixture
async def user_in_tenant_a_headers(db_session: AsyncSession, tenant_a: Tenant) -> dict:
    user = User(
        id=uuid.uuid4(),
        email="alice@acme.test",
        hashed_password=hash_password("Pass#Acme1"),
        full_name="Alice",
        role="ciso",
        is_active=True,
        is_super_admin=False,
        tenant_id=tenant_a.id,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    token = create_access_token(str(user.id), user.role, tenant_id=str(tenant_a.id))
    return {"Authorization": f"Bearer {token}"}


@pytest_asyncio.fixture
async def super_admin_headers_branding(db_session: AsyncSession) -> dict:
    user = User(
        id=uuid.uuid4(),
        email="super@platform.test",
        hashed_password=hash_password("Super#1"),
        full_name="Super",
        role="ciso",
        is_active=True,
        is_super_admin=True,
        tenant_id=None,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    token = create_access_token(
        str(user.id), user.role, tenant_id=None, is_super_admin=True
    )
    return {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------------------
# GAP 3 — GET /api/tenants/{slug}/branding
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_branding_own_tenant_returns_200(
    client: AsyncClient, tenant_a: Tenant, user_in_tenant_a_headers: dict
):
    """Tenant user reads own tenant's branding → 200 + all 4 fields."""
    resp = await client.get(
        f"/api/tenants/{tenant_a.slug}/branding", headers=user_in_tenant_a_headers
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["app_name"] == "Acme RiskPanel"
    assert body["logo_url"] == "https://cdn.acme.test/logo.png"
    assert body["primary_color"] == "#112233"
    assert body["secondary_color"] == "#445566"


@pytest.mark.asyncio
async def test_branding_other_tenant_returns_404(
    client: AsyncClient,
    tenant_a: Tenant,
    tenant_b: Tenant,
    user_in_tenant_a_headers: dict,
):
    """Tenant user reads OTHER tenant's branding → 404 (no info leak)."""
    resp = await client.get(
        f"/api/tenants/{tenant_b.slug}/branding", headers=user_in_tenant_a_headers
    )
    assert resp.status_code == 404, resp.text


@pytest.mark.asyncio
async def test_branding_unknown_tenant_returns_404(
    client: AsyncClient, user_in_tenant_a_headers: dict
):
    resp = await client.get(
        "/api/tenants/nonexistent-tenant/branding",
        headers=user_in_tenant_a_headers,
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_branding_super_admin_can_read_any(
    client: AsyncClient,
    tenant_a: Tenant,
    tenant_b: Tenant,
    super_admin_headers_branding: dict,
):
    """Super-admin reads any tenant's branding → 200."""
    for slug in (tenant_a.slug, tenant_b.slug):
        resp = await client.get(
            f"/api/tenants/{slug}/branding", headers=super_admin_headers_branding
        )
        assert resp.status_code == 200, f"slug={slug}: {resp.text}"
        body = resp.json()
        # Required fields always present (may be null)
        assert "app_name" in body
        assert "logo_url" in body
        assert "primary_color" in body
        assert "secondary_color" in body


@pytest.mark.asyncio
async def test_branding_unauthenticated_returns_403_or_401(
    client: AsyncClient, tenant_a: Tenant
):
    """No token → 403 (HTTPBearer behaviour) or 401."""
    resp = await client.get(f"/api/tenants/{tenant_a.slug}/branding")
    assert resp.status_code in (401, 403)


# ---------------------------------------------------------------------------
# GAP 5 — TenantUpdate must accept secondary_color (super-admin PATCH)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_patch_tenant_with_secondary_color_persists(
    client: AsyncClient,
    tenant_a: Tenant,
    super_admin_headers_branding: dict,
):
    resp = await client.patch(
        f"/api/admin/tenants/{tenant_a.slug}",
        json={"secondary_color": "#ABCDEF"},
        headers=super_admin_headers_branding,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["settings"]["secondary_color"] == "#ABCDEF"


@pytest.mark.asyncio
async def test_patch_tenant_secondary_color_invalid_hex_rejected(
    client: AsyncClient,
    tenant_a: Tenant,
    super_admin_headers_branding: dict,
):
    """Invalid hex format → 422."""
    resp = await client.patch(
        f"/api/admin/tenants/{tenant_a.slug}",
        json={"secondary_color": "notacolor"},
        headers=super_admin_headers_branding,
    )
    assert resp.status_code == 422, resp.text
