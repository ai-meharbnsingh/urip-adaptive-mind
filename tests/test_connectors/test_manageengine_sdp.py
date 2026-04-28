"""
TDD tests for the ManageEngine ServiceDesk Plus live connector.

Uses respx to mock all HTTP traffic — no real API calls.
Coverage: authentication (OAuth + Auth Token), fetch_findings (security tickets),
normalization, bidirectional ticket creation, error handling, tenant isolation,
health check.
"""

from datetime import datetime, timezone
from typing import Any

import httpx
import pytest
import respx

from connectors.base.connector import (
    ConnectorAuthError,
    ConnectorFetchError,
    ConnectorHealth,
    ConnectorSession,
    RawFinding,
    URIPRiskRecord,
)
from connectors.manageengine_sdp.connector import ManageEngineSdpConnector


# ─────────────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture
def connector() -> ManageEngineSdpConnector:
    return ManageEngineSdpConnector()


@pytest.fixture
def valid_oauth_credentials() -> dict[str, str]:
    return {
        "auth_method": "oauth",
        "client_id": "SDP_CLIENT_ID",
        "client_secret": "SDP_CLIENT_SECRET",
        "refresh_token": "SDP_REFRESH_TOKEN",
        "base_url": "https://sdp.example.com",
        "tenant_id": "tenant-sdp",
    }


@pytest.fixture
def valid_token_credentials() -> dict[str, str]:
    return {
        "auth_method": "token",
        "auth_token": "SDP_AUTH_TOKEN",
        "base_url": "https://sdp.example.com",
        "tenant_id": "tenant-sdp",
    }


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

BASE = "https://sdp.example.com"


def _mock_oauth_token():
    return respx.post(f"{BASE}/api/v3/token").mock(
        return_value=httpx.Response(
            200,
            json={
                "access_token": "FAKE_ACCESS_TOKEN",
                "token_type": "Bearer",
                "expires_in": 3600,
            },
        )
    )


def _mock_ticket(priority: str = "High") -> dict[str, Any]:
    return {
        "id": "ticket-001",
        "subject": "Suspicious Login Detected",
        "description": "Multiple failed login attempts from unknown IP",
        "priority": priority,
        "category": "Security",
        "requester": "security@example.com",
        "status": "Open",
        "created_time": "2024-01-15T10:30:00Z",
    }


# ─────────────────────────────────────────────────────────────────────────────
# Tests: Authentication
# ─────────────────────────────────────────────────────────────────────────────

class TestManageEngineSdpAuthentication:
    @respx.mock
    def test_authenticate_oauth_success(self, connector: ManageEngineSdpConnector, valid_oauth_credentials: dict):
        route = _mock_oauth_token()
        session = connector.authenticate(valid_oauth_credentials)
        assert isinstance(session, ConnectorSession)
        assert session.connector_name == "manageengine_sdp"
        assert session.tenant_id == "tenant-sdp"
        assert route.called

    @respx.mock
    def test_authenticate_token_success(self, connector: ManageEngineSdpConnector, valid_token_credentials: dict):
        session = connector.authenticate(valid_token_credentials)
        assert isinstance(session, ConnectorSession)
        assert session.connector_name == "manageengine_sdp"
        assert session.tenant_id == "tenant-sdp"

    @respx.mock
    def test_authenticate_oauth_failure_invalid_creds(self, connector: ManageEngineSdpConnector):
        respx.post(f"{BASE}/api/v3/token").mock(
            return_value=httpx.Response(401, json={"error": "Unauthorized"})
        )
        with pytest.raises(ConnectorAuthError):
            connector.authenticate(
                {
                    "auth_method": "oauth",
                    "client_id": "bad",
                    "client_secret": "bad",
                    "refresh_token": "bad",
                    "base_url": BASE,
                    "tenant_id": "t",
                }
            )

    def test_authenticate_failure_missing_auth_method(self, connector: ManageEngineSdpConnector):
        with pytest.raises(ConnectorAuthError):
            connector.authenticate(
                {"base_url": BASE, "tenant_id": "t"}
            )

    def test_authenticate_failure_missing_base_url(self, connector: ManageEngineSdpConnector):
        with pytest.raises(ConnectorAuthError):
            connector.authenticate(
                {"auth_method": "token", "auth_token": "tok", "tenant_id": "t"}
            )

    def test_authenticate_failure_missing_token_for_token_method(self, connector: ManageEngineSdpConnector):
        with pytest.raises(ConnectorAuthError):
            connector.authenticate(
                {"auth_method": "token", "base_url": BASE, "tenant_id": "t"}
            )

    def test_authenticate_failure_missing_oauth_fields(self, connector: ManageEngineSdpConnector):
        with pytest.raises(ConnectorAuthError):
            connector.authenticate(
                {
                    "auth_method": "oauth",
                    "client_id": "c",
                    "base_url": BASE,
                    "tenant_id": "t",
                }
            )


# ─────────────────────────────────────────────────────────────────────────────
# Tests: Fetch findings
# ─────────────────────────────────────────────────────────────────────────────

class TestManageEngineSdpFetchFindings:
    @respx.mock
    def test_fetch_findings_empty(self, connector: ManageEngineSdpConnector, valid_oauth_credentials: dict):
        _mock_oauth_token()
        respx.get(f"{BASE}/api/v3/requests").mock(
            return_value=httpx.Response(200, json={"requests": []})
        )
        connector.authenticate(valid_oauth_credentials)
        findings = connector.fetch_findings(
            since=datetime(2024, 1, 1, tzinfo=timezone.utc),
            tenant_id="tenant-sdp",
        )
        assert findings == []

    @respx.mock
    def test_fetch_findings_security_tickets(self, connector: ManageEngineSdpConnector, valid_oauth_credentials: dict):
        _mock_oauth_token()
        respx.get(f"{BASE}/api/v3/requests").mock(
            return_value=httpx.Response(
                200, json={"requests": [_mock_ticket("High"), _mock_ticket("Low")]}
            )
        )
        connector.authenticate(valid_oauth_credentials)
        findings = connector.fetch_findings(
            since=datetime(2024, 1, 1, tzinfo=timezone.utc),
            tenant_id="tenant-sdp",
        )
        assert len(findings) == 2
        assert findings[0].source == "manageengine_sdp"
        assert findings[0].raw_data["priority"] == "High"

    @respx.mock
    def test_fetch_findings_5xx_error(self, connector: ManageEngineSdpConnector, valid_oauth_credentials: dict):
        _mock_oauth_token()
        respx.get(f"{BASE}/api/v3/requests").mock(
            return_value=httpx.Response(503, json={"error": "Service Unavailable"})
        )
        connector.authenticate(valid_oauth_credentials)
        with pytest.raises(ConnectorFetchError):
            connector.fetch_findings(
                since=datetime(2024, 1, 1, tzinfo=timezone.utc),
                tenant_id="tenant-sdp",
            )

    def test_fetch_findings_not_authenticated(self, connector: ManageEngineSdpConnector):
        with pytest.raises(ConnectorFetchError):
            connector.fetch_findings(since=datetime.now(timezone.utc))


# ─────────────────────────────────────────────────────────────────────────────
# Tests: Normalization
# ─────────────────────────────────────────────────────────────────────────────

class TestManageEngineSdpNormalize:
    def test_normalize_high_priority(self, connector: ManageEngineSdpConnector):
        raw = RawFinding(
            id="ticket-001",
            source="manageengine_sdp",
            raw_data=_mock_ticket("High"),
            fetched_at=datetime.now(timezone.utc),
            tenant_id="t1",
        )
        record = connector.normalize(raw)
        assert isinstance(record, URIPRiskRecord)
        assert record.finding == "SDP Ticket: Suspicious Login Detected"
        assert record.severity == "high"
        assert record.asset == "security@example.com"
        assert record.source == "manageengine_sdp"
        assert record.domain == "application"
        assert record.owner_team == "IT Service Management"
        assert "unknown IP" in record.description

    def test_normalize_critical_priority(self, connector: ManageEngineSdpConnector):
        raw = RawFinding(
            id="ticket-002",
            source="manageengine_sdp",
            raw_data=_mock_ticket("Critical"),
            fetched_at=datetime.now(timezone.utc),
            tenant_id="t1",
        )
        record = connector.normalize(raw)
        assert record.severity == "critical"

    def test_normalize_medium_priority(self, connector: ManageEngineSdpConnector):
        raw = RawFinding(
            id="ticket-003",
            source="manageengine_sdp",
            raw_data=_mock_ticket("Medium"),
            fetched_at=datetime.now(timezone.utc),
            tenant_id="t1",
        )
        record = connector.normalize(raw)
        assert record.severity == "medium"

    def test_normalize_low_priority(self, connector: ManageEngineSdpConnector):
        raw = RawFinding(
            id="ticket-004",
            source="manageengine_sdp",
            raw_data=_mock_ticket("Low"),
            fetched_at=datetime.now(timezone.utc),
            tenant_id="t1",
        )
        record = connector.normalize(raw)
        assert record.severity == "low"

    def test_normalize_unknown_priority_defaults_medium(self, connector: ManageEngineSdpConnector):
        raw = RawFinding(
            id="ticket-005",
            source="manageengine_sdp",
            raw_data={
                "id": "ticket-005",
                "subject": "Unknown",
                "description": "Desc",
                "priority": "Unknown",
                "category": "Security",
                "requester": "user@example.com",
                "status": "Open",
            },
            fetched_at=datetime.now(timezone.utc),
            tenant_id="t1",
        )
        record = connector.normalize(raw)
        assert record.severity == "medium"


# ─────────────────────────────────────────────────────────────────────────────
# Tests: Bidirectional ticket creation
# ─────────────────────────────────────────────────────────────────────────────

class TestManageEngineSdpCreateTicket:
    @respx.mock
    def test_create_ticket_success(self, connector: ManageEngineSdpConnector, valid_oauth_credentials: dict):
        _mock_oauth_token()
        respx.post(f"{BASE}/api/v3/requests").mock(
            return_value=httpx.Response(200, json={"request": {"id": "ticket-999"}})
        )
        connector.authenticate(valid_oauth_credentials)
        ticket_id = connector.create_ticket(
            {
                "subject": "Auto-created from URIP",
                "description": "Risk detected by URIP scoring engine",
                "priority": "High",
                "requester": "urip@example.com",
            }
        )
        assert ticket_id == "ticket-999"

    @respx.mock
    def test_create_ticket_failure(self, connector: ManageEngineSdpConnector, valid_oauth_credentials: dict):
        _mock_oauth_token()
        respx.post(f"{BASE}/api/v3/requests").mock(
            return_value=httpx.Response(400, json={"error": "Bad Request"})
        )
        connector.authenticate(valid_oauth_credentials)
        with pytest.raises(ConnectorFetchError):
            connector.create_ticket(
                {
                    "subject": "Auto-created from URIP",
                    "description": "Risk detected",
                }
            )

    def test_create_ticket_not_authenticated(self, connector: ManageEngineSdpConnector):
        with pytest.raises(ConnectorFetchError):
            connector.create_ticket({"subject": "Test"})


# ─────────────────────────────────────────────────────────────────────────────
# Tests: Error handling
# ─────────────────────────────────────────────────────────────────────────────

class TestManageEngineSdpErrorHandling:
    @respx.mock
    def test_rate_limit_during_auth(self, connector: ManageEngineSdpConnector):
        respx.post(f"{BASE}/api/v3/token").mock(
            return_value=httpx.Response(429, json={"error": "Rate limited"})
        )
        with pytest.raises(ConnectorAuthError):
            connector.authenticate(
                {
                    "auth_method": "oauth",
                    "client_id": "c",
                    "client_secret": "s",
                    "refresh_token": "r",
                    "base_url": BASE,
                    "tenant_id": "t",
                }
            )

    @respx.mock
    def test_fetch_increments_error_count(self, connector: ManageEngineSdpConnector, valid_oauth_credentials: dict):
        _mock_oauth_token()
        respx.get(f"{BASE}/api/v3/requests").mock(
            return_value=httpx.Response(500, json={"error": "boom"})
        )
        connector.authenticate(valid_oauth_credentials)
        with pytest.raises(ConnectorFetchError):
            connector.fetch_findings(since=datetime.now(timezone.utc))
        assert connector._error_count == 1
        assert "boom" in (connector._last_error or "")


# ─────────────────────────────────────────────────────────────────────────────
# Tests: Tenant isolation
# ─────────────────────────────────────────────────────────────────────────────

class TestManageEngineSdpTenantIsolation:
    @respx.mock
    def test_different_tenant_credentials_produce_different_results(self):
        base_a = "https://sdp-a.example.com"
        base_b = "https://sdp-b.example.com"
        respx.post(f"{base_a}/api/v3/token").mock(
            return_value=httpx.Response(
                200, json={"access_token": "TOK_A", "token_type": "Bearer", "expires_in": 3600}
            )
        )
        respx.post(f"{base_b}/api/v3/token").mock(
            return_value=httpx.Response(
                200, json={"access_token": "TOK_B", "token_type": "Bearer", "expires_in": 3600}
            )
        )
        respx.get(f"{base_a}/api/v3/requests").mock(
            return_value=httpx.Response(200, json={"requests": []})
        )
        respx.get(f"{base_b}/api/v3/requests").mock(
            return_value=httpx.Response(200, json={"requests": []})
        )

        conn_a = ManageEngineSdpConnector()
        session_a = conn_a.authenticate(
            {
                "auth_method": "oauth",
                "client_id": "C_A",
                "client_secret": "S_A",
                "refresh_token": "R_A",
                "base_url": base_a,
                "tenant_id": "tenant-a",
            }
        )
        findings_a = conn_a.fetch_findings(
            since=datetime(2024, 1, 1, tzinfo=timezone.utc),
            tenant_id="tenant-a",
        )

        conn_b = ManageEngineSdpConnector()
        session_b = conn_b.authenticate(
            {
                "auth_method": "oauth",
                "client_id": "C_B",
                "client_secret": "S_B",
                "refresh_token": "R_B",
                "base_url": base_b,
                "tenant_id": "tenant-b",
            }
        )
        findings_b = conn_b.fetch_findings(
            since=datetime(2024, 1, 1, tzinfo=timezone.utc),
            tenant_id="tenant-b",
        )

        assert session_a.tenant_id == "tenant-a"
        assert session_b.tenant_id == "tenant-b"
        assert all(f.tenant_id == "tenant-a" for f in findings_a)
        assert all(f.tenant_id == "tenant-b" for f in findings_b)


# ─────────────────────────────────────────────────────────────────────────────
# Tests: Health check
# ─────────────────────────────────────────────────────────────────────────────

class TestManageEngineSdpHealthCheck:
    def test_health_check_ok_fresh_connector(self, connector: ManageEngineSdpConnector):
        health = connector.health_check()
        assert isinstance(health, ConnectorHealth)
        assert health.connector_name == "manageengine_sdp"
        assert health.status == "ok"
        assert health.error_count == 0
        assert health.last_run is None

    @respx.mock
    def test_health_check_degraded_after_errors(self, connector: ManageEngineSdpConnector):
        _mock_oauth_token()
        respx.get(f"{BASE}/api/v3/requests").mock(
            return_value=httpx.Response(500, json={"error": "boom"})
        )
        connector.authenticate(
            {
                "auth_method": "oauth",
                "client_id": "c",
                "client_secret": "s",
                "refresh_token": "r",
                "base_url": BASE,
                "tenant_id": "t",
            }
        )
        for _ in range(3):
            try:
                connector.fetch_findings(since=datetime.now(timezone.utc))
            except ConnectorFetchError:
                pass
        health = connector.health_check()
        assert health.status == "degraded"
        assert health.error_count == 3
        assert health.last_error is not None

    @respx.mock
    def test_health_check_error_after_many_errors(self, connector: ManageEngineSdpConnector):
        _mock_oauth_token()
        respx.get(f"{BASE}/api/v3/requests").mock(
            return_value=httpx.Response(500, json={"error": "boom"})
        )
        connector.authenticate(
            {
                "auth_method": "oauth",
                "client_id": "c",
                "client_secret": "s",
                "refresh_token": "r",
                "base_url": BASE,
                "tenant_id": "t",
            }
        )
        for _ in range(6):
            try:
                connector.fetch_findings(since=datetime.now(timezone.utc))
            except ConnectorFetchError:
                pass
        health = connector.health_check()
        assert health.status == "error"
        assert health.error_count == 6

    @respx.mock
    def test_health_check_last_run_populated_after_successful_fetch(
        self, connector: ManageEngineSdpConnector, valid_oauth_credentials: dict
    ):
        _mock_oauth_token()
        respx.get(f"{BASE}/api/v3/requests").mock(
            return_value=httpx.Response(200, json={"requests": []})
        )
        connector.authenticate(valid_oauth_credentials)
        connector.fetch_findings(since=datetime.now(timezone.utc))
        health = connector.health_check()
        assert health.last_run is not None
