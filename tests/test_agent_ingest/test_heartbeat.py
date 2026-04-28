"""
Tests for POST /api/agent-ingest/heartbeat — signature verification + last_seen.
"""

from __future__ import annotations

import json
import time

import pytest
from sqlalchemy import select

from backend.models.agent_ingest import AgentRegistration
from tests.test_agent_ingest.conftest import (
    KNOWN_SHARED_SECRET,
    build_signed_headers,
    sign,
)


pytestmark = pytest.mark.asyncio


# ─── 1. Valid signature → 200 + last_seen updated ───────────────────────────


async def test_valid_heartbeat_updates_last_seen(
    client, licensed_tenant, registered_agent, db_session
):
    body_dict = {"connector_health": {"tenable": {"status": "ok"}}}
    body = json.dumps(body_dict, separators=(",", ":"), sort_keys=True).encode()
    path = "/api/agent-ingest/heartbeat"
    headers = build_signed_headers(licensed_tenant.slug, KNOWN_SHARED_SECRET, path, body)

    initial_last_seen = registered_agent.last_seen
    response = await client.post(path, content=body, headers=headers)
    assert response.status_code == 200, response.text
    assert response.json()["ok"] is True

    # Reload reg
    await db_session.refresh(registered_agent)
    assert registered_agent.last_seen >= initial_last_seen
    assert registered_agent.connector_health == {"tenable": {"status": "ok"}}


# ─── 2. Bad signature → 401 ──────────────────────────────────────────────────


async def test_bad_signature_returns_401(client, licensed_tenant, registered_agent):
    body = b'{"connector_health":{}}'
    headers = build_signed_headers(
        licensed_tenant.slug, KNOWN_SHARED_SECRET, "/api/agent-ingest/heartbeat", body
    )
    headers["X-Signature"] = "0" * 64
    response = await client.post(
        "/api/agent-ingest/heartbeat", content=body, headers=headers
    )
    assert response.status_code == 401


# ─── 3. Stale timestamp → 401 (anti-replay) ─────────────────────────────────


async def test_stale_timestamp_returns_401(client, licensed_tenant, registered_agent):
    body = b'{"connector_health":{}}'
    path = "/api/agent-ingest/heartbeat"
    stale_ts = str(int(time.time()) - 10 * 60)  # 10 min ago
    headers = {
        "X-Agent-Tenant": licensed_tenant.slug,
        "X-Agent-Version": "0.1.0-test",
        "X-Timestamp": stale_ts,
        "X-Signature": sign(KNOWN_SHARED_SECRET, stale_ts, path, body),
        "Content-Type": "application/json",
    }
    response = await client.post(path, content=body, headers=headers)
    assert response.status_code == 401
    assert "X-Timestamp outside" in response.json()["detail"]


# ─── 4. Future timestamp also rejected ──────────────────────────────────────


async def test_future_timestamp_returns_401(client, licensed_tenant, registered_agent):
    body = b'{"connector_health":{}}'
    path = "/api/agent-ingest/heartbeat"
    future_ts = str(int(time.time()) + 10 * 60)
    headers = {
        "X-Agent-Tenant": licensed_tenant.slug,
        "X-Agent-Version": "0.1.0-test",
        "X-Timestamp": future_ts,
        "X-Signature": sign(KNOWN_SHARED_SECRET, future_ts, path, body),
        "Content-Type": "application/json",
    }
    response = await client.post(path, content=body, headers=headers)
    assert response.status_code == 401


# ─── 5. Missing headers → 401 ────────────────────────────────────────────────


async def test_missing_signature_header_returns_401(client, licensed_tenant, registered_agent):
    response = await client.post(
        "/api/agent-ingest/heartbeat",
        content=b"{}",
        headers={
            "X-Agent-Tenant": licensed_tenant.slug,
            "X-Timestamp": str(int(time.time())),
            # X-Signature missing
            "Content-Type": "application/json",
        },
    )
    assert response.status_code == 401


# ─── 6. Unknown tenant → 401 ────────────────────────────────────────────────


async def test_unknown_tenant_returns_401(client, registered_agent):
    body = b"{}"
    path = "/api/agent-ingest/heartbeat"
    headers = build_signed_headers("nope", KNOWN_SHARED_SECRET, path, body)
    response = await client.post(path, content=body, headers=headers)
    assert response.status_code == 401
