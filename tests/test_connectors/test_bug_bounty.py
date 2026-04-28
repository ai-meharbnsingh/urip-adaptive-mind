"""
TDD tests for the Bug Bounty connector (HackerOne + Bugcrowd).

Uses respx to mock all HTTP traffic — no real API calls.
Coverage: authentication per platform, fetch reports, severity mapping,
webhook ingest, normalization, health check, error handling.
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
from connectors.bug_bounty.connector import BugBountyConnector


# ─────────────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture
def connector() -> BugBountyConnector:
    return BugBountyConnector()


@pytest.fixture
def hackerone_credentials() -> dict[str, Any]:
    return {
        "platform": "hackerone",
        "api_token": "h1-api-token-123",
        "program_handle": "acme-corp",
        "tenant_id": "tenant-bb",
    }


@pytest.fixture
def bugcrowd_credentials() -> dict[str, Any]:
    return {
        "platform": "bugcrowd",
        "api_token": "bc-api-token-456",
        "tenant_id": "tenant-bb",
    }


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _mock_h1_report(
    report_id: str = "h1-1234",
    severity: str = "critical",
    state: str = "triaged",
) -> dict[str, Any]:
    return {
        "id": report_id,
        "attributes": {
            "title": f"H1 Report {report_id}",
            "state": state,
            "severity": {"rating": severity},
            "weakness": {"name": "SQL Injection"},
            "vulnerability_types": [{"name": "sql_injection"}],
            "structured_scope": {"asset_type": "URL", "asset_identifier": "https://app.example.com"},
            "disclosed_at": None,
            "bounty_awarded_at": None,
        },
    }


def _mock_bc_report(
    report_id: str = "bc-5678",
    severity: int = 2,
    state: str = "triaged",
) -> dict[str, Any]:
    return {
        "id": report_id,
        "attributes": {
            "title": f"BC Report {report_id}",
            "state": state,
            "priority": severity,
            "vrt_lineage": ["web_application", "sql_injection"],
            "target": {"name": "https://api.example.com"},
            "submitted": "2024-06-15T10:00:00.000Z",
            "remediation_recommendation": "Use parameterized queries",
        },
    }


# ─────────────────────────────────────────────────────────────────────────────
# Tests: Authentication
# ─────────────────────────────────────────────────────────────────────────────

class TestBugBountyAuthentication:
    @respx.mock
    def test_authenticate_hackerone_success(self, connector: BugBountyConnector, hackerone_credentials: dict):
        route = respx.get("https://api.hackerone.com/v1/me").mock(
            return_value=httpx.Response(200, json={"data": {"id": "me"}})
        )
        session = connector.authenticate(hackerone_credentials)
        assert isinstance(session, ConnectorSession)
        assert session.connector_name == "bug_bounty"
        assert "hackerone" in session.token
        assert route.called

    @respx.mock
    def test_authenticate_hackerone_failure(self, connector: BugBountyConnector, hackerone_credentials: dict):
        respx.get("https://api.hackerone.com/v1/me").mock(
            return_value=httpx.Response(401, text='Unauthorized')
        )
        with pytest.raises(ConnectorAuthError):
            connector.authenticate(hackerone_credentials)

    @respx.mock
    def test_authenticate_bugcrowd_success(self, connector: BugBountyConnector, bugcrowd_credentials: dict):
        route = respx.get("https://api.bugcrowd.com/user").mock(
            return_value=httpx.Response(200, json={"user": {"uuid": "user-123"}})
        )
        session = connector.authenticate(bugcrowd_credentials)
        assert isinstance(session, ConnectorSession)
        assert "bugcrowd" in session.token
        assert route.called

    @respx.mock
    def test_authenticate_bugcrowd_failure(self, connector: BugBountyConnector, bugcrowd_credentials: dict):
        respx.get("https://api.bugcrowd.com/user").mock(
            return_value=httpx.Response(401, text='Unauthorized')
        )
        with pytest.raises(ConnectorAuthError):
            connector.authenticate(bugcrowd_credentials)

    def test_authenticate_unknown_platform(self, connector: BugBountyConnector):
        with pytest.raises(ConnectorAuthError):
            connector.authenticate({"platform": "unknown"})

    def test_authenticate_missing_platform(self, connector: BugBountyConnector):
        with pytest.raises(ConnectorAuthError):
            connector.authenticate({})


# ─────────────────────────────────────────────────────────────────────────────
# Tests: fetch_findings HackerOne
# ─────────────────────────────────────────────────────────────────────────────

class TestBugBountyFetchHackerOne:
    @respx.mock
    def test_fetch_hackerone_success(self, connector: BugBountyConnector, hackerone_credentials: dict):
        respx.get("https://api.hackerone.com/v1/me").mock(
            return_value=httpx.Response(200, json={"data": {"id": "me"}})
        )
        connector.authenticate(hackerone_credentials)
        respx.get("https://api.hackerone.com/v1/reports").mock(
            return_value=httpx.Response(200, json={
                "data": [_mock_h1_report(report_id="h1-001", severity="critical")]
            })
        )
        since = datetime(2024, 6, 1, tzinfo=timezone.utc)
        findings = connector.fetch_findings(since, tenant_id="tenant-bb")
        assert len(findings) == 1
        assert findings[0].id == "h1-001"
        assert findings[0].raw_data.get("platform") == "hackerone"

    @respx.mock
    def test_fetch_hackerone_empty(self, connector: BugBountyConnector, hackerone_credentials: dict):
        respx.get("https://api.hackerone.com/v1/me").mock(
            return_value=httpx.Response(200, json={"data": {"id": "me"}})
        )
        connector.authenticate(hackerone_credentials)
        respx.get("https://api.hackerone.com/v1/reports").mock(
            return_value=httpx.Response(200, json={"data": []})
        )
        since = datetime(2024, 6, 1, tzinfo=timezone.utc)
        findings = connector.fetch_findings(since, tenant_id="tenant-bb")
        assert findings == []

    @respx.mock
    def test_fetch_hackerone_program_filter(self, connector: BugBountyConnector, hackerone_credentials: dict):
        respx.get("https://api.hackerone.com/v1/me").mock(
            return_value=httpx.Response(200, json={"data": {"id": "me"}})
        )
        connector.authenticate(hackerone_credentials)
        route = respx.get("https://api.hackerone.com/v1/reports").mock(
            return_value=httpx.Response(200, json={"data": []})
        )
        since = datetime(2024, 6, 1, tzinfo=timezone.utc)
        connector.fetch_findings(since, tenant_id="tenant-bb")
        req = route.calls[0].request
        assert "program_handle%5B%5D=acme-corp" in str(req.url) or "program_handle[]=acme-corp" in str(req.url)


# ─────────────────────────────────────────────────────────────────────────────
# Tests: fetch_findings Bugcrowd
# ─────────────────────────────────────────────────────────────────────────────

class TestBugBountyFetchBugcrowd:
    @respx.mock
    def test_fetch_bugcrowd_success(self, connector: BugBountyConnector, bugcrowd_credentials: dict):
        respx.get("https://api.bugcrowd.com/user").mock(
            return_value=httpx.Response(200, json={"user": {"uuid": "user-123"}})
        )
        connector.authenticate(bugcrowd_credentials)
        respx.get("https://api.bugcrowd.com/submissions").mock(
            return_value=httpx.Response(200, json={
                "submissions": [_mock_bc_report(report_id="bc-001", severity=1)]
            })
        )
        since = datetime(2024, 6, 1, tzinfo=timezone.utc)
        findings = connector.fetch_findings(since, tenant_id="tenant-bb")
        assert len(findings) == 1
        assert findings[0].id == "bc-001"
        assert findings[0].raw_data.get("platform") == "bugcrowd"

    @respx.mock
    def test_fetch_bugcrowd_empty(self, connector: BugBountyConnector, bugcrowd_credentials: dict):
        respx.get("https://api.bugcrowd.com/user").mock(
            return_value=httpx.Response(200, json={"user": {"uuid": "user-123"}})
        )
        connector.authenticate(bugcrowd_credentials)
        respx.get("https://api.bugcrowd.com/submissions").mock(
            return_value=httpx.Response(200, json={"submissions": []})
        )
        since = datetime(2024, 6, 1, tzinfo=timezone.utc)
        findings = connector.fetch_findings(since, tenant_id="tenant-bb")
        assert findings == []


# ─────────────────────────────────────────────────────────────────────────────
# Tests: Severity mapping
# ─────────────────────────────────────────────────────────────────────────────

class TestBugBountySeverityMapping:
    def test_hackerone_critical(self, connector: BugBountyConnector):
        raw = RawFinding(
            id="h1-crit",
            source="bug_bounty",
            raw_data={"platform": "hackerone", **_mock_h1_report(severity="critical")},
            fetched_at=datetime.now(timezone.utc),
            tenant_id="tenant-bb",
        )
        record = connector.normalize(raw)
        assert record.severity == "critical"
        assert record.cvss_score == 9.0

    def test_hackerone_high(self, connector: BugBountyConnector):
        raw = RawFinding(
            id="h1-high",
            source="bug_bounty",
            raw_data={"platform": "hackerone", **_mock_h1_report(severity="high")},
            fetched_at=datetime.now(timezone.utc),
            tenant_id="tenant-bb",
        )
        record = connector.normalize(raw)
        assert record.severity == "high"
        assert record.cvss_score == 7.0

    def test_hackerone_medium(self, connector: BugBountyConnector):
        raw = RawFinding(
            id="h1-med",
            source="bug_bounty",
            raw_data={"platform": "hackerone", **_mock_h1_report(severity="medium")},
            fetched_at=datetime.now(timezone.utc),
            tenant_id="tenant-bb",
        )
        record = connector.normalize(raw)
        assert record.severity == "medium"
        assert record.cvss_score == 5.0

    def test_hackerone_low(self, connector: BugBountyConnector):
        raw = RawFinding(
            id="h1-low",
            source="bug_bounty",
            raw_data={"platform": "hackerone", **_mock_h1_report(severity="low")},
            fetched_at=datetime.now(timezone.utc),
            tenant_id="tenant-bb",
        )
        record = connector.normalize(raw)
        assert record.severity == "low"
        assert record.cvss_score == 3.0

    def test_bugcrowd_p1_critical(self, connector: BugBountyConnector):
        raw = RawFinding(
            id="bc-p1",
            source="bug_bounty",
            raw_data={"platform": "bugcrowd", **_mock_bc_report(severity=1)},
            fetched_at=datetime.now(timezone.utc),
            tenant_id="tenant-bb",
        )
        record = connector.normalize(raw)
        assert record.severity == "critical"
        assert record.cvss_score == 9.0

    def test_bugcrowd_p2_high(self, connector: BugBountyConnector):
        raw = RawFinding(
            id="bc-p2",
            source="bug_bounty",
            raw_data={"platform": "bugcrowd", **_mock_bc_report(severity=2)},
            fetched_at=datetime.now(timezone.utc),
            tenant_id="tenant-bb",
        )
        record = connector.normalize(raw)
        assert record.severity == "high"
        assert record.cvss_score == 7.0

    def test_bugcrowd_p3_medium(self, connector: BugBountyConnector):
        raw = RawFinding(
            id="bc-p3",
            source="bug_bounty",
            raw_data={"platform": "bugcrowd", **_mock_bc_report(severity=3)},
            fetched_at=datetime.now(timezone.utc),
            tenant_id="tenant-bb",
        )
        record = connector.normalize(raw)
        assert record.severity == "medium"
        assert record.cvss_score == 5.0

    def test_bugcrowd_p4_low(self, connector: BugBountyConnector):
        raw = RawFinding(
            id="bc-p4",
            source="bug_bounty",
            raw_data={"platform": "bugcrowd", **_mock_bc_report(severity=4)},
            fetched_at=datetime.now(timezone.utc),
            tenant_id="tenant-bb",
        )
        record = connector.normalize(raw)
        assert record.severity == "low"
        assert record.cvss_score == 3.0


# ─────────────────────────────────────────────────────────────────────────────
# Tests: Webhook ingest
# ─────────────────────────────────────────────────────────────────────────────

class TestBugBountyWebhook:
    def test_webhook_ingest_hackerone(self, connector: BugBountyConnector):
        payload = {
            "platform": "hackerone",
            "report": _mock_h1_report(report_id="h1-webhook-001", severity="high"),
        }
        record = connector.ingest_webhook(payload, tenant_id="tenant-bb")
        assert isinstance(record, URIPRiskRecord)
        assert record.source == "bug_bounty:hackerone"
        assert record.severity == "high"
        assert record.finding == "H1 Report h1-webhook-001"

    def test_webhook_ingest_bugcrowd(self, connector: BugBountyConnector):
        payload = {
            "platform": "bugcrowd",
            "report": _mock_bc_report(report_id="bc-webhook-001", severity=2),
        }
        record = connector.ingest_webhook(payload, tenant_id="tenant-bb")
        assert isinstance(record, URIPRiskRecord)
        assert record.source == "bug_bounty:bugcrowd"
        assert record.severity == "high"

    def test_webhook_ingest_unknown_platform(self, connector: BugBountyConnector):
        with pytest.raises(ConnectorFetchError):
            connector.ingest_webhook({"platform": "unknown", "report": {}}, tenant_id="tenant-bb")

    def test_webhook_includes_remediation(self, connector: BugBountyConnector):
        payload = {
            "platform": "bugcrowd",
            "report": _mock_bc_report(report_id="bc-webhook-002", severity=1),
        }
        record = connector.ingest_webhook(payload, tenant_id="tenant-bb")
        assert "Use parameterized queries" in (record.description or "")


# ─────────────────────────────────────────────────────────────────────────────
# Tests: Normalization misc
# ─────────────────────────────────────────────────────────────────────────────

class TestBugBountyNormalize:
    def test_normalize_hackerone_asset(self, connector: BugBountyConnector):
        raw = RawFinding(
            id="h1-asset",
            source="bug_bounty",
            raw_data={"platform": "hackerone", **_mock_h1_report()},
            fetched_at=datetime.now(timezone.utc),
            tenant_id="tenant-bb",
        )
        record = connector.normalize(raw)
        assert record.asset == "https://app.example.com"
        assert record.owner_team == "Bug Bounty"

    def test_normalize_bugcrowd_asset(self, connector: BugBountyConnector):
        raw = RawFinding(
            id="bc-asset",
            source="bug_bounty",
            raw_data={"platform": "bugcrowd", **_mock_bc_report()},
            fetched_at=datetime.now(timezone.utc),
            tenant_id="tenant-bb",
        )
        record = connector.normalize(raw)
        assert record.asset == "https://api.example.com"


# ─────────────────────────────────────────────────────────────────────────────
# Tests: Error handling
# ─────────────────────────────────────────────────────────────────────────────

class TestBugBountyErrors:
    def test_fetch_without_authenticate(self, connector: BugBountyConnector):
        since = datetime(2024, 6, 1, tzinfo=timezone.utc)
        with pytest.raises(ConnectorFetchError):
            connector.fetch_findings(since, tenant_id="tenant-bb")

    @respx.mock
    def test_fetch_hackerone_http_error(self, connector: BugBountyConnector, hackerone_credentials: dict):
        respx.get("https://api.hackerone.com/v1/me").mock(
            return_value=httpx.Response(200, json={"data": {"id": "me"}})
        )
        connector.authenticate(hackerone_credentials)
        respx.get("https://api.hackerone.com/v1/reports").mock(
            return_value=httpx.Response(500, text="Internal Server Error")
        )
        since = datetime(2024, 6, 1, tzinfo=timezone.utc)
        with pytest.raises(ConnectorFetchError):
            connector.fetch_findings(since, tenant_id="tenant-bb")


# ─────────────────────────────────────────────────────────────────────────────
# Tests: Health check
# ─────────────────────────────────────────────────────────────────────────────

class TestBugBountyHealthCheck:
    def test_health_check_ok(self, connector: BugBountyConnector):
        health = connector.health_check()
        assert isinstance(health, ConnectorHealth)
        assert health.connector_name == "bug_bounty"
        assert health.status == "ok"

    @respx.mock
    def test_health_check_degraded_after_errors(self, connector: BugBountyConnector, hackerone_credentials: dict):
        respx.get("https://api.hackerone.com/v1/me").mock(
            return_value=httpx.Response(200, json={"data": {"id": "me"}})
        )
        connector.authenticate(hackerone_credentials)
        respx.get("https://api.hackerone.com/v1/reports").mock(
            return_value=httpx.Response(500, text="Error")
        )
        since = datetime(2024, 6, 1, tzinfo=timezone.utc)
        for _ in range(3):
            try:
                connector.fetch_findings(since, tenant_id="tenant-bb")
            except Exception:
                pass
        health = connector.health_check()
        assert health.status == "degraded"
        assert health.error_count == 3
