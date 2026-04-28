"""
CrowdStrike RTR OAuth2 client-credentials flow — unit tests.

These tests pin the fix for the audit finding that the previous executor
shipped Basic-encoded ``client_id:client_secret`` to the RTR endpoints
directly. CrowdStrike Falcon requires a Bearer access token obtained from
``/oauth2/token`` — the previous shape returned HTTP 401 in production.

We validate:
  1. Token exchange happens BEFORE the first RTR API call.
  2. Token is reused within its TTL (no double exchange).
  3. Token is refreshed when expired (cache invalidates correctly).
  4. OAuth2 failure raises ConnectorAuthError; secret is never leaked
     into the exception message.
  5. The RTR endpoints receive ``Authorization: Bearer <token>`` —
     never ``Basic …``.

All HTTP traffic is mocked via ``respx``; no real Falcon API contact.
"""
from __future__ import annotations

import dataclasses
import time

import httpx
import pytest
import respx

from backend.services.auto_remediation.crowdstrike_rtr import (
    CrowdStrikeRTRExecutor,
)
from connectors.base.connector import ConnectorAuthError


BASE = "https://api.crowdstrike.com"


@dataclasses.dataclass
class FakeRisk:
    risk_id: str = "RISK-OAUTH-1"
    asset: str = "device-77"
    cve_id: str = "CVE-2025-9999"
    finding: str = "OAuth2 test"
    source: str = "crowdstrike"
    indicator_value: str | None = None


def _ok_token_response(token: str = "access-tok-123", expires_in: int = 1799):
    return httpx.Response(
        200,
        json={
            "access_token": token,
            "expires_in": expires_in,
            "token_type": "bearer",
        },
    )


def _ok_session_response():
    return httpx.Response(201, json={"resources": [{"session_id": "sess-A"}]})


def _ok_command_response():
    return httpx.Response(201, json={"resources": [{"task_id": "t-A"}]})


# --------------------------------------------------------------------------- #
# 1. Token exchange happens BEFORE the first RTR API call.
# --------------------------------------------------------------------------- #
@respx.mock
def test_oauth2_token_exchange_happens_before_first_api_call():
    """The very first thing on the wire must be POST /oauth2/token —
    not a session POST."""
    call_order: list[str] = []

    def token_side_effect(request: httpx.Request) -> httpx.Response:
        call_order.append("token")
        return _ok_token_response()

    def session_side_effect(request: httpx.Request) -> httpx.Response:
        call_order.append("session")
        return _ok_session_response()

    def cmd_side_effect(request: httpx.Request) -> httpx.Response:
        call_order.append("command")
        return _ok_command_response()

    respx.post(f"{BASE}/oauth2/token").mock(side_effect=token_side_effect)
    respx.post(
        f"{BASE}/real-time-response/entities/sessions/v1"
    ).mock(side_effect=session_side_effect)
    respx.post(
        f"{BASE}/real-time-response/entities/admin-command/v1"
    ).mock(side_effect=cmd_side_effect)

    ex = CrowdStrikeRTRExecutor(
        base_url=BASE, client_id="cid", client_secret="csecret"
    )
    result = ex.execute(FakeRisk(), dry_run=False)
    assert result.success
    # The exact ordering: token exchange first, then session, then command.
    assert call_order == ["token", "session", "command"], call_order


# --------------------------------------------------------------------------- #
# 2. Token reused within TTL — only one token exchange across two calls.
# --------------------------------------------------------------------------- #
@respx.mock
def test_token_reused_within_ttl():
    """Two RTR executions back-to-back should trigger exactly one
    /oauth2/token POST."""
    token_route = respx.post(f"{BASE}/oauth2/token").mock(
        return_value=_ok_token_response(expires_in=1799)
    )
    respx.post(
        f"{BASE}/real-time-response/entities/sessions/v1"
    ).mock(return_value=_ok_session_response())
    respx.post(
        f"{BASE}/real-time-response/entities/admin-command/v1"
    ).mock(return_value=_ok_command_response())

    # Inject our own httpx.Client so the cache survives across both
    # execute() calls (otherwise close_after=True would close it).
    client = httpx.Client(timeout=5.0)
    ex = CrowdStrikeRTRExecutor(
        base_url=BASE,
        client_id="cid",
        client_secret="csecret",
        client=client,
    )
    r1 = ex.execute(FakeRisk(), dry_run=False)
    r2 = ex.execute(FakeRisk(asset="device-78"), dry_run=False)
    client.close()

    assert r1.success and r2.success
    assert token_route.call_count == 1, (
        f"expected exactly 1 /oauth2/token POST across 2 executions; "
        f"got {token_route.call_count}"
    )


# --------------------------------------------------------------------------- #
# 3. Token refreshed when expired.
# --------------------------------------------------------------------------- #
@respx.mock
def test_token_refreshed_when_expired():
    """If we manually expire the cached token, the next call must
    trigger a fresh /oauth2/token POST."""
    token_route = respx.post(f"{BASE}/oauth2/token").mock(
        return_value=_ok_token_response(token="tok-refreshed")
    )
    respx.post(
        f"{BASE}/real-time-response/entities/sessions/v1"
    ).mock(return_value=_ok_session_response())
    respx.post(
        f"{BASE}/real-time-response/entities/admin-command/v1"
    ).mock(return_value=_ok_command_response())

    client = httpx.Client(timeout=5.0)
    ex = CrowdStrikeRTRExecutor(
        base_url=BASE,
        client_id="cid",
        client_secret="csecret",
        client=client,
    )
    # Pre-seed an expired token.
    ex._access_token = "stale-token"
    ex._token_expires_at = time.time() - 10  # 10s in the past

    r = ex.execute(FakeRisk(), dry_run=False)
    client.close()

    assert r.success
    # Exactly one /oauth2/token POST happened — proving the stale
    # cache was invalidated and a refresh was triggered.
    assert token_route.call_count == 1
    # And the new token is what was cached.
    assert ex._access_token == "tok-refreshed"


# --------------------------------------------------------------------------- #
# 4. OAuth2 failure raises ConnectorAuthError; secret never leaked.
# --------------------------------------------------------------------------- #
@respx.mock
def test_oauth2_failure_raises_ConnectorAuthError():
    """Non-200 from /oauth2/token must surface as ConnectorAuthError,
    and the client_secret value must NOT appear in the exception text."""
    SECRET = "S3CRET-DO-NOT-LEAK"
    respx.post(f"{BASE}/oauth2/token").mock(
        return_value=httpx.Response(
            401,
            # Simulate a server that echoes the secret back in error text —
            # we must scrub it before raising.
            text=f"Unauthorized: bad client_secret={SECRET}",
        )
    )

    client = httpx.Client(timeout=5.0)
    ex = CrowdStrikeRTRExecutor(
        base_url=BASE,
        client_id="cid",
        client_secret=SECRET,
        client=client,
    )

    with pytest.raises(ConnectorAuthError) as exc_info:
        ex._fetch_oauth2_token(client)
    client.close()

    msg = str(exc_info.value)
    assert "401" in msg
    assert SECRET not in msg, (
        f"client_secret leaked into ConnectorAuthError message: {msg!r}"
    )


# --------------------------------------------------------------------------- #
# 5. Bearer header on RTR calls (NEVER Basic).
# --------------------------------------------------------------------------- #
@respx.mock
def test_bearer_header_sent_on_rtr_calls():
    """The Authorization header on RTR calls must be 'Bearer <token>',
    never 'Basic …' (the audit finding being fixed)."""
    captured_auth: dict[str, str] = {}

    def token_se(request: httpx.Request) -> httpx.Response:
        return _ok_token_response(token="THE-BEARER-TOKEN")

    def session_se(request: httpx.Request) -> httpx.Response:
        captured_auth["session"] = request.headers.get("Authorization", "")
        return _ok_session_response()

    def cmd_se(request: httpx.Request) -> httpx.Response:
        captured_auth["command"] = request.headers.get("Authorization", "")
        return _ok_command_response()

    respx.post(f"{BASE}/oauth2/token").mock(side_effect=token_se)
    respx.post(
        f"{BASE}/real-time-response/entities/sessions/v1"
    ).mock(side_effect=session_se)
    respx.post(
        f"{BASE}/real-time-response/entities/admin-command/v1"
    ).mock(side_effect=cmd_se)

    ex = CrowdStrikeRTRExecutor(
        base_url=BASE, client_id="cid", client_secret="csecret"
    )
    result = ex.execute(FakeRisk(), dry_run=False)
    assert result.success

    for endpoint, header in captured_auth.items():
        assert header == "Bearer THE-BEARER-TOKEN", (
            f"{endpoint} got Authorization={header!r} — expected Bearer"
        )
        assert not header.lower().startswith("basic "), (
            f"{endpoint} sent Basic auth — the regression we're fixing!"
        )
