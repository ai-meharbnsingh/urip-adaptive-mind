"""
Backend Gaps Fixer — TDD tests for GAP 1 + GAP 2.

GAP 1: `is_super_admin` not propagated to JWT on login.
GAP 2: `tenant_slug` missing from /auth/me response (UserProfile schema).
"""
import uuid

import pytest
import pytest_asyncio
from httpx import AsyncClient
import jwt
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import settings
from backend.middleware.auth import hash_password
from backend.models.tenant import Tenant
from backend.models.user import User


@pytest_asyncio.fixture
async def super_admin_in_db(db_session: AsyncSession) -> User:
    """Create a super-admin user (no tenant) directly in the DB."""
    user = User(
        id=uuid.uuid4(),
        email="superadmin@platform.test",
        hashed_password=hash_password("Super#Pass1"),
        full_name="Platform Super Admin",
        role="ciso",
        is_active=True,
        is_super_admin=True,
        tenant_id=None,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


# ---------------------------------------------------------------------------
# GAP 1 — login must propagate is_super_admin to the JWT
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_login_super_admin_jwt_contains_is_super_admin_true(
    client: AsyncClient, super_admin_in_db: User
):
    """Super-admin login → decoded JWT has is_super_admin == True."""
    resp = await client.post(
        "/api/auth/login",
        json={"email": "superadmin@platform.test", "password": "Super#Pass1"},
    )
    assert resp.status_code == 200, resp.text
    token = resp.json()["access_token"]
    payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
    assert payload.get("is_super_admin") is True, (
        f"Expected is_super_admin=True in JWT for super-admin, got: {payload}"
    )


@pytest.mark.asyncio
async def test_login_regular_user_jwt_super_admin_false(
    client: AsyncClient, auth_headers: dict
):
    """Regular CISO user login → decoded JWT has is_super_admin == False."""
    resp = await client.post(
        "/api/auth/login",
        json={"email": "ciso@urip.test", "password": "Secure#Pass1"},
    )
    assert resp.status_code == 200
    token = resp.json()["access_token"]
    payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
    # Either explicitly False or absent (treated as False) — but the field MUST be present
    assert payload.get("is_super_admin", False) is False


# ---------------------------------------------------------------------------
# GAP 2 — UserProfile must include tenant_slug
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_me_includes_tenant_slug_for_regular_user(
    client: AsyncClient, auth_headers: dict, default_tenant: Tenant
):
    """GET /api/auth/me returns tenant_slug populated for regular tenant user."""
    resp = await client.get("/api/auth/me", headers=auth_headers)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert "tenant_slug" in body, f"tenant_slug missing from /me response: {body}"
    assert body["tenant_slug"] == default_tenant.slug


@pytest.mark.asyncio
async def test_me_tenant_slug_null_for_super_admin(
    client: AsyncClient, super_admin_in_db: User
):
    """GET /api/auth/me returns tenant_slug=null for super-admin (no tenant)."""
    # Login first to get token (validates Gap 1 too)
    login_resp = await client.post(
        "/api/auth/login",
        json={"email": "superadmin@platform.test", "password": "Super#Pass1"},
    )
    assert login_resp.status_code == 200
    token = login_resp.json()["access_token"]

    resp = await client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert "tenant_slug" in body
    assert body["tenant_slug"] is None
