"""
Shared fixtures for cloud-side agent_ingest tests.

These tests need:
- A tenant with a known license_key
- A pre-registered AgentRegistration with a known plain shared_secret
- A helper to build signed headers for arbitrary requests
"""

from __future__ import annotations

import hashlib
import hmac
import json
import time
import uuid
from typing import Any

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.agent_ingest import AgentRegistration
from backend.models.tenant import Tenant


# HIGH-6 — agent ingest now caches recent X-Signature values to defeat
# replay attacks. The cache is module-state; clear it before every test so
# (1) ordering doesn't change pass/fail outcomes, and (2) tests that
# legitimately need to replay an exact (ts, body) pair (e.g. the
# "double-fulfilment is rejected" test) can still observe the application
# semantics they care about.
@pytest.fixture(autouse=True)
def _reset_signature_replay_cache():
    try:
        from backend.routers import agent_ingest as _ai
        if hasattr(_ai, "_signature_replay_cache"):
            _ai._signature_replay_cache.clear()
    except Exception:
        pass
    yield


KNOWN_LICENSE_KEY = "license-test-1234567890-abcdef-FAKE"
KNOWN_SHARED_SECRET = "shared-secret-test-32-bytes-of-entropy-here-XYZ"


@pytest_asyncio.fixture
async def licensed_tenant(db_session: AsyncSession) -> Tenant:
    """Create a tenant with a known license_key."""
    t = Tenant(
        id=uuid.uuid4(),
        name="Acme Test",
        slug="acme-test",
        domain="acme.test",
        is_active=True,
        settings={},
        license_key=KNOWN_LICENSE_KEY,
    )
    db_session.add(t)
    await db_session.commit()
    await db_session.refresh(t)
    return t


@pytest_asyncio.fixture
async def registered_agent(
    db_session: AsyncSession, licensed_tenant: Tenant
) -> AgentRegistration:
    """Pre-create an AgentRegistration with a known shared_secret hash."""
    secret_hash = hashlib.sha256(KNOWN_SHARED_SECRET.encode()).hexdigest()
    reg = AgentRegistration(
        id=uuid.uuid4(),
        tenant_id=licensed_tenant.id,
        agent_version="0.1.0-test",
        capabilities={"connectors": ["simulator"]},
        shared_secret_hash=secret_hash,
    )
    db_session.add(reg)
    await db_session.commit()
    await db_session.refresh(reg)
    return reg


def sign(secret: str, timestamp: str, path: str, body: bytes) -> str:
    """Mirror agent-side signing for tests.

    Audit-fix CRIT-G5: agent + cloud both HKDF-derive a separate HMAC signing
    key from sha256(secret). This helper imports the agent's derivation
    function so the fixture stays in lockstep with the production agent
    code path — there is exactly one source of truth for the derivation.
    """
    from agent.reporter import _derive_hmac_key  # local import: production parity

    secret_hash = hashlib.sha256(secret.encode()).hexdigest()
    hmac_key = _derive_hmac_key(secret_hash)
    canonical = timestamp.encode() + b"." + path.encode() + b"." + body
    return hmac.new(hmac_key, canonical, hashlib.sha256).hexdigest()


def build_signed_headers(
    tenant_slug: str, secret: str, path: str, body: bytes
) -> dict[str, str]:
    # HIGH-6 — sub-second resolution so consecutive calls within the same
    # test produce DIFFERENT signatures. The cloud-side replay cache (added
    # in the HIGH-6 audit fix) blocks repeated identical signatures; tests
    # that legitimately make two signed calls in the same second must
    # produce distinct timestamps so the application semantics being tested
    # (e.g. 409 "token already fulfilled") are reachable.
    ts = repr(time.time())  # microsecond-ish precision
    return {
        "X-Agent-Tenant": tenant_slug,
        "X-Agent-Version": "0.1.0-test",
        "X-Timestamp": ts,
        "X-Signature": sign(secret, ts, path, body),
        "Content-Type": "application/json",
    }
