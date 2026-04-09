"""Tests for /api/dashboard endpoints (KPIs, charts, alerts)."""

import pytest
from httpx import AsyncClient

from backend.models.risk import Risk


@pytest.mark.asyncio
async def test_get_kpis(client: AsyncClient, auth_headers, seeded_risks):
    """GET /api/dashboard/kpis returns severity counts matching seeded data."""
    resp = await client.get("/api/dashboard/kpis", headers=auth_headers)
    assert resp.status_code == 200

    body = resp.json()
    # All 10 seeded risks are "open" status
    assert body["total_open"] == 10
    assert body["critical"] == 2
    assert body["high"] == 3
    assert body["medium"] == 3
    assert body["low"] == 2
    assert body["accepted"] == 0
    assert isinstance(body["sla_breaching"], list)


@pytest.mark.asyncio
async def test_charts_by_domain(client: AsyncClient, auth_headers, seeded_risks):
    """GET /api/dashboard/charts/by-domain returns labels and data arrays."""
    resp = await client.get("/api/dashboard/charts/by-domain", headers=auth_headers)
    assert resp.status_code == 200

    body = resp.json()
    assert "labels" in body
    assert "data" in body
    assert len(body["labels"]) == len(body["data"])
    assert len(body["labels"]) > 0
    # Total across all domains should equal 10 open risks
    assert sum(body["data"]) == 10


@pytest.mark.asyncio
async def test_charts_by_source(client: AsyncClient, auth_headers, seeded_risks):
    """GET /api/dashboard/charts/by-source returns labels and data arrays."""
    resp = await client.get("/api/dashboard/charts/by-source", headers=auth_headers)
    assert resp.status_code == 200

    body = resp.json()
    assert "labels" in body
    assert "data" in body
    assert len(body["labels"]) == len(body["data"])
    assert len(body["labels"]) > 0
    assert sum(body["data"]) == 10


@pytest.mark.asyncio
async def test_charts_trend(client: AsyncClient, auth_headers, seeded_risks):
    """GET /api/dashboard/charts/trend returns datasets with labels."""
    resp = await client.get("/api/dashboard/charts/trend?months=3", headers=auth_headers)
    assert resp.status_code == 200

    body = resp.json()
    assert "labels" in body
    assert "datasets" in body
    assert len(body["labels"]) == 3
    assert len(body["datasets"]) == 4  # Critical, High, Medium, Total

    dataset_labels = [ds["label"] for ds in body["datasets"]]
    assert "Critical" in dataset_labels
    assert "High" in dataset_labels
    assert "Medium" in dataset_labels
    assert "Total" in dataset_labels

    for ds in body["datasets"]:
        assert len(ds["data"]) == 3


@pytest.mark.asyncio
async def test_get_alerts(client: AsyncClient, auth_headers, seeded_risks):
    """GET /api/dashboard/alerts returns critical/high risks sorted by CVSS desc."""
    resp = await client.get("/api/dashboard/alerts?limit=10", headers=auth_headers)
    assert resp.status_code == 200

    body = resp.json()
    assert isinstance(body, list)
    # Only critical + high = 2 + 3 = 5 from seeded data
    assert len(body) == 5

    # Verify sorted descending by CVSS
    cvss_scores = [item["cvss_score"] for item in body]
    assert cvss_scores == sorted(cvss_scores, reverse=True)

    # All items must be critical or high severity
    for item in body:
        assert item["severity"] in ("critical", "high")
        assert "risk_id" in item
        assert "finding" in item
        assert "asset" in item
