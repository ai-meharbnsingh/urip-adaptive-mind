"""
Tests for POST /api/agent-ingest/metadata.

Verified:
1. Valid signed payload → RiskScoreSummary + ConnectorHealthSummary rows created
2. Raw findings (asset/ip/hostname/cve_id/etc.) in payload → 400, NOTHING persisted
3. Bad signature → 401
"""

from __future__ import annotations

import json

import pytest
from sqlalchemy import select

from backend.models.agent_ingest import ConnectorHealthSummary
from backend.models.risk_snapshot import RiskScoreSummary
from tests.test_agent_ingest.conftest import (
    KNOWN_SHARED_SECRET,
    build_signed_headers,
)


pytestmark = pytest.mark.asyncio


# ─── 1. Aggregate snapshot is persisted ──────────────────────────────────────


async def test_metadata_creates_risk_score_summary_and_connector_health(
    client, licensed_tenant, registered_agent, db_session
):
    body_dict = {
        "risk_summary": {
            "total_risks": 412,
            "critical_count": 15,
            "high_count": 73,
            "medium_count": 200,
            "low_count": 124,
            "exploit_active_count": 7,
            "kev_active_count": 3,
            "mean_ttr_hours": 48.5,
            "mean_composite_score": 6.2,
            "top_sources": [
                {"source": "tenable", "count": 200},
                {"source": "sentinelone", "count": 80},
            ],
        },
        "control_summary": {
            "connectors": [
                {
                    "name": "tenable",
                    "status": "ok",
                    "error_count_24h": 0,
                },
                {
                    "name": "sentinelone",
                    "status": "degraded",
                    "error_count_24h": 2,
                    "last_error": "rate limit",
                },
            ]
        },
        "score_history_delta": {},
    }
    body = json.dumps(body_dict, separators=(",", ":"), sort_keys=True).encode()
    path = "/api/agent-ingest/metadata"
    headers = build_signed_headers(licensed_tenant.slug, KNOWN_SHARED_SECRET, path, body)

    response = await client.post(path, content=body, headers=headers)
    assert response.status_code == 200, response.text
    assert response.json()["raw_persisted"] is False

    # RiskScoreSummary row exists
    rss_q = await db_session.execute(
        select(RiskScoreSummary).where(
            RiskScoreSummary.tenant_id == licensed_tenant.id
        )
    )
    rss_rows = rss_q.scalars().all()
    assert len(rss_rows) == 1
    rss = rss_rows[0]
    assert rss.total_risks == 412
    assert rss.critical_count == 15
    assert rss.exploit_active_count == 7

    # Per-connector health rows
    chs_q = await db_session.execute(
        select(ConnectorHealthSummary).where(
            ConnectorHealthSummary.tenant_id == licensed_tenant.id
        )
    )
    rows = {r.connector_name: r for r in chs_q.scalars().all()}
    assert "tenable" in rows
    assert rows["tenable"].status == "ok"
    assert "sentinelone" in rows
    assert rows["sentinelone"].status == "degraded"
    assert rows["sentinelone"].error_count_24h == 2


# ─── 2. Raw findings → 400 + NOTHING persisted ──────────────────────────────


@pytest.mark.parametrize(
    "bad_payload",
    [
        {"risk_summary": {"asset": "10.0.0.1"}},
        {"risk_summary": {"top_sources": [{"hostname": "evil.host"}]}},
        {"control_summary": {"connectors": [{"name": "tenable", "ip": "1.1.1.1"}]}},
        {"risk_summary": {"cve_id": "CVE-2026-0001"}},
        {"risk_summary": {"finding": "leaked password"}},
        {"risk_summary": {"counts": {"username": "admin"}}},  # 'username' key
    ],
)
async def test_raw_findings_payload_rejected_with_400_and_nothing_persisted(
    client, licensed_tenant, registered_agent, db_session, bad_payload
):
    body = json.dumps(bad_payload, separators=(",", ":"), sort_keys=True).encode()
    path = "/api/agent-ingest/metadata"
    headers = build_signed_headers(licensed_tenant.slug, KNOWN_SHARED_SECRET, path, body)

    # Pre-state
    pre = (
        await db_session.execute(
            select(RiskScoreSummary).where(
                RiskScoreSummary.tenant_id == licensed_tenant.id
            )
        )
    ).scalars().all()
    pre_count = len(pre)

    response = await client.post(path, content=body, headers=headers)
    assert response.status_code == 400, response.text
    assert "raw-finding" in response.json()["detail"]

    # Post-state — must be unchanged
    post = (
        await db_session.execute(
            select(RiskScoreSummary).where(
                RiskScoreSummary.tenant_id == licensed_tenant.id
            )
        )
    ).scalars().all()
    assert len(post) == pre_count


# ─── 3. Bad signature → 401 ─────────────────────────────────────────────────


async def test_metadata_bad_signature_returns_401(
    client, licensed_tenant, registered_agent, db_session
):
    body = b'{"risk_summary":{"total_risks":1}}'
    path = "/api/agent-ingest/metadata"
    headers = build_signed_headers(
        licensed_tenant.slug, "WRONG-SECRET", path, body
    )
    response = await client.post(path, content=body, headers=headers)
    assert response.status_code == 401


# ─── 4. Multiple snapshots accumulate (append-only) ──────────────────────────


async def test_metadata_snapshots_are_append_only(
    client, licensed_tenant, registered_agent, db_session
):
    for n in (1, 2, 3):
        body_dict = {"risk_summary": {"total_risks": n * 10}}
        body = json.dumps(body_dict, separators=(",", ":"), sort_keys=True).encode()
        path = "/api/agent-ingest/metadata"
        headers = build_signed_headers(
            licensed_tenant.slug, KNOWN_SHARED_SECRET, path, body
        )
        response = await client.post(path, content=body, headers=headers)
        assert response.status_code == 200

    rows = (
        await db_session.execute(
            select(RiskScoreSummary).where(
                RiskScoreSummary.tenant_id == licensed_tenant.id
            )
        )
    ).scalars().all()
    totals = sorted(r.total_risks for r in rows)
    assert totals == [10, 20, 30]
