"""
TDD tests for the Microsoft Entra ID live connector.

Uses respx to mock all HTTP traffic — no real API calls.
Coverage: authentication (OAuth2 client credentials), fetch_findings
(riskyUsers, riskDetections, riskySignIns, caPolicyResults),
normalization with Identity Risk severity mapping, error handling,
tenant isolation, health check.
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
from connectors.ms_entra.connector import MsEntraConnector


# ─────────────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture
def connector() -> MsEntraConnector:
    return MsEntraConnector()


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


def _mock_risky_user() -> dict[str, Any]:
    return {
        "id": "user-001",
        "userPrincipalName": "alice@example.com",
        "riskState": "atRisk",
        "riskLevel": "high",
    }


def _mock_risk_detection(risk_type: str) -> dict[str, Any]:
    return {
        "id": f"rd-{risk_type}",
        "userPrincipalName": "alice@example.com",
        "riskEventType": risk_type,
        "riskLevel": "high",
        "riskState": "atRisk",
        "detectedDateTime": "2024-01-15T10:30:00Z",
    }


def _mock_risky_signin() -> dict[str, Any]:
    return {
        "id": "si-001",
        "userPrincipalName": "alice@example.com",
        "riskLevelDuringSignIn": "high",
        "riskState": "atRisk",
        "createdDateTime": "2024-01-15T10:30:00Z",
    }


def _mock_ca_policy_result() -> dict[str, Any]:
    return {
        "id": "ca-001",
        "policyName": "Require MFA",
        "result": "failure",
        "userPrincipalName": "alice@example.com",
        "createdDateTime": "2024-01-15T10:30:00Z",
    }


# ─────────────────────────────────────────────────────────────────────────────
# Tests: Authentication
# ─────────────────────────────────────────────────────────────────────────────

class TestMsEntraAuthentication:
    @respx.mock
    def test_authenticate_success(self, connector: MsEntraConnector, valid_credentials: dict):
        route = _mock_token()
        session = connector.authenticate(valid_credentials)
        assert isinstance(session, ConnectorSession)
        assert session.connector_name == "ms_entra"
        assert session.tenant_id == "test-tenant-id"
        assert route.called

    @respx.mock
    def test_authenticate_failure_invalid_creds(self, connector: MsEntraConnector):
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

    def test_authenticate_failure_missing_tenant_id(self, connector: MsEntraConnector):
        with pytest.raises(ConnectorAuthError):
            connector.authenticate(
                {"client_id": "c", "client_secret": "s"}
            )

    def test_authenticate_failure_missing_client_id(self, connector: MsEntraConnector):
        with pytest.raises(ConnectorAuthError):
            connector.authenticate(
                {"tenant_id": "t", "client_secret": "s"}
            )

    def test_authenticate_failure_missing_client_secret(self, connector: MsEntraConnector):
        with pytest.raises(ConnectorAuthError):
            connector.authenticate(
                {"tenant_id": "t", "client_id": "c"}
            )


# ─────────────────────────────────────────────────────────────────────────────
# Tests: Fetch findings
# ─────────────────────────────────────────────────────────────────────────────

class TestMsEntraFetchFindings:
    @respx.mock
    def test_fetch_findings_empty(self, connector: MsEntraConnector, valid_credentials: dict):
        _mock_token()
        respx.get(f"{GRAPH_BASE}/identityProtection/riskyUsers").mock(
            return_value=httpx.Response(200, json={"value": []})
        )
        respx.get(f"{GRAPH_BASE}/identityProtection/riskDetections").mock(
            return_value=httpx.Response(200, json={"value": []})
        )
        respx.get(f"{GRAPH_BASE}/auditLogs/signIns").mock(
            return_value=httpx.Response(200, json={"value": []})
        )
        respx.get(f"{GRAPH_BASE}/identityProtection/conditionalAccessPolicyResults").mock(
            return_value=httpx.Response(200, json={"value": []})
        )
        connector.authenticate(valid_credentials)
        findings = connector.fetch_findings(
            since=datetime(2024, 1, 1, tzinfo=timezone.utc),
            tenant_id="test-tenant-id",
        )
        assert findings == []

    @respx.mock
    def test_fetch_findings_risky_users(self, connector: MsEntraConnector, valid_credentials: dict):
        _mock_token()
        respx.get(f"{GRAPH_BASE}/identityProtection/riskyUsers").mock(
            return_value=httpx.Response(200, json={"value": [_mock_risky_user()]})
        )
        respx.get(f"{GRAPH_BASE}/identityProtection/riskDetections").mock(
            return_value=httpx.Response(200, json={"value": []})
        )
        respx.get(f"{GRAPH_BASE}/auditLogs/signIns").mock(
            return_value=httpx.Response(200, json={"value": []})
        )
        respx.get(f"{GRAPH_BASE}/identityProtection/conditionalAccessPolicyResults").mock(
            return_value=httpx.Response(200, json={"value": []})
        )
        connector.authenticate(valid_credentials)
        findings = connector.fetch_findings(
            since=datetime(2024, 1, 1, tzinfo=timezone.utc),
            tenant_id="test-tenant-id",
        )
        assert len(findings) == 1
        assert findings[0].source == "ms_entra"
        assert findings[0].raw_data["category"] == "risky_user"

    @respx.mock
    def test_fetch_findings_risk_detections(self, connector: MsEntraConnector, valid_credentials: dict):
        _mock_token()
        respx.get(f"{GRAPH_BASE}/identityProtection/riskyUsers").mock(
            return_value=httpx.Response(200, json={"value": []})
        )
        respx.get(f"{GRAPH_BASE}/identityProtection/riskDetections").mock(
            return_value=httpx.Response(
                200, json={"value": [_mock_risk_detection("maliciousIPAddress")]}
            )
        )
        respx.get(f"{GRAPH_BASE}/auditLogs/signIns").mock(
            return_value=httpx.Response(200, json={"value": []})
        )
        respx.get(f"{GRAPH_BASE}/identityProtection/conditionalAccessPolicyResults").mock(
            return_value=httpx.Response(200, json={"value": []})
        )
        connector.authenticate(valid_credentials)
        findings = connector.fetch_findings(
            since=datetime(2024, 1, 1, tzinfo=timezone.utc),
            tenant_id="test-tenant-id",
        )
        assert len(findings) == 1
        assert findings[0].raw_data["category"] == "risk_detection"

    @respx.mock
    def test_fetch_findings_risky_signins(self, connector: MsEntraConnector, valid_credentials: dict):
        _mock_token()
        respx.get(f"{GRAPH_BASE}/identityProtection/riskyUsers").mock(
            return_value=httpx.Response(200, json={"value": []})
        )
        respx.get(f"{GRAPH_BASE}/identityProtection/riskDetections").mock(
            return_value=httpx.Response(200, json={"value": []})
        )
        respx.get(f"{GRAPH_BASE}/auditLogs/signIns").mock(
            return_value=httpx.Response(200, json={"value": [_mock_risky_signin()]})
        )
        respx.get(f"{GRAPH_BASE}/identityProtection/conditionalAccessPolicyResults").mock(
            return_value=httpx.Response(200, json={"value": []})
        )
        connector.authenticate(valid_credentials)
        findings = connector.fetch_findings(
            since=datetime(2024, 1, 1, tzinfo=timezone.utc),
            tenant_id="test-tenant-id",
        )
        assert len(findings) == 1
        assert findings[0].raw_data["category"] == "risky_signin"

    @respx.mock
    def test_fetch_findings_ca_policies(self, connector: MsEntraConnector, valid_credentials: dict):
        _mock_token()
        respx.get(f"{GRAPH_BASE}/identityProtection/riskyUsers").mock(
            return_value=httpx.Response(200, json={"value": []})
        )
        respx.get(f"{GRAPH_BASE}/identityProtection/riskDetections").mock(
            return_value=httpx.Response(200, json={"value": []})
        )
        respx.get(f"{GRAPH_BASE}/auditLogs/signIns").mock(
            return_value=httpx.Response(200, json={"value": []})
        )
        respx.get(f"{GRAPH_BASE}/identityProtection/conditionalAccessPolicyResults").mock(
            return_value=httpx.Response(200, json={"value": [_mock_ca_policy_result()]})
        )
        connector.authenticate(valid_credentials)
        findings = connector.fetch_findings(
            since=datetime(2024, 1, 1, tzinfo=timezone.utc),
            tenant_id="test-tenant-id",
        )
        assert len(findings) == 1
        assert findings[0].raw_data["category"] == "ca_policy"

    @respx.mock
    def test_fetch_findings_all_categories(self, connector: MsEntraConnector, valid_credentials: dict):
        _mock_token()
        respx.get(f"{GRAPH_BASE}/identityProtection/riskyUsers").mock(
            return_value=httpx.Response(200, json={"value": [_mock_risky_user()]})
        )
        respx.get(f"{GRAPH_BASE}/identityProtection/riskDetections").mock(
            return_value=httpx.Response(
                200, json={"value": [_mock_risk_detection("mfaFatigue")]}
            )
        )
        respx.get(f"{GRAPH_BASE}/auditLogs/signIns").mock(
            return_value=httpx.Response(200, json={"value": [_mock_risky_signin()]})
        )
        respx.get(f"{GRAPH_BASE}/identityProtection/conditionalAccessPolicyResults").mock(
            return_value=httpx.Response(200, json={"value": [_mock_ca_policy_result()]})
        )
        connector.authenticate(valid_credentials)
        findings = connector.fetch_findings(
            since=datetime(2024, 1, 1, tzinfo=timezone.utc),
            tenant_id="test-tenant-id",
        )
        assert len(findings) == 4
        cats = {f.raw_data["category"] for f in findings}
        assert cats == {"risky_user", "risk_detection", "risky_signin", "ca_policy"}

    @respx.mock
    def test_fetch_findings_5xx_error(self, connector: MsEntraConnector, valid_credentials: dict):
        _mock_token()
        respx.get(f"{GRAPH_BASE}/identityProtection/riskyUsers").mock(
            return_value=httpx.Response(503, json={"error": "Service Unavailable"})
        )
        connector.authenticate(valid_credentials)
        with pytest.raises(ConnectorFetchError):
            connector.fetch_findings(
                since=datetime(2024, 1, 1, tzinfo=timezone.utc),
                tenant_id="test-tenant-id",
            )

    def test_fetch_findings_not_authenticated(self, connector: MsEntraConnector):
        with pytest.raises(ConnectorFetchError):
            connector.fetch_findings(since=datetime.now(timezone.utc))

    @respx.mock
    def test_fetch_pagination_via_odata_nextlink(self, connector: MsEntraConnector, valid_credentials: dict):
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
                        "value": [_mock_risky_user()],
                        "@odata.nextLink": f"{GRAPH_BASE}/identityProtection/riskyUsers?$skip=1",
                    },
                )
            return httpx.Response(200, json={"value": [_mock_risky_user()]})

        respx.get(f"{GRAPH_BASE}/identityProtection/riskyUsers").mock(side_effect=_handler)
        respx.get(f"{GRAPH_BASE}/identityProtection/riskDetections").mock(
            return_value=httpx.Response(200, json={"value": []})
        )
        respx.get(f"{GRAPH_BASE}/auditLogs/signIns").mock(
            return_value=httpx.Response(200, json={"value": []})
        )
        respx.get(f"{GRAPH_BASE}/identityProtection/conditionalAccessPolicyResults").mock(
            return_value=httpx.Response(200, json={"value": []})
        )
        connector.authenticate(valid_credentials)
        findings = connector.fetch_findings(
            since=datetime(2024, 1, 1, tzinfo=timezone.utc),
            tenant_id="test-tenant-id",
        )
        # 2 riskyUsers + 0 others = 2 findings
        assert len(findings) == 2
        assert call_count == 2

    @respx.mock
    def test_fetch_respects_throttling_retry_after(self, connector: MsEntraConnector, valid_credentials: dict):
        _mock_token()
        call_count = 0

        def _handler(request: httpx.Request):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return httpx.Response(429, headers={"Retry-After": "0"}, json={"error": "Throttled"})
            return httpx.Response(200, json={"value": [_mock_risky_user()]})

        respx.get(f"{GRAPH_BASE}/identityProtection/riskyUsers").mock(side_effect=_handler)
        respx.get(f"{GRAPH_BASE}/identityProtection/riskDetections").mock(
            return_value=httpx.Response(200, json={"value": []})
        )
        respx.get(f"{GRAPH_BASE}/auditLogs/signIns").mock(
            return_value=httpx.Response(200, json={"value": []})
        )
        respx.get(f"{GRAPH_BASE}/identityProtection/conditionalAccessPolicyResults").mock(
            return_value=httpx.Response(200, json={"value": []})
        )
        connector.authenticate(valid_credentials)
        findings = connector.fetch_findings(
            since=datetime(2024, 1, 1, tzinfo=timezone.utc),
            tenant_id="test-tenant-id",
        )
        assert len(findings) == 1
        assert call_count == 2


# ─────────────────────────────────────────────────────────────────────────────
# Tests: Normalization + Identity Risk severity mapping
# ─────────────────────────────────────────────────────────────────────────────

class TestMsEntraNormalize:
    def test_normalize_risky_user(self, connector: MsEntraConnector):
        raw = RawFinding(
            id="user-001",
            source="ms_entra",
            raw_data={
                "id": "user-001",
                "userPrincipalName": "alice@example.com",
                "riskState": "atRisk",
                "riskLevel": "high",
                "category": "risky_user",
            },
            fetched_at=datetime.now(timezone.utc),
            tenant_id="t1",
        )
        record = connector.normalize(raw)
        assert isinstance(record, URIPRiskRecord)
        assert record.finding == "Risky User: alice@example.com"
        assert record.severity == "high"
        assert record.asset == "alice@example.com"
        assert record.source == "ms_entra"
        assert record.domain == "identity"
        assert record.owner_team == "IAM"

    def test_normalize_risky_signin(self, connector: MsEntraConnector):
        raw = RawFinding(
            id="si-001",
            source="ms_entra",
            raw_data={
                "id": "si-001",
                "userPrincipalName": "alice@example.com",
                "riskLevelDuringSignIn": "medium",
                "riskState": "atRisk",
                "category": "risky_signin",
            },
            fetched_at=datetime.now(timezone.utc),
            tenant_id="t1",
        )
        record = connector.normalize(raw)
        assert record.finding == "Risky Sign-In: alice@example.com"
        assert record.severity == "medium"
        assert record.asset == "alice@example.com"

    def test_normalize_ca_policy_failure(self, connector: MsEntraConnector):
        raw = RawFinding(
            id="ca-001",
            source="ms_entra",
            raw_data={
                "id": "ca-001",
                "policyName": "Require MFA",
                "result": "failure",
                "userPrincipalName": "alice@example.com",
                "category": "ca_policy",
            },
            fetched_at=datetime.now(timezone.utc),
            tenant_id="t1",
        )
        record = connector.normalize(raw)
        assert record.finding == "CA Policy Failure: Require MFA"
        assert record.severity == "high"
        assert record.asset == "alice@example.com"

    # ── Identity Risk severity mapping (per MASTER_BLUEPRINT) ──

    def test_normalize_risk_detection_leaked_credentials(self, connector: MsEntraConnector):
        raw = RawFinding(
            id="rd-1",
            source="ms_entra",
            raw_data={
                "id": "rd-1",
                "userPrincipalName": "alice@example.com",
                "riskEventType": "leakedCredentials",
                "category": "risk_detection",
            },
            fetched_at=datetime.now(timezone.utc),
            tenant_id="t1",
        )
        record = connector.normalize(raw)
        assert record.severity == "critical"
        assert "leakedCredentials" in record.description

    def test_normalize_risk_detection_malicious_ip(self, connector: MsEntraConnector):
        raw = RawFinding(
            id="rd-2",
            source="ms_entra",
            raw_data={
                "id": "rd-2",
                "userPrincipalName": "alice@example.com",
                "riskEventType": "maliciousIPAddress",
                "category": "risk_detection",
            },
            fetched_at=datetime.now(timezone.utc),
            tenant_id="t1",
        )
        record = connector.normalize(raw)
        assert record.severity == "critical"

    def test_normalize_risk_detection_mfa_fatigue(self, connector: MsEntraConnector):
        raw = RawFinding(
            id="rd-3",
            source="ms_entra",
            raw_data={
                "id": "rd-3",
                "userPrincipalName": "alice@example.com",
                "riskEventType": "mfaFatigue",
                "category": "risk_detection",
            },
            fetched_at=datetime.now(timezone.utc),
            tenant_id="t1",
        )
        record = connector.normalize(raw)
        assert record.severity == "high"

    def test_normalize_risk_detection_atypical_travel(self, connector: MsEntraConnector):
        raw = RawFinding(
            id="rd-4",
            source="ms_entra",
            raw_data={
                "id": "rd-4",
                "userPrincipalName": "alice@example.com",
                "riskEventType": "atypicalTravel",
                "category": "risk_detection",
            },
            fetched_at=datetime.now(timezone.utc),
            tenant_id="t1",
        )
        record = connector.normalize(raw)
        assert record.severity == "high"

    def test_normalize_risk_detection_anonymized_ip(self, connector: MsEntraConnector):
        raw = RawFinding(
            id="rd-5",
            source="ms_entra",
            raw_data={
                "id": "rd-5",
                "userPrincipalName": "alice@example.com",
                "riskEventType": "anonymizedIPAddress",
                "category": "risk_detection",
            },
            fetched_at=datetime.now(timezone.utc),
            tenant_id="t1",
        )
        record = connector.normalize(raw)
        assert record.severity == "medium"

    def test_normalize_risk_detection_suspicious_api_traffic(self, connector: MsEntraConnector):
        raw = RawFinding(
            id="rd-6",
            source="ms_entra",
            raw_data={
                "id": "rd-6",
                "userPrincipalName": "alice@example.com",
                "riskEventType": "suspiciousAPITraffic",
                "category": "risk_detection",
            },
            fetched_at=datetime.now(timezone.utc),
            tenant_id="t1",
        )
        record = connector.normalize(raw)
        assert record.severity == "medium"

    def test_normalize_unknown_risk_event_type_defaults_medium(self, connector: MsEntraConnector):
        raw = RawFinding(
            id="rd-7",
            source="ms_entra",
            raw_data={
                "id": "rd-7",
                "userPrincipalName": "alice@example.com",
                "riskEventType": "unknownRiskType",
                "category": "risk_detection",
            },
            fetched_at=datetime.now(timezone.utc),
            tenant_id="t1",
        )
        record = connector.normalize(raw)
        assert record.severity == "medium"

    def test_normalize_missing_upn(self, connector: MsEntraConnector):
        raw = RawFinding(
            id="rd-8",
            source="ms_entra",
            raw_data={
                "id": "rd-8",
                "riskEventType": "mfaFatigue",
                "category": "risk_detection",
            },
            fetched_at=datetime.now(timezone.utc),
            tenant_id="t1",
        )
        record = connector.normalize(raw)
        assert record.asset == "unknown-user"


# ─────────────────────────────────────────────────────────────────────────────
# Tests: Error handling
# ─────────────────────────────────────────────────────────────────────────────

class TestMsEntraErrorHandling:
    @respx.mock
    def test_rate_limit_during_auth(self, connector: MsEntraConnector):
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
    def test_fetch_increments_error_count(self, connector: MsEntraConnector, valid_credentials: dict):
        _mock_token()
        respx.get(f"{GRAPH_BASE}/identityProtection/riskyUsers").mock(
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

class TestMsEntraTenantIsolation:
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
        respx.get(f"{graph}/identityProtection/riskyUsers").mock(
            return_value=httpx.Response(200, json={"value": []})
        )
        respx.get(f"{graph}/identityProtection/riskDetections").mock(
            return_value=httpx.Response(200, json={"value": []})
        )
        respx.get(f"{graph}/auditLogs/signIns").mock(
            return_value=httpx.Response(200, json={"value": []})
        )
        respx.get(f"{graph}/identityProtection/conditionalAccessPolicyResults").mock(
            return_value=httpx.Response(200, json={"value": []})
        )

        conn_a = MsEntraConnector()
        session_a = conn_a.authenticate(
            {"tenant_id": "tenant-a", "client_id": "C_A", "client_secret": "S_A"}
        )
        findings_a = conn_a.fetch_findings(
            since=datetime(2024, 1, 1, tzinfo=timezone.utc),
            tenant_id="tenant-a",
        )

        conn_b = MsEntraConnector()
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

class TestMsEntraHealthCheck:
    def test_health_check_ok_fresh_connector(self, connector: MsEntraConnector):
        health = connector.health_check()
        assert isinstance(health, ConnectorHealth)
        assert health.connector_name == "ms_entra"
        assert health.status == "ok"
        assert health.error_count == 0
        assert health.last_run is None

    @respx.mock
    def test_health_check_degraded_after_errors(self, connector: MsEntraConnector):
        _mock_token()
        respx.get(f"{GRAPH_BASE}/identityProtection/riskyUsers").mock(
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
    def test_health_check_error_after_many_errors(self, connector: MsEntraConnector):
        _mock_token()
        respx.get(f"{GRAPH_BASE}/identityProtection/riskyUsers").mock(
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
        self, connector: MsEntraConnector, valid_credentials: dict
    ):
        _mock_token()
        respx.get(f"{GRAPH_BASE}/identityProtection/riskyUsers").mock(
            return_value=httpx.Response(200, json={"value": []})
        )
        respx.get(f"{GRAPH_BASE}/identityProtection/riskDetections").mock(
            return_value=httpx.Response(200, json={"value": []})
        )
        respx.get(f"{GRAPH_BASE}/auditLogs/signIns").mock(
            return_value=httpx.Response(200, json={"value": []})
        )
        respx.get(f"{GRAPH_BASE}/identityProtection/conditionalAccessPolicyResults").mock(
            return_value=httpx.Response(200, json={"value": []})
        )
        connector.authenticate(valid_credentials)
        connector.fetch_findings(since=datetime.now(timezone.utc))
        health = connector.health_check()
        assert health.last_run is not None
