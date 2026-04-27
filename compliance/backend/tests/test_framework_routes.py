"""
TDD — framework API route tests.

Tests written BEFORE the router implementation.
Requires auth token to access protected routes.
"""
import time
import pytest
from jose import jwt
from sqlalchemy import select

from compliance_backend.models.framework import Framework, FrameworkVersion, Control
from compliance_backend.seeders.soc2 import seed_soc2
from compliance_backend.seeders.iso27001 import seed_iso27001


STANDALONE_SECRET = "test-secret-standalone"


def _auth_headers() -> dict:
    payload = {
        "sub": "user-123",
        "tenant_id": "tenant-abc",
        "role": "admin",
        "exp": int(time.time()) + 3600,
        "iss": "compliance",
    }
    token = jwt.encode(payload, STANDALONE_SECRET, algorithm="HS256")
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.anyio
async def test_get_frameworks_returns_list(client, db_session):
    """GET /frameworks returns a JSON list."""
    await seed_soc2(db_session)
    await seed_iso27001(db_session)
    await db_session.commit()

    response = await client.get("/frameworks", headers=_auth_headers())
    assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
    body = response.json()
    assert isinstance(body, list), f"Expected list, got {type(body)}"


@pytest.mark.anyio
async def test_get_frameworks_includes_soc2_and_iso27001(client, db_session):
    """GET /frameworks returns at least SOC 2 and ISO 27001."""
    await seed_soc2(db_session)
    await seed_iso27001(db_session)
    await db_session.commit()

    response = await client.get("/frameworks", headers=_auth_headers())
    assert response.status_code == 200
    body = response.json()
    short_codes = [f["short_code"] for f in body]
    assert "SOC2" in short_codes, f"SOC2 not in frameworks: {short_codes}"
    assert "ISO27001" in short_codes, f"ISO27001 not in frameworks: {short_codes}"


@pytest.mark.anyio
async def test_get_framework_by_short_code(client, db_session):
    """GET /frameworks/SOC2 returns framework detail with current version."""
    await seed_soc2(db_session)
    await db_session.commit()

    response = await client.get("/frameworks/SOC2", headers=_auth_headers())
    assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
    body = response.json()
    assert body["short_code"] == "SOC2"
    assert "current_version" in body, "Response must include current_version"


@pytest.mark.anyio
async def test_get_framework_not_found(client):
    """GET /frameworks/UNKNOWN returns 404."""
    response = await client.get("/frameworks/UNKNOWN_FRAMEWORK_XYZ", headers=_auth_headers())
    assert response.status_code == 404, f"Expected 404, got {response.status_code}"


@pytest.mark.anyio
async def test_get_soc2_controls_is_paginated(client, db_session):
    """GET /frameworks/SOC2/controls returns paginated response."""
    await seed_soc2(db_session)
    await db_session.commit()

    response = await client.get("/frameworks/SOC2/controls", headers=_auth_headers())
    assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
    body = response.json()
    # Expect pagination envelope
    assert "items" in body, f"Expected 'items' key, got keys: {list(body.keys())}"
    assert "total" in body, f"Expected 'total' key, got keys: {list(body.keys())}"
    assert "page" in body or "skip" in body or "offset" in body, (
        f"Expected pagination info in response, got: {list(body.keys())}"
    )


@pytest.mark.anyio
async def test_get_soc2_controls_has_at_least_30(client, db_session):
    """GET /frameworks/SOC2/controls total must be >= 30."""
    await seed_soc2(db_session)
    await db_session.commit()

    response = await client.get("/frameworks/SOC2/controls?limit=100", headers=_auth_headers())
    assert response.status_code == 200
    body = response.json()
    assert body["total"] >= 30, f"Expected >= 30 controls, got {body['total']}"


@pytest.mark.anyio
async def test_controls_filter_by_category(client, db_session):
    """GET /frameworks/SOC2/controls?category=Security returns only Security controls."""
    await seed_soc2(db_session)
    await db_session.commit()

    response = await client.get(
        "/frameworks/SOC2/controls?category=Security&limit=100",
        headers=_auth_headers(),
    )
    assert response.status_code == 200
    body = response.json()
    for item in body["items"]:
        assert item["category"] == "Security", (
            f"Filter by category=Security returned non-Security control: {item}"
        )
