"""
TDD — health endpoint.

Test written BEFORE implementation.
Expected to FAIL until main.py + /health route exists.
"""
import pytest


@pytest.mark.anyio
async def test_health_returns_ok(client):
    response = await client.get("/health")
    assert response.status_code == 200, f"Expected 200, got {response.status_code}"


@pytest.mark.anyio
async def test_health_payload(client):
    response = await client.get("/health")
    body = response.json()
    assert body["status"] == "ok", f"Expected status=ok, got {body}"
    assert body["service"] == "compliance", f"Expected service=compliance, got {body}"


@pytest.mark.anyio
async def test_health_no_auth_required(client):
    """Health endpoint must be reachable without a JWT."""
    response = await client.get("/health")
    assert response.status_code != 401, "Health endpoint must not require auth"
    assert response.status_code != 403, "Health endpoint must not require auth"
