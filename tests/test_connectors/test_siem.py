"""
TDD tests for the Generic SIEM/SoC connector.

Uses respx to mock all HTTP traffic — no real API calls.
Coverage: authentication per sub-adapter (Splunk, Elastic, QRadar),
fetched search results, normalization, severity mapping, domain inference,
health check, error handling, tenant isolation.
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
from connectors.siem.connector import SiemConnector


# ─────────────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture
def connector() -> SiemConnector:
    return SiemConnector()


@pytest.fixture
def splunk_credentials() -> dict[str, Any]:
    return {
        "siem_type": "splunk",
        "base_url": "https://splunk.example.com",
        "token": "splunk-hec-token-123",
        "tenant_id": "tenant-siem",
        "saved_search": "security_alerts_last_15m",
    }


@pytest.fixture
def elastic_credentials() -> dict[str, Any]:
    return {
        "siem_type": "elastic",
        "base_url": "https://elastic.example.com",
        "api_key": "elastic-api-key-456",
        "tenant_id": "tenant-siem",
        "query_dsl": '{"query": {"match_all": {}}}',
    }


@pytest.fixture
def qradar_credentials() -> dict[str, Any]:
    return {
        "siem_type": "qradar",
        "base_url": "https://qradar.example.com",
        "sec_token": "qradar-sec-token-789",
        "tenant_id": "tenant-siem",
        "ariel_query": "SELECT * FROM events WHERE severity >= 5 LAST 15 MINUTES",
    }


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _mock_splunk_event(
    event_id: str = "splunk-ev-001",
    severity: str = "high",
    domain_hint: str = "network",
) -> dict[str, Any]:
    return {
        "_time": "2024-06-15T10:00:00.000+00:00",
        "source": "firewall",
        "host": "fw-01",
        "event_id": event_id,
        "severity": severity,
        "message": f"Suspicious {domain_hint} activity detected",
        "domain_hint": domain_hint,
    }


def _mock_elastic_hit(
    hit_id: str = "elastic-hit-001",
    severity: str = "critical",
    domain_hint: str = "endpoint",
) -> dict[str, Any]:
    return {
        "_id": hit_id,
        "_source": {
            "@timestamp": "2024-06-15T10:00:00.000Z",
            "event.severity": 4,
            "host.name": "ws-01",
            "message": f"Malware detected on {domain_hint}",
            "domain_hint": domain_hint,
            "severity_label": severity,
        },
    }


def _mock_qradar_event(
    event_id: str = "qradar-ev-001",
    severity: int = 7,
    domain_hint: str = "identity",
) -> dict[str, Any]:
    return {
        "id": event_id,
        "starttime": 1718445600000,
        "severity": severity,
        "eventname": "Failed Login",
        "sourceip": "10.0.0.5",
        "domain_hint": domain_hint,
        "message": f"Multiple failed logins — {domain_hint} risk",
    }


# ─────────────────────────────────────────────────────────────────────────────
# Tests: Authentication
# ─────────────────────────────────────────────────────────────────────────────

class TestSiemAuthentication:
    @respx.mock
    def test_authenticate_splunk_success(self, connector: SiemConnector, splunk_credentials: dict):
        route = respx.get("https://splunk.example.com/services/server/info").mock(
            return_value=httpx.Response(200, text='<title>Server Info</title>')
        )
        session = connector.authenticate(splunk_credentials)
        assert isinstance(session, ConnectorSession)
        assert session.connector_name == "siem"
        assert "splunk" in session.token
        assert route.called

    @respx.mock
    def test_authenticate_splunk_failure(self, connector: SiemConnector, splunk_credentials: dict):
        respx.get("https://splunk.example.com/services/server/info").mock(
            return_value=httpx.Response(401, text='Unauthorized')
        )
        with pytest.raises(ConnectorAuthError):
            connector.authenticate(splunk_credentials)

    @respx.mock
    def test_authenticate_elastic_success(self, connector: SiemConnector, elastic_credentials: dict):
        route = respx.get("https://elastic.example.com/_cluster/health").mock(
            return_value=httpx.Response(200, json={"status": "green"})
        )
        session = connector.authenticate(elastic_credentials)
        assert isinstance(session, ConnectorSession)
        assert "elastic" in session.token
        assert route.called

    @respx.mock
    def test_authenticate_elastic_failure(self, connector: SiemConnector, elastic_credentials: dict):
        respx.get("https://elastic.example.com/_cluster/health").mock(
            return_value=httpx.Response(403, text='Forbidden')
        )
        with pytest.raises(ConnectorAuthError):
            connector.authenticate(elastic_credentials)

    @respx.mock
    def test_authenticate_qradar_success(self, connector: SiemConnector, qradar_credentials: dict):
        route = respx.get("https://qradar.example.com/api/system/about").mock(
            return_value=httpx.Response(200, json={"product_name": "IBM QRadar"})
        )
        session = connector.authenticate(qradar_credentials)
        assert isinstance(session, ConnectorSession)
        assert "qradar" in session.token
        assert route.called

    @respx.mock
    def test_authenticate_qradar_failure(self, connector: SiemConnector, qradar_credentials: dict):
        respx.get("https://qradar.example.com/api/system/about").mock(
            return_value=httpx.Response(401, text='Unauthorized')
        )
        with pytest.raises(ConnectorAuthError):
            connector.authenticate(qradar_credentials)

    def test_authenticate_unknown_siem_type(self, connector: SiemConnector):
        with pytest.raises(ConnectorAuthError):
            connector.authenticate({"siem_type": "unknown"})

    def test_authenticate_missing_siem_type(self, connector: SiemConnector):
        with pytest.raises(ConnectorAuthError):
            connector.authenticate({})


# ─────────────────────────────────────────────────────────────────────────────
# Tests: fetch_findings Splunk
# ─────────────────────────────────────────────────────────────────────────────

class TestSiemFetchSplunk:
    @respx.mock
    def test_fetch_splunk_success(self, connector: SiemConnector, splunk_credentials: dict):
        respx.get("https://splunk.example.com/services/server/info").mock(
            return_value=httpx.Response(200, text='<title>Server Info</title>')
        )
        connector.authenticate(splunk_credentials)
        respx.post("https://splunk.example.com/services/search/jobs/export").mock(
            return_value=httpx.Response(200, text='{"_time":"2024-06-15T10:00:00.000+00:00","event_id":"splunk-ev-001","severity":"high","message":"Suspicious activity","host":"fw-01"}\n')
        )
        since = datetime(2024, 6, 1, tzinfo=timezone.utc)
        findings = connector.fetch_findings(since, tenant_id="tenant-siem")
        assert len(findings) >= 1
        assert findings[0].source == "siem"
        raw = findings[0].raw_data
        assert raw.get("siem_type") == "splunk"

    @respx.mock
    def test_fetch_splunk_empty(self, connector: SiemConnector, splunk_credentials: dict):
        respx.get("https://splunk.example.com/services/server/info").mock(
            return_value=httpx.Response(200, text='<title>Server Info</title>')
        )
        connector.authenticate(splunk_credentials)
        respx.post("https://splunk.example.com/services/search/jobs/export").mock(
            return_value=httpx.Response(200, text='')
        )
        since = datetime(2024, 6, 1, tzinfo=timezone.utc)
        findings = connector.fetch_findings(since, tenant_id="tenant-siem")
        assert findings == []


# ─────────────────────────────────────────────────────────────────────────────
# Tests: fetch_findings Elastic
# ─────────────────────────────────────────────────────────────────────────────

class TestSiemFetchElastic:
    @respx.mock
    def test_fetch_elastic_success(self, connector: SiemConnector, elastic_credentials: dict):
        respx.get("https://elastic.example.com/_cluster/health").mock(
            return_value=httpx.Response(200, json={"status": "green"})
        )
        connector.authenticate(elastic_credentials)
        respx.post("https://elastic.example.com/*/_search").mock(
            return_value=httpx.Response(200, json={
                "hits": {
                    "hits": [
                        {"_id": "hit-1", "_source": {"@timestamp": "2024-06-15T10:00:00Z", "severity_label": "critical", "message": "Malware", "host.name": "ws-01"}}
                    ]
                }
            })
        )
        since = datetime(2024, 6, 1, tzinfo=timezone.utc)
        findings = connector.fetch_findings(since, tenant_id="tenant-siem")
        assert len(findings) >= 1
        raw = findings[0].raw_data
        assert raw.get("siem_type") == "elastic"

    @respx.mock
    def test_fetch_elastic_empty(self, connector: SiemConnector, elastic_credentials: dict):
        respx.get("https://elastic.example.com/_cluster/health").mock(
            return_value=httpx.Response(200, json={"status": "green"})
        )
        connector.authenticate(elastic_credentials)
        respx.post("https://elastic.example.com/*/_search").mock(
            return_value=httpx.Response(200, json={"hits": {"hits": []}})
        )
        since = datetime(2024, 6, 1, tzinfo=timezone.utc)
        findings = connector.fetch_findings(since, tenant_id="tenant-siem")
        assert findings == []


# ─────────────────────────────────────────────────────────────────────────────
# Tests: fetch_findings QRadar
# ─────────────────────────────────────────────────────────────────────────────

class TestSiemFetchQRadar:
    @respx.mock
    def test_fetch_qradar_success(self, connector: SiemConnector, qradar_credentials: dict):
        respx.get("https://qradar.example.com/api/system/about").mock(
            return_value=httpx.Response(200, json={"product_name": "IBM QRadar"})
        )
        connector.authenticate(qradar_credentials)
        # Create search
        respx.post("https://qradar.example.com/api/ariel/searches").mock(
            return_value=httpx.Response(201, json={"search_id": "search-123"})
        )
        # Poll status
        respx.get("https://qradar.example.com/api/ariel/searches/search-123").mock(
            return_value=httpx.Response(200, json={"status": "COMPLETED"})
        )
        # Get results
        respx.get("https://qradar.example.com/api/ariel/searches/search-123/results").mock(
            return_value=httpx.Response(200, json={
                "events": [
                    {"id": "ev-1", "severity": 7, "eventname": "Failed Login", "sourceip": "10.0.0.5", "starttime": 1718445600000}
                ]
            })
        )
        since = datetime(2024, 6, 1, tzinfo=timezone.utc)
        findings = connector.fetch_findings(since, tenant_id="tenant-siem")
        assert len(findings) >= 1
        raw = findings[0].raw_data
        assert raw.get("siem_type") == "qradar"

    @respx.mock
    def test_fetch_qradar_empty(self, connector: SiemConnector, qradar_credentials: dict):
        respx.get("https://qradar.example.com/api/system/about").mock(
            return_value=httpx.Response(200, json={"product_name": "IBM QRadar"})
        )
        connector.authenticate(qradar_credentials)
        respx.post("https://qradar.example.com/api/ariel/searches").mock(
            return_value=httpx.Response(201, json={"search_id": "search-456"})
        )
        respx.get("https://qradar.example.com/api/ariel/searches/search-456").mock(
            return_value=httpx.Response(200, json={"status": "COMPLETED"})
        )
        respx.get("https://qradar.example.com/api/ariel/searches/search-456/results").mock(
            return_value=httpx.Response(200, json={"events": []})
        )
        since = datetime(2024, 6, 1, tzinfo=timezone.utc)
        findings = connector.fetch_findings(since, tenant_id="tenant-siem")
        assert findings == []


# ─────────────────────────────────────────────────────────────────────────────
# Tests: Normalization
# ─────────────────────────────────────────────────────────────────────────────

class TestSiemNormalize:
    def test_normalize_splunk_critical(self, connector: SiemConnector):
        raw = RawFinding(
            id="splunk-001",
            source="siem",
            raw_data={"siem_type": "splunk", **_mock_splunk_event(severity="critical", domain_hint="network")},
            fetched_at=datetime.now(timezone.utc),
            tenant_id="tenant-siem",
        )
        record = connector.normalize(raw)
        assert record.source == "siem:splunk"
        assert record.severity == "critical"
        assert record.cvss_score == 9.0
        assert record.domain == "network"

    def test_normalize_splunk_high(self, connector: SiemConnector):
        raw = RawFinding(
            id="splunk-002",
            source="siem",
            raw_data={"siem_type": "splunk", **_mock_splunk_event(severity="high", domain_hint="endpoint")},
            fetched_at=datetime.now(timezone.utc),
            tenant_id="tenant-siem",
        )
        record = connector.normalize(raw)
        assert record.severity == "high"
        assert record.cvss_score == 7.5

    def test_normalize_elastic_medium(self, connector: SiemConnector):
        raw = RawFinding(
            id="elastic-001",
            source="siem",
            raw_data={"siem_type": "elastic", **_mock_elastic_hit(severity="medium", domain_hint="application")},
            fetched_at=datetime.now(timezone.utc),
            tenant_id="tenant-siem",
        )
        record = connector.normalize(raw)
        assert record.source == "siem:elastic"
        assert record.severity == "medium"
        assert record.cvss_score == 5.0
        assert record.domain == "application"

    def test_normalize_elastic_low(self, connector: SiemConnector):
        raw = RawFinding(
            id="elastic-002",
            source="siem",
            raw_data={"siem_type": "elastic", **_mock_elastic_hit(severity="low", domain_hint="identity")},
            fetched_at=datetime.now(timezone.utc),
            tenant_id="tenant-siem",
        )
        record = connector.normalize(raw)
        assert record.severity == "low"
        assert record.cvss_score == 3.0
        assert record.domain == "identity"

    def test_normalize_qradar_critical(self, connector: SiemConnector):
        raw = RawFinding(
            id="qradar-001",
            source="siem",
            raw_data={"siem_type": "qradar", **_mock_qradar_event(severity=10, domain_hint="network")},
            fetched_at=datetime.now(timezone.utc),
            tenant_id="tenant-siem",
        )
        record = connector.normalize(raw)
        assert record.source == "siem:qradar"
        assert record.severity == "critical"
        assert record.cvss_score == 9.0

    def test_normalize_qradar_high(self, connector: SiemConnector):
        raw = RawFinding(
            id="qradar-002",
            source="siem",
            raw_data={"siem_type": "qradar", **_mock_qradar_event(severity=7, domain_hint="endpoint")},
            fetched_at=datetime.now(timezone.utc),
            tenant_id="tenant-siem",
        )
        record = connector.normalize(raw)
        assert record.severity == "high"
        assert record.cvss_score == 7.5

    def test_normalize_unknown_severity_defaults_medium(self, connector: SiemConnector):
        raw = RawFinding(
            id="splunk-003",
            source="siem",
            raw_data={"siem_type": "splunk", **_mock_splunk_event(severity="info")},
            fetched_at=datetime.now(timezone.utc),
            tenant_id="tenant-siem",
        )
        record = connector.normalize(raw)
        assert record.severity == "medium"
        assert record.cvss_score == 5.0

    def test_normalize_missing_domain_hint_defaults_network(self, connector: SiemConnector):
        data = _mock_splunk_event()
        data.pop("domain_hint", None)
        raw = RawFinding(
            id="splunk-004",
            source="siem",
            raw_data={"siem_type": "splunk", **data},
            fetched_at=datetime.now(timezone.utc),
            tenant_id="tenant-siem",
        )
        record = connector.normalize(raw)
        assert record.domain == "network"


# ─────────────────────────────────────────────────────────────────────────────
# Tests: Error handling
# ─────────────────────────────────────────────────────────────────────────────

class TestSiemErrors:
    def test_fetch_without_authenticate(self, connector: SiemConnector):
        since = datetime(2024, 6, 1, tzinfo=timezone.utc)
        with pytest.raises(ConnectorFetchError):
            connector.fetch_findings(since, tenant_id="tenant-siem")

    @respx.mock
    def test_fetch_splunk_http_error(self, connector: SiemConnector, splunk_credentials: dict):
        respx.get("https://splunk.example.com/services/server/info").mock(
            return_value=httpx.Response(200, text='<title>Server Info</title>')
        )
        connector.authenticate(splunk_credentials)
        respx.post("https://splunk.example.com/services/search/jobs/export").mock(
            return_value=httpx.Response(500, text="Internal Server Error")
        )
        since = datetime(2024, 6, 1, tzinfo=timezone.utc)
        with pytest.raises(ConnectorFetchError):
            connector.fetch_findings(since, tenant_id="tenant-siem")


# ─────────────────────────────────────────────────────────────────────────────
# Tests: Health check
# ─────────────────────────────────────────────────────────────────────────────

class TestSiemHealthCheck:
    def test_health_check_ok(self, connector: SiemConnector):
        health = connector.health_check()
        assert isinstance(health, ConnectorHealth)
        assert health.connector_name == "siem"
        assert health.status == "ok"

    @respx.mock
    def test_health_check_degraded_after_errors(self, connector: SiemConnector, splunk_credentials: dict):
        respx.get("https://splunk.example.com/services/server/info").mock(
            return_value=httpx.Response(200, text='<title>Server Info</title>')
        )
        connector.authenticate(splunk_credentials)
        respx.post("https://splunk.example.com/services/search/jobs/export").mock(
            return_value=httpx.Response(500, text="Error")
        )
        since = datetime(2024, 6, 1, tzinfo=timezone.utc)
        for _ in range(3):
            try:
                connector.fetch_findings(since, tenant_id="tenant-siem")
            except Exception:
                pass
        health = connector.health_check()
        assert health.status == "degraded"
        assert health.error_count == 3
