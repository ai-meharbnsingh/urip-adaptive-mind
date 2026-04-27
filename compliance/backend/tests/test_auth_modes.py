"""
TDD — JWT auth mode tests.

Tests written BEFORE the middleware implementation.
"""
import os
import time
import pytest
from jose import jwt


STANDALONE_SECRET = "test-secret-standalone"
URIP_SECRET = "urip-shared-secret-for-test"


def _make_token(secret: str, tenant_id: str = "tenant-abc", role: str = "admin") -> str:
    payload = {
        "sub": "user-123",
        "tenant_id": tenant_id,
        "role": role,
        "exp": int(time.time()) + 3600,
        "iss": "compliance" if secret == STANDALONE_SECRET else "urip",
    }
    return jwt.encode(payload, secret, algorithm="HS256")


def _make_expired_token(secret: str) -> str:
    payload = {
        "sub": "user-123",
        "tenant_id": "tenant-abc",
        "role": "admin",
        "exp": int(time.time()) - 10,
        "iss": "urip",
    }
    return jwt.encode(payload, secret, algorithm="HS256")


# ---------------------------------------------------------------------------
# STANDALONE mode tests (default in conftest — COMPLIANCE_AUTH_MODE=STANDALONE)
# ---------------------------------------------------------------------------

@pytest.mark.anyio
async def test_standalone_accepts_compliance_token(client):
    """STANDALONE mode: own compliance JWT → 200 on a protected route."""
    token = _make_token(STANDALONE_SECRET)
    response = await client.get(
        "/frameworks",
        headers={"Authorization": f"Bearer {token}"},
    )
    # 200 or 404 (no data yet) — both mean auth passed
    assert response.status_code in (200, 404, 422), (
        f"Expected auth to pass (200/404), got {response.status_code}: {response.text}"
    )


@pytest.mark.anyio
async def test_standalone_rejects_urip_token(client):
    """
    STANDALONE mode: a URIP-signed token (different secret) must be rejected.
    If COMPLIANCE_AUTH_MODE=STANDALONE, the service only accepts its own tokens.
    """
    urip_token = _make_token(URIP_SECRET)  # signed with URIP secret, not standalone secret
    response = await client.get(
        "/frameworks",
        headers={"Authorization": f"Bearer {urip_token}"},
    )
    assert response.status_code == 401, (
        f"STANDALONE mode must reject URIP-signed token, got {response.status_code}: {response.text}"
    )


@pytest.mark.anyio
async def test_standalone_rejects_expired_token(client):
    """Expired tokens are always rejected."""
    token = _make_expired_token(STANDALONE_SECRET)
    response = await client.get(
        "/frameworks",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 401, (
        f"Expired token must be rejected, got {response.status_code}"
    )


@pytest.mark.anyio
async def test_missing_token_rejected(client):
    """No Authorization header → 401."""
    response = await client.get("/frameworks")
    assert response.status_code == 401, (
        f"Missing token must return 401, got {response.status_code}"
    )


# ---------------------------------------------------------------------------
# INTEGRATED mode tests — swaps env var + re-imports
# ---------------------------------------------------------------------------

@pytest.mark.anyio
async def test_integrated_mode_accepts_urip_token(monkeypatch):
    """
    INTEGRATED mode: a URIP-signed JWT (shared secret) must be accepted.
    We temporarily switch COMPLIANCE_AUTH_MODE to INTEGRATED.
    """
    import importlib
    from compliance_backend.middleware import auth as auth_mod

    monkeypatch.setenv("COMPLIANCE_AUTH_MODE", "INTEGRATED")
    monkeypatch.setenv("URIP_JWT_SECRET", URIP_SECRET)

    # Re-read settings after env change
    from compliance_backend import config
    importlib.reload(config)
    importlib.reload(auth_mod)

    urip_token = _make_token(URIP_SECRET)
    result = auth_mod.verify_token(urip_token)
    assert result is not None, "INTEGRATED mode must accept URIP-signed token"
    assert result["tenant_id"] == "tenant-abc"

    # Restore
    monkeypatch.setenv("COMPLIANCE_AUTH_MODE", "STANDALONE")
    importlib.reload(config)
    importlib.reload(auth_mod)


@pytest.mark.anyio
async def test_integrated_mode_rejects_compliance_standalone_token(monkeypatch):
    """
    INTEGRATED mode: a token signed with COMPLIANCE_JWT_SECRET (not URIP secret)
    must be rejected.
    """
    import importlib
    from compliance_backend.middleware import auth as auth_mod

    monkeypatch.setenv("COMPLIANCE_AUTH_MODE", "INTEGRATED")
    monkeypatch.setenv("URIP_JWT_SECRET", URIP_SECRET)

    from compliance_backend import config
    importlib.reload(config)
    importlib.reload(auth_mod)

    standalone_token = _make_token(STANDALONE_SECRET)
    with pytest.raises(Exception):
        auth_mod.verify_token(standalone_token)

    # Restore
    monkeypatch.setenv("COMPLIANCE_AUTH_MODE", "STANDALONE")
    importlib.reload(config)
    importlib.reload(auth_mod)
