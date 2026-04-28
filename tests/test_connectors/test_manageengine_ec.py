"""
TDD tests for the ManageEngine Endpoint Central live connector.

Uses respx to mock all HTTP traffic — no real API calls.
Coverage: authentication, fetch_findings (computers, missing patches),
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
from connectors.manageengine_ec.connector import ManageEngineECConnector


# ─────────────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture
def connector() -> ManageEngineECConnector:
    return ManageEngineECConnector()


@pytest.fixture
def valid_credentials() -> dict[str, str]:
    return {
        "base_url": "https://endpointcentral.example.com",
        "api_token": "TEST_API_TOKEN",
        "tenant_id": "tenant-abc",
        "max_requests_per_hour": 1_000_000,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

BASE = "https://endpointcentral.example.com"


def _mock_computer(
    computer_id: str = "pc-001",
    name: str = "WS-01",
    patch_status: str = "compliant",
    compliance_score: float = 95.0,
) -> dict[str, Any]:
    return {
        "id": computer_id,
        "name": name,
        "ip_address": "10.0.0.1",
        "os": "Windows 11",
        "patch_status": patch_status,
        "compliance_score": compliance_score,
        "last_scan_time": "2024-01-15T10:00:00Z",
    }


def _mock_missing_patch(
    patch_id: str = "patch-001",
    computer_id: str = "pc-001",
    severity: str = "critical",
) -> dict[str, Any]:
    return {
        "id": patch_id,
        "computer_id": computer_id,
        "computer_name": "WS-01",
        "patch_id": "KB5028185",
        "patch_name": "Security Update for Windows",
        "severity": severity,
        "release_date": "2024-01-10",
    }


# ─────────────────────────────────────────────────────────────────────────────
# Tests: Authentication
# ─────────────────────────────────────────────────────────────────────────────

class TestManageEngineECAuthentication:
    @respx.mock
    def test_authenticate_success(self, connector: ManageEngineECConnector, valid_credentials: dict):
        route = respx.get(f"{BASE}/api/v1/sdp/Computers").mock(
            return_value=httpx.Response(200, json={"data": []})
        )
        session = connector.authenticate(valid_credentials)
        assert isinstance(session, ConnectorSession)
        assert session.connector_name == "manageengine_ec"
        assert session.tenant_id == "tenant-abc"
        assert route.called

    @respx.mock
    def test_authenticate_failure_invalid_token(self, connector: ManageEngineECConnector):
        respx.get(f"{BASE}/api/v1/sdp/Computers").mock(
            return_value=httpx.Response(401, json={"error": "Unauthorized"})
        )
        with pytest.raises(ConnectorAuthError):
            connector.authenticate(
                {
                    "base_url": BASE,
                    "api_token": "bad",
                    "tenant_id": "t",
                }
            )

    def test_authenticate_failure_missing_base_url(self, connector: ManageEngineECConnector):
        with pytest.raises(ConnectorAuthError):
            connector.authenticate({"api_token": "t", "tenant_id": "t"})

    def test_authenticate_failure_missing_api_token(self, connector: ManageEngineECConnector):
        with pytest.raises(ConnectorAuthError):
            connector.authenticate({"base_url": BASE, "tenant_id": "t"})

    @respx.mock
    def test_authenticate_uses_custom_base_url(self, connector: ManageEngineECConnector):
        custom_url = "https://meec.custom.com"
        route = respx.get(f"{custom_url}/api/v1/sdp/Computers").mock(
            return_value=httpx.Response(200, json={"data": []})
        )
        connector.authenticate(
            {"base_url": custom_url, "api_token": "tok", "tenant_id": "t"}
        )
        assert route.called


# ─────────────────────────────────────────────────────────────────────────────
# Tests: Fetch findings
# ─────────────────────────────────────────────────────────────────────────────

class TestManageEngineECFetchFindings:
    @respx.mock
    def test_fetch_findings_empty(self, connector: ManageEngineECConnector, valid_credentials: dict):
        respx.get(f"{BASE}/api/v1/sdp/Computers").mock(
            return_value=httpx.Response(200, json={"data": []})
        )
        respx.get(f"{BASE}/api/v1/patch/missing_patches").mock(
            return_value=httpx.Response(200, json={"data": []})
        )
        connector.authenticate(valid_credentials)
        findings = connector.fetch_findings(
            since=datetime(2024, 1, 1, tzinfo=timezone.utc),
            tenant_id="tenant-abc",
        )
        assert findings == []

    @respx.mock
    def test_fetch_findings_computers(self, connector: ManageEngineECConnector, valid_credentials: dict):
        respx.get(f"{BASE}/api/v1/sdp/Computers").mock(
            return_value=httpx.Response(200, json={"data": [_mock_computer(patch_status="non_compliant")]})
        )
        respx.get(f"{BASE}/api/v1/patch/missing_patches").mock(
            return_value=httpx.Response(200, json={"data": []})
        )
        connector.authenticate(valid_credentials)
        findings = connector.fetch_findings(
            since=datetime(2024, 1, 1, tzinfo=timezone.utc),
            tenant_id="tenant-abc",
        )
        assert len(findings) == 1
        assert findings[0].raw_data["category"] == "computer"

    @respx.mock
    def test_fetch_findings_missing_patches(self, connector: ManageEngineECConnector, valid_credentials: dict):
        respx.get(f"{BASE}/api/v1/sdp/Computers").mock(
            return_value=httpx.Response(200, json={"data": []})
        )
        respx.get(f"{BASE}/api/v1/patch/missing_patches").mock(
            return_value=httpx.Response(200, json={"data": [_mock_missing_patch()]})
        )
        connector.authenticate(valid_credentials)
        findings = connector.fetch_findings(
            since=datetime(2024, 1, 1, tzinfo=timezone.utc),
            tenant_id="tenant-abc",
        )
        assert len(findings) == 1
        assert findings[0].raw_data["category"] == "missing_patch"

    @respx.mock
    def test_fetch_findings_both_categories(self, connector: ManageEngineECConnector, valid_credentials: dict):
        respx.get(f"{BASE}/api/v1/sdp/Computers").mock(
            return_value=httpx.Response(200, json={"data": [_mock_computer()]})
        )
        respx.get(f"{BASE}/api/v1/patch/missing_patches").mock(
            return_value=httpx.Response(200, json={"data": [_mock_missing_patch()]})
        )
        connector.authenticate(valid_credentials)
        findings = connector.fetch_findings(
            since=datetime(2024, 1, 1, tzinfo=timezone.utc),
            tenant_id="tenant-abc",
        )
        assert len(findings) == 2
        cats = {f.raw_data["category"] for f in findings}
        assert cats == {"computer", "missing_patch"}

    @respx.mock
    def test_fetch_findings_5xx_error(self, connector: ManageEngineECConnector, valid_credentials: dict):
        respx.get(f"{BASE}/api/v1/sdp/Computers").mock(
            return_value=httpx.Response(200, json={"data": []})
        )
        respx.get(f"{BASE}/api/v1/patch/missing_patches").mock(
            return_value=httpx.Response(503, json={"error": "Service Unavailable"})
        )
        connector.authenticate(valid_credentials)
        with pytest.raises(ConnectorFetchError):
            connector.fetch_findings(
                since=datetime(2024, 1, 1, tzinfo=timezone.utc),
                tenant_id="tenant-abc",
            )

    def test_fetch_findings_not_authenticated(self, connector: ManageEngineECConnector):
        with pytest.raises(ConnectorFetchError):
            connector.fetch_findings(since=datetime.now(timezone.utc))


# ─────────────────────────────────────────────────────────────────────────────
# Tests: Normalization
# ─────────────────────────────────────────────────────────────────────────────

class TestManageEngineECNormalize:
    def test_normalize_computer_compliant(self, connector: ManageEngineECConnector):
        raw = RawFinding(
            id="pc-001",
            source="manageengine_ec",
            raw_data={
                "id": "pc-001",
                "name": "WS-01",
                "ip_address": "10.0.0.1",
                "os": "Windows 11",
                "patch_status": "compliant",
                "compliance_score": 98.0,
                "category": "computer",
            },
            fetched_at=datetime.now(timezone.utc),
            tenant_id="t1",
        )
        record = connector.normalize(raw)
        assert isinstance(record, URIPRiskRecord)
        assert record.finding == "Endpoint Patch Status: WS-01"
        assert record.severity == "low"
        assert record.asset == "WS-01"
        assert record.source == "manageengine_ec"
        assert record.domain == "endpoint"
        assert record.owner_team == "Endpoint Security"

    def test_normalize_computer_non_compliant(self, connector: ManageEngineECConnector):
        raw = RawFinding(
            id="pc-002",
            source="manageengine_ec",
            raw_data={
                "id": "pc-002",
                "name": "WS-02",
                "patch_status": "non_compliant",
                "compliance_score": 45.0,
                "category": "computer",
            },
            fetched_at=datetime.now(timezone.utc),
            tenant_id="t1",
        )
        record = connector.normalize(raw)
        assert record.finding == "Non-Compliant Endpoint: WS-02"
        assert record.severity == "high"

    def test_normalize_computer_unknown_status(self, connector: ManageEngineECConnector):
        raw = RawFinding(
            id="pc-003",
            source="manageengine_ec",
            raw_data={
                "id": "pc-003",
                "name": "WS-03",
                "patch_status": "unknown",
                "category": "computer",
            },
            fetched_at=datetime.now(timezone.utc),
            tenant_id="t1",
        )
        record = connector.normalize(raw)
        assert record.finding == "Unknown Patch Status: WS-03"
        assert record.severity == "medium"

    def test_normalize_missing_patch_critical(self, connector: ManageEngineECConnector):
        raw = RawFinding(
            id="patch-001",
            source="manageengine_ec",
            raw_data={
                "id": "patch-001",
                "computer_id": "pc-001",
                "computer_name": "WS-01",
                "patch_id": "KB5028185",
                "patch_name": "Security Update for Windows",
                "severity": "critical",
                "category": "missing_patch",
            },
            fetched_at=datetime.now(timezone.utc),
            tenant_id="t1",
        )
        record = connector.normalize(raw)
        assert record.finding == "Missing Patch: Security Update for Windows"
        assert record.severity == "critical"
        assert record.asset == "WS-01"

    def test_normalize_missing_patch_low(self, connector: ManageEngineECConnector):
        raw = RawFinding(
            id="patch-002",
            source="manageengine_ec",
            raw_data={
                "id": "patch-002",
                "computer_id": "pc-002",
                "patch_name": "Optional Driver Update",
                "severity": "low",
                "category": "missing_patch",
            },
            fetched_at=datetime.now(timezone.utc),
            tenant_id="t1",
        )
        record = connector.normalize(raw)
        assert record.severity == "low"

    def test_normalize_unknown_category(self, connector: ManageEngineECConnector):
        raw = RawFinding(
            id="x",
            source="manageengine_ec",
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

class TestManageEngineECErrorHandling:
    @respx.mock
    def test_rate_limit_during_auth(self, connector: ManageEngineECConnector):
        respx.get(f"{BASE}/api/v1/sdp/Computers").mock(
            return_value=httpx.Response(429, json={"error": "Rate limited"})
        )
        with pytest.raises(ConnectorAuthError):
            connector.authenticate(
                {"base_url": BASE, "api_token": "tok", "tenant_id": "t"}
            )

    @respx.mock
    def test_fetch_increments_error_count(self, connector: ManageEngineECConnector, valid_credentials: dict):
        respx.get(f"{BASE}/api/v1/sdp/Computers").mock(
            return_value=httpx.Response(200, json={"data": []})
        )
        respx.get(f"{BASE}/api/v1/patch/missing_patches").mock(
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

class TestManageEngineECTenantIsolation:
    @respx.mock
    def test_different_tenant_credentials_produce_different_results(self):
        base_a = "https://meec-a.example.com"
        base_b = "https://meec-b.example.com"

        respx.get(f"{base_a}/api/v1/sdp/Computers").mock(
            return_value=httpx.Response(200, json={"data": [_mock_computer(name="host-a")]})
        )
        respx.get(f"{base_a}/api/v1/patch/missing_patches").mock(
            return_value=httpx.Response(200, json={"data": []})
        )
        respx.get(f"{base_b}/api/v1/sdp/Computers").mock(
            return_value=httpx.Response(200, json={"data": [_mock_computer(name="host-b")]})
        )
        respx.get(f"{base_b}/api/v1/patch/missing_patches").mock(
            return_value=httpx.Response(200, json={"data": []})
        )

        conn_a = ManageEngineECConnector()
        session_a = conn_a.authenticate(
            {"base_url": base_a, "api_token": "TOK_A", "tenant_id": "tenant-a"}
        )
        findings_a = conn_a.fetch_findings(
            since=datetime(2024, 1, 1, tzinfo=timezone.utc),
            tenant_id="tenant-a",
        )

        conn_b = ManageEngineECConnector()
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
        assert findings_a[0].raw_data["name"] == "host-a"
        assert findings_b[0].raw_data["name"] == "host-b"


# ─────────────────────────────────────────────────────────────────────────────
# Tests: Health check
# ─────────────────────────────────────────────────────────────────────────────

class TestManageEngineECHealthCheck:
    def test_health_check_ok_fresh_connector(self, connector: ManageEngineECConnector):
        health = connector.health_check()
        assert isinstance(health, ConnectorHealth)
        assert health.connector_name == "manageengine_ec"
        assert health.status == "ok"
        assert health.error_count == 0
        assert health.last_run is None

    @respx.mock
    def test_health_check_degraded_after_errors(self, connector: ManageEngineECConnector):
        respx.get(f"{BASE}/api/v1/sdp/Computers").mock(
            return_value=httpx.Response(200, json={"data": []})
        )
        respx.get(f"{BASE}/api/v1/patch/missing_patches").mock(
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
    def test_health_check_error_after_many_errors(self, connector: ManageEngineECConnector):
        respx.get(f"{BASE}/api/v1/sdp/Computers").mock(
            return_value=httpx.Response(200, json={"data": []})
        )
        respx.get(f"{BASE}/api/v1/patch/missing_patches").mock(
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
        self, connector: ManageEngineECConnector, valid_credentials: dict
    ):
        respx.get(f"{BASE}/api/v1/sdp/Computers").mock(
            return_value=httpx.Response(200, json={"data": []})
        )
        respx.get(f"{BASE}/api/v1/patch/missing_patches").mock(
            return_value=httpx.Response(200, json={"data": []})
        )
        connector.authenticate(valid_credentials)
        connector.fetch_findings(since=datetime.now(timezone.utc))
        health = connector.health_check()
        assert health.last_run is not None
