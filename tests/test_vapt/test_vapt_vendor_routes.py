"""HTTP-level tests for both admin (User JWT) and vendor (vapt_vendor JWT) routers."""
from __future__ import annotations

import pytest


# ---------------------------------------------------------------------------
#  Admin: invite vendor via HTTP
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_admin_invite_vendor_returns_201_with_invitation_url(
    client, default_tenant, auth_headers, vm_subscription
):
    resp = await client.post(
        "/api/vapt-vendors",
        headers=auth_headers,
        json={
            "name": "Pentestify",
            "contact_email": "lead@pentestify.example.com",
            "ttl_days": 14,
        },
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["name"] == "Pentestify"
    assert body["status"] == "active"
    assert body["invitation_url"] is not None
    assert "vapt-portal-login.html?token=" in body["invitation_url"]


@pytest.mark.asyncio
async def test_admin_invite_vendor_requires_ciso_role(
    client, default_tenant, it_team_headers, vm_subscription
):
    """it_team users do NOT have role >= ciso → 403."""
    resp = await client.post(
        "/api/vapt-vendors",
        headers=it_team_headers,
        json={"name": "X", "contact_email": "x@example.com"},
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_admin_list_vendors(
    client, auth_headers, vapt_vendor, vm_subscription
):
    resp = await client.get("/api/vapt-vendors", headers=auth_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] >= 1
    assert any(v["id"] == str(vapt_vendor.id) for v in body["items"])


@pytest.mark.asyncio
async def test_admin_get_vendor_detail(
    client, auth_headers, vapt_vendor, vm_subscription
):
    resp = await client.get(
        f"/api/vapt-vendors/{vapt_vendor.id}", headers=auth_headers
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["id"] == str(vapt_vendor.id)
    assert body["submission_count"] == 0


@pytest.mark.asyncio
async def test_admin_revoke_vendor(
    client, auth_headers, vapt_vendor, vm_subscription
):
    resp = await client.delete(
        f"/api/vapt-vendors/{vapt_vendor.id}", headers=auth_headers
    )
    assert resp.status_code == 204

    # Detail still readable but status now suspended
    detail = await client.get(
        f"/api/vapt-vendors/{vapt_vendor.id}", headers=auth_headers
    )
    assert detail.status_code == 200
    assert detail.json()["status"] == "suspended"


# ---------------------------------------------------------------------------
#  Public: vendor accepts invitation
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_vendor_accept_invitation_returns_jwt(
    client, vapt_invitation
):
    raw_token, inv = vapt_invitation
    resp = await client.post(
        "/api/vapt-vendor/invitations/accept", json={"token": raw_token}
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert "vapt_vendor_jwt" in body
    assert body["vendor"]["status"] == "active"


@pytest.mark.asyncio
async def test_vendor_accept_invitation_bad_token_401(client):
    resp = await client.post(
        "/api/vapt-vendor/invitations/accept",
        json={"token": "x" * 40},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_vendor_accept_invitation_already_redeemed_409(
    client, vapt_invitation
):
    raw_token, _ = vapt_invitation
    first = await client.post(
        "/api/vapt-vendor/invitations/accept", json={"token": raw_token}
    )
    assert first.status_code == 200

    second = await client.post(
        "/api/vapt-vendor/invitations/accept", json={"token": raw_token}
    )
    assert second.status_code == 409


# ---------------------------------------------------------------------------
#  Vendor: profile + listings
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_vendor_profile_returns_own_data(
    client, vapt_headers, vapt_vendor
):
    resp = await client.get("/api/vapt-vendor/profile", headers=vapt_headers)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["id"] == str(vapt_vendor.id)
    assert body["contact_email"] == vapt_vendor.contact_email


@pytest.mark.asyncio
async def test_vendor_profile_requires_jwt(client):
    resp = await client.get("/api/vapt-vendor/profile")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_vendor_list_submissions_empty_initially(
    client, vapt_headers, vapt_vendor
):
    resp = await client.get("/api/vapt-vendor/submissions", headers=vapt_headers)
    assert resp.status_code == 200
    assert resp.json()["total"] == 0


# ---------------------------------------------------------------------------
#  Submission via multipart
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_vendor_submit_finding_creates_risk(
    client, vapt_headers, vapt_vendor, db_session
):
    """End-to-end: multipart submit → 201 → linked Risk row exists."""
    files = {
        "evidence": ("poc.txt", b"# PoC log content", "text/plain"),
    }
    data = {
        "finding_title": "RCE in /admin/login",
        "cvss_score": "9.8",
        "severity": "critical",
        "cve_id": "CVE-2026-9999",
        "affected_asset_hostname": "admin.urip.test",
        "affected_asset_ip": "10.0.0.42",
        "exploit_maturity": "weaponized",
        "description": "Unauth RCE via crafted POST.",
        "remediation_recommendation": "Patch to v2.3.4 + WAF rule.",
    }
    resp = await client.post(
        "/api/vapt-vendor/submissions",
        headers=vapt_headers,
        data=data,
        files=files,
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["finding_title"] == "RCE in /admin/login"
    assert body["risk_record_id"] is not None
    assert body["risk_id_label"] is not None
    assert body["risk_id_label"].startswith("RISK-")
    assert body["evidence_filename"] == "poc.txt"
    assert body["status"] == "submitted"
    assert body["severity"] == "critical"

    # Verify risk row actually exists in DB
    from backend.models.risk import Risk
    from sqlalchemy import select
    res = await db_session.execute(
        select(Risk).where(Risk.id == body["risk_record_id"])
    )
    risk = res.scalar_one_or_none()
    assert risk is not None
    assert risk.tenant_id == vapt_vendor.tenant_id
    assert risk.cve_id == "CVE-2026-9999"
    assert float(risk.cvss_score) == 9.8
    assert risk.source.startswith("vapt_vendor:")
    assert risk.status == "open"
    assert risk.composite_score is not None  # computed inline


@pytest.mark.asyncio
async def test_vendor_submit_finding_rejects_oversize_evidence(
    client, vapt_headers, vapt_vendor
):
    """50 MB cap — anything bigger → 413."""
    big_blob = b"\x89PNG\r\n\x1a\n" + (b"X" * (51 * 1024 * 1024))
    files = {"evidence": ("big.png", big_blob, "image/png")}
    data = {
        "finding_title": "X",
        "cvss_score": "5.0",
        "severity": "medium",
    }
    resp = await client.post(
        "/api/vapt-vendor/submissions",
        headers=vapt_headers,
        data=data,
        files=files,
    )
    assert resp.status_code == 413


@pytest.mark.asyncio
async def test_vendor_submit_finding_invalid_severity_422(
    client, vapt_headers, vapt_vendor
):
    data = {
        "finding_title": "X",
        "cvss_score": "5.0",
        "severity": "very-bad-not-a-real-severity",
    }
    resp = await client.post(
        "/api/vapt-vendor/submissions", headers=vapt_headers, data=data
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_vendor_submit_finding_invalid_cvss_422(
    client, vapt_headers, vapt_vendor
):
    data = {
        "finding_title": "X",
        "cvss_score": "15.0",  # > 10
        "severity": "high",
    }
    resp = await client.post(
        "/api/vapt-vendor/submissions", headers=vapt_headers, data=data
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_admin_lists_all_submissions(
    client, vapt_headers, auth_headers, vapt_vendor, vm_subscription
):
    # Vendor submits one
    await client.post(
        "/api/vapt-vendor/submissions",
        headers=vapt_headers,
        data={
            "finding_title": "Test",
            "cvss_score": "5.0",
            "severity": "medium",
        },
    )
    # Admin sees it
    resp = await client.get("/api/vapt-submissions", headers=auth_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 1
    assert body["items"][0]["finding_title"] == "Test"
