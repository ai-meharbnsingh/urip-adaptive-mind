"""
TDD tests for the ManageEngine MDM live connector.

Uses respx to mock all HTTP traffic — no real API calls.
Coverage: authentication, fetch_findings (devices, lost/stolen),
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
from connectors.manageengine_mdm.connector import ManageEngineMDMConnector


# ─────────────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture
def connector() -> ManageEngineMDMConnector:
    return ManageEngineMDMConnector()


@pytest.fixture
def valid_credentials() -> dict[str, str]:
    return {
        "base_url": "https://mdm.example.com",
        "api_token": "TEST_API_TOKEN",
        "tenant_id": "tenant-abc",
        "max_requests_per_hour": 1_000_000,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

BASE = "https://mdm.example.com"


def _mock_device(
    device_id: str = "dev-001",
    name: str = "iPhone-CEO",
    is_jailbroken: bool = False,
    compliance_status: str = "compliant",
) -> dict[str, Any]:
    return {
        "id": device_id,
        "device_name": name,
        "user_name": "ceo@example.com",
        "platform": "iOS",
        "os_version": "17.1",
        "is_jailbroken": is_jailbroken,
        "compliance_status": compliance_status,
        "enrollment_status": "enrolled",
        "last_contact_time": "2024-01-15T10:00:00Z",
    }


def _mock_lost_stolen_event(
    event_id: str = "evt-001",
    event_type: str = "lost",
) -> dict[str, Any]:
    return {
        "id": event_id,
        "device_id": "dev-001",
        "device_name": "iPhone-CEO",
        "event_type": event_type,
        "reported_at": "2024-01-15T09:00:00Z",
        "reported_by": "admin@example.com",
    }


# ─────────────────────────────────────────────────────────────────────────────
# Tests: Authentication
# ─────────────────────────────────────────────────────────────────────────────

class TestManageEngineMDMAuthentication:
    @respx.mock
    def test_authenticate_success(self, connector: ManageEngineMDMConnector, valid_credentials: dict):
        route = respx.get(f"{BASE}/api/v1/mdm/devices").mock(
            return_value=httpx.Response(200, json={"data": []})
        )
        session = connector.authenticate(valid_credentials)
        assert isinstance(session, ConnectorSession)
        assert session.connector_name == "manageengine_mdm"
        assert session.tenant_id == "tenant-abc"
        assert route.called

    @respx.mock
    def test_authenticate_failure_invalid_token(self, connector: ManageEngineMDMConnector):
        respx.get(f"{BASE}/api/v1/mdm/devices").mock(
            return_value=httpx.Response(401, json={"error": "Unauthorized"})
        )
        with pytest.raises(ConnectorAuthError):
            connector.authenticate(
                {"base_url": BASE, "api_token": "bad", "tenant_id": "t"}
            )

    def test_authenticate_failure_missing_base_url(self, connector: ManageEngineMDMConnector):
        with pytest.raises(ConnectorAuthError):
            connector.authenticate({"api_token": "t", "tenant_id": "t"})

    def test_authenticate_failure_missing_api_token(self, connector: ManageEngineMDMConnector):
        with pytest.raises(ConnectorAuthError):
            connector.authenticate({"base_url": BASE, "tenant_id": "t"})


# ─────────────────────────────────────────────────────────────────────────────
# Tests: Fetch findings
# ─────────────────────────────────────────────────────────────────────────────

class TestManageEngineMDMFetchFindings:
    @respx.mock
    def test_fetch_findings_empty(self, connector: ManageEngineMDMConnector, valid_credentials: dict):
        respx.get(f"{BASE}/api/v1/mdm/devices").mock(
            return_value=httpx.Response(200, json={"data": []})
        )
        respx.get(f"{BASE}/api/v1/mdm/lost_stolen").mock(
            return_value=httpx.Response(200, json={"data": []})
        )
        connector.authenticate(valid_credentials)
        findings = connector.fetch_findings(
            since=datetime(2024, 1, 1, tzinfo=timezone.utc),
            tenant_id="tenant-abc",
        )
        assert findings == []

    @respx.mock
    def test_fetch_findings_devices(self, connector: ManageEngineMDMConnector, valid_credentials: dict):
        respx.get(f"{BASE}/api/v1/mdm/devices").mock(
            return_value=httpx.Response(200, json={"data": [_mock_device()]})
        )
        respx.get(f"{BASE}/api/v1/mdm/lost_stolen").mock(
            return_value=httpx.Response(200, json={"data": []})
        )
        connector.authenticate(valid_credentials)
        findings = connector.fetch_findings(
            since=datetime(2024, 1, 1, tzinfo=timezone.utc),
            tenant_id="tenant-abc",
        )
        assert len(findings) == 1
        assert findings[0].raw_data["category"] == "device"

    @respx.mock
    def test_fetch_findings_lost_stolen(self, connector: ManageEngineMDMConnector, valid_credentials: dict):
        respx.get(f"{BASE}/api/v1/mdm/devices").mock(
            return_value=httpx.Response(200, json={"data": []})
        )
        respx.get(f"{BASE}/api/v1/mdm/lost_stolen").mock(
            return_value=httpx.Response(200, json={"data": [_mock_lost_stolen_event()]})
        )
        connector.authenticate(valid_credentials)
        findings = connector.fetch_findings(
            since=datetime(2024, 1, 1, tzinfo=timezone.utc),
            tenant_id="tenant-abc",
        )
        assert len(findings) == 1
        assert findings[0].raw_data["category"] == "lost_stolen"

    @respx.mock
    def test_fetch_findings_both_categories(self, connector: ManageEngineMDMConnector, valid_credentials: dict):
        respx.get(f"{BASE}/api/v1/mdm/devices").mock(
            return_value=httpx.Response(200, json={"data": [_mock_device()]})
        )
        respx.get(f"{BASE}/api/v1/mdm/lost_stolen").mock(
            return_value=httpx.Response(200, json={"data": [_mock_lost_stolen_event()]})
        )
        connector.authenticate(valid_credentials)
        findings = connector.fetch_findings(
            since=datetime(2024, 1, 1, tzinfo=timezone.utc),
            tenant_id="tenant-abc",
        )
        assert len(findings) == 2
        cats = {f.raw_data["category"] for f in findings}
        assert cats == {"device", "lost_stolen"}

    @respx.mock
    def test_fetch_findings_5xx_error(self, connector: ManageEngineMDMConnector, valid_credentials: dict):
        respx.get(f"{BASE}/api/v1/mdm/devices").mock(
            return_value=httpx.Response(200, json={"data": []})
        )
        respx.get(f"{BASE}/api/v1/mdm/lost_stolen").mock(
            return_value=httpx.Response(503, json={"error": "Service Unavailable"})
        )
        connector.authenticate(valid_credentials)
        with pytest.raises(ConnectorFetchError):
            connector.fetch_findings(
                since=datetime(2024, 1, 1, tzinfo=timezone.utc),
                tenant_id="tenant-abc",
            )

    def test_fetch_findings_not_authenticated(self, connector: ManageEngineMDMConnector):
        with pytest.raises(ConnectorFetchError):
            connector.fetch_findings(since=datetime.now(timezone.utc))


# ─────────────────────────────────────────────────────────────────────────────
# Tests: Normalization
# ─────────────────────────────────────────────────────────────────────────────

class TestManageEngineMDMNormalize:
    def test_normalize_device_jailbroken(self, connector: ManageEngineMDMConnector):
        raw = RawFinding(
            id="dev-001",
            source="manageengine_mdm",
            raw_data={
                "id": "dev-001",
                "device_name": "iPhone-CEO",
                "user_name": "ceo@example.com",
                "platform": "iOS",
                "os_version": "17.1",
                "is_jailbroken": True,
                "compliance_status": "non_compliant",
                "category": "device",
            },
            fetched_at=datetime.now(timezone.utc),
            tenant_id="t1",
        )
        record = connector.normalize(raw)
        assert isinstance(record, URIPRiskRecord)
        assert record.finding == "Jailbroken Device: iPhone-CEO"
        assert record.severity == "critical"
        assert record.asset == "iPhone-CEO"
        assert record.source == "manageengine_mdm"
        assert record.domain == "mobile"
        assert record.owner_team == "Mobile Security"

    def test_normalize_device_non_compliant(self, connector: ManageEngineMDMConnector):
        raw = RawFinding(
            id="dev-002",
            source="manageengine_mdm",
            raw_data={
                "id": "dev-002",
                "device_name": "Android-Dev",
                "is_jailbroken": False,
                "compliance_status": "non_compliant",
                "category": "device",
            },
            fetched_at=datetime.now(timezone.utc),
            tenant_id="t1",
        )
        record = connector.normalize(raw)
        assert record.finding == "Non-Compliant Mobile Device: Android-Dev"
        assert record.severity == "high"

    def test_normalize_device_compliant(self, connector: ManageEngineMDMConnector):
        raw = RawFinding(
            id="dev-003",
            source="manageengine_mdm",
            raw_data={
                "id": "dev-003",
                "device_name": "iPad-Sales",
                "is_jailbroken": False,
                "compliance_status": "compliant",
                "category": "device",
            },
            fetched_at=datetime.now(timezone.utc),
            tenant_id="t1",
        )
        record = connector.normalize(raw)
        assert record.finding == "Mobile Device: iPad-Sales"
        assert record.severity == "low"

    def test_normalize_lost_stolen_stolen(self, connector: ManageEngineMDMConnector):
        raw = RawFinding(
            id="evt-001",
            source="manageengine_mdm",
            raw_data={
                "id": "evt-001",
                "device_id": "dev-001",
                "device_name": "iPhone-CEO",
                "event_type": "stolen",
                "reported_at": "2024-01-15T09:00:00Z",
                "reported_by": "admin@example.com",
                "category": "lost_stolen",
            },
            fetched_at=datetime.now(timezone.utc),
            tenant_id="t1",
        )
        record = connector.normalize(raw)
        assert record.finding == "Stolen Device: iPhone-CEO"
        assert record.severity == "critical"
        assert record.asset == "iPhone-CEO"

    def test_normalize_lost_stolen_lost(self, connector: ManageEngineMDMConnector):
        raw = RawFinding(
            id="evt-002",
            source="manageengine_mdm",
            raw_data={
                "id": "evt-002",
                "device_name": "Android-Dev",
                "event_type": "lost",
                "category": "lost_stolen",
            },
            fetched_at=datetime.now(timezone.utc),
            tenant_id="t1",
        )
        record = connector.normalize(raw)
        assert record.finding == "Lost Device: Android-Dev"
        assert record.severity == "high"

    def test_normalize_lost_stolen_recovered(self, connector: ManageEngineMDMConnector):
        raw = RawFinding(
            id="evt-003",
            source="manageengine_mdm",
            raw_data={
                "id": "evt-003",
                "device_name": "iPad-Sales",
                "event_type": "recovered",
                "category": "lost_stolen",
            },
            fetched_at=datetime.now(timezone.utc),
            tenant_id="t1",
        )
        record = connector.normalize(raw)
        assert record.finding == "Device Event: iPad-Sales"
        assert record.severity == "medium"

    def test_normalize_unknown_category(self, connector: ManageEngineMDMConnector):
        raw = RawFinding(
            id="x",
            source="manageengine_mdm",
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

class TestManageEngineMDMErrorHandling:
    @respx.mock
    def test_rate_limit_during_auth(self, connector: ManageEngineMDMConnector):
        respx.get(f"{BASE}/api/v1/mdm/devices").mock(
            return_value=httpx.Response(429, json={"error": "Rate limited"})
        )
        with pytest.raises(ConnectorAuthError):
            connector.authenticate(
                {"base_url": BASE, "api_token": "tok", "tenant_id": "t"}
            )

    @respx.mock
    def test_fetch_increments_error_count(self, connector: ManageEngineMDMConnector, valid_credentials: dict):
        respx.get(f"{BASE}/api/v1/mdm/devices").mock(
            return_value=httpx.Response(200, json={"data": []})
        )
        respx.get(f"{BASE}/api/v1/mdm/lost_stolen").mock(
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

class TestManageEngineMDMTenantIsolation:
    @respx.mock
    def test_different_tenant_credentials_produce_different_results(self):
        base_a = "https://mdm-a.example.com"
        base_b = "https://mdm-b.example.com"

        respx.get(f"{base_a}/api/v1/mdm/devices").mock(
            return_value=httpx.Response(200, json={"data": [_mock_device(name="device-a")]})
        )
        respx.get(f"{base_a}/api/v1/mdm/lost_stolen").mock(
            return_value=httpx.Response(200, json={"data": []})
        )
        respx.get(f"{base_b}/api/v1/mdm/devices").mock(
            return_value=httpx.Response(200, json={"data": [_mock_device(name="device-b")]})
        )
        respx.get(f"{base_b}/api/v1/mdm/lost_stolen").mock(
            return_value=httpx.Response(200, json={"data": []})
        )

        conn_a = ManageEngineMDMConnector()
        session_a = conn_a.authenticate(
            {"base_url": base_a, "api_token": "TOK_A", "tenant_id": "tenant-a"}
        )
        findings_a = conn_a.fetch_findings(
            since=datetime(2024, 1, 1, tzinfo=timezone.utc),
            tenant_id="tenant-a",
        )

        conn_b = ManageEngineMDMConnector()
        session_b = conn_b.authenticate(
            {"base_url": base_b, "api_token": "TOK_B", "tenant_id": "tenant-b"}
        )
        findings_b = conn_b.fetch_findings(
            since=datetime(2024, 1, 1, tzinfo=timezone.utc),
            tenant_id="tenant-b",
        )

        assert session_a.tenant_id == "tenant-a"
        assert session_b.tenant_id == "tenant-b"
        assert all(f.tenant_id == "tenant-a" for f in findings_a)
        assert all(f.tenant_id == "tenant-b" for f in findings_b)
        assert findings_a[0].raw_data["device_name"] == "device-a"
        assert findings_b[0].raw_data["device_name"] == "device-b"


# ─────────────────────────────────────────────────────────────────────────────
# Tests: Health check
# ─────────────────────────────────────────────────────────────────────────────

class TestManageEngineMDMHealthCheck:
    def test_health_check_ok_fresh_connector(self, connector: ManageEngineMDMConnector):
        health = connector.health_check()
        assert isinstance(health, ConnectorHealth)
        assert health.connector_name == "manageengine_mdm"
        assert health.status == "ok"
        assert health.error_count == 0
        assert health.last_run is None

    @respx.mock
    def test_health_check_degraded_after_errors(self, connector: ManageEngineMDMConnector):
        respx.get(f"{BASE}/api/v1/mdm/devices").mock(
            return_value=httpx.Response(200, json={"data": []})
        )
        respx.get(f"{BASE}/api/v1/mdm/lost_stolen").mock(
            return_value=httpx.Response(500, json={"error": "boom"})
        )
        connector.authenticate(
            {"base_url": BASE, "api_token": "tok", "tenant_id": "t"}
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
    def test_health_check_error_after_many_errors(self, connector: ManageEngineMDMConnector):
        respx.get(f"{BASE}/api/v1/mdm/devices").mock(
            return_value=httpx.Response(200, json={"data": []})
        )
        respx.get(f"{BASE}/api/v1/mdm/lost_stolen").mock(
            return_value=httpx.Response(500, json={"error": "boom"})
        )
        connector.authenticate(
            {"base_url": BASE, "api_token": "tok", "tenant_id": "t"}
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
        self, connector: ManageEngineMDMConnector, valid_credentials: dict
    ):
        respx.get(f"{BASE}/api/v1/mdm/devices").mock(
            return_value=httpx.Response(200, json={"data": []})
        )
        respx.get(f"{BASE}/api/v1/mdm/lost_stolen").mock(
            return_value=httpx.Response(200, json={"data": []})
        )
        connector.authenticate(valid_credentials)
        connector.fetch_findings(since=datetime.now(timezone.utc))
        health = connector.health_check()
        assert health.last_run is not None
