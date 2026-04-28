"""
Per-resource scope enforcement tests.

Tests the additive scope layer in backend/middleware/scopes.py that sits
on top of the existing role_required hierarchy.

Scope vocabulary tested:
  tenants:read   tenants:write
  modules:read   modules:write
  scoring:write
  vapt:read      vapt:write
  settings:read  settings:write

NOTE: The scope layer runs AFTER the user is authenticated. These tests
mint JWTs directly (no DB round-trip for auth) but still require the DB
to be seeded with the necessary tenant + subscription for routes gated
behind require_module("CORE") / require_module("VM").
"""

import uuid

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from backend.middleware.auth import create_access_token, hash_password
from backend.middleware.scopes import ROLE_SCOPES, _has, require_scope
from backend.models.subscription import TenantSubscription
from backend.models.tenant import Tenant
from backend.models.user import User


# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------

SCOPE_TENANT_ID = uuid.UUID("00000000-0000-0000-0000-000000000099")
SCOPE_TENANT_SLUG = "scope-test"


async def _ensure_scope_tenant(db: AsyncSession) -> Tenant:
    """Create (or reuse) a dedicated tenant for scope tests."""
    from sqlalchemy import select

    result = await db.execute(select(Tenant).where(Tenant.id == SCOPE_TENANT_ID))
    tenant = result.scalar_one_or_none()
    if not tenant:
        tenant = Tenant(
            id=SCOPE_TENANT_ID,
            name="Scope Test Tenant",
            slug=SCOPE_TENANT_SLUG,
            domain="scope.urip.test",
            is_active=True,
            settings={},
        )
        db.add(tenant)
        await db.commit()
        await db.refresh(tenant)
    return tenant


async def _ensure_modules(db: AsyncSession) -> None:
    """Enable CORE + VM modules for the scope-test tenant (idempotent)."""
    from sqlalchemy import select

    for code in ("CORE", "VM"):
        result = await db.execute(
            select(TenantSubscription).where(
                TenantSubscription.tenant_id == SCOPE_TENANT_ID,
                TenantSubscription.module_code == code,
                TenantSubscription.is_enabled.is_(True),
            )
        )
        if result.scalar_one_or_none() is None:
            db.add(
                TenantSubscription(
                    id=uuid.uuid4(),
                    tenant_id=SCOPE_TENANT_ID,
                    module_code=code,
                    is_enabled=True,
                    billing_tier="STANDARD",
                    expires_at=None,
                )
            )
    await db.commit()


async def _mint_headers(db: AsyncSession, role: str, email: str) -> dict[str, str]:
    """Create a user with the given role and return their auth headers."""
    user = User(
        id=uuid.uuid4(),
        email=email,
        hashed_password=hash_password("Pass#Scope1234"),
        full_name=f"Scope Test {role.title()}",
        role=role,
        team="Security",
        is_active=True,
        tenant_id=SCOPE_TENANT_ID,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    token = create_access_token(
        str(user.id), user.role, tenant_id=str(SCOPE_TENANT_ID)
    )
    return {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------------------
# Unit tests for scopes.py (no DB/HTTP needed)
# ---------------------------------------------------------------------------


class TestScopeLogic:
    """Pure unit tests for _has() and ROLE_SCOPES map — no I/O."""

    def test_admin_wildcard_scope_grants_all(self):
        """admin:* in user_scopes satisfies any required scope."""
        user_scopes = ROLE_SCOPES["ciso"]
        assert "admin:*" in user_scopes
        for scope in (
            "tenants:write",
            "modules:write",
            "scoring:write",
            "vapt:write",
            "settings:write",
        ):
            assert _has(user_scopes, scope), f"admin:* should grant {scope}"

    def test_unknown_role_gets_no_scopes(self):
        """A role not in ROLE_SCOPES gets an empty set — all scopes denied."""
        from backend.middleware.scopes import ROLE_SCOPES as rs

        unknown_scopes = rs.get("unknown_role", set())
        assert unknown_scopes == set()
        assert not _has(unknown_scopes, "tenants:read")
        assert not _has(unknown_scopes, "admin:*")

    def test_ciso_has_all_defined_scopes(self):
        """CISO must have every named scope (via admin:* wildcard)."""
        ciso_scopes = ROLE_SCOPES["ciso"]
        assert "admin:*" in ciso_scopes

    def test_it_team_cannot_write_tenants(self):
        """it_team does NOT have tenants:write."""
        it_scopes = ROLE_SCOPES["it_team"]
        assert not _has(it_scopes, "tenants:write")

    def test_it_team_can_read_tenants(self):
        """it_team has tenants:read."""
        it_scopes = ROLE_SCOPES["it_team"]
        assert _has(it_scopes, "tenants:read")

    def test_executive_cannot_write_modules(self):
        """executive does NOT have modules:write."""
        exec_scopes = ROLE_SCOPES["executive"]
        assert not _has(exec_scopes, "modules:write")

    def test_executive_can_read_modules(self):
        """executive has modules:read."""
        exec_scopes = ROLE_SCOPES["executive"]
        assert _has(exec_scopes, "modules:read")

    def test_board_minimum_scope(self):
        """board only has tenants:read, nothing else."""
        board_scopes = ROLE_SCOPES["board"]
        assert _has(board_scopes, "tenants:read")
        assert not _has(board_scopes, "tenants:write")
        assert not _has(board_scopes, "modules:read")
        assert not _has(board_scopes, "vapt:read")
        assert not _has(board_scopes, "settings:read")

    def test_it_team_has_scoring_write(self):
        """it_team has scoring:write (they manage fixes)."""
        it_scopes = ROLE_SCOPES["it_team"]
        assert _has(it_scopes, "scoring:write")

    def test_executive_lacks_scoring_write(self):
        """executive does NOT have scoring:write."""
        exec_scopes = ROLE_SCOPES["executive"]
        assert not _has(exec_scopes, "scoring:write")


# ---------------------------------------------------------------------------
# Integration tests (HTTP) — scope enforcement on real routes
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_ciso_can_read_scoring(client: AsyncClient, db_session: AsyncSession):
    """CISO (has scoring:write) can read GET /api/settings/scoring."""
    await _ensure_scope_tenant(db_session)
    await _ensure_modules(db_session)
    headers = await _mint_headers(db_session, "ciso", "ciso-scope-score@urip.test")

    resp = await client.get("/api/settings/scoring", headers=headers)
    assert resp.status_code == 200, resp.text


@pytest.mark.asyncio
async def test_executive_blocked_from_scoring(client: AsyncClient, db_session: AsyncSession):
    """executive (lacks scoring:write) is blocked from GET /api/settings/scoring."""
    await _ensure_scope_tenant(db_session)
    await _ensure_modules(db_session)
    headers = await _mint_headers(db_session, "executive", "exec-scope-score@urip.test")

    resp = await client.get("/api/settings/scoring", headers=headers)
    assert resp.status_code == 403
    assert "scoring:write" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_ciso_can_list_vapt_vendors(client: AsyncClient, db_session: AsyncSession):
    """CISO has vapt:read — GET /api/vapt-vendors returns 200."""
    await _ensure_scope_tenant(db_session)
    await _ensure_modules(db_session)
    headers = await _mint_headers(db_session, "ciso", "ciso-vapt-list@urip.test")

    resp = await client.get("/api/vapt-vendors", headers=headers)
    assert resp.status_code == 200, resp.text


@pytest.mark.asyncio
async def test_board_blocked_from_vapt_read(client: AsyncClient, db_session: AsyncSession):
    """board lacks vapt:read — GET /api/vapt-vendors returns 403."""
    await _ensure_scope_tenant(db_session)
    await _ensure_modules(db_session)
    headers = await _mint_headers(db_session, "board", "board-vapt@urip.test")

    resp = await client.get("/api/vapt-vendors", headers=headers)
    assert resp.status_code == 403
    assert "vapt:read" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_it_team_blocked_from_settings_write(
    client: AsyncClient, db_session: AsyncSession
):
    """it_team lacks settings:write — POST /api/users returns 403."""
    await _ensure_scope_tenant(db_session)
    await _ensure_modules(db_session)
    headers = await _mint_headers(db_session, "it_team", "it-settings-write@urip.test")

    # it_team is also blocked by role_required("ciso") — but the scope check
    # fires first (both role_required and require_scope are independent deps;
    # FastAPI may call either first).  Either 403 is acceptable.
    resp = await client.post(
        "/api/settings/users",
        headers=headers,
        json={
            "email": "newuser@urip.test",
            "full_name": "New User",
            "password": "SuperSecret123!",
            "role": "board",
        },
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_ciso_can_read_settings(client: AsyncClient, db_session: AsyncSession):
    """CISO (has settings:read via admin:*) can list users GET /api/settings/users."""
    await _ensure_scope_tenant(db_session)
    await _ensure_modules(db_session)
    headers = await _mint_headers(db_session, "ciso", "ciso-settings-read@urip.test")

    resp = await client.get("/api/settings/users", headers=headers)
    assert resp.status_code == 200, resp.text


@pytest.mark.asyncio
async def test_board_blocked_from_settings_read(
    client: AsyncClient, db_session: AsyncSession
):
    """board lacks settings:read — GET /api/settings/users returns 403."""
    await _ensure_scope_tenant(db_session)
    await _ensure_modules(db_session)
    headers = await _mint_headers(db_session, "board", "board-settings@urip.test")

    # board also fails role_required("ciso") but scope check may fire first
    resp = await client.get("/api/settings/users", headers=headers)
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_it_team_can_read_vapt_submissions(
    client: AsyncClient, db_session: AsyncSession
):
    """it_team has vapt:read — GET /api/vapt-submissions returns 200."""
    await _ensure_scope_tenant(db_session)
    await _ensure_modules(db_session)
    headers = await _mint_headers(db_session, "it_team", "it-vapt-read@urip.test")

    resp = await client.get("/api/vapt-submissions", headers=headers)
    assert resp.status_code == 200, resp.text
