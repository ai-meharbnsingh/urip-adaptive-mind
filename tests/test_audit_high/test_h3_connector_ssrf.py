"""
HIGH-3 — Connector SSRF: when a user supplies ``base_url`` in inline credentials
to the connector test/configure endpoints, the URL must:

  1. Use the HTTPS scheme. http://, file://, gopher://, ftp:// are rejected.
  2. NOT resolve to a private / link-local / loopback / metadata IP.

Without this, an attacker with ``ciso`` role can probe the metadata service
(169.254.169.254), localhost, or other internal hosts via the URIP backend.

Auditors:
  - Claude finding (SSRF)
  - Kimi HIGH-002

We exercise the public POST /api/connectors/{name}/test endpoint with the
``sentinelone`` connector (which exposes a required base_url field).
"""
from __future__ import annotations

import os
import uuid

# Ensure crypto key is available even if test_routers conftest hasn't loaded.
os.environ.setdefault(
    "URIP_FERNET_KEY",
    "M3JKpUVOfx1nPLQYMRrxnVZsJq3cJ5vXq7bOe6jfXok=",
)
os.environ.setdefault("DISABLE_CONNECTOR_SCHEDULER", "true")

# Import the connector_loader so all 9 connectors self-register before any
# test in this module runs. Without this, /api/connectors/simulator returns
# 404 because the simulator connector class isn't in the registry.
import backend.connector_loader  # noqa: F401

import pytest
import pytest_asyncio


@pytest_asyncio.fixture
async def core_enabled_headers(db_session, default_tenant):
    """
    Build CISO auth headers AND seed the CORE module subscription so the
    connectors router (gated on `Depends(require_module("CORE"))`) is reachable.
    Replaces the stripped `core_subscription` fixture from the audit-fix-era
    conftest.
    """
    from backend.middleware.auth import create_access_token, hash_password
    from backend.models.subscription import TenantSubscription
    from backend.models.user import User

    sub = TenantSubscription(
        id=uuid.uuid4(),
        tenant_id=default_tenant.id,
        module_code="CORE",
        is_enabled=True,
        billing_tier="STANDARD",
    )
    db_session.add(sub)
    user = User(
        id=uuid.uuid4(),
        email="ssrf-ciso@urip.test",
        hashed_password=hash_password("Secure#Pass1"),
        full_name="SSRF Test CISO",
        role="ciso",
        team="Security",
        is_active=True,
        tenant_id=default_tenant.id,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    token = create_access_token(
        str(user.id), user.role, tenant_id=str(default_tenant.id)
    )
    return {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------------------
# Scheme rejection — must be HTTPS
# ---------------------------------------------------------------------------

@pytest.mark.anyio
@pytest.mark.parametrize(
    "url",
    [
        "http://example.com/foo",            # plain HTTP
        "ftp://example.com/foo",             # ftp scheme
        "file:///etc/passwd",                # file scheme
        "gopher://example.com/foo",          # legacy SSRF favourite
        "javascript:alert(1)",               # not a URL really
        "//example.com/foo",                 # protocol-relative
        "example.com/foo",                   # missing scheme
    ],
)
async def test_test_endpoint_rejects_non_https_base_url(
    client, core_enabled_headers, url
):
    resp = await client.post(
        "/api/connectors/sentinelone/test",
        headers=core_enabled_headers,
        json={
            "credentials": {
                "api_token": "fake",
                "base_url": url,
            }
        },
    )
    assert resp.status_code == 422, (
        f"Expected 422 for non-HTTPS base_url {url!r}, "
        f"got {resp.status_code}: {resp.text}"
    )


# ---------------------------------------------------------------------------
# Private / loopback / metadata hosts
# ---------------------------------------------------------------------------

@pytest.mark.anyio
@pytest.mark.parametrize(
    "url",
    [
        # IPv4 private ranges
        "https://10.0.0.5/api",
        "https://192.168.1.1/api",
        "https://172.16.5.5/api",
        # Loopback
        "https://127.0.0.1/api",
        "https://localhost/api",
        # Link-local
        "https://169.254.10.10/api",
        # Cloud metadata service (the canonical SSRF target)
        "https://169.254.169.254/latest/meta-data/",
        # IPv6 loopback / link-local
        "https://[::1]/api",
        "https://[fe80::1]/api",
        # IPv6 unique local
        "https://[fc00::1]/api",
    ],
)
async def test_test_endpoint_rejects_private_or_loopback_base_url(
    client, core_enabled_headers, url
):
    resp = await client.post(
        "/api/connectors/sentinelone/test",
        headers=core_enabled_headers,
        json={
            "credentials": {
                "api_token": "fake",
                "base_url": url,
            }
        },
    )
    assert resp.status_code == 422, (
        f"Expected 422 for private/loopback {url!r}, "
        f"got {resp.status_code}: {resp.text}"
    )


# ---------------------------------------------------------------------------
# Hostname that resolves to a private IP — also blocked.
# We use a guaranteed-loopback name handled by stdlib resolution.
# ---------------------------------------------------------------------------

@pytest.mark.anyio
async def test_test_endpoint_rejects_hostname_resolving_to_loopback(
    client, core_enabled_headers
):
    # `localhost` is hard-coded to 127.0.0.1 in /etc/hosts on every OS we
    # care about — this validates the resolver-time check.
    resp = await client.post(
        "/api/connectors/sentinelone/test",
        headers=core_enabled_headers,
        json={
            "credentials": {
                "api_token": "fake",
                "base_url": "https://localhost/api",
            }
        },
    )
    assert resp.status_code == 422, resp.text


# ---------------------------------------------------------------------------
# Valid public HTTPS still works (configure path, simulator backend).
# We cannot rely on real DNS in CI, so we use the configure endpoint with the
# simulator connector — which has no base_url field — to verify the SSRF guard
# does not break unrelated connectors.
# ---------------------------------------------------------------------------

@pytest.mark.anyio
async def test_simulator_configure_unaffected_by_ssrf_guard(
    client, core_enabled_headers
):
    """The simulator connector has no base_url — SSRF check must not block it."""
    resp = await client.post(
        "/api/connectors/simulator/configure",
        headers=core_enabled_headers,
        json={"credentials": {"tenant_id": "test"}},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "configured"
