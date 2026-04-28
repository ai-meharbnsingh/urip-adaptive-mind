"""
TDD — Policy API route tests.

Tests written BEFORE router implementation.
Requires auth token to access protected routes.
"""
import time
import pytest
# CRIT-005 (Z2.1): migrated python-jose -> PyJWT (HS256 surface identical)
import jwt
from sqlalchemy import text

from compliance_backend.services import policy_manager


@pytest.fixture(autouse=True)
async def cleanup_policies(db_session):
    """Truncate policy tables after each test to ensure isolation."""
    yield
    await db_session.rollback()
    await db_session.execute(text("DELETE FROM policy_acknowledgments"))
    await db_session.execute(text("DELETE FROM policy_versions"))
    await db_session.execute(text("DELETE FROM policies"))
    await db_session.commit()


STANDALONE_SECRET = "test-secret-standalone"


def _auth_headers(role: str = "admin", tenant_id: str = "tenant-abc", user_id: str = "user-123") -> dict:
    payload = {
        "sub": user_id,
        "tenant_id": tenant_id,
        "role": role,
        "exp": int(time.time()) + 3600,
        "iss": "compliance",
    }
    token = jwt.encode(payload, STANDALONE_SECRET, algorithm="HS256")
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.anyio
async def test_create_policy_as_admin(client, db_session):
    """POST /policies creates a policy when caller is admin."""
    response = await client.post(
        "/policies",
        headers=_auth_headers(role="admin"),
        json={
            "name": "Security Policy",
            "content": "# Security\nBe safe.",
        },
    )
    assert response.status_code == 201, f"Expected 201, got {response.status_code}: {response.text}"
    body = response.json()
    assert body["name"] == "Security Policy"
    assert body["tenant_id"] == "tenant-abc"
    assert body["current_version_id"] is not None


@pytest.mark.anyio
async def test_create_policy_forbidden_for_non_admin(client):
    """POST /policies returns 403 for non-admin."""
    response = await client.post(
        "/policies",
        headers=_auth_headers(role="analyst"),
        json={"name": "X", "content": "Y"},
    )
    assert response.status_code == 403, f"Expected 403, got {response.status_code}"


@pytest.mark.anyio
async def test_list_policies_returns_tenant_scoped(client, db_session):
    """GET /policies returns only the caller's tenant policies."""
    await policy_manager.create_policy(
        session=db_session,
        tenant_id="tenant-abc",
        name="Policy A",
        content="# A",
        owner="admin-1",
    )
    await policy_manager.create_policy(
        session=db_session,
        tenant_id="tenant-other",
        name="Policy B",
        content="# B",
        owner="admin-2",
    )
    await db_session.commit()

    response = await client.get("/policies", headers=_auth_headers(role="admin"))
    assert response.status_code == 200
    body = response.json()
    assert isinstance(body, list)
    assert len(body) == 1
    assert body[0]["name"] == "Policy A"
    assert body[0]["tenant_id"] == "tenant-abc"


@pytest.mark.anyio
async def test_get_policy_detail(client, db_session):
    """GET /policies/{id} returns detail with current version."""
    policy = await policy_manager.create_policy(
        session=db_session,
        tenant_id="tenant-abc",
        name="Detail Policy",
        content="# Detail",
        owner="admin-1",
    )
    await db_session.commit()

    response = await client.get(
        f"/policies/{policy.id}",
        headers=_auth_headers(role="admin"),
    )
    assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
    body = response.json()
    assert body["name"] == "Detail Policy"
    assert "current_version" in body
    assert body["current_version"]["content"] == "# Detail"


@pytest.mark.anyio
async def test_get_policy_not_found_wrong_tenant(client, db_session):
    """GET /policies/{id} returns 404 for a policy in another tenant."""
    policy = await policy_manager.create_policy(
        session=db_session,
        tenant_id="tenant-other",
        name="Other Policy",
        content="# Other",
        owner="admin-1",
    )
    await db_session.commit()

    response = await client.get(
        f"/policies/{policy.id}",
        headers=_auth_headers(role="admin", tenant_id="tenant-abc"),
    )
    assert response.status_code == 404


@pytest.mark.anyio
async def test_list_versions(client, db_session):
    """GET /policies/{id}/versions returns version history."""
    policy = await policy_manager.create_policy(
        session=db_session,
        tenant_id="tenant-abc",
        name="Versioned",
        content="# V1",
        owner="admin-1",
    )
    await policy_manager.publish_new_version(
        session=db_session,
        policy_id=policy.id,
        content="# V2",
        change_summary="Update",
        publisher="admin-1",
    )
    await db_session.commit()

    response = await client.get(
        f"/policies/{policy.id}/versions",
        headers=_auth_headers(role="admin"),
    )
    assert response.status_code == 200
    body = response.json()
    assert len(body) == 2
    assert body[0]["version_number"] == 2
    assert body[1]["version_number"] == 1


@pytest.mark.anyio
async def test_publish_version_as_admin(client, db_session):
    """POST /policies/{id}/versions publishes a new version."""
    policy = await policy_manager.create_policy(
        session=db_session,
        tenant_id="tenant-abc",
        name="Publishable",
        content="# V1",
        owner="admin-1",
    )
    await db_session.commit()

    response = await client.post(
        f"/policies/{policy.id}/versions",
        headers=_auth_headers(role="admin"),
        json={
            "content": "# V2",
            "change_summary": "Added requirements",
        },
    )
    assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
    body = response.json()
    assert body["version_number"] == 2
    assert body["change_summary"] == "Added requirements"


@pytest.mark.anyio
async def test_acknowledge_current_version(client, db_session):
    """POST /policies/{id}/acknowledge records acknowledgment."""
    policy = await policy_manager.create_policy(
        session=db_session,
        tenant_id="tenant-abc",
        name="Ack Policy",
        content="# Ack",
        owner="admin-1",
    )
    await db_session.commit()

    response = await client.post(
        f"/policies/{policy.id}/acknowledge",
        headers=_auth_headers(role="analyst", user_id="user-456"),
        json={"signature": "sha256:deadbeef"},
    )
    assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
    body = response.json()
    assert body["user_id"] == "user-456"
    # HIGH-5 audit fix — user-supplied "sha256:deadbeef" was the VULNERABLE
    # behaviour (Codex HIGH-004). Server now stores its own HMAC-SHA256.
    # Original assertion `body["signature"] == "sha256:deadbeef"` captured the
    # bug; the new assertion confirms the user-supplied value is rejected and
    # a 64-hex server signature is stored instead.
    assert body["signature"] != "sha256:deadbeef"
    assert len(body["signature"]) == 64
    assert body["policy_version_id"] == policy.current_version_id


@pytest.mark.anyio
async def test_get_pending_acknowledgments(client, db_session):
    """GET /policies/pending returns current user's pending policies."""
    policy = await policy_manager.create_policy(
        session=db_session,
        tenant_id="tenant-abc",
        name="Pending",
        content="# Pending",
        owner="admin-1",
    )
    await db_session.commit()

    response = await client.get(
        "/policies/pending",
        headers=_auth_headers(role="analyst", user_id="user-456"),
    )
    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["name"] == "Pending"


@pytest.mark.anyio
async def test_get_expiring_as_admin(client, db_session):
    """GET /policies/expiring returns policies expiring soon (admin only)."""
    from datetime import datetime, timedelta

    await policy_manager.create_policy(
        session=db_session,
        tenant_id="tenant-abc",
        name="Soon Expiring",
        content="# Expire",
        owner="admin-1",
        expires_at=datetime.utcnow() + timedelta(days=5),
    )
    await db_session.commit()

    response = await client.get(
        "/policies/expiring",
        headers=_auth_headers(role="admin"),
    )
    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["name"] == "Soon Expiring"


@pytest.mark.anyio
async def test_get_expiring_forbidden_for_non_admin(client):
    """GET /policies/expiring returns 403 for non-admin."""
    response = await client.get(
        "/policies/expiring",
        headers=_auth_headers(role="analyst"),
    )
    assert response.status_code == 403
