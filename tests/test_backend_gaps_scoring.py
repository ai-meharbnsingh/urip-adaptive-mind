"""
GAP 4 — PATCH /api/settings/scoring updates tenant scoring weights.

Storage: tenant.settings["scoring_weights"] JSONB.
Tenant-scoped via TenantContext. Audit log written.
"""
import uuid

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.middleware.auth import create_access_token, hash_password
from backend.models.audit_log import AuditLog
from backend.models.subscription import TenantSubscription
from backend.models.tenant import Tenant
from backend.models.user import User


async def _enable_core(db_session: AsyncSession, tenant_id: uuid.UUID) -> None:
    """
    CRIT-007 — settings (incl. scoring) are CORE-gated.

    Tests that mint their own tenants must seed a CORE TenantSubscription
    so that calls to /api/settings/* don't 403 at the module gate before
    reaching the actual handler under test. This mirrors what `auth_headers`
    in the shared conftest does for the default tenant.
    """
    db_session.add(
        TenantSubscription(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            module_code="CORE",
            is_enabled=True,
            billing_tier="STANDARD",
        )
    )
    await db_session.commit()


@pytest_asyncio.fixture
async def tenant_with_user(db_session: AsyncSession):
    t = Tenant(
        id=uuid.uuid4(),
        name="Scoring Co",
        slug="scoringco",
        domain="scoring.test",
        is_active=True,
        settings={},
    )
    db_session.add(t)
    await db_session.commit()
    await db_session.refresh(t)

    # CRIT-007: settings router requires CORE module enabled
    await _enable_core(db_session, t.id)

    user = User(
        id=uuid.uuid4(),
        email="ciso-scoring@scoring.test",
        hashed_password=hash_password("Pass#Score1"),
        full_name="Scoring CISO",
        role="ciso",
        is_active=True,
        is_super_admin=False,
        tenant_id=t.id,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)

    token = create_access_token(str(user.id), user.role, tenant_id=str(t.id))
    return {
        "tenant": t,
        "user": user,
        "headers": {"Authorization": f"Bearer {token}"},
    }


@pytest_asyncio.fixture
async def other_tenant_user(db_session: AsyncSession):
    t = Tenant(
        id=uuid.uuid4(),
        name="Other Co",
        slug="otherco",
        domain="other.test",
        is_active=True,
        settings={"scoring_weights": {"cvss": 1.0, "epss": 2.0, "kev_bonus": 3.0}},
    )
    db_session.add(t)
    await db_session.commit()
    await db_session.refresh(t)

    # CRIT-007: settings router requires CORE module enabled
    await _enable_core(db_session, t.id)

    user = User(
        id=uuid.uuid4(),
        email="ciso-other@other.test",
        hashed_password=hash_password("Pass#Other1"),
        full_name="Other CISO",
        role="ciso",
        is_active=True,
        is_super_admin=False,
        tenant_id=t.id,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)

    token = create_access_token(str(user.id), user.role, tenant_id=str(t.id))
    return {
        "tenant": t,
        "user": user,
        "headers": {"Authorization": f"Bearer {token}"},
    }


# ---------------------------------------------------------------------------
# Happy path: PATCH valid weights → 200, persisted in JSON, audit log written
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_patch_scoring_valid_weights_persists(
    client: AsyncClient, db_session: AsyncSession, tenant_with_user: dict
):
    payload = {"cvss": 0.6, "epss": 2.0, "kev_bonus": 1.5}
    resp = await client.patch(
        "/api/settings/scoring", json=payload, headers=tenant_with_user["headers"]
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["weights"]["cvss"] == 0.6
    assert body["weights"]["epss"] == 2.0
    assert body["weights"]["kev_bonus"] == 1.5

    # Reload tenant from DB to confirm persisted
    tenant = tenant_with_user["tenant"]
    await db_session.refresh(tenant)
    assert tenant.settings.get("scoring_weights") == {
        "cvss": 0.6,
        "epss": 2.0,
        "kev_bonus": 1.5,
    }

    # Audit log entry exists
    log_result = await db_session.execute(
        select(AuditLog).where(
            AuditLog.tenant_id == tenant.id,
            AuditLog.action == "scoring_weights_updated",
        )
    )
    logs = log_result.scalars().all()
    assert len(logs) >= 1, "expected at least one audit_log entry for scoring update"


# ---------------------------------------------------------------------------
# Validation: negative or absurd weights rejected (422)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_patch_scoring_negative_weight_rejected(
    client: AsyncClient, tenant_with_user: dict
):
    resp = await client.patch(
        "/api/settings/scoring",
        json={"cvss": -1.0, "epss": 2.0, "kev_bonus": 1.0},
        headers=tenant_with_user["headers"],
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_patch_scoring_absurd_weight_rejected(
    client: AsyncClient, tenant_with_user: dict
):
    resp = await client.patch(
        "/api/settings/scoring",
        json={"cvss": 0.5, "epss": 2.0, "kev_bonus": 999.0},
        headers=tenant_with_user["headers"],
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_patch_scoring_no_fields_rejected(
    client: AsyncClient, tenant_with_user: dict
):
    """Empty body / no overrides → 422 (must specify at least one weight)."""
    resp = await client.patch(
        "/api/settings/scoring", json={}, headers=tenant_with_user["headers"]
    )
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# Tenant isolation: each tenant updates only their own settings.scoring_weights
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_patch_scoring_isolated_per_tenant(
    client: AsyncClient,
    db_session: AsyncSession,
    tenant_with_user: dict,
    other_tenant_user: dict,
):
    """
    Tenant A patches its own scoring → Tenant B's scoring untouched.
    Cross-tenant write impossible (no tenant_id parameter exposed).
    """
    # Tenant A patches
    await client.patch(
        "/api/settings/scoring",
        json={"cvss": 0.7, "epss": 1.5, "kev_bonus": 2.5},
        headers=tenant_with_user["headers"],
    )

    # Tenant B's row remains as it was
    tenant_b = other_tenant_user["tenant"]
    await db_session.refresh(tenant_b)
    assert tenant_b.settings["scoring_weights"] == {
        "cvss": 1.0,
        "epss": 2.0,
        "kev_bonus": 3.0,
    }


# ---------------------------------------------------------------------------
# GET /api/settings/scoring still works (regression)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_scoring_still_works(client: AsyncClient, tenant_with_user: dict):
    resp = await client.get(
        "/api/settings/scoring", headers=tenant_with_user["headers"]
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert "weights" in body
