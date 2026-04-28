"""
TDD — vendor/third-party risk API route tests (P2B.7).

Validates:
  - Auth required
  - Tenant scoping on list/detail
  - Multipart document upload
"""
from __future__ import annotations

import time
from datetime import date, timedelta

import pytest
# CRIT-005 (Z2.1): migrated python-jose -> PyJWT (HS256 surface identical)
import jwt

from compliance_backend.main import app
from compliance_backend.routers.vendors import router as vendors_router


STANDALONE_SECRET = "test-secret-standalone"


def _ensure_router_installed() -> None:
    # Conftest imports app from main which currently only includes frameworks router.
    # For this module’s tests, include vendors router if not already registered.
    for r in app.router.routes:
        if getattr(r, "path", "").startswith("/vendors"):
            return
    app.include_router(vendors_router)


def _auth_headers(tenant_id: str) -> dict:
    payload = {
        "sub": "user-123",
        "tenant_id": tenant_id,
        "role": "admin",
        "exp": int(time.time()) + 3600,
        "iss": "compliance",
    }
    token = jwt.encode(payload, STANDALONE_SECRET, algorithm="HS256")
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.anyio
async def test_vendors_auth_required(client):
    _ensure_router_installed()
    resp = await client.get("/vendors")
    assert resp.status_code == 401


@pytest.mark.anyio
async def test_register_and_list_vendors_tenant_scoped(client):
    _ensure_router_installed()
    # Tenant A registers vendor
    resp = await client.post(
        "/vendors",
        headers=_auth_headers("tenant-a"),
        json={
            "name": "Acme",
            "criticality": "medium",
            "contact_email": "sec@acme.example",
            "contact_name": "Alice",
        },
    )
    assert resp.status_code == 200, resp.text
    vendor_id = resp.json()["id"]

    # Tenant A sees it
    list_a = await client.get("/vendors", headers=_auth_headers("tenant-a"))
    assert list_a.status_code == 200
    ids_a = [v["id"] for v in list_a.json()]
    assert vendor_id in ids_a

    # Tenant B does not
    list_b = await client.get("/vendors", headers=_auth_headers("tenant-b"))
    assert list_b.status_code == 200
    ids_b = [v["id"] for v in list_b.json()]
    assert vendor_id not in ids_b


@pytest.mark.anyio
async def test_vendor_document_upload_multipart_and_expiring_docs(client):
    _ensure_router_installed()
    # Register vendor
    resp = await client.post(
        "/vendors",
        headers=_auth_headers("tenant-a"),
        json={"name": "Acme", "criticality": "high"},
    )
    vendor_id = resp.json()["id"]

    valid_until = (date.today() + timedelta(days=10)).isoformat()
    upload = await client.post(
        f"/vendors/{vendor_id}/documents",
        headers=_auth_headers("tenant-a"),
        data={"document_type": "CONTRACT", "valid_until": valid_until},
        files={"file": ("contract.pdf", b"%PDF-1.4\npdf-bytes\n%%EOF\n", "application/pdf")},
    )
    assert upload.status_code == 200, upload.text
    body = upload.json()
    assert body["document_type"] == "CONTRACT"

    docs = await client.get(f"/vendors/{vendor_id}/documents", headers=_auth_headers("tenant-a"))
    assert docs.status_code == 200
    assert len(docs.json()) >= 1

    expiring = await client.get(
        "/vendors/expiring-documents?days=60",
        headers=_auth_headers("tenant-a"),
    )
    assert expiring.status_code == 200
    expiring_items = expiring.json()
    assert any(item["document"]["vendor_id"] == vendor_id for item in expiring_items)

