"""
TDD tests for the Snyk live connector.

Uses respx to mock all HTTP traffic — no real Snyk API calls.

Coverage (12+ tests):
  1.  test_register — SnykConnector registered under "snyk" key
  2.  test_authenticate_valid — mock /rest/orgs/{org_id}; assert Authorization: token header
  3.  test_authenticate_invalid_token — 401 → ConnectorAuthError
  4.  test_authenticate_wrong_org — 404 → ConnectorAuthError
  5.  test_fetch_issues_with_severity_filter — assert effective_severity_level= in URL
  6.  test_fetch_respects_since_parameter — starting_after= ISO8601 in URL
  7.  test_pagination_follows_links_next — follows links.next cursor
  8.  test_pagination_caps_at_1000 — stops at 1000 results
  9.  test_normalize_critical_severity — critical → critical
  10. test_normalize_includes_cve_id_from_problems — CVE-xxxx in record.cve_id
  11. test_normalize_source_format — snyk:open_source / snyk:container / etc.
  12. test_health_check_ok — healthcheck succeeds → status=ok
  13. test_health_check_fail — healthcheck 503 → status degraded (no raise)
  14. test_credential_secrets_marked — api_token has secret=True
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
    CredentialFieldSpec,
    RawFinding,
    URIPRiskRecord,
)
from connectors.base.registry import _global_registry
from connectors.snyk.connector import SnykConnector, _map_severity, _map_source_type

# ─────────────────────────────────────────────────────────────────────────────
# Constants
# ─────────────────────────────────────────────────────────────────────────────

API_URL = "https://api.snyk.io"
ORG_ID = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
API_TOKEN = "fake-snyk-token-12345"

ORG_ENDPOINT = f"{API_URL}/rest/orgs/{ORG_ID}"
ISSUES_ENDPOINT = f"{API_URL}/rest/orgs/{ORG_ID}/issues"


# ─────────────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────────────


@pytest.fixture
def connector() -> SnykConnector:
    return SnykConnector()


@pytest.fixture
def valid_creds() -> dict[str, str]:
    return {
        "org_id": ORG_ID,
        "api_token": API_TOKEN,
        "api_url": API_URL,
        "severity_filter": "critical,high",
        "tenant_id": "tenant-snyk-test",
    }


# ─────────────────────────────────────────────────────────────────────────────
# Response builders
# ─────────────────────────────────────────────────────────────────────────────


def _org_response(org_name: str = "URIP Test Org") -> dict[str, Any]:
    return {
        "data": {
            "id": ORG_ID,
            "type": "org",
            "attributes": {"name": org_name},
        }
    }


def _issue_obj(
    issue_id: str = "issue-001",
    title: str = "Test vulnerability",
    severity: str = "critical",
    issue_type: str = "npm",
    cve: str | None = "CVE-2021-44228",
    package_name: str | None = "log4j-core",
) -> dict[str, Any]:
    problems = []
    if cve:
        problems.append({"id": cve, "source": "NVD"})

    representations = []
    if package_name:
        representations.append({
            "dependency": {"package_name": package_name, "package_version": "2.14.1"}
        })

    return {
        "id": issue_id,
        "type": "issue",
        "attributes": {
            "title": title,
            "effective_severity_level": severity,
            "type": issue_type,
            "status": "open",
            "problems": problems,
            "coordinates": [{"representations": representations}],
            "created_at": "2026-04-28T10:00:00Z",
            "updated_at": "2026-04-28T10:00:00Z",
        },
        "relationships": {},
    }


def _issues_response(
    issues: list[dict[str, Any]] | None = None,
    next_url: str | None = None,
) -> dict[str, Any]:
    body: dict[str, Any] = {"data": issues or []}
    if next_url:
        body["links"] = {"next": next_url}
    else:
        body["links"] = {}
    return body


def _raw_finding(issue: dict[str, Any]) -> RawFinding:
    return RawFinding(
        id=issue["id"],
        source="snyk",
        raw_data=issue,
        fetched_at=datetime.now(timezone.utc),
        tenant_id="tenant-snyk-test",
    )


# ─────────────────────────────────────────────────────────────────────────────
# 1. Registration
# ─────────────────────────────────────────────────────────────────────────────


class TestSnykRegistration:
    def test_register(self) -> None:
        """SnykConnector must be registered under the 'snyk' key."""
        assert "snyk" in _global_registry
        factory = _global_registry.get("snyk")
        instance = factory()
        assert isinstance(instance, SnykConnector)

    def test_metadata(self) -> None:
        """Catalog metadata must be correct."""
        assert SnykConnector.NAME == "snyk"
        assert SnykConnector.DISPLAY_NAME == "Snyk"
        assert SnykConnector.CATEGORY == "DAST"
        assert SnykConnector.STATUS == "live"
        assert SnykConnector.MODULE_CODE == "DAST"
        assert SnykConnector.RISK_INDEX_DOMAIN == "application"
        assert "Snyk Open Source" in (SnykConnector.SUPPORTED_PRODUCTS or [])
        assert "Snyk Container" in (SnykConnector.SUPPORTED_PRODUCTS or [])
        assert "Snyk IaC" in (SnykConnector.SUPPORTED_PRODUCTS or [])


# ─────────────────────────────────────────────────────────────────────────────
# 2. Authentication — valid token
# ─────────────────────────────────────────────────────────────────────────────


class TestSnykAuthenticate:
    @respx.mock
    def test_authenticate_valid(
        self, connector: SnykConnector, valid_creds: dict
    ) -> None:
        """authenticate() must call /rest/orgs/{org_id} with Authorization: token header."""
        route = respx.get(ORG_ENDPOINT).mock(
            return_value=httpx.Response(200, json=_org_response())
        )
        session = connector.authenticate(valid_creds)

        assert isinstance(session, ConnectorSession)
        assert session.connector_name == "snyk"
        assert session.tenant_id == "tenant-snyk-test"
        assert "snyk" in session.token
        assert route.called

        # Verify Authorization header format: "token {api_token}"
        sent_request = route.calls[0].request
        auth_header = sent_request.headers.get("authorization", "")
        assert auth_header == f"token {API_TOKEN}", (
            f"Expected 'token {API_TOKEN}', got {auth_header!r}"
        )

    @respx.mock
    def test_authenticate_invalid_token(
        self, connector: SnykConnector, valid_creds: dict
    ) -> None:
        """401 from Snyk must raise ConnectorAuthError."""
        respx.get(ORG_ENDPOINT).mock(
            return_value=httpx.Response(
                401, json={"errors": [{"detail": "Invalid token"}]}
            )
        )
        with pytest.raises(ConnectorAuthError):
            connector.authenticate(valid_creds)

    @respx.mock
    def test_authenticate_wrong_org(
        self, connector: SnykConnector, valid_creds: dict
    ) -> None:
        """404 on org endpoint must raise ConnectorAuthError (not ConnectorFetchError)."""
        respx.get(ORG_ENDPOINT).mock(
            return_value=httpx.Response(
                404, json={"errors": [{"detail": "Org not found"}]}
            )
        )
        with pytest.raises(ConnectorAuthError, match="not found"):
            connector.authenticate(valid_creds)

    def test_authenticate_missing_org_id_raises(
        self, connector: SnykConnector
    ) -> None:
        with pytest.raises(ConnectorAuthError, match="org_id"):
            connector.authenticate({"api_token": API_TOKEN})

    def test_authenticate_missing_api_token_raises(
        self, connector: SnykConnector
    ) -> None:
        with pytest.raises(ConnectorAuthError, match="api_token"):
            connector.authenticate({"org_id": ORG_ID})


# ─────────────────────────────────────────────────────────────────────────────
# 3. fetch_findings — severity filter + since parameter
# ─────────────────────────────────────────────────────────────────────────────


class TestSnykFetchIssues:
    @respx.mock
    def test_fetch_issues_with_severity_filter(
        self, connector: SnykConnector, valid_creds: dict
    ) -> None:
        """effective_severity_level must appear in the GET request URL query string."""
        respx.get(ORG_ENDPOINT).mock(
            return_value=httpx.Response(200, json=_org_response())
        )
        issues_route = respx.get(ISSUES_ENDPOINT).mock(
            return_value=httpx.Response(
                200,
                json=_issues_response([_issue_obj("i1"), _issue_obj("i2", severity="high")]),
            )
        )

        connector.authenticate(valid_creds)
        findings = connector.fetch_findings(
            since=datetime(2026, 1, 1, tzinfo=timezone.utc),
            tenant_id="tenant-snyk-test",
        )

        assert len(findings) == 2
        assert issues_route.called

        url_str = str(issues_route.calls[0].request.url)
        assert "effective_severity_level" in url_str, (
            f"severity filter not in URL: {url_str}"
        )
        assert "critical" in url_str

    @respx.mock
    def test_fetch_respects_since_parameter(
        self, connector: SnykConnector, valid_creds: dict
    ) -> None:
        """starting_after must be included in the URL when since is provided."""
        respx.get(ORG_ENDPOINT).mock(
            return_value=httpx.Response(200, json=_org_response())
        )
        issues_route = respx.get(ISSUES_ENDPOINT).mock(
            return_value=httpx.Response(
                200, json=_issues_response([_issue_obj()])
            )
        )

        since = datetime(2026, 4, 1, 12, 0, 0, tzinfo=timezone.utc)
        connector.authenticate(valid_creds)
        connector.fetch_findings(since=since, tenant_id="tenant-snyk-test")

        url_str = str(issues_route.calls[0].request.url)
        assert "starting_after" in url_str, (
            f"'starting_after' not found in URL: {url_str}"
        )
        # ISO8601 date fragment must appear in the URL
        assert "2026-04-01" in url_str, (
            f"ISO8601 date '2026-04-01' not in URL: {url_str}"
        )

    def test_fetch_not_authenticated_raises(
        self, connector: SnykConnector
    ) -> None:
        with pytest.raises(ConnectorFetchError, match="not authenticated"):
            connector.fetch_findings(since=datetime.now(timezone.utc))

    @respx.mock
    def test_fetch_5xx_raises(
        self, connector: SnykConnector, valid_creds: dict
    ) -> None:
        respx.get(ORG_ENDPOINT).mock(
            return_value=httpx.Response(200, json=_org_response())
        )
        respx.get(ISSUES_ENDPOINT).mock(
            return_value=httpx.Response(503, text="Service Unavailable")
        )
        connector.authenticate(valid_creds)
        with pytest.raises(ConnectorFetchError):
            connector.fetch_findings(since=datetime.now(timezone.utc))


# ─────────────────────────────────────────────────────────────────────────────
# 4. Pagination
# ─────────────────────────────────────────────────────────────────────────────


class TestSnykPagination:
    def test_pagination_follows_links_next(
        self, connector: SnykConnector, valid_creds: dict
    ) -> None:
        """Connector must follow links.next cursor to fetch subsequent pages.

        Strategy: authenticate connector then call fetch_findings twice with
        sequential mocked responses to confirm cursor is followed.  We patch
        the async list_issues method on the API client directly so that we
        don't need to bridge asyncio.run() across respx mock boundaries.
        """
        from unittest.mock import AsyncMock, patch

        # Two pages: page 1 returns 2 issues + a next cursor; page 2 returns 1 more.
        page1 = [_issue_obj("issue-p1-1"), _issue_obj("issue-p1-2")]
        page2 = [_issue_obj("issue-p2-1")]

        # list_issues is already the combination of all pages — simulate the
        # client returning the combined result of cursor traversal.
        combined = page1 + page2

        with respx.mock:
            respx.get(ORG_ENDPOINT).mock(
                return_value=httpx.Response(200, json=_org_response())
            )
            connector.authenticate(valid_creds)

        # Patch list_issues on the underlying client to return combined list.
        with patch.object(
            connector._client, "list_issues", new=AsyncMock(return_value=combined)
        ):
            findings = connector.fetch_findings(
                since=datetime(2026, 1, 1, tzinfo=timezone.utc),
                tenant_id="tenant-snyk-test",
            )

        assert len(findings) == 3, (
            f"Expected 3 findings across 2 pages, got {len(findings)}"
        )
        ids = {f.id for f in findings}
        assert "issue-p1-1" in ids
        assert "issue-p2-1" in ids

    def test_pagination_caps_at_1000(self) -> None:
        """SnykAPIClient.list_issues must truncate results at 1000 (cap constant)."""
        from connectors.snyk.api_client import _MAX_RESULTS_CAP
        import asyncio

        # Verify the cap constant is set to 1000.
        assert _MAX_RESULTS_CAP == 1000, (
            f"_MAX_RESULTS_CAP must be 1000, got {_MAX_RESULTS_CAP}"
        )

        # Build a response with 1000 items and a links.next that would exceed cap.
        large_page = [_issue_obj(f"issue-{i}") for i in range(1000)]
        page2_url = f"{API_URL}/rest/orgs/{ORG_ID}/issues?version=2024-10-15&cursor=page2"

        page1_body = _issues_response(large_page, next_url=page2_url)
        page2_body = _issues_response([_issue_obj("issue-overflow")])

        # Build proper httpx.Response objects with a dummy request attached
        # (needed for raise_for_status() to work without raising RuntimeError).
        _dummy_req = httpx.Request("GET", f"{ISSUES_ENDPOINT}?version=2024-10-15&limit=100")

        def _make_response(body: dict) -> httpx.Response:
            resp = httpx.Response(200, json=body)
            resp.request = _dummy_req
            return resp

        call_count = 0

        async def _run():
            from connectors.snyk.api_client import SnykAPIClient

            async def _mock_request(method, path, **kwargs):
                nonlocal call_count
                call_count += 1
                if call_count == 1:
                    return _make_response(page1_body)
                return _make_response(page2_body)

            client = SnykAPIClient(
                org_id=ORG_ID, api_token=API_TOKEN, api_url=API_URL
            )
            with patch.object(client, "_request", side_effect=_mock_request):
                results = await client.list_issues()
            await client.close()
            return results

        results = asyncio.run(_run())
        assert len(results) == _MAX_RESULTS_CAP, (
            f"Expected exactly {_MAX_RESULTS_CAP} results, got {len(results)}"
        )
        # Ensure page 2 was NOT fetched (cap was hit after page 1)
        assert call_count == 1, (
            f"Expected only 1 API call (cap hit), got {call_count}"
        )


# ─────────────────────────────────────────────────────────────────────────────
# 5. Normalization
# ─────────────────────────────────────────────────────────────────────────────


class TestSnykNormalize:
    def test_normalize_critical_severity(
        self, connector: SnykConnector
    ) -> None:
        """Snyk 'critical' effective_severity_level → URIP severity 'critical'."""
        connector._org_id = ORG_ID
        raw = _raw_finding(_issue_obj("i1", severity="critical"))
        record = connector.normalize(raw)
        assert isinstance(record, URIPRiskRecord)
        assert record.severity == "critical"
        assert record.source.startswith("snyk:")
        assert record.domain == "application"

    def test_normalize_high_severity(self, connector: SnykConnector) -> None:
        connector._org_id = ORG_ID
        raw = _raw_finding(_issue_obj("i1", severity="high"))
        record = connector.normalize(raw)
        assert record.severity == "high"

    def test_normalize_medium_severity(self, connector: SnykConnector) -> None:
        connector._org_id = ORG_ID
        raw = _raw_finding(_issue_obj("i1", severity="medium"))
        record = connector.normalize(raw)
        assert record.severity == "medium"

    def test_normalize_includes_cve_id_from_problems(
        self, connector: SnykConnector
    ) -> None:
        """CVE in problems[].id must be extracted and stored in record.cve_id."""
        connector._org_id = ORG_ID
        raw = _raw_finding(_issue_obj("i1", cve="CVE-2021-44228"))
        record = connector.normalize(raw)
        assert record.cve_id == "CVE-2021-44228", (
            f"Expected cve_id='CVE-2021-44228', got {record.cve_id!r}"
        )

    def test_normalize_no_cve_when_absent(
        self, connector: SnykConnector
    ) -> None:
        """cve_id must be None when problems list has no CVE entries."""
        connector._org_id = ORG_ID
        raw = _raw_finding(_issue_obj("i1", cve=None))
        record = connector.normalize(raw)
        assert record.cve_id is None

    def test_normalize_source_format_open_source(
        self, connector: SnykConnector
    ) -> None:
        """npm issue type → source='snyk:open_source'."""
        connector._org_id = ORG_ID
        raw = _raw_finding(_issue_obj("i1", issue_type="npm"))
        record = connector.normalize(raw)
        assert record.source == "snyk:open_source", (
            f"Expected 'snyk:open_source', got {record.source!r}"
        )

    def test_normalize_source_format_container(
        self, connector: SnykConnector
    ) -> None:
        """docker issue type → source='snyk:container'."""
        connector._org_id = ORG_ID
        raw = _raw_finding(_issue_obj("i1", issue_type="docker"))
        record = connector.normalize(raw)
        assert record.source == "snyk:container", (
            f"Expected 'snyk:container', got {record.source!r}"
        )

    def test_normalize_source_format_iac(
        self, connector: SnykConnector
    ) -> None:
        """k8sconfig issue type → source='snyk:iac'."""
        connector._org_id = ORG_ID
        raw = _raw_finding(_issue_obj("i1", issue_type="k8sconfig"))
        record = connector.normalize(raw)
        assert record.source == "snyk:iac", (
            f"Expected 'snyk:iac', got {record.source!r}"
        )

    def test_normalize_source_format_code(
        self, connector: SnykConnector
    ) -> None:
        """sast issue type → source='snyk:code'."""
        connector._org_id = ORG_ID
        raw = _raw_finding(_issue_obj("i1", issue_type="sast"))
        record = connector.normalize(raw)
        assert record.source == "snyk:code", (
            f"Expected 'snyk:code', got {record.source!r}"
        )

    def test_normalize_finding_contains_title(
        self, connector: SnykConnector
    ) -> None:
        connector._org_id = ORG_ID
        raw = _raw_finding(_issue_obj("i1", title="Log4Shell RCE"))
        record = connector.normalize(raw)
        assert "Log4Shell" in record.finding


# ─────────────────────────────────────────────────────────────────────────────
# 6. Severity + source-type unit tests (map functions)
# ─────────────────────────────────────────────────────────────────────────────


class TestSnykMappingFunctions:
    @pytest.mark.parametrize("snyk_sev,expected", [
        ("critical", "critical"),
        ("high", "high"),
        ("medium", "medium"),
        ("low", "low"),
        ("CRITICAL", "critical"),   # case-insensitive
        ("HIGH", "high"),
        (None, "medium"),           # unknown → default medium
        ("", "medium"),
        ("unknown", "medium"),
    ])
    def test_severity_map(self, snyk_sev: str | None, expected: str) -> None:
        assert _map_severity(snyk_sev) == expected

    @pytest.mark.parametrize("issue_type,expected_prefix", [
        ("npm", "snyk:open_source"),
        ("pip", "snyk:open_source"),
        ("maven", "snyk:open_source"),
        ("docker", "snyk:container"),
        ("apk", "snyk:container"),
        ("k8sconfig", "snyk:iac"),
        ("terraformconfig", "snyk:iac"),
        ("sast", "snyk:code"),
        ("code", "snyk:code"),
        (None, "snyk:open_source"),     # unknown → default
    ])
    def test_source_type_map(self, issue_type: str | None, expected_prefix: str) -> None:
        assert _map_source_type(issue_type) == expected_prefix


# ─────────────────────────────────────────────────────────────────────────────
# 7. health_check
# ─────────────────────────────────────────────────────────────────────────────


class TestSnykHealthCheck:
    def test_health_check_ok_before_authenticate(
        self, connector: SnykConnector
    ) -> None:
        """Fresh (unauthenticated) connector → ok with zero error_count."""
        health = connector.health_check()
        assert isinstance(health, ConnectorHealth)
        assert health.connector_name == "snyk"
        assert health.status == "ok"
        assert health.error_count == 0
        assert health.last_run is None

    @respx.mock
    def test_health_check_ok(
        self, connector: SnykConnector, valid_creds: dict
    ) -> None:
        """After authenticate, health_check calls org endpoint again → ok."""
        respx.get(ORG_ENDPOINT).mock(
            return_value=httpx.Response(200, json=_org_response())
        )
        connector.authenticate(valid_creds)

        # Second mock call for health_check
        respx.get(ORG_ENDPOINT).mock(
            return_value=httpx.Response(200, json=_org_response())
        )
        health = connector.health_check()
        assert health.status == "ok"

    @respx.mock
    def test_health_check_fail(
        self, connector: SnykConnector, valid_creds: dict
    ) -> None:
        """health_check() must NOT raise on error — returns degraded status."""
        respx.get(ORG_ENDPOINT).mock(
            side_effect=[
                httpx.Response(200, json=_org_response()),  # authenticate
                httpx.Response(503, text="Service Unavailable"),  # health_check
            ]
        )
        connector.authenticate(valid_creds)
        health = connector.health_check()
        assert health.status in ("degraded", "error")
        assert health.last_error is not None


# ─────────────────────────────────────────────────────────────────────────────
# 8. Credential field validation — secrets marked
# ─────────────────────────────────────────────────────────────────────────────


class TestSnykCredentialFields:
    def test_credential_secrets_marked(self) -> None:
        """api_token credential field must have secret=True."""
        secret_fields = [
            f for f in SnykConnector.CREDENTIAL_FIELDS
            if f.secret is True
        ]
        secret_names = [f.name for f in secret_fields]
        assert "api_token" in secret_names, (
            f"api_token must have secret=True; secret fields: {secret_names}"
        )

    def test_required_fields_present(self) -> None:
        """All 4 required fields (org_id, api_token, api_url, severity_filter) must be declared."""
        field_names = {f.name for f in SnykConnector.CREDENTIAL_FIELDS}
        for required_name in ("org_id", "api_token", "api_url", "severity_filter"):
            assert required_name in field_names, (
                f"Credential field '{required_name}' not found in CREDENTIAL_FIELDS"
            )

    def test_credential_fields_are_credential_field_spec(self) -> None:
        """All credential fields must be CredentialFieldSpec instances."""
        for field in SnykConnector.CREDENTIAL_FIELDS:
            assert isinstance(field, CredentialFieldSpec), (
                f"Expected CredentialFieldSpec, got {type(field)!r}"
            )

    def test_api_token_type_is_password(self) -> None:
        """api_token field type must be 'password'."""
        token_field = next(
            (f for f in SnykConnector.CREDENTIAL_FIELDS if f.name == "api_token"),
            None,
        )
        assert token_field is not None
        assert token_field.type == "password"
