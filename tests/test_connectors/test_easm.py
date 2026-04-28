"""
TDD tests for the generic EASM connector (Censys / Shodan / Detectify).

Uses respx to mock all HTTP traffic — no real API calls.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import httpx
import pytest
import respx

from connectors.base.connector import (
    CONNECTOR_CATEGORIES,
    ConnectorAuthError,
    ConnectorFetchError,
    ConnectorHealth,
    ConnectorSession,
    CredentialFieldSpec,
    RawFinding,
    URIPRiskRecord,
)
from connectors.easm.connector import EasmConnector


# ─────────────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture
def connector() -> EasmConnector:
    return EasmConnector()


@pytest.fixture
def censys_credentials() -> dict[str, Any]:
    return {
        "easm_provider": "censys",
        "api_token": "censys-token-XYZ",
        "base_url": "https://search.censys.io",
        "monitor_domains": ["example.com", "test.com"],
        "tenant_id": "tenant-1",
    }


@pytest.fixture
def shodan_credentials() -> dict[str, Any]:
    return {
        "easm_provider": "shodan",
        "api_key": "SHODAN-KEY-1",
        "monitor_ips": ["1.2.3.4", "5.6.7.8"],
        "tenant_id": "tenant-1",
    }


@pytest.fixture
def detectify_credentials() -> dict[str, Any]:
    return {
        "easm_provider": "detectify",
        "api_token": "DT-TOKEN-1",
        "monitor_domains": ["test.com"],
        "tenant_id": "tenant-1",
    }


# ─────────────────────────────────────────────────────────────────────────────
# 1. METADATA assertions
# ─────────────────────────────────────────────────────────────────────────────

class TestEasmMetadata:
    def test_all_eight_metadata_attrs_set(self):
        assert EasmConnector.DISPLAY_NAME == "External Attack Surface (EASM)"
        assert EasmConnector.CATEGORY == "EASM"
        assert EasmConnector.CATEGORY in CONNECTOR_CATEGORIES
        assert EasmConnector.SHORT_DESCRIPTION
        assert EasmConnector.STATUS == "live"
        assert EasmConnector.VENDOR_DOCS_URL
        assert EasmConnector.VENDOR_DOCS_URL.startswith("https://")
        assert EasmConnector.SUPPORTED_PRODUCTS == ["censys", "shodan", "detectify"]
        assert EasmConnector.MODULE_CODE == "VM"
        assert isinstance(EasmConnector.CREDENTIAL_FIELDS, list)
        assert len(EasmConnector.CREDENTIAL_FIELDS) >= 2
        for f in EasmConnector.CREDENTIAL_FIELDS:
            assert isinstance(f, CredentialFieldSpec)
        names = [f.name for f in EasmConnector.CREDENTIAL_FIELDS]
        assert "easm_provider" in names

    def test_registered_in_global_registry(self):
        from connectors.base.registry import _global_registry
        assert "easm" in _global_registry
        cls = _global_registry.get("easm")
        assert cls is EasmConnector


# ─────────────────────────────────────────────────────────────────────────────
# 2. Censys adapter
# ─────────────────────────────────────────────────────────────────────────────

class TestEasmCensys:
    @respx.mock
    def test_censys_authenticate_uses_bearer_token(
        self, connector: EasmConnector, censys_credentials: dict
    ):
        # Censys API v2 uses /api/v2/account or /api/v2/hosts/search
        route = respx.get("https://search.censys.io/api/v2/account").mock(
            return_value=httpx.Response(200, json={"login": "ok"})
        )
        session = connector.authenticate(censys_credentials)
        assert isinstance(session, ConnectorSession)
        assert session.connector_name == "easm"
        assert route.called
        # Bearer token must be sent
        last_req = route.calls[-1].request
        assert "censys-token-XYZ" in last_req.headers.get("authorization", "")

    @respx.mock
    def test_censys_fetch_findings_filters_by_monitor_domains(
        self, connector: EasmConnector, censys_credentials: dict
    ):
        respx.get("https://search.censys.io/api/v2/account").mock(
            return_value=httpx.Response(200, json={"login": "ok"})
        )
        # Censys host search response
        captured = []

        def _search_handler(request: httpx.Request):
            captured.append(request.url.params.get("q") or request.url.params.get("query"))
            return httpx.Response(
                200,
                json={
                    "result": {
                        "hits": [
                            {
                                "ip": "203.0.113.10",
                                "name": "exposed-admin.example.com",
                                "services": [
                                    {"port": 22, "service_name": "SSH",
                                     "transport_protocol": "TCP"},
                                    {"port": 8080, "service_name": "HTTP",
                                     "extended_service_name": "admin-panel"},
                                ],
                                "risk": {"severity": "high"},
                            }
                        ],
                        "links": {"next": ""},
                    }
                },
            )

        respx.get("https://search.censys.io/api/v2/hosts/search").mock(side_effect=_search_handler)

        connector.authenticate(censys_credentials)
        findings = connector.fetch_findings(
            since=datetime(2024, 1, 1, tzinfo=timezone.utc), tenant_id="tenant-1",
        )
        assert len(findings) >= 1
        assert all(f.source == "easm:censys" for f in findings)
        # The query string includes a monitored domain (example.com or test.com)
        assert any("example.com" in (q or "") or "test.com" in (q or "") for q in captured)

    @respx.mock
    def test_censys_pagination(self, connector: EasmConnector, censys_credentials: dict):
        respx.get("https://search.censys.io/api/v2/account").mock(
            return_value=httpx.Response(200, json={"login": "ok"})
        )

        calls = []

        def _h(request: httpx.Request):
            cursor = request.url.params.get("cursor", "")
            calls.append(cursor)
            if not cursor:
                return httpx.Response(
                    200,
                    json={
                        "result": {
                            "hits": [{"ip": "1.1.1.1", "name": "a.example.com",
                                      "services": [], "risk": {"severity": "low"}}],
                            "links": {"next": "page2"},
                        }
                    },
                )
            return httpx.Response(
                200,
                json={
                    "result": {
                        "hits": [{"ip": "2.2.2.2", "name": "b.example.com",
                                  "services": [], "risk": {"severity": "low"}}],
                        "links": {"next": ""},
                    }
                },
            )

        respx.get("https://search.censys.io/api/v2/hosts/search").mock(side_effect=_h)

        connector.authenticate(censys_credentials)
        findings = connector.fetch_findings(
            since=datetime(2024, 1, 1, tzinfo=timezone.utc), tenant_id="tenant-1",
        )
        # 2 monitor domains × 2 pages each = at least 2 paginated requests
        assert len(calls) >= 2


# ─────────────────────────────────────────────────────────────────────────────
# 3. Shodan adapter
# ─────────────────────────────────────────────────────────────────────────────

class TestEasmShodan:
    @respx.mock
    def test_shodan_authenticate_uses_query_string_key(
        self, connector: EasmConnector, shodan_credentials: dict
    ):
        captured = []

        def _h(request: httpx.Request):
            captured.append(request.url.params.get("key"))
            return httpx.Response(
                200, json={"plan": "dev", "query_credits": 100, "scan_credits": 0}
            )

        respx.get("https://api.shodan.io/api-info").mock(side_effect=_h)
        session = connector.authenticate(shodan_credentials)
        assert isinstance(session, ConnectorSession)
        assert "SHODAN-KEY-1" in captured

    @respx.mock
    def test_shodan_fetch_findings_pulls_exposed_hosts(
        self, connector: EasmConnector, shodan_credentials: dict
    ):
        respx.get("https://api.shodan.io/api-info").mock(
            return_value=httpx.Response(
                200, json={"plan": "dev", "query_credits": 100, "scan_credits": 0}
            )
        )

        def _host_handler(request: httpx.Request):
            ip = str(request.url).split("/host/")[-1].split("?")[0]
            return httpx.Response(
                200,
                json={
                    "ip_str": ip,
                    "ports": [22, 8443],
                    "data": [
                        {"port": 22, "product": "OpenSSH", "version": "7.4"},
                        {"port": 8443, "product": "nginx", "version": "1.18",
                         "http": {"title": "Admin Console"}},
                    ],
                    "vulns": ["CVE-2023-1234"],
                },
            )

        respx.get(url__regex=r"https://api\.shodan\.io/shodan/host/.*").mock(
            side_effect=_host_handler
        )

        connector.authenticate(shodan_credentials)
        findings = connector.fetch_findings(
            since=datetime(2024, 1, 1, tzinfo=timezone.utc), tenant_id="tenant-1",
        )
        assert len(findings) >= 1
        assert all(f.source == "easm:shodan" for f in findings)

    @respx.mock
    def test_shodan_filters_by_monitor_ips(
        self, connector: EasmConnector, shodan_credentials: dict
    ):
        """Adapter must only query the IPs the tenant configured."""
        respx.get("https://api.shodan.io/api-info").mock(
            return_value=httpx.Response(200, json={"plan": "dev"})
        )

        ip_calls: list[str] = []

        def _h(request: httpx.Request):
            ip = str(request.url).split("/host/")[-1].split("?")[0]
            ip_calls.append(ip)
            return httpx.Response(
                200,
                json={"ip_str": ip, "ports": [], "data": [], "vulns": []},
            )

        respx.get(url__regex=r"https://api\.shodan\.io/shodan/host/.*").mock(side_effect=_h)

        connector.authenticate(shodan_credentials)
        connector.fetch_findings(
            since=datetime(2024, 1, 1, tzinfo=timezone.utc), tenant_id="tenant-1",
        )
        # Only configured IPs queried, no others
        assert set(ip_calls) <= {"1.2.3.4", "5.6.7.8"}
        assert len(ip_calls) == 2


# ─────────────────────────────────────────────────────────────────────────────
# 4. Detectify adapter
# ─────────────────────────────────────────────────────────────────────────────

class TestEasmDetectify:
    @respx.mock
    def test_detectify_authenticate(
        self, connector: EasmConnector, detectify_credentials: dict
    ):
        route = respx.get("https://api.detectify.com/rest/v3/domains/").mock(
            return_value=httpx.Response(200, json={"domains": []})
        )
        session = connector.authenticate(detectify_credentials)
        assert isinstance(session, ConnectorSession)
        assert route.called
        last_req = route.calls[-1].request
        assert "DT-TOKEN-1" in last_req.headers.get("authorization", "")

    @respx.mock
    def test_detectify_fetch_findings(
        self, connector: EasmConnector, detectify_credentials: dict
    ):
        respx.get("https://api.detectify.com/rest/v3/domains/").mock(
            return_value=httpx.Response(200, json={"domains": []})
        )
        respx.get(
            url__regex=r"https://api\.detectify\.com/rest/v3/domains/.+/findings.*"
        ).mock(
            return_value=httpx.Response(
                200,
                json={
                    "findings": [
                        {
                            "uuid": "f-1",
                            "title": "SQL Injection",
                            "severity": "critical",
                            "found_at": "2024-08-01T00:00:00Z",
                            "url": "https://test.com/login",
                            "category": "OWASP-A03",
                            "confirmed": True,
                        }
                    ],
                    "next_cursor": "",
                },
            )
        )

        connector.authenticate(detectify_credentials)
        findings = connector.fetch_findings(
            since=datetime(2024, 1, 1, tzinfo=timezone.utc), tenant_id="tenant-1",
        )
        assert len(findings) >= 1
        assert all(f.source == "easm:detectify" for f in findings)


# ─────────────────────────────────────────────────────────────────────────────
# 5. Auth failures
# ─────────────────────────────────────────────────────────────────────────────

class TestEasmAuthFailures:
    @respx.mock
    def test_censys_invalid_token(self, connector: EasmConnector):
        respx.get("https://search.censys.io/api/v2/account").mock(
            return_value=httpx.Response(401, json={"error": "Unauthorized"})
        )
        with pytest.raises(ConnectorAuthError):
            connector.authenticate(
                {
                    "easm_provider": "censys",
                    "api_token": "bad",
                    "base_url": "https://search.censys.io",
                    "monitor_domains": ["a.com"],
                }
            )

    def test_missing_provider_field(self, connector: EasmConnector):
        with pytest.raises(ConnectorAuthError):
            connector.authenticate({"api_token": "x"})

    def test_unknown_provider(self, connector: EasmConnector):
        with pytest.raises(ConnectorAuthError):
            connector.authenticate(
                {"easm_provider": "made_up", "api_token": "x"}
            )


# ─────────────────────────────────────────────────────────────────────────────
# 6. Severity mapping per provider
# ─────────────────────────────────────────────────────────────────────────────

class TestEasmSeverityMapping:
    def test_severity_active_exploit_critical(self, connector: EasmConnector):
        raw = RawFinding(
            id="f-1",
            source="easm:censys",
            raw_data={
                "_provider": "censys",
                "ip": "1.1.1.1",
                "name": "x.com",
                "services": [],
                "risk": {"severity": "low"},
                "active_exploit": True,
            },
            fetched_at=datetime.now(timezone.utc),
            tenant_id="t",
        )
        rec = connector.normalize(raw)
        assert rec.severity == "critical"

    def test_severity_exposed_admin_high(self, connector: EasmConnector):
        raw = RawFinding(
            id="f-2",
            source="easm:shodan",
            raw_data={
                "_provider": "shodan",
                "ip_str": "1.1.1.1",
                "data": [
                    {"port": 8443, "http": {"title": "Admin Console"}},
                ],
                "vulns": [],
            },
            fetched_at=datetime.now(timezone.utc),
            tenant_id="t",
        )
        rec = connector.normalize(raw)
        assert rec.severity == "high"

    def test_severity_dev_staging_medium(self, connector: EasmConnector):
        raw = RawFinding(
            id="f-3",
            source="easm:censys",
            raw_data={
                "_provider": "censys",
                "name": "dev.example.com",
                "services": [{"port": 80, "service_name": "HTTP"}],
                "risk": {"severity": "medium"},
            },
            fetched_at=datetime.now(timezone.utc),
            tenant_id="t",
        )
        rec = connector.normalize(raw)
        assert rec.severity == "medium"

    def test_severity_internal_only_low(self, connector: EasmConnector):
        raw = RawFinding(
            id="f-4",
            source="easm:shodan",
            raw_data={
                "_provider": "shodan",
                "ip_str": "10.0.0.5",
                "data": [{"port": 9100}],
                "vulns": [],
            },
            fetched_at=datetime.now(timezone.utc),
            tenant_id="t",
        )
        rec = connector.normalize(raw)
        assert rec.severity == "low"

    def test_detectify_severity_critical(self, connector: EasmConnector):
        raw = RawFinding(
            id="f-5",
            source="easm:detectify",
            raw_data={
                "_provider": "detectify",
                "uuid": "f-5",
                "severity": "critical",
                "title": "SQL Injection",
                "url": "https://test.com/x",
                "confirmed": True,
            },
            fetched_at=datetime.now(timezone.utc),
            tenant_id="t",
        )
        rec = connector.normalize(raw)
        assert rec.severity == "critical"

    def test_normalize_domain_is_external_attack_surface(
        self, connector: EasmConnector
    ):
        raw = RawFinding(
            id="f-6",
            source="easm:censys",
            raw_data={
                "_provider": "censys",
                "name": "x.com",
                "services": [],
                "risk": {"severity": "low"},
            },
            fetched_at=datetime.now(timezone.utc),
            tenant_id="t",
        )
        rec = connector.normalize(raw)
        assert rec.domain == "external_attack_surface"


# ─────────────────────────────────────────────────────────────────────────────
# 7. Health check
# ─────────────────────────────────────────────────────────────────────────────

class TestEasmHealth:
    def test_health_check_fresh_ok(self, connector: EasmConnector):
        h = connector.health_check()
        assert isinstance(h, ConnectorHealth)
        assert h.connector_name == "easm"
        assert h.status == "ok"
        assert h.last_run is None

    @respx.mock
    def test_health_check_last_run_after_success(
        self, connector: EasmConnector, censys_credentials: dict
    ):
        respx.get("https://search.censys.io/api/v2/account").mock(
            return_value=httpx.Response(200, json={"login": "ok"})
        )
        respx.get("https://search.censys.io/api/v2/hosts/search").mock(
            return_value=httpx.Response(
                200, json={"result": {"hits": [], "links": {"next": ""}}}
            )
        )
        connector.authenticate(censys_credentials)
        connector.fetch_findings(
            since=datetime(2024, 1, 1, tzinfo=timezone.utc), tenant_id="tenant-1",
        )
        h = connector.health_check()
        assert h.last_run is not None

    @respx.mock
    def test_health_check_degraded_after_errors(
        self, connector: EasmConnector, censys_credentials: dict
    ):
        respx.get("https://search.censys.io/api/v2/account").mock(
            return_value=httpx.Response(200, json={"login": "ok"})
        )
        respx.get("https://search.censys.io/api/v2/hosts/search").mock(
            return_value=httpx.Response(500, json={"error": "boom"})
        )
        connector.authenticate(censys_credentials)
        for _ in range(2):
            try:
                connector.fetch_findings(
                    since=datetime(2024, 1, 1, tzinfo=timezone.utc), tenant_id="tenant-1",
                )
            except ConnectorFetchError:
                pass
        h = connector.health_check()
        assert h.error_count >= 1
        assert h.status in ("degraded", "error")
