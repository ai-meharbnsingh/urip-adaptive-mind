"""
TDD tests for the Netskope live connector.

Uses respx to mock all HTTP traffic — no real API calls.
Coverage: authentication (OAuth2), fetch_findings (DLP, threats, anomalies),
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
from connectors.netskope.connector import NetskopeConnector


# ─────────────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture
def connector() -> NetskopeConnector:
    return NetskopeConnector()


@pytest.fixture
def valid_credentials() -> dict[str, str]:
    return {
        "client_id": "NETSKOPE_CLIENT_ID",
        "client_secret": "NETSKOPE_CLIENT_SECRET",
        "tenant_id": "tenant-ns",
        "base_url": "https://tenant-ns.goskope.com",
    }


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

BASE = "https://tenant-ns.goskope.com"


def _mock_oauth_token():
    return respx.post(f"{BASE}/api/v2/oauth2/token").mock(
        return_value=httpx.Response(
            200,
            json={
                "access_token": "FAKE_TOKEN_123",
                "token_type": "Bearer",
                "expires_in": 3600,
            },
        )
    )


def _mock_dlp_incident() -> dict[str, Any]:
    return {
        "id": "dlp-001",
        "incident_name": "PII Exfiltration",
        "severity": "high",
        "user": "user@example.com",
        "app": "Gmail",
        "timestamp": "2024-01-15T10:30:00Z",
    }


def _mock_threat() -> dict[str, Any]:
    return {
        "id": "threat-001",
        "threat_name": "Malware Upload",
        "severity": "critical",
        "user": "user@example.com",
        "app": "Dropbox",
        "timestamp": "2024-01-15T10:30:00Z",
    }


def _mock_anomaly() -> dict[str, Any]:
    return {
        "id": "anom-001",
        "anomaly_name": "Impossible Travel",
        "severity": "medium",
        "user": "user@example.com",
        "app": "Office365",
        "timestamp": "2024-01-15T10:30:00Z",
    }


# ─────────────────────────────────────────────────────────────────────────────
# Tests: Authentication
# ─────────────────────────────────────────────────────────────────────────────

class TestNetskopeAuthentication:
    @respx.mock
    def test_authenticate_success(self, connector: NetskopeConnector, valid_credentials: dict):
        route = _mock_oauth_token()
        session = connector.authenticate(valid_credentials)
        assert isinstance(session, ConnectorSession)
        assert session.connector_name == "netskope"
        assert session.tenant_id == "tenant-ns"
        assert route.called

    @respx.mock
    def test_authenticate_failure_invalid_creds(self, connector: NetskopeConnector):
        respx.post(f"{BASE}/api/v2/oauth2/token").mock(
            return_value=httpx.Response(401, json={"error": "Unauthorized"})
        )
        with pytest.raises(ConnectorAuthError):
            connector.authenticate(
                {
                    "client_id": "bad",
                    "client_secret": "bad",
                    "tenant_id": "t",
                    "base_url": BASE,
                }
            )

    def test_authenticate_failure_missing_client_id(self, connector: NetskopeConnector):
        with pytest.raises(ConnectorAuthError):
            connector.authenticate(
                {"client_secret": "s", "tenant_id": "t", "base_url": BASE}
            )

    def test_authenticate_failure_missing_client_secret(self, connector: NetskopeConnector):
        with pytest.raises(ConnectorAuthError):
            connector.authenticate(
                {"client_id": "c", "tenant_id": "t", "base_url": BASE}
            )

    def test_authenticate_failure_missing_base_url(self, connector: NetskopeConnector):
        with pytest.raises(ConnectorAuthError):
            connector.authenticate(
                {"client_id": "c", "client_secret": "s", "tenant_id": "t"}
            )


# ─────────────────────────────────────────────────────────────────────────────
# Tests: Fetch findings
# ─────────────────────────────────────────────────────────────────────────────

class TestNetskopeFetchFindings:
    @respx.mock
    def test_fetch_findings_empty(self, connector: NetskopeConnector, valid_credentials: dict):
        _mock_oauth_token()
        respx.get(f"{BASE}/api/v2/incidents/dlp").mock(
            return_value=httpx.Response(200, json={"data": []})
        )
        respx.get(f"{BASE}/api/v2/incidents/threats").mock(
            return_value=httpx.Response(200, json={"data": []})
        )
        respx.get(f"{BASE}/api/v2/incidents/anomalies").mock(
            return_value=httpx.Response(200, json={"data": []})
        )
        connector.authenticate(valid_credentials)
        findings = connector.fetch_findings(
            since=datetime(2024, 1, 1, tzinfo=timezone.utc),
            tenant_id="tenant-ns",
        )
        assert findings == []

    @respx.mock
    def test_fetch_findings_dlp(self, connector: NetskopeConnector, valid_credentials: dict):
        _mock_oauth_token()
        respx.get(f"{BASE}/api/v2/incidents/dlp").mock(
            return_value=httpx.Response(200, json={"data": [_mock_dlp_incident()]})
        )
        respx.get(f"{BASE}/api/v2/incidents/threats").mock(
            return_value=httpx.Response(200, json={"data": []})
        )
        respx.get(f"{BASE}/api/v2/incidents/anomalies").mock(
            return_value=httpx.Response(200, json={"data": []})
        )
        connector.authenticate(valid_credentials)
        findings = connector.fetch_findings(
            since=datetime(2024, 1, 1, tzinfo=timezone.utc),
            tenant_id="tenant-ns",
        )
        assert len(findings) == 1
        assert findings[0].source == "netskope"
        assert findings[0].raw_data["category"] == "dlp"

    @respx.mock
    def test_fetch_findings_threats(self, connector: NetskopeConnector, valid_credentials: dict):
        _mock_oauth_token()
        respx.get(f"{BASE}/api/v2/incidents/dlp").mock(
            return_value=httpx.Response(200, json={"data": []})
        )
        respx.get(f"{BASE}/api/v2/incidents/threats").mock(
            return_value=httpx.Response(200, json={"data": [_mock_threat()]})
        )
        respx.get(f"{BASE}/api/v2/incidents/anomalies").mock(
            return_value=httpx.Response(200, json={"data": []})
        )
        connector.authenticate(valid_credentials)
        findings = connector.fetch_findings(
            since=datetime(2024, 1, 1, tzinfo=timezone.utc),
            tenant_id="tenant-ns",
        )
        assert len(findings) == 1
        assert findings[0].raw_data["category"] == "threat"

    @respx.mock
    def test_fetch_findings_anomalies(self, connector: NetskopeConnector, valid_credentials: dict):
        _mock_oauth_token()
        respx.get(f"{BASE}/api/v2/incidents/dlp").mock(
            return_value=httpx.Response(200, json={"data": []})
        )
        respx.get(f"{BASE}/api/v2/incidents/threats").mock(
            return_value=httpx.Response(200, json={"data": []})
        )
        respx.get(f"{BASE}/api/v2/incidents/anomalies").mock(
            return_value=httpx.Response(200, json={"data": [_mock_anomaly()]})
        )
        connector.authenticate(valid_credentials)
        findings = connector.fetch_findings(
            since=datetime(2024, 1, 1, tzinfo=timezone.utc),
            tenant_id="tenant-ns",
        )
        assert len(findings) == 1
        assert findings[0].raw_data["category"] == "anomaly"

    @respx.mock
    def test_fetch_findings_all_categories(self, connector: NetskopeConnector, valid_credentials: dict):
        _mock_oauth_token()
        respx.get(f"{BASE}/api/v2/incidents/dlp").mock(
            return_value=httpx.Response(200, json={"data": [_mock_dlp_incident()]})
        )
        respx.get(f"{BASE}/api/v2/incidents/threats").mock(
            return_value=httpx.Response(200, json={"data": [_mock_threat()]})
        )
        respx.get(f"{BASE}/api/v2/incidents/anomalies").mock(
            return_value=httpx.Response(200, json={"data": [_mock_anomaly()]})
        )
        connector.authenticate(valid_credentials)
        findings = connector.fetch_findings(
            since=datetime(2024, 1, 1, tzinfo=timezone.utc),
            tenant_id="tenant-ns",
        )
        assert len(findings) == 3
        cats = {f.raw_data["category"] for f in findings}
        assert cats == {"dlp", "threat", "anomaly"}

    @respx.mock
    def test_fetch_findings_5xx_error(self, connector: NetskopeConnector, valid_credentials: dict):
        _mock_oauth_token()
        respx.get(f"{BASE}/api/v2/incidents/dlp").mock(
            return_value=httpx.Response(503, json={"error": "Service Unavailable"})
        )
        connector.authenticate(valid_credentials)
        with pytest.raises(ConnectorFetchError):
            connector.fetch_findings(
                since=datetime(2024, 1, 1, tzinfo=timezone.utc),
                tenant_id="tenant-ns",
            )

    def test_fetch_findings_not_authenticated(self, connector: NetskopeConnector):
        with pytest.raises(ConnectorFetchError):
            connector.fetch_findings(since=datetime.now(timezone.utc))


# ─────────────────────────────────────────────────────────────────────────────
# Tests: Normalization
# ─────────────────────────────────────────────────────────────────────────────

class TestNetskopeNormalize:
    def test_normalize_dlp(self, connector: NetskopeConnector):
        raw = RawFinding(
            id="dlp-001",
            source="netskope",
            raw_data={
                "id": "dlp-001",
                "incident_name": "PII Exfiltration",
                "severity": "high",
                "user": "user@example.com",
                "app": "Gmail",
                "category": "dlp",
            },
            fetched_at=datetime.now(timezone.utc),
            tenant_id="t1",
        )
        record = connector.normalize(raw)
        assert isinstance(record, URIPRiskRecord)
        assert record.finding == "DLP: PII Exfiltration"
        assert record.severity == "high"
        assert record.asset == "user@example.com"
        assert record.source == "netskope"
        assert record.domain == "cloud"
        assert record.owner_team == "Data Protection"
        assert "Gmail" in record.description

    def test_normalize_threat(self, connector: NetskopeConnector):
        raw = RawFinding(
            id="threat-001",
            source="netskope",
            raw_data={
                "id": "threat-001",
                "threat_name": "Malware Upload",
                "severity": "critical",
                "user": "user@example.com",
                "app": "Dropbox",
                "category": "threat",
            },
            fetched_at=datetime.now(timezone.utc),
            tenant_id="t1",
        )
        record = connector.normalize(raw)
        assert record.finding == "Cloud Threat: Malware Upload"
        assert record.severity == "critical"
        assert record.domain == "cloud"
        assert record.owner_team == "Cloud Security"

    def test_normalize_anomaly(self, connector: NetskopeConnector):
        raw = RawFinding(
            id="anom-001",
            source="netskope",
            raw_data={
                "id": "anom-001",
                "anomaly_name": "Impossible Travel",
                "severity": "medium",
                "user": "user@example.com",
                "app": "Office365",
                "category": "anomaly",
            },
            fetched_at=datetime.now(timezone.utc),
            tenant_id="t1",
        )
        record = connector.normalize(raw)
        assert record.finding == "Anomaly: Impossible Travel"
        assert record.severity == "medium"
        assert record.domain == "cloud"
        assert record.owner_team == "Cloud Security"

    def test_normalize_unknown_category_defaults(self, connector: NetskopeConnector):
        raw = RawFinding(
            id="x-001",
            source="netskope",
            raw_data={
                "id": "x-001",
                "incident_name": "Unknown",
                "severity": "low",
                "user": "user@example.com",
                "category": "unknown",
            },
            fetched_at=datetime.now(timezone.utc),
            tenant_id="t1",
        )
        record = connector.normalize(raw)
        assert record.severity == "low"
        assert record.domain == "cloud"

    def test_normalize_severity_mapping(self, connector: NetskopeConnector):
        for sev_in, sev_out in [
            ("critical", "critical"),
            ("high", "high"),
            ("medium", "medium"),
            ("low", "low"),
        ]:
            raw = RawFinding(
                id="t",
                source="netskope",
                raw_data={
                    "id": "t",
                    "incident_name": "Test",
                    "severity": sev_in,
                    "user": "u",
                    "category": "dlp",
                },
                fetched_at=datetime.now(timezone.utc),
                tenant_id="t1",
            )
            record = connector.normalize(raw)
            assert record.severity == sev_out


# ─────────────────────────────────────────────────────────────────────────────
# Tests: Error handling
# ─────────────────────────────────────────────────────────────────────────────

class TestNetskopeErrorHandling:
    @respx.mock
    def test_rate_limit_during_auth(self, connector: NetskopeConnector):
        respx.post(f"{BASE}/api/v2/oauth2/token").mock(
            return_value=httpx.Response(429, json={"error": "Rate limited"})
        )
        with pytest.raises(ConnectorAuthError):
            connector.authenticate(
                {
                    "client_id": "c",
                    "client_secret": "s",
                    "tenant_id": "t",
                    "base_url": BASE,
                }
            )

    @respx.mock
    def test_fetch_increments_error_count(self, connector: NetskopeConnector, valid_credentials: dict):
        _mock_oauth_token()
        respx.get(f"{BASE}/api/v2/incidents/dlp").mock(
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

class TestNetskopeTenantIsolation:
    @respx.mock
    def test_different_tenant_credentials_produce_different_results(self):
        base_a = "https://tenant-a.goskope.com"
        base_b = "https://tenant-b.goskope.com"
        respx.post(f"{base_a}/api/v2/oauth2/token").mock(
            return_value=httpx.Response(
                200, json={"access_token": "TOK_A", "token_type": "Bearer", "expires_in": 3600}
            )
        )
        respx.post(f"{base_b}/api/v2/oauth2/token").mock(
            return_value=httpx.Response(
                200, json={"access_token": "TOK_B", "token_type": "Bearer", "expires_in": 3600}
            )
        )
        respx.get(f"{base_a}/api/v2/incidents/dlp").mock(
            return_value=httpx.Response(200, json={"data": []})
        )
        respx.get(f"{base_a}/api/v2/incidents/threats").mock(
            return_value=httpx.Response(200, json={"data": []})
        )
        respx.get(f"{base_a}/api/v2/incidents/anomalies").mock(
            return_value=httpx.Response(200, json={"data": []})
        )
        respx.get(f"{base_b}/api/v2/incidents/dlp").mock(
            return_value=httpx.Response(200, json={"data": []})
        )
        respx.get(f"{base_b}/api/v2/incidents/threats").mock(
            return_value=httpx.Response(200, json={"data": []})
        )
        respx.get(f"{base_b}/api/v2/incidents/anomalies").mock(
            return_value=httpx.Response(200, json={"data": []})
        )

        conn_a = NetskopeConnector()
        session_a = conn_a.authenticate(
            {
                "client_id": "C_A",
                "client_secret": "S_A",
                "tenant_id": "tenant-a",
                "base_url": base_a,
            }
        )
        findings_a = conn_a.fetch_findings(
            since=datetime(2024, 1, 1, tzinfo=timezone.utc),
            tenant_id="tenant-a",
        )

        conn_b = NetskopeConnector()
        session_b = conn_b.authenticate(
            {
                "client_id": "C_B",
                "client_secret": "S_B",
                "tenant_id": "tenant-b",
                "base_url": base_b,
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

class TestNetskopeHealthCheck:
    def test_health_check_ok_fresh_connector(self, connector: NetskopeConnector):
        health = connector.health_check()
        assert isinstance(health, ConnectorHealth)
        assert health.connector_name == "netskope"
        assert health.status == "ok"
        assert health.error_count == 0
        assert health.last_run is None

    @respx.mock
    def test_health_check_degraded_after_errors(self, connector: NetskopeConnector):
        _mock_oauth_token()
        respx.get(f"{BASE}/api/v2/incidents/dlp").mock(
            return_value=httpx.Response(500, json={"error": "boom"})
        )
        connector.authenticate(
            {
                "client_id": "c",
                "client_secret": "s",
                "tenant_id": "t",
                "base_url": BASE,
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
    def test_health_check_error_after_many_errors(self, connector: NetskopeConnector):
        _mock_oauth_token()
        respx.get(f"{BASE}/api/v2/incidents/dlp").mock(
            return_value=httpx.Response(500, json={"error": "boom"})
        )
        connector.authenticate(
            {
                "client_id": "c",
                "client_secret": "s",
                "tenant_id": "t",
                "base_url": BASE,
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
        self, connector: NetskopeConnector, valid_credentials: dict
    ):
        _mock_oauth_token()
        respx.get(f"{BASE}/api/v2/incidents/dlp").mock(
            return_value=httpx.Response(200, json={"data": []})
        )
        respx.get(f"{BASE}/api/v2/incidents/threats").mock(
            return_value=httpx.Response(200, json={"data": []})
        )
        respx.get(f"{BASE}/api/v2/incidents/anomalies").mock(
            return_value=httpx.Response(200, json={"data": []})
        )
        connector.authenticate(valid_credentials)
        connector.fetch_findings(since=datetime.now(timezone.utc))
        health = connector.health_check()
        assert health.last_run is not None
