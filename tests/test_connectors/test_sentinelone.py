"""
TDD tests for the SentinelOne Singularity live connector.

Uses respx to mock all HTTP traffic — no real API calls.
Coverage: authentication, cursor pagination, normalization,
error handling (5xx, rate-limit), tenant isolation, health check.
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
from connectors.sentinelone.connector import SentinelOneConnector


# ─────────────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture
def connector() -> SentinelOneConnector:
    return SentinelOneConnector()


@pytest.fixture
def valid_credentials() -> dict[str, str]:
    return {
        "api_token": "S1APITOKEN123456789",
        "base_url": "https://test.sentinelone.net",
        "tenant_id": "tenant-s1",
        "max_requests_per_minute": 1_000_000,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _mock_threat(
    threat_id: str = "threat-001",
    classification: str = "Malware",
    mitigated: str = "not_mitigated",
    agent_name: str = "ws-01",
    agent_os: str = "windows",
    threat_name: str = "Trojan.Fake",
) -> dict[str, Any]:
    return {
        "id": threat_id,
        "agent_id": "agent-001",
        "agent_name": agent_name,
        "agent_os": agent_os,
        "classification": classification,
        "mitigated_status": mitigated,
        "created_at": "2024-01-15T10:30:00.000Z",
        "threat_info": {
            "threat_name": threat_name,
            "confidence_level": "high",
        },
        "file_display_name": "evil.exe",
    }


def _mock_agent(
    agent_id: str = "agent-001",
    computer_name: str = "ws-01",
    os_name: str = "Windows 10",
    is_active: bool = True,
) -> dict[str, Any]:
    return {
        "id": agent_id,
        "computer_name": computer_name,
        "os_name": os_name,
        "is_active": is_active,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Tests: Authentication
# ─────────────────────────────────────────────────────────────────────────────

class TestSentinelOneAuthentication:
    @respx.mock
    def test_authenticate_success(self, connector: SentinelOneConnector, valid_credentials: dict):
        route = respx.get("https://test.sentinelone.net/web/api/v2.1/system/info").mock(
            return_value=httpx.Response(200, json={"data": {"version": "23.1"}})
        )
        session = connector.authenticate(valid_credentials)
        assert isinstance(session, ConnectorSession)
        assert session.connector_name == "sentinelone"
        assert session.tenant_id == "tenant-s1"
        assert route.called

    @respx.mock
    def test_authenticate_failure_invalid_token(self, connector: SentinelOneConnector):
        respx.get("https://test.sentinelone.net/web/api/v2.1/system/info").mock(
            return_value=httpx.Response(401, json={"error": "Unauthorized"})
        )
        with pytest.raises(ConnectorAuthError):
            connector.authenticate(
                {
                    "api_token": "bad",
                    "base_url": "https://test.sentinelone.net",
                    "tenant_id": "t",
                    "max_requests_per_minute": 1_000_000,
                }
            )

    def test_authenticate_failure_missing_token(self, connector: SentinelOneConnector):
        with pytest.raises(ConnectorAuthError):
            connector.authenticate({"base_url": "https://test.sentinelone.net"})

    def test_authenticate_failure_missing_base_url(self, connector: SentinelOneConnector):
        with pytest.raises(ConnectorAuthError):
            connector.authenticate({"api_token": "token"})


# ─────────────────────────────────────────────────────────────────────────────
# Tests: Fetch findings
# ─────────────────────────────────────────────────────────────────────────────

class TestSentinelOneFetchFindings:
    @respx.mock
    def test_fetch_findings_empty_threats(self, connector: SentinelOneConnector, valid_credentials: dict):
        respx.get("https://test.sentinelone.net/web/api/v2.1/system/info").mock(
            return_value=httpx.Response(200, json={"data": {}})
        )
        respx.get("https://test.sentinelone.net/web/api/v2.1/threats").mock(
            return_value=httpx.Response(
                200,
                json={"data": [], "pagination": {"next_cursor": None, "total_items": 0}},
            )
        )
        respx.get("https://test.sentinelone.net/web/api/v2.1/agents").mock(
            return_value=httpx.Response(
                200,
                json={"data": [], "pagination": {"next_cursor": None, "total_items": 0}},
            )
        )
        connector.authenticate(valid_credentials)
        findings = connector.fetch_findings(
            since=datetime(2024, 1, 1, tzinfo=timezone.utc),
            tenant_id="tenant-s1",
        )
        assert findings == []

    @respx.mock
    def test_fetch_findings_cursor_pagination(self, connector: SentinelOneConnector, valid_credentials: dict):
        respx.get("https://test.sentinelone.net/web/api/v2.1/system/info").mock(
            return_value=httpx.Response(200, json={"data": {}})
        )
        # Page 1
        respx.get(
            "https://test.sentinelone.net/web/api/v2.1/threats",
        ).mock(
            return_value=httpx.Response(
                200,
                json={
                    "data": [_mock_threat("t-1"), _mock_threat("t-2")],
                    "pagination": {"next_cursor": "cursor2", "total_items": 4},
                },
            )
        )
        # Page 2 — respx will match the same route but we need to distinguish by query params
        # Actually respx matches by URL pattern. We'll use a side-effect function or multiple routes.
        # For simplicity, we mock the agents endpoint and use a single threats page with no cursor
        # for most tests, and for cursor test we rely on the route being called twice.
        # respx doesn't auto-differentiate by query param unless we use different routes.
        # We'll use a custom side effect.

        # Actually, let's use two separate route registrations with query param matching
        page1 = respx.get(
            "https://test.sentinelone.net/web/api/v2.1/threats",
        ).mock(
            return_value=httpx.Response(
                200,
                json={
                    "data": [_mock_threat("t-1"), _mock_threat("t-2")],
                    "pagination": {"next_cursor": "cursor2", "total_items": 4},
                },
            )
        )

        respx.get("https://test.sentinelone.net/web/api/v2.1/agents").mock(
            return_value=httpx.Response(
                200,
                json={"data": [], "pagination": {"next_cursor": None, "total_items": 0}},
            )
        )

        connector.authenticate(valid_credentials)
        findings = connector.fetch_findings(
            since=datetime(2024, 1, 1, tzinfo=timezone.utc),
            tenant_id="tenant-s1",
            max_threats=2,  # Only need 2 so pagination stops after page 1
        )
        assert len(findings) == 2
        assert {f.id for f in findings} == {"t-1", "t-2"}
        assert page1.called

    @respx.mock
    def test_fetch_findings_cursor_follows_to_page_2(self, connector: SentinelOneConnector, valid_credentials: dict):
        """Simulate two pages of threats and verify cursor is followed."""
        respx.get("https://test.sentinelone.net/web/api/v2.1/system/info").mock(
            return_value=httpx.Response(200, json={"data": {}})
        )

        call_count = 0

        def _threats_handler(request: httpx.Request):
            nonlocal call_count
            call_count += 1
            cursor = request.url.params.get("cursor")
            if cursor is None:
                return httpx.Response(
                    200,
                    json={
                        "data": [_mock_threat("t-1")],
                        "pagination": {"next_cursor": "page2", "total_items": 2},
                    },
                )
            elif cursor == "page2":
                return httpx.Response(
                    200,
                    json={
                        "data": [_mock_threat("t-2")],
                        "pagination": {"next_cursor": None, "total_items": 2},
                    },
                )
            return httpx.Response(400, json={"error": "unexpected cursor"})

        respx.get("https://test.sentinelone.net/web/api/v2.1/threats").mock(
            side_effect=_threats_handler
        )
        respx.get("https://test.sentinelone.net/web/api/v2.1/agents").mock(
            return_value=httpx.Response(
                200,
                json={"data": [], "pagination": {"next_cursor": None, "total_items": 0}},
            )
        )

        connector.authenticate(valid_credentials)
        findings = connector.fetch_findings(
            since=datetime(2024, 1, 1, tzinfo=timezone.utc),
            tenant_id="tenant-s1",
            max_threats=3,
        )
        assert len(findings) == 2
        assert {f.id for f in findings} == {"t-1", "t-2"}
        assert call_count == 2

    @respx.mock
    def test_fetch_findings_includes_inactive_agents(
        self, connector: SentinelOneConnector, valid_credentials: dict
    ):
        respx.get("https://test.sentinelone.net/web/api/v2.1/system/info").mock(
            return_value=httpx.Response(200, json={"data": {}})
        )
        respx.get("https://test.sentinelone.net/web/api/v2.1/threats").mock(
            return_value=httpx.Response(
                200,
                json={"data": [], "pagination": {"next_cursor": None, "total_items": 0}},
            )
        )
        respx.get("https://test.sentinelone.net/web/api/v2.1/agents").mock(
            return_value=httpx.Response(
                200,
                json={
                    "data": [
                        _mock_agent("a-1", "ws-01", is_active=True),
                        _mock_agent("a-2", "ws-02", is_active=False),
                    ],
                    "pagination": {"next_cursor": None, "total_items": 2},
                },
            )
        )

        connector.authenticate(valid_credentials)
        findings = connector.fetch_findings(
            since=datetime(2024, 1, 1, tzinfo=timezone.utc),
            tenant_id="tenant-s1",
        )
        # Only the inactive agent becomes a finding
        assert len(findings) == 1
        assert findings[0].id == "agent:a-2"
        assert findings[0].raw_data["agent_name"] == "ws-02"

    @respx.mock
    def test_fetch_findings_5xx_error(self, connector: SentinelOneConnector, valid_credentials: dict):
        respx.get("https://test.sentinelone.net/web/api/v2.1/system/info").mock(
            return_value=httpx.Response(200, json={"data": {}})
        )
        respx.get("https://test.sentinelone.net/web/api/v2.1/threats").mock(
            return_value=httpx.Response(503, json={"error": "Service Unavailable"})
        )
        connector.authenticate(valid_credentials)
        with pytest.raises(ConnectorFetchError):
            connector.fetch_findings(
                since=datetime(2024, 1, 1, tzinfo=timezone.utc),
                tenant_id="tenant-s1",
            )

    @respx.mock
    def test_fetch_findings_not_authenticated(self, connector: SentinelOneConnector):
        with pytest.raises(ConnectorFetchError):
            connector.fetch_findings(since=datetime.now(timezone.utc))


# ─────────────────────────────────────────────────────────────────────────────
# Tests: Normalization
# ─────────────────────────────────────────────────────────────────────────────

class TestSentinelOneNormalize:
    def test_normalize_threat_correctness(self, connector: SentinelOneConnector):
        raw = RawFinding(
            id="threat-007",
            source="sentinelone",
            raw_data={
                "id": "threat-007",
                "agent_id": "agent-007",
                "agent_name": "finance-ws-03",
                "agent_os": "windows",
                "classification": "Ransomware",
                "mitigated_status": "not_mitigated",
                "created_at": "2024-06-01T12:00:00.000Z",
                "threat_info": {
                    "threat_name": "WannaCry Variant",
                    "confidence_level": "high",
                },
                "file_display_name": "invoice.pdf.exe",
            },
            fetched_at=datetime.now(timezone.utc),
            tenant_id="t1",
        )
        record = connector.normalize(raw)
        assert isinstance(record, URIPRiskRecord)
        assert record.finding == "WannaCry Variant"
        assert record.severity == "critical"
        assert record.asset == "finance-ws-03"
        assert record.source == "sentinelone"
        assert record.domain == "endpoint"
        assert record.exploit_status == "active"
        assert "invoice.pdf.exe" in record.description

    def test_normalize_mitigated_threat(self, connector: SentinelOneConnector):
        raw = RawFinding(
            id="threat-008",
            source="sentinelone",
            raw_data={
                "id": "threat-008",
                "agent_name": "dev-ws-01",
                "classification": "Malware",
                "mitigated_status": "mitigated",
                "threat_info": {"threat_name": "Adware.Dropper"},
            },
            fetched_at=datetime.now(timezone.utc),
            tenant_id="t1",
        )
        record = connector.normalize(raw)
        assert record.severity == "high"
        assert record.exploit_status is None  # mitigated → no active exploit

    def test_normalize_pup_threat(self, connector: SentinelOneConnector):
        raw = RawFinding(
            id="threat-009",
            source="sentinelone",
            raw_data={
                "id": "threat-009",
                "agent_name": "hr-ws-02",
                "classification": "PUP",
                "mitigated_status": "not_mitigated",
                "threat_info": {"threat_name": "BrowserModifier"},
            },
            fetched_at=datetime.now(timezone.utc),
            tenant_id="t1",
        )
        record = connector.normalize(raw)
        assert record.severity == "medium"

    def test_normalize_agent_finding(self, connector: SentinelOneConnector):
        raw = RawFinding(
            id="agent:a-99",
            source="sentinelone",
            raw_data={
                "agent_id": "a-99",
                "agent_name": "offsite-laptop-01",
                "agent_os": "macOS 14",
                "classification": "Inactive Agent",
                "mitigated_status": "not_mitigated",
                "is_agent_finding": True,
            },
            fetched_at=datetime.now(timezone.utc),
            tenant_id="t1",
        )
        record = connector.normalize(raw)
        assert record.finding == "Inactive SentinelOne Agent: offsite-laptop-01"
        assert record.severity == "medium"
        assert record.cvss_score == 5.0
        assert record.asset == "offsite-laptop-01"
        assert "macOS 14" in record.description

    def test_normalize_threat_without_name(self, connector: SentinelOneConnector):
        raw = RawFinding(
            id="threat-010",
            source="sentinelone",
            raw_data={
                "id": "threat-010",
                "agent_name": "unknown",
                "classification": "Behavioral",
                "mitigated_status": "not_mitigated",
                "threat_info": {},
            },
            fetched_at=datetime.now(timezone.utc),
            tenant_id="t1",
        )
        record = connector.normalize(raw)
        assert record.finding == "Behavioral Threat"


# ─────────────────────────────────────────────────────────────────────────────
# Tests: Error handling
# ─────────────────────────────────────────────────────────────────────────────

class TestSentinelOneErrorHandling:
    @respx.mock
    def test_rate_limit_during_auth(self, connector: SentinelOneConnector):
        respx.get("https://test.sentinelone.net/web/api/v2.1/system/info").mock(
            return_value=httpx.Response(429, json={"error": "Rate limited"})
        )
        with pytest.raises(ConnectorAuthError):
            connector.authenticate(
                {
                    "api_token": "tok",
                    "base_url": "https://test.sentinelone.net",
                    "tenant_id": "t",
                }
            )

    @respx.mock
    def test_fetch_increments_error_count(self, connector: SentinelOneConnector, valid_credentials: dict):
        respx.get("https://test.sentinelone.net/web/api/v2.1/system/info").mock(
            return_value=httpx.Response(200, json={"data": {}})
        )
        respx.get("https://test.sentinelone.net/web/api/v2.1/threats").mock(
            return_value=httpx.Response(500, json={"error": "Internal Server Error"})
        )
        connector.authenticate(valid_credentials)
        with pytest.raises(ConnectorFetchError):
            connector.fetch_findings(since=datetime.now(timezone.utc))
        assert connector._error_count == 1
        assert "Internal Server Error" in (connector._last_error or "")


# ─────────────────────────────────────────────────────────────────────────────
# Tests: Tenant isolation
# ─────────────────────────────────────────────────────────────────────────────

class TestSentinelOneTenantIsolation:
    @respx.mock
    def test_different_tenant_credentials_produce_different_results(self):
        respx.get("https://tenant-a.sentinelone.net/web/api/v2.1/system/info").mock(
            return_value=httpx.Response(200, json={"data": {}})
        )
        respx.get("https://tenant-b.sentinelone.net/web/api/v2.1/system/info").mock(
            return_value=httpx.Response(200, json={"data": {}})
        )
        respx.get("https://tenant-a.sentinelone.net/web/api/v2.1/threats").mock(
            return_value=httpx.Response(
                200,
                json={"data": [], "pagination": {"next_cursor": None, "total_items": 0}},
            )
        )
        respx.get("https://tenant-a.sentinelone.net/web/api/v2.1/agents").mock(
            return_value=httpx.Response(
                200,
                json={"data": [], "pagination": {"next_cursor": None, "total_items": 0}},
            )
        )
        respx.get("https://tenant-b.sentinelone.net/web/api/v2.1/threats").mock(
            return_value=httpx.Response(
                200,
                json={"data": [], "pagination": {"next_cursor": None, "total_items": 0}},
            )
        )
        respx.get("https://tenant-b.sentinelone.net/web/api/v2.1/agents").mock(
            return_value=httpx.Response(
                200,
                json={"data": [], "pagination": {"next_cursor": None, "total_items": 0}},
            )
        )

        conn_a = SentinelOneConnector()
        session_a = conn_a.authenticate(
            {
                "api_token": "TOK_A",
                "base_url": "https://tenant-a.sentinelone.net",
                "tenant_id": "tenant-a",
            }
        )
        findings_a = conn_a.fetch_findings(
            since=datetime(2024, 1, 1, tzinfo=timezone.utc),
            tenant_id="tenant-a",
        )

        conn_b = SentinelOneConnector()
        session_b = conn_b.authenticate(
            {
                "api_token": "TOK_B",
                "base_url": "https://tenant-b.sentinelone.net",
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

class TestSentinelOneHealthCheck:
    def test_health_check_ok_fresh_connector(self, connector: SentinelOneConnector):
        health = connector.health_check()
        assert isinstance(health, ConnectorHealth)
        assert health.connector_name == "sentinelone"
        assert health.status == "ok"
        assert health.error_count == 0
        assert health.last_run is None

    @respx.mock
    def test_health_check_degraded_after_errors(self, connector: SentinelOneConnector):
        respx.get("https://test.sentinelone.net/web/api/v2.1/system/info").mock(
            return_value=httpx.Response(200, json={"data": {}})
        )
        respx.get("https://test.sentinelone.net/web/api/v2.1/threats").mock(
            return_value=httpx.Response(500, json={"error": "boom"})
        )
        connector.authenticate(
            {
                "api_token": "tok",
                "base_url": "https://test.sentinelone.net",
                "tenant_id": "t",
                "max_requests_per_minute": 1_000_000,
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
    def test_health_check_error_after_many_errors(self, connector: SentinelOneConnector):
        respx.get("https://test.sentinelone.net/web/api/v2.1/system/info").mock(
            return_value=httpx.Response(200, json={"data": {}})
        )
        respx.get("https://test.sentinelone.net/web/api/v2.1/threats").mock(
            return_value=httpx.Response(500, json={"error": "boom"})
        )
        connector.authenticate(
            {
                "api_token": "tok",
                "base_url": "https://test.sentinelone.net",
                "tenant_id": "t",
                "max_requests_per_minute": 1_000_000,
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
        self, connector: SentinelOneConnector, valid_credentials: dict
    ):
        respx.get("https://test.sentinelone.net/web/api/v2.1/system/info").mock(
            return_value=httpx.Response(200, json={"data": {}})
        )
        respx.get("https://test.sentinelone.net/web/api/v2.1/threats").mock(
            return_value=httpx.Response(
                200,
                json={"data": [], "pagination": {"next_cursor": None, "total_items": 0}},
            )
        )
        respx.get("https://test.sentinelone.net/web/api/v2.1/agents").mock(
            return_value=httpx.Response(
                200,
                json={"data": [], "pagination": {"next_cursor": None, "total_items": 0}},
            )
        )
        connector.authenticate(valid_credentials)
        connector.fetch_findings(since=datetime.now(timezone.utc))
        health = connector.health_check()
        assert health.last_run is not None
