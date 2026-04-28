"""Tests for /api/remediation endpoints (list, create, update)."""

import pytest
from httpx import AsyncClient

from backend.models.risk import Risk


@pytest.mark.asyncio
async def test_list_remediation(
    client: AsyncClient, it_team_headers, auth_headers, seeded_risks
):
    """GET /api/remediation returns paginated task list."""
    # Create a task first so the list is not empty
    risk_id = seeded_risks[0].risk_id
    await client.post("/api/remediation", headers=it_team_headers, json={
        "risk_id": risk_id,
        "title": "Patch critical vulnerability",
        "description": "Apply vendor patch to server-01",
        "priority": "high",
    })

    resp = await client.get("/api/remediation", headers=auth_headers)
    assert resp.status_code == 200

    body = resp.json()
    assert "items" in body
    assert "total" in body
    assert "page" in body
    assert body["total"] >= 1

    first_item = body["items"][0]
    assert first_item["title"] == "Patch critical vulnerability"
    assert first_item["status"] == "not_started"
    assert first_item["priority"] == "high"
    # Enriched with risk detail
    assert first_item["risk_detail"] is not None
    assert first_item["risk_detail"]["risk_id"] == risk_id


@pytest.mark.asyncio
async def test_create_remediation(
    client: AsyncClient, it_team_headers, seeded_risks
):
    """POST /api/remediation creates a task linked to a risk."""
    risk_id = seeded_risks[1].risk_id

    resp = await client.post("/api/remediation", headers=it_team_headers, json={
        "risk_id": risk_id,
        "title": "Upgrade TLS to 1.3",
        "description": "Current servers use TLS 1.2",
        "priority": "medium",
        "jira_key": "SEC-1234",
    })
    # 201 Created — see ENDPOINT_AUDIT.md criterion #7.
    assert resp.status_code == 201

    body = resp.json()
    assert body["title"] == "Upgrade TLS to 1.3"
    assert body["status"] == "not_started"
    assert body["priority"] == "medium"
    assert body["jira_key"] == "SEC-1234"
    assert body["risk_id"] is not None
    assert body["completed_at"] is None


@pytest.mark.asyncio
async def test_update_remediation_status(
    client: AsyncClient, it_team_headers, seeded_risks
):
    """PATCH /api/remediation/{id} marks task completed with timestamp."""
    risk_id = seeded_risks[2].risk_id

    # Create task
    create_resp = await client.post("/api/remediation", headers=it_team_headers, json={
        "risk_id": risk_id,
        "title": "Deploy WAF rules",
        "priority": "high",
    })
    assert create_resp.status_code == 201
    task_id = create_resp.json()["id"]

    # Update to in_progress
    progress_resp = await client.patch(
        f"/api/remediation/{task_id}", headers=it_team_headers,
        json={"status": "in_progress"},
    )
    assert progress_resp.status_code == 200
    assert progress_resp.json()["status"] == "in_progress"
    assert progress_resp.json()["completed_at"] is None

    # Update to completed
    complete_resp = await client.patch(
        f"/api/remediation/{task_id}", headers=it_team_headers,
        json={"status": "completed"},
    )
    assert complete_resp.status_code == 200
    assert complete_resp.json()["status"] == "completed"
    assert complete_resp.json()["completed_at"] is not None
