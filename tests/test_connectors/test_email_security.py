"""
TDD tests for the Email Security connector (Google Workspace + M365 Defender).

Uses respx to mock all HTTP traffic — no real API calls.
Coverage: OAuth2 authentication per provider, fetch phishing/BEC/DMARC alerts,
normalization, severity mapping, health check, error handling.
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
from connectors.email_security.connector import EmailSecurityConnector


# ─────────────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture
def connector() -> EmailSecurityConnector:
    return EmailSecurityConnector()


@pytest.fixture
def google_credentials() -> dict[str, Any]:
    return {
        "provider": "google_workspace",
        "service_account_json": '{"type": "service_account", "client_email": "test@project.iam.gserviceaccount.com"}',
        "admin_email": "admin@example.com",
        "tenant_id": "tenant-email",
    }


@pytest.fixture
def m365_credentials() -> dict[str, Any]:
    return {
        "provider": "m365_defender",
        "client_id": "m365-client-id",
        "client_secret": "m365-client-secret",
        "tenant_id": "tenant-email",
    }


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _mock_google_alert(
    alert_id: str = "google-alert-001",
    alert_type: str = "User reported phishing",
    severity: str = "HIGH",
) -> dict[str, Any]:
    return {
        "alertId": alert_id,
        "createTime": "2024-06-15T10:00:00.000Z",
        "customerId": "C123abc",
        "type": alert_type,
        "source": "Gmail security",
        "data": {
            "email": "phishing@evil.com",
            "displayName": "Phishing Attempt",
            "isDomainOwned": False,
        },
        "severity": severity,
    }


def _mock_m365_alert(
    alert_id: str = "m365-alert-001",
    severity: str = "high",
    category: str = "Phishing",
) -> dict[str, Any]:
    return {
        "id": alert_id,
        "title": f"{category} alert",
        "category": category,
        "severity": severity,
        "createdDateTime": "2024-06-15T10:00:00Z",
        "description": f"Suspicious {category} email detected",
        "recommendedActions": "Investigate and quarantine",
        "azureTenantId": "tenant-email",
    }


# ─────────────────────────────────────────────────────────────────────────────
# Tests: Authentication
# ─────────────────────────────────────────────────────────────────────────────

class TestEmailSecurityAuthentication:
    @respx.mock
    def test_authenticate_google_success(self, connector: EmailSecurityConnector, google_credentials: dict):
        # Mock token endpoint
        respx.post("https://oauth2.googleapis.com/token").mock(
            return_value=httpx.Response(200, json={"access_token": "google-token-123", "expires_in": 3600})
        )
        session = connector.authenticate(google_credentials)
        assert isinstance(session, ConnectorSession)
        assert session.connector_name == "email_security"
        assert "google_workspace" in session.token

    @respx.mock
    def test_authenticate_google_token_failure(self, connector: EmailSecurityConnector, google_credentials: dict):
        respx.post("https://oauth2.googleapis.com/token").mock(
            return_value=httpx.Response(400, json={"error": "invalid_grant"})
        )
        with pytest.raises(ConnectorAuthError):
            connector.authenticate(google_credentials)

    @respx.mock
    def test_authenticate_m365_success(self, connector: EmailSecurityConnector, m365_credentials: dict):
        respx.post("https://login.microsoftonline.com/tenant-email/oauth2/v2.0/token").mock(
            return_value=httpx.Response(200, json={"access_token": "m365-token-456", "expires_in": 3600})
        )
        session = connector.authenticate(m365_credentials)
        assert isinstance(session, ConnectorSession)
        assert "m365_defender" in session.token

    @respx.mock
    def test_authenticate_m365_token_failure(self, connector: EmailSecurityConnector, m365_credentials: dict):
        respx.post("https://login.microsoftonline.com/tenant-email/oauth2/v2.0/token").mock(
            return_value=httpx.Response(400, json={"error": "invalid_client"})
        )
        with pytest.raises(ConnectorAuthError):
            connector.authenticate(m365_credentials)

    def test_authenticate_unknown_provider(self, connector: EmailSecurityConnector):
        with pytest.raises(ConnectorAuthError):
            connector.authenticate({"provider": "unknown"})

    def test_authenticate_missing_provider(self, connector: EmailSecurityConnector):
        with pytest.raises(ConnectorAuthError):
            connector.authenticate({})


# ─────────────────────────────────────────────────────────────────────────────
# Tests: fetch_findings Google Workspace
# ─────────────────────────────────────────────────────────────────────────────

class TestEmailSecurityFetchGoogle:
    @respx.mock
    def test_fetch_google_success(self, connector: EmailSecurityConnector, google_credentials: dict):
        respx.post("https://oauth2.googleapis.com/token").mock(
            return_value=httpx.Response(200, json={"access_token": "google-token-123", "expires_in": 3600})
        )
        connector.authenticate(google_credentials)
        respx.get("https://alertcenter.googleapis.com/v1beta1/alerts").mock(
            return_value=httpx.Response(200, json={"alerts": [_mock_google_alert()]})
        )
        since = datetime(2024, 6, 1, tzinfo=timezone.utc)
        findings = connector.fetch_findings(since, tenant_id="tenant-email")
        assert len(findings) == 1
        assert findings[0].source == "email_security"
        assert findings[0].raw_data.get("provider") == "google_workspace"

    @respx.mock
    def test_fetch_google_empty(self, connector: EmailSecurityConnector, google_credentials: dict):
        respx.post("https://oauth2.googleapis.com/token").mock(
            return_value=httpx.Response(200, json={"access_token": "google-token-123", "expires_in": 3600})
        )
        connector.authenticate(google_credentials)
        respx.get("https://alertcenter.googleapis.com/v1beta1/alerts").mock(
            return_value=httpx.Response(200, json={"alerts": []})
        )
        since = datetime(2024, 6, 1, tzinfo=timezone.utc)
        findings = connector.fetch_findings(since, tenant_id="tenant-email")
        assert findings == []


# ─────────────────────────────────────────────────────────────────────────────
# Tests: fetch_findings M365 Defender
# ─────────────────────────────────────────────────────────────────────────────

class TestEmailSecurityFetchM365:
    @respx.mock
    def test_fetch_m365_success(self, connector: EmailSecurityConnector, m365_credentials: dict):
        respx.post("https://login.microsoftonline.com/tenant-email/oauth2/v2.0/token").mock(
            return_value=httpx.Response(200, json={"access_token": "m365-token-456", "expires_in": 3600})
        )
        connector.authenticate(m365_credentials)
        respx.get("https://graph.microsoft.com/v1.0/security/alerts").mock(
            return_value=httpx.Response(200, json={"value": [_mock_m365_alert()]})
        )
        since = datetime(2024, 6, 1, tzinfo=timezone.utc)
        findings = connector.fetch_findings(since, tenant_id="tenant-email")
        assert len(findings) == 1
        assert findings[0].raw_data.get("provider") == "m365_defender"

    @respx.mock
    def test_fetch_m365_empty(self, connector: EmailSecurityConnector, m365_credentials: dict):
        respx.post("https://login.microsoftonline.com/tenant-email/oauth2/v2.0/token").mock(
            return_value=httpx.Response(200, json={"access_token": "m365-token-456", "expires_in": 3600})
        )
        connector.authenticate(m365_credentials)
        respx.get("https://graph.microsoft.com/v1.0/security/alerts").mock(
            return_value=httpx.Response(200, json={"value": []})
        )
        since = datetime(2024, 6, 1, tzinfo=timezone.utc)
        findings = connector.fetch_findings(since, tenant_id="tenant-email")
        assert findings == []


# ─────────────────────────────────────────────────────────────────────────────
# Tests: Normalization
# ─────────────────────────────────────────────────────────────────────────────

class TestEmailSecurityNormalize:
    def test_normalize_google_phishing_high(self, connector: EmailSecurityConnector):
        raw = RawFinding(
            id="google-001",
            source="email_security",
            raw_data={"provider": "google_workspace", **_mock_google_alert(alert_type="User reported phishing", severity="HIGH")},
            fetched_at=datetime.now(timezone.utc),
            tenant_id="tenant-email",
        )
        record = connector.normalize(raw)
        assert record.source == "email_security:google_workspace"
        assert record.severity == "high"
        assert record.cvss_score == 7.5
        assert record.domain == "email"

    def test_normalize_google_bec_critical(self, connector: EmailSecurityConnector):
        raw = RawFinding(
            id="google-002",
            source="email_security",
            raw_data={"provider": "google_workspace", **_mock_google_alert(alert_type="Business email compromise", severity="HIGH")},
            fetched_at=datetime.now(timezone.utc),
            tenant_id="tenant-email",
        )
        record = connector.normalize(raw)
        assert record.severity == "critical"
        assert record.cvss_score == 9.0

    def test_normalize_google_suspicious_medium(self, connector: EmailSecurityConnector):
        raw = RawFinding(
            id="google-003",
            source="email_security",
            raw_data={"provider": "google_workspace", **_mock_google_alert(alert_type="Suspicious login", severity="MEDIUM")},
            fetched_at=datetime.now(timezone.utc),
            tenant_id="tenant-email",
        )
        record = connector.normalize(raw)
        assert record.severity == "medium"
        assert record.cvss_score == 5.0

    def test_normalize_google_dmarc_low(self, connector: EmailSecurityConnector):
        raw = RawFinding(
            id="google-004",
            source="email_security",
            raw_data={"provider": "google_workspace", **_mock_google_alert(alert_type="DMARC failure", severity="LOW")},
            fetched_at=datetime.now(timezone.utc),
            tenant_id="tenant-email",
        )
        record = connector.normalize(raw)
        assert record.severity == "low"
        assert record.cvss_score == 3.0

    def test_normalize_m365_phishing_high(self, connector: EmailSecurityConnector):
        raw = RawFinding(
            id="m365-001",
            source="email_security",
            raw_data={"provider": "m365_defender", **_mock_m365_alert(category="Phishing", severity="high")},
            fetched_at=datetime.now(timezone.utc),
            tenant_id="tenant-email",
        )
        record = connector.normalize(raw)
        assert record.source == "email_security:m365_defender"
        assert record.severity == "high"
        assert record.cvss_score == 7.5
        assert record.domain == "email"

    def test_normalize_m365_malware_critical(self, connector: EmailSecurityConnector):
        raw = RawFinding(
            id="m365-002",
            source="email_security",
            raw_data={"provider": "m365_defender", **_mock_m365_alert(category="Malware", severity="high")},
            fetched_at=datetime.now(timezone.utc),
            tenant_id="tenant-email",
        )
        record = connector.normalize(raw)
        assert record.severity == "critical"
        assert record.cvss_score == 9.0

    def test_normalize_m365_suspicious_medium(self, connector: EmailSecurityConnector):
        raw = RawFinding(
            id="m365-003",
            source="email_security",
            raw_data={"provider": "m365_defender", **_mock_m365_alert(category="SuspiciousEmail", severity="medium")},
            fetched_at=datetime.now(timezone.utc),
            tenant_id="tenant-email",
        )
        record = connector.normalize(raw)
        assert record.severity == "medium"
        assert record.cvss_score == 5.0

    def test_normalize_m365_hygiene_low(self, connector: EmailSecurityConnector):
        raw = RawFinding(
            id="m365-004",
            source="email_security",
            raw_data={"provider": "m365_defender", **_mock_m365_alert(category="SpfRecord", severity="low")},
            fetched_at=datetime.now(timezone.utc),
            tenant_id="tenant-email",
        )
        record = connector.normalize(raw)
        assert record.severity == "low"
        assert record.cvss_score == 3.0

    def test_normalize_unknown_provider_defaults(self, connector: EmailSecurityConnector):
        raw = RawFinding(
            id="unknown-001",
            source="email_security",
            raw_data={"provider": "unknown", "title": "Test", "severity": "medium"},
            fetched_at=datetime.now(timezone.utc),
            tenant_id="tenant-email",
        )
        record = connector.normalize(raw)
        assert record.source == "email_security:unknown"
        assert record.severity == "medium"
        assert record.domain == "email"


# ─────────────────────────────────────────────────────────────────────────────
# Tests: Error handling
# ─────────────────────────────────────────────────────────────────────────────

class TestEmailSecurityErrors:
    def test_fetch_without_authenticate(self, connector: EmailSecurityConnector):
        since = datetime(2024, 6, 1, tzinfo=timezone.utc)
        with pytest.raises(ConnectorFetchError):
            connector.fetch_findings(since, tenant_id="tenant-email")

    @respx.mock
    def test_fetch_google_http_error(self, connector: EmailSecurityConnector, google_credentials: dict):
        respx.post("https://oauth2.googleapis.com/token").mock(
            return_value=httpx.Response(200, json={"access_token": "google-token-123", "expires_in": 3600})
        )
        connector.authenticate(google_credentials)
        respx.get("https://alertcenter.googleapis.com/v1beta1/alerts").mock(
            return_value=httpx.Response(500, text="Internal Server Error")
        )
        since = datetime(2024, 6, 1, tzinfo=timezone.utc)
        with pytest.raises(ConnectorFetchError):
            connector.fetch_findings(since, tenant_id="tenant-email")


# ─────────────────────────────────────────────────────────────────────────────
# Tests: Health check
# ─────────────────────────────────────────────────────────────────────────────

class TestEmailSecurityHealthCheck:
    def test_health_check_ok(self, connector: EmailSecurityConnector):
        health = connector.health_check()
        assert isinstance(health, ConnectorHealth)
        assert health.connector_name == "email_security"
        assert health.status == "ok"

    @respx.mock
    def test_health_check_degraded_after_errors(self, connector: EmailSecurityConnector, google_credentials: dict):
        respx.post("https://oauth2.googleapis.com/token").mock(
            return_value=httpx.Response(200, json={"access_token": "google-token-123", "expires_in": 3600})
        )
        connector.authenticate(google_credentials)
        respx.get("https://alertcenter.googleapis.com/v1beta1/alerts").mock(
            return_value=httpx.Response(500, text="Error")
        )
        since = datetime(2024, 6, 1, tzinfo=timezone.utc)
        for _ in range(3):
            try:
                connector.fetch_findings(since, tenant_id="tenant-email")
            except Exception:
                pass
        health = connector.health_check()
        assert health.status == "degraded"
        assert health.error_count == 3
