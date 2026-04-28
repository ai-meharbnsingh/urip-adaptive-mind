"""
TDD tests for the Microsoft 365 Collaboration live connector.

Uses respx to mock all HTTP traffic — no real API calls.
Coverage: authentication (OAuth2), fetch_findings (sharepoint, onedrive, teams),
normalization, error handling, tenant isolation, health check, pagination.
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
from connectors.m365_collab.connector import M365CollabConnector


# ─────────────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture
def connector() -> M365CollabConnector:
    return M365CollabConnector()


@pytest.fixture
def valid_credentials() -> dict[str, str]:
    return {
        "tenant_id": "test-tenant-id",
        "client_id": "TEST_CLIENT_ID",
        "client_secret": "TEST_CLIENT_SECRET",
    }


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

TOKEN_URL = "https://login.microsoftonline.com/test-tenant-id/oauth2/v2.0/token"
GRAPH_BASE = "https://graph.microsoft.com/v1.0"


def _mock_token():
    return respx.post(TOKEN_URL).mock(
        return_value=httpx.Response(
            200,
            json={
                "token_type": "Bearer",
                "expires_in": 3599,
                "access_token": "FAKE_GRAPH_TOKEN",
            },
        )
    )


def _mock_sharepoint_site() -> dict[str, Any]:
    return {
        "id": "site-001",
        "name": "HR Portal",
        "webUrl": "https://contoso.sharepoint.com/sites/hr",
        "displayName": "HR Portal",
        "isPersonalSite": False,
    }


def _mock_user() -> dict[str, Any]:
    return {
        "id": "user-001",
        "displayName": "Alice Smith",
        "userPrincipalName": "alice@contoso.com",
        "mail": "alice@contoso.com",
    }


def _mock_team(visibility: str = "public") -> dict[str, Any]:
    return {
        "id": "team-001",
        "displayName": "Engineering",
        "description": "Engineering team",
        "visibility": visibility,
        "isArchived": False,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Tests: Authentication
# ─────────────────────────────────────────────────────────────────────────────

class TestM365CollabAuthentication:
    @respx.mock
    def test_authenticate_success(self, connector: M365CollabConnector, valid_credentials: dict):
        route = _mock_token()
        session = connector.authenticate(valid_credentials)
        assert isinstance(session, ConnectorSession)
        assert session.connector_name == "m365_collab"
        assert session.tenant_id == "test-tenant-id"
        assert route.called

    @respx.mock
    def test_authenticate_failure_invalid_creds(self, connector: M365CollabConnector):
        respx.post(TOKEN_URL).mock(
            return_value=httpx.Response(401, json={"error": "Unauthorized"})
        )
        with pytest.raises(ConnectorAuthError):
            connector.authenticate(
                {
                    "tenant_id": "test-tenant-id",
                    "client_id": "bad",
                    "client_secret": "bad",
                }
            )

    def test_authenticate_failure_missing_tenant_id(self, connector: M365CollabConnector):
        with pytest.raises(ConnectorAuthError):
            connector.authenticate({"client_id": "c", "client_secret": "s"})

    def test_authenticate_failure_missing_client_id(self, connector: M365CollabConnector):
        with pytest.raises(ConnectorAuthError):
            connector.authenticate({"tenant_id": "t", "client_secret": "s"})

    def test_authenticate_failure_missing_client_secret(self, connector: M365CollabConnector):
        with pytest.raises(ConnectorAuthError):
            connector.authenticate({"tenant_id": "t", "client_id": "c"})


# ─────────────────────────────────────────────────────────────────────────────
# Tests: Fetch findings
# ─────────────────────────────────────────────────────────────────────────────

class TestM365CollabFetchFindings:
    @respx.mock
    def test_fetch_findings_empty(self, connector: M365CollabConnector, valid_credentials: dict):
        _mock_token()
        respx.get(f"{GRAPH_BASE}/sites").mock(return_value=httpx.Response(200, json={"value": []}))
        respx.get(f"{GRAPH_BASE}/users").mock(return_value=httpx.Response(200, json={"value": []}))
        respx.get(f"{GRAPH_BASE}/teams").mock(return_value=httpx.Response(200, json={"value": []}))
        connector.authenticate(valid_credentials)
        findings = connector.fetch_findings(
            since=datetime(2024, 1, 1, tzinfo=timezone.utc),
            tenant_id="test-tenant-id",
        )
        assert findings == []

    @respx.mock
    def test_fetch_findings_sharepoint(self, connector: M365CollabConnector, valid_credentials: dict):
        _mock_token()
        respx.get(f"{GRAPH_BASE}/sites").mock(
            return_value=httpx.Response(200, json={"value": [_mock_sharepoint_site()]})
        )
        respx.get(f"{GRAPH_BASE}/users").mock(return_value=httpx.Response(200, json={"value": []}))
        respx.get(f"{GRAPH_BASE}/teams").mock(return_value=httpx.Response(200, json={"value": []}))
        connector.authenticate(valid_credentials)
        findings = connector.fetch_findings(
            since=datetime(2024, 1, 1, tzinfo=timezone.utc),
            tenant_id="test-tenant-id",
        )
        assert len(findings) == 1
        assert findings[0].raw_data["category"] == "sharepoint"

    @respx.mock
    def test_fetch_findings_onedrive(self, connector: M365CollabConnector, valid_credentials: dict):
        _mock_token()
        respx.get(f"{GRAPH_BASE}/sites").mock(return_value=httpx.Response(200, json={"value": []}))
        respx.get(f"{GRAPH_BASE}/users").mock(
            return_value=httpx.Response(200, json={"value": [_mock_user()]})
        )
        respx.get(f"{GRAPH_BASE}/teams").mock(return_value=httpx.Response(200, json={"value": []}))
        connector.authenticate(valid_credentials)
        findings = connector.fetch_findings(
            since=datetime(2024, 1, 1, tzinfo=timezone.utc),
            tenant_id="test-tenant-id",
        )
        assert len(findings) == 1
        assert findings[0].raw_data["category"] == "onedrive"

    @respx.mock
    def test_fetch_findings_teams(self, connector: M365CollabConnector, valid_credentials: dict):
        _mock_token()
        respx.get(f"{GRAPH_BASE}/sites").mock(return_value=httpx.Response(200, json={"value": []}))
        respx.get(f"{GRAPH_BASE}/users").mock(return_value=httpx.Response(200, json={"value": []}))
        respx.get(f"{GRAPH_BASE}/teams").mock(
            return_value=httpx.Response(200, json={"value": [_mock_team("public")]})
        )
        connector.authenticate(valid_credentials)
        findings = connector.fetch_findings(
            since=datetime(2024, 1, 1, tzinfo=timezone.utc),
            tenant_id="test-tenant-id",
        )
        assert len(findings) == 1
        assert findings[0].raw_data["category"] == "teams"

    @respx.mock
    def test_fetch_findings_all_categories(self, connector: M365CollabConnector, valid_credentials: dict):
        _mock_token()
        respx.get(f"{GRAPH_BASE}/sites").mock(
            return_value=httpx.Response(200, json={"value": [_mock_sharepoint_site()]})
        )
        respx.get(f"{GRAPH_BASE}/users").mock(
            return_value=httpx.Response(200, json={"value": [_mock_user()]})
        )
        respx.get(f"{GRAPH_BASE}/teams").mock(
            return_value=httpx.Response(200, json={"value": [_mock_team("private")]})
        )
        connector.authenticate(valid_credentials)
        findings = connector.fetch_findings(
            since=datetime(2024, 1, 1, tzinfo=timezone.utc),
            tenant_id="test-tenant-id",
        )
        assert len(findings) == 3
        cats = {f.raw_data["category"] for f in findings}
        assert cats == {"sharepoint", "onedrive", "teams"}

    @respx.mock
    def test_fetch_findings_5xx_error(self, connector: M365CollabConnector, valid_credentials: dict):
        _mock_token()
        respx.get(f"{GRAPH_BASE}/sites").mock(
            return_value=httpx.Response(503, json={"error": "Service Unavailable"})
        )
        connector.authenticate(valid_credentials)
        with pytest.raises(ConnectorFetchError):
            connector.fetch_findings(
                since=datetime(2024, 1, 1, tzinfo=timezone.utc),
                tenant_id="test-tenant-id",
            )

    def test_fetch_findings_not_authenticated(self, connector: M365CollabConnector):
        with pytest.raises(ConnectorFetchError):
            connector.fetch_findings(since=datetime.now(timezone.utc))

    @respx.mock
    def test_fetch_pagination_via_odata_nextlink(self, connector: M365CollabConnector, valid_credentials: dict):
        _mock_token()
        call_count = 0

        def _handler(request: httpx.Request):
            nonlocal call_count
            call_count += 1
            skip = request.url.params.get("$skip")
            if skip is None:
                return httpx.Response(
                    200,
                    json={
                        "value": [_mock_sharepoint_site()],
                        "@odata.nextLink": f"{GRAPH_BASE}/sites?$skip=1",
                    },
                )
            return httpx.Response(200, json={"value": [_mock_sharepoint_site()]})

        respx.get(f"{GRAPH_BASE}/sites").mock(side_effect=_handler)
        respx.get(f"{GRAPH_BASE}/users").mock(return_value=httpx.Response(200, json={"value": []}))
        respx.get(f"{GRAPH_BASE}/teams").mock(return_value=httpx.Response(200, json={"value": []}))
        connector.authenticate(valid_credentials)
        findings = connector.fetch_findings(
            since=datetime(2024, 1, 1, tzinfo=timezone.utc),
            tenant_id="test-tenant-id",
        )
        # 2 sharepoint + 0 users + 0 teams = 2 findings
        assert len(findings) == 2
        assert call_count == 2


# ─────────────────────────────────────────────────────────────────────────────
# Tests: Normalization
# ─────────────────────────────────────────────────────────────────────────────

class TestM365CollabNormalize:
    def test_normalize_sharepoint(self, connector: M365CollabConnector):
        raw = RawFinding(
            id="site-001",
            source="m365_collab",
            raw_data={
                "id": "site-001",
                "name": "HR Portal",
                "webUrl": "https://contoso.sharepoint.com/sites/hr",
                "displayName": "HR Portal",
                "isPersonalSite": False,
                "category": "sharepoint",
            },
            fetched_at=datetime.now(timezone.utc),
            tenant_id="t1",
        )
        record = connector.normalize(raw)
        assert isinstance(record, URIPRiskRecord)
        assert record.finding == "SharePoint Site Exposure: HR Portal"
        assert record.severity == "high"
        assert record.asset == "https://contoso.sharepoint.com/sites/hr"
        assert record.source == "m365_collab:sharepoint"
        assert record.domain == "collaboration"
        assert record.owner_team == "IT"

    def test_normalize_onedrive(self, connector: M365CollabConnector):
        raw = RawFinding(
            id="user-001",
            source="m365_collab",
            raw_data={
                "id": "user-001",
                "displayName": "Alice Smith",
                "userPrincipalName": "alice@contoso.com",
                "mail": "alice@contoso.com",
                "category": "onedrive",
            },
            fetched_at=datetime.now(timezone.utc),
            tenant_id="t1",
        )
        record = connector.normalize(raw)
        assert isinstance(record, URIPRiskRecord)
        assert record.finding == "OneDrive External Sharing: Alice Smith"
        assert record.severity == "medium"
        assert record.asset == "alice@contoso.com"
        assert record.source == "m365_collab:onedrive"

    def test_normalize_teams_public(self, connector: M365CollabConnector):
        raw = RawFinding(
            id="team-001",
            source="m365_collab",
            raw_data={
                "id": "team-001",
                "displayName": "Engineering",
                "description": "Engineering team",
                "visibility": "public",
                "isArchived": False,
                "category": "teams",
            },
            fetched_at=datetime.now(timezone.utc),
            tenant_id="t1",
        )
        record = connector.normalize(raw)
        assert record.finding == "Public Teams Exposure: Engineering"
        assert record.severity == "high"
        assert record.asset == "Engineering"
        assert record.source == "m365_collab:teams"

    def test_normalize_teams_private(self, connector: M365CollabConnector):
        raw = RawFinding(
            id="team-002",
            source="m365_collab",
            raw_data={
                "id": "team-002",
                "displayName": "Finance",
                "visibility": "private",
                "category": "teams",
            },
            fetched_at=datetime.now(timezone.utc),
            tenant_id="t1",
        )
        record = connector.normalize(raw)
        assert record.finding == "Teams Configuration: Finance"
        assert record.severity == "low"

    def test_normalize_unknown_category(self, connector: M365CollabConnector):
        raw = RawFinding(
            id="x",
            source="m365_collab",
            raw_data={"id": "x", "category": "unknown"},
            fetched_at=datetime.now(timezone.utc),
            tenant_id="t1",
        )
        record = connector.normalize(raw)
        assert record.severity == "medium"
        assert record.asset == "unknown"


# ─────────────────────────────────────────────────────────────────────────────
# Tests: Error handling
# ─────────────────────────────────────────────────────────────────────────────

class TestM365CollabErrorHandling:
    @respx.mock
    def test_rate_limit_during_auth(self, connector: M365CollabConnector):
        respx.post(TOKEN_URL).mock(
            return_value=httpx.Response(429, json={"error": "Rate limited"})
        )
        with pytest.raises(ConnectorAuthError):
            connector.authenticate(
                {
                    "tenant_id": "test-tenant-id",
                    "client_id": "c",
                    "client_secret": "s",
                }
            )

    @respx.mock
    def test_fetch_increments_error_count(self, connector: M365CollabConnector, valid_credentials: dict):
        _mock_token()
        respx.get(f"{GRAPH_BASE}/sites").mock(
            return_value=httpx.Response(500, json={"error": "boom"})
        )
        connector.authenticate(valid_credentials)
        with pytest.raises(ConnectorFetchError):
            connector.fetch_findings(since=datetime.now(timezone.utc))
        assert connector._error_count == 1
        assert "boom" in (connector._last_error or "")


# ─────────────────────────────────────────────────────────────────────────────
# Tests: Tenant isolation
# ─────────────────────────────────────────────────────────────────────────────

class TestM365CollabTenantIsolation:
    @respx.mock
    def test_different_tenant_credentials_produce_different_results(self):
        token_a = "https://login.microsoftonline.com/tenant-a/oauth2/v2.0/token"
        token_b = "https://login.microsoftonline.com/tenant-b/oauth2/v2.0/token"
        graph = "https://graph.microsoft.com/v1.0"

        respx.post(token_a).mock(
            return_value=httpx.Response(
                200, json={"token_type": "Bearer", "expires_in": 3599, "access_token": "TOK_A"}
            )
        )
        respx.post(token_b).mock(
            return_value=httpx.Response(
                200, json={"token_type": "Bearer", "expires_in": 3599, "access_token": "TOK_B"}
            )
        )
        respx.get(f"{graph}/sites").mock(return_value=httpx.Response(200, json={"value": []}))
        respx.get(f"{graph}/users").mock(return_value=httpx.Response(200, json={"value": []}))
        respx.get(f"{graph}/teams").mock(return_value=httpx.Response(200, json={"value": []}))

        conn_a = M365CollabConnector()
        session_a = conn_a.authenticate(
            {"tenant_id": "tenant-a", "client_id": "C_A", "client_secret": "S_A"}
        )
        findings_a = conn_a.fetch_findings(
            since=datetime(2024, 1, 1, tzinfo=timezone.utc),
            tenant_id="tenant-a",
        )

        conn_b = M365CollabConnector()
        session_b = conn_b.authenticate(
            {"tenant_id": "tenant-b", "client_id": "C_B", "client_secret": "S_B"}
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

class TestM365CollabHealthCheck:
    def test_health_check_ok_fresh_connector(self, connector: M365CollabConnector):
        health = connector.health_check()
        assert isinstance(health, ConnectorHealth)
        assert health.connector_name == "m365_collab"
        assert health.status == "ok"
        assert health.error_count == 0
        assert health.last_run is None

    @respx.mock
    def test_health_check_degraded_after_errors(self, connector: M365CollabConnector):
        _mock_token()
        respx.get(f"{GRAPH_BASE}/sites").mock(
            return_value=httpx.Response(500, json={"error": "boom"})
        )
        connector.authenticate(
            {"tenant_id": "test-tenant-id", "client_id": "c", "client_secret": "s"}
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
    def test_health_check_error_after_many_errors(self, connector: M365CollabConnector):
        _mock_token()
        respx.get(f"{GRAPH_BASE}/sites").mock(
            return_value=httpx.Response(500, json={"error": "boom"})
        )
        connector.authenticate(
            {"tenant_id": "test-tenant-id", "client_id": "c", "client_secret": "s"}
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
        self, connector: M365CollabConnector, valid_credentials: dict
    ):
        _mock_token()
        respx.get(f"{GRAPH_BASE}/sites").mock(return_value=httpx.Response(200, json={"value": []}))
        respx.get(f"{GRAPH_BASE}/users").mock(return_value=httpx.Response(200, json={"value": []}))
        respx.get(f"{GRAPH_BASE}/teams").mock(return_value=httpx.Response(200, json={"value": []}))
        connector.authenticate(valid_credentials)
        connector.fetch_findings(since=datetime.now(timezone.utc))
        health = connector.health_check()
        assert health.last_run is not None
