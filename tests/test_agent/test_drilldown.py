"""
Tests for agent/drilldown_responder.py — the long-poll drilldown responder.

Verified:
1. fetch_pending issues a SIGNED GET and returns the JSON list
2. fulfil dispatches to the correct handler and posts back signed
3. unsupported request_type → posts an error response (not silent drop)
"""

from __future__ import annotations

import asyncio
import json
from typing import Any

import httpx
import pytest

from agent.drilldown_responder import DrilldownResponder
from agent.reporter import EncryptedReporter, sign_payload


SECRET = "test-shared-secret"
TENANT = "acme"
PORTAL = "https://example.invalid"
VERSION = "0.1.0-test"


def _build_reporter_with_transport(handler) -> tuple[EncryptedReporter, httpx.Client]:
    transport = httpx.MockTransport(handler)
    client = httpx.Client(transport=transport)
    reporter = EncryptedReporter(
        cloud_portal_url=PORTAL,
        tenant_slug=TENANT,
        shared_secret=SECRET,
        agent_version=VERSION,
        http_client=client,
        max_retries=2,
        backoff_base_seconds=0.001,
    )
    return reporter, client


def _build_responder_with_transport(handler, handlers=None) -> DrilldownResponder:
    """Wire the same MockTransport into BOTH reporter and responder."""
    transport = httpx.MockTransport(handler)
    client = httpx.Client(transport=transport)
    reporter = EncryptedReporter(
        cloud_portal_url=PORTAL,
        tenant_slug=TENANT,
        shared_secret=SECRET,
        agent_version=VERSION,
        http_client=client,
        max_retries=2,
        backoff_base_seconds=0.001,
    )
    return DrilldownResponder(reporter, handlers=handlers or {}, http_client=client)


# ─── 1. fetch_pending sends a signed GET ─────────────────────────────────────


@pytest.mark.asyncio
async def test_fetch_pending_returns_pending_list_and_signs_get():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["method"] = request.method
        captured["path"] = request.url.path
        captured["headers"] = dict(request.headers)
        return httpx.Response(
            200,
            json={
                "pending": [
                    {
                        "token": "abc123",
                        "request_type": "fetch_risk_by_id",
                        "request_payload": {"risk_id": "RISK-2026-001"},
                        "expires_at": "2099-01-01T00:00:00+00:00",
                    }
                ]
            },
        )

    responder = _build_responder_with_transport(handler, handlers={})

    pending = await responder.fetch_pending()
    assert len(pending) == 1
    assert pending[0]["token"] == "abc123"

    # Signed correctly?
    h = captured["headers"]
    assert h["x-agent-tenant"] == TENANT
    assert "x-signature" in h
    expected = sign_payload(
        SECRET, h["x-timestamp"], "/api/agent-ingest/pending-requests", b""
    )
    assert h["x-signature"] == expected
    assert captured["method"] == "GET"


# ─── 2. fulfil dispatches handler and posts back ─────────────────────────────


@pytest.mark.asyncio
async def test_fulfil_dispatches_handler_and_posts_signed_response():
    posted = {}

    def handler(request: httpx.Request) -> httpx.Response:
        # Should be a POST to /api/agent-ingest/drilldown-response/{token}
        if request.method == "POST" and "drilldown-response" in request.url.path:
            posted["path"] = request.url.path
            posted["headers"] = dict(request.headers)
            posted["body"] = request.content
            return httpx.Response(200, json={"ok": True})
        return httpx.Response(404)

    invoked = {}

    async def my_handler(request_type: str, payload: dict) -> dict:
        invoked["type"] = request_type
        invoked["payload"] = payload
        return {"asset": "secret-host-internal"}  # raw — only ok in drill-down

    responder = _build_responder_with_transport(
        handler, handlers={"fetch_risk_by_id": my_handler}
    )
    pending = {
        "token": "tok-xyz",
        "request_type": "fetch_risk_by_id",
        "request_payload": {"risk_id": "RISK-2026-001"},
        "expires_at": "2099-01-01T00:00:00+00:00",
    }
    ok = await responder.fulfil(pending)
    assert ok is True
    assert invoked["type"] == "fetch_risk_by_id"
    assert invoked["payload"] == {"risk_id": "RISK-2026-001"}

    # Confirm the POST went through with the right path + body
    assert posted["path"] == "/api/agent-ingest/drilldown-response/tok-xyz"
    body = json.loads(posted["body"])
    assert body == {"asset": "secret-host-internal"}

    # Signature is correct
    h = posted["headers"]
    expected = sign_payload(
        SECRET,
        h["x-timestamp"],
        "/api/agent-ingest/drilldown-response/tok-xyz",
        posted["body"],
    )
    assert h["x-signature"] == expected


# ─── 3. Unsupported request_type → error response, not silent drop ──────────


@pytest.mark.asyncio
async def test_unsupported_request_type_posts_error():
    posted = {}

    def handler(request: httpx.Request) -> httpx.Response:
        # Drilldown-response goes through reporter.report_to_cloud — which has
        # the leak check.  Our error payload {"error": ...} has no banned keys.
        if request.method == "POST" and "drilldown-response" in request.url.path:
            posted["body"] = json.loads(request.content)
            return httpx.Response(200, json={"ok": True})
        return httpx.Response(404)

    responder = _build_responder_with_transport(handler, handlers={})  # NO handlers
    pending = {
        "token": "tok-error",
        "request_type": "fetch_evidence_file",
        "request_payload": {},
        "expires_at": "2099-01-01T00:00:00+00:00",
    }
    ok = await responder.fulfil(pending)
    assert ok is False
    assert posted["body"]["error"].startswith("unsupported request_type")
