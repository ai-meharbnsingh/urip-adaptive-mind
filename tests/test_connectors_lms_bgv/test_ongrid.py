"""
TDD tests for the OnGrid BGV connector (alternative to AuthBridge).

Coverage:
- Authenticate via API key
- fetch_findings pulls verification status records
- Incomplete BGV → finding (cites HIPAA §164.308(a)(1)(ii)(B))
- Class metadata + SETUP_GUIDE present
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import httpx
import pytest
import respx

from connectors.base.connector import (
    ConnectorAuthError,
    ConnectorHealth,
    ConnectorSession,
    RawFinding,
    URIPRiskRecord,
)
from connectors.ongrid.connector import OnGridConnector


@pytest.fixture
def connector() -> OnGridConnector:
    return OnGridConnector()


@pytest.fixture
def valid_credentials() -> dict[str, Any]:
    return {
        "api_key": "og-secret-token",
        "api_base": "https://api.ongrid.in",
        "tenant_id": "tenant-og",
    }


class TestMetadata:
    def test_class_metadata(self):
        assert OnGridConnector.NAME == "ongrid"
        assert OnGridConnector.DISPLAY_NAME
        assert OnGridConnector.CATEGORY
        assert OnGridConnector.STATUS in ("live", "building", "simulated", "roadmap")
        assert OnGridConnector.SETUP_GUIDE is not None

    def test_setup_guide_validates(self):
        problems = OnGridConnector.SETUP_GUIDE.validate()
        assert problems == [], f"SETUP_GUIDE validation problems: {problems}"


class TestAuthenticate:
    def test_missing_key_raises(self, connector):
        with pytest.raises(ConnectorAuthError):
            connector.authenticate({})

    @respx.mock
    def test_valid_credentials_succeeds(self, connector, valid_credentials):
        respx.get("https://api.ongrid.in/v1/me").mock(
            return_value=httpx.Response(200, json={"id": "me-1"})
        )
        session = connector.authenticate(valid_credentials)
        assert isinstance(session, ConnectorSession)
        assert session.connector_name == "ongrid"

    @respx.mock
    def test_invalid_credentials_raises(self, connector, valid_credentials):
        respx.get("https://api.ongrid.in/v1/me").mock(
            return_value=httpx.Response(401, json={})
        )
        with pytest.raises(ConnectorAuthError):
            connector.authenticate(valid_credentials)


class TestFetchFindings:
    @respx.mock
    def test_fetch_returns_only_incomplete_or_failed(self, connector, valid_credentials):
        respx.get("https://api.ongrid.in/v1/me").mock(
            return_value=httpx.Response(200, json={"id": "me-1"})
        )
        respx.get("https://api.ongrid.in/v1/checks").mock(
            return_value=httpx.Response(
                200,
                json={
                    "results": [
                        {
                            "id": "og-1",
                            "candidate_email": "henry@acme.com",
                            "candidate_name": "Henry",
                            "verification_status": "pending",
                            "checks_completed": ["aadhaar"],
                            "checks_remaining": ["pan", "address"],
                        },
                        {
                            "id": "og-2",
                            "candidate_email": "iris@acme.com",
                            "candidate_name": "Iris",
                            "verification_status": "verified",
                        },
                        {
                            "id": "og-3",
                            "candidate_email": "jack@acme.com",
                            "candidate_name": "Jack",
                            "verification_status": "rejected",
                            "rejection_reason": "criminal record found",
                        },
                    ]
                },
            )
        )
        connector.authenticate(valid_credentials)
        findings = connector.fetch_findings(
            since=datetime(2026, 1, 1, tzinfo=timezone.utc),
            tenant_id="tenant-og",
        )
        assert len(findings) == 2
        emails = sorted([f.raw_data.get("candidate_email") for f in findings])
        assert emails == ["henry@acme.com", "jack@acme.com"]


class TestNormalize:
    def test_normalize_pending_bgv_cites_hipaa(self, connector):
        raw = RawFinding(
            id="og-1",
            source="ongrid",
            raw_data={
                "id": "og-1",
                "candidate_email": "henry@acme.com",
                "candidate_name": "Henry",
                "verification_status": "pending",
                "checks_remaining": ["pan", "address"],
            },
            fetched_at=datetime.now(timezone.utc),
            tenant_id="tenant-og",
        )
        record = connector.normalize(raw)
        assert isinstance(record, URIPRiskRecord)
        assert "164.308" in record.description
        assert record.asset == "henry@acme.com"

    def test_normalize_rejected_high_severity(self, connector):
        raw = RawFinding(
            id="og-3",
            source="ongrid",
            raw_data={
                "id": "og-3",
                "candidate_email": "jack@acme.com",
                "candidate_name": "Jack",
                "verification_status": "rejected",
                "rejection_reason": "criminal record found",
            },
            fetched_at=datetime.now(timezone.utc),
            tenant_id="tenant-og",
        )
        record = connector.normalize(raw)
        assert record.severity == "high"


class TestHealthCheck:
    def test_initial_state_is_ok(self, connector):
        h = connector.health_check()
        assert isinstance(h, ConnectorHealth)
        assert h.status == "ok"
