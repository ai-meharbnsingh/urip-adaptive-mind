"""ZTNA module — model + service + route tests (Project_33a §13 MVP scaffold)."""
from __future__ import annotations

import uuid

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.middleware.auth import create_access_token, hash_password
from backend.models.subscription import TenantSubscription
from backend.models.user import User
from backend.models.ztna import (
    DECISION_VALUES,
    POSTURE_REQUIREMENT_VALUES,
    ZTNAAccessDecision,
    ZTNAPolicy,
    ZTNAPostureViolation,
)
from backend.services.ztna import (
    create_policy,
    list_access_decisions,
    list_policies,
    list_posture_violations,
    record_access_decision,
    record_posture_violation,
)


# --------------------------------------------------------------------------- #
@pytest_asyncio.fixture
async def ztna_subscription(db_session: AsyncSession, default_tenant) -> TenantSubscription:
    sub = TenantSubscription(
        id=uuid.uuid4(),
        tenant_id=default_tenant.id,
        module_code="ZTNA",
        is_enabled=True,
        billing_tier="STANDARD",
    )
    db_session.add(sub)
    await db_session.commit()
    return sub


@pytest_asyncio.fixture
async def ztna_auth_headers(
    db_session: AsyncSession, default_tenant, ztna_subscription
) -> dict[str, str]:
    user = User(
        id=uuid.uuid4(),
        email="ciso-ztna@urip.test",
        hashed_password=hash_password("Secure#Pass1"),
        full_name="ZTNA CISO",
        role="ciso",
        team="Security",
        is_active=True,
        tenant_id=default_tenant.id,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    token = create_access_token(str(user.id), user.role, tenant_id=str(default_tenant.id))
    return {"Authorization": f"Bearer {token}"}


# --------------------------------------------------------------------------- #
# Model
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_ztna_policy_persists(db_session, default_tenant):
    p = ZTNAPolicy(
        id=uuid.uuid4(),
        tenant_id=default_tenant.id,
        policy_name="Finance App MFA",
        target_app="finance.example.com",
        identity_required=True,
        mfa_required=True,
        device_posture_required=["edr_running", "os_patched"],
        source_provider="zscaler-zpa",
    )
    db_session.add(p)
    await db_session.commit()
    rows = (await db_session.execute(select(ZTNAPolicy))).scalars().all()
    assert len(rows) == 1
    assert rows[0].mfa_required is True
    assert "edr_running" in rows[0].device_posture_required


def test_decision_values_constant():
    assert DECISION_VALUES == {"allow", "deny", "step_up"}


def test_posture_requirement_values_constant():
    for v in {"encryption_at_rest", "edr_running", "os_patched", "no_jailbreak"}:
        assert v in POSTURE_REQUIREMENT_VALUES


# --------------------------------------------------------------------------- #
# Service
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_create_policy_validates_posture_requirements(db_session, default_tenant):
    with pytest.raises(ValueError):
        await create_policy(
            db_session, default_tenant.id,
            policy_name="x", target_app="y",
            device_posture_required=["nuclear_authorization"],
        )


@pytest.mark.asyncio
async def test_record_access_decision_validates_decision(db_session, default_tenant):
    with pytest.raises(ValueError):
        await record_access_decision(
            db_session, default_tenant.id,
            user_identity="alice", target_app="app", decision="maybe",
        )


@pytest.mark.asyncio
async def test_record_posture_violation_validates_requirement(db_session, default_tenant):
    with pytest.raises(ValueError):
        await record_posture_violation(
            db_session, default_tenant.id,
            user_identity="alice", failed_requirement="happy_user",
        )


@pytest.mark.asyncio
async def test_list_policies_filters_by_target_app(db_session, default_tenant):
    await create_policy(
        db_session, default_tenant.id,
        policy_name="finance", target_app="finance.example.com",
    )
    await create_policy(
        db_session, default_tenant.id,
        policy_name="hr", target_app="hr.example.com",
    )
    await db_session.commit()
    result = await list_policies(
        db_session, default_tenant.id, target_app="finance.example.com",
    )
    assert len(result) == 1
    assert result[0].policy_name == "finance"


@pytest.mark.asyncio
async def test_list_posture_violations_filters_by_severity(db_session, default_tenant):
    await record_posture_violation(
        db_session, default_tenant.id,
        user_identity="a", failed_requirement="edr_running", severity="high",
    )
    await record_posture_violation(
        db_session, default_tenant.id,
        user_identity="b", failed_requirement="os_patched", severity="low",
    )
    await db_session.commit()
    high = await list_posture_violations(db_session, default_tenant.id, severity="high")
    assert len(high) == 1
    assert high[0].user_identity == "a"


# --------------------------------------------------------------------------- #
# Routes
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_ztna_route_403_without_subscription(client: AsyncClient, auth_headers):
    resp = await client.get("/api/ztna/policies", headers=auth_headers)
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_ztna_post_then_get_policy(
    client: AsyncClient, db_session, default_tenant, ztna_auth_headers
):
    resp = await client.post(
        "/api/ztna/policies",
        json={
            "policy_name": "Crown jewel app",
            "target_app": "crown-jewel.example.com",
            "identity_required": True,
            "mfa_required": True,
            "device_posture_required": ["edr_running", "os_patched"],
            "source_provider": "cloudflare-access",
        },
        headers=ztna_auth_headers,
    )
    assert resp.status_code == 201, resp.text

    get_resp = await client.get("/api/ztna/policies", headers=ztna_auth_headers)
    assert get_resp.status_code == 200
    body = get_resp.json()
    assert body["total"] == 1
    assert body["items"][0]["policy_name"] == "Crown jewel app"


@pytest.mark.asyncio
async def test_ztna_access_decisions_endpoint(
    client: AsyncClient, db_session, default_tenant, ztna_auth_headers
):
    db_session.add(
        ZTNAAccessDecision(
            id=uuid.uuid4(),
            tenant_id=default_tenant.id,
            user_identity="bob@example.com",
            target_app="finance.example.com",
            decision="deny",
            reason="failed device posture",
        )
    )
    await db_session.commit()
    resp = await client.get(
        "/api/ztna/access-decisions?decision=deny",
        headers=ztna_auth_headers,
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["total"] == 1
    assert data["items"][0]["decision"] == "deny"


@pytest.mark.asyncio
async def test_ztna_posture_violations_endpoint(
    client: AsyncClient, db_session, default_tenant, ztna_auth_headers
):
    db_session.add(
        ZTNAPostureViolation(
            id=uuid.uuid4(),
            tenant_id=default_tenant.id,
            user_identity="carol@example.com",
            device_id="dev-42",
            failed_requirement="encryption_at_rest",
            severity="critical",
        )
    )
    await db_session.commit()
    resp = await client.get(
        "/api/ztna/posture-violations?severity=critical",
        headers=ztna_auth_headers,
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["total"] == 1
