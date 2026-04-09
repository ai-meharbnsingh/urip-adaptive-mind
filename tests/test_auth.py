"""Tests for /api/auth endpoints (login + /me)."""

import pytest
from httpx import AsyncClient

from backend.middleware.auth import hash_password
from backend.models.user import User


@pytest.mark.asyncio
async def test_login_success(client: AsyncClient, db_session, auth_headers):
    """Valid credentials return a JWT and user profile."""
    # The CISO user was already created by auth_headers fixture
    resp = await client.post("/api/auth/login", json={
        "email": "ciso@urip.test",
        "password": "Secure#Pass1",
    })
    assert resp.status_code == 200

    body = resp.json()
    assert "access_token" in body
    assert body["token_type"] == "bearer"
    assert body["user"]["email"] == "ciso@urip.test"
    assert body["user"]["role"] == "ciso"
    assert body["user"]["full_name"] == "Test CISO"


@pytest.mark.asyncio
async def test_login_wrong_password(client: AsyncClient, db_session, auth_headers):
    """Wrong password returns 401."""
    resp = await client.post("/api/auth/login", json={
        "email": "ciso@urip.test",
        "password": "WrongPassword",
    })
    assert resp.status_code == 401
    assert resp.json()["detail"] == "Invalid email or password"


@pytest.mark.asyncio
async def test_login_nonexistent_user(client: AsyncClient, db_session):
    """Email that does not exist returns 401."""
    resp = await client.post("/api/auth/login", json={
        "email": "nobody@urip.test",
        "password": "anything",
    })
    assert resp.status_code == 401
    assert resp.json()["detail"] == "Invalid email or password"


@pytest.mark.asyncio
async def test_get_me(client: AsyncClient, auth_headers):
    """GET /me with valid token returns the user profile."""
    resp = await client.get("/api/auth/me", headers=auth_headers)
    assert resp.status_code == 200

    body = resp.json()
    assert body["email"] == "ciso@urip.test"
    assert body["role"] == "ciso"
    assert body["full_name"] == "Test CISO"
    assert body["team"] == "Security"


@pytest.mark.asyncio
async def test_get_me_no_token(client: AsyncClient):
    """GET /me without Authorization header returns 403 (HTTPBearer)."""
    resp = await client.get("/api/auth/me")
    assert resp.status_code == 403
