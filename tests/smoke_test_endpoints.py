"""
End-to-end smoke test for all backend gap fixes.

Boots the FastAPI app against an in-memory SQLite DB (same fixtures as the
test suite) and walks every newly-touched endpoint end-to-end.  Output is
plain-text so it can be saved as smoke_test_output.txt for the audit log.

Run:
    python -m tests.smoke_test_endpoints
"""
from __future__ import annotations

import asyncio
import json
import sys
import uuid

# Patch PostgreSQL types BEFORE importing models — same trick as conftest.py
import sqlalchemy.dialects.postgresql as _pg
from sqlalchemy import Text
from sqlalchemy.types import CHAR, TypeDecorator


class _UUID(TypeDecorator):
    impl = CHAR(32)
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        if isinstance(value, uuid.UUID):
            return value.hex
        return uuid.UUID(value).hex

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        return uuid.UUID(value)


class _JSON(TypeDecorator):
    impl = Text
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        return json.dumps(value)

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        return json.loads(value)


_pg.UUID = _UUID
_pg.JSON = _JSON

from httpx import ASGITransport, AsyncClient  # noqa: E402
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

from backend.database import Base, get_db  # noqa: E402
from backend.main import app  # noqa: E402
from backend.middleware.auth import create_access_token, hash_password  # noqa: E402
from backend.models.subscription import TenantSubscription  # noqa: E402
from backend.models.tenant import Tenant  # noqa: E402
from backend.models.user import User  # noqa: E402

engine = create_async_engine(
    "sqlite+aiosqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False)


async def _setup_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    return SessionLocal()


async def _seed(session):
    tenant = Tenant(
        id=uuid.uuid4(),
        name="Smoke Tenant",
        slug="smoke",
        domain="smoke.test",
        is_active=True,
        settings={
            "app_name": "Smoke RiskPanel",
            "logo_url": "https://cdn.smoke.test/l.png",
            "primary_color": "#001122",
            "secondary_color": "#334455",
        },
    )
    session.add(tenant)

    user = User(
        id=uuid.uuid4(),
        email="ciso@smoke.test",
        hashed_password=hash_password("Smoke#Pass1"),
        full_name="Smoke CISO",
        role="ciso",
        team="Security",
        is_active=True,
        is_super_admin=False,
        tenant_id=tenant.id,
    )
    session.add(user)

    super_admin = User(
        id=uuid.uuid4(),
        email="super@smoke.test",
        hashed_password=hash_password("Super#Pass1"),
        full_name="Super",
        role="ciso",
        is_active=True,
        is_super_admin=True,
        tenant_id=None,
    )
    session.add(super_admin)

    sub = TenantSubscription(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        module_code="VM",
        is_enabled=True,
        billing_tier="STANDARD",
    )
    session.add(sub)

    await session.commit()
    return tenant, user, super_admin


def _check(label: str, resp, expected: int | tuple[int, ...]):
    expected_set = (expected,) if isinstance(expected, int) else expected
    ok = resp.status_code in expected_set
    body_preview = ""
    try:
        body_preview = json.dumps(resp.json())[:200]
    except Exception:
        body_preview = resp.text[:200]
    print(
        f"  {'PASS' if ok else 'FAIL'}  {label:60s}  "
        f"status={resp.status_code} expected={expected_set}  body[:200]={body_preview}"
    )
    return ok


async def main():
    session = await _setup_db()
    tenant, user, super_admin = await _seed(session)

    async def _override_get_db():
        yield session

    app.dependency_overrides[get_db] = _override_get_db

    transport = ASGITransport(app=app)
    failures = 0

    async with AsyncClient(transport=transport, base_url="http://smoke") as client:
        print("=" * 80)
        print("GAP 1 + 2 — login JWT contains is_super_admin; /me returns tenant_slug")
        print("=" * 80)

        # Login as regular CISO
        login = await client.post(
            "/api/auth/login",
            json={"email": "ciso@smoke.test", "password": "Smoke#Pass1"},
        )
        ok = _check("POST /api/auth/login (regular)", login, 200)
        if not ok:
            failures += 1
        else:
            body = login.json()
            assert "is_super_admin" in body["user"], "user.is_super_admin missing"
            assert "tenant_slug" in body["user"], "user.tenant_slug missing"
            assert body["user"]["tenant_slug"] == "smoke"
            assert body["user"]["is_super_admin"] is False
            print(f"      → user.tenant_slug = {body['user']['tenant_slug']}, is_super_admin = {body['user']['is_super_admin']}")

        token = login.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # Login as super-admin
        s_login = await client.post(
            "/api/auth/login",
            json={"email": "super@smoke.test", "password": "Super#Pass1"},
        )
        if not _check("POST /api/auth/login (super-admin)", s_login, 200):
            failures += 1
        else:
            sb = s_login.json()
            assert sb["user"]["is_super_admin"] is True, "super-admin login should set is_super_admin=True"
            assert sb["user"]["tenant_slug"] is None
            print(f"      → super-admin user.is_super_admin = {sb['user']['is_super_admin']}, tenant_slug = {sb['user']['tenant_slug']}")
        s_token = s_login.json()["access_token"]
        s_headers = {"Authorization": f"Bearer {s_token}"}

        # /auth/me regular
        me = await client.get("/api/auth/me", headers=headers)
        if not _check("GET  /api/auth/me (regular)", me, 200):
            failures += 1
        else:
            mb = me.json()
            assert mb["tenant_slug"] == "smoke"
            assert mb["is_super_admin"] is False

        # /auth/me super-admin
        s_me = await client.get("/api/auth/me", headers=s_headers)
        if not _check("GET  /api/auth/me (super-admin)", s_me, 200):
            failures += 1

        print()
        print("=" * 80)
        print("GAP 3 — public /branding endpoint")
        print("=" * 80)
        b = await client.get(f"/api/tenants/{tenant.slug}/branding", headers=headers)
        if not _check(f"GET  /api/tenants/{tenant.slug}/branding (own)", b, 200):
            failures += 1
        else:
            bb = b.json()
            assert bb["app_name"] == "Smoke RiskPanel"
            assert bb["secondary_color"] == "#334455"

        # Cross-tenant 404 (use a slug that doesn't exist)
        b404 = await client.get("/api/tenants/nonexistent/branding", headers=headers)
        if not _check("GET  /api/tenants/nonexistent/branding", b404, 404):
            failures += 1

        # Super-admin reads
        sb_branding = await client.get(f"/api/tenants/{tenant.slug}/branding", headers=s_headers)
        if not _check(f"GET  /api/tenants/{tenant.slug}/branding (super-admin)", sb_branding, 200):
            failures += 1

        # Unauthenticated → 403 (HTTPBearer)
        no_auth = await client.get(f"/api/tenants/{tenant.slug}/branding")
        if not _check(f"GET  /api/tenants/{tenant.slug}/branding (no auth)", no_auth, (401, 403)):
            failures += 1

        print()
        print("=" * 80)
        print("GAP 4 — PATCH /api/settings/scoring")
        print("=" * 80)
        sg = await client.get("/api/settings/scoring", headers=headers)
        if not _check("GET  /api/settings/scoring", sg, 200):
            failures += 1

        ps = await client.patch(
            "/api/settings/scoring",
            headers=headers,
            json={"cvss": 0.65, "epss": 2.1, "kev_bonus": 1.8},
        )
        if not _check("PATCH /api/settings/scoring (valid)", ps, 200):
            failures += 1
        else:
            assert ps.json()["weights"]["cvss"] == 0.65

        ps_neg = await client.patch(
            "/api/settings/scoring",
            headers=headers,
            json={"cvss": -1.0, "epss": 2.0, "kev_bonus": 1.0},
        )
        if not _check("PATCH /api/settings/scoring (negative → 422)", ps_neg, 422):
            failures += 1

        ps_empty = await client.patch(
            "/api/settings/scoring", headers=headers, json={}
        )
        if not _check("PATCH /api/settings/scoring (empty → 422)", ps_empty, 422):
            failures += 1

        print()
        print("=" * 80)
        print("GAP 5 — TenantUpdate.secondary_color (super-admin PATCH)")
        print("=" * 80)
        upd = await client.patch(
            f"/api/admin/tenants/{tenant.slug}",
            headers=s_headers,
            json={"secondary_color": "#FFEEDD"},
        )
        if not _check(f"PATCH /api/admin/tenants/{tenant.slug} (secondary_color valid)", upd, 200):
            failures += 1
        else:
            assert upd.json()["settings"]["secondary_color"] == "#FFEEDD"

        upd_bad = await client.patch(
            f"/api/admin/tenants/{tenant.slug}",
            headers=s_headers,
            json={"secondary_color": "purple"},
        )
        if not _check(f"PATCH /api/admin/tenants/{tenant.slug} (bad hex → 422)", upd_bad, 422):
            failures += 1

        print()
        print("=" * 80)
        print("REGRESSION SPOTCHECK — endpoints that were tightened")
        print("=" * 80)

        # POST /api/risks now 201
        risk_resp = await client.post(
            "/api/risks",
            headers=headers,
            json={
                "finding": "Smoke test risk",
                "description": "smoke",
                "source": "vapt",
                "domain": "application",
                "cvss_score": 5.5,
                "severity": "medium",
                "asset": "smoke.host",
                "owner_team": "AppSec",
            },
        )
        if not _check("POST /api/risks (201 created)", risk_resp, 201):
            failures += 1
        risk_id = risk_resp.json()["risk_id"]

        # GET /api/risks/{id} now Pydantic (RiskDetailResponse)
        rd = await client.get(f"/api/risks/{risk_id}", headers=headers)
        if not _check(f"GET  /api/risks/{risk_id}", rd, 200):
            failures += 1
        else:
            rdb = rd.json()
            assert "risk" in rdb and "history" in rdb

        # POST /api/acceptance now 201
        ar = await client.post(
            "/api/acceptance",
            headers=headers,
            json={"risk_id": risk_id, "justification": "compensating controls in place"},
        )
        if not _check("POST /api/acceptance (201 created)", ar, 201):
            failures += 1

        # POST /api/settings/users now 201
        nu = await client.post(
            "/api/settings/users",
            headers=headers,
            json={
                "email": "newuser@smoke.test",
                "full_name": "New User",
                "password": "NewUser#Pass1",
                "role": "it_team",
                "team": "Ops",
            },
        )
        if not _check("POST /api/settings/users (201 created)", nu, 201):
            failures += 1

        # GET /api/settings/users now Pydantic + tenant-scoped
        lu = await client.get("/api/settings/users", headers=headers)
        if not _check("GET  /api/settings/users (Pydantic + tenant-scoped)", lu, 200):
            failures += 1

        # GET /api/dashboard/kpis still works (regression)
        k = await client.get("/api/dashboard/kpis", headers=headers)
        if not _check("GET  /api/dashboard/kpis", k, 200):
            failures += 1

        # Cross-tenant 404 on /api/tenants/{slug}/modules
        cross = await client.get("/api/tenants/nonexistent/modules", headers=headers)
        if not _check("GET  /api/tenants/nonexistent/modules (404 not 403)", cross, 404):
            failures += 1

    print()
    print("=" * 80)
    print(f"SMOKE TEST COMPLETE — failures: {failures}")
    print("=" * 80)
    return failures


if __name__ == "__main__":
    failures = asyncio.run(main())
    sys.exit(0 if failures == 0 else 1)
