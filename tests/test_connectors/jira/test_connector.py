"""
TDD tests for the Jira Cloud + Jira Data Center live connector.

Uses respx to mock all HTTP traffic — no real API calls.

Coverage:
  - Connector registration ("jira" key in global registry)
  - Priority normalization map (Highest → critical, High → high, …)
  - Authentication — Basic (Cloud) and Bearer (DC/Server)
  - fetch_findings — verifies JQL is passed through
  - create_ticket — verifies POST body shape (summary + ADF description + priority)
  - health_check — ok path and degraded path
"""

from __future__ import annotations

import base64
from datetime import datetime, timezone
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

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
from connectors.jira.connector import JiraConnector, _extract_adf_text
from connectors.jira.api_client import _plain_text_to_adf

# ─────────────────────────────────────────────────────────────────────────────
# Constants
# ─────────────────────────────────────────────────────────────────────────────

BASE = "https://jira-test.atlassian.net"
DC_BASE = "https://jira.internal.example.com"


# ─────────────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────────────


@pytest.fixture
def connector() -> JiraConnector:
    return JiraConnector()


@pytest.fixture
def basic_creds() -> dict[str, str]:
    return {
        "base_url": BASE,
        "auth_method": "basic",
        "email": "urip@atlassian-test.com",
        "api_token": "FAKE_API_TOKEN",
        "default_project_key": "SEC",
        "risk_jql": 'project = SEC AND labels = "security"',
        "tenant_id": "tenant-jira",
    }


@pytest.fixture
def bearer_creds() -> dict[str, str]:
    return {
        "base_url": DC_BASE,
        "auth_method": "bearer",
        "bearer_token": "FAKE_PAT_TOKEN",
        "default_project_key": "OPS",
        "risk_jql": 'project = OPS AND labels = "security"',
        "tenant_id": "tenant-dc",
    }


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────


def _myself_response(account_id: str = "abc123") -> dict[str, Any]:
    return {
        "accountId": account_id,
        "displayName": "URIP Service Account",
        "emailAddress": "urip@example.com",
        "active": True,
    }


def _search_response(issues: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    return {
        "total": len(issues or []),
        "startAt": 0,
        "maxResults": 50,
        "issues": issues or [],
    }


def _jira_issue(
    key: str = "SEC-1",
    summary: str = "Test finding",
    priority: str = "High",
    status: str = "Open",
) -> dict[str, Any]:
    return {
        "id": "10001",
        "key": key,
        "self": f"{BASE}/rest/api/3/issue/10001",
        "fields": {
            "summary": summary,
            "status": {"name": status},
            "priority": {"name": priority},
            "created": "2026-04-28T10:00:00Z",
            "updated": "2026-04-28T10:00:00Z",
            "description": None,
            "labels": ["security"],
        },
    }


def _raw_finding(issue: dict[str, Any], base_url: str = BASE) -> RawFinding:
    return RawFinding(
        id=issue["key"],
        source="jira",
        raw_data=issue,
        fetched_at=datetime.now(timezone.utc),
        tenant_id="tenant-jira",
    )


# ─────────────────────────────────────────────────────────────────────────────
# 1. Registration
# ─────────────────────────────────────────────────────────────────────────────


class TestJiraRegistration:
    def test_register(self):
        """JiraConnector must be registered under the 'jira' key."""
        assert "jira" in _global_registry
        factory = _global_registry.get("jira")
        instance = factory()
        assert isinstance(instance, JiraConnector)

    def test_metadata(self):
        """Catalog metadata must be populated correctly."""
        assert JiraConnector.NAME == "jira"
        assert JiraConnector.DISPLAY_NAME == "Jira"
        assert JiraConnector.CATEGORY == "ITSM"
        assert JiraConnector.STATUS == "live"
        assert JiraConnector.MODULE_CODE == "ITSM"
        assert JiraConnector.RISK_INDEX_DOMAIN is None
        assert "Jira Cloud" in (JiraConnector.SUPPORTED_PRODUCTS or [])
        assert "Jira Data Center" in (JiraConnector.SUPPORTED_PRODUCTS or [])


# ─────────────────────────────────────────────────────────────────────────────
# 2. Priority normalization map
# ─────────────────────────────────────────────────────────────────────────────


class TestJiraNormalizePriorityMap:
    """Verify Jira priority → URIP severity mapping."""

    @pytest.mark.parametrize("jira_priority,expected_severity", [
        ("Highest", "critical"),
        ("High",    "high"),
        ("Medium",  "medium"),
        ("Low",     "low"),
        ("Lowest",  "low"),
        ("HIGHEST", "critical"),   # case-insensitive
        ("HIGH",    "high"),
        (None,      "medium"),     # unknown → medium default
        ("",        "medium"),
        ("Unknown", "medium"),
    ])
    def test_normalize_priority_map(
        self,
        connector: JiraConnector,
        jira_priority: str | None,
        expected_severity: str,
    ) -> None:
        issue = _jira_issue(priority=jira_priority or "")
        # For None priority, remove the field
        if jira_priority is None:
            issue["fields"]["priority"] = None
        raw = _raw_finding(issue)
        # We need base_url set for normalize to build source_url
        connector._base_url = BASE
        record = connector.normalize(raw)
        assert record.severity == expected_severity, (
            f"Jira priority {jira_priority!r} should map to {expected_severity!r}, "
            f"got {record.severity!r}"
        )


# ─────────────────────────────────────────────────────────────────────────────
# 3. Authentication — Basic (Cloud)
# ─────────────────────────────────────────────────────────────────────────────


class TestJiraAuthenticateBasic:
    @respx.mock
    def test_authenticate_basic_success(
        self, connector: JiraConnector, basic_creds: dict
    ) -> None:
        """Basic auth should set Authorization: Basic base64(email:token) header."""
        route = respx.get(f"{BASE}/rest/api/3/myself").mock(
            return_value=httpx.Response(200, json=_myself_response())
        )
        session = connector.authenticate(basic_creds)

        assert isinstance(session, ConnectorSession)
        assert session.connector_name == "jira"
        assert session.tenant_id == "tenant-jira"
        assert "jira-basic" in session.token
        assert route.called

        # Verify Basic header was generated correctly.
        sent_request = route.calls[0].request
        auth_header = sent_request.headers.get("authorization", "")
        assert auth_header.startswith("Basic "), (
            f"Expected 'Basic …' header, got {auth_header!r}"
        )
        decoded = base64.b64decode(auth_header[6:]).decode()
        assert decoded == f"{basic_creds['email']}:{basic_creds['api_token']}"

    @respx.mock
    def test_authenticate_basic_401_raises(
        self, connector: JiraConnector, basic_creds: dict
    ) -> None:
        respx.get(f"{BASE}/rest/api/3/myself").mock(
            return_value=httpx.Response(401, json={"errorMessages": ["Unauthorized"]})
        )
        with pytest.raises(ConnectorAuthError):
            connector.authenticate(basic_creds)

    def test_authenticate_basic_missing_email_raises(
        self, connector: JiraConnector
    ) -> None:
        creds = {
            "base_url": BASE,
            "auth_method": "basic",
            "api_token": "tok",
            "default_project_key": "SEC",
            "risk_jql": "project = SEC",
        }
        with pytest.raises(ConnectorAuthError, match="email"):
            connector.authenticate(creds)

    def test_authenticate_missing_base_url_raises(
        self, connector: JiraConnector
    ) -> None:
        with pytest.raises(ConnectorAuthError, match="base_url"):
            connector.authenticate({"auth_method": "basic"})

    def test_authenticate_unsupported_auth_method_raises(
        self, connector: JiraConnector
    ) -> None:
        with pytest.raises(ConnectorAuthError, match="Unsupported"):
            connector.authenticate({
                "base_url": BASE,
                "auth_method": "oauth",
                "default_project_key": "SEC",
                "risk_jql": "project = SEC",
            })


# ─────────────────────────────────────────────────────────────────────────────
# 4. Authentication — Bearer (DC/Server)
# ─────────────────────────────────────────────────────────────────────────────


class TestJiraAuthenticateBearer:
    @respx.mock
    def test_authenticate_bearer_success(
        self, connector: JiraConnector, bearer_creds: dict
    ) -> None:
        """Bearer auth should set Authorization: Bearer <PAT> header."""
        route = respx.get(f"{DC_BASE}/rest/api/3/myself").mock(
            return_value=httpx.Response(200, json=_myself_response("dc-user"))
        )
        session = connector.authenticate(bearer_creds)

        assert isinstance(session, ConnectorSession)
        assert "jira-bearer" in session.token
        assert route.called

        # Verify Bearer header.
        sent_request = route.calls[0].request
        auth_header = sent_request.headers.get("authorization", "")
        assert auth_header == f"Bearer {bearer_creds['bearer_token']}", (
            f"Expected Bearer header, got {auth_header!r}"
        )

    @respx.mock
    def test_authenticate_bearer_403_raises(
        self, connector: JiraConnector, bearer_creds: dict
    ) -> None:
        respx.get(f"{DC_BASE}/rest/api/3/myself").mock(
            return_value=httpx.Response(403, json={"errorMessages": ["Forbidden"]})
        )
        with pytest.raises(ConnectorAuthError):
            connector.authenticate(bearer_creds)

    def test_authenticate_bearer_missing_token_raises(
        self, connector: JiraConnector
    ) -> None:
        with pytest.raises(ConnectorAuthError, match="bearer_token"):
            connector.authenticate({
                "base_url": DC_BASE,
                "auth_method": "bearer",
                "default_project_key": "SEC",
                "risk_jql": "project = SEC",
            })


# ─────────────────────────────────────────────────────────────────────────────
# 5. fetch_findings — verifies JQL is passed
# ─────────────────────────────────────────────────────────────────────────────


class TestJiraFetchFindings:
    @respx.mock
    def test_fetch_findings_uses_jql(
        self, connector: JiraConnector, basic_creds: dict
    ) -> None:
        """fetch_findings must POST to /rest/api/3/search with the configured JQL."""
        respx.get(f"{BASE}/rest/api/3/myself").mock(
            return_value=httpx.Response(200, json=_myself_response())
        )
        search_route = respx.post(f"{BASE}/rest/api/3/search").mock(
            return_value=httpx.Response(
                200,
                json=_search_response([_jira_issue("SEC-1"), _jira_issue("SEC-2")]),
            )
        )

        connector.authenticate(basic_creds)
        findings = connector.fetch_findings(
            since=datetime(2026, 1, 1, tzinfo=timezone.utc),
            tenant_id="tenant-jira",
        )

        assert len(findings) == 2
        assert findings[0].source == "jira"
        assert findings[0].tenant_id == "tenant-jira"
        assert search_route.called

        # Verify JQL sent in the body.
        import json
        sent_body = json.loads(search_route.calls[0].request.content)
        assert sent_body["jql"] == basic_creds["risk_jql"]

    @respx.mock
    def test_fetch_findings_empty(
        self, connector: JiraConnector, basic_creds: dict
    ) -> None:
        respx.get(f"{BASE}/rest/api/3/myself").mock(
            return_value=httpx.Response(200, json=_myself_response())
        )
        respx.post(f"{BASE}/rest/api/3/search").mock(
            return_value=httpx.Response(200, json=_search_response([]))
        )
        connector.authenticate(basic_creds)
        findings = connector.fetch_findings(since=datetime.now(timezone.utc))
        assert findings == []

    def test_fetch_findings_not_authenticated_raises(
        self, connector: JiraConnector
    ) -> None:
        with pytest.raises(ConnectorFetchError, match="not authenticated"):
            connector.fetch_findings(since=datetime.now(timezone.utc))

    @respx.mock
    def test_fetch_findings_5xx_raises(
        self, connector: JiraConnector, basic_creds: dict
    ) -> None:
        respx.get(f"{BASE}/rest/api/3/myself").mock(
            return_value=httpx.Response(200, json=_myself_response())
        )
        respx.post(f"{BASE}/rest/api/3/search").mock(
            return_value=httpx.Response(503, text="Service Unavailable")
        )
        connector.authenticate(basic_creds)
        with pytest.raises(ConnectorFetchError):
            connector.fetch_findings(since=datetime.now(timezone.utc))


# ─────────────────────────────────────────────────────────────────────────────
# 6. Normalization
# ─────────────────────────────────────────────────────────────────────────────


class TestJiraNormalize:
    def test_normalize_returns_urip_risk_record(
        self, connector: JiraConnector
    ) -> None:
        connector._base_url = BASE
        raw = _raw_finding(_jira_issue("SEC-42", "SQL injection in API", "Highest", "Open"))
        record = connector.normalize(raw)
        assert isinstance(record, URIPRiskRecord)
        assert record.source == "jira"
        assert record.domain == "application"
        assert record.severity == "critical"
        assert "SEC-42" in record.finding or "SQL injection" in record.finding
        assert record.owner_team == "IT Service Management"

    def test_normalize_source_url_in_description(
        self, connector: JiraConnector
    ) -> None:
        connector._base_url = BASE
        raw = _raw_finding(_jira_issue("SEC-5"))
        record = connector.normalize(raw)
        assert f"{BASE}/browse/SEC-5" in record.description

    def test_normalize_adf_description_extracted(
        self, connector: JiraConnector
    ) -> None:
        connector._base_url = BASE
        issue = _jira_issue("SEC-10")
        issue["fields"]["description"] = {
            "version": 1,
            "type": "doc",
            "content": [
                {"type": "paragraph", "content": [
                    {"type": "text", "text": "Detailed description here."}
                ]}
            ],
        }
        raw = _raw_finding(issue)
        record = connector.normalize(raw)
        assert "Detailed description here" in (record.description or "")


# ─────────────────────────────────────────────────────────────────────────────
# 7. create_ticket — payload shape
# ─────────────────────────────────────────────────────────────────────────────


class TestJiraCreateTicket:
    @respx.mock
    def test_create_ticket_payload_shape(
        self, connector: JiraConnector, basic_creds: dict
    ) -> None:
        """POST body to /rest/api/3/issue must have summary + ADF description + priority."""
        import json

        respx.get(f"{BASE}/rest/api/3/myself").mock(
            return_value=httpx.Response(200, json=_myself_response())
        )
        create_route = respx.post(f"{BASE}/rest/api/3/issue").mock(
            return_value=httpx.Response(
                201,
                json={"id": "10099", "key": "SEC-99", "self": f"{BASE}/rest/api/3/issue/10099"},
            )
        )

        connector.authenticate(basic_creds)
        risk = URIPRiskRecord(
            finding="Exposed S3 bucket with public read access",
            source="jira",
            domain="cloud",
            cvss_score=7.5,
            severity="high",
            asset="s3://acme-data-bucket",
            owner_team="Cloud Security",
        )
        result = connector.create_ticket(session=None, risk=risk)

        assert result["key"] == "SEC-99"
        assert result["url"] == f"{BASE}/browse/SEC-99"
        assert create_route.called

        body = json.loads(create_route.calls[0].request.content)
        fields = body["fields"]

        # summary must be present
        assert fields["summary"] == risk.finding

        # description must be ADF format (has "type": "doc")
        desc = fields["description"]
        assert isinstance(desc, dict), "description must be ADF dict"
        assert desc.get("type") == "doc"
        assert desc.get("version") == 1

        # priority must be set
        assert "priority" in fields
        assert fields["priority"]["name"] == "High"

    @respx.mock
    def test_create_ticket_critical_maps_highest(
        self, connector: JiraConnector, basic_creds: dict
    ) -> None:
        import json

        respx.get(f"{BASE}/rest/api/3/myself").mock(
            return_value=httpx.Response(200, json=_myself_response())
        )
        create_route = respx.post(f"{BASE}/rest/api/3/issue").mock(
            return_value=httpx.Response(
                201, json={"id": "10100", "key": "SEC-100", "self": f"{BASE}/…"}
            )
        )

        connector.authenticate(basic_creds)
        risk = URIPRiskRecord(
            finding="Critical vulnerability",
            source="jira",
            domain="application",
            cvss_score=9.8,
            severity="critical",
            asset="web-app",
            owner_team="AppSec",
        )
        connector.create_ticket(session=None, risk=risk)

        body = json.loads(create_route.calls[0].request.content)
        assert body["fields"]["priority"]["name"] == "Highest"

    def test_create_ticket_not_authenticated_raises(
        self, connector: JiraConnector
    ) -> None:
        risk = URIPRiskRecord(
            finding="Test",
            source="jira",
            domain="application",
            cvss_score=0.0,
            severity="medium",
            asset="x",
            owner_team="y",
        )
        with pytest.raises(ConnectorFetchError, match="not authenticated"):
            connector.create_ticket(session=None, risk=risk)


# ─────────────────────────────────────────────────────────────────────────────
# 8. health_check — ok and degraded
# ─────────────────────────────────────────────────────────────────────────────


class TestJiraHealthCheck:
    def test_health_check_ok_before_authenticate(
        self, connector: JiraConnector
    ) -> None:
        """Fresh connector (not authenticated) should return ok with error_count=0."""
        health = connector.health_check()
        assert isinstance(health, ConnectorHealth)
        assert health.connector_name == "jira"
        assert health.status == "ok"
        assert health.error_count == 0
        assert health.last_run is None

    @respx.mock
    def test_health_check_ok_after_authenticate(
        self, connector: JiraConnector, basic_creds: dict
    ) -> None:
        respx.get(f"{BASE}/rest/api/3/myself").mock(
            return_value=httpx.Response(200, json=_myself_response())
        ).mock(  # second call from health_check()
            return_value=httpx.Response(200, json=_myself_response())
        )
        connector.authenticate(basic_creds)
        health = connector.health_check()
        assert health.status == "ok"

    @respx.mock
    def test_health_check_fail_returns_degraded(
        self, connector: JiraConnector, basic_creds: dict
    ) -> None:
        """health_check() should NOT raise — returns degraded ConnectorHealth instead."""
        # First call (from authenticate) succeeds; second call (from health_check) fails.
        respx.get(f"{BASE}/rest/api/3/myself").mock(
            side_effect=[
                httpx.Response(200, json=_myself_response()),
                httpx.Response(503, text="Service Unavailable"),
            ]
        )
        connector.authenticate(basic_creds)
        health = connector.health_check()
        assert health.status in ("degraded", "error")
        assert health.last_error is not None


# ─────────────────────────────────────────────────────────────────────────────
# 9. ADF utilities
# ─────────────────────────────────────────────────────────────────────────────


class TestADFHelpers:
    def test_plain_text_to_adf_structure(self) -> None:
        adf = _plain_text_to_adf("Hello world")
        assert adf["type"] == "doc"
        assert adf["version"] == 1
        content = adf["content"]
        assert len(content) >= 1
        para = content[0]
        assert para["type"] == "paragraph"
        # text node present
        texts = [n["text"] for n in para["content"] if n.get("type") == "text"]
        assert "Hello world" in texts

    def test_plain_text_to_adf_empty(self) -> None:
        adf = _plain_text_to_adf("")
        assert adf["type"] == "doc"
        # should not raise

    def test_plain_text_to_adf_multiline(self) -> None:
        adf = _plain_text_to_adf("Line one\nLine two")
        # should contain hardBreak node
        para_content = adf["content"][0]["content"]
        node_types = [n["type"] for n in para_content]
        assert "hardBreak" in node_types

    def test_extract_adf_text(self) -> None:
        adf = {
            "version": 1,
            "type": "doc",
            "content": [
                {
                    "type": "paragraph",
                    "content": [
                        {"type": "text", "text": "Hello"},
                        {"type": "hardBreak"},
                        {"type": "text", "text": "World"},
                    ],
                }
            ],
        }
        result = _extract_adf_text(adf)
        assert "Hello" in result
        assert "World" in result

    def test_extract_adf_text_empty(self) -> None:
        result = _extract_adf_text({})
        assert result == ""
