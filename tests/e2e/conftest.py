"""
Shared E2E fixtures and helpers for URIP-side end-to-end workflows.

Builds on the project-level tests/conftest.py (which provides:
  - SQLite-in-memory async engine
  - `client` httpx.AsyncClient bound to the FastAPI app
  - `db_session` AsyncSession
  - `default_tenant` Tenant
  - `auth_headers`, `it_team_headers`, `vm_subscription`, `seeded_risks`).

These E2E fixtures add:
  - `super_admin_headers`            : JWT with is_super_admin=True
  - `tenant_factory`                 : async helper to create a tenant + provision admin
  - `enable_module`                  : async helper to switch on a module subscription
  - `tenant_user_headers`            : helper to build a JWT for a given (user_id, tenant_id)
"""

from __future__ import annotations

import uuid
from typing import Any, Awaitable, Callable

import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from backend.middleware.auth import create_access_token, hash_password
from backend.models.tenant import Tenant
from backend.models.user import User


# ---------------------------------------------------------------------------
# Super-admin user + headers
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def super_admin_user(db_session: AsyncSession) -> User:
    user = User(
        id=uuid.uuid4(),
        email=f"super-{uuid.uuid4().hex[:6]}@platform.test",
        hashed_password=hash_password("Super#Admin1"),
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


@pytest_asyncio.fixture
async def super_admin_headers(super_admin_user: User) -> dict[str, str]:
    token = create_access_token(
        str(super_admin_user.id),
        super_admin_user.role,
        tenant_id=None,
        is_super_admin=True,
    )
    return {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------------------
# Tenant factory — wraps the public super-admin onboarding API.
#
# Returns a dict like:
#   {
#       "tenant":   <Tenant ORM>,
#       "slug":     "alpha",
#       "admin_id": "<uuid>",
#       "admin_email": "ciso@alpha.test",
#       "admin_token": "<jwt>",
#       "admin_headers": {"Authorization": "Bearer ..."},
#   }
# ---------------------------------------------------------------------------


TenantFactory = Callable[..., Awaitable[dict[str, Any]]]


@pytest_asyncio.fixture
async def tenant_factory(
    client: AsyncClient,
    db_session: AsyncSession,
    super_admin_headers: dict[str, str],
) -> TenantFactory:
    async def _make(
        slug: str,
        *,
        name: str | None = None,
        domain: str | None = None,
        admin_email: str | None = None,
        admin_role: str = "ciso",
        admin_password: str = "Tenant#Admin1",
        enable_core: bool = True,
    ) -> dict[str, Any]:
        body = {
            "name": name or f"Tenant {slug.title()}",
            "slug": slug,
            "domain": domain or f"{slug}.test",
        }
        resp = await client.post(
            "/api/admin/tenants", json=body, headers=super_admin_headers
        )
        assert resp.status_code == 201, (
            f"tenant_factory: failed to create tenant '{slug}': {resp.status_code} {resp.text}"
        )
        tenant_payload = resp.json()
        tenant_id = uuid.UUID(tenant_payload["id"])

        # CRIT-007 — every fresh tenant in E2E flows is given the CORE module by
        # default so that platform features (audit-log, dashboard, settings,
        # branding) are reachable. Workflows that explicitly test the disabled
        # path can pass enable_core=False.
        if enable_core:
            core_resp = await client.post(
                f"/api/admin/tenants/{slug}/modules",
                json={"module_code": "CORE", "billing_tier": "STANDARD"},
                headers=super_admin_headers,
            )
            assert core_resp.status_code in (201, 409), (
                f"tenant_factory: failed to enable CORE for '{slug}': "
                f"{core_resp.status_code} {core_resp.text}"
            )

        # Provision an admin user via the super-admin endpoint.
        email = admin_email or f"admin-{uuid.uuid4().hex[:5]}@{slug}.test"
        resp_user = await client.post(
            f"/api/admin/tenants/{slug}/users",
            json={
                "email": email,
                "full_name": f"{slug.title()} Admin",
                "password": admin_password,
                "role": admin_role,
            },
            headers=super_admin_headers,
        )
        assert resp_user.status_code == 201, (
            f"tenant_factory: failed to provision admin for '{slug}': "
            f"{resp_user.status_code} {resp_user.text}"
        )
        user_payload = resp_user.json()

        # Refresh the Tenant ORM object from DB so callers can use its UUID.
        from sqlalchemy import select

        result = await db_session.execute(select(Tenant).where(Tenant.id == tenant_id))
        tenant_orm = result.scalar_one()

        return {
            "tenant": tenant_orm,
            "slug": slug,
            "tenant_id": tenant_id,
            "admin_id": user_payload["user_id"],
            "admin_email": user_payload["email"],
            "admin_password": admin_password,
            "admin_token": user_payload["access_token"],
            "admin_headers": {
                "Authorization": f"Bearer {user_payload['access_token']}"
            },
        }

    return _make


# ---------------------------------------------------------------------------
# Module subscription helper
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def enable_module(
    client: AsyncClient, super_admin_headers: dict[str, str]
) -> Callable[..., Awaitable[dict[str, Any]]]:
    async def _enable(slug: str, module_code: str = "VM", billing_tier: str = "STANDARD"):
        resp = await client.post(
            f"/api/admin/tenants/{slug}/modules",
            json={"module_code": module_code, "billing_tier": billing_tier},
            headers=super_admin_headers,
        )
        # 201 = newly created; 409 = already enabled (treat as ok for the workflow)
        assert resp.status_code in (201, 409), (
            f"enable_module {slug}/{module_code}: {resp.status_code} {resp.text}"
        )
        if resp.status_code == 201:
            return resp.json()
        return None

    return _enable


@pytest_asyncio.fixture
async def disable_module(
    client: AsyncClient, super_admin_headers: dict[str, str]
) -> Callable[..., Awaitable[dict[str, Any] | None]]:
    async def _disable(slug: str, module_code: str = "VM") -> dict[str, Any] | None:
        resp = await client.delete(
            f"/api/admin/tenants/{slug}/modules/{module_code}",
            headers=super_admin_headers,
        )
        # 200 = disabled; 409 = already disabled
        assert resp.status_code in (200, 409), (
            f"disable_module {slug}/{module_code}: {resp.status_code} {resp.text}"
        )
        return resp.json() if resp.status_code == 200 else None

    return _disable


# ---------------------------------------------------------------------------
# Generic JWT builder — useful when you need a non-admin user under a tenant
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def make_user_in_tenant(db_session: AsyncSession):
    async def _make(
        tenant_id: uuid.UUID,
        *,
        email: str | None = None,
        role: str = "it_team",
        full_name: str = "E2E User",
    ) -> tuple[User, dict[str, str]]:
        user = User(
            id=uuid.uuid4(),
            email=email or f"u-{uuid.uuid4().hex[:6]}@e2e.test",
            hashed_password=hash_password("E2E#Pass1"),
            full_name=full_name,
            role=role,
            is_active=True,
            is_super_admin=False,
            tenant_id=tenant_id,
        )
        db_session.add(user)
        await db_session.commit()
        await db_session.refresh(user)
        token = create_access_token(str(user.id), role, tenant_id=str(tenant_id))
        return user, {"Authorization": f"Bearer {token}"}

    return _make
