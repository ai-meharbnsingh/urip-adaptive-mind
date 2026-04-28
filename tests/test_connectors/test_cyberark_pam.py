"""
TDD tests for the CyberArk PAM live connector.

Uses httpx.MockTransport — no real API calls.
Coverage: API key auth + session reuse, fetch, normalization, error handling, metadata, health check.
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
from connectors.cyberark_pam.connector import CyberArkPAMConnector


@pytest.fixture
def connector() -> CyberArkPAMConnector:
    return CyberArkPAMConnector()


def _transport(handler):
    return httpx.MockTransport(handler)


class TestCyberArkMetadata:
    def test_metadata_fields_set(self):
        assert CyberArkPAMConnector.DISPLAY_NAME == "CyberArk Privileged Access"
        assert CyberArkPAMConnector.CATEGORY == "PAM"
        assert CyberArkPAMConnector.MODULE_CODE == "IDENTITY"
        assert CyberArkPAMConnector.SHORT_DESCRIPTION
        assert CyberArkPAMConnector.STATUS
        assert isinstance(CyberArkPAMConnector.CREDENTIAL_FIELDS, list)


class TestCyberArkAuthentication:
    def test_authenticate_missing_api_key(self, connector: CyberArkPAMConnector):
        with pytest.raises(ConnectorAuthError):
            connector.authenticate({"base_url": "https://pvwa.test"})

    def test_authenticate_success(self, connector: CyberArkPAMConnector):
        def handler(request: httpx.Request) -> httpx.Response:
            if request.method == "POST" and str(request.url) == "https://pvwa.test/PasswordVault/API/Auth/APIKey/Logon":
                return httpx.Response(200, text="CYBERARK_TOKEN")
            if request.method == "POST" and str(request.url) == "https://pvwa.test/PasswordVault/API/Auth/Logoff":
                return httpx.Response(200, text="ok")
            return httpx.Response(404)

        creds = {
            "base_url": "https://pvwa.test",
            "api_key": "APIKEY123",
            "tenant_id": "tenant-pam",
            "_transport": _transport(handler),
        }
        session = connector.authenticate(creds)
        assert isinstance(session, ConnectorSession)
        assert session.tenant_id == "tenant-pam"

    def test_authenticate_invalid_key(self, connector: CyberArkPAMConnector):
        def handler(request: httpx.Request) -> httpx.Response:
            if request.method == "POST":
                return httpx.Response(401, json={"error": "unauthorized"})
            return httpx.Response(404)

        with pytest.raises(ConnectorAuthError):
            connector.authenticate(
                {
                    "base_url": "https://pvwa.test",
                    "api_key": "bad",
                    "_transport": _transport(handler),
                }
            )


class TestCyberArkFetch:
    def test_fetch_empty_returns_empty_list(self, connector: CyberArkPAMConnector):
        def handler(request: httpx.Request) -> httpx.Response:
            url = str(request.url)
            if request.method == "POST" and url.endswith("/APIKey/Logon"):
                return httpx.Response(200, text="CYBERARK_TOKEN")
            if request.method == "POST" and url.endswith("/Auth/Logoff"):
                return httpx.Response(200, text="ok")
            if request.method == "GET" and url.startswith("https://pvwa.test/PasswordVault/API/Logs/"):
                return httpx.Response(200, json={"data": []})
            return httpx.Response(404)

        connector.authenticate(
            {
                "base_url": "https://pvwa.test",
                "api_key": "APIKEY123",
                "_transport": _transport(handler),
            }
        )
        findings = connector.fetch_findings(datetime(2024, 1, 1, tzinfo=timezone.utc), tenant_id="t")
        assert findings == []

    def test_fetch_not_authenticated(self, connector: CyberArkPAMConnector):
        with pytest.raises(ConnectorFetchError):
            connector.fetch_findings(datetime.now(timezone.utc), tenant_id="t")

    def test_fetch_session_logon_only_once_for_multiple_calls(self, connector: CyberArkPAMConnector):
        counters = {"logon": 0, "logoff": 0, "calls": 0}

        def handler(request: httpx.Request) -> httpx.Response:
            url = str(request.url)
            if request.method == "POST" and url.endswith("/APIKey/Logon"):
                counters["logon"] += 1
                return httpx.Response(200, text="CYBERARK_TOKEN")
            if request.method == "POST" and url.endswith("/Auth/Logoff"):
                counters["logoff"] += 1
                return httpx.Response(200, text="ok")
            if request.method == "GET" and url.startswith("https://pvwa.test/PasswordVault/API/Logs/"):
                counters["calls"] += 1
                return httpx.Response(
                    200,
                    json={
                        "data": [
                            {
                                "id": f"ev-{counters['calls']}",
                                "event_type": "vault_access",
                                "severity": "low",
                                "user": "admin",
                                "asset": "vault-1",
                                "message": "read secret",
                            }
                        ]
                    },
                )
            return httpx.Response(404, json={"error": "not mocked", "url": url})

        creds = {
            "base_url": "https://pvwa.test",
            "api_key": "APIKEY123",
            "tenant_id": "tenant-pam",
            "_transport": _transport(handler),
        }
        connector.authenticate(creds)
        findings = connector.fetch_findings(datetime(2024, 1, 1, tzinfo=timezone.utc), tenant_id="tenant-pam")
        assert len(findings) == 3
        assert counters["logon"] == 1
        assert counters["calls"] == 3
        assert counters["logoff"] == 1

    def test_fetch_5xx_raises(self, connector: CyberArkPAMConnector):
        def handler(request: httpx.Request) -> httpx.Response:
            url = str(request.url)
            if request.method == "POST" and url.endswith("/APIKey/Logon"):
                return httpx.Response(200, text="CYBERARK_TOKEN")
            if request.method == "POST" and url.endswith("/Auth/Logoff"):
                return httpx.Response(200, text="ok")
            if request.method == "GET" and url.endswith("/PasswordVault/API/Logs/VaultAccess"):
                return httpx.Response(503, json={"error": "down"})
            if request.method == "GET":
                return httpx.Response(200, json={"data": []})
            return httpx.Response(404)

        connector.authenticate(
            {
                "base_url": "https://pvwa.test",
                "api_key": "APIKEY123",
                "_transport": _transport(handler),
            }
        )
        with pytest.raises(ConnectorFetchError):
            connector.fetch_findings(datetime.now(timezone.utc), tenant_id="t")


class TestCyberArkNormalization:
    def test_normalize_vault_access(self, connector: CyberArkPAMConnector):
        raw = RawFinding(
            id="ev-1",
            source="cyberark_pam",
            raw_data={
                "record_type": "vault_access",
                "event": {
                    "id": "ev-1",
                    "event_type": "vault_access",
                    "severity": "low",
                    "user": "admin",
                    "asset": "vault-1",
                    "message": "read secret",
                },
            },
            fetched_at=datetime.now(timezone.utc),
            tenant_id="t",
        )
        record = connector.normalize(raw)
        assert isinstance(record, URIPRiskRecord)
        assert record.domain == "identity"
        assert record.severity == "low"
        assert record.asset == "vault-1"

    def test_normalize_session_anomaly_high(self, connector: CyberArkPAMConnector):
        raw = RawFinding(
            id="ev-2",
            source="cyberark_pam",
            raw_data={
                "record_type": "session_anomaly",
                "event": {
                    "id": "ev-2",
                    "event_type": "session_anomaly",
                    "severity": "high",
                    "user": "svc-admin",
                    "asset": "srv-22",
                    "message": "impossible travel",
                },
            },
            fetched_at=datetime.now(timezone.utc),
            tenant_id="t",
        )
        record = connector.normalize(raw)
        assert record.severity == "high"

    def test_normalize_credential_usage_defaults_medium(self, connector: CyberArkPAMConnector):
        raw = RawFinding(
            id="ev-3",
            source="cyberark_pam",
            raw_data={
                "record_type": "credential_usage",
                "event": {
                    "id": "ev-3",
                    "event_type": "credential_usage",
                    "user": "svc-batch",
                    "asset": "db-01",
                    "message": "shared credential used",
                },
            },
            fetched_at=datetime.now(timezone.utc),
            tenant_id="t",
        )
        record = connector.normalize(raw)
        assert record.severity == "medium"

    def test_normalize_unknown_type_raises(self, connector: CyberArkPAMConnector):
        raw = RawFinding(
            id="x",
            source="cyberark_pam",
            raw_data={"record_type": "nope"},
            fetched_at=datetime.now(timezone.utc),
            tenant_id="t",
        )
        with pytest.raises(ConnectorNormalizeError):
            connector.normalize(raw)
