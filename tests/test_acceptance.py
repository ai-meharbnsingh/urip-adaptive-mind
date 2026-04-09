"""Tests for /api/acceptance endpoints (create, approve, reject, duplicate)."""

import pytest
from httpx import AsyncClient

from backend.models.risk import Risk


@pytest.mark.asyncio
async def test_create_acceptance(
    client: AsyncClient, it_team_headers, auth_headers, seeded_risks
):
    """POST /api/acceptance creates a pending acceptance request."""
    risk_id = seeded_risks[0].risk_id

    resp = await client.post("/api/acceptance", headers=it_team_headers, json={
        "risk_id": risk_id,
        "justification": "Legacy system, compensating controls in place",
        "compensating_controls": ["Network segmentation", "IDS monitoring"],
        "residual_risk": "Low — isolated environment",
    })
    assert resp.status_code == 200

    body = resp.json()
    assert body["status"] == "pending"
    assert body["justification"] == "Legacy system, compensating controls in place"
    assert body["residual_risk"] == "Low — isolated environment"
    assert body["id"] is not None
    assert body["requested_by"] is not None


@pytest.mark.asyncio
async def test_approve_acceptance(
    client: AsyncClient, it_team_headers, auth_headers, seeded_risks, db_session
):
    """Approving acceptance changes status to approved and risk to accepted."""
    risk_id = seeded_risks[2].risk_id

    # Create the request (IT team)
    create_resp = await client.post("/api/acceptance", headers=it_team_headers, json={
        "risk_id": risk_id,
        "justification": "Acceptable per business risk assessment",
    })
    assert create_resp.status_code == 200
    acceptance_id = create_resp.json()["id"]

    # Approve (CISO)
    approve_resp = await client.post(
        f"/api/acceptance/{acceptance_id}/approve",
        headers=auth_headers,
    )
    assert approve_resp.status_code == 200
    assert approve_resp.json()["status"] == "approved"
    assert approve_resp.json()["acceptance_id"] == acceptance_id

    # Verify risk status changed to "accepted"
    risk_resp = await client.get(f"/api/risks/{risk_id}", headers=auth_headers)
    assert risk_resp.status_code == 200
    assert risk_resp.json()["risk"]["status"] == "accepted"


@pytest.mark.asyncio
async def test_reject_acceptance(
    client: AsyncClient, it_team_headers, auth_headers, seeded_risks
):
    """Rejecting acceptance changes status to rejected."""
    risk_id = seeded_risks[3].risk_id

    # Create the request
    create_resp = await client.post("/api/acceptance", headers=it_team_headers, json={
        "risk_id": risk_id,
        "justification": "Not critical enough to remediate",
    })
    assert create_resp.status_code == 200
    acceptance_id = create_resp.json()["id"]

    # Reject (CISO)
    reject_resp = await client.post(
        f"/api/acceptance/{acceptance_id}/reject",
        headers=auth_headers,
        json={"reason": "CVSS too high to accept without board approval"},
    )
    assert reject_resp.status_code == 200
    assert reject_resp.json()["status"] == "rejected"
    assert reject_resp.json()["acceptance_id"] == acceptance_id


@pytest.mark.asyncio
async def test_duplicate_acceptance(
    client: AsyncClient, it_team_headers, auth_headers, seeded_risks
):
    """Creating a second acceptance for the same risk returns 409."""
    risk_id = seeded_risks[4].risk_id

    # First request succeeds
    resp1 = await client.post("/api/acceptance", headers=it_team_headers, json={
        "risk_id": risk_id,
        "justification": "First request",
    })
    assert resp1.status_code == 200

    # Second request for same risk returns 409
    resp2 = await client.post("/api/acceptance", headers=it_team_headers, json={
        "risk_id": risk_id,
        "justification": "Duplicate request",
    })
    assert resp2.status_code == 409
    assert "already exists" in resp2.json()["detail"].lower()
