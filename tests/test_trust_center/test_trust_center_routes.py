"""End-to-end Trust Center router tests — public landing → request → approve → download."""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.trust_center import TrustCenterDocument


@pytest.mark.asyncio
async def test_landing_returns_published_docs_only(
    client: AsyncClient, db_session: AsyncSession, default_tenant
):
    db_session.add(
        TrustCenterDocument(
            id=uuid.uuid4(),
            tenant_id=default_tenant.id,
            doc_type="SOC2_REPORT",
            title="SOC 2 Type II",
            file_storage_uri="s3://soc2.pdf",
            is_published=True,
            requires_nda=True,
        )
    )
    db_session.add(
        TrustCenterDocument(
            id=uuid.uuid4(),
            tenant_id=default_tenant.id,
            doc_type="POLICY",
            title="Internal staging doc",
            file_storage_uri="s3://stage.pdf",
            is_published=False,
            requires_nda=False,
        )
    )
    await db_session.commit()
    resp = await client.get(f"/trust/{default_tenant.slug}")
    assert resp.status_code == 200
    data = resp.json()
    titles = [d["title"] for d in data["documents"]]
    assert "SOC 2 Type II" in titles
    assert "Internal staging doc" not in titles


@pytest.mark.asyncio
async def test_landing_404_for_unknown_slug(client: AsyncClient):
    resp = await client.get("/trust/no-such-tenant")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_request_access_endpoint_creates_pending(
    client: AsyncClient, db_session: AsyncSession, default_tenant
):
    doc = TrustCenterDocument(
        id=uuid.uuid4(),
        tenant_id=default_tenant.id,
        doc_type="SOC2_REPORT",
        title="SOC2",
        file_storage_uri="s3://soc2.pdf",
        is_published=True,
        requires_nda=True,
    )
    db_session.add(doc)
    await db_session.commit()
    resp = await client.post(
        f"/trust/{default_tenant.slug}/request-access",
        json={
            "doc_id": str(doc.id),
            "requester_email": "buyer@acme.example.com",
            "requester_company": "Acme Inc.",
        },
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["status"] == "pending"
    assert data["nda_required"] is True


@pytest.mark.asyncio
async def test_full_flow_publish_request_approve_download(
    client: AsyncClient,
    db_session: AsyncSession,
    auth_headers: dict,
    default_tenant,
    tmp_path,
):
    """End-to-end happy path now exercises the REAL streaming download.

    NOTE — original v3 test expected a JSON envelope; v5 promoted Trust Center
    streaming from PARTIAL → LIVE so the download endpoint streams bytes.  The
    JSON envelope is gone by design.
    """
    # Use a real local file (file:// scheme) so the download streams real bytes.
    local_file = tmp_path / "policy.pdf"
    body = b"%PDF-1.4 policy bytes for full-flow test " * 4
    local_file.write_bytes(body)

    pub_resp = await client.post(
        "/api/trust-center/documents",
        json={
            "doc_type": "POLICY",
            "title": "Public Policy",
            "file_storage_uri": f"file://{local_file}",
            "requires_nda": False,
            "is_published": True,
        },
        headers=auth_headers,
    )
    assert pub_resp.status_code == 200, pub_resp.text
    doc_id = pub_resp.json()["id"]

    # Public buyer requests access
    req_resp = await client.post(
        f"/trust/{default_tenant.slug}/request-access",
        json={"doc_id": doc_id, "requester_email": "buyer@acme.example.com"},
    )
    assert req_resp.status_code == 200
    request_id = req_resp.json()["request_id"]

    # Admin approves
    appr_resp = await client.post(
        f"/api/trust-center/access-requests/{request_id}/approve",
        headers=auth_headers,
    )
    assert appr_resp.status_code == 200, appr_resp.text
    token = appr_resp.json()["access_token"]
    assert token

    # Buyer downloads — must now return the real bytes from disk.
    dl_resp = await client.get(f"/trust/access/{token}/download/{doc_id}")
    assert dl_resp.status_code == 200
    assert dl_resp.content == body
    assert "attachment" in dl_resp.headers.get("content-disposition", "").lower()


@pytest.mark.asyncio
async def test_download_with_invalid_token_returns_403(
    client: AsyncClient, db_session: AsyncSession, default_tenant
):
    doc = TrustCenterDocument(
        id=uuid.uuid4(),
        tenant_id=default_tenant.id,
        doc_type="POLICY",
        title="Policy",
        file_storage_uri="s3://policy.pdf",
        is_published=True,
        requires_nda=False,
    )
    db_session.add(doc)
    await db_session.commit()
    resp = await client.get(f"/trust/access/bogus-token/download/{doc.id}")
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_admin_endpoints_require_auth(client: AsyncClient):
    resp = await client.get("/api/trust-center/documents")
    assert resp.status_code in (401, 403)
