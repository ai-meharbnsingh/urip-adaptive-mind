"""
Tests for agent/reporter.py — the encrypted reporter.

What we're verifying:
1. Signature correctness  — HMAC equals what the cloud verifier computes.
2. Retry behaviour         — exponential backoff up to max_retries, then raise.
3. NO raw findings ever in payload — recursive deny-list check.
4. Headers present and correct (X-Agent-Tenant, X-Timestamp, X-Signature, etc.).
"""

from __future__ import annotations

import hashlib
import hmac
import json
import time
from typing import Any
from unittest.mock import patch

import httpx
import pytest

from agent.reporter import (
    EncryptedReporter,
    _assert_no_raw_findings,
    sign_payload,
)


# ─── Helpers ─────────────────────────────────────────────────────────────────


SECRET = "test-shared-secret-32-bytes-of-entropy-here"
TENANT = "acme"
PORTAL = "https://example.invalid"
VERSION = "0.1.0-test"


# ─── 1. Signature correctness ────────────────────────────────────────────────


def test_sign_payload_matches_cloud_verifier_logic():
    """
    The cloud-side verifier (backend/routers/agent_ingest.py::_verify_agent_signature)
    HKDF-derives the HMAC key from the stored sha256(secret) hash using the
    same constants as the agent. The agent must produce identical signatures.

    Audit-fix CRIT-G5: previously the stored hash was used directly as the
    HMAC key — that meant a DB read = signing key. Now both sides HKDF-derive
    a separate key from that hash; the hash alone is not enough to forge.
    """
    from backend.routers.agent_ingest import _derive_hmac_key as _cloud_derive_key

    timestamp = "1714210000"
    path = "/api/agent-ingest/heartbeat"
    body = b'{"connector_health":{}}'

    agent_sig = sign_payload(SECRET, timestamp, path, body)

    # Reconstruct what the cloud computes (mirror cloud-side _verify_agent_signature):
    secret_hash = hashlib.sha256(SECRET.encode()).hexdigest()
    cloud_hmac_key = _cloud_derive_key(secret_hash)
    canonical = timestamp.encode() + b"." + path.encode() + b"." + body
    cloud_sig = hmac.new(cloud_hmac_key, canonical, hashlib.sha256).hexdigest()

    assert agent_sig == cloud_sig
    assert len(agent_sig) == 64  # hex sha256


def test_sign_payload_different_body_yields_different_signature():
    sig1 = sign_payload(SECRET, "1", "/p", b'{"a":1}')
    sig2 = sign_payload(SECRET, "1", "/p", b'{"a":2}')
    assert sig1 != sig2


def test_sign_payload_different_timestamp_yields_different_signature():
    sig1 = sign_payload(SECRET, "1", "/p", b"x")
    sig2 = sign_payload(SECRET, "2", "/p", b"x")
    assert sig1 != sig2


# ─── 2. NO raw findings ever in payload ──────────────────────────────────────


@pytest.mark.parametrize(
    "payload",
    [
        {"asset": "10.0.0.1"},
        {"risk_summary": {"asset": "host1"}},
        {"risk_summary": {"nested": {"ip": "1.1.1.1"}}},
        {"items": [{"hostname": "evil.local"}]},
        {"items": [{"deeper": [{"username": "admin"}]}]},
        {"control_summary": {"finding": "leak"}},
        {"control_summary": {"cve_id": "CVE-2026-0001"}},
    ],
)
def test_assert_no_raw_findings_blocks_banned_keys(payload):
    with pytest.raises(RuntimeError, match="raw-finding key"):
        _assert_no_raw_findings(payload)


@pytest.mark.parametrize(
    "payload",
    [
        {"risk_summary": {"total_risks": 10, "critical_count": 2}},
        {"score": 8.2, "counts": {"critical": 5, "high": 12}},
        {"connectors": [{"name": "tenable", "status": "ok", "error_count_24h": 0}]},
    ],
)
def test_assert_no_raw_findings_allows_clean_payload(payload):
    _assert_no_raw_findings(payload)  # must not raise


def test_reporter_blocks_raw_finding_payload_before_http_call():
    """The reporter must call _assert_no_raw_findings BEFORE constructing the request."""
    reporter = EncryptedReporter(
        cloud_portal_url=PORTAL,
        tenant_slug=TENANT,
        shared_secret=SECRET,
        agent_version=VERSION,
    )
    bad = {"risk_summary": {"asset": "10.0.0.5"}}
    with patch("httpx.Client") as mock_client_cls:
        with pytest.raises(RuntimeError, match="raw-finding key"):
            reporter.report_to_cloud("metadata", bad)
        # Critical: no HTTP call should have been made
        mock_client_cls.assert_not_called()


# ─── 3. Headers present + correct ────────────────────────────────────────────


def test_report_to_cloud_sends_correct_headers_and_body():
    """Use httpx MockTransport to capture the request, verify everything."""
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["method"] = request.method
        captured["url"] = str(request.url)
        captured["headers"] = dict(request.headers)
        captured["body"] = request.content
        return httpx.Response(200, json={"ok": True})

    transport = httpx.MockTransport(handler)
    client = httpx.Client(transport=transport)

    reporter = EncryptedReporter(
        cloud_portal_url=PORTAL,
        tenant_slug=TENANT,
        shared_secret=SECRET,
        agent_version=VERSION,
        http_client=client,
    )
    payload = {"risk_summary": {"total_risks": 5, "critical_count": 1}}

    response = reporter.report_to_cloud("metadata", payload)
    assert response.status_code == 200

    # Headers
    h = captured["headers"]
    assert h["x-agent-tenant"] == TENANT
    assert h["x-agent-version"] == VERSION
    assert "x-timestamp" in h
    assert "x-signature" in h
    assert h["content-type"] == "application/json"

    # Anti-replay: timestamp is recent
    ts = int(h["x-timestamp"])
    assert abs(time.time() - ts) < 5

    # Signature is correct given the captured body + timestamp + path
    expected_sig = sign_payload(
        SECRET,
        h["x-timestamp"],
        "/api/agent-ingest/metadata",
        captured["body"],
    )
    assert h["x-signature"] == expected_sig


# ─── 4. Retry behaviour ──────────────────────────────────────────────────────


def test_retries_on_5xx_then_succeeds():
    attempts = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        attempts["count"] += 1
        if attempts["count"] < 3:
            return httpx.Response(503, text="busy")
        return httpx.Response(200, json={"ok": True})

    transport = httpx.MockTransport(handler)
    client = httpx.Client(transport=transport)

    reporter = EncryptedReporter(
        cloud_portal_url=PORTAL,
        tenant_slug=TENANT,
        shared_secret=SECRET,
        agent_version=VERSION,
        http_client=client,
        max_retries=5,
        backoff_base_seconds=0.001,  # fast for tests
    )
    response = reporter.report_to_cloud("metadata", {"risk_summary": {}})
    assert response.status_code == 200
    assert attempts["count"] == 3


def test_gives_up_after_max_retries():
    attempts = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        attempts["count"] += 1
        return httpx.Response(503, text="always busy")

    transport = httpx.MockTransport(handler)
    client = httpx.Client(transport=transport)

    reporter = EncryptedReporter(
        cloud_portal_url=PORTAL,
        tenant_slug=TENANT,
        shared_secret=SECRET,
        agent_version=VERSION,
        http_client=client,
        max_retries=3,
        backoff_base_seconds=0.001,
    )
    with pytest.raises(httpx.HTTPError, match="gave up after 3 attempts"):
        reporter.report_to_cloud("metadata", {"risk_summary": {}})
    assert attempts["count"] == 3


def test_does_not_retry_on_4xx():
    """A 4xx response is a real error — do NOT retry, return immediately."""
    attempts = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        attempts["count"] += 1
        return httpx.Response(401, text="bad signature")

    transport = httpx.MockTransport(handler)
    client = httpx.Client(transport=transport)

    reporter = EncryptedReporter(
        cloud_portal_url=PORTAL,
        tenant_slug=TENANT,
        shared_secret=SECRET,
        agent_version=VERSION,
        http_client=client,
        max_retries=5,
        backoff_base_seconds=0.001,
    )
    response = reporter.report_to_cloud("metadata", {"risk_summary": {}})
    assert response.status_code == 401
    assert attempts["count"] == 1


def test_retries_on_429_rate_limit():
    """429 is treated as transient — should retry."""
    attempts = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        attempts["count"] += 1
        if attempts["count"] < 2:
            return httpx.Response(429, text="rate limit")
        return httpx.Response(200, json={"ok": True})

    transport = httpx.MockTransport(handler)
    client = httpx.Client(transport=transport)

    reporter = EncryptedReporter(
        cloud_portal_url=PORTAL,
        tenant_slug=TENANT,
        shared_secret=SECRET,
        agent_version=VERSION,
        http_client=client,
        max_retries=3,
        backoff_base_seconds=0.001,
    )
    response = reporter.report_to_cloud("metadata", {"risk_summary": {}})
    assert response.status_code == 200
    assert attempts["count"] == 2


# ─── 5. Constructor validation ───────────────────────────────────────────────


@pytest.mark.parametrize(
    "kwargs",
    [
        {"cloud_portal_url": "", "tenant_slug": TENANT, "shared_secret": SECRET},
        {"cloud_portal_url": PORTAL, "tenant_slug": "", "shared_secret": SECRET},
        {"cloud_portal_url": PORTAL, "tenant_slug": TENANT, "shared_secret": ""},
    ],
)
def test_reporter_requires_all_creds(kwargs):
    kwargs.setdefault("agent_version", VERSION)
    with pytest.raises(ValueError):
        EncryptedReporter(**kwargs)
