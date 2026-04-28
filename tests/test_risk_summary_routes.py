"""
Tests for /api/risk-summary REST endpoints.

Covers:
  - GET /api/risk-summary           (latest snapshot, cached)
  - GET /api/risk-summary/trend     (historical, ?days param)
  - POST /api/risk-summary/snapshot (admin/ciso only)
  - Auth enforcement (401 without token)
  - Tenant scoping (snapshots from other tenants not returned)
  - Role gate on POST (403 for it_team, 201 for ciso)

INV-4: Tests actually execute via pytest + httpx AsyncClient.
INV-6: Test expectations never changed to pass.
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from httpx import AsyncClient

from backend.models.risk import Risk
from backend.models.risk_snapshot import RiskScoreSummary
from backend.models.tenant import Tenant
from backend.services import risk_aggregate_service as svc_module


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _risk(tenant_id: uuid.UUID, severity: str = "high") -> Risk:
    now = datetime.now(timezone.utc)
    return Risk(
        id=uuid.uuid4(),
        risk_id=f"RISK-{uuid.uuid4().hex[:6].upper()}",
        finding="Route test finding",
        source="crowdstrike",
        domain="network",
        cvss_score=7.5,
        severity=severity,
        asset="test-server.local",
        owner_team="Security",
        status="open",
        sla_deadline=now + timedelta(days=7),
        tenant_id=tenant_id,
    )


def _snap(tenant_id: uuid.UUID, days_ago: int = 0, total_risks: int = 5) -> RiskScoreSummary:
    return RiskScoreSummary(
        tenant_id=tenant_id,
        snapshot_at=datetime.now(timezone.utc) - timedelta(days=days_ago),
        total_risks=total_risks,
        critical_count=1,
        high_count=2,
        medium_count=1,
        low_count=1,
        info_count=0,
        exploit_active_count=0,
        kev_active_count=0,
        top_sources_json=json.dumps([{"source": "crowdstrike", "count": 5}]),
        module_breakdown_json=json.dumps({"NETWORK": 5}),
    )


# ---------------------------------------------------------------------------
# GET /api/risk-summary
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_latest_no_snapshot_returns_404(
    client: AsyncClient,
    auth_headers: dict,
    vm_subscription,
    default_tenant,
    db_session,
):
    """Returns 404 when no snapshot exists yet for the tenant."""
    # Clear any cached state
    svc_module._cache_invalidate(default_tenant.id)

    resp = await client.get("/api/risk-summary", headers=auth_headers)
    assert resp.status_code == 404
    assert "snapshot" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_get_latest_returns_snapshot(
    client: AsyncClient,
    auth_headers: dict,
    vm_subscription,
    default_tenant,
    db_session,
):
    """Returns the most recent snapshot for the current tenant."""
    svc_module._cache_invalidate(default_tenant.id)

    snap = _snap(default_tenant.id, total_risks=42)
    db_session.add(snap)
    await db_session.commit()
    await db_session.refresh(snap)

    resp = await client.get("/api/risk-summary", headers=auth_headers)
    assert resp.status_code == 200

    body = resp.json()
    assert body["total_risks"] == 42
    assert body["critical_count"] == 1
    assert "snapshot_at" in body
    assert "top_sources" in body
    assert isinstance(body["top_sources"], list)
    assert "module_breakdown" in body
    assert isinstance(body["module_breakdown"], dict)


@pytest.mark.asyncio
async def test_get_latest_requires_auth(client: AsyncClient, vm_subscription):
    """Returns 403 without Authorization header (module gate returns 401/403)."""
    resp = await client.get("/api/risk-summary")
    assert resp.status_code in (401, 403)


@pytest.mark.asyncio
async def test_get_latest_tenant_scoping(
    client: AsyncClient,
    auth_headers: dict,
    vm_subscription,
    default_tenant,
    db_session,
):
    """Only returns the current tenant's snapshot, not another tenant's."""
    svc_module._cache_invalidate(default_tenant.id)

    other_tid = uuid.uuid4()
    # Snapshot for default tenant
    my_snap = _snap(default_tenant.id, total_risks=7)
    # Snapshot for other tenant
    other_snap = _snap(other_tid, total_risks=999)
    db_session.add(my_snap)
    db_session.add(other_snap)
    await db_session.commit()

    resp = await client.get("/api/risk-summary", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["total_risks"] == 7  # NOT 999


# ---------------------------------------------------------------------------
# GET /api/risk-summary/trend
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_trend_returns_ordered_list(
    client: AsyncClient,
    auth_headers: dict,
    vm_subscription,
    default_tenant,
    db_session,
):
    """Returns snapshots ordered oldest-first."""
    for days_ago in [5, 2, 0]:
        db_session.add(_snap(default_tenant.id, days_ago=days_ago, total_risks=days_ago * 10))
    await db_session.commit()

    resp = await client.get("/api/risk-summary/trend?days=30", headers=auth_headers)
    assert resp.status_code == 200

    items = resp.json()
    assert len(items) == 3
    # Oldest first: total_risks 50, 20, 0
    assert items[0]["total_risks"] == 50
    assert items[1]["total_risks"] == 20
    assert items[2]["total_risks"] == 0


@pytest.mark.asyncio
async def test_get_trend_empty(
    client: AsyncClient,
    auth_headers: dict,
    vm_subscription,
    default_tenant,
):
    """Returns empty list when no snapshots exist."""
    resp = await client.get("/api/risk-summary/trend?days=30", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_get_trend_days_param_validation(
    client: AsyncClient,
    auth_headers: dict,
    vm_subscription,
):
    """days=0 is rejected (ge=1 validation)."""
    resp = await client.get("/api/risk-summary/trend?days=0", headers=auth_headers)
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_get_trend_requires_auth(client: AsyncClient, vm_subscription):
    """Returns 401/403 without Authorization header."""
    resp = await client.get("/api/risk-summary/trend")
    assert resp.status_code in (401, 403)


@pytest.mark.asyncio
async def test_get_trend_tenant_scoping(
    client: AsyncClient,
    auth_headers: dict,
    vm_subscription,
    default_tenant,
    db_session,
):
    """Trend only returns snapshots for the current tenant."""
    other_tid = uuid.uuid4()
    db_session.add(_snap(default_tenant.id, total_risks=10))
    db_session.add(_snap(other_tid, total_risks=999))
    await db_session.commit()

    resp = await client.get("/api/risk-summary/trend?days=30", headers=auth_headers)
    assert resp.status_code == 200

    items = resp.json()
    assert len(items) == 1
    assert items[0]["total_risks"] == 10


# ---------------------------------------------------------------------------
# POST /api/risk-summary/snapshot
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_trigger_snapshot_ciso_allowed(
    client: AsyncClient,
    auth_headers: dict,
    vm_subscription,
    default_tenant,
    db_session,
):
    """CISO role can trigger a snapshot — returns 201 with snapshot body."""
    svc_module._cache_invalidate(default_tenant.id)

    # Seed some risks so the snapshot is non-trivial
    for _ in range(3):
        db_session.add(_risk(default_tenant.id, severity="high"))
    await db_session.commit()

    resp = await client.post("/api/risk-summary/snapshot", headers=auth_headers)
    assert resp.status_code == 201

    body = resp.json()
    assert "id" in body
    assert "tenant_id" in body
    assert body["total_risks"] == 3
    assert body["high_count"] == 3
    assert "snapshot_at" in body


@pytest.mark.asyncio
async def test_trigger_snapshot_it_team_forbidden(
    client: AsyncClient,
    it_team_headers: dict,
    vm_subscription,
    default_tenant,
):
    """IT-team role is rejected (role_required('ciso') gate)."""
    resp = await client.post("/api/risk-summary/snapshot", headers=it_team_headers)
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_trigger_snapshot_no_auth(client: AsyncClient, vm_subscription):
    """No auth returns 401/403."""
    resp = await client.post("/api/risk-summary/snapshot")
    assert resp.status_code in (401, 403)


@pytest.mark.asyncio
async def test_trigger_snapshot_idempotent(
    client: AsyncClient,
    auth_headers: dict,
    vm_subscription,
    default_tenant,
    db_session,
):
    """Two consecutive POST requests within the same minute return the same snapshot id."""
    svc_module._cache_invalidate(default_tenant.id)

    resp1 = await client.post("/api/risk-summary/snapshot", headers=auth_headers)
    resp2 = await client.post("/api/risk-summary/snapshot", headers=auth_headers)

    assert resp1.status_code == 201
    assert resp2.status_code == 201
    assert resp1.json()["id"] == resp2.json()["id"]


@pytest.mark.asyncio
async def test_snapshot_response_shape(
    client: AsyncClient,
    auth_headers: dict,
    vm_subscription,
    default_tenant,
):
    """Snapshot response contains all expected keys."""
    svc_module._cache_invalidate(default_tenant.id)

    resp = await client.post("/api/risk-summary/snapshot", headers=auth_headers)
    assert resp.status_code == 201

    body = resp.json()
    required_keys = {
        "id", "tenant_id", "snapshot_at", "total_risks",
        "critical_count", "high_count", "medium_count", "low_count", "info_count",
        "exploit_active_count", "kev_active_count",
        "mean_ttr_hours", "mean_composite_score",
        "top_sources", "module_breakdown", "created_at",
    }
    for key in required_keys:
        assert key in body, f"Missing key: {key}"
