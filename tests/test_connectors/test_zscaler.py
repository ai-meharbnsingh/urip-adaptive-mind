"""
TDD tests for the Zscaler live connector.

Uses respx to mock all HTTP traffic — no real API calls.
Coverage: authentication, fetch_findings (web threats, shadow SaaS, admin audit),
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
from connectors.zscaler.connector import ZscalerConnector


# ─────────────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture
def connector() -> ZscalerConnector:
    return ZscalerConnector()


@pytest.fixture
def valid_credentials() -> dict[str, str]:
    return {
        "api_key": "ZSCALER_API_KEY",
        "username": "admin@example.com",
        "password": "secret123",
        "cloud": "zscalerone",
        "tenant_id": "tenant-zs",
    }


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

BASE = "https://zsapi.zscalerone.net"


def _mock_auth_ok():
    return respx.post(f"{BASE}/api/v1/authenticatedSession").mock(
        return_value=httpx.Response(200, headers={"Set-Cookie": "JSESSIONID=abc123; Path=/"})
    )


def _mock_threat() -> dict[str, Any]:
    return {
        "id": "threat-001",
        "threat_name": "Phishing Domain",
        "url": "http://evil.example.com",
        "severity": "high",
        "category": "malware",
        "device": "ws-01",
        "timestamp": "2024-01-15T10:30:00Z",
    }


def _mock_saas_app() -> dict[str, Any]:
    return {
        "id": "saas-001",
        "name": "UnsanctionedFileShare",
        "category": "Cloud Storage",
        "risk_score": 85,
        "users": 12,
    }


def _mock_audit_log() -> dict[str, Any]:
    return {
        "id": "audit-001",
        "admin_user": "admin@example.com",
        "action": "DELETE_POLICY",
        "resource": "Firewall Rule #42",
        "severity": "medium",
        "timestamp": "2024-01-15T10:30:00Z",
    }


# ─────────────────────────────────────────────────────────────────────────────
# Tests: Authentication
# ─────────────────────────────────────────────────────────────────────────────

class TestZscalerAuthentication:
    @respx.mock
    def test_authenticate_success(self, connector: ZscalerConnector, valid_credentials: dict):
        route = _mock_auth_ok()
        session = connector.authenticate(valid_credentials)
        assert isinstance(session, ConnectorSession)
        assert session.connector_name == "zscaler"
        assert session.tenant_id == "tenant-zs"
        assert route.called

    @respx.mock
    def test_authenticate_failure_invalid_creds(self, connector: ZscalerConnector):
        respx.post(f"{BASE}/api/v1/authenticatedSession").mock(
            return_value=httpx.Response(401, json={"error": "Unauthorized"})
        )
        with pytest.raises(ConnectorAuthError):
            connector.authenticate(
                {
                    "api_key": "bad",
                    "username": "bad",
                    "password": "bad",
                    "cloud": "zscalerone",
                    "tenant_id": "t",
                }
            )

    def test_authenticate_failure_missing_api_key(self, connector: ZscalerConnector):
        with pytest.raises(ConnectorAuthError):
            connector.authenticate(
                {"username": "u", "password": "p", "cloud": "zscalerone"}
            )

    def test_authenticate_failure_missing_username(self, connector: ZscalerConnector):
        with pytest.raises(ConnectorAuthError):
            connector.authenticate(
                {"api_key": "k", "password": "p", "cloud": "zscalerone"}
            )

    def test_authenticate_failure_missing_password(self, connector: ZscalerConnector):
        with pytest.raises(ConnectorAuthError):
            connector.authenticate(
                {"api_key": "k", "username": "u", "cloud": "zscalerone"}
            )

    def test_authenticate_failure_missing_cloud(self, connector: ZscalerConnector):
        with pytest.raises(ConnectorAuthError):
            connector.authenticate(
                {"api_key": "k", "username": "u", "password": "p"}
            )

    @respx.mock
    def test_authenticate_uses_correct_cloud_url(self, connector: ZscalerConnector):
        custom = "https://zsapi.zscaler.net"
        route = respx.post(f"{custom}/api/v1/authenticatedSession").mock(
            return_value=httpx.Response(200, headers={"Set-Cookie": "JSESSIONID=x; Path=/"})
        )
        connector.authenticate(
            {
                "api_key": "k",
                "username": "u",
                "password": "p",
                "cloud": "zscaler",
                "tenant_id": "t",
            }
        )
        assert route.called


# ─────────────────────────────────────────────────────────────────────────────
# Tests: Fetch findings
# ─────────────────────────────────────────────────────────────────────────────

class TestZscalerFetchFindings:
    @respx.mock
    def test_fetch_findings_empty(self, connector: ZscalerConnector, valid_credentials: dict):
        _mock_auth_ok()
        respx.get(f"{BASE}/api/v1/threatIntel/threats").mock(
            return_value=httpx.Response(200, json={"threats": []})
        )
        respx.get(f"{BASE}/api/v1/casb/saasApps").mock(
            return_value=httpx.Response(200, json={"saasApps": []})
        )
        respx.get(f"{BASE}/api/v1/users/admin/auditLogs").mock(
            return_value=httpx.Response(200, json={"auditLogs": []})
        )
        connector.authenticate(valid_credentials)
        findings = connector.fetch_findings(
            since=datetime(2024, 1, 1, tzinfo=timezone.utc),
            tenant_id="tenant-zs",
        )
        assert findings == []

    @respx.mock
    def test_fetch_findings_web_threats(self, connector: ZscalerConnector, valid_credentials: dict):
        _mock_auth_ok()
        respx.get(f"{BASE}/api/v1/threatIntel/threats").mock(
            return_value=httpx.Response(200, json={"threats": [_mock_threat()]})
        )
        respx.get(f"{BASE}/api/v1/casb/saasApps").mock(
            return_value=httpx.Response(200, json={"saasApps": []})
        )
        respx.get(f"{BASE}/api/v1/users/admin/auditLogs").mock(
            return_value=httpx.Response(200, json={"auditLogs": []})
        )
        connector.authenticate(valid_credentials)
        findings = connector.fetch_findings(
            since=datetime(2024, 1, 1, tzinfo=timezone.utc),
            tenant_id="tenant-zs",
        )
        assert len(findings) == 1
        assert findings[0].source == "zscaler"
        assert findings[0].raw_data["category"] == "web_threat"

    @respx.mock
    def test_fetch_findings_shadow_saas(self, connector: ZscalerConnector, valid_credentials: dict):
        _mock_auth_ok()
        respx.get(f"{BASE}/api/v1/threatIntel/threats").mock(
            return_value=httpx.Response(200, json={"threats": []})
        )
        respx.get(f"{BASE}/api/v1/casb/saasApps").mock(
            return_value=httpx.Response(200, json={"saasApps": [_mock_saas_app()]})
        )
        respx.get(f"{BASE}/api/v1/users/admin/auditLogs").mock(
            return_value=httpx.Response(200, json={"auditLogs": []})
        )
        connector.authenticate(valid_credentials)
        findings = connector.fetch_findings(
            since=datetime(2024, 1, 1, tzinfo=timezone.utc),
            tenant_id="tenant-zs",
        )
        assert len(findings) == 1
        assert findings[0].raw_data["category"] == "shadow_saas"

    @respx.mock
    def test_fetch_findings_admin_audit(self, connector: ZscalerConnector, valid_credentials: dict):
        _mock_auth_ok()
        respx.get(f"{BASE}/api/v1/threatIntel/threats").mock(
            return_value=httpx.Response(200, json={"threats": []})
        )
        respx.get(f"{BASE}/api/v1/casb/saasApps").mock(
            return_value=httpx.Response(200, json={"saasApps": []})
        )
        respx.get(f"{BASE}/api/v1/users/admin/auditLogs").mock(
            return_value=httpx.Response(200, json={"auditLogs": [_mock_audit_log()]})
        )
        connector.authenticate(valid_credentials)
        findings = connector.fetch_findings(
            since=datetime(2024, 1, 1, tzinfo=timezone.utc),
            tenant_id="tenant-zs",
        )
        assert len(findings) == 1
        assert findings[0].raw_data["category"] == "casb_violation"

    @respx.mock
    def test_fetch_findings_all_categories(self, connector: ZscalerConnector, valid_credentials: dict):
        _mock_auth_ok()
        respx.get(f"{BASE}/api/v1/threatIntel/threats").mock(
            return_value=httpx.Response(200, json={"threats": [_mock_threat(), _mock_threat()]})
        )
        respx.get(f"{BASE}/api/v1/casb/saasApps").mock(
            return_value=httpx.Response(200, json={"saasApps": [_mock_saas_app()]})
        )
        respx.get(f"{BASE}/api/v1/users/admin/auditLogs").mock(
            return_value=httpx.Response(200, json={"auditLogs": [_mock_audit_log()]})
        )
        connector.authenticate(valid_credentials)
        findings = connector.fetch_findings(
            since=datetime(2024, 1, 1, tzinfo=timezone.utc),
            tenant_id="tenant-zs",
        )
        assert len(findings) == 4
        cats = {f.raw_data["category"] for f in findings}
        assert cats == {"web_threat", "shadow_saas", "casb_violation"}

    @respx.mock
    def test_fetch_findings_5xx_error(self, connector: ZscalerConnector, valid_credentials: dict):
        _mock_auth_ok()
        respx.get(f"{BASE}/api/v1/threatIntel/threats").mock(
            return_value=httpx.Response(503, json={"error": "Service Unavailable"})
        )
        connector.authenticate(valid_credentials)
        with pytest.raises(ConnectorFetchError):
            connector.fetch_findings(
                since=datetime(2024, 1, 1, tzinfo=timezone.utc),
                tenant_id="tenant-zs",
            )

    def test_fetch_findings_not_authenticated(self, connector: ZscalerConnector):
        with pytest.raises(ConnectorFetchError):
            connector.fetch_findings(since=datetime.now(timezone.utc))


# ─────────────────────────────────────────────────────────────────────────────
# Tests: Normalization
# ─────────────────────────────────────────────────────────────────────────────

class TestZscalerNormalize:
    def test_normalize_web_threat(self, connector: ZscalerConnector):
        raw = RawFinding(
            id="threat-001",
            source="zscaler",
            raw_data={
                "id": "threat-001",
                "threat_name": "Phishing Domain",
                "url": "http://evil.example.com",
                "severity": "high",
                "category": "web_threat",
                "device": "ws-01",
            },
            fetched_at=datetime.now(timezone.utc),
            tenant_id="t1",
        )
        record = connector.normalize(raw)
        assert isinstance(record, URIPRiskRecord)
        assert record.finding == "Phishing Domain"
        assert record.severity == "high"
        assert record.asset == "ws-01"
        assert record.source == "zscaler"
        assert record.domain == "network"
        assert record.owner_team == "Network Security"
        assert "evil.example.com" in record.description

    def test_normalize_shadow_saas(self, connector: ZscalerConnector):
        raw = RawFinding(
            id="saas-001",
            source="zscaler",
            raw_data={
                "id": "saas-001",
                "name": "UnsanctionedFileShare",
                "category": "shadow_saas",
                "risk_score": 85,
                "users": 12,
            },
            fetched_at=datetime.now(timezone.utc),
            tenant_id="t1",
        )
        record = connector.normalize(raw)
        assert record.finding == "Shadow SaaS: UnsanctionedFileShare"
        assert record.severity == "high"
        assert record.domain == "cloud"
        assert record.asset == "UnsanctionedFileShare"
        assert record.owner_team == "Cloud Security"

    def test_normalize_casb_violation(self, connector: ZscalerConnector):
        raw = RawFinding(
            id="audit-001",
            source="zscaler",
            raw_data={
                "id": "audit-001",
                "admin_user": "admin@example.com",
                "action": "DELETE_POLICY",
                "resource": "Firewall Rule #42",
                "severity": "medium",
                "category": "casb_violation",
            },
            fetched_at=datetime.now(timezone.utc),
            tenant_id="t1",
        )
        record = connector.normalize(raw)
        assert record.finding == "Admin Action: DELETE_POLICY"
        assert record.severity == "medium"
        assert record.domain == "network"
        assert record.asset == "admin@example.com"
        assert record.owner_team == "Network Security"
        assert "Firewall Rule #42" in record.description

    def test_normalize_unknown_category_defaults(self, connector: ZscalerConnector):
        raw = RawFinding(
            id="x-001",
            source="zscaler",
            raw_data={
                "id": "x-001",
                "threat_name": "Unknown",
                "category": "unknown",
                "severity": "low",
                "device": "dev-01",
            },
            fetched_at=datetime.now(timezone.utc),
            tenant_id="t1",
        )
        record = connector.normalize(raw)
        assert record.severity == "low"
        assert record.domain == "network"

    def test_normalize_severity_mapping(self, connector: ZscalerConnector):
        for sev_in, sev_out in [("critical", "critical"), ("high", "high"), ("medium", "medium"), ("low", "low")]:
            raw = RawFinding(
                id="t",
                source="zscaler",
                raw_data={
                    "id": "t",
                    "threat_name": "Test",
                    "category": "web_threat",
                    "severity": sev_in,
                    "device": "d",
                },
                fetched_at=datetime.now(timezone.utc),
                tenant_id="t1",
            )
            record = connector.normalize(raw)
            assert record.severity == sev_out


# ─────────────────────────────────────────────────────────────────────────────
# Tests: Error handling
# ─────────────────────────────────────────────────────────────────────────────

class TestZscalerErrorHandling:
    @respx.mock
    def test_rate_limit_during_auth(self, connector: ZscalerConnector):
        respx.post(f"{BASE}/api/v1/authenticatedSession").mock(
            return_value=httpx.Response(429, json={"error": "Rate limited"})
        )
        with pytest.raises(ConnectorAuthError):
            connector.authenticate(
                {
                    "api_key": "k",
                    "username": "u",
                    "password": "p",
                    "cloud": "zscalerone",
                    "tenant_id": "t",
                }
            )

    @respx.mock
    def test_fetch_increments_error_count(self, connector: ZscalerConnector, valid_credentials: dict):
        _mock_auth_ok()
        respx.get(f"{BASE}/api/v1/threatIntel/threats").mock(
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

class TestZscalerTenantIsolation:
    @respx.mock
    def test_different_tenant_credentials_produce_different_results(self):
        base_a = "https://zsapi.zscalerone.net"
        base_b = "https://zsapi.zscalertwo.net"
        respx.post(f"{base_a}/api/v1/authenticatedSession").mock(
            return_value=httpx.Response(200, headers={"Set-Cookie": "JSESSIONID=a; Path=/"})
        )
        respx.post(f"{base_b}/api/v1/authenticatedSession").mock(
            return_value=httpx.Response(200, headers={"Set-Cookie": "JSESSIONID=b; Path=/"})
        )
        respx.get(f"{base_a}/api/v1/threatIntel/threats").mock(
            return_value=httpx.Response(200, json={"threats": []})
        )
        respx.get(f"{base_a}/api/v1/casb/saasApps").mock(
            return_value=httpx.Response(200, json={"saasApps": []})
        )
        respx.get(f"{base_a}/api/v1/users/admin/auditLogs").mock(
            return_value=httpx.Response(200, json={"auditLogs": []})
        )
        respx.get(f"{base_b}/api/v1/threatIntel/threats").mock(
            return_value=httpx.Response(200, json={"threats": []})
        )
        respx.get(f"{base_b}/api/v1/casb/saasApps").mock(
            return_value=httpx.Response(200, json={"saasApps": []})
        )
        respx.get(f"{base_b}/api/v1/users/admin/auditLogs").mock(
            return_value=httpx.Response(200, json={"auditLogs": []})
        )

        conn_a = ZscalerConnector()
        session_a = conn_a.authenticate(
            {
                "api_key": "K_A",
                "username": "u",
                "password": "p",
                "cloud": "zscalerone",
                "tenant_id": "tenant-a",
            }
        )
        findings_a = conn_a.fetch_findings(
            since=datetime(2024, 1, 1, tzinfo=timezone.utc),
            tenant_id="tenant-a",
        )

        conn_b = ZscalerConnector()
        session_b = conn_b.authenticate(
            {
                "api_key": "K_B",
                "username": "u",
                "password": "p",
                "cloud": "zscalertwo",
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

class TestZscalerHealthCheck:
    def test_health_check_ok_fresh_connector(self, connector: ZscalerConnector):
        health = connector.health_check()
        assert isinstance(health, ConnectorHealth)
        assert health.connector_name == "zscaler"
        assert health.status == "ok"
        assert health.error_count == 0
        assert health.last_run is None

    @respx.mock
    def test_health_check_degraded_after_errors(self, connector: ZscalerConnector):
        _mock_auth_ok()
        respx.get(f"{BASE}/api/v1/threatIntel/threats").mock(
            return_value=httpx.Response(500, json={"error": "boom"})
        )
        connector.authenticate(
            {
                "api_key": "k",
                "username": "u",
                "password": "p",
                "cloud": "zscalerone",
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
    def test_health_check_error_after_many_errors(self, connector: ZscalerConnector):
        _mock_auth_ok()
        respx.get(f"{BASE}/api/v1/threatIntel/threats").mock(
            return_value=httpx.Response(500, json={"error": "boom"})
        )
        connector.authenticate(
            {
                "api_key": "k",
                "username": "u",
                "password": "p",
                "cloud": "zscalerone",
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
        self, connector: ZscalerConnector, valid_credentials: dict
    ):
        _mock_auth_ok()
        respx.get(f"{BASE}/api/v1/threatIntel/threats").mock(
            return_value=httpx.Response(200, json={"threats": []})
        )
        respx.get(f"{BASE}/api/v1/casb/saasApps").mock(
            return_value=httpx.Response(200, json={"saasApps": []})
        )
        respx.get(f"{BASE}/api/v1/users/admin/auditLogs").mock(
            return_value=httpx.Response(200, json={"auditLogs": []})
        )
        connector.authenticate(valid_credentials)
        connector.fetch_findings(since=datetime.now(timezone.utc))
        health = connector.health_check()
        assert health.last_run is not None
