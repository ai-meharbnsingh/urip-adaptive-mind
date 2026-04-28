"""
TDD tests for the Network Access Control connector (Forescout eyeSight + Cisco ISE).

Uses httpx.MockTransport — no real API calls.
Coverage: sub-adapter selection, OAuth2 (Forescout), ERS (Cisco ISE),
fetch, normalization, error handling, metadata, health check.
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
from connectors.forescout_nac.connector import ForescoutNACConnector


@pytest.fixture
def connector() -> ForescoutNACConnector:
    return ForescoutNACConnector()


def _transport(routes: dict[tuple[str, str], httpx.Response]):
    def handler(request: httpx.Request) -> httpx.Response:
        key = (request.method, str(request.url))
        if key in routes:
            return routes[key]
        return httpx.Response(404, json={"error": "not mocked", "url": str(request.url)})

    return httpx.MockTransport(handler)


class TestNACMetadata:
    def test_metadata_fields_set(self):
        assert ForescoutNACConnector.DISPLAY_NAME == "Network Access Control"
        assert ForescoutNACConnector.CATEGORY == "NAC"
        assert ForescoutNACConnector.MODULE_CODE == "NETWORK"
        assert ForescoutNACConnector.SHORT_DESCRIPTION
        assert ForescoutNACConnector.STATUS
        assert isinstance(ForescoutNACConnector.CREDENTIAL_FIELDS, list)


class TestNACAuthentication:
    def test_authenticate_missing_nac_type(self, connector: ForescoutNACConnector):
        with pytest.raises(ConnectorAuthError):
            connector.authenticate({"tenant_id": "t"})

    def test_authenticate_invalid_nac_type(self, connector: ForescoutNACConnector):
        with pytest.raises(ConnectorAuthError):
            connector.authenticate({"nac_type": "unknown", "tenant_id": "t"})

    def test_authenticate_forescout_success(self, connector: ForescoutNACConnector):
        routes = {
            ("POST", "https://forescout.test/oauth2/token"): httpx.Response(
                200, json={"access_token": "FS_TOKEN", "expires_in": 3600}
            ),
            ("GET", "https://forescout.test/api/v1/me"): httpx.Response(200, json={"id": "me"}),
        }
        creds = {
            "nac_type": "forescout",
            "base_url": "https://forescout.test",
            "client_id": "cid",
            "client_secret": "csec",
            "tenant_id": "tenant-nac",
            "_transport": _transport(routes),
        }
        session = connector.authenticate(creds)
        assert isinstance(session, ConnectorSession)
        assert session.connector_name == "forescout_nac"

    def test_authenticate_forescout_missing_client_secret(self, connector: ForescoutNACConnector):
        with pytest.raises(ConnectorAuthError):
            connector.authenticate(
                {"nac_type": "forescout", "base_url": "https://x", "client_id": "cid"}
            )

    def test_authenticate_cisco_ise_success(self, connector: ForescoutNACConnector):
        routes = {
            ("GET", "https://ise.test/ers/config/endpoint?size=1&page=1"): httpx.Response(
                200, json={"SearchResult": {"resources": [], "total": 0}}
            )
        }
        creds = {
            "nac_type": "cisco_ise",
            "base_url": "https://ise.test",
            "username": "u",
            "password": "p",
            "tenant_id": "tenant-nac",
            "_transport": _transport(routes),
        }
        session = connector.authenticate(creds)
        assert isinstance(session, ConnectorSession)
        assert session.tenant_id == "tenant-nac"


class TestNACFetchFindings:
    def test_fetch_findings_not_authenticated(self, connector: ForescoutNACConnector):
        with pytest.raises(ConnectorFetchError):
            connector.fetch_findings(datetime.now(timezone.utc), tenant_id="t")

    def test_fetch_findings_forescout_empty(self, connector: ForescoutNACConnector):
        routes = {
            ("POST", "https://forescout.test/oauth2/token"): httpx.Response(
                200, json={"access_token": "FS_TOKEN", "expires_in": 3600}
            ),
            ("GET", "https://forescout.test/api/v1/me"): httpx.Response(200, json={"id": "me"}),
            ("GET", "https://forescout.test/api/v1/alerts"): httpx.Response(200, json={"data": []}),
            ("GET", "https://forescout.test/api/v1/events"): httpx.Response(200, json={"data": []}),
            ("GET", "https://forescout.test/api/v1/devices"): httpx.Response(200, json={"data": []}),
        }
        creds = {
            "nac_type": "forescout",
            "base_url": "https://forescout.test",
            "client_id": "cid",
            "client_secret": "csec",
            "tenant_id": "tenant-nac",
            "_transport": _transport(routes),
        }
        connector.authenticate(creds)
        findings = connector.fetch_findings(datetime(2024, 1, 1, tzinfo=timezone.utc), tenant_id="tenant-nac")
        assert findings == []

    def test_fetch_findings_forescout_returns_three_streams(self, connector: ForescoutNACConnector):
        routes = {
            ("POST", "https://forescout.test/oauth2/token"): httpx.Response(
                200, json={"access_token": "FS_TOKEN", "expires_in": 3600}
            ),
            ("GET", "https://forescout.test/api/v1/me"): httpx.Response(200, json={"id": "me"}),
            ("GET", "https://forescout.test/api/v1/alerts"): httpx.Response(
                200,
                json={"data": [{"id": "a-1", "type": "rogue_device", "severity": "high", "device": "sw-1"}]},
            ),
            ("GET", "https://forescout.test/api/v1/events"): httpx.Response(
                200,
                json={"data": [{"id": "e-1", "event_type": "quarantine", "severity": "medium", "device": "sw-1"}]},
            ),
            ("GET", "https://forescout.test/api/v1/devices"): httpx.Response(
                200,
                json={"data": [{"id": "d-1", "mac": "aa:bb:cc:dd:ee:ff", "classification": "IoT"}]},
            ),
        }
        creds = {
            "nac_type": "forescout",
            "base_url": "https://forescout.test",
            "client_id": "cid",
            "client_secret": "csec",
            "tenant_id": "tenant-nac",
            "_transport": _transport(routes),
        }
        connector.authenticate(creds)
        findings = connector.fetch_findings(datetime(2024, 1, 1, tzinfo=timezone.utc), tenant_id="tenant-nac")
        assert len(findings) == 3
        assert {f.raw_data["record_type"] for f in findings} == {"alert", "event", "device"}

    def test_fetch_findings_cisco_ise_5xx_raises(self, connector: ForescoutNACConnector):
        routes = {
            ("GET", "https://ise.test/ers/config/endpoint?size=1&page=1"): httpx.Response(
                200, json={"SearchResult": {"resources": [], "total": 0}}
            ),
            ("GET", "https://ise.test/ers/config/endpoint?size=50&page=1"): httpx.Response(
                503, json={"error": "down"}
            ),
        }
        creds = {
            "nac_type": "cisco_ise",
            "base_url": "https://ise.test",
            "username": "u",
            "password": "p",
            "tenant_id": "tenant-nac",
            "_transport": _transport(routes),
        }
        connector.authenticate(creds)
        with pytest.raises(ConnectorFetchError):
            connector.fetch_findings(datetime(2024, 1, 1, tzinfo=timezone.utc), tenant_id="tenant-nac")


class TestNACNormalization:
    def test_normalize_rogue_alert_high(self, connector: ForescoutNACConnector):
        raw = RawFinding(
            id="a-1",
            source="forescout_nac",
            raw_data={
                "record_type": "alert",
                "alert": {"id": "a-1", "type": "rogue_device", "severity": "high", "device": "sw-1"},
            },
            fetched_at=datetime.now(timezone.utc),
            tenant_id="t",
        )
        record = connector.normalize(raw)
        assert isinstance(record, URIPRiskRecord)
        assert record.domain == "network"
        assert record.severity == "high"
        assert record.asset == "sw-1"

    def test_normalize_device_classification_low(self, connector: ForescoutNACConnector):
        raw = RawFinding(
            id="d-1",
            source="forescout_nac",
            raw_data={
                "record_type": "device",
                "device": {"id": "d-1", "mac": "aa:bb", "classification": "IoT"},
            },
            fetched_at=datetime.now(timezone.utc),
            tenant_id="t",
        )
        record = connector.normalize(raw)
        assert record.severity in {"low", "medium"}

    def test_normalize_unknown_type_raises(self, connector: ForescoutNACConnector):
        raw = RawFinding(
            id="x",
            source="forescout_nac",
            raw_data={"record_type": "nope"},
            fetched_at=datetime.now(timezone.utc),
            tenant_id="t",
        )
        with pytest.raises(ConnectorNormalizeError):
            connector.normalize(raw)

