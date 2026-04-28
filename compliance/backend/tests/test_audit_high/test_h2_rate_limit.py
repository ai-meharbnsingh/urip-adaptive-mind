"""
HIGH-2 — Compliance backend rate limiting.

Auditors:
  - Kimi HIGH-003 (no rate limiting on compliance side)
  - Claude HIGH-A

Required behaviour:
  - The compliance FastAPI app installs a slowapi-backed limiter.
  - Auth-shaped endpoints (POST /auditor-invitations/accept) → 5/min/IP.
    The 6th attempt within the same minute returns 429.
  - Generic writes (POST/PUT/PATCH/DELETE) → 60/min/IP.
"""
from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _trust_test_client_proxy(monkeypatch):
    """Force the limiter to treat the test client as a trusted proxy + reset."""
    monkeypatch.setenv("TRUSTED_PROXY_IPS", "*")
    try:
        from compliance_backend.middleware import rate_limit as _rl
        try:
            _rl.limiter.limiter.storage.reset()
        except Exception:
            # Some storages don't expose reset(); clear the inner dicts directly.
            for attr in ("storage", "events", "expirations", "locks"):
                bucket = getattr(_rl.limiter.limiter.storage, attr, None)
                if bucket is not None and hasattr(bucket, "clear"):
                    try:
                        bucket.clear()
                    except Exception:
                        pass
    except Exception:
        pass
    yield


# ---------------------------------------------------------------------------
# /auditor-invitations/accept — auth-shape endpoint, 5/min cap.
# ---------------------------------------------------------------------------

@pytest.mark.anyio
async def test_accept_endpoint_capped_at_five_per_minute(client):
    """
    The 6th POST /auditor-invitations/accept from the same IP within a minute
    must return 429. We send a deliberately bad token — earlier hits return
    401, the 6th hits the rate limiter first.
    """
    headers = {"X-Forwarded-For": "203.0.113.10"}
    body = {"token": "definitely-not-valid"}
    statuses = []
    for _ in range(6):
        r = await client.post(
            "/auditor-invitations/accept", json=body, headers=headers
        )
        statuses.append(r.status_code)
    # First 5 are 401 (bad token); the 6th must be 429 (rate-limited).
    assert statuses[:5] == [401] * 5, statuses
    assert statuses[5] == 429, f"6th attempt expected 429, got {statuses[5]}"


@pytest.mark.anyio
async def test_distinct_real_ips_get_independent_buckets(client):
    """Two different X-Forwarded-For values share separate per-IP buckets."""
    body = {"token": "definitely-not-valid"}

    # Exhaust IP A
    for _ in range(5):
        r = await client.post(
            "/auditor-invitations/accept",
            json=body,
            headers={"X-Forwarded-For": "203.0.113.20"},
        )
        assert r.status_code == 401

    r6_a = await client.post(
        "/auditor-invitations/accept",
        json=body,
        headers={"X-Forwarded-For": "203.0.113.20"},
    )
    assert r6_a.status_code == 429

    # IP B should still be allowed
    r_b = await client.post(
        "/auditor-invitations/accept",
        json=body,
        headers={"X-Forwarded-For": "203.0.113.21"},
    )
    assert r_b.status_code == 401


# ---------------------------------------------------------------------------
# Generic write cap — exercised against the same accept endpoint.
# We can't easily fire 60+ different writes here (most other writes need auth),
# so the per-minute cap above is the strongest auth-path assertion.
# This smoke test confirms the limiter doesn't accidentally cap GET requests.
# ---------------------------------------------------------------------------

@pytest.mark.anyio
async def test_get_health_is_not_rate_limited(client):
    """GET /health must NOT be rate-limited (it's a liveness probe)."""
    headers = {"X-Forwarded-For": "203.0.113.30"}
    for _ in range(20):
        r = await client.get("/health", headers=headers)
        assert r.status_code == 200, r.text
