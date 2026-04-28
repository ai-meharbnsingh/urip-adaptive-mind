"""
Tests for the drilldown round-trip:

  1. Frontend POST /drilldown-request          → token, expires_at
  2. Agent  GET  /pending-requests             → sees the row
  3. Agent  POST /drilldown-response/{token}   → 200 ok
  4. Backend persists payload TEMPORARILY only

Plus expiry, double-fulfilment, and SSE forward (tested at handler level).
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select

from backend.models.agent_ingest import DrilldownRequest
from tests.test_agent_ingest.conftest import (
    KNOWN_SHARED_SECRET,
    build_signed_headers,
)


pytestmark = pytest.mark.asyncio


# ─── 1. Full happy-path round trip ──────────────────────────────────────────


async def test_drilldown_full_cycle(
    client, licensed_tenant, registered_agent, auth_headers, db_session
):
    """Frontend → cloud → agent → cloud (response stored briefly)."""
    # We need a user attached to the licensed_tenant — auth_headers fixture
    # uses default_tenant.  Build a user on licensed_tenant manually.
    from backend.middleware.auth import create_access_token, hash_password
    from backend.models.user import User

    user = User(
        id=uuid.uuid4(),
        email="ciso@acme.test",
        hashed_password=hash_password("Secure#Pass1"),
        full_name="Acme CISO",
        role="ciso",
        team="Security",
        is_active=True,
        tenant_id=licensed_tenant.id,
    )
    db_session.add(user)
    await db_session.commit()
    token = create_access_token(str(user.id), user.role, tenant_id=str(licensed_tenant.id))
    user_headers = {"Authorization": f"Bearer {token}"}

    # 1. Frontend → cloud
    r1 = await client.post(
        "/api/agent-ingest/drilldown-request",
        json={
            "request_type": "fetch_risk_by_id",
            "request_payload": {"risk_id": "RISK-2026-001"},
        },
        headers=user_headers,
    )
    assert r1.status_code == 200, r1.text
    out = r1.json()
    drilldown_token = out["token"]
    assert len(drilldown_token) == 64
    assert "expires_at" in out

    # 2. Agent → cloud (poll for pending)
    path = "/api/agent-ingest/pending-requests"
    headers = build_signed_headers(licensed_tenant.slug, KNOWN_SHARED_SECRET, path, b"")
    # GET with body=b'' → use http get
    r2 = await client.get(path, headers=headers)
    assert r2.status_code == 200, r2.text
    pending = r2.json()["pending"]
    assert len(pending) == 1
    assert pending[0]["token"] == drilldown_token
    assert pending[0]["request_type"] == "fetch_risk_by_id"

    # 3. Agent fulfils
    raw_response = {
        "risk_id": "RISK-2026-001",
        "asset": "10.0.0.5",
        "finding": "leaked OpenSSH config",
    }
    body = json.dumps(raw_response, separators=(",", ":"), sort_keys=True).encode()
    path3 = f"/api/agent-ingest/drilldown-response/{drilldown_token}"
    headers3 = build_signed_headers(
        licensed_tenant.slug, KNOWN_SHARED_SECRET, path3, body
    )
    r3 = await client.post(path3, content=body, headers=headers3)
    assert r3.status_code == 200, r3.text

    # 4. Backend has stored the payload TEMPORARILY in fulfilled_payload_temp
    q = await db_session.execute(
        select(DrilldownRequest).where(DrilldownRequest.token == drilldown_token)
    )
    row = q.scalar_one()
    assert row.fulfilled_at is not None
    assert row.fulfilled_payload_temp is not None
    stored = json.loads(row.fulfilled_payload_temp)
    assert stored["risk_id"] == "RISK-2026-001"


# ─── 2. Double-fulfilment is rejected (one-time token) ──────────────────────


async def test_token_cannot_be_fulfilled_twice(
    client, licensed_tenant, registered_agent, db_session
):
    # Create a request directly
    drilldown_token = "a" * 64
    row = DrilldownRequest(
        id=uuid.uuid4(),
        tenant_id=licensed_tenant.id,
        request_type="fetch_risk_by_id",
        request_payload={"risk_id": "X"},
        token=drilldown_token,
        expires_at=datetime.now(timezone.utc) + timedelta(seconds=60),
    )
    db_session.add(row)
    await db_session.commit()

    body = b'{"risk_id":"X"}'
    path = f"/api/agent-ingest/drilldown-response/{drilldown_token}"
    headers = build_signed_headers(licensed_tenant.slug, KNOWN_SHARED_SECRET, path, body)

    # First fulfilment OK
    r1 = await client.post(path, content=body, headers=headers)
    assert r1.status_code == 200

    # Second fulfilment rejected
    headers2 = build_signed_headers(licensed_tenant.slug, KNOWN_SHARED_SECRET, path, body)
    r2 = await client.post(path, content=body, headers=headers2)
    assert r2.status_code == 409


# ─── 3. Expired token rejected ──────────────────────────────────────────────


async def test_expired_token_returns_410(
    client, licensed_tenant, registered_agent, db_session
):
    drilldown_token = "b" * 64
    row = DrilldownRequest(
        id=uuid.uuid4(),
        tenant_id=licensed_tenant.id,
        request_type="fetch_risk_by_id",
        request_payload={},
        token=drilldown_token,
        expires_at=datetime.now(timezone.utc) - timedelta(seconds=1),
    )
    db_session.add(row)
    await db_session.commit()

    body = b'{"risk_id":"X"}'
    path = f"/api/agent-ingest/drilldown-response/{drilldown_token}"
    headers = build_signed_headers(licensed_tenant.slug, KNOWN_SHARED_SECRET, path, body)
    r = await client.post(path, content=body, headers=headers)
    assert r.status_code == 410


# ─── 4. Unknown token returns 404 ───────────────────────────────────────────


async def test_unknown_token_returns_404(
    client, licensed_tenant, registered_agent
):
    body = b'{"risk_id":"X"}'
    path = "/api/agent-ingest/drilldown-response/" + ("c" * 64)
    headers = build_signed_headers(licensed_tenant.slug, KNOWN_SHARED_SECRET, path, body)
    r = await client.post(path, content=body, headers=headers)
    assert r.status_code == 404


# ─── 5. pending-requests excludes fulfilled and expired rows ────────────────


async def test_pending_requests_filters_out_fulfilled_and_expired(
    client, licensed_tenant, registered_agent, db_session
):
    now = datetime.now(timezone.utc)
    db_session.add_all(
        [
            # active pending
            DrilldownRequest(
                id=uuid.uuid4(),
                tenant_id=licensed_tenant.id,
                request_type="A",
                request_payload={},
                token="a" * 64,
                expires_at=now + timedelta(seconds=60),
            ),
            # already fulfilled
            DrilldownRequest(
                id=uuid.uuid4(),
                tenant_id=licensed_tenant.id,
                request_type="B",
                request_payload={},
                token="b" * 64,
                fulfilled_at=now,
                fulfilled_payload_temp="{}",
                expires_at=now + timedelta(seconds=60),
            ),
            # expired
            DrilldownRequest(
                id=uuid.uuid4(),
                tenant_id=licensed_tenant.id,
                request_type="C",
                request_payload={},
                token="c" * 64,
                expires_at=now - timedelta(seconds=1),
            ),
        ]
    )
    await db_session.commit()

    path = "/api/agent-ingest/pending-requests"
    headers = build_signed_headers(licensed_tenant.slug, KNOWN_SHARED_SECRET, path, b"")
    r = await client.get(path, headers=headers)
    assert r.status_code == 200
    pending = r.json()["pending"]
    assert len(pending) == 1
    assert pending[0]["request_type"] == "A"
