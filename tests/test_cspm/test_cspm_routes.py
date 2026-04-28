"""
Tests for CSPM REST API routes.

Covers:
- Tenant scoping
- Module gate (require_module('CSPM'))
- All CSPM endpoints
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from backend.middleware.auth import create_access_token, hash_password
from backend.models.cspm import CspmCheckResult, CspmControl, CspmFramework, CspmScoreSnapshot
from backend.models.subscription import TenantSubscription
from backend.models.tenant import Tenant
from backend.models.tenant_connector_credential import TenantConnectorCredential
from backend.models.user import User


@pytest.fixture(autouse=True)
def _set_fernet_key(monkeypatch):
    monkeypatch.setenv(
        "URIP_FERNET_KEY",
        "M3JKpUVOfx1nPLQYMRrxnVZsJq3cJ5vXq7bOe6jfXok=",
    )


@pytest_asyncio.fixture
async def cspm_tenant(db_session: AsyncSession) -> Tenant:
    t = Tenant(
        id=uuid.uuid4(),
        name="CSPM Tenant",
        slug="cspm-tenant",
        domain="cspm.test",
        is_active=True,
        settings={},
    )
    db_session.add(t)
    await db_session.commit()
    await db_session.refresh(t)

    sub = TenantSubscription(
        id=uuid.uuid4(),
        tenant_id=t.id,
        module_code="CSPM",
        is_enabled=True,
        billing_tier="STANDARD",
    )
    db_session.add(sub)
    await db_session.commit()
    return t


@pytest_asyncio.fixture
async def cspm_user(db_session: AsyncSession, cspm_tenant: Tenant) -> User:
    user = User(
        id=uuid.uuid4(),
        email="cspm@urip.test",
        hashed_password=hash_password("Secure#Csp1"),
        full_name="CSPM Admin",
        role="ciso",
        is_active=True,
        tenant_id=cspm_tenant.id,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture
async def cspm_headers(cspm_user: User, cspm_tenant: Tenant) -> dict:
    token = create_access_token(
        str(cspm_user.id),
        cspm_user.role,
        tenant_id=str(cspm_tenant.id),
    )
    return {"Authorization": f"Bearer {token}"}


@pytest_asyncio.fixture
async def no_cspm_headers(db_session: AsyncSession, default_tenant: Tenant) -> dict:
    user = User(
        id=uuid.uuid4(),
        email="no-cspm@urip.test",
        hashed_password=hash_password("Secure#No1"),
        full_name="No CSPM",
        role="ciso",
        is_active=True,
        tenant_id=default_tenant.id,
    )
    db_session.add(user)
    await db_session.commit()
    token = create_access_token(str(user.id), user.role, tenant_id=str(default_tenant.id))
    return {"Authorization": f"Bearer {token}"}


@pytest_asyncio.fixture
async def seeded_cspm_data(db_session: AsyncSession, cspm_tenant: Tenant):
    fw = CspmFramework(
        id=uuid.uuid4(),
        name="CIS AWS Foundations v2.0",
        cloud_provider="aws",
        version="2.0",
    )
    db_session.add(fw)
    await db_session.flush()

    ctrl = CspmControl(
        id=uuid.uuid4(),
        framework_id=fw.id,
        control_code="CIS-AWS-1.1",
        title="Test Control",
        description="Desc",
        severity="high",
        rule_function=None,
    )
    db_session.add(ctrl)
    await db_session.flush()

    result = CspmCheckResult(
        id=uuid.uuid4(),
        tenant_id=cspm_tenant.id,
        control_id=ctrl.id,
        status="fail",
        evidence_json={"test": True},
        run_at=datetime.now(timezone.utc),
        failing_resource_ids=["res-1"],
    )
    db_session.add(result)

    snap = CspmScoreSnapshot(
        id=uuid.uuid4(),
        tenant_id=cspm_tenant.id,
        cloud_provider="aws",
        snapshot_at=datetime.now(timezone.utc),
        score=75.0,
        pass_count=10,
        fail_count=5,
        inconclusive_count=0,
    )
    db_session.add(snap)
    await db_session.commit()
    return {"framework": fw, "control": ctrl, "result": result, "snapshot": snap}


# ---------------------------------------------------------------------------
# Module gate
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_module_gate_blocks_without_cspm(client: AsyncClient, no_cspm_headers: dict):
    resp = await client.get("/api/cspm/score", headers=no_cspm_headers)
    assert resp.status_code == 403
    assert "CSPM" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_module_gate_allows_with_cspm(client: AsyncClient, cspm_headers: dict):
    resp = await client.get("/api/cspm/score", headers=cspm_headers)
    assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Clouds
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_list_cloud_accounts_empty(client: AsyncClient, cspm_headers: dict):
    resp = await client.get("/api/cspm/clouds", headers=cspm_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["items"]) == 3


@pytest.mark.asyncio
async def test_connect_cloud(client: AsyncClient, cspm_headers: dict, cspm_tenant: Tenant):
    resp = await client.post(
        "/api/cspm/clouds",
        json={"credentials": {"provider": "aws", "access_key": "AKIA", "secret_key": "secret", "region": "us-east-1"}},
        headers=cspm_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["connector"] == "aws"


# ---------------------------------------------------------------------------
# Score
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_score(client: AsyncClient, cspm_headers: dict, seeded_cspm_data: dict):
    resp = await client.get("/api/cspm/score", headers=cspm_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["items"]) == 1
    assert body["items"][0]["cloud_provider"] == "aws"
    assert body["items"][0]["score"] == 75.0


@pytest.mark.asyncio
async def test_get_provider_score(client: AsyncClient, cspm_headers: dict, seeded_cspm_data: dict):
    resp = await client.get("/api/cspm/score/aws", headers=cspm_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["cloud_provider"] == "aws"
    assert body["score"] == 75.0


@pytest.mark.asyncio
async def test_get_provider_score_not_found(client: AsyncClient, cspm_headers: dict):
    resp = await client.get("/api/cspm/score/azure", headers=cspm_headers)
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Findings
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_list_findings(client: AsyncClient, cspm_headers: dict, seeded_cspm_data: dict):
    resp = await client.get("/api/cspm/findings", headers=cspm_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 1
    assert body["items"][0]["status"] == "fail"


@pytest.mark.asyncio
async def test_list_findings_filtered(client: AsyncClient, cspm_headers: dict, seeded_cspm_data: dict):
    resp = await client.get("/api/cspm/findings?status=pass", headers=cspm_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 0


@pytest.mark.asyncio
async def test_get_finding_detail(client: AsyncClient, cspm_headers: dict, seeded_cspm_data: dict):
    result_id = str(seeded_cspm_data["result"].id)
    resp = await client.get(f"/api/cspm/findings/{result_id}", headers=cspm_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "fail"
    assert body["failing_resource_ids"] == ["res-1"]


@pytest.mark.asyncio
async def test_get_finding_detail_not_found(client: AsyncClient, cspm_headers: dict):
    resp = await client.get(f"/api/cspm/findings/{uuid.uuid4()}", headers=cspm_headers)
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Trend
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_trend(client: AsyncClient, cspm_headers: dict, seeded_cspm_data: dict):
    resp = await client.get("/api/cspm/trend?days=30", headers=cspm_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 1
    assert body[0]["cloud_provider"] == "aws"
    assert len(body[0]["points"]) == 1


# ---------------------------------------------------------------------------
# Scan now
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_scan_now_no_clouds(client: AsyncClient, cspm_headers: dict):
    resp = await client.post("/api/cspm/scan-now", headers=cspm_headers)
    assert resp.status_code == 400
    assert "No cloud accounts configured" in resp.json()["detail"]
