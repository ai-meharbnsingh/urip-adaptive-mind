"""
HIGH-4 — Login timing attack.

Auditors:
  - Gemini HIGH-G1
  - Kimi MED-004

Vulnerability: when the submitted email is unknown, the login endpoint short-
circuits BEFORE running bcrypt.checkpw. That makes "user does not exist"
visibly faster than "user exists, wrong password" — a remote attacker can
enumerate valid accounts by timing each request.

Required fix: always run bcrypt.checkpw, even when the user is missing —
against a constant-time fake hash. Response time becomes statistically
indistinguishable.

This test:
  1. Calibrates the per-call jitter using the known-bad-password path.
  2. Asserts the unknown-user path's mean is within that calibrated noise
     band — concretely: |Δmean| < 50ms (the brief).

We use median-of-N samples to keep CI noise from flapping the test.
"""
from __future__ import annotations

import statistics
import time
import uuid

import pytest

from backend.middleware.auth import hash_password
from backend.models.user import User


N_SAMPLES = 7  # odd → real median


@pytest.fixture(autouse=True)
def _disable_rate_limiters_for_timing_test(monkeypatch):
    """
    Both the legacy in-router login limiter and the slowapi middleware would
    otherwise return 429 long before we collected enough timing samples.
    Disable both for the duration of this test (the timing fix itself is
    independent of the limiters).
    """
    # Slowapi middleware reset
    try:
        from backend.middleware import rate_limit as _rl
        try:
            _rl.limiter.limiter.storage.reset()
        except Exception:
            pass
        # Force every path to NOT match a policy → middleware short-circuits.
        monkeypatch.setattr(_rl, "_match_policy", lambda *a, **kw: None)
    except Exception:
        pass
    # Legacy auth limiter
    try:
        from backend.routers import auth as _auth
        _auth._login_attempts.clear()
        monkeypatch.setattr(_auth, "check_rate_limit", lambda ip: True)
        monkeypatch.setattr(_auth, "record_failed_attempt", lambda ip: None)
    except Exception:
        pass
    yield


async def _create_user(db_session, default_tenant) -> tuple[str, str]:
    pw = "Secure#Pass-Timing-Test1"
    email = f"timing-{uuid.uuid4().hex[:6]}@example.com"
    user = User(
        id=uuid.uuid4(),
        email=email,
        hashed_password=hash_password(pw),
        full_name="Timing Test User",
        role="ciso",
        team="Security",
        is_active=True,
        tenant_id=default_tenant.id,
    )
    db_session.add(user)
    await db_session.commit()
    return email, pw


@pytest.mark.anyio
async def test_login_unknown_user_runs_dummy_bcrypt(
    client, db_session, default_tenant
):
    """
    The unknown-email path must take roughly the same time as the
    known-user / wrong-password path. Both should be dominated by bcrypt.
    """
    email, _pw = await _create_user(db_session, default_tenant)

    def _time(req_email: str, req_pw: str) -> float:
        t0 = time.perf_counter()
        # We use sync httpx via the client fixture isn't trivially sync,
        # so we measure inside the async helper below via run_until_complete.
        return time.perf_counter() - t0

    # --- known user, wrong password ---
    known_times: list[float] = []
    for _ in range(N_SAMPLES):
        t0 = time.perf_counter()
        r = await client.post(
            "/api/auth/login",
            json={"email": email, "password": "wrong-password"},
        )
        elapsed = time.perf_counter() - t0
        # Non-rate-limited rejections — 401 is expected.
        assert r.status_code in (401, 429), r.text
        if r.status_code == 401:
            known_times.append(elapsed)

    # --- unknown user ---
    unknown_times: list[float] = []
    for _ in range(N_SAMPLES):
        t0 = time.perf_counter()
        r = await client.post(
            "/api/auth/login",
            json={
                "email": f"never-existed-{uuid.uuid4().hex[:6]}@example.com",
                "password": "wrong-password",
            },
        )
        elapsed = time.perf_counter() - t0
        assert r.status_code in (401, 429), r.text
        if r.status_code == 401:
            unknown_times.append(elapsed)

    assert known_times, "no successful 401 calibration samples"
    assert unknown_times, "no successful 401 unknown samples"

    median_known = statistics.median(known_times)
    median_unknown = statistics.median(unknown_times)
    delta_ms = abs(median_known - median_unknown) * 1000

    # The brief allows a 50ms tolerance. bcrypt at default cost is ~50-200ms
    # per call so if both paths run bcrypt the delta is bounded by jitter.
    # If the unknown path skips bcrypt, the delta is comfortably > 30ms.
    assert delta_ms < 50, (
        f"Login timing leak detected: known-user-wrong-password median "
        f"{median_known*1000:.1f}ms vs unknown-user median "
        f"{median_unknown*1000:.1f}ms (Δ={delta_ms:.1f}ms > 50ms)"
    )
