"""Tests for RBAC enforcement across endpoints.

Role hierarchy: board(0) < executive(1) < it_team(2) < ciso(3).
"""

import uuid

import pytest
from httpx import AsyncClient

from backend.middleware.auth import create_access_token, hash_password
from backend.models.user import User


# ---------------------------------------------------------------------------
# Helpers — create users with specific roles and return their auth headers
# ---------------------------------------------------------------------------

async def _make_user(db_session, role: str, email: str) -> dict[str, str]:
    user = User(
        id=uuid.uuid4(),
        email=email,
        hashed_password=hash_password("Pass#1234"),
        full_name=f"Test {role.title()}",
        role=role,
        team="General",
        is_active=True,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    token = create_access_token(str(user.id), user.role)
    return {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_ciso_can_approve_acceptance(
    client: AsyncClient, auth_headers, it_team_headers, seeded_risks, db_session
):
    """CISO (level 3) can approve acceptance requests."""
    risk_id = seeded_risks[0].risk_id

    # IT team creates the acceptance request
    create_resp = await client.post("/api/acceptance", headers=it_team_headers, json={
        "risk_id": risk_id,
        "justification": "Low business impact, compensating controls in place",
        "compensating_controls": ["WAF rule", "rate limiting"],
        "residual_risk": "Minimal",
    })
    assert create_resp.status_code == 200
    acceptance_id = create_resp.json()["id"]

    # CISO approves
    approve_resp = await client.post(
        f"/api/acceptance/{acceptance_id}/approve",
        headers=auth_headers,
    )
    assert approve_resp.status_code == 200
    assert approve_resp.json()["status"] == "approved"


@pytest.mark.asyncio
async def test_it_team_cannot_approve(
    client: AsyncClient, it_team_headers, auth_headers, seeded_risks, db_session
):
    """IT team (level 2) cannot approve acceptance — requires CISO (level 3)."""
    risk_id = seeded_risks[1].risk_id

    # IT team creates the request
    create_resp = await client.post("/api/acceptance", headers=it_team_headers, json={
        "risk_id": risk_id,
        "justification": "Known issue with mitigating controls",
    })
    assert create_resp.status_code == 200
    acceptance_id = create_resp.json()["id"]

    # IT team tries to approve — should fail
    approve_resp = await client.post(
        f"/api/acceptance/{acceptance_id}/approve",
        headers=it_team_headers,
    )
    assert approve_resp.status_code == 403
    assert "insufficient" in approve_resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_executive_cannot_create_risk(client: AsyncClient, db_session, seeded_risks):
    """Executive (level 1) cannot create risks — requires it_team (level 2)."""
    exec_headers = await _make_user(db_session, "executive", "exec@urip.test")

    resp = await client.post("/api/risks", headers=exec_headers, json={
        "finding": "Should be blocked",
        "source": "vapt",
        "domain": "network",
        "cvss_score": 5.0,
        "severity": "medium",
        "asset": "test.urip.test",
        "owner_team": "Infra",
    })
    assert resp.status_code == 403
    assert "insufficient" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_board_read_only(client: AsyncClient, db_session, seeded_risks, auth_headers):
    """Board (level 0) can read dashboard but cannot create risks."""
    board_headers = await _make_user(db_session, "board", "board@urip.test")

    # Board CAN read the dashboard
    kpi_resp = await client.get("/api/dashboard/kpis", headers=board_headers)
    assert kpi_resp.status_code == 200
    assert "total_open" in kpi_resp.json()

    # Board CANNOT create a risk (requires it_team, level 2)
    create_resp = await client.post("/api/risks", headers=board_headers, json={
        "finding": "Board should not create",
        "source": "easm",
        "domain": "cloud",
        "cvss_score": 4.0,
        "severity": "medium",
        "asset": "board.urip.test",
        "owner_team": "Infra",
    })
    assert create_resp.status_code == 403
