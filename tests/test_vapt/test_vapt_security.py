"""
Security tests:
  - vendor JWT cannot be substituted for a regular user JWT and vice-versa
  - vendor cannot see another vendor's submissions
  - revoked vendor → 401 even with previously-valid JWT
  - expired JWT → 401
  - tampered JWT → 401
  - cross-tenant fetch is blocked
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import jwt as pyjwt
import pytest
from sqlalchemy import select

from backend.config import settings
from backend.middleware.auth import create_access_token
from backend.models.vapt_vendor import VaptVendor
from backend.services.vapt_vendor_service import (
    VAPT_JWT_AUDIENCE,
    VAPT_JWT_ISSUER,
    VAPT_JWT_TYPE,
    VaptVendorService,
)


@pytest.mark.asyncio
async def test_regular_user_jwt_rejected_on_vendor_endpoints(
    client, auth_headers
):
    """A normal user JWT (kind != vapt_vendor) must NOT pass vapt_vendor middleware."""
    resp = await client.get("/api/vapt-vendor/profile", headers=auth_headers)
    # The user JWT has aud=urip-tenant not urip-vapt-vendor → 401
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_vendor_jwt_rejected_on_admin_endpoints(
    client, vapt_headers
):
    """A vendor JWT (aud=urip-vapt-vendor) must NOT pass the regular user middleware."""
    resp = await client.get("/api/vapt-vendors", headers=vapt_headers)
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_revoked_vendor_jwt_rejected(
    client, db_session, vapt_headers, vapt_vendor
):
    """Revoke the vendor → previously-valid JWT must now 401."""
    # First call works
    ok = await client.get("/api/vapt-vendor/profile", headers=vapt_headers)
    assert ok.status_code == 200

    # Suspend the vendor
    svc = VaptVendorService(db=db_session)
    await svc.revoke_vendor(vapt_vendor.id, vapt_vendor.tenant_id)
    await db_session.commit()

    # Now the same JWT must fail
    resp = await client.get("/api/vapt-vendor/profile", headers=vapt_headers)
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_expired_vendor_jwt_rejected(client, db_session, vapt_vendor):
    """Manually mint a token with exp in the past → 401."""
    svc = VaptVendorService(db=db_session)
    expired = datetime.now(timezone.utc) - timedelta(seconds=10)
    # Manually craft an expired token
    payload = {
        "sub": vapt_vendor.contact_email,
        "type": VAPT_JWT_TYPE,
        "vendor_id": str(vapt_vendor.id),
        "tenant_id": str(vapt_vendor.tenant_id),
        "exp": int(expired.timestamp()),
        "iss": VAPT_JWT_ISSUER,
        "aud": VAPT_JWT_AUDIENCE,
    }
    expired_token = pyjwt.encode(
        payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM
    )
    resp = await client.get(
        "/api/vapt-vendor/profile",
        headers={"Authorization": f"Bearer {expired_token}"},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_tampered_vendor_jwt_rejected(client, vapt_headers):
    """Flipping a single character in the signature → 401."""
    bad_token = vapt_headers["Authorization"].replace("Bearer ", "")
    bad_token = bad_token[:-1] + ("A" if bad_token[-1] != "A" else "B")
    resp = await client.get(
        "/api/vapt-vendor/profile",
        headers={"Authorization": f"Bearer {bad_token}"},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_vendor_cannot_see_other_vendors_submissions(
    client, db_session, vapt_vendor, second_tenant_vendor, vapt_headers
):
    """
    Two vendors in DIFFERENT tenants. Vendor A's JWT should never surface
    Vendor B's submissions. (The router scopes by JWT-derived vendor_id;
    second_tenant_vendor lives in a different tenant for extra strength.)
    """
    # Have second_tenant_vendor submit something via the service
    svc = VaptVendorService(db=db_session)
    await svc.submit_finding(
        vendor=second_tenant_vendor,
        finding_title="Other-tenant secret bug",
        cvss_score=9.0,
        severity="critical",
        schedule_enrichment=False,
    )
    await db_session.commit()

    # Vendor A lists their own submissions — must not see Vendor B's
    resp = await client.get(
        "/api/vapt-vendor/submissions", headers=vapt_headers
    )
    assert resp.status_code == 200
    body = resp.json()
    titles = [s["finding_title"] for s in body["items"]]
    assert "Other-tenant secret bug" not in titles


@pytest.mark.asyncio
async def test_vendor_get_submission_by_id_blocks_cross_vendor(
    client, db_session, vapt_vendor, second_tenant_vendor, vapt_headers
):
    """
    Even if vendor A guesses vendor B's submission UUID, GET /vapt-vendor/
    submissions/{id} must 404 (NOT 200) because of the WHERE vendor_id filter.
    """
    svc = VaptVendorService(db=db_session)
    created = await svc.submit_finding(
        vendor=second_tenant_vendor,
        finding_title="Hidden",
        cvss_score=8.0,
        severity="high",
        schedule_enrichment=False,
    )
    await db_session.commit()

    other_id = str(created.submission.id)
    resp = await client.get(
        f"/api/vapt-vendor/submissions/{other_id}", headers=vapt_headers
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_admin_cannot_see_other_tenants_vendors(
    client, auth_headers, second_tenant_vendor, vm_subscription
):
    """Tenant admin's listing must not reveal vendors from other tenants."""
    resp = await client.get("/api/vapt-vendors", headers=auth_headers)
    assert resp.status_code == 200
    ids = [v["id"] for v in resp.json()["items"]]
    assert str(second_tenant_vendor.id) not in ids


@pytest.mark.asyncio
async def test_admin_cannot_get_vendor_in_other_tenant_404(
    client, auth_headers, second_tenant_vendor, vm_subscription
):
    """Direct GET on cross-tenant vendor UUID → 404."""
    resp = await client.get(
        f"/api/vapt-vendors/{second_tenant_vendor.id}", headers=auth_headers
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_user_jwt_with_wrong_audience_rejected(
    client, db_session, default_tenant, vapt_vendor
):
    """
    Forged JWT with aud=urip-vapt-vendor but type='regular_user' → 401
    (defence in depth: JWT decode + claim check).
    """
    payload = {
        "sub": "attacker@evil.test",
        "type": "regular_user",  # wrong type
        "vendor_id": str(vapt_vendor.id),
        "tenant_id": str(vapt_vendor.tenant_id),
        "exp": int(
            (datetime.now(timezone.utc) + timedelta(hours=1)).timestamp()
        ),
        "iss": VAPT_JWT_ISSUER,
        "aud": VAPT_JWT_AUDIENCE,
    }
    token = pyjwt.encode(
        payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM
    )
    resp = await client.get(
        "/api/vapt-vendor/profile",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_jwt_with_unknown_vendor_id_rejected(
    client, db_session, default_tenant
):
    """Vendor_id present in JWT but no row in DB → 401 (DB layer enforcement)."""
    fake_vendor_id = str(uuid.uuid4())
    payload = {
        "sub": "ghost@test.test",
        "type": VAPT_JWT_TYPE,
        "vendor_id": fake_vendor_id,
        "tenant_id": str(default_tenant.id),
        "exp": int(
            (datetime.now(timezone.utc) + timedelta(hours=1)).timestamp()
        ),
        "iss": VAPT_JWT_ISSUER,
        "aud": VAPT_JWT_AUDIENCE,
    }
    token = pyjwt.encode(
        payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM
    )
    resp = await client.get(
        "/api/vapt-vendor/profile",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_missing_authorization_header_rejected(client):
    resp = await client.get("/api/vapt-vendor/profile")
    assert resp.status_code == 401
