"""Tests for /api/reports endpoints (generate, certin, scheduled)."""

import pytest
from httpx import AsyncClient

from backend.models.risk import Risk


@pytest.mark.asyncio
async def test_generate_excel(client: AsyncClient, auth_headers, seeded_risks):
    """POST /api/reports/generate with format=excel returns an xlsx file."""
    resp = await client.post("/api/reports/generate", headers=auth_headers, json={
        "report_type": "ciso",
        "format": "excel",
    })
    assert resp.status_code == 200
    assert "spreadsheetml" in resp.headers["content-type"]
    assert "attachment" in resp.headers["content-disposition"]
    assert ".xlsx" in resp.headers["content-disposition"]
    # File content should be non-empty
    assert len(resp.content) > 100


@pytest.mark.asyncio
async def test_generate_pdf(client: AsyncClient, auth_headers, seeded_risks):
    """POST /api/reports/generate with format=pdf returns a pdf file."""
    resp = await client.post("/api/reports/generate", headers=auth_headers, json={
        "report_type": "executive",
        "format": "pdf",
    })
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "application/pdf"
    assert "attachment" in resp.headers["content-disposition"]
    assert ".pdf" in resp.headers["content-disposition"]
    # PDF should start with %PDF magic bytes
    assert resp.content[:5] == b"%PDF-"


@pytest.mark.asyncio
async def test_certin_advisories(client: AsyncClient, auth_headers, seeded_risks):
    """GET /api/reports/certin returns CERT-In sourced risks as advisories."""
    resp = await client.get("/api/reports/certin", headers=auth_headers)
    assert resp.status_code == 200

    body = resp.json()
    assert isinstance(body, list)
    # From seeded data, one risk has source="cert_in"
    assert len(body) >= 1

    for advisory in body:
        assert "advisory_id" in advisory
        assert "title" in advisory
        assert "published_date" in advisory
        assert "severity" in advisory
        assert "response_status" in advisory


@pytest.mark.asyncio
async def test_scheduled_reports(client: AsyncClient, auth_headers):
    """GET /api/reports/scheduled returns the static schedule list."""
    resp = await client.get("/api/reports/scheduled", headers=auth_headers)
    assert resp.status_code == 200

    body = resp.json()
    assert isinstance(body, list)
    assert len(body) == 3

    names = [r["name"] for r in body]
    assert "Weekly Security Summary" in names
    assert "Monthly Board Report" in names
    assert "CERT-In Response Report" in names

    for report in body:
        assert report["status"] == "active"
        assert "frequency" in report
        assert "recipients" in report
        assert "next_run" in report
