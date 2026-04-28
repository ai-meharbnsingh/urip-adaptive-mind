"""
TDD — Auditor invitation flow (P2B.10)

Endpoints exercised:
  POST   /auditor-invitations         (admin)   — create invitation
  POST   /auditor-invitations/accept            — auditor redeems token
  DELETE /auditor-invitations/{id}    (admin)   — revoke

Token model (decided & documented):
  Invitation token = opaque random secret (URL-safe, 32 bytes), hashed (SHA-256)
  before storage. Auditor JWT = HS256 with claims
    {sub: auditor_email, kind: "auditor", access_id, tenant_id, framework_id,
     period_start, period_end, exp}
  Justification: opaque tokens cannot be tampered with at rest; JWT after
  acceptance gives stateless verification per request without DB hit.
"""
from __future__ import annotations

import time
import uuid
from datetime import datetime, timedelta

import pytest
# CRIT-005 (Z2.1): migrated python-jose -> PyJWT (HS256 surface identical)
import jwt
from sqlalchemy import select

from compliance_backend.models.auditor import AuditorAccess

STANDALONE_SECRET = "test-secret-standalone"


def _admin_token(tenant_id: str = "tenant-aud-flow", role: str = "admin") -> str:
    payload = {
        "sub": "user-admin-1",
        "tenant_id": tenant_id,
        "role": role,
        "exp": int(time.time()) + 3600,
        "iss": "compliance",
    }
    return jwt.encode(payload, STANDALONE_SECRET, algorithm="HS256")


def _admin_headers(tenant_id: str = "tenant-aud-flow") -> dict:
    return {"Authorization": f"Bearer {_admin_token(tenant_id)}"}


# ---------------------------------------------------------------------------
# POST /auditor-invitations
# ---------------------------------------------------------------------------

@pytest.mark.anyio
async def test_create_invitation_returns_url_with_token(client):
    """Admin creates an invitation; response includes the redemption URL with token."""
    now = datetime.utcnow()
    body = {
        "auditor_email": "auditor@example.com",
        "framework_id": "fw-create-001",
        "audit_period_start": now.isoformat(),
        "audit_period_end": (now + timedelta(days=30)).isoformat(),
        "expires_at": (now + timedelta(days=7)).isoformat(),
    }
    resp = await client.post(
        "/auditor-invitations",
        headers=_admin_headers("tenant-create-inv"),
        json=body,
    )
    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert data["auditor_email"] == "auditor@example.com"
    assert data["framework_id"] == "fw-create-001"
    assert "invitation_url" in data
    assert "token=" in data["invitation_url"]
    assert "id" in data


@pytest.mark.anyio
async def test_create_invitation_requires_admin_role(client):
    """Non-admin (viewer) cannot create invitations."""
    now = datetime.utcnow()
    body = {
        "auditor_email": "x@y.com",
        "framework_id": "fw-x",
        "audit_period_start": now.isoformat(),
        "audit_period_end": (now + timedelta(days=10)).isoformat(),
        "expires_at": (now + timedelta(days=10)).isoformat(),
    }
    headers = {"Authorization": f"Bearer {_admin_token(role='viewer')}"}
    resp = await client.post("/auditor-invitations", headers=headers, json=body)
    assert resp.status_code == 403


@pytest.mark.anyio
async def test_create_invitation_requires_auth(client):
    resp = await client.post("/auditor-invitations", json={})
    assert resp.status_code == 401


@pytest.mark.anyio
async def test_create_invitation_period_must_be_chronological(client):
    """audit_period_end must be after audit_period_start."""
    now = datetime.utcnow()
    body = {
        "auditor_email": "x@y.com",
        "framework_id": "fw-x",
        "audit_period_start": now.isoformat(),
        "audit_period_end": (now - timedelta(days=1)).isoformat(),
        "expires_at": (now + timedelta(days=10)).isoformat(),
    }
    resp = await client.post(
        "/auditor-invitations", headers=_admin_headers(), json=body,
    )
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# POST /auditor-invitations/accept
# ---------------------------------------------------------------------------

@pytest.mark.anyio
async def test_accept_invitation_returns_auditor_jwt(client):
    """Auditor redeems token → gets a JWT with kind='auditor'."""
    now = datetime.utcnow()
    create_resp = await client.post(
        "/auditor-invitations",
        headers=_admin_headers("tenant-accept-test"),
        json={
            "auditor_email": "accepter@x.com",
            "framework_id": "fw-accept",
            "audit_period_start": now.isoformat(),
            "audit_period_end": (now + timedelta(days=30)).isoformat(),
            "expires_at": (now + timedelta(days=7)).isoformat(),
        },
    )
    assert create_resp.status_code == 201
    url = create_resp.json()["invitation_url"]
    token = url.split("token=")[1]

    accept_resp = await client.post(
        "/auditor-invitations/accept", json={"token": token}
    )
    assert accept_resp.status_code == 200, accept_resp.text
    body = accept_resp.json()
    assert "auditor_jwt" in body
    # PyJWT (CRIT-005 Z2.1) — auditor JWTs carry ``aud="compliance-auditor"``
    # so decode must pass the matching audience (jose silently ignored aud).
    decoded = jwt.decode(
        body["auditor_jwt"],
        STANDALONE_SECRET,
        algorithms=["HS256"],
        audience="compliance-auditor",
    )
    assert decoded["kind"] == "auditor"
    assert decoded["tenant_id"] == "tenant-accept-test"
    assert decoded["framework_id"] == "fw-accept"
    assert decoded["sub"] == "accepter@x.com"
    assert "exp" in decoded


@pytest.mark.anyio
async def test_accept_invitation_invalid_token_returns_401(client):
    resp = await client.post(
        "/auditor-invitations/accept", json={"token": "this-token-does-not-exist"}
    )
    assert resp.status_code == 401


@pytest.mark.anyio
async def test_accept_invitation_revoked_token_returns_401(client, db_session):
    """Once revoked, the invitation cannot be redeemed."""
    now = datetime.utcnow()
    create_resp = await client.post(
        "/auditor-invitations",
        headers=_admin_headers("tenant-revoke-test"),
        json={
            "auditor_email": "revokee@x.com",
            "framework_id": "fw-rev",
            "audit_period_start": now.isoformat(),
            "audit_period_end": (now + timedelta(days=30)).isoformat(),
            "expires_at": (now + timedelta(days=7)).isoformat(),
        },
    )
    invitation_id = create_resp.json()["id"]
    url = create_resp.json()["invitation_url"]
    token = url.split("token=")[1]

    # Revoke
    del_resp = await client.delete(
        f"/auditor-invitations/{invitation_id}",
        headers=_admin_headers("tenant-revoke-test"),
    )
    assert del_resp.status_code == 204

    # Try to accept
    accept_resp = await client.post(
        "/auditor-invitations/accept", json={"token": token}
    )
    assert accept_resp.status_code == 401


@pytest.mark.anyio
async def test_accept_invitation_expired_token_returns_401(client, db_session):
    """An invitation whose expires_at has passed cannot be redeemed."""
    # Insert directly so we can backdate expires_at.
    import hashlib, secrets
    from compliance_backend.services.auditor_service import AuditorService

    raw_token = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(raw_token.encode()).hexdigest()

    now = datetime.utcnow()
    rec = AuditorAccess(
        tenant_id="tenant-exp",
        auditor_email="exp@x.com",
        framework_id="fw-exp",
        audit_period_start=now,
        audit_period_end=now + timedelta(days=30),
        invited_by_user_id="u-admin",
        invitation_token_hash=token_hash,
        expires_at=now - timedelta(days=1),  # already expired
    )
    db_session.add(rec)
    await db_session.commit()

    accept_resp = await client.post(
        "/auditor-invitations/accept", json={"token": raw_token}
    )
    assert accept_resp.status_code == 401


@pytest.mark.anyio
async def test_accept_invitation_marks_accepted_at(client, db_session):
    now = datetime.utcnow()
    create_resp = await client.post(
        "/auditor-invitations",
        headers=_admin_headers("tenant-acc-mark"),
        json={
            "auditor_email": "marker@x.com",
            "framework_id": "fw-mark",
            "audit_period_start": now.isoformat(),
            "audit_period_end": (now + timedelta(days=30)).isoformat(),
            "expires_at": (now + timedelta(days=7)).isoformat(),
        },
    )
    invitation_id = create_resp.json()["id"]
    url = create_resp.json()["invitation_url"]
    token = url.split("token=")[1]

    await client.post("/auditor-invitations/accept", json={"token": token})

    rec = (await db_session.execute(
        select(AuditorAccess).where(AuditorAccess.id == invitation_id)
    )).scalar_one()
    assert rec.accepted_at is not None


# ---------------------------------------------------------------------------
# DELETE /auditor-invitations/{id}
# ---------------------------------------------------------------------------

@pytest.mark.anyio
async def test_revoke_invitation_sets_is_revoked(client, db_session):
    now = datetime.utcnow()
    create_resp = await client.post(
        "/auditor-invitations",
        headers=_admin_headers("tenant-revoke-flag"),
        json={
            "auditor_email": "revflag@x.com",
            "framework_id": "fw-revflag",
            "audit_period_start": now.isoformat(),
            "audit_period_end": (now + timedelta(days=30)).isoformat(),
            "expires_at": (now + timedelta(days=7)).isoformat(),
        },
    )
    invitation_id = create_resp.json()["id"]

    del_resp = await client.delete(
        f"/auditor-invitations/{invitation_id}",
        headers=_admin_headers("tenant-revoke-flag"),
    )
    assert del_resp.status_code == 204

    rec = (await db_session.execute(
        select(AuditorAccess).where(AuditorAccess.id == invitation_id)
    )).scalar_one()
    assert rec.is_revoked is True


@pytest.mark.anyio
async def test_revoke_invitation_other_tenant_returns_404(client):
    """A tenant cannot revoke another tenant's invitation."""
    now = datetime.utcnow()
    create_resp = await client.post(
        "/auditor-invitations",
        headers=_admin_headers("tenant-rev-A"),
        json={
            "auditor_email": "owner@x.com",
            "framework_id": "fw-cross",
            "audit_period_start": now.isoformat(),
            "audit_period_end": (now + timedelta(days=30)).isoformat(),
            "expires_at": (now + timedelta(days=7)).isoformat(),
        },
    )
    invitation_id = create_resp.json()["id"]

    del_resp = await client.delete(
        f"/auditor-invitations/{invitation_id}",
        headers=_admin_headers("tenant-rev-B"),  # different tenant
    )
    assert del_resp.status_code == 404
