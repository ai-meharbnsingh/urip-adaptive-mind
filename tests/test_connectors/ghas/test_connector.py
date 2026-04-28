"""
TDD tests for the GitHub Advanced Security (GHAS) live connector.

Uses respx to mock all HTTP traffic — no real API calls.

Coverage (14 tests):
  1.  test_register                              — "ghas" key in global registry
  2.  test_authenticate_valid                    — mock /orgs/{org}, assert Bearer header
  3.  test_authenticate_invalid_token (401)      — ConnectorAuthError raised
  4.  test_authenticate_invalid_org (404)        — ConnectorFetchError raised
  5.  test_fetch_code_scanning_alerts            — mocked code-scanning endpoint
  6.  test_fetch_secret_scanning_alerts          — mocked secret-scanning endpoint
  7.  test_fetch_dependabot_alerts               — mocked dependabot endpoint
  8.  test_normalize_critical_severity           — security_severity_level=critical → critical
  9.  test_normalize_secret_alert_always_critical — secret alerts always severity=critical
  10. test_normalize_dependabot_uses_advisory_severity — advisory.severity drives URIP severity
  11. test_pagination_follows_link_header        — connector follows Link: next page
  12. test_pagination_caps_at_1000              — pagination stops at 1000 results
  13. test_health_check_ok                       — healthy after authenticate
  14. test_health_check_fail                     — degraded when /orgs/{org} returns 503
"""

from __future__ import annotations

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
from connectors.base.registry import _global_registry
from connectors.ghas.connector import GhasConnector
from connectors.ghas.api_client import GhasAPIClient, _next_link

# ─────────────────────────────────────────────────────────────────────────────
# Constants
# ─────────────────────────────────────────────────────────────────────────────

API_BASE = "https://api.github.com"
ORG = "test-org"


# ─────────────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────────────


@pytest.fixture
def connector() -> GhasConnector:
    return GhasConnector()


@pytest.fixture
def valid_creds() -> dict[str, str]:
    return {
        "org": ORG,
        "token": "ghp_FAKE_TOKEN_12345",
        "api_url": API_BASE,
        "tenant_id": "tenant-ghas-test",
    }


# ─────────────────────────────────────────────────────────────────────────────
# Helpers — mock payloads
# ─────────────────────────────────────────────────────────────────────────────


def _org_response(login: str = ORG) -> dict[str, Any]:
    return {
        "login": login,
        "id": 12345678,
        "url": f"{API_BASE}/orgs/{login}",
        "description": "Test organization",
    }


def _code_scanning_alert(
    number: int = 1,
    state: str = "open",
    rule_id: str = "java/sql-injection",
    security_severity: str = "critical",
    file_path: str = "src/Main.java",
) -> dict[str, Any]:
    return {
        "number": number,
        "state": state,
        "rule": {
            "id": rule_id,
            "severity": "error",
            "security_severity_level": security_severity,
        },
        "most_recent_instance": {
            "location": {
                "path": file_path,
                "start_line": 42,
                "end_line": 44,
            },
            "ref": "refs/heads/main",
            "state": state,
        },
        "html_url": f"https://github.com/{ORG}/backend/security/code-scanning/{number}",
        "created_at": "2026-04-01T10:00:00Z",
        "updated_at": "2026-04-28T10:00:00Z",
    }


def _secret_scanning_alert(
    number: int = 1,
    state: str = "open",
    secret_type: str = "github_personal_access_token",
    display_name: str = "GitHub Personal Access Token",
) -> dict[str, Any]:
    return {
        "number": number,
        "state": state,
        "secret_type": secret_type,
        "secret_type_display_name": display_name,
        "html_url": f"https://github.com/{ORG}/repo/security/secret-scanning/{number}",
        "created_at": "2026-04-01T10:00:00Z",
        "updated_at": "2026-04-28T10:00:00Z",
    }


def _dependabot_alert(
    number: int = 1,
    state: str = "open",
    advisory_severity: str = "high",
    package_name: str = "lodash",
    vuln_range: str = "< 4.17.21",
    cve_id: str = "CVE-2021-23337",
) -> dict[str, Any]:
    return {
        "number": number,
        "state": state,
        "security_advisory": {
            "ghsa_id": "GHSA-xxxx-xxxx-xxxx",
            "cve_id": cve_id,
            "summary": f"Command injection in {package_name}",
            "severity": advisory_severity,
            "cvss_score": 7.2,
        },
        "security_vulnerability": {
            "package": {
                "ecosystem": "npm",
                "name": package_name,
            },
            "severity": advisory_severity,
            "vulnerable_version_range": vuln_range,
        },
        "html_url": f"https://github.com/{ORG}/frontend/security/dependabot/{number}",
        "created_at": "2026-04-01T10:00:00Z",
        "updated_at": "2026-04-28T10:00:00Z",
    }


def _raw_finding_code(alert: dict[str, Any]) -> RawFinding:
    return RawFinding(
        id=f"ghas:code:{alert['number']}",
        source="ghas:code",
        raw_data=alert,
        fetched_at=datetime.now(timezone.utc),
        tenant_id="tenant-test",
    )


def _raw_finding_secret(alert: dict[str, Any]) -> RawFinding:
    return RawFinding(
        id=f"ghas:secret:{alert['number']}",
        source="ghas:secret",
        raw_data=alert,
        fetched_at=datetime.now(timezone.utc),
        tenant_id="tenant-test",
    )


def _raw_finding_dependabot(alert: dict[str, Any]) -> RawFinding:
    return RawFinding(
        id=f"ghas:dependabot:{alert['number']}",
        source="ghas:dependabot",
        raw_data=alert,
        fetched_at=datetime.now(timezone.utc),
        tenant_id="tenant-test",
    )


# ─────────────────────────────────────────────────────────────────────────────
# 1. Registration
# ─────────────────────────────────────────────────────────────────────────────


class TestGhasRegistration:
    def test_register(self) -> None:
        """GhasConnector must be registered under the 'ghas' key."""
        assert "ghas" in _global_registry
        factory = _global_registry.get("ghas")
        instance = factory()
        assert isinstance(instance, GhasConnector)

    def test_metadata(self) -> None:
        """Catalog metadata must be populated correctly."""
        assert GhasConnector.NAME == "ghas"
        assert GhasConnector.DISPLAY_NAME == "GitHub Advanced Security"
        assert GhasConnector.CATEGORY == "DAST"
        assert GhasConnector.MODULE_CODE == "DAST"
        assert GhasConnector.STATUS == "live"
        assert GhasConnector.RISK_INDEX_DOMAIN == "application"
        assert len(GhasConnector.CREDENTIAL_FIELDS) == 3

    def test_credential_secrets_marked(self) -> None:
        """The 'token' field must have secret=True."""
        token_field = next(
            (f for f in GhasConnector.CREDENTIAL_FIELDS if f.name == "token"), None
        )
        assert token_field is not None, "token credential field must exist"
        assert token_field.secret is True, "token field must have secret=True"

        # 'org' and 'api_url' are not secrets
        org_field = next(f for f in GhasConnector.CREDENTIAL_FIELDS if f.name == "org")
        assert org_field.secret is False

        api_url_field = next(
            f for f in GhasConnector.CREDENTIAL_FIELDS if f.name == "api_url"
        )
        assert api_url_field.secret is False


# ─────────────────────────────────────────────────────────────────────────────
# 2. Authentication — valid credentials
# ─────────────────────────────────────────────────────────────────────────────


class TestGhasAuthenticate:
    @respx.mock
    def test_authenticate_valid(
        self, connector: GhasConnector, valid_creds: dict
    ) -> None:
        """authenticate() must call GET /orgs/{org} with Bearer token header."""
        route = respx.get(f"{API_BASE}/orgs/{ORG}").mock(
            return_value=httpx.Response(200, json=_org_response())
        )

        session = connector.authenticate(valid_creds)

        assert isinstance(session, ConnectorSession)
        assert session.connector_name == "ghas"
        assert session.token == "ghas-bearer-****"

        # Verify the correct auth header was sent
        assert route.called
        request_headers = route.calls[0].request.headers
        assert "Authorization" in request_headers
        assert request_headers["Authorization"] == f"Bearer {valid_creds['token']}"
        assert request_headers["Accept"] == "application/vnd.github+json"
        assert "X-GitHub-Api-Version" in request_headers

    @respx.mock
    def test_authenticate_invalid_token(
        self, connector: GhasConnector, valid_creds: dict
    ) -> None:
        """401 from /orgs/{org} must raise ConnectorAuthError."""
        respx.get(f"{API_BASE}/orgs/{ORG}").mock(
            return_value=httpx.Response(
                401, json={"message": "Bad credentials"}
            )
        )

        with pytest.raises(ConnectorAuthError):
            connector.authenticate(valid_creds)

    @respx.mock
    def test_authenticate_invalid_org(
        self, connector: GhasConnector, valid_creds: dict
    ) -> None:
        """404 from /orgs/{org} must raise ConnectorFetchError (org not found)."""
        respx.get(f"{API_BASE}/orgs/{ORG}").mock(
            return_value=httpx.Response(
                404, json={"message": "Not Found"}
            )
        )

        with pytest.raises((ConnectorFetchError, ConnectorAuthError)):
            connector.authenticate(valid_creds)

    def test_authenticate_missing_org_raises(
        self, connector: GhasConnector
    ) -> None:
        """authenticate() must raise ConnectorAuthError if 'org' is missing."""
        with pytest.raises(ConnectorAuthError, match="'org'"):
            connector.authenticate({"token": "ghp_abc", "api_url": API_BASE})

    def test_authenticate_missing_token_raises(
        self, connector: GhasConnector
    ) -> None:
        """authenticate() must raise ConnectorAuthError if 'token' is missing."""
        with pytest.raises(ConnectorAuthError, match="'token'"):
            connector.authenticate({"org": ORG, "api_url": API_BASE})


# ─────────────────────────────────────────────────────────────────────────────
# 3–5. fetch_findings per alert type
# ─────────────────────────────────────────────────────────────────────────────


class TestGhasFetchFindings:
    def _authenticate(
        self, connector: GhasConnector, valid_creds: dict
    ) -> None:
        """Helper: authenticate connector with a mocked /orgs/{org} response."""
        with respx.mock:
            respx.get(f"{API_BASE}/orgs/{ORG}").mock(
                return_value=httpx.Response(200, json=_org_response())
            )
            connector.authenticate(valid_creds)

    @respx.mock
    def test_fetch_code_scanning_alerts(
        self, connector: GhasConnector, valid_creds: dict
    ) -> None:
        """fetch_findings() must return RawFindings with source='ghas:code'."""
        respx.get(f"{API_BASE}/orgs/{ORG}").mock(
            return_value=httpx.Response(200, json=_org_response())
        )
        respx.get(f"{API_BASE}/orgs/{ORG}/code-scanning/alerts").mock(
            return_value=httpx.Response(200, json=[_code_scanning_alert(number=1)])
        )
        respx.get(f"{API_BASE}/orgs/{ORG}/secret-scanning/alerts").mock(
            return_value=httpx.Response(200, json=[])
        )
        respx.get(f"{API_BASE}/orgs/{ORG}/dependabot/alerts").mock(
            return_value=httpx.Response(200, json=[])
        )

        connector.authenticate(valid_creds)
        findings = connector.fetch_findings(
            since=datetime(2020, 1, 1, tzinfo=timezone.utc),
            tenant_id="tenant-test",
        )

        code_findings = [f for f in findings if f.source == "ghas:code"]
        assert len(code_findings) == 1
        assert code_findings[0].id == "ghas:code:1"
        assert code_findings[0].raw_data["number"] == 1

    @respx.mock
    def test_fetch_secret_scanning_alerts(
        self, connector: GhasConnector, valid_creds: dict
    ) -> None:
        """fetch_findings() must return RawFindings with source='ghas:secret'."""
        respx.get(f"{API_BASE}/orgs/{ORG}").mock(
            return_value=httpx.Response(200, json=_org_response())
        )
        respx.get(f"{API_BASE}/orgs/{ORG}/code-scanning/alerts").mock(
            return_value=httpx.Response(200, json=[])
        )
        respx.get(f"{API_BASE}/orgs/{ORG}/secret-scanning/alerts").mock(
            return_value=httpx.Response(
                200, json=[_secret_scanning_alert(number=7)]
            )
        )
        respx.get(f"{API_BASE}/orgs/{ORG}/dependabot/alerts").mock(
            return_value=httpx.Response(200, json=[])
        )

        connector.authenticate(valid_creds)
        findings = connector.fetch_findings(
            since=datetime(2020, 1, 1, tzinfo=timezone.utc),
            tenant_id="tenant-test",
        )

        secret_findings = [f for f in findings if f.source == "ghas:secret"]
        assert len(secret_findings) == 1
        assert secret_findings[0].id == "ghas:secret:7"
        assert secret_findings[0].raw_data["secret_type"] == "github_personal_access_token"

    @respx.mock
    def test_fetch_dependabot_alerts(
        self, connector: GhasConnector, valid_creds: dict
    ) -> None:
        """fetch_findings() must return RawFindings with source='ghas:dependabot'."""
        respx.get(f"{API_BASE}/orgs/{ORG}").mock(
            return_value=httpx.Response(200, json=_org_response())
        )
        respx.get(f"{API_BASE}/orgs/{ORG}/code-scanning/alerts").mock(
            return_value=httpx.Response(200, json=[])
        )
        respx.get(f"{API_BASE}/orgs/{ORG}/secret-scanning/alerts").mock(
            return_value=httpx.Response(200, json=[])
        )
        respx.get(f"{API_BASE}/orgs/{ORG}/dependabot/alerts").mock(
            return_value=httpx.Response(
                200, json=[_dependabot_alert(number=15)]
            )
        )

        connector.authenticate(valid_creds)
        findings = connector.fetch_findings(
            since=datetime(2020, 1, 1, tzinfo=timezone.utc),
            tenant_id="tenant-test",
        )

        dep_findings = [f for f in findings if f.source == "ghas:dependabot"]
        assert len(dep_findings) == 1
        assert dep_findings[0].id == "ghas:dependabot:15"
        assert dep_findings[0].raw_data["security_advisory"]["cve_id"] == "CVE-2021-23337"

    def test_fetch_not_authenticated_raises(
        self, connector: GhasConnector
    ) -> None:
        """fetch_findings() must raise ConnectorFetchError if not authenticated."""
        with pytest.raises(ConnectorFetchError, match="not authenticated"):
            connector.fetch_findings(since=datetime(2020, 1, 1, tzinfo=timezone.utc))


# ─────────────────────────────────────────────────────────────────────────────
# 6–8. normalize — severity mapping
# ─────────────────────────────────────────────────────────────────────────────


class TestGhasNormalize:
    @pytest.fixture(autouse=True)
    def _set_org(self, connector: GhasConnector) -> None:
        """Set _org on connector so normalize methods work without authentication."""
        connector._org = ORG

    def test_normalize_critical_severity(
        self, connector: GhasConnector
    ) -> None:
        """security_severity_level=critical must produce severity='critical' in URIPRiskRecord."""
        alert = _code_scanning_alert(security_severity="critical")
        raw = _raw_finding_code(alert)
        record = connector.normalize(raw)

        assert isinstance(record, URIPRiskRecord)
        assert record.severity == "critical"
        assert record.source == "ghas:code"
        assert record.domain == "application"
        assert "java/sql-injection" in record.finding

    def test_normalize_high_severity(
        self, connector: GhasConnector
    ) -> None:
        """security_severity_level=high → severity='high'."""
        alert = _code_scanning_alert(security_severity="high")
        raw = _raw_finding_code(alert)
        record = connector.normalize(raw)
        assert record.severity == "high"

    def test_normalize_medium_severity(
        self, connector: GhasConnector
    ) -> None:
        """security_severity_level=medium → severity='medium'."""
        alert = _code_scanning_alert(security_severity="medium")
        raw = _raw_finding_code(alert)
        record = connector.normalize(raw)
        assert record.severity == "medium"

    def test_normalize_rule_severity_fallback(
        self, connector: GhasConnector
    ) -> None:
        """When security_severity_level is absent, fall back to rule.severity."""
        alert = _code_scanning_alert(security_severity=None)
        # Manually remove security_severity_level from the rule
        alert["rule"]["security_severity_level"] = None
        alert["rule"]["severity"] = "warning"
        raw = _raw_finding_code(alert)
        record = connector.normalize(raw)
        assert record.severity == "medium"  # "warning" → "medium"

    def test_normalize_secret_alert_always_critical(
        self, connector: GhasConnector
    ) -> None:
        """Secret scanning alerts must always produce severity='critical'."""
        alert = _secret_scanning_alert(
            secret_type="aws_access_key_id",
            display_name="Amazon Web Services Access Key ID",
        )
        raw = _raw_finding_secret(alert)
        record = connector.normalize(raw)

        assert record.severity == "critical"
        assert record.source == "ghas:secret"
        assert "Amazon Web Services Access Key ID" in record.finding
        # Secret leaks should be marked as actively exploitable
        assert record.exploit_status == "active"

    def test_normalize_dependabot_uses_advisory_severity(
        self, connector: GhasConnector
    ) -> None:
        """Dependabot: severity must come from security_advisory.severity."""
        alert = _dependabot_alert(advisory_severity="high", package_name="lodash")
        raw = _raw_finding_dependabot(alert)
        record = connector.normalize(raw)

        assert record.severity == "high"
        assert record.source == "ghas:dependabot"
        assert "lodash" in record.finding
        assert record.cve_id == "CVE-2021-23337"
        assert record.cvss_score == 7.2

    def test_normalize_dependabot_critical(
        self, connector: GhasConnector
    ) -> None:
        """Dependabot: critical advisory → severity='critical'."""
        alert = _dependabot_alert(advisory_severity="critical", package_name="openssl")
        raw = _raw_finding_dependabot(alert)
        record = connector.normalize(raw)
        assert record.severity == "critical"

    def test_normalize_code_scanning_asset_is_file_path(
        self, connector: GhasConnector
    ) -> None:
        """Code scanning: asset field must be the file path from most_recent_instance."""
        alert = _code_scanning_alert(file_path="src/auth/LoginService.py")
        raw = _raw_finding_code(alert)
        record = connector.normalize(raw)
        assert record.asset == "src/auth/LoginService.py"

    def test_normalize_dependabot_asset_is_dep_package(
        self, connector: GhasConnector
    ) -> None:
        """Dependabot: asset must be 'dep:{package_name}'."""
        alert = _dependabot_alert(package_name="express")
        raw = _raw_finding_dependabot(alert)
        record = connector.normalize(raw)
        assert record.asset == "dep:express"


# ─────────────────────────────────────────────────────────────────────────────
# 9. Pagination — Link: rel="next" header handling
# ─────────────────────────────────────────────────────────────────────────────


class TestGhasPagination:
    def test_next_link_parser_returns_url(self) -> None:
        """_next_link() must extract the URL from Link: rel="next" header."""
        link_header = (
            '<https://api.github.com/orgs/test-org/code-scanning/alerts?page=2>; rel="next", '
            '<https://api.github.com/orgs/test-org/code-scanning/alerts?page=5>; rel="last"'
        )
        result = _next_link(link_header)
        assert result == "https://api.github.com/orgs/test-org/code-scanning/alerts?page=2"

    def test_next_link_parser_returns_none_when_no_next(self) -> None:
        """_next_link() must return None when no rel="next" is present."""
        link_header = (
            '<https://api.github.com/orgs/test-org/code-scanning/alerts?page=5>; rel="last"'
        )
        assert _next_link(link_header) is None

    def test_next_link_parser_returns_none_for_empty(self) -> None:
        """_next_link() must return None for empty/None input."""
        assert _next_link(None) is None
        assert _next_link("") is None

    @respx.mock
    def test_pagination_follows_link_header(
        self, connector: GhasConnector, valid_creds: dict
    ) -> None:
        """
        Connector must follow Link: rel="next" pagination across multiple pages.
        Page 1 has alert #1, page 2 has alert #2. Both must appear in fetch_findings.

        Uses side_effect to serve different responses per call so the page-1 mock
        does not accidentally match the page-2 URL (respx path matching ignores
        query params by default).
        """
        page2_url = f"{API_BASE}/orgs/{ORG}/code-scanning/alerts?page=2&per_page=100"

        # Auth
        respx.get(f"{API_BASE}/orgs/{ORG}").mock(
            return_value=httpx.Response(200, json=_org_response())
        )

        # Code scanning: first call returns page 1 + Link header, second call returns page 2
        respx.get(f"{API_BASE}/orgs/{ORG}/code-scanning/alerts").mock(
            side_effect=[
                httpx.Response(
                    200,
                    json=[_code_scanning_alert(number=1)],
                    headers={"link": f'<{page2_url}>; rel="next"'},
                ),
                httpx.Response(
                    200,
                    json=[_code_scanning_alert(number=2)],
                ),
            ]
        )

        # Secret + Dependabot return empty
        respx.get(f"{API_BASE}/orgs/{ORG}/secret-scanning/alerts").mock(
            return_value=httpx.Response(200, json=[])
        )
        respx.get(f"{API_BASE}/orgs/{ORG}/dependabot/alerts").mock(
            return_value=httpx.Response(200, json=[])
        )

        connector.authenticate(valid_creds)
        findings = connector.fetch_findings(
            since=datetime(2020, 1, 1, tzinfo=timezone.utc),
            tenant_id="tenant-test",
        )

        code_findings = [f for f in findings if f.source == "ghas:code"]
        # Both pages must have been fetched
        alert_numbers = {f.raw_data["number"] for f in code_findings}
        assert 1 in alert_numbers
        assert 2 in alert_numbers

    def test_pagination_caps_at_1000(self) -> None:
        """
        _paginate() must stop collecting results once 1000 items are gathered,
        even if more pages remain.
        """
        import asyncio

        async def _run_cap_test() -> int:
            client = GhasAPIClient(org=ORG, token="ghp_fake", api_url=API_BASE)
            page_url = f"{API_BASE}/orgs/{ORG}/code-scanning/alerts"
            page2_url = f"{API_BASE}/orgs/{ORG}/code-scanning/alerts?page=2"

            # Build 600 items on page 1 and 600 on page 2 (total 1200 — should be capped at 1000)
            page1_data = [_code_scanning_alert(number=i) for i in range(1, 601)]
            page2_data = [_code_scanning_alert(number=i) for i in range(601, 1201)]

            with respx.mock:
                respx.get(page_url).mock(
                    return_value=httpx.Response(
                        200,
                        json=page1_data,
                        headers={"link": f'<{page2_url}>; rel="next"'},
                    )
                )
                respx.get(page2_url).mock(
                    return_value=httpx.Response(200, json=page2_data)
                )

                results = await client._paginate(page_url, {"state": "open", "per_page": 100})
                await client.close()
                return len(results)

        total = asyncio.run(_run_cap_test())
        assert total == 1000, f"Expected 1000 results (cap), got {total}"


# ─────────────────────────────────────────────────────────────────────────────
# 10. health_check
# ─────────────────────────────────────────────────────────────────────────────


class TestGhasHealthCheck:
    def test_health_check_ok_before_authenticate(
        self, connector: GhasConnector
    ) -> None:
        """Fresh (unauthenticated) connector must return status='ok' with no errors."""
        health = connector.health_check()
        assert isinstance(health, ConnectorHealth)
        assert health.connector_name == "ghas"
        assert health.status == "ok"
        assert health.error_count == 0
        assert health.last_run is None

    @respx.mock
    def test_health_check_ok(
        self, connector: GhasConnector, valid_creds: dict
    ) -> None:
        """health_check() returns 'ok' after successful authenticate."""
        # Two calls: one from authenticate(), one from health_check()
        respx.get(f"{API_BASE}/orgs/{ORG}").mock(
            return_value=httpx.Response(200, json=_org_response())
        )

        connector.authenticate(valid_creds)

        # health_check() calls healthcheck() again
        respx.get(f"{API_BASE}/orgs/{ORG}").mock(
            return_value=httpx.Response(200, json=_org_response())
        )

        health = connector.health_check()
        assert health.status == "ok"
        assert health.connector_name == "ghas"

    @respx.mock
    def test_health_check_fail(
        self, connector: GhasConnector, valid_creds: dict
    ) -> None:
        """health_check() must NOT raise — returns degraded ConnectorHealth on 5xx."""
        # authenticate() call
        respx.get(f"{API_BASE}/orgs/{ORG}").mock(
            return_value=httpx.Response(200, json=_org_response())
        )
        connector.authenticate(valid_creds)

        # health_check() call fails with 503
        respx.get(f"{API_BASE}/orgs/{ORG}").mock(
            return_value=httpx.Response(503, text="Service Unavailable")
        )

        health = connector.health_check()
        assert health.status in ("degraded", "error")
        assert health.last_error is not None
        assert health.connector_name == "ghas"
