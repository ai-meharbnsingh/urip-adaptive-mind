"""
TDD tests for the GTB Endpoint Protector live connector.

Uses respx to mock all HTTP traffic — no real API calls.
Coverage: authentication, fetch_findings (violations, usb_block, exfil),
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
from connectors.gtb.connector import GTBConnector


# ─────────────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture
def connector() -> GTBConnector:
    return GTBConnector()


@pytest.fixture
def valid_credentials() -> dict[str, str]:
    return {
        "base_url": "https://gtb.example.com",
        "api_key": "TEST_API_KEY",
        "tenant_id": "tenant-abc",
        "max_requests_per_hour": 1_000_000,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

BASE = "https://gtb.example.com"


def _mock_violation(
    violation_id: str = "viol-001",
    policy_name: str = "PCI-DSS",
    severity: str = "high",
) -> dict[str, Any]:
    return {
        "id": violation_id,
        "policy_name": policy_name,
        "severity": severity,
        "endpoint_name": "WS-FINANCE-03",
        "user_name": "john.doe@example.com",
        "channel": "email",
        "file_name": "card_numbers.xlsx",
        "action_taken": "blocked",
        "detected_at": "2024-01-15T10:00:00Z",
    }


def _mock_usb_event(
    event_id: str = "usb-001",
    action: str = "blocked",
) -> dict[str, Any]:
    return {
        "id": event_id,
        "endpoint_name": "WS-ENGINEERING-01",
        "user_name": "jane.smith@example.com",
        "device_id": "USB-12345",
        "device_type": "USB Storage",
        "action": action,
        "occurred_at": "2024-01-15T09:30:00Z",
    }


def _mock_exfil_event(
    event_id: str = "exfil-001",
) -> dict[str, Any]:
    return {
        "id": event_id,
        "endpoint_name": "WS-SALES-02",
        "user_name": "alice@example.com",
        "destination": "personal-dropbox.com",
        "channel": "cloud",
        "file_count": 15,
        "total_size_bytes": 10485760,
        "detected_at": "2024-01-15T08:00:00Z",
    }


# ─────────────────────────────────────────────────────────────────────────────
# Tests: Authentication
# ─────────────────────────────────────────────────────────────────────────────

class TestGTBAuthentication:
    @respx.mock
    def test_authenticate_success(self, connector: GTBConnector, valid_credentials: dict):
        route = respx.get(f"{BASE}/api/v1/status").mock(
            return_value=httpx.Response(200, json={"status": "ok"})
        )
        session = connector.authenticate(valid_credentials)
        assert isinstance(session, ConnectorSession)
        assert session.connector_name == "gtb"
        assert session.tenant_id == "tenant-abc"
        assert route.called

    @respx.mock
    def test_authenticate_failure_invalid_key(self, connector: GTBConnector):
        respx.get(f"{BASE}/api/v1/status").mock(
            return_value=httpx.Response(401, json={"error": "Unauthorized"})
        )
        with pytest.raises(ConnectorAuthError):
            connector.authenticate(
                {"base_url": BASE, "api_key": "bad", "tenant_id": "t"}
            )

    def test_authenticate_failure_missing_base_url(self, connector: GTBConnector):
        with pytest.raises(ConnectorAuthError):
            connector.authenticate({"api_key": "k", "tenant_id": "t"})

    def test_authenticate_failure_missing_api_key(self, connector: GTBConnector):
        with pytest.raises(ConnectorAuthError):
            connector.authenticate({"base_url": BASE, "tenant_id": "t"})


# ─────────────────────────────────────────────────────────────────────────────
# Tests: Fetch findings
# ─────────────────────────────────────────────────────────────────────────────

class TestGTBFetchFindings:
    @respx.mock
    def test_fetch_findings_empty(self, connector: GTBConnector, valid_credentials: dict):
        respx.get(f"{BASE}/api/v1/status").mock(
            return_value=httpx.Response(200, json={"status": "ok"})
        )
        respx.get(f"{BASE}/api/v1/violations").mock(
            return_value=httpx.Response(200, json={"data": []})
        )
        respx.get(f"{BASE}/api/v1/events/usb").mock(
            return_value=httpx.Response(200, json={"data": []})
        )
        respx.get(f"{BASE}/api/v1/events/exfil").mock(
            return_value=httpx.Response(200, json={"data": []})
        )
        connector.authenticate(valid_credentials)
        findings = connector.fetch_findings(
            since=datetime(2024, 1, 1, tzinfo=timezone.utc),
            tenant_id="tenant-abc",
        )
        assert findings == []

    @respx.mock
    def test_fetch_findings_violations(self, connector: GTBConnector, valid_credentials: dict):
        respx.get(f"{BASE}/api/v1/status").mock(
            return_value=httpx.Response(200, json={"status": "ok"})
        )
        respx.get(f"{BASE}/api/v1/violations").mock(
            return_value=httpx.Response(200, json={"data": [_mock_violation()]})
        )
        respx.get(f"{BASE}/api/v1/events/usb").mock(
            return_value=httpx.Response(200, json={"data": []})
        )
        respx.get(f"{BASE}/api/v1/events/exfil").mock(
            return_value=httpx.Response(200, json={"data": []})
        )
        connector.authenticate(valid_credentials)
        findings = connector.fetch_findings(
            since=datetime(2024, 1, 1, tzinfo=timezone.utc),
            tenant_id="tenant-abc",
        )
        assert len(findings) == 1
        assert findings[0].raw_data["category"] == "violation"

    @respx.mock
    def test_fetch_findings_usb_events(self, connector: GTBConnector, valid_credentials: dict):
        respx.get(f"{BASE}/api/v1/status").mock(
            return_value=httpx.Response(200, json={"status": "ok"})
        )
        respx.get(f"{BASE}/api/v1/violations").mock(
            return_value=httpx.Response(200, json={"data": []})
        )
        respx.get(f"{BASE}/api/v1/events/usb").mock(
            return_value=httpx.Response(200, json={"data": [_mock_usb_event()]})
        )
        respx.get(f"{BASE}/api/v1/events/exfil").mock(
            return_value=httpx.Response(200, json={"data": []})
        )
        connector.authenticate(valid_credentials)
        findings = connector.fetch_findings(
            since=datetime(2024, 1, 1, tzinfo=timezone.utc),
            tenant_id="tenant-abc",
        )
        assert len(findings) == 1
        assert findings[0].raw_data["category"] == "usb_block"

    @respx.mock
    def test_fetch_findings_exfil_events(self, connector: GTBConnector, valid_credentials: dict):
        respx.get(f"{BASE}/api/v1/status").mock(
            return_value=httpx.Response(200, json={"status": "ok"})
        )
        respx.get(f"{BASE}/api/v1/violations").mock(
            return_value=httpx.Response(200, json={"data": []})
        )
        respx.get(f"{BASE}/api/v1/events/usb").mock(
            return_value=httpx.Response(200, json={"data": []})
        )
        respx.get(f"{BASE}/api/v1/events/exfil").mock(
            return_value=httpx.Response(200, json={"data": [_mock_exfil_event()]})
        )
        connector.authenticate(valid_credentials)
        findings = connector.fetch_findings(
            since=datetime(2024, 1, 1, tzinfo=timezone.utc),
            tenant_id="tenant-abc",
        )
        assert len(findings) == 1
        assert findings[0].raw_data["category"] == "exfil"

    @respx.mock
    def test_fetch_findings_all_categories(self, connector: GTBConnector, valid_credentials: dict):
        respx.get(f"{BASE}/api/v1/status").mock(
            return_value=httpx.Response(200, json={"status": "ok"})
        )
        respx.get(f"{BASE}/api/v1/violations").mock(
            return_value=httpx.Response(200, json={"data": [_mock_violation()]})
        )
        respx.get(f"{BASE}/api/v1/events/usb").mock(
            return_value=httpx.Response(200, json={"data": [_mock_usb_event()]})
        )
        respx.get(f"{BASE}/api/v1/events/exfil").mock(
            return_value=httpx.Response(200, json={"data": [_mock_exfil_event()]})
        )
        connector.authenticate(valid_credentials)
        findings = connector.fetch_findings(
            since=datetime(2024, 1, 1, tzinfo=timezone.utc),
            tenant_id="tenant-abc",
        )
        assert len(findings) == 3
        cats = {f.raw_data["category"] for f in findings}
        assert cats == {"violation", "usb_block", "exfil"}

    @respx.mock
    def test_fetch_findings_5xx_error(self, connector: GTBConnector, valid_credentials: dict):
        respx.get(f"{BASE}/api/v1/status").mock(
            return_value=httpx.Response(200, json={"status": "ok"})
        )
        respx.get(f"{BASE}/api/v1/violations").mock(
            return_value=httpx.Response(503, json={"error": "Service Unavailable"})
        )
        connector.authenticate(valid_credentials)
        with pytest.raises(ConnectorFetchError):
            connector.fetch_findings(
                since=datetime(2024, 1, 1, tzinfo=timezone.utc),
                tenant_id="tenant-abc",
            )

    def test_fetch_findings_not_authenticated(self, connector: GTBConnector):
        with pytest.raises(ConnectorFetchError):
            connector.fetch_findings(since=datetime.now(timezone.utc))


# ─────────────────────────────────────────────────────────────────────────────
# Tests: Normalization
# ─────────────────────────────────────────────────────────────────────────────

class TestGTBNormalize:
    def test_normalize_violation_high(self, connector: GTBConnector):
        raw = RawFinding(
            id="viol-001",
            source="gtb",
            raw_data={
                "id": "viol-001",
                "policy_name": "PCI-DSS",
                "severity": "high",
                "endpoint_name": "WS-FINANCE-03",
                "user_name": "john.doe@example.com",
                "channel": "email",
                "file_name": "card_numbers.xlsx",
                "action_taken": "blocked",
                "category": "violation",
            },
            fetched_at=datetime.now(timezone.utc),
            tenant_id="t1",
        )
        record = connector.normalize(raw)
        assert isinstance(record, URIPRiskRecord)
        assert record.finding == "DLP Violation: PCI-DSS"
        assert record.severity == "high"
        assert record.asset == "WS-FINANCE-03"
        assert record.source == "gtb"
        assert record.domain == "dlp"
        assert record.owner_team == "Data Protection"

    def test_normalize_violation_critical(self, connector: GTBConnector):
        raw = RawFinding(
            id="viol-002",
            source="gtb",
            raw_data={
                "id": "viol-002",
                "policy_name": "HIPAA",
                "severity": "critical",
                "endpoint_name": "WS-MEDICAL-01",
                "user_name": "dr.house@example.com",
                "channel": "usb",
                "action_taken": "alerted",
                "category": "violation",
            },
            fetched_at=datetime.now(timezone.utc),
            tenant_id="t1",
        )
        record = connector.normalize(raw)
        assert record.severity == "critical"

    def test_normalize_usb_blocked(self, connector: GTBConnector):
        raw = RawFinding(
            id="usb-001",
            source="gtb",
            raw_data={
                "id": "usb-001",
                "endpoint_name": "WS-ENGINEERING-01",
                "user_name": "jane.smith@example.com",
                "device_id": "USB-12345",
                "device_type": "USB Storage",
                "action": "blocked",
                "category": "usb_block",
            },
            fetched_at=datetime.now(timezone.utc),
            tenant_id="t1",
        )
        record = connector.normalize(raw)
        assert record.finding == "USB Device Blocked: USB Storage"
        assert record.severity == "medium"
        assert record.asset == "WS-ENGINEERING-01"

    def test_normalize_usb_allowed(self, connector: GTBConnector):
        raw = RawFinding(
            id="usb-002",
            source="gtb",
            raw_data={
                "id": "usb-002",
                "endpoint_name": "WS-IT-01",
                "device_type": "USB Keyboard",
                "action": "allowed",
                "category": "usb_block",
            },
            fetched_at=datetime.now(timezone.utc),
            tenant_id="t1",
        )
        record = connector.normalize(raw)
        assert record.finding == "USB Event: USB Keyboard"
        assert record.severity == "low"

    def test_normalize_exfil(self, connector: GTBConnector):
        raw = RawFinding(
            id="exfil-001",
            source="gtb",
            raw_data={
                "id": "exfil-001",
                "endpoint_name": "WS-SALES-02",
                "user_name": "alice@example.com",
                "destination": "personal-dropbox.com",
                "channel": "cloud",
                "file_count": 15,
                "total_size_bytes": 10485760,
                "category": "exfil",
            },
            fetched_at=datetime.now(timezone.utc),
            tenant_id="t1",
        )
        record = connector.normalize(raw)
        assert record.finding == "Exfiltration Attempt: personal-dropbox.com"
        assert record.severity == "high"
        assert record.asset == "WS-SALES-02"

    def test_normalize_unknown_category(self, connector: GTBConnector):
        raw = RawFinding(
            id="x",
            source="gtb",
            raw_data={"id": "x", "category": "unknown"},
            fetched_at=datetime.now(timezone.utc),
            tenant_id="t1",
        )
        record = connector.normalize(raw)
        assert record.severity == "medium"
        assert record.asset == "unknown"


# ─────────────────────────────────────────────────────────────────────────────
# Tests: Error handling
# ─────────────────────────────────────────────────────────────────────────────

class TestGTBErrorHandling:
    @respx.mock
    def test_rate_limit_during_auth(self, connector: GTBConnector):
        respx.get(f"{BASE}/api/v1/status").mock(
            return_value=httpx.Response(429, json={"error": "Rate limited"})
        )
        with pytest.raises(ConnectorAuthError):
            connector.authenticate(
                {"base_url": BASE, "api_key": "key", "tenant_id": "t"}
            )

    @respx.mock
    def test_fetch_increments_error_count(self, connector: GTBConnector, valid_credentials: dict):
        respx.get(f"{BASE}/api/v1/status").mock(
            return_value=httpx.Response(200, json={"status": "ok"})
        )
        respx.get(f"{BASE}/api/v1/violations").mock(
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

class TestGTBTenantIsolation:
    @respx.mock
    def test_different_tenant_credentials_produce_different_results(self):
        base_a = "https://gtb-a.example.com"
        base_b = "https://gtb-b.example.com"

        respx.get(f"{base_a}/api/v1/status").mock(
            return_value=httpx.Response(200, json={"status": "ok"})
        )
        respx.get(f"{base_a}/api/v1/violations").mock(
            return_value=httpx.Response(200, json={"data": [_mock_violation("viol-a", "Policy-A", "high")]})
        )
        respx.get(f"{base_a}/api/v1/events/usb").mock(
            return_value=httpx.Response(200, json={"data": []})
        )
        respx.get(f"{base_a}/api/v1/events/exfil").mock(
            return_value=httpx.Response(200, json={"data": []})
        )
        respx.get(f"{base_b}/api/v1/status").mock(
            return_value=httpx.Response(200, json={"status": "ok"})
        )
        respx.get(f"{base_b}/api/v1/violations").mock(
            return_value=httpx.Response(200, json={"data": [_mock_violation("viol-b", "Policy-B", "critical")]})
        )
        respx.get(f"{base_b}/api/v1/events/usb").mock(
            return_value=httpx.Response(200, json={"data": []})
        )
        respx.get(f"{base_b}/api/v1/events/exfil").mock(
            return_value=httpx.Response(200, json={"data": []})
        )

        conn_a = GTBConnector()
        session_a = conn_a.authenticate(
            {"base_url": base_a, "api_key": "KEY_A", "tenant_id": "tenant-a"}
        )
        findings_a = conn_a.fetch_findings(
            since=datetime(2024, 1, 1, tzinfo=timezone.utc),
            tenant_id="tenant-a",
        )

        conn_b = GTBConnector()
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
        assert findings_a[0].raw_data["policy_name"] == "Policy-A"
        assert findings_b[0].raw_data["policy_name"] == "Policy-B"


# ─────────────────────────────────────────────────────────────────────────────
# Tests: Health check
# ─────────────────────────────────────────────────────────────────────────────

class TestGTBHealthCheck:
    def test_health_check_ok_fresh_connector(self, connector: GTBConnector):
        health = connector.health_check()
        assert isinstance(health, ConnectorHealth)
        assert health.connector_name == "gtb"
        assert health.status == "ok"
        assert health.error_count == 0
        assert health.last_run is None

    @respx.mock
    def test_health_check_degraded_after_errors(self, connector: GTBConnector):
        respx.get(f"{BASE}/api/v1/status").mock(
            return_value=httpx.Response(200, json={"status": "ok"})
        )
        respx.get(f"{BASE}/api/v1/violations").mock(
            return_value=httpx.Response(500, json={"error": "boom"})
        )
        connector.authenticate(
            {"base_url": BASE, "api_key": "key", "tenant_id": "t"}
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
    def test_health_check_error_after_many_errors(self, connector: GTBConnector):
        respx.get(f"{BASE}/api/v1/status").mock(
            return_value=httpx.Response(200, json={"status": "ok"})
        )
        respx.get(f"{BASE}/api/v1/violations").mock(
            return_value=httpx.Response(500, json={"error": "boom"})
        )
        connector.authenticate(
            {"base_url": BASE, "api_key": "key", "tenant_id": "t"}
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
        self, connector: GTBConnector, valid_credentials: dict
    ):
        respx.get(f"{BASE}/api/v1/status").mock(
            return_value=httpx.Response(200, json={"status": "ok"})
        )
        respx.get(f"{BASE}/api/v1/violations").mock(
            return_value=httpx.Response(200, json={"data": []})
        )
        respx.get(f"{BASE}/api/v1/events/usb").mock(
            return_value=httpx.Response(200, json={"data": []})
        )
        respx.get(f"{BASE}/api/v1/events/exfil").mock(
            return_value=httpx.Response(200, json={"data": []})
        )
        connector.authenticate(valid_credentials)
        connector.fetch_findings(since=datetime.now(timezone.utc))
        health = connector.health_check()
        assert health.last_run is not None
