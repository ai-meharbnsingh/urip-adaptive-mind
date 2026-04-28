"""
CRIT-007: @require_module gating coverage.

Vulnerability:
- Only `GET /api/risks` was gated by @require_module("VM").
- A tenant subscribed to only CORE could call any other module-specific
  endpoint (POST /api/risks, /api/acceptance, /api/remediation, /api/threat-intel,
  /api/dashboard/*, /api/reports, /api/audit-log, /api/settings) and read or
  mutate data the tenant had not paid for.

Required gating (from task spec):
- risks.py        — ALL endpoints  → require_module("VM")
- acceptance.py   — ALL endpoints  → require_module("VM")
- remediation.py  — ALL endpoints  → require_module("VM")
- threat_intel.py — ALL endpoints  → require_any_module(["VM","EDR","NETWORK"])
- dashboard.py    — KPI endpoints  → require_module("CORE")
- reports.py      — ALL endpoints  → require_module("CORE")
- audit_log.py    — ALL endpoints  → require_module("CORE")
- settings.py     — ALL endpoints  → require_module("CORE")
- super-admin bypasses every gate.

Tests verify:
A. require_any_module helper exists and behaves correctly.
B. A tenant with ONLY CORE enabled hits VM-gated endpoints → 403.
C. A tenant with ONLY CORE enabled hits CORE-gated endpoints → 200/4xx-not-403.
D. A super-admin (acting in a tenant with NO subscriptions) bypasses every gate.
"""

import uuid
from datetime import datetime, timezone

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from backend.middleware.auth import create_access_token, hash_password
from backend.models.subscription import TenantSubscription
from backend.models.tenant import Tenant
from backend.models.user import User


# ---------------------------------------------------------------------------
# Test helpers
# ---------------------------------------------------------------------------


async def _make_tenant(db: AsyncSession, slug: str, modules: list[str]) -> Tenant:
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
    for code in modules:
        db.add(TenantSubscription(
            id=uuid.uuid4(),
            tenant_id=t.id,
            module_code=code,
            is_enabled=True,
            billing_tier="STANDARD",
        ))
    await db.commit()
    return t


async def _make_user(db: AsyncSession, tenant: Tenant, role: str = "ciso") -> User:
    u = User(
        id=uuid.uuid4(),
        email=f"user-{tenant.slug}@{tenant.domain}",
        hashed_password=hash_password("Pa55word#1!"),
        full_name=f"User {tenant.slug}",
        role=role,
        is_active=True,
        is_super_admin=False,
        tenant_id=tenant.id,
    )
    db.add(u)
    await db.commit()
    await db.refresh(u)
    return u


def _headers_for(user: User, tenant: Tenant | None = None, is_super_admin: bool = False) -> dict:
    tid = str(tenant.id) if tenant is not None else None
    token = create_access_token(
        str(user.id),
        user.role,
        tenant_id=tid,
        is_super_admin=is_super_admin,
    )
    return {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def core_only_tenant(db_session: AsyncSession) -> Tenant:
    """Tenant with only CORE module enabled — can hit core endpoints, not VM."""
    return await _make_tenant(db_session, "core-only", ["CORE"])


@pytest_asyncio.fixture
async def core_only_user(db_session: AsyncSession, core_only_tenant: Tenant) -> User:
    return await _make_user(db_session, core_only_tenant)


@pytest_asyncio.fixture
async def core_only_headers(core_only_user: User, core_only_tenant: Tenant) -> dict:
    return _headers_for(core_only_user, core_only_tenant)


@pytest_asyncio.fixture
async def vm_tenant(db_session: AsyncSession) -> Tenant:
    """Tenant with CORE + VM enabled — can hit both."""
    return await _make_tenant(db_session, "vm-tenant", ["CORE", "VM"])


@pytest_asyncio.fixture
async def vm_user(db_session: AsyncSession, vm_tenant: Tenant) -> User:
    return await _make_user(db_session, vm_tenant, role="it_team")


@pytest_asyncio.fixture
async def vm_headers(vm_user: User, vm_tenant: Tenant) -> dict:
    return _headers_for(vm_user, vm_tenant)


@pytest_asyncio.fixture
async def edr_only_tenant(db_session: AsyncSession) -> Tenant:
    """Tenant with EDR enabled (used to confirm threat-intel any-of helper)."""
    return await _make_tenant(db_session, "edr-only", ["CORE", "EDR"])


@pytest_asyncio.fixture
async def edr_only_user(db_session: AsyncSession, edr_only_tenant: Tenant) -> User:
    return await _make_user(db_session, edr_only_tenant)


@pytest_asyncio.fixture
async def edr_only_headers(edr_only_user: User, edr_only_tenant: Tenant) -> dict:
    return _headers_for(edr_only_user, edr_only_tenant)


@pytest_asyncio.fixture
async def super_admin_user(db_session: AsyncSession) -> User:
    u = User(
        id=uuid.uuid4(),
        email="super@platform.io",
        hashed_password=hash_password("Admin#Pass2"),
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
async def super_admin_headers_for_core_tenant(super_admin_user: User, core_only_tenant: Tenant) -> dict:
    """Super-admin acting within core_only_tenant context."""
    return _headers_for(super_admin_user, core_only_tenant, is_super_admin=True)


# ---------------------------------------------------------------------------
# A. require_any_module helper
# ---------------------------------------------------------------------------


def test_require_any_module_helper_exists():
    """module_gate exposes a require_any_module(["VM","EDR"]) helper."""
    from backend.middleware import module_gate

    assert hasattr(module_gate, "require_any_module"), (
        "module_gate.require_any_module(...) helper missing — needed by "
        "threat_intel router (any of VM/EDR/NETWORK)"
    )
    # Smoke-call: returns a FastAPI dependency callable
    dep = module_gate.require_any_module(["VM", "EDR"])
    assert callable(dep)


# ---------------------------------------------------------------------------
# B. CORE-only tenant → blocked from VM-gated endpoints
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "method,path",
    [
        ("GET", "/api/risks"),
        ("GET", "/api/risks/RISK-DOES-NOT-EXIST"),
        ("POST", "/api/risks"),
        ("PATCH", "/api/risks/RISK-DOES-NOT-EXIST"),
        ("POST", "/api/risks/RISK-DOES-NOT-EXIST/assign"),
        # acceptance
        ("GET", "/api/acceptance"),
        ("POST", "/api/acceptance"),
        # remediation
        ("GET", "/api/remediation"),
        ("POST", "/api/remediation"),
        ("PATCH", f"/api/remediation/{uuid.uuid4()}"),
    ],
)
@pytest.mark.asyncio
async def test_vm_endpoints_blocked_for_core_only_tenant(
    client: AsyncClient,
    core_only_headers: dict,
    method: str,
    path: str,
):
    """Tenant with only CORE → all VM-gated endpoints return 403."""
    body = {} if method in {"POST", "PATCH"} else None
    resp = await client.request(method, path, headers=core_only_headers, json=body)
    assert resp.status_code == 403, (
        f"{method} {path} should be 403 for CORE-only tenant; "
        f"got {resp.status_code}: {resp.text[:200]}"
    )
    assert "module" in resp.json().get("detail", "").lower() or "vm" in resp.json().get("detail", "").lower()


@pytest.mark.parametrize(
    "method,path",
    [
        ("GET", "/api/threat-intel/pulses"),
        ("GET", "/api/threat-intel/apt-groups"),
        ("GET", "/api/threat-intel/iocs"),
        ("GET", "/api/threat-intel/iocs/match"),
        ("GET", "/api/threat-intel/geo-stats"),
        ("GET", "/api/threat-intel/dark-web"),
    ],
)
@pytest.mark.asyncio
async def test_threat_intel_blocked_when_no_security_module(
    client: AsyncClient,
    core_only_headers: dict,
    method: str,
    path: str,
):
    """Threat-intel needs at least one of VM/EDR/NETWORK; CORE-only → 403."""
    resp = await client.request(method, path, headers=core_only_headers)
    assert resp.status_code == 403, (
        f"{method} {path} should be 403 for CORE-only tenant (needs VM/EDR/NETWORK); "
        f"got {resp.status_code}: {resp.text[:200]}"
    )


@pytest.mark.asyncio
async def test_threat_intel_allowed_when_edr_enabled(
    client: AsyncClient,
    edr_only_headers: dict,
):
    """Tenant with EDR (any of the security set) can hit threat-intel."""
    resp = await client.get("/api/threat-intel/pulses", headers=edr_only_headers)
    # 200 (data returned) or 5xx for upstream API issue — but NOT 403 from gate
    assert resp.status_code != 403, (
        f"EDR-enabled tenant should not be 403 on /api/threat-intel; "
        f"got {resp.status_code}: {resp.text[:200]}"
    )


# ---------------------------------------------------------------------------
# C. CORE-gated endpoints — CORE-only tenant must NOT receive 403
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "method,path",
    [
        # dashboard
        ("GET", "/api/dashboard/kpis"),
        ("GET", "/api/dashboard/charts/by-domain"),
        ("GET", "/api/dashboard/charts/by-source"),
        ("GET", "/api/dashboard/charts/trend"),
        ("GET", "/api/dashboard/alerts"),
        # reports
        ("GET", "/api/reports/certin"),
        ("GET", "/api/reports/scheduled"),
        # audit log
        ("GET", "/api/audit-log"),
        # settings
        ("GET", "/api/settings/users"),
        ("GET", "/api/settings/connectors"),
        ("GET", "/api/settings/scoring"),
    ],
)
@pytest.mark.asyncio
async def test_core_endpoints_allowed_for_core_only_tenant(
    client: AsyncClient,
    core_only_headers: dict,
    method: str,
    path: str,
):
    """Core endpoints must NOT 403 a tenant with CORE enabled."""
    resp = await client.request(method, path, headers=core_only_headers)
    assert resp.status_code != 403, (
        f"{method} {path} unexpectedly 403 for CORE-only tenant: {resp.text[:200]}"
    )


# ---------------------------------------------------------------------------
# C2. CORE-gated endpoints — tenant WITHOUT CORE → 403
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def no_modules_tenant(db_session: AsyncSession) -> Tenant:
    """Tenant with NO modules enabled at all."""
    return await _make_tenant(db_session, "no-mods", [])


@pytest_asyncio.fixture
async def no_modules_user(db_session: AsyncSession, no_modules_tenant: Tenant) -> User:
    return await _make_user(db_session, no_modules_tenant)


@pytest_asyncio.fixture
async def no_modules_headers(no_modules_user: User, no_modules_tenant: Tenant) -> dict:
    return _headers_for(no_modules_user, no_modules_tenant)


@pytest.mark.parametrize(
    "method,path",
    [
        ("GET", "/api/dashboard/kpis"),
        ("GET", "/api/audit-log"),
        ("GET", "/api/settings/scoring"),
        ("GET", "/api/reports/scheduled"),
    ],
)
@pytest.mark.asyncio
async def test_core_endpoints_blocked_when_no_core_module(
    client: AsyncClient,
    no_modules_headers: dict,
    method: str,
    path: str,
):
    """Tenant with no modules → CORE-gated endpoints return 403."""
    resp = await client.request(method, path, headers=no_modules_headers)
    assert resp.status_code == 403, (
        f"{method} {path} should be 403 when CORE not enabled; "
        f"got {resp.status_code}: {resp.text[:200]}"
    )


# ---------------------------------------------------------------------------
# D. Super-admin bypass
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "method,path",
    [
        ("GET", "/api/risks"),
        ("GET", "/api/acceptance"),
        ("GET", "/api/remediation"),
        ("GET", "/api/threat-intel/pulses"),
        ("GET", "/api/dashboard/kpis"),
        ("GET", "/api/audit-log"),
        ("GET", "/api/settings/users"),
        ("GET", "/api/reports/scheduled"),
    ],
)
@pytest.mark.asyncio
async def test_super_admin_bypasses_every_gate(
    client: AsyncClient,
    super_admin_headers_for_core_tenant: dict,
    method: str,
    path: str,
):
    """Super-admin (acting inside core_only_tenant which lacks VM) bypasses gates."""
    resp = await client.request(method, path, headers=super_admin_headers_for_core_tenant)
    assert resp.status_code != 403, (
        f"super-admin unexpectedly blocked at {method} {path}: {resp.text[:200]}"
    )
