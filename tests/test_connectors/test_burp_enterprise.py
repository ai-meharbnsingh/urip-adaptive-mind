"""
TDD tests for the Burp Suite Enterprise live connector.

Uses respx to mock all HTTP traffic — no real API calls.
Coverage: authentication, fetch_findings (scans, issues),
normalization, error handling, tenant isolation, health check.
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
from connectors.burp_enterprise.connector import BurpEnterpriseConnector


# ─────────────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture
def connector() -> BurpEnterpriseConnector:
    return BurpEnterpriseConnector()


@pytest.fixture
def valid_credentials() -> dict[str, str]:
    return {
        "base_url": "https://burp-enterprise.example.com",
        "api_key": "TEST_API_KEY",
        "tenant_id": "tenant-abc",
        "max_requests_per_hour": 1_000_000,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

BASE = "https://burp-enterprise.example.com"


def _mock_scan(scan_id: str = "scan-001", target_url: str = "https://app.example.com") -> dict[str, Any]:
    return {
        "id": scan_id,
        "name": "Weekly Scan",
        "status": "succeeded",
        "start_time": "2024-01-15T08:00:00Z",
        "end_time": "2024-01-15T09:00:00Z",
        "target_url": target_url,
        "scan_config_id": "cfg-001",
    }


def _mock_issue(
    issue_id: str = "issue-001",
    issue_type: str = "SQL Injection",
    severity: str = "high",
) -> dict[str, Any]:
    return {
        "id": issue_id,
        "scan_id": "scan-001",
        "issue_type": issue_type,
        "severity": severity,
        "confidence": "certain",
        "path": "/login",
        "url": "https://app.example.com/login",
        "description": "Parameterized query not used",
        "remediation": "Use prepared statements",
    }


# ─────────────────────────────────────────────────────────────────────────────
# Tests: Authentication
# ─────────────────────────────────────────────────────────────────────────────

class TestBurpEnterpriseAuthentication:
    @respx.mock
    def test_authenticate_success(self, connector: BurpEnterpriseConnector, valid_credentials: dict):
        route = respx.get(f"{BASE}/api/v2/scans").mock(
            return_value=httpx.Response(200, json={"data": []})
        )
        session = connector.authenticate(valid_credentials)
        assert isinstance(session, ConnectorSession)
        assert session.connector_name == "burp_enterprise"
        assert session.tenant_id == "tenant-abc"
        assert route.called

    @respx.mock
    def test_authenticate_failure_invalid_key(self, connector: BurpEnterpriseConnector):
        respx.get(f"{BASE}/api/v2/scans").mock(
            return_value=httpx.Response(401, json={"error": "Unauthorized"})
        )
        with pytest.raises(ConnectorAuthError):
            connector.authenticate(
                {"base_url": BASE, "api_key": "bad", "tenant_id": "t"}
            )

    def test_authenticate_failure_missing_base_url(self, connector: BurpEnterpriseConnector):
        with pytest.raises(ConnectorAuthError):
            connector.authenticate({"api_key": "k", "tenant_id": "t"})

    def test_authenticate_failure_missing_api_key(self, connector: BurpEnterpriseConnector):
        with pytest.raises(ConnectorAuthError):
            connector.authenticate({"base_url": BASE, "tenant_id": "t"})


# ─────────────────────────────────────────────────────────────────────────────
# Tests: Fetch findings
# ─────────────────────────────────────────────────────────────────────────────

class TestBurpEnterpriseFetchFindings:
    @respx.mock
    def test_fetch_findings_empty(self, connector: BurpEnterpriseConnector, valid_credentials: dict):
        respx.get(f"{BASE}/api/v2/scans").mock(
            return_value=httpx.Response(200, json={"data": []})
        )
        connector.authenticate(valid_credentials)
        findings = connector.fetch_findings(
            since=datetime(2024, 1, 1, tzinfo=timezone.utc),
            tenant_id="tenant-abc",
        )
        assert findings == []

    @respx.mock
    def test_fetch_findings_with_issues(self, connector: BurpEnterpriseConnector, valid_credentials: dict):
        respx.get(f"{BASE}/api/v2/scans").mock(
            return_value=httpx.Response(200, json={"data": [_mock_scan()]})
        )
        respx.get(f"{BASE}/api/v2/scans/scan-001/issues").mock(
            return_value=httpx.Response(200, json={"data": [_mock_issue()]})
        )
        connector.authenticate(valid_credentials)
        findings = connector.fetch_findings(
            since=datetime(2024, 1, 1, tzinfo=timezone.utc),
            tenant_id="tenant-abc",
        )
        assert len(findings) == 1
        assert findings[0].source == "burp_enterprise"
        assert findings[0].id == "scan-001:issue-001"

    @respx.mock
    def test_fetch_findings_multiple_scans(self, connector: BurpEnterpriseConnector, valid_credentials: dict):
        respx.get(f"{BASE}/api/v2/scans").mock(
            return_value=httpx.Response(
                200,
                json={
                    "data": [
                        _mock_scan("scan-001", "https://app1.example.com"),
                        _mock_scan("scan-002", "https://app2.example.com"),
                    ]
                },
            )
        )
        respx.get(f"{BASE}/api/v2/scans/scan-001/issues").mock(
            return_value=httpx.Response(200, json={"data": [_mock_issue("issue-001", "XSS", "high")]})
        )
        respx.get(f"{BASE}/api/v2/scans/scan-002/issues").mock(
            return_value=httpx.Response(200, json={"data": [_mock_issue("issue-002", "SQLi", "critical")]})
        )
        connector.authenticate(valid_credentials)
        findings = connector.fetch_findings(
            since=datetime(2024, 1, 1, tzinfo=timezone.utc),
            tenant_id="tenant-abc",
        )
        assert len(findings) == 2
        issue_types = {f.raw_data["issue_type"] for f in findings}
        assert issue_types == {"XSS", "SQLi"}

    @respx.mock
    def test_fetch_findings_respects_max_scans(self, connector: BurpEnterpriseConnector, valid_credentials: dict):
        respx.get(f"{BASE}/api/v2/scans").mock(
            return_value=httpx.Response(
                200,
                json={
                    "data": [
                        _mock_scan("scan-001"),
                    ]
                },
            )
        )
        respx.get(f"{BASE}/api/v2/scans/scan-001/issues").mock(
            return_value=httpx.Response(200, json={"data": [_mock_issue()]})
        )
        connector.authenticate(valid_credentials)
        findings = connector.fetch_findings(
            since=datetime(2024, 1, 1, tzinfo=timezone.utc),
            tenant_id="tenant-abc",
            max_scans=1,
        )
        assert len(findings) == 1

    @respx.mock
    def test_fetch_findings_5xx_error(self, connector: BurpEnterpriseConnector, valid_credentials: dict):
        respx.get(f"{BASE}/api/v2/scans").mock(
            return_value=httpx.Response(200, json={"data": [_mock_scan()]})
        )
        respx.get(f"{BASE}/api/v2/scans/scan-001/issues").mock(
            return_value=httpx.Response(503, json={"error": "Service Unavailable"})
        )
        connector.authenticate(valid_credentials)
        with pytest.raises(ConnectorFetchError):
            connector.fetch_findings(
                since=datetime(2024, 1, 1, tzinfo=timezone.utc),
                tenant_id="tenant-abc",
            )

    def test_fetch_findings_not_authenticated(self, connector: BurpEnterpriseConnector):
        with pytest.raises(ConnectorFetchError):
            connector.fetch_findings(since=datetime.now(timezone.utc))


# ─────────────────────────────────────────────────────────────────────────────
# Tests: Normalization
# ─────────────────────────────────────────────────────────────────────────────

class TestBurpEnterpriseNormalize:
    def test_normalize_high_severity(self, connector: BurpEnterpriseConnector):
        raw = RawFinding(
            id="scan-001:issue-001",
            source="burp_enterprise",
            raw_data={
                "id": "issue-001",
                "scan_id": "scan-001",
                "issue_type": "SQL Injection",
                "severity": "high",
                "confidence": "certain",
                "path": "/login",
                "url": "https://app.example.com/login",
                "description": "Parameterized query not used",
                "category": "issue",
            },
            fetched_at=datetime.now(timezone.utc),
            tenant_id="t1",
        )
        record = connector.normalize(raw)
        assert isinstance(record, URIPRiskRecord)
        assert record.finding == "DAST: SQL Injection"
        assert record.severity == "high"
        assert record.asset == "https://app.example.com/login"
        assert record.source == "burp_enterprise"
        assert record.domain == "application"
        assert record.owner_team == "Application Security"

    def test_normalize_critical_severity(self, connector: BurpEnterpriseConnector):
        raw = RawFinding(
            id="scan-001:issue-002",
            source="burp_enterprise",
            raw_data={
                "id": "issue-002",
                "issue_type": "Remote Code Execution",
                "severity": "critical",
                "url": "https://app.example.com/api",
                "category": "issue",
            },
            fetched_at=datetime.now(timezone.utc),
            tenant_id="t1",
        )
        record = connector.normalize(raw)
        assert record.severity == "critical"

    def test_normalize_low_severity(self, connector: BurpEnterpriseConnector):
        raw = RawFinding(
            id="scan-001:issue-003",
            source="burp_enterprise",
            raw_data={
                "id": "issue-003",
                "issue_type": "Information Disclosure",
                "severity": "low",
                "url": "https://app.example.com/about",
                "category": "issue",
            },
            fetched_at=datetime.now(timezone.utc),
            tenant_id="t1",
        )
        record = connector.normalize(raw)
        assert record.severity == "low"

    def test_normalize_missing_url_uses_scan_id(self, connector: BurpEnterpriseConnector):
        raw = RawFinding(
            id="scan-001:issue-004",
            source="burp_enterprise",
            raw_data={
                "id": "issue-004",
                "issue_type": "CSRF",
                "severity": "medium",
                "scan_id": "scan-001",
                "category": "issue",
            },
            fetched_at=datetime.now(timezone.utc),
            tenant_id="t1",
        )
        record = connector.normalize(raw)
        assert record.asset == "scan-001"

    def test_normalize_info_severity_maps_to_low(self, connector: BurpEnterpriseConnector):
        raw = RawFinding(
            id="scan-001:issue-005",
            source="burp_enterprise",
            raw_data={
                "id": "issue-005",
                "issue_type": "Cookie Flags",
                "severity": "info",
                "url": "https://app.example.com",
                "category": "issue",
            },
            fetched_at=datetime.now(timezone.utc),
            tenant_id="t1",
        )
        record = connector.normalize(raw)
        assert record.severity == "low"


# ─────────────────────────────────────────────────────────────────────────────
# Tests: Error handling
# ─────────────────────────────────────────────────────────────────────────────

class TestBurpEnterpriseErrorHandling:
    @respx.mock
    def test_rate_limit_during_auth(self, connector: BurpEnterpriseConnector):
        respx.get(f"{BASE}/api/v2/scans").mock(
            return_value=httpx.Response(429, json={"error": "Rate limited"})
        )
        with pytest.raises(ConnectorAuthError):
            connector.authenticate(
                {"base_url": BASE, "api_key": "key", "tenant_id": "t"}
            )

    @respx.mock
    def test_fetch_increments_error_count(self, connector: BurpEnterpriseConnector, valid_credentials: dict):
        respx.get(f"{BASE}/api/v2/scans").mock(
            return_value=httpx.Response(200, json={"data": [_mock_scan()]})
        )
        respx.get(f"{BASE}/api/v2/scans/scan-001/issues").mock(
            return_value=httpx.Response(500, json={"error": "boom"})
        )
        connector.authenticate(valid_credentials)
        with pytest.raises(ConnectorFetchError):
            connector.fetch_findings(since=datetime.now(timezone.utc))
        assert connector._error_count == 1
        assert "boom" in (connector._last_error or "")


# ─────────────────────────────────────────────────────────────────────────────
# Tests: Tenant isolation
# ─────────────────────────────────────────────────────────────────────────────

class TestBurpEnterpriseTenantIsolation:
    @respx.mock
    def test_different_tenant_credentials_produce_different_results(self):
        base_a = "https://burp-a.example.com"
        base_b = "https://burp-b.example.com"

        respx.get(f"{base_a}/api/v2/scans").mock(
            return_value=httpx.Response(200, json={"data": [_mock_scan("scan-a", "https://app-a.com")]})
        )
        respx.get(f"{base_a}/api/v2/scans/scan-a/issues").mock(
            return_value=httpx.Response(200, json={"data": [_mock_issue("issue-a", "XSS", "high")]})
        )
        respx.get(f"{base_b}/api/v2/scans").mock(
            return_value=httpx.Response(200, json={"data": [_mock_scan("scan-b", "https://app-b.com")]})
        )
        respx.get(f"{base_b}/api/v2/scans/scan-b/issues").mock(
            return_value=httpx.Response(200, json={"data": [_mock_issue("issue-b", "SQLi", "critical")]})
        )

        conn_a = BurpEnterpriseConnector()
        session_a = conn_a.authenticate(
            {"base_url": base_a, "api_key": "KEY_A", "tenant_id": "tenant-a"}
        )
        findings_a = conn_a.fetch_findings(
            since=datetime(2024, 1, 1, tzinfo=timezone.utc),
            tenant_id="tenant-a",
        )

        conn_b = BurpEnterpriseConnector()
        session_b = conn_b.authenticate(
            {"base_url": base_b, "api_key": "KEY_B", "tenant_id": "tenant-b"}
        )
        findings_b = conn_b.fetch_findings(
            since=datetime(2024, 1, 1, tzinfo=timezone.utc),
            tenant_id="tenant-b",
        )

        assert session_a.tenant_id == "tenant-a"
        assert session_b.tenant_id == "tenant-b"
        assert all(f.tenant_id == "tenant-a" for f in findings_a)
        assert all(f.tenant_id == "tenant-b" for f in findings_b)
        assert findings_a[0].raw_data["issue_type"] == "XSS"
        assert findings_b[0].raw_data["issue_type"] == "SQLi"


# ─────────────────────────────────────────────────────────────────────────────
# Tests: Health check
# ─────────────────────────────────────────────────────────────────────────────

class TestBurpEnterpriseHealthCheck:
    def test_health_check_ok_fresh_connector(self, connector: BurpEnterpriseConnector):
        health = connector.health_check()
        assert isinstance(health, ConnectorHealth)
        assert health.connector_name == "burp_enterprise"
        assert health.status == "ok"
        assert health.error_count == 0
        assert health.last_run is None

    @respx.mock
    def test_health_check_degraded_after_errors(self, connector: BurpEnterpriseConnector):
        respx.get(f"{BASE}/api/v2/scans").mock(
            return_value=httpx.Response(200, json={"data": [_mock_scan()]})
        )
        respx.get(f"{BASE}/api/v2/scans/scan-001/issues").mock(
            return_value=httpx.Response(500, json={"error": "boom"})
        )
        connector.authenticate(
            {"base_url": BASE, "api_key": "key", "tenant_id": "t", "max_requests_per_hour": 1_000_000}
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
    def test_health_check_error_after_many_errors(self, connector: BurpEnterpriseConnector):
        respx.get(f"{BASE}/api/v2/scans").mock(
            return_value=httpx.Response(200, json={"data": [_mock_scan()]})
        )
        respx.get(f"{BASE}/api/v2/scans/scan-001/issues").mock(
            return_value=httpx.Response(500, json={"error": "boom"})
        )
        connector.authenticate(
            {"base_url": BASE, "api_key": "key", "tenant_id": "t", "max_requests_per_hour": 1_000_000}
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
        self, connector: BurpEnterpriseConnector, valid_credentials: dict
    ):
        respx.get(f"{BASE}/api/v2/scans").mock(
            return_value=httpx.Response(200, json={"data": []})
        )
        connector.authenticate(valid_credentials)
        connector.fetch_findings(since=datetime.now(timezone.utc))
        health = connector.health_check()
        assert health.last_run is not None
