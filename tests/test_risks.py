"""Tests for /api/risks endpoints (CRUD + assign)."""

import pytest
from httpx import AsyncClient

from backend.models.risk import Risk


@pytest.mark.asyncio
async def test_list_risks(client: AsyncClient, auth_headers, seeded_risks):
    """GET /api/risks returns a paginated list of risks."""
    resp = await client.get("/api/risks", headers=auth_headers)
    assert resp.status_code == 200

    body = resp.json()
    assert "items" in body
    assert "total" in body
    assert "page" in body
    assert "pages" in body
    assert body["total"] == 10
    assert body["page"] == 1
    assert len(body["items"]) == 10


@pytest.mark.asyncio
async def test_list_risks_filter_severity(client: AsyncClient, auth_headers, seeded_risks):
    """Filtering by severity returns only matching risks."""
    resp = await client.get("/api/risks?severity=critical", headers=auth_headers)
    assert resp.status_code == 200

    body = resp.json()
    assert body["total"] == 2
    assert len(body["items"]) == 2
    for item in body["items"]:
        assert item["severity"] == "critical"


@pytest.mark.asyncio
async def test_list_risks_search(client: AsyncClient, auth_headers, seeded_risks):
    """Search finds risks by finding text."""
    resp = await client.get("/api/risks?search=vulnerability+%231", headers=auth_headers)
    assert resp.status_code == 200

    body = resp.json()
    # Should match "#1" and "#10"
    assert body["total"] >= 1
    for item in body["items"]:
        assert "#1" in item["finding"]


@pytest.mark.asyncio
async def test_get_risk_detail(client: AsyncClient, auth_headers, seeded_risks):
    """GET /api/risks/{risk_id} returns the risk with history."""
    risk_id = seeded_risks[0].risk_id  # "RISK-2026-001"
    resp = await client.get(f"/api/risks/{risk_id}", headers=auth_headers)
    assert resp.status_code == 200

    body = resp.json()
    assert "risk" in body
    assert "history" in body
    assert body["risk"]["risk_id"] == risk_id
    assert body["risk"]["severity"] == "critical"
    assert isinstance(body["history"], list)


@pytest.mark.asyncio
async def test_get_risk_not_found(client: AsyncClient, auth_headers):
    """Requesting a non-existent risk_id returns 404."""
    resp = await client.get("/api/risks/RISK-9999-999", headers=auth_headers)
    assert resp.status_code == 404
    assert resp.json()["detail"] == "Risk not found"


@pytest.mark.asyncio
async def test_create_risk(client: AsyncClient, it_team_headers, seeded_risks):
    """POST /api/risks creates a new risk with auto-generated risk_id.

    Status 201 (was 200) — see ENDPOINT_AUDIT.md criterion #7 for HTTP semantics.
    """
    resp = await client.post("/api/risks", headers=it_team_headers, json={
        "finding": "New SQL injection in payments API",
        "description": "Parameterized queries not used",
        "source": "vapt",
        "domain": "application",
        "cvss_score": 8.6,
        "severity": "high",
        "asset": "payments-api.prod.urip.test",
        "owner_team": "AppSec",
        "cve_id": "CVE-2026-5555",
    })
    assert resp.status_code == 201

    body = resp.json()
    assert body["risk_id"].startswith("RISK-2026-")
    assert body["finding"] == "New SQL injection in payments API"
    assert body["severity"] == "high"
    assert body["source"] == "vapt"
    assert body["status"] == "open"
    assert body["cve_id"] == "CVE-2026-5555"
    assert body["sla_deadline"] is not None


@pytest.mark.asyncio
async def test_update_risk_status(client: AsyncClient, it_team_headers, seeded_risks):
    """PATCH /api/risks/{risk_id} changes status and creates history entry."""
    risk_id = seeded_risks[0].risk_id
    resp = await client.patch(f"/api/risks/{risk_id}", headers=it_team_headers, json={
        "status": "in_progress",
    })
    assert resp.status_code == 200
    assert resp.json()["status"] == "in_progress"

    # Verify history was created
    detail = await client.get(f"/api/risks/{risk_id}", headers=it_team_headers)
    assert detail.status_code == 200
    history = detail.json()["history"]
    assert len(history) >= 1
    status_change = [h for h in history if h["field_changed"] == "status"]
    assert len(status_change) == 1
    assert status_change[0]["old_value"] == "open"
    assert status_change[0]["new_value"] == "in_progress"


@pytest.mark.asyncio
async def test_assign_risk(client: AsyncClient, it_team_headers, seeded_risks, db_session):
    """POST /api/risks/{risk_id}/assign assigns a user to the risk."""
    # Get the IT user's ID from the token-created user
    from sqlalchemy import select
    from backend.models.user import User

    result = await db_session.execute(select(User).where(User.email == "itlead@urip.test"))
    user = result.scalar_one()

    risk_id = seeded_risks[1].risk_id
    resp = await client.post(f"/api/risks/{risk_id}/assign", headers=it_team_headers, json={
        "user_id": str(user.id),
    })
    assert resp.status_code == 200
    assert resp.json()["assigned_to"] == str(user.id)
