"""
HIGH-009 — Rate limiting broken behind reverse proxy.

Vulnerabilities:
    1. The legacy in-router rate limiter keys by request.client.host. When the
       app sits behind a reverse proxy (nginx, cloudflare, vercel) every
       request reports the proxy's IP — so all attackers share one bucket and
       the limiter is effectively global, not per-IP.
    2. Unbounded write/read endpoints with no per-user/per-IP cap.

Required behaviour:
    - A global slowapi Limiter is registered on the app.
    - The IP key extractor honours `X-Forwarded-For` when the immediate peer
      is in a trusted proxy list (TRUSTED_PROXY_IPS env var). The leftmost
      address in `X-Forwarded-For` is treated as the real client.
    - When the immediate peer is NOT trusted, X-Forwarded-For is ignored
      (otherwise spoofable from the public internet).
    - /api/auth/login is limited to 5 requests per minute per real-client IP.
      The 6th attempt within the same window → 429.

These tests use the in-process FastAPI test client. We force `TRUSTED_PROXY_IPS`
to "*" so the test client (peer = 127.0.0.1) is trusted; this lets us inject
distinct X-Forwarded-For headers and confirm they are honoured per real client.
"""
from __future__ import annotations

import os
import uuid

import pytest
from httpx import AsyncClient


@pytest.fixture(autouse=True)
def _trust_test_client_proxy(monkeypatch):
    """
    For these tests, treat the local test client as a trusted proxy so we can
    drive the X-Forwarded-For path. In real deployments this would be set to
    the explicit nginx / cloudflare egress range.

    Also resets:
      - the new middleware's in-memory storage (so each test sees a fresh
        bucket regardless of order),
      - the legacy in-router login counter (auth.py keys on
        request.client.host, which is always 127.0.0.1 under the test client
        — without this reset earlier tests would exhaust the legacy bucket
        and the new middleware would never even be the one to deny).
    """
    monkeypatch.setenv("TRUSTED_PROXY_IPS", "*")

    # Reset new middleware storage
    from backend.middleware import rate_limit as _rl
    try:
        _rl.limiter.limiter.storage.reset()  # MemoryStorage.reset()
    except Exception:
        # Some storages don't implement reset; best-effort.
        pass

    # Disable the legacy in-router login counter for these tests. The legacy
    # limiter keys on request.client.host, which is always 127.0.0.1 under the
    # in-process test client — that means it would mistakenly flag distinct
    # forwarded IPs as the same "client" and we could not exercise the new
    # middleware's per-real-IP behaviour. The new middleware (the subject of
    # this test) IS the source of truth for HIGH-009; the legacy limiter is
    # left in place for now to give CritFix-A's auth.py rewrite room to land
    # without conflicting edits.
    try:
        from backend.routers import auth as _auth_router
        _auth_router._login_attempts.clear()
        monkeypatch.setattr(
            _auth_router, "check_rate_limit", lambda ip: True
        )
        monkeypatch.setattr(
            _auth_router, "record_failed_attempt", lambda ip: None
        )
    except Exception:
        pass

    yield


def _seed_user_payload() -> dict:
    """Return a payload that will deterministically fail auth (no such user)."""
    return {
        "email": f"nonexistent-{uuid.uuid4().hex[:6]}@urip.test",
        "password": "wrong-password",
    }


@pytest.mark.anyio
async def test_login_rate_limit_per_real_client_ip(client: AsyncClient):
    """
    6th login attempt from the SAME real-client IP within a minute → 429.
    """
    # Use a unique forwarded IP so this test does not share a bucket with
    # earlier tests in the session.
    fwd_ip = f"203.0.113.{(hash('per-ip-1') % 200) + 10}"
    headers = {"X-Forwarded-For": fwd_ip}
    payload = _seed_user_payload()

    # 5 attempts MUST be allowed (status 401 = invalid creds, but not 429)
    for i in range(5):
        resp = await client.post("/api/auth/login", json=payload, headers=headers)
        assert resp.status_code != 429, (
            f"attempt {i + 1}: should not be rate-limited yet, got {resp.status_code}"
        )

    # 6th attempt: must be 429
    resp = await client.post("/api/auth/login", json=payload, headers=headers)
    assert resp.status_code == 429, (
        f"6th attempt within 1 minute should be 429, got {resp.status_code}: {resp.text}"
    )


@pytest.mark.anyio
async def test_login_rate_limit_isolated_per_ip(client: AsyncClient):
    """
    Two distinct real-client IPs maintain separate buckets.
    """
    ip_a = f"203.0.113.{(hash('isolation-a') % 200) + 10}"
    ip_b = f"198.51.100.{(hash('isolation-b') % 200) + 10}"
    payload = _seed_user_payload()

    # Exhaust IP A
    for _ in range(5):
        await client.post(
            "/api/auth/login", json=payload, headers={"X-Forwarded-For": ip_a}
        )
    a_blocked = await client.post(
        "/api/auth/login", json=payload, headers={"X-Forwarded-For": ip_a}
    )
    assert a_blocked.status_code == 429, "IP A should be blocked after 5 attempts"

    # IP B must still get a normal (non-429) response on its first attempt
    b_first = await client.post(
        "/api/auth/login", json=payload, headers={"X-Forwarded-For": ip_b}
    )
    assert b_first.status_code != 429, (
        f"IP B should NOT be blocked — independent bucket; got {b_first.status_code}"
    )


@pytest.mark.anyio
async def test_x_forwarded_for_ignored_when_proxy_not_trusted(monkeypatch, client: AsyncClient):
    """
    If TRUSTED_PROXY_IPS does NOT include the immediate peer, X-Forwarded-For
    must be ignored. Otherwise any internet client could spoof the header to
    bypass the rate limit by rotating fake IPs.
    """
    # Restrict trust to a non-localhost range so 127.0.0.1 is no longer trusted.
    monkeypatch.setenv("TRUSTED_PROXY_IPS", "10.0.0.1")

    # Re-import the rate limiter so it picks up the new env.
    import importlib
    import sys
    if "backend.middleware.rate_limit" in sys.modules:
        importlib.reload(sys.modules["backend.middleware.rate_limit"])

    payload = _seed_user_payload()
    # All attempts arrive from spoofed IPs but the limiter must use
    # request.client.host (= 127.0.0.1) and rate-limit them as one bucket.
    spoofed_ips = [f"203.0.113.{50 + i}" for i in range(10)]
    statuses = []
    for ip in spoofed_ips:
        r = await client.post(
            "/api/auth/login", json=payload, headers={"X-Forwarded-For": ip}
        )
        statuses.append(r.status_code)

    assert 429 in statuses, (
        "When proxy is untrusted, spoofed XFF must NOT bypass the limiter; "
        f"got statuses {statuses}"
    )
