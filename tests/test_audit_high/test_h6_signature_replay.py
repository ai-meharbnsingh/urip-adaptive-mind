"""
HIGH-6 — Drilldown / agent-ingest signature replay protection.

Auditors:
  - Codex MED-001
  - Gemini HIGH-G4

Vulnerability: ``_verify_agent_signature`` only checks the timestamp window
(±5 min). An attacker who captures a valid signed request can re-send it any
number of times within that window and the cloud accepts every replay.

Fix: maintain a cache of recent ``X-Signature`` values; reject any signature
seen within the anti-replay window even if its timestamp is still fresh.
We use a small in-process LRU (we don't depend on Redis to keep tests
hermetic; the production version uses Redis with the same TTL).
"""
from __future__ import annotations

import hashlib
import hmac
import json
import time
import uuid

import pytest

from backend.middleware.auth import hash_password
from backend.models.agent_ingest import AgentRegistration
from backend.models.tenant import Tenant
from backend.routers import agent_ingest as ai_router


def _signed_headers(secret_hash: str, body: bytes, path: str, ts: str | None = None):
    """Sign exactly the way the cloud-side _verify_agent_signature expects."""
    if ts is None:
        ts = str(time.time())
    hmac_key = ai_router._derive_hmac_key(secret_hash)
    canonical = ts.encode() + b"." + path.encode() + b"." + body
    sig = hmac.new(hmac_key, canonical, hashlib.sha256).hexdigest()
    return {
        "X-Agent-Tenant": "replay-tenant",
        "X-Timestamp": ts,
        "X-Signature": sig,
    }, sig


@pytest.fixture(autouse=True)
def _reset_replay_cache():
    """Each test gets a fresh nonce cache."""
    if hasattr(ai_router, "_signature_replay_cache"):
        ai_router._signature_replay_cache.clear()
    yield


@pytest.mark.anyio
async def test_replayed_signature_within_window_returns_401(client, db_session):
    """
    First request with a valid signature succeeds (200). Replaying the
    SAME headers (same ts + sig) within the anti-replay window must 401.
    """
    # Seed tenant + agent registration
    tenant = Tenant(
        id=uuid.uuid4(),
        name="Replay Test",
        slug="replay-tenant",
        domain="replay.example.com",
        is_active=True,
        settings={},
    )
    db_session.add(tenant)
    plain_secret = "test-secret-123"
    secret_hash = hashlib.sha256(plain_secret.encode()).hexdigest()
    reg = AgentRegistration(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        agent_version="0.1",
        capabilities={},
        shared_secret_hash=secret_hash,
    )
    db_session.add(reg)
    await db_session.commit()

    body = json.dumps({"connector_health": {}}).encode()
    headers, sig = _signed_headers(secret_hash, body, "/api/agent-ingest/heartbeat")

    # First request — accepted
    r1 = await client.post(
        "/api/agent-ingest/heartbeat", content=body, headers=headers
    )
    assert r1.status_code == 200, r1.text

    # Replay — same headers, same body, fresh ts → MUST 401
    r2 = await client.post(
        "/api/agent-ingest/heartbeat", content=body, headers=headers
    )
    assert r2.status_code == 401, (
        f"Replay must be rejected; got {r2.status_code}: {r2.text}"
    )


@pytest.mark.anyio
async def test_distinct_signatures_not_blocked(client, db_session):
    """Two legitimate signed requests with different timestamps both succeed."""
    tenant = Tenant(
        id=uuid.uuid4(),
        name="Replay Test 2",
        slug="replay-tenant-2",
        domain="replay2.example.com",
        is_active=True,
        settings={},
    )
    db_session.add(tenant)
    plain_secret = "test-secret-456"
    secret_hash = hashlib.sha256(plain_secret.encode()).hexdigest()
    reg = AgentRegistration(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        agent_version="0.1",
        capabilities={},
        shared_secret_hash=secret_hash,
    )
    db_session.add(reg)
    await db_session.commit()

    body = json.dumps({"connector_health": {}}).encode()

    # Two requests with different timestamps — different signatures.
    headers1, _sig1 = _signed_headers(
        secret_hash, body, "/api/agent-ingest/heartbeat", ts=str(time.time())
    )
    headers1["X-Agent-Tenant"] = "replay-tenant-2"
    r1 = await client.post(
        "/api/agent-ingest/heartbeat", content=body, headers=headers1
    )
    assert r1.status_code == 200, r1.text

    headers2, _sig2 = _signed_headers(
        secret_hash, body, "/api/agent-ingest/heartbeat", ts=str(time.time() + 1)
    )
    headers2["X-Agent-Tenant"] = "replay-tenant-2"
    r2 = await client.post(
        "/api/agent-ingest/heartbeat", content=body, headers=headers2
    )
    assert r2.status_code == 200, r2.text
