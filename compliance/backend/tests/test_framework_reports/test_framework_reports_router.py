"""
TDD tests for the /reports framework-report router.

Endpoints under test:
  POST /reports/{short_code}/generate  → returns {job_id, status: "queued"}
  GET  /reports/{job_id}               → returns metadata + (when ready) download link
  GET  /reports/{job_id}/download      → returns PDF/HTML bytes
  GET  /reports                        → list past report generations

Auth: STANDALONE mode JWT (compliance-issued). Same token style used elsewhere
in the test suite (see test_framework_routes.py).
"""
from __future__ import annotations

import pytest
import jwt

from compliance_backend.config import settings


def _bearer_headers(role: str = "admin", tenant_id: str = "tenant-test") -> dict:
    token = jwt.encode(
        {"sub": "tester@example.com", "role": role, "tenant_id": tenant_id},
        settings.COMPLIANCE_JWT_SECRET,
        algorithm="HS256",
    )
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_generate_unknown_framework_returns_404(client):
    resp = await client.post(
        "/reports/UNKNOWN_FW/generate",
        headers=_bearer_headers(),
        json={"org_name": "Acme"},
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_generate_returns_job_id_and_queued_status(client):
    resp = await client.post(
        "/reports/SOC2/generate",
        headers=_bearer_headers(),
        json={
            "org_name": "Acme Corp",
            "format": "pdf",
        },
    )
    assert resp.status_code == 202, resp.text
    body = resp.json()
    assert "job_id" in body
    assert body["status"] in ("queued", "completed")
    assert body["framework_short_code"] == "SOC2"


@pytest.mark.asyncio
async def test_get_job_returns_metadata_and_completes(client):
    create = await client.post(
        "/reports/ISO27001/generate",
        headers=_bearer_headers(),
        json={"org_name": "Acme", "format": "html"},
    )
    assert create.status_code == 202
    job_id = create.json()["job_id"]

    detail = await client.get(f"/reports/{job_id}", headers=_bearer_headers())
    assert detail.status_code == 200
    body = detail.json()
    assert body["job_id"] == job_id
    assert body["framework_short_code"] == "ISO27001"
    assert body["status"] == "completed"
    assert body["format"] == "html"


@pytest.mark.asyncio
async def test_download_returns_pdf_bytes(client):
    create = await client.post(
        "/reports/HIPAA/generate",
        headers=_bearer_headers(),
        json={"org_name": "Acme", "format": "pdf"},
    )
    job_id = create.json()["job_id"]
    dl = await client.get(f"/reports/{job_id}/download", headers=_bearer_headers())
    assert dl.status_code == 200
    assert dl.headers["content-type"] == "application/pdf"
    assert dl.content.startswith(b"%PDF")


@pytest.mark.asyncio
async def test_download_returns_html(client):
    create = await client.post(
        "/reports/GDPR/generate",
        headers=_bearer_headers(),
        json={"org_name": "Acme", "format": "html"},
    )
    job_id = create.json()["job_id"]
    dl = await client.get(f"/reports/{job_id}/download", headers=_bearer_headers())
    assert dl.status_code == 200
    assert dl.headers["content-type"].startswith("text/html")
    assert b"GDPR" in dl.content


@pytest.mark.asyncio
async def test_list_reports_returns_past_generations(client):
    # generate two
    await client.post(
        "/reports/PCI_DSS/generate",
        headers=_bearer_headers(),
        json={"org_name": "Acme", "format": "pdf"},
    )
    await client.post(
        "/reports/INDIA_DPDP/generate",
        headers=_bearer_headers(),
        json={"org_name": "Acme", "format": "pdf"},
    )
    listing = await client.get("/reports", headers=_bearer_headers())
    assert listing.status_code == 200
    body = listing.json()
    assert "items" in body
    assert len(body["items"]) >= 2
    codes = {it["framework_short_code"] for it in body["items"]}
    assert "PCI_DSS" in codes
    assert "INDIA_DPDP" in codes


@pytest.mark.asyncio
async def test_unauthenticated_request_rejected(client):
    resp = await client.post("/reports/SOC2/generate", json={"org_name": "x"})
    assert resp.status_code == 401
