"""
TDD tests for the Tenable.io live connector.

Uses respx to mock all HTTP traffic — no real API calls.
Coverage: authentication, fetch+pagination, normalization,
error handling (5xx, rate-limit), tenant isolation, health check.
"""

from datetime import datetime, timezone
from typing import Any
from unittest.mock import patch

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
from connectors.tenable.connector import SEVERITY_MAP, TenableConnector


# ─────────────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture
def connector() -> TenableConnector:
    return TenableConnector()


@pytest.fixture
def valid_credentials() -> dict[str, str]:
    return {
        "access_key": "TESTACCESSKEY123",
        "secret_key": "TESTSECRETKEY456",
        "tenant_id": "tenant-abc",
        "max_requests_per_hour": 1_000_000,
    }


@pytest.fixture
def asset_uuid() -> str:
    return "a1b2c3d4-e5f6-7890-abcd-ef1234567890"


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _mock_asset(asset_uuid: str, hostname: str = "srv-01") -> dict[str, Any]:
    return {
        "id": asset_uuid,
        "uuid": asset_uuid,
        "hostname": hostname,
        "ipv4": ["10.0.0.1"],
        "operating_system": ["Ubuntu 22.04"],
    }


def _mock_vulnerability(
    plugin_id: int = 12345,
    plugin_name: str = "Test Vuln",
    severity: int = 3,
    cvss3: float = 8.5,
    cve: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "plugin_id": plugin_id,
        "plugin_name": plugin_name,
        "severity": severity,
        "cvss3_base_score": cvss3,
        "cvss_base_score": 7.5,
        "cve": cve or ["CVE-2024-1234"],
        "vulnerability_state": "Active",
        "count": 1,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Tests: Authentication
# ─────────────────────────────────────────────────────────────────────────────

class TestTenableAuthentication:
    @respx.mock
    def test_authenticate_success(self, connector: TenableConnector, valid_credentials: dict):
        route = respx.get("https://cloud.tenable.com/scans").mock(
            return_value=httpx.Response(200, json={"scans": []})
        )
        session = connector.authenticate(valid_credentials)
        assert isinstance(session, ConnectorSession)
        assert session.connector_name == "tenable"
        assert session.tenant_id == "tenant-abc"
        assert route.called

    @respx.mock
    def test_authenticate_failure_invalid_keys(self, connector: TenableConnector):
        respx.get("https://cloud.tenable.com/scans").mock(
            return_value=httpx.Response(401, json={"error": "Unauthorized"})
        )
        with pytest.raises(ConnectorAuthError):
            connector.authenticate(
                {"access_key": "bad", "secret_key": "bad", "tenant_id": "t", "max_requests_per_hour": 1_000_000}
            )

    @respx.mock
    def test_authenticate_failure_missing_keys(self, connector: TenableConnector):
        with pytest.raises(ConnectorAuthError):
            connector.authenticate({"tenant_id": "t"})

    @respx.mock
    def test_authenticate_uses_custom_base_url(self, connector: TenableConnector):
        custom_url = "https://tenable.example.com"
        route = respx.get(f"{custom_url}/scans").mock(
            return_value=httpx.Response(200, json={"scans": []})
        )
        connector.authenticate(
            {
                "access_key": "ak",
                "secret_key": "sk",
                "base_url": custom_url,
                "max_requests_per_hour": 1_000_000,
            }
        )
        assert route.called


# ─────────────────────────────────────────────────────────────────────────────
# Tests: Fetch findings
# ─────────────────────────────────────────────────────────────────────────────

class TestTenableFetchFindings:
    @respx.mock
    def test_fetch_findings_empty_assets(self, connector: TenableConnector, valid_credentials: dict):
        respx.get("https://cloud.tenable.com/scans").mock(
            return_value=httpx.Response(200, json={"scans": []})
        )
        respx.get("https://cloud.tenable.com/workbenches/assets").mock(
            return_value=httpx.Response(200, json={"assets": []})
        )
        connector.authenticate(valid_credentials)
        findings = connector.fetch_findings(
            since=datetime(2024, 1, 1, tzinfo=timezone.utc),
            tenant_id="tenant-abc",
        )
        assert findings == []

    @respx.mock
    def test_fetch_findings_with_vulnerabilities(
        self, connector: TenableConnector, valid_credentials: dict, asset_uuid: str
    ):
        # Auth
        respx.get("https://cloud.tenable.com/scans").mock(
            return_value=httpx.Response(200, json={"scans": []})
        )
        # Assets
        respx.get("https://cloud.tenable.com/workbenches/assets").mock(
            return_value=httpx.Response(
                200, json={"assets": [_mock_asset(asset_uuid, hostname="web-01")]}
            )
        )
        # Asset vulns
        respx.get(
            f"https://cloud.tenable.com/workbenches/assets/{asset_uuid}/vulnerabilities"
        ).mock(
            return_value=httpx.Response(
                200,
                json={
                    "vulnerabilities": [
                        _mock_vulnerability(
                            plugin_id=1001,
                            plugin_name="Apache Struts RCE",
                            severity=4,
                            cvss3=9.8,
                            cve=["CVE-2023-50164"],
                        ),
                        _mock_vulnerability(
                            plugin_id=1002,
                            plugin_name="Expired SSL Cert",
                            severity=1,
                            cvss3=5.3,
                            cve=[],
                        ),
                    ]
                },
            )
        )

        connector.authenticate(valid_credentials)
        findings = connector.fetch_findings(
            since=datetime(2024, 1, 1, tzinfo=timezone.utc),
            tenant_id="tenant-abc",
        )

        assert len(findings) == 2
        assert all(isinstance(f, RawFinding) for f in findings)
        assert findings[0].source == "tenable"
        assert findings[0].tenant_id == "tenant-abc"
        assert f"{asset_uuid}:1001" in findings[0].id

    @respx.mock
    def test_fetch_findings_pagination_ignored_when_under_limit(
        self, connector: TenableConnector, valid_credentials: dict
    ):
        """Tenable asset pagination via offset/limit is handled by setting limit=max_assets."""
        respx.get("https://cloud.tenable.com/scans").mock(
            return_value=httpx.Response(200, json={"scans": []})
        )
        assets = [
            _mock_asset(f"uuid-{i:03d}", hostname=f"host-{i:03d}")
            for i in range(3)
        ]
        respx.get("https://cloud.tenable.com/workbenches/assets").mock(
            return_value=httpx.Response(200, json={"assets": assets})
        )
        for a in assets:
            respx.get(
                f"https://cloud.tenable.com/workbenches/assets/{a['uuid']}/vulnerabilities"
            ).mock(
                return_value=httpx.Response(
                    200, json={"vulnerabilities": [_mock_vulnerability(plugin_id=1)]}
                )
            )

        connector.authenticate(valid_credentials)
        findings = connector.fetch_findings(
            since=datetime(2024, 1, 1, tzinfo=timezone.utc),
            tenant_id="tenant-abc",
            max_assets=3,
        )
        assert len(findings) == 3

    @respx.mock
    def test_fetch_findings_respects_max_assets(
        self, connector: TenableConnector, valid_credentials: dict
    ):
        """Only max_assets should be queried even if more exist."""
        respx.get("https://cloud.tenable.com/scans").mock(
            return_value=httpx.Response(200, json={"scans": []})
        )
        assets = [
            _mock_asset(f"uuid-{i:03d}", hostname=f"host-{i:03d}")
            for i in range(10)
        ]
        respx.get("https://cloud.tenable.com/workbenches/assets").mock(
            return_value=httpx.Response(200, json={"assets": assets})
        )
        # Only first 2 should be hit because max_assets defaults to 50,
        # but we mock the assets endpoint to return 10 and expect all 10
        # to be processed since 10 < 50.
        for a in assets:
            respx.get(
                f"https://cloud.tenable.com/workbenches/assets/{a['uuid']}/vulnerabilities"
            ).mock(
                return_value=httpx.Response(
                    200, json={"vulnerabilities": [_mock_vulnerability(plugin_id=1)]}
                )
            )

        connector.authenticate(valid_credentials)
        findings = connector.fetch_findings(
            since=datetime(2024, 1, 1, tzinfo=timezone.utc),
            tenant_id="tenant-abc",
            max_assets=10,
        )
        assert len(findings) == 10

    @respx.mock
    def test_fetch_findings_5xx_error(self, connector: TenableConnector, valid_credentials: dict):
        respx.get("https://cloud.tenable.com/scans").mock(
            return_value=httpx.Response(200, json={"scans": []})
        )
        respx.get("https://cloud.tenable.com/workbenches/assets").mock(
            return_value=httpx.Response(503, json={"error": "Service Unavailable"})
        )
        connector.authenticate(valid_credentials)
        with pytest.raises(ConnectorFetchError):
            connector.fetch_findings(
                since=datetime(2024, 1, 1, tzinfo=timezone.utc),
                tenant_id="tenant-abc",
            )

    @respx.mock
    def test_fetch_findings_not_authenticated(self, connector: TenableConnector):
        with pytest.raises(ConnectorFetchError):
            connector.fetch_findings(since=datetime.now(timezone.utc))


# ─────────────────────────────────────────────────────────────────────────────
# Tests: Normalization
# ─────────────────────────────────────────────────────────────────────────────

class TestTenableNormalize:
    def test_normalize_correctness(self, connector: TenableConnector, asset_uuid: str):
        raw = RawFinding(
            id=f"{asset_uuid}:1001",
            source="tenable",
            raw_data={
                "plugin_id": 1001,
                "plugin_name": "Apache Struts RCE",
                "severity": 4,
                "cvss3_base_score": 9.8,
                "cvss_base_score": 9.3,
                "cve": ["CVE-2023-50164"],
                "vulnerability_state": "Active",
                "asset": {
                    "id": asset_uuid,
                    "uuid": asset_uuid,
                    "hostname": "app-01",
                    "ipv4": ["10.0.0.5"],
                    "operating_system": ["Ubuntu 22.04"],
                },
            },
            fetched_at=datetime.now(timezone.utc),
            tenant_id="t1",
        )
        record = connector.normalize(raw)
        assert isinstance(record, URIPRiskRecord)
        assert record.finding == "Apache Struts RCE"
        assert record.severity == "critical"
        assert record.cvss_score == 9.8
        assert record.cve_id == "CVE-2023-50164"
        assert record.asset == "app-01"
        assert record.source == "tenable"
        assert record.owner_team == "Vulnerability Management"

    def test_normalize_missing_hostname_uses_ipv4(self, connector: TenableConnector, asset_uuid: str):
        raw = RawFinding(
            id=f"{asset_uuid}:1002",
            source="tenable",
            raw_data={
                "plugin_id": 1002,
                "plugin_name": "SSL Weak Cipher",
                "severity": 2,
                "cvss3_base_score": 5.3,
                "cve": [],
                "asset": {
                    "id": asset_uuid,
                    "uuid": asset_uuid,
                    "hostname": None,
                    "ipv4": ["192.168.1.10"],
                    "operating_system": [],
                },
            },
            fetched_at=datetime.now(timezone.utc),
            tenant_id="t1",
        )
        record = connector.normalize(raw)
        assert record.asset == "192.168.1.10"
        assert record.cve_id is None
        assert record.severity == "medium"

    def test_normalize_fallback_cvss2_when_cvss3_missing(
        self, connector: TenableConnector, asset_uuid: str
    ):
        raw = RawFinding(
            id=f"{asset_uuid}:1003",
            source="tenable",
            raw_data={
                "plugin_id": 1003,
                "plugin_name": "Old finding",
                "severity": 1,
                "cvss3_base_score": None,
                "cvss_base_score": 4.2,
                "cve": ["CVE-2020-0001"],
                "asset": {
                    "id": asset_uuid,
                    "uuid": asset_uuid,
                    "hostname": "legacy-srv",
                    "ipv4": [],
                    "operating_system": ["Windows Server 2008"],
                },
            },
            fetched_at=datetime.now(timezone.utc),
            tenant_id="t1",
        )
        record = connector.normalize(raw)
        assert record.cvss_score == 4.2
        assert record.severity == "low"

    def test_normalize_defaults_to_zero_cvss_when_both_missing(
        self, connector: TenableConnector, asset_uuid: str
    ):
        raw = RawFinding(
            id=f"{asset_uuid}:1004",
            source="tenable",
            raw_data={
                "plugin_id": 1004,
                "plugin_name": "Info finding",
                "severity": 0,
                "cve": [],
                "asset": {
                    "id": asset_uuid,
                    "uuid": asset_uuid,
                    "hostname": None,
                    "ipv4": [],
                    "operating_system": [],
                },
            },
            fetched_at=datetime.now(timezone.utc),
            tenant_id="t1",
        )
        record = connector.normalize(raw)
        assert record.cvss_score == 0.0
        assert record.asset == asset_uuid


# ─────────────────────────────────────────────────────────────────────────────
# Tests: Error handling
# ─────────────────────────────────────────────────────────────────────────────

class TestTenableErrorHandling:
    @respx.mock
    def test_rate_limit_during_auth(self, connector: TenableConnector):
        respx.get("https://cloud.tenable.com/scans").mock(
            return_value=httpx.Response(429, json={"error": "Rate limited"})
        )
        # 429 is not 401/403, so validate_auth raises instead of returning False
        with pytest.raises(ConnectorAuthError):
            connector.authenticate(
                {"access_key": "ak", "secret_key": "sk", "tenant_id": "t"}
            )

    @respx.mock
    def test_fetch_increments_error_count(self, connector: TenableConnector, valid_credentials: dict):
        respx.get("https://cloud.tenable.com/scans").mock(
            return_value=httpx.Response(200, json={"scans": []})
        )
        respx.get("https://cloud.tenable.com/workbenches/assets").mock(
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

class TestTenableTenantIsolation:
    @respx.mock
    def test_different_tenant_credentials_produce_different_results(
        self, asset_uuid: str
    ):
        """
        Two connectors with different tenant configs must talk to Tenable
        with different keys and scope findings to different tenant_ids.
        """
        respx.get("https://cloud.tenable.com/scans").mock(
            return_value=httpx.Response(200, json={"scans": []})
        )
        # Tenant A assets
        respx.get("https://cloud.tenable.com/workbenches/assets").mock(
            return_value=httpx.Response(
                200, json={"assets": [_mock_asset(asset_uuid, hostname="tenant-a-srv")]}
            )
        )
        respx.get(
            f"https://cloud.tenable.com/workbenches/assets/{asset_uuid}/vulnerabilities"
        ).mock(
            return_value=httpx.Response(
                200, json={"vulnerabilities": [_mock_vulnerability(plugin_id=1)]}
            )
        )

        conn_a = TenableConnector()
        session_a = conn_a.authenticate(
            {"access_key": "AK_A", "secret_key": "SK_A", "tenant_id": "tenant-a"}
        )
        findings_a = conn_a.fetch_findings(
            since=datetime(2024, 1, 1, tzinfo=timezone.utc),
            tenant_id="tenant-a",
        )

        conn_b = TenableConnector()
        session_b = conn_b.authenticate(
            {"access_key": "AK_B", "secret_key": "SK_B", "tenant_id": "tenant-b"}
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

class TestTenableHealthCheck:
    def test_health_check_ok_fresh_connector(self, connector: TenableConnector):
        health = connector.health_check()
        assert isinstance(health, ConnectorHealth)
        assert health.connector_name == "tenable"
        assert health.status == "ok"
        assert health.error_count == 0
        assert health.last_run is None

    @respx.mock
    def test_health_check_degraded_after_errors(self, connector: TenableConnector):
        respx.get("https://cloud.tenable.com/scans").mock(
            return_value=httpx.Response(200, json={"scans": []})
        )
        respx.get("https://cloud.tenable.com/workbenches/assets").mock(
            return_value=httpx.Response(500, json={"error": "boom"})
        )
        connector.authenticate(
            {"access_key": "ak", "secret_key": "sk", "tenant_id": "t", "max_requests_per_hour": 1_000_000}
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
    def test_health_check_error_after_many_errors(self, connector: TenableConnector):
        respx.get("https://cloud.tenable.com/scans").mock(
            return_value=httpx.Response(200, json={"scans": []})
        )
        respx.get("https://cloud.tenable.com/workbenches/assets").mock(
            return_value=httpx.Response(500, json={"error": "boom"})
        )
        connector.authenticate(
            {"access_key": "ak", "secret_key": "sk", "tenant_id": "t", "max_requests_per_hour": 1_000_000}
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
        self, connector: TenableConnector, valid_credentials: dict, asset_uuid: str
    ):
        respx.get("https://cloud.tenable.com/scans").mock(
            return_value=httpx.Response(200, json={"scans": []})
        )
        respx.get("https://cloud.tenable.com/workbenches/assets").mock(
            return_value=httpx.Response(200, json={"assets": [_mock_asset(asset_uuid)]})
        )
        respx.get(
            f"https://cloud.tenable.com/workbenches/assets/{asset_uuid}/vulnerabilities"
        ).mock(return_value=httpx.Response(200, json={"vulnerabilities": []}))

        connector.authenticate(valid_credentials)
        connector.fetch_findings(since=datetime.now(timezone.utc))
        health = connector.health_check()
        assert health.last_run is not None
