"""
TDD tests for the AuthBridge BGV (background-verification) connector.

Coverage:
- Authenticate validates API token
- fetch_findings pulls per-employee BGV status
- Incomplete BGV (status != "completed") → finding citing HIPAA §164.308(a)(1)(ii)(B)
- normalize → URIPRiskRecord
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
from connectors.authbridge.connector import AuthBridgeConnector


@pytest.fixture
def connector() -> AuthBridgeConnector:
    return AuthBridgeConnector()


@pytest.fixture
def valid_credentials() -> dict[str, Any]:
    return {
        "api_token": "ab-secret-token",
        "api_base": "https://api.authbridge.com",
        "tenant_id": "tenant-ab",
    }


class TestMetadata:
    def test_class_metadata(self):
        assert AuthBridgeConnector.NAME == "authbridge"
        assert AuthBridgeConnector.DISPLAY_NAME
        assert AuthBridgeConnector.CATEGORY
        assert AuthBridgeConnector.STATUS in ("live", "building", "simulated", "roadmap")
        assert AuthBridgeConnector.SETUP_GUIDE is not None

    def test_setup_guide_validates(self):
        problems = AuthBridgeConnector.SETUP_GUIDE.validate()
        assert problems == [], f"SETUP_GUIDE validation problems: {problems}"


class TestAuthenticate:
    def test_missing_token_raises(self, connector):
        with pytest.raises(ConnectorAuthError):
            connector.authenticate({})

    @respx.mock
    def test_valid_credentials_succeeds(self, connector, valid_credentials):
        respx.get("https://api.authbridge.com/v1/account").mock(
            return_value=httpx.Response(200, json={"id": "acct-1"})
        )
        session = connector.authenticate(valid_credentials)
        assert isinstance(session, ConnectorSession)
        assert session.connector_name == "authbridge"

    @respx.mock
    def test_invalid_credentials_raises(self, connector, valid_credentials):
        respx.get("https://api.authbridge.com/v1/account").mock(
            return_value=httpx.Response(401, json={})
        )
        with pytest.raises(ConnectorAuthError):
            connector.authenticate(valid_credentials)


class TestFetchFindings:
    @respx.mock
    def test_fetch_returns_only_incomplete_bgv(self, connector, valid_credentials):
        respx.get("https://api.authbridge.com/v1/account").mock(
            return_value=httpx.Response(200, json={"id": "acct-1"})
        )
        respx.get("https://api.authbridge.com/v1/verifications").mock(
            return_value=httpx.Response(
                200,
                json={
                    "data": [
                        {
                            "id": "ab-1",
                            "employee_email": "emily@acme.com",
                            "employee_name": "Emily",
                            "status": "in_progress",
                            "checks_done": ["education"],
                            "checks_pending": ["criminal", "address"],
                            "initiated_at": "2026-03-01T00:00:00Z",
                        },
                        {
                            "id": "ab-2",
                            "employee_email": "frank@acme.com",
                            "employee_name": "Frank",
                            "status": "completed",
                            "checks_done": ["education", "criminal", "address"],
                            "completed_at": "2026-02-15T00:00:00Z",
                        },
                        {
                            "id": "ab-3",
                            "employee_email": "grace@acme.com",
                            "employee_name": "Grace",
                            "status": "failed",
                            "checks_done": ["education"],
                            "completed_at": "2026-03-20T00:00:00Z",
                        },
                    ]
                },
            )
        )

        connector.authenticate(valid_credentials)
        findings = connector.fetch_findings(
            since=datetime(2026, 1, 1, tzinfo=timezone.utc),
            tenant_id="tenant-ab",
        )
        # Should pull Emily (in_progress) + Grace (failed); Frank is excluded.
        assert len(findings) == 2
        emails = sorted([f.raw_data.get("employee_email") for f in findings])
        assert emails == ["emily@acme.com", "grace@acme.com"]


class TestNormalize:
    def test_normalize_incomplete_bgv_cites_hipaa(self, connector):
        raw = RawFinding(
            id="ab-1",
            source="authbridge",
            raw_data={
                "id": "ab-1",
                "employee_email": "emily@acme.com",
                "employee_name": "Emily",
                "status": "in_progress",
                "checks_pending": ["criminal", "address"],
            },
            fetched_at=datetime.now(timezone.utc),
            tenant_id="tenant-ab",
        )
        record = connector.normalize(raw)
        assert isinstance(record, URIPRiskRecord)
        assert "164.308" in record.description
        assert record.asset == "emily@acme.com"
        assert record.severity in ("medium", "high")

    def test_normalize_failed_bgv_high_severity(self, connector):
        raw = RawFinding(
            id="ab-3",
            source="authbridge",
            raw_data={
                "id": "ab-3",
                "employee_email": "grace@acme.com",
                "employee_name": "Grace",
                "status": "failed",
            },
            fetched_at=datetime.now(timezone.utc),
            tenant_id="tenant-ab",
        )
        record = connector.normalize(raw)
        assert record.severity == "high"


class TestHealthCheck:
    def test_initial_state_is_ok(self, connector):
        h = connector.health_check()
        assert isinstance(h, ConnectorHealth)
        assert h.status == "ok"
