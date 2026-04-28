"""
TDD tests for the Hoxhunt connector (LMS / phishing-training competitor).

Coverage:
- Authenticate via API token
- fetch_findings pulls training status + behaviour change scores
- Low engagement (training_status != "active") → finding
- Failed phishing simulation → finding
- normalize → URIPRiskRecord with ISO 27001 A.6.3 / SOC 2 CC1.4 citations
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
from connectors.hoxhunt.connector import HoxhuntConnector


@pytest.fixture
def connector() -> HoxhuntConnector:
    return HoxhuntConnector()


@pytest.fixture
def valid_credentials() -> dict[str, Any]:
    return {
        "api_token": "hox-secret-token",
        "api_base": "https://api.hoxhunt.com",
        "tenant_id": "tenant-hox",
    }


class TestMetadata:
    def test_class_metadata(self):
        assert HoxhuntConnector.NAME == "hoxhunt"
        assert HoxhuntConnector.DISPLAY_NAME
        assert HoxhuntConnector.CATEGORY
        assert HoxhuntConnector.STATUS in ("live", "building", "simulated", "roadmap")
        assert HoxhuntConnector.SETUP_GUIDE is not None

    def test_setup_guide_validates(self):
        problems = HoxhuntConnector.SETUP_GUIDE.validate()
        assert problems == [], f"SETUP_GUIDE validation problems: {problems}"


class TestAuthenticate:
    def test_missing_token_raises(self, connector):
        with pytest.raises(ConnectorAuthError):
            connector.authenticate({})

    @respx.mock
    def test_valid_credentials_succeeds(self, connector, valid_credentials):
        respx.get("https://api.hoxhunt.com/v1/organization").mock(
            return_value=httpx.Response(200, json={"id": "org-1"})
        )
        session = connector.authenticate(valid_credentials)
        assert isinstance(session, ConnectorSession)
        assert session.connector_name == "hoxhunt"

    @respx.mock
    def test_invalid_credentials_raises(self, connector, valid_credentials):
        respx.get("https://api.hoxhunt.com/v1/organization").mock(
            return_value=httpx.Response(403, json={"error": "forbidden"})
        )
        with pytest.raises(ConnectorAuthError):
            connector.authenticate(valid_credentials)


class TestFetchFindings:
    @respx.mock
    def test_fetch_returns_inactive_users_and_failed_simulations(
        self, connector, valid_credentials
    ):
        respx.get("https://api.hoxhunt.com/v1/organization").mock(
            return_value=httpx.Response(200, json={"id": "org-1"})
        )

        # Users — one inactive (low engagement), one active
        respx.get("https://api.hoxhunt.com/v1/users").mock(
            return_value=httpx.Response(
                200,
                json={
                    "data": [
                        {
                            "id": "u-1",
                            "email": "carol@acme.com",
                            "training_status": "inactive",
                            "behaviour_score": 0.2,
                            "last_engaged_at": "2026-01-15T00:00:00Z",
                        },
                        {
                            "id": "u-2",
                            "email": "dan@acme.com",
                            "training_status": "active",
                            "behaviour_score": 0.9,
                            "last_engaged_at": "2026-04-20T00:00:00Z",
                        },
                    ]
                },
            )
        )

        # Simulations — Dan clicked, Carol reported
        respx.get("https://api.hoxhunt.com/v1/simulations/responses").mock(
            return_value=httpx.Response(
                200,
                json={
                    "data": [
                        {
                            "id": "sim-1",
                            "user_email": "dan@acme.com",
                            "outcome": "clicked",
                            "campaign": "Q1 2026",
                            "delivered_at": "2026-03-15T00:00:00Z",
                        },
                        {
                            "id": "sim-2",
                            "user_email": "carol@acme.com",
                            "outcome": "reported",
                            "campaign": "Q1 2026",
                            "delivered_at": "2026-03-15T00:00:00Z",
                        },
                    ]
                },
            )
        )

        connector.authenticate(valid_credentials)
        findings = connector.fetch_findings(
            since=datetime(2026, 1, 1, tzinfo=timezone.utc),
            tenant_id="tenant-hox",
        )
        assert len(findings) == 2
        kinds = sorted([f.raw_data.get("_kind") for f in findings])
        assert kinds == ["phishing_failed", "training_inactive"]


class TestNormalize:
    def test_normalize_inactive_training_has_compliance_citations(self, connector):
        raw = RawFinding(
            id="u-1",
            source="hoxhunt",
            raw_data={
                "_kind": "training_inactive",
                "id": "u-1",
                "email": "carol@acme.com",
                "training_status": "inactive",
                "behaviour_score": 0.2,
            },
            fetched_at=datetime.now(timezone.utc),
            tenant_id="tenant-hox",
        )
        record = connector.normalize(raw)
        assert isinstance(record, URIPRiskRecord)
        assert "A.6.3" in record.description
        assert "CC1.4" in record.description
        assert record.asset == "carol@acme.com"

    def test_normalize_failed_phishing_high_severity(self, connector):
        raw = RawFinding(
            id="sim-1",
            source="hoxhunt",
            raw_data={
                "_kind": "phishing_failed",
                "id": "sim-1",
                "user_email": "dan@acme.com",
                "outcome": "clicked",
                "campaign": "Q1 2026",
            },
            fetched_at=datetime.now(timezone.utc),
            tenant_id="tenant-hox",
        )
        record = connector.normalize(raw)
        assert record.severity == "high"


class TestHealthCheck:
    def test_initial_state_is_ok(self, connector):
        h = connector.health_check()
        assert isinstance(h, ConnectorHealth)
        assert h.status == "ok"
