"""trust_center_service — service-layer tests against the test DB."""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.trust_center import TrustCenterDocument
from backend.models.user import User
from backend.services.trust_center_service import (
    approve_access,
    deny_access,
    download_document,
    hash_access_token,
    list_published_documents,
    publish_document,
    request_access,
    sign_nda,
)


# --------------------------------------------------------------------------- #
@pytest_asyncio.fixture
async def admin_user(db_session: AsyncSession, default_tenant):
    user = User(
        id=uuid.uuid4(),
        email="admin@trustco.test",
        hashed_password="x",
        full_name="Trust Admin",
        role="ciso",
        team="Security",
        is_active=True,
        tenant_id=default_tenant.id,
    )
    db_session.add(user)
    await db_session.commit()
    return user


# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_publish_document_persists_with_defaults(db_session: AsyncSession, default_tenant):
    doc = await publish_document(
        db_session,
        default_tenant.id,
        doc_type="SOC2_REPORT",
        title="SOC 2 Type II - 2026",
        file_storage_uri="s3://trust/soc2-2026.pdf",
    )
    await db_session.commit()
    assert doc.id is not None
    assert doc.is_published is True
    assert doc.requires_nda is True


@pytest.mark.asyncio
async def test_publish_document_rejects_invalid_type(db_session, default_tenant):
    with pytest.raises(ValueError):
        await publish_document(
            db_session, default_tenant.id,
            doc_type="NOT_A_TYPE", title="x", file_storage_uri="s3://x",
        )


@pytest.mark.asyncio
async def test_list_published_filters_unpublished_and_expired(db_session, default_tenant):
    # Published, valid.
    await publish_document(
        db_session, default_tenant.id,
        doc_type="POLICY", title="Live policy", file_storage_uri="s3://policy.pdf",
        is_published=True,
    )
    # Published but expired.
    await publish_document(
        db_session, default_tenant.id,
        doc_type="ISO_CERT", title="Old cert", file_storage_uri="s3://old.pdf",
        is_published=True, valid_until=datetime.now(timezone.utc) - timedelta(days=1),
    )
    # Unpublished (staged).
    await publish_document(
        db_session, default_tenant.id,
        doc_type="SOC2_REPORT", title="Staged", file_storage_uri="s3://staged.pdf",
        is_published=False,
    )
    await db_session.commit()
    docs = await list_published_documents(db_session, default_tenant.id)
    titles = {d.title for d in docs}
    assert "Live policy" in titles
    assert "Old cert" not in titles
    assert "Staged" not in titles


# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_request_access_creates_pending_row(db_session, default_tenant):
    doc = await publish_document(
        db_session, default_tenant.id,
        doc_type="SOC2_REPORT", title="SOC2", file_storage_uri="s3://soc2.pdf",
    )
    await db_session.commit()
    req = await request_access(
        db_session, default_tenant.id, doc.id,
        requester_email="buyer@acme.test",
        requester_company="Acme Inc.",
    )
    await db_session.commit()
    assert req.status == "pending"
    assert req.access_token_hash is None


@pytest.mark.asyncio
async def test_request_access_rejects_bad_email(db_session, default_tenant):
    doc = await publish_document(
        db_session, default_tenant.id,
        doc_type="SOC2_REPORT", title="SOC2", file_storage_uri="s3://soc2.pdf",
    )
    await db_session.commit()
    with pytest.raises(ValueError):
        await request_access(
            db_session, default_tenant.id, doc.id,
            requester_email="not-an-email",
        )


@pytest.mark.asyncio
async def test_request_access_rejects_unpublished_doc(db_session, default_tenant):
    doc = await publish_document(
        db_session, default_tenant.id,
        doc_type="SOC2_REPORT", title="SOC2", file_storage_uri="s3://soc2.pdf",
        is_published=False,
    )
    await db_session.commit()
    with pytest.raises(ValueError):
        await request_access(
            db_session, default_tenant.id, doc.id,
            requester_email="buyer@acme.test",
        )


# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_approve_access_blocks_when_nda_required_but_unsigned(
    db_session, default_tenant, admin_user
):
    doc = await publish_document(
        db_session, default_tenant.id,
        doc_type="SOC2_REPORT", title="SOC2", file_storage_uri="s3://soc2.pdf",
        requires_nda=True,
    )
    await db_session.commit()
    req = await request_access(
        db_session, default_tenant.id, doc.id,
        requester_email="buyer@acme.test",
    )
    await db_session.commit()
    with pytest.raises(ValueError):
        await approve_access(db_session, req.id, admin_user.id)


@pytest.mark.asyncio
async def test_full_approve_flow_with_nda_signed(
    db_session, default_tenant, admin_user
):
    doc = await publish_document(
        db_session, default_tenant.id,
        doc_type="SOC2_REPORT", title="SOC2", file_storage_uri="s3://soc2.pdf",
        requires_nda=True,
    )
    await db_session.commit()
    req = await request_access(
        db_session, default_tenant.id, doc.id,
        requester_email="buyer@acme.test",
    )
    await db_session.commit()
    await sign_nda(db_session, req.id, signature_text="Jane Doe")
    granted = await approve_access(db_session, req.id, admin_user.id)
    await db_session.commit()
    assert granted is not None
    assert granted.raw_token  # plaintext one-time
    assert granted.request.status == "approved"
    assert granted.request.access_token_hash == hash_access_token(granted.raw_token)
    assert granted.request.expires_at is not None


@pytest.mark.asyncio
async def test_approve_access_no_nda_required(db_session, default_tenant, admin_user):
    doc = await publish_document(
        db_session, default_tenant.id,
        doc_type="POLICY", title="Public policy", file_storage_uri="s3://policy.pdf",
        requires_nda=False,
    )
    await db_session.commit()
    req = await request_access(
        db_session, default_tenant.id, doc.id,
        requester_email="public@anywhere.test",
    )
    await db_session.commit()
    granted = await approve_access(db_session, req.id, admin_user.id)
    assert granted is not None  # no NDA → can approve directly


# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_download_document_succeeds_with_valid_token(
    db_session, default_tenant, admin_user
):
    doc = await publish_document(
        db_session, default_tenant.id,
        doc_type="POLICY", title="Public policy", file_storage_uri="s3://policy.pdf",
        requires_nda=False,
    )
    await db_session.commit()
    req = await request_access(
        db_session, default_tenant.id, doc.id,
        requester_email="x@y.test",
    )
    await db_session.commit()
    granted = await approve_access(db_session, req.id, admin_user.id)
    await db_session.commit()
    handle = await download_document(db_session, granted.raw_token, doc.id)
    assert handle is not None
    assert handle.file_storage_uri == "s3://policy.pdf"


@pytest.mark.asyncio
async def test_download_rejects_wrong_doc_id(db_session, default_tenant, admin_user):
    doc1 = await publish_document(
        db_session, default_tenant.id,
        doc_type="POLICY", title="A", file_storage_uri="s3://a.pdf", requires_nda=False,
    )
    doc2 = await publish_document(
        db_session, default_tenant.id,
        doc_type="POLICY", title="B", file_storage_uri="s3://b.pdf", requires_nda=False,
    )
    await db_session.commit()
    req = await request_access(
        db_session, default_tenant.id, doc1.id,
        requester_email="x@y.test",
    )
    await db_session.commit()
    granted = await approve_access(db_session, req.id, admin_user.id)
    await db_session.commit()
    # Try downloading doc2 with token granted for doc1 — must fail.
    out = await download_document(db_session, granted.raw_token, doc2.id)
    assert out is None


@pytest.mark.asyncio
async def test_download_rejects_invalid_token(db_session, default_tenant):
    doc = await publish_document(
        db_session, default_tenant.id,
        doc_type="POLICY", title="A", file_storage_uri="s3://a.pdf",
    )
    await db_session.commit()
    out = await download_document(db_session, "not-a-real-token", doc.id)
    assert out is None


@pytest.mark.asyncio
async def test_deny_access_marks_request_denied(db_session, default_tenant, admin_user):
    doc = await publish_document(
        db_session, default_tenant.id,
        doc_type="POLICY", title="A", file_storage_uri="s3://a.pdf", requires_nda=False,
    )
    await db_session.commit()
    req = await request_access(
        db_session, default_tenant.id, doc.id,
        requester_email="x@y.test",
    )
    await db_session.commit()
    out = await deny_access(db_session, req.id, admin_user.id)
    assert out is not None
    assert out.status == "denied"
