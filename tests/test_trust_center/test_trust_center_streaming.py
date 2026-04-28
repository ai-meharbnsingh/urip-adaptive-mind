"""
Trust Center file streaming — tests that download endpoint returns ACTUAL bytes,
not a JSON envelope.  Covers:
  - filesystem (file://) URIs use StreamingResponse over open(local_path, 'rb')
  - s3:// URIs go through boto3 streaming get_object
  - Content-Type sniffed from file header / extension
  - Content-Disposition: attachment; filename="..."
  - Range request support (HTTP 206)
  - Audit log row written on download
"""
from __future__ import annotations

import os
import tempfile
import uuid
import unittest.mock as mock

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.audit_log import AuditLog
from backend.models.trust_center import TrustCenterDocument
from backend.services.trust_center_service import (
    approve_access,
    publish_document,
    request_access,
    sign_nda,
)


# -------------------- helpers -------------------- #
@pytest_asyncio.fixture
async def filesystem_doc_with_token(
    db_session: AsyncSession, default_tenant, auth_headers, client
):
    """Publish a document backed by a real local file and grant a token."""
    payload_bytes = b"%PDF-1.4\n% Test SOC2 PDF body\n0123456789ABCDEF" * 64
    fd, local_path = tempfile.mkstemp(suffix=".pdf", prefix="urip_trust_test_")
    try:
        os.write(fd, payload_bytes)
    finally:
        os.close(fd)
    file_uri = f"file://{local_path}"

    # Admin publishes via service directly (router-level test still hits HTTP).
    doc = await publish_document(
        db_session,
        default_tenant.id,
        doc_type="POLICY",
        title="Local test policy",
        file_storage_uri=file_uri,
        requires_nda=False,
        is_published=True,
    )
    await db_session.commit()

    req = await request_access(
        db_session, default_tenant.id, doc.id, requester_email="b@x.test"
    )
    await db_session.commit()

    # User from auth_headers acts as admin approver.
    from backend.models.user import User
    # Ensure there's at least one user; reuse if fixture seeded one.
    q = await db_session.execute(select(User).limit(1))
    user = q.scalar_one_or_none()
    if user is None:
        user = User(
            id=uuid.uuid4(),
            email=f"approver-{uuid.uuid4().hex[:6]}@trust.test",
            hashed_password="x",
            full_name="Trust approver",
            role="ciso",
            is_active=True,
            tenant_id=default_tenant.id,
        )
        db_session.add(user)
        await db_session.commit()

    granted = await approve_access(db_session, req.id, user.id)
    await db_session.commit()
    return doc, granted.raw_token, local_path, payload_bytes


# -------------------- 1. filesystem streaming returns bytes -------------------- #
@pytest.mark.asyncio
async def test_download_returns_bytes_for_filesystem_uri(
    client: AsyncClient, filesystem_doc_with_token
):
    doc, token, local_path, expected_bytes = filesystem_doc_with_token
    resp = await client.get(f"/trust/access/{token}/download/{doc.id}")
    assert resp.status_code == 200
    # Must be the actual bytes from disk, not a JSON envelope.
    assert resp.content == expected_bytes


# -------------------- 2. content-type detection -------------------- #
@pytest.mark.asyncio
async def test_download_sets_content_type_pdf(
    client: AsyncClient, filesystem_doc_with_token
):
    doc, token, _, _ = filesystem_doc_with_token
    resp = await client.get(f"/trust/access/{token}/download/{doc.id}")
    assert resp.status_code == 200
    ct = resp.headers.get("content-type", "")
    assert "pdf" in ct.lower()


# -------------------- 3. content-disposition attachment -------------------- #
@pytest.mark.asyncio
async def test_download_sets_content_disposition_attachment(
    client: AsyncClient, filesystem_doc_with_token
):
    doc, token, _, _ = filesystem_doc_with_token
    resp = await client.get(f"/trust/access/{token}/download/{doc.id}")
    cd = resp.headers.get("content-disposition", "")
    assert "attachment" in cd.lower()
    assert "filename=" in cd.lower()


# -------------------- 4. range request -> 206 -------------------- #
@pytest.mark.asyncio
async def test_download_supports_range_request(
    client: AsyncClient, filesystem_doc_with_token
):
    doc, token, _, expected_bytes = filesystem_doc_with_token
    end = min(99, len(expected_bytes) - 1)
    resp = await client.get(
        f"/trust/access/{token}/download/{doc.id}",
        headers={"Range": f"bytes=0-{end}"},
    )
    assert resp.status_code == 206
    cr = resp.headers.get("content-range", "")
    assert cr.startswith("bytes 0-"), cr
    assert resp.content == expected_bytes[: end + 1]


# -------------------- 5. invalid token still 403 -------------------- #
@pytest.mark.asyncio
async def test_invalid_token_returns_403(
    client: AsyncClient, db_session, default_tenant
):
    doc = await publish_document(
        db_session, default_tenant.id,
        doc_type="POLICY", title="x",
        file_storage_uri="file:///nonexistent/path.pdf",
        is_published=True, requires_nda=False,
    )
    await db_session.commit()
    resp = await client.get(f"/trust/access/bad-token/download/{doc.id}")
    assert resp.status_code == 403


# -------------------- 6. file missing on disk -> 404 -------------------- #
@pytest.mark.asyncio
async def test_filesystem_uri_missing_file_returns_404(
    client: AsyncClient, db_session, default_tenant, auth_headers
):
    bogus = "file:///definitely-not-here-" + uuid.uuid4().hex + ".pdf"
    doc = await publish_document(
        db_session, default_tenant.id,
        doc_type="POLICY", title="missing",
        file_storage_uri=bogus,
        is_published=True, requires_nda=False,
    )
    await db_session.commit()
    req = await request_access(
        db_session, default_tenant.id, doc.id, requester_email="b@x.test"
    )
    await db_session.commit()
    from backend.models.user import User
    # Ensure there's at least one user; reuse if fixture seeded one.
    q = await db_session.execute(select(User).limit(1))
    user = q.scalar_one_or_none()
    if user is None:
        user = User(
            id=uuid.uuid4(),
            email=f"approver-{uuid.uuid4().hex[:6]}@trust.test",
            hashed_password="x",
            full_name="Trust approver",
            role="ciso",
            is_active=True,
            tenant_id=default_tenant.id,
        )
        db_session.add(user)
        await db_session.commit()
    granted = await approve_access(db_session, req.id, user.id)
    await db_session.commit()
    resp = await client.get(f"/trust/access/{granted.raw_token}/download/{doc.id}")
    assert resp.status_code == 404


# -------------------- 7. s3:// URI uses boto3 streaming -------------------- #
@pytest.mark.asyncio
async def test_s3_uri_calls_boto3_streaming_client(
    client: AsyncClient, db_session, default_tenant
):
    """For s3:// URIs the router MUST call boto3 get_object and stream.
    We mock boto3.client to assert the right call shape and return fake bytes.
    """
    fake_bytes = b"hello-from-fake-s3-this-is-the-pdf-body" * 32

    class _FakeBody:
        def __init__(self, b: bytes) -> None:
            self._b = b
            self._pos = 0

        def read(self, amt: int = -1) -> bytes:
            if amt is None or amt < 0:
                out = self._b[self._pos:]
                self._pos = len(self._b)
                return out
            out = self._b[self._pos : self._pos + amt]
            self._pos += len(out)
            return out

        def iter_chunks(self, chunk_size: int = 8192):
            # boto3 StreamingBody supports iter_chunks
            while True:
                chunk = self.read(chunk_size)
                if not chunk:
                    break
                yield chunk

        def close(self) -> None:
            pass

    fake_client = mock.MagicMock()
    fake_client.get_object.return_value = {
        "Body": _FakeBody(fake_bytes),
        "ContentLength": len(fake_bytes),
        "ContentType": "application/pdf",
    }

    doc = await publish_document(
        db_session, default_tenant.id,
        doc_type="POLICY", title="from-s3",
        file_storage_uri="s3://urip-trust/test/object.pdf",
        is_published=True, requires_nda=False,
    )
    await db_session.commit()
    req = await request_access(
        db_session, default_tenant.id, doc.id, requester_email="b@x.test"
    )
    await db_session.commit()
    from backend.models.user import User
    # Ensure there's at least one user; reuse if fixture seeded one.
    q = await db_session.execute(select(User).limit(1))
    user = q.scalar_one_or_none()
    if user is None:
        user = User(
            id=uuid.uuid4(),
            email=f"approver-{uuid.uuid4().hex[:6]}@trust.test",
            hashed_password="x",
            full_name="Trust approver",
            role="ciso",
            is_active=True,
            tenant_id=default_tenant.id,
        )
        db_session.add(user)
        await db_session.commit()
    granted = await approve_access(db_session, req.id, user.id)
    await db_session.commit()

    with mock.patch(
        "backend.routers.trust_center_public._boto3_client",
        return_value=fake_client,
    ):
        resp = await client.get(
            f"/trust/access/{granted.raw_token}/download/{doc.id}"
        )

    assert resp.status_code == 200, resp.text
    # Must have invoked get_object on the right bucket/key
    call = fake_client.get_object.call_args
    assert call is not None, "boto3 get_object was not called"
    kwargs = call.kwargs or call[1]
    assert kwargs.get("Bucket") == "urip-trust"
    assert kwargs.get("Key") == "test/object.pdf"
    assert resp.content == fake_bytes


# -------------------- 8. download writes audit log entry -------------------- #
@pytest.mark.asyncio
async def test_download_writes_audit_log(
    client: AsyncClient, db_session, filesystem_doc_with_token
):
    doc, token, _, _ = filesystem_doc_with_token
    before_q = await db_session.execute(
        select(AuditLog).where(AuditLog.action == "trust_center_download")
    )
    before = list(before_q.scalars().all())

    resp = await client.get(f"/trust/access/{token}/download/{doc.id}")
    assert resp.status_code == 200

    # Re-query for new audit row
    await db_session.commit()
    after_q = await db_session.execute(
        select(AuditLog).where(
            AuditLog.action == "trust_center_download",
            AuditLog.resource_id == doc.id,
        )
    )
    after = list(after_q.scalars().all())
    assert len(after) > len(before), "trust_center_download audit row missing"


# -------------------- 9. approve / deny audit log entries -------------------- #
@pytest.mark.asyncio
async def test_approve_writes_audit_log(
    client: AsyncClient, db_session: AsyncSession, default_tenant, auth_headers
):
    pub_resp = await client.post(
        "/api/trust-center/documents",
        json={
            "doc_type": "POLICY",
            "title": "Audit-able policy",
            "file_storage_uri": "s3://policy.pdf",
            "requires_nda": False,
            "is_published": True,
        },
        headers=auth_headers,
    )
    assert pub_resp.status_code == 200, pub_resp.text
    doc_id = pub_resp.json()["id"]

    req_resp = await client.post(
        f"/trust/{default_tenant.slug}/request-access",
        json={"doc_id": doc_id, "requester_email": "buyer@acme.example.com"},
    )
    assert req_resp.status_code == 200
    request_id = req_resp.json()["request_id"]

    appr_resp = await client.post(
        f"/api/trust-center/access-requests/{request_id}/approve",
        headers=auth_headers,
    )
    assert appr_resp.status_code == 200, appr_resp.text

    await db_session.commit()
    rows = await db_session.execute(
        select(AuditLog).where(AuditLog.action == "trust_center_approve_access")
    )
    rows = list(rows.scalars().all())
    assert len(rows) >= 1, "approve_access must write an audit row"


@pytest.mark.asyncio
async def test_deny_writes_audit_log(
    client: AsyncClient, db_session: AsyncSession, default_tenant, auth_headers
):
    pub_resp = await client.post(
        "/api/trust-center/documents",
        json={
            "doc_type": "POLICY",
            "title": "Deny-able policy",
            "file_storage_uri": "s3://policy.pdf",
            "requires_nda": False,
            "is_published": True,
        },
        headers=auth_headers,
    )
    assert pub_resp.status_code == 200, pub_resp.text
    doc_id = pub_resp.json()["id"]

    req_resp = await client.post(
        f"/trust/{default_tenant.slug}/request-access",
        json={"doc_id": doc_id, "requester_email": "buyer@acme.example.com"},
    )
    request_id = req_resp.json()["request_id"]

    deny_resp = await client.post(
        f"/api/trust-center/access-requests/{request_id}/deny",
        headers=auth_headers,
    )
    assert deny_resp.status_code == 200, deny_resp.text

    await db_session.commit()
    rows = await db_session.execute(
        select(AuditLog).where(AuditLog.action == "trust_center_deny_access")
    )
    rows = list(rows.scalars().all())
    assert len(rows) >= 1, "deny_access must write an audit row"
