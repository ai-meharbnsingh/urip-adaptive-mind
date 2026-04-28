"""
TDD tests for the Fortinet Fortiguard firewall connector (syslog CEF + optional REST).

Coverage: syslog-only mode, API mode validation, CEF parsing, fetch+normalize, errors, metadata, health check.
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
from connectors.fortiguard_fw.connector import FortiguardFirewallConnector


@pytest.fixture
def connector() -> FortiguardFirewallConnector:
    return FortiguardFirewallConnector()


def _transport(routes: dict[tuple[str, str], httpx.Response]):
    def handler(request: httpx.Request) -> httpx.Response:
        key = (request.method, str(request.url))
        if key in routes:
            return routes[key]
        return httpx.Response(404, json={"error": "not mocked", "url": str(request.url)})

    return httpx.MockTransport(handler)


class TestFortiguardMetadata:
    def test_metadata_fields_set(self):
        assert FortiguardFirewallConnector.DISPLAY_NAME == "Fortinet Fortiguard"
        assert FortiguardFirewallConnector.CATEGORY == "FIREWALL"
        assert FortiguardFirewallConnector.MODULE_CODE == "NETWORK"
        assert FortiguardFirewallConnector.SHORT_DESCRIPTION
        assert FortiguardFirewallConnector.STATUS
        assert isinstance(FortiguardFirewallConnector.CREDENTIAL_FIELDS, list)


class TestFortiguardAuthentication:
    def test_authenticate_invalid_mode_raises(self, connector: FortiguardFirewallConnector):
        with pytest.raises(ConnectorAuthError):
            connector.authenticate({"ingest_mode": "nope", "tenant_id": "t"})

    def test_authenticate_syslog_mode_allows_no_api_creds(self, connector: FortiguardFirewallConnector):
        session = connector.authenticate({"ingest_mode": "syslog", "tenant_id": "t"})
        assert isinstance(session, ConnectorSession)

    def test_authenticate_api_mode_requires_base_url_and_token(self, connector: FortiguardFirewallConnector):
        with pytest.raises(ConnectorAuthError):
            connector.authenticate({"ingest_mode": "api"})

    def test_authenticate_api_mode_success(self, connector: FortiguardFirewallConnector):
        routes = {
            ("GET", "https://fg.test/api/v2/monitor/system/status"): httpx.Response(
                200, json={"status": "success", "version": "7.4"}
            )
        }
        session = connector.authenticate(
            {
                "ingest_mode": "api",
                "base_url": "https://fg.test",
                "api_token": "FG_TOKEN",
                "tenant_id": "t",
                "_transport": _transport(routes),
            }
        )
        assert isinstance(session, ConnectorSession)


class TestFortiguardFetch:
    def test_fetch_not_authenticated(self, connector: FortiguardFirewallConnector):
        with pytest.raises(ConnectorFetchError):
            connector.fetch_findings(datetime.now(timezone.utc), tenant_id="t")

    def test_fetch_syslog_lines_parsed(self, connector: FortiguardFirewallConnector):
        connector.authenticate({"ingest_mode": "syslog", "tenant_id": "t"})
        lines = [
            "CEF:0|Fortinet|FortiGate|7.4|100|Blocked Threat|8 src=10.0.0.1 dst=1.1.1.1 act=blocked cat=ips",
            "CEF:0|Fortinet|FortiGate|7.4|200|IPS Event|6 src=10.0.0.2 dst=2.2.2.2 act=detected cat=ips",
        ]
        findings = connector.fetch_findings(datetime(2024, 1, 1, tzinfo=timezone.utc), tenant_id="t", syslog_lines=lines)
        assert len(findings) == 2
        assert all(isinstance(f, RawFinding) for f in findings)
        assert findings[0].raw_data["record_type"] == "cef"

    def test_fetch_syslog_ignores_unparseable_lines(self, connector: FortiguardFirewallConnector):
        connector.authenticate({"ingest_mode": "syslog", "tenant_id": "t"})
        lines = ["not a cef line", "CEF:0|Fortinet|FortiGate|7.4|100|Blocked Threat|8 src=10.0.0.1"]
        findings = connector.fetch_findings(datetime(2024, 1, 1, tzinfo=timezone.utc), tenant_id="t", syslog_lines=lines)
        assert len(findings) == 1

    def test_fetch_api_blocked_threats(self, connector: FortiguardFirewallConnector):
        routes = {
            ("GET", "https://fg.test/api/v2/monitor/system/status"): httpx.Response(200, json={"status": "success"}),
            ("GET", "https://fg.test/api/v2/monitor/firewall/blocked-threats"): httpx.Response(
                200,
                json={
                    "results": [
                        {"id": "bt-1", "srcip": "10.0.0.9", "dstip": "8.8.8.8", "action": "blocked", "severity": "high"}
                    ]
                },
            ),
        }
        connector.authenticate(
            {
                "ingest_mode": "api",
                "base_url": "https://fg.test",
                "api_token": "FG_TOKEN",
                "tenant_id": "t",
                "_transport": _transport(routes),
            }
        )
        findings = connector.fetch_findings(datetime(2024, 1, 1, tzinfo=timezone.utc), tenant_id="t")
        assert len(findings) == 1
        assert findings[0].raw_data["record_type"] == "blocked_threat"


class TestFortiguardNormalization:
    def test_normalize_cef_blocked_threat(self, connector: FortiguardFirewallConnector):
        raw = RawFinding(
            id="cef:100",
            source="fortiguard_fw",
            raw_data={
                "record_type": "cef",
                "event": {
                    "signature_id": "100",
                    "name": "Blocked Threat",
                    "severity": 8,
                    "extensions": {"src": "10.0.0.1", "dst": "1.1.1.1", "act": "blocked", "cat": "ips"},
                },
            },
            fetched_at=datetime.now(timezone.utc),
            tenant_id="t",
        )
        record = connector.normalize(raw)
        assert isinstance(record, URIPRiskRecord)
        assert record.domain == "network"
        assert record.severity in {"high", "critical"}

    def test_normalize_api_blocked_threat_high(self, connector: FortiguardFirewallConnector):
        raw = RawFinding(
            id="bt-1",
            source="fortiguard_fw",
            raw_data={
                "record_type": "blocked_threat",
                "threat": {"id": "bt-1", "srcip": "10.0.0.9", "dstip": "8.8.8.8", "action": "blocked", "severity": "high"},
            },
            fetched_at=datetime.now(timezone.utc),
            tenant_id="t",
        )
        record = connector.normalize(raw)
        assert record.severity == "high"
        assert record.asset == "10.0.0.9"

    def test_normalize_unknown_type_raises(self, connector: FortiguardFirewallConnector):
        raw = RawFinding(
            id="x",
            source="fortiguard_fw",
            raw_data={"record_type": "nope"},
            fetched_at=datetime.now(timezone.utc),
            tenant_id="t",
        )
        with pytest.raises(ConnectorNormalizeError):
            connector.normalize(raw)
