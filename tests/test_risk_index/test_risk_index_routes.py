"""
Tests for /api/risk-index REST endpoints.

Endpoints under test:
  GET /api/risk-index
  GET /api/risk-index/trend
  GET /api/risk-index/subindexes/{name}
  GET /api/risk-index/domains/{name}

Covers:
  - Auth enforcement (401 without token)
  - Module gate (403 when CORE not subscribed)
  - Empty tenant happy-path (score=0, level=low)
  - Populated tenant returns sensible payload shape
  - Tenant scoping (cross-tenant rows excluded)
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from httpx import AsyncClient

from backend.models.risk import Risk
from backend.models.risk_snapshot import RiskScoreSummary


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _risk(
    tenant_id: uuid.UUID,
    severity: str = "high",
    status: str = "open",
    source: str = "crowdstrike",
    domain: str = "network",
    composite_score: float | None = 7.0,
    in_kev_catalog: bool = False,
) -> Risk:
    now = datetime.now(timezone.utc)
    return Risk(
        id=uuid.uuid4(),
        risk_id=f"RISK-IDX-RT-{uuid.uuid4().hex[:6].upper()}",
        finding="Route test finding",
        source=source,
        domain=domain,
        cvss_score=7.5,
        severity=severity,
        asset="server.test",
        owner_team="Security",
        status=status,
        sla_deadline=now + timedelta(days=7),
        tenant_id=tenant_id,
        composite_score=composite_score,
        in_kev_catalog=in_kev_catalog,
    )


# ---------------------------------------------------------------------------
# Auth enforcement
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_risk_index_no_auth_returns_unauthorized(client: AsyncClient):
    """FastAPI's HTTPBearer returns 403 (not 401) when the header is missing —
    follow the existing repo convention used in test_risk_summary_routes."""
    response = await client.get("/api/risk-index")
    assert response.status_code in (401, 403)


@pytest.mark.asyncio
async def test_get_risk_index_trend_no_auth_returns_unauthorized(client: AsyncClient):
    response = await client.get("/api/risk-index/trend")
    assert response.status_code in (401, 403)


# ---------------------------------------------------------------------------
# Module gate (CORE)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_risk_index_without_core_subscription_returns_403(
    client: AsyncClient,
    db_session,
    default_tenant,
):
    """Auth user but no CORE subscription → 403."""
    from backend.middleware.auth import create_access_token, hash_password
    from backend.models.user import User

    user = User(
        id=uuid.uuid4(),
        email="nocore@urip.test",
        hashed_password=hash_password("Secure#Pass1"),
        full_name="No Core",
        role="ciso",
        team="Security",
        is_active=True,
        tenant_id=default_tenant.id,
    )
    db_session.add(user)
    await db_session.commit()

    token = create_access_token(str(user.id), user.role, tenant_id=str(default_tenant.id))
    headers = {"Authorization": f"Bearer {token}"}

    response = await client.get("/api/risk-index", headers=headers)
    assert response.status_code == 403


# ---------------------------------------------------------------------------
# GET /api/risk-index — happy path
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_risk_index_empty_tenant(
    client: AsyncClient,
    auth_headers: dict,
    core_subscription,
    default_tenant,
    db_session,
):
    """Empty tenant returns score=0, level=low, all subindexes & domain buckets zero."""
    response = await client.get("/api/risk-index", headers=auth_headers)
    assert response.status_code == 200
    body = response.json()

    assert body["score"] == 0.0
    assert body["level"] == "low"
    assert body["color_code"] == "green"

    subs = body["subindexes"]
    assert subs["exposure"]["score"] == 0.0
    assert subs["attack"]["score"] == 0.0
    assert subs["security_config"]["score"] == 0.0

    domains = body["domains"]
    assert domains["devices"]["total"] == 0
    assert domains["internet_facing"]["total"] == 0
    assert domains["accounts"]["total"] == 0
    assert domains["applications"]["total"] == 0
    assert domains["cloud_assets"]["total"] == 0


@pytest.mark.asyncio
async def test_get_risk_index_populated_tenant(
    client: AsyncClient,
    auth_headers: dict,
    core_subscription,
    default_tenant,
    db_session,
):
    """Populated tenant returns full payload with all sections."""
    tid = default_tenant.id
    db_session.add(_risk(tid, source="tenable", composite_score=8.0, severity="critical"))
    db_session.add(_risk(tid, source="aws_cspm", composite_score=6.0, severity="high"))
    db_session.add(_risk(tid, source="crowdstrike", composite_score=7.0, severity="high"))
    await db_session.commit()

    response = await client.get("/api/risk-index", headers=auth_headers)
    assert response.status_code == 200
    body = response.json()

    assert body["score"] > 0
    assert body["level"] in ("low", "medium", "high", "critical")
    assert "exposure" in body["subindexes"]
    assert "attack" in body["subindexes"]
    assert "security_config" in body["subindexes"]

    # Each domain has the expected fields
    for d in ("devices", "internet_facing", "accounts", "applications", "cloud_assets"):
        bucket = body["domains"][d]
        assert "total" in bucket
        assert "critical_count" in bucket
        assert "high_count" in bucket
        assert "level" in bucket


# ---------------------------------------------------------------------------
# GET /api/risk-index/trend
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_trend_returns_history(
    client: AsyncClient,
    auth_headers: dict,
    core_subscription,
    default_tenant,
    db_session,
):
    """Trend endpoint returns historical snapshots."""
    tid = default_tenant.id
    now = datetime.now(timezone.utc)
    # Seed two snapshots
    db_session.add(RiskScoreSummary(
        tenant_id=tid,
        snapshot_at=now - timedelta(days=2),
        total_risks=5,
        index_0_100=42.0,
        level="medium",
        subindex_exposure=30.0,
        subindex_attack=20.0,
        subindex_security_config=10.0,
    ))
    db_session.add(RiskScoreSummary(
        tenant_id=tid,
        snapshot_at=now - timedelta(days=1),
        total_risks=8,
        index_0_100=55.0,
        level="medium",
        subindex_exposure=35.0,
        subindex_attack=25.0,
        subindex_security_config=15.0,
    ))
    await db_session.commit()

    response = await client.get("/api/risk-index/trend?days=30", headers=auth_headers)
    assert response.status_code == 200
    body = response.json()

    assert isinstance(body, list)
    assert len(body) == 2
    # Oldest first
    assert body[0]["index_0_100"] == 42.0
    assert body[1]["index_0_100"] == 55.0


# ---------------------------------------------------------------------------
# GET /api/risk-index/subindexes/{name}
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_subindex_drilldown_exposure(
    client: AsyncClient,
    auth_headers: dict,
    core_subscription,
    default_tenant,
    db_session,
):
    """Drill-down returns top contributing risks for a subindex."""
    tid = default_tenant.id
    db_session.add(_risk(tid, source="tenable", composite_score=8.5, severity="critical"))
    db_session.add(_risk(tid, source="easm", composite_score=7.0, severity="high"))
    # A non-exposure risk that should NOT appear
    db_session.add(_risk(tid, source="aws_cspm", composite_score=6.0, severity="medium"))
    await db_session.commit()

    response = await client.get("/api/risk-index/subindexes/exposure", headers=auth_headers)
    assert response.status_code == 200
    body = response.json()

    assert body["name"] == "exposure"
    assert "score" in body
    assert "level" in body
    assert "top_risks" in body
    sources_in_top = {r["source"] for r in body["top_risks"]}
    assert "tenable" in sources_in_top or "easm" in sources_in_top
    # aws_cspm is in security_config, not exposure
    assert "aws_cspm" not in sources_in_top


@pytest.mark.asyncio
async def test_get_subindex_drilldown_invalid_name_returns_400(
    client: AsyncClient,
    auth_headers: dict,
    core_subscription,
    default_tenant,
):
    response = await client.get("/api/risk-index/subindexes/bogus", headers=auth_headers)
    assert response.status_code == 400


# ---------------------------------------------------------------------------
# GET /api/risk-index/domains/{name}
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_domain_drilldown_devices(
    client: AsyncClient,
    auth_headers: dict,
    core_subscription,
    default_tenant,
    db_session,
):
    tid = default_tenant.id
    db_session.add(_risk(tid, source="crowdstrike", composite_score=8.0, severity="critical"))
    db_session.add(_risk(tid, source="sentinelone", composite_score=7.0, severity="high"))
    # Internet facing — should not appear
    db_session.add(_risk(tid, source="easm", composite_score=6.0, severity="medium"))
    await db_session.commit()

    response = await client.get("/api/risk-index/domains/devices", headers=auth_headers)
    assert response.status_code == 200
    body = response.json()

    assert body["name"] == "devices"
    assert "total" in body
    assert "top_risks" in body
    sources = {r["source"] for r in body["top_risks"]}
    assert "easm" not in sources


@pytest.mark.asyncio
async def test_get_domain_drilldown_invalid_name_returns_400(
    client: AsyncClient,
    auth_headers: dict,
    core_subscription,
    default_tenant,
):
    response = await client.get("/api/risk-index/domains/bogus", headers=auth_headers)
    assert response.status_code == 400


# ---------------------------------------------------------------------------
# Tenant isolation at the route layer
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_route_tenant_isolation(
    client: AsyncClient,
    auth_headers: dict,
    core_subscription,
    default_tenant,
    db_session,
):
    """Other tenants' risks must not surface in the dashboard payload."""
    from backend.models.tenant import Tenant
    other = Tenant(
        id=uuid.uuid4(), name="OtherIso", slug="other-iso",
        domain="other-iso.test", is_active=True, settings={},
    )
    db_session.add(other)
    await db_session.commit()

    # Other tenant has 5 KEV criticals
    for _ in range(5):
        db_session.add(_risk(
            other.id, source="tenable", severity="critical",
            composite_score=10.0, in_kev_catalog=True,
        ))
    await db_session.commit()

    # Default tenant is empty — should return 0
    response = await client.get("/api/risk-index", headers=auth_headers)
    assert response.status_code == 200
    body = response.json()
    assert body["score"] == 0.0
    assert body["level"] == "low"
