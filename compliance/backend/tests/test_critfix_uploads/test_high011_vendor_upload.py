"""
HIGH-011 (vendor side) — vendor document upload guards.

Same allowlist + size cap + filename sanitisation as evidence upload, applied
to POST /vendors/{vendor_id}/documents.
"""
import io
import time
import uuid

import pytest
# CRIT-005 (Z2.1): migrated python-jose -> PyJWT (HS256 surface identical)
import jwt

from compliance_backend.models.vendor import Vendor
from compliance_backend.services.control_rules import load_builtin_rules

STANDALONE_SECRET = "test-secret-standalone"
load_builtin_rules()


def _make_token(tenant_id: str, role: str = "admin") -> str:
    payload = {
        "sub": "user-vd-1",
        "tenant_id": tenant_id,
        "role": role,
        "exp": int(time.time()) + 3600,
        "iss": "compliance",
    }
    return jwt.encode(payload, STANDALONE_SECRET, algorithm="HS256")


def _headers(tenant_id: str) -> dict:
    return {"Authorization": f"Bearer {_make_token(tenant_id)}"}


async def _seed_vendor(db_session, tenant_id: str) -> Vendor:
    from datetime import date, datetime, timedelta
    v = Vendor(
        id=str(uuid.uuid4()),
        tenant_id=tenant_id,
        name=f"Vendor {uuid.uuid4().hex[:6]}",
        criticality="medium",
        contact_email="x@y.z",
        contact_name="X",
        status="active",
        onboarded_at=datetime.utcnow(),
        next_review_at=date.today() + timedelta(days=365),
    )
    db_session.add(v)
    await db_session.flush()
    await db_session.commit()
    return v


@pytest.mark.anyio
async def test_vendor_doc_oversize_413(client, db_session):
    tenant = "tenant-vd-size"
    v = await _seed_vendor(db_session, tenant)
    big = b"\0" * (51 * 1024 * 1024)
    resp = await client.post(
        f"/vendors/{v.id}/documents",
        headers=_headers(tenant),
        files={"file": ("big.pdf", io.BytesIO(big), "application/pdf")},
        data={"document_type": "SOC2_REPORT"},
    )
    assert resp.status_code == 413, (
        f"51MB vendor doc upload should be 413, got {resp.status_code}: "
        f"{resp.text[:200]}"
    )


@pytest.mark.anyio
async def test_vendor_doc_disallowed_type_422(client, db_session):
    tenant = "tenant-vd-type"
    v = await _seed_vendor(db_session, tenant)
    resp = await client.post(
        f"/vendors/{v.id}/documents",
        headers=_headers(tenant),
        files={
            "file": (
                "evil.exe",
                io.BytesIO(b"MZ\x90\x00fake-pe-header"),
                "application/x-msdownload",
            )
        },
        data={"document_type": "SOC2_REPORT"},
    )
    assert resp.status_code == 422, (
        f".exe vendor doc upload should be 422, got {resp.status_code}: "
        f"{resp.text[:200]}"
    )


@pytest.mark.anyio
async def test_vendor_doc_filename_sanitised(client, db_session):
    """L2 (CL-NEW-2): API response does NOT expose ``storage_uri``; verify the
    sanitisation property at the storage layer by reading ``VendorDocument``
    directly from ``db_session``."""
    from compliance_backend.models.vendor import VendorDocument

    tenant = "tenant-vd-fn"
    v = await _seed_vendor(db_session, tenant)
    resp = await client.post(
        f"/vendors/{v.id}/documents",
        headers=_headers(tenant),
        files={
            "file": (
                "../../etc/passwd",
                io.BytesIO(b"root:x:0:0:root"),
                "text/plain",
            )
        },
        data={"document_type": "SOC2_REPORT"},
    )
    assert resp.status_code == 200 or resp.status_code == 201, resp.text
    doc_id = resp.json()["id"]
    record = await db_session.get(VendorDocument, doc_id)
    assert record is not None, "vendor document row must persist"
    assert ".." not in record.storage_uri
    assert "etc/passwd" not in record.storage_uri.lower()
