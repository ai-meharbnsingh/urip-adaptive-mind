"""
TDD tests for the Armis OT live connector.

Uses httpx.MockTransport — no real API calls.
Coverage: authentication, fetch, normalization, error handling, metadata, health check.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import httpx
import pytest

from connectors.base.connector import (
    ConnectorAuthError,
    ConnectorFetchError,
    ConnectorNormalizeError,
    ConnectorSession,
    RawFinding,
    URIPRiskRecord,
)
from connectors.armis_ot.connector import ArmisOTConnector


@pytest.fixture
def connector() -> ArmisOTConnector:
    return ArmisOTConnector()


def _armis_transport(routes: dict[tuple[str, str], httpx.Response]):
    def handler(request: httpx.Request) -> httpx.Response:
        key = (request.method, str(request.url))
        if key in routes:
            return routes[key]
        return httpx.Response(404, json={"error": "not mocked", "url": str(request.url)})

    return httpx.MockTransport(handler)


@pytest.fixture
def valid_credentials() -> dict[str, Any]:
    return {
        "base_url": "https://api.armis.test",
        "api_token": "ARMIS_TOKEN_123",
        "tenant_id": "tenant-ot-1",
    }


class TestArmisOTMetadata:
    def test_metadata_fields_set(self):
        assert ArmisOTConnector.DISPLAY_NAME
        assert ArmisOTConnector.CATEGORY == "OT"
        assert ArmisOTConnector.SHORT_DESCRIPTION
        assert ArmisOTConnector.STATUS
        assert ArmisOTConnector.MODULE_CODE == "OT"
        assert isinstance(ArmisOTConnector.CREDENTIAL_FIELDS, list)


class TestArmisOTAuthentication:
    def test_authenticate_success(self, connector: ArmisOTConnector, valid_credentials: dict[str, Any]):
        transport = _armis_transport(
            {
                ("GET", "https://api.armis.test/api/v1/me"): httpx.Response(
                    200, json={"id": "u-1", "email": "ot@example.com"}
                )
            }
        )
        valid_credentials["_transport"] = transport
        session = connector.authenticate(valid_credentials)
        assert isinstance(session, ConnectorSession)
        assert session.connector_name == "armis_ot"
        assert session.tenant_id == "tenant-ot-1"

    def test_authenticate_missing_token(self, connector: ArmisOTConnector):
        with pytest.raises(ConnectorAuthError):
            connector.authenticate({"base_url": "https://api.armis.test"})

    def test_authenticate_invalid_token(self, connector: ArmisOTConnector, valid_credentials: dict[str, Any]):
        transport = _armis_transport(
            {
                ("GET", "https://api.armis.test/api/v1/me"): httpx.Response(
                    401, json={"error": "Unauthorized"}
                )
            }
        )
        valid_credentials["_transport"] = transport
        with pytest.raises(ConnectorAuthError):
            connector.authenticate(valid_credentials)


class TestArmisOTFetchFindings:
    def test_fetch_findings_not_authenticated(self, connector: ArmisOTConnector):
        with pytest.raises(ConnectorFetchError):
            connector.fetch_findings(datetime.now(timezone.utc), tenant_id="t")

    def test_fetch_findings_empty(self, connector: ArmisOTConnector, valid_credentials: dict[str, Any]):
        transport = _armis_transport(
            {
                ("GET", "https://api.armis.test/api/v1/me"): httpx.Response(200, json={"id": "u-1"}),
                ("GET", "https://api.armis.test/api/v1/assets"): httpx.Response(200, json={"data": []}),
                ("GET", "https://api.armis.test/api/v1/vulnerabilities"): httpx.Response(200, json={"data": []}),
                ("GET", "https://api.armis.test/api/v1/risk-events"): httpx.Response(200, json={"data": []}),
            }
        )
        valid_credentials["_transport"] = transport
        connector.authenticate(valid_credentials)
        findings = connector.fetch_findings(
            datetime(2024, 1, 1, tzinfo=timezone.utc), tenant_id="tenant-ot-1"
        )
        assert findings == []

    def test_fetch_findings_returns_inventory_vulns_and_risk_events(
        self, connector: ArmisOTConnector, valid_credentials: dict[str, Any]
    ):
        transport = _armis_transport(
            {
                ("GET", "https://api.armis.test/api/v1/me"): httpx.Response(200, json={"id": "u-1"}),
                ("GET", "https://api.armis.test/api/v1/assets"): httpx.Response(
                    200,
                    json={
                        "data": [
                            {"id": "a-1", "name": "PLC-01", "site": "Plant-7", "criticality": 5}
                        ]
                    },
                ),
                ("GET", "https://api.armis.test/api/v1/vulnerabilities"): httpx.Response(
                    200,
                    json={
                        "data": [
                            {
                                "id": "v-1",
                                "asset_id": "a-1",
                                "title": "OpenSSH CVE",
                                "cvss": 9.8,
                                "cve": "CVE-2024-9999",
                                "severity": "critical",
                            }
                        ]
                    },
                ),
                ("GET", "https://api.armis.test/api/v1/risk-events"): httpx.Response(
                    200,
                    json={
                        "data": [
                            {
                                "id": "r-1",
                                "asset_id": "a-1",
                                "event_type": "unsafe_protocol",
                                "risk_level": "high",
                                "message": "Device speaking Telnet",
                            }
                        ]
                    },
                ),
            }
        )
        valid_credentials["_transport"] = transport
        connector.authenticate(valid_credentials)
        findings = connector.fetch_findings(
            datetime(2024, 1, 1, tzinfo=timezone.utc), tenant_id="tenant-ot-1"
        )
        assert len(findings) == 3
        assert all(isinstance(f, RawFinding) for f in findings)
        assert {f.raw_data["record_type"] for f in findings} == {"asset", "vulnerability", "risk_event"}

    def test_fetch_findings_5xx_raises(self, connector: ArmisOTConnector, valid_credentials: dict[str, Any]):
        transport = _armis_transport(
            {
                ("GET", "https://api.armis.test/api/v1/me"): httpx.Response(200, json={"id": "u-1"}),
                ("GET", "https://api.armis.test/api/v1/assets"): httpx.Response(503, json={"error": "down"}),
            }
        )
        valid_credentials["_transport"] = transport
        connector.authenticate(valid_credentials)
        with pytest.raises(ConnectorFetchError):
            connector.fetch_findings(datetime.now(timezone.utc), tenant_id="tenant-ot-1")
        health = connector.health_check()
        assert health.status in {"degraded", "error"}
        assert health.error_count >= 1


class TestArmisOTNormalization:
    def test_normalize_vulnerability(self, connector: ArmisOTConnector):
        raw = RawFinding(
            id="v-1",
            source="armis_ot",
            raw_data={
                "record_type": "vulnerability",
                "vulnerability": {
                    "id": "v-1",
                    "asset_id": "a-1",
                    "title": "OpenSSH CVE",
                    "cvss": 9.8,
                    "cve": "CVE-2024-9999",
                    "severity": "critical",
                },
                "asset": {"id": "a-1", "name": "PLC-01", "site": "Plant-7"},
            },
            fetched_at=datetime.now(timezone.utc),
            tenant_id="t",
        )
        record = connector.normalize(raw)
        assert isinstance(record, URIPRiskRecord)
        assert record.domain == "ot"
        assert record.severity == "critical"
        assert record.cve_id == "CVE-2024-9999"
        assert record.asset == "PLC-01"

    def test_normalize_risk_event(self, connector: ArmisOTConnector):
        raw = RawFinding(
            id="r-1",
            source="armis_ot",
            raw_data={
                "record_type": "risk_event",
                "risk_event": {
                    "id": "r-1",
                    "asset_id": "a-1",
                    "event_type": "unsafe_protocol",
                    "risk_level": "high",
                    "message": "Device speaking Telnet",
                },
                "asset": {"id": "a-1", "name": "PLC-01"},
            },
            fetched_at=datetime.now(timezone.utc),
            tenant_id="t",
        )
        record = connector.normalize(raw)
        assert record.domain == "ot"
        assert record.severity == "high"
        assert record.cvss_score >= 0.0

    def test_normalize_asset_inventory_low_severity(self, connector: ArmisOTConnector):
        raw = RawFinding(
            id="a-1",
            source="armis_ot",
            raw_data={
                "record_type": "asset",
                "asset": {"id": "a-1", "name": "PLC-01", "site": "Plant-7", "criticality": 5},
            },
            fetched_at=datetime.now(timezone.utc),
            tenant_id="t",
        )
        record = connector.normalize(raw)
        assert record.domain == "ot"
        assert record.severity in {"low", "medium"}

    def test_normalize_unknown_type_raises(self, connector: ArmisOTConnector):
        raw = RawFinding(
            id="x",
            source="armis_ot",
            raw_data={"record_type": "unknown"},
            fetched_at=datetime.now(timezone.utc),
            tenant_id="t",
        )
        with pytest.raises(ConnectorNormalizeError):
            connector.normalize(raw)

