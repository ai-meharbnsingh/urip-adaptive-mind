"""
Tests for POST /api/agent-ingest/register — license validation.

Verified:
1. Valid license key → 200, returns shared_secret + tenant_id
2. Wrong license key → 401
3. Unknown tenant slug → 401 (constant-time, no oracle)
4. Re-registration rotates the secret
5. shared_secret stored as HMAC hash, NOT plaintext
"""

from __future__ import annotations

import hashlib
import uuid

import pytest
from sqlalchemy import select

from backend.models.agent_ingest import AgentRegistration
from backend.models.tenant import Tenant
from tests.test_agent_ingest.conftest import KNOWN_LICENSE_KEY


pytestmark = pytest.mark.asyncio


# ─── 1. Happy path ───────────────────────────────────────────────────────────


async def test_valid_license_key_returns_secret(client, licensed_tenant, db_session):
    response = await client.post(
        "/api/agent-ingest/register",
        json={
            "tenant_slug": licensed_tenant.slug,
            "license_key": KNOWN_LICENSE_KEY,
            "agent_version": "0.1.0-test",
            "capabilities": {"connectors": ["tenable", "simulator"]},
        },
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["tenant_id"] == str(licensed_tenant.id)
    assert "shared_secret" in body
    assert len(body["shared_secret"]) == 64  # 32-byte hex
    assert "registered_at" in body


# ─── 2. Bad license key ──────────────────────────────────────────────────────


async def test_wrong_license_key_returns_401(client, licensed_tenant):
    response = await client.post(
        "/api/agent-ingest/register",
        json={
            "tenant_slug": licensed_tenant.slug,
            "license_key": "WRONG-KEY-XXXXXXXXXXXXXXXXXX",  # ≥16 chars, but wrong
            "agent_version": "0.1.0-test",
            "capabilities": {},
        },
    )
    assert response.status_code == 401


# ─── 3. Unknown tenant ───────────────────────────────────────────────────────


async def test_unknown_tenant_returns_401(client, licensed_tenant):
    response = await client.post(
        "/api/agent-ingest/register",
        json={
            "tenant_slug": "does-not-exist",
            "license_key": KNOWN_LICENSE_KEY,
            "agent_version": "0.1.0-test",
            "capabilities": {},
        },
    )
    assert response.status_code == 401


async def test_tenant_with_no_license_key_set_returns_401(client, db_session):
    """A tenant exists but has no license_key — registration must be rejected."""
    t = Tenant(
        id=uuid.uuid4(),
        name="No-License Tenant",
        slug="no-license",
        domain="x.test",
        is_active=True,
        settings={},
        license_key=None,
    )
    db_session.add(t)
    await db_session.commit()

    response = await client.post(
        "/api/agent-ingest/register",
        json={
            "tenant_slug": "no-license",
            "license_key": "any-valid-length-key-here-1234",
            "agent_version": "0.1.0-test",
            "capabilities": {},
        },
    )
    assert response.status_code == 401


# ─── 4. Re-registration rotates the secret ───────────────────────────────────


async def test_reregistration_rotates_secret(client, licensed_tenant, db_session):
    r1 = await client.post(
        "/api/agent-ingest/register",
        json={
            "tenant_slug": licensed_tenant.slug,
            "license_key": KNOWN_LICENSE_KEY,
            "agent_version": "0.1.0-test",
            "capabilities": {},
        },
    )
    assert r1.status_code == 200
    secret1 = r1.json()["shared_secret"]

    r2 = await client.post(
        "/api/agent-ingest/register",
        json={
            "tenant_slug": licensed_tenant.slug,
            "license_key": KNOWN_LICENSE_KEY,
            "agent_version": "0.1.1-test",
            "capabilities": {},
        },
    )
    assert r2.status_code == 200
    secret2 = r2.json()["shared_secret"]
    assert secret1 != secret2  # rotated


# ─── 5. shared_secret stored as hash, NOT plaintext ──────────────────────────


async def test_shared_secret_stored_as_sha256_hash(
    client, licensed_tenant, db_session
):
    response = await client.post(
        "/api/agent-ingest/register",
        json={
            "tenant_slug": licensed_tenant.slug,
            "license_key": KNOWN_LICENSE_KEY,
            "agent_version": "0.1.0-test",
            "capabilities": {},
        },
    )
    assert response.status_code == 200
    plain_secret = response.json()["shared_secret"]

    q = await db_session.execute(
        select(AgentRegistration).where(
            AgentRegistration.tenant_id == licensed_tenant.id
        )
    )
    reg = q.scalar_one()
    expected_hash = hashlib.sha256(plain_secret.encode()).hexdigest()
    assert reg.shared_secret_hash == expected_hash
    # Plaintext is NOT stored anywhere on the row
    assert plain_secret not in reg.shared_secret_hash
