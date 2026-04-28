"""
Tests for Azure CSPM connector.

Uses respx to mock HTTPX calls to Azure APIs.
"""
from __future__ import annotations

from datetime import datetime, timezone

import httpx
import pytest
import respx

from connectors.azure_cspm.connector import AzureCspmConnector
from connectors.base.connector import ConnectorAuthError, ConnectorFetchError


@pytest.fixture
def azure_connector() -> AzureCspmConnector:
    return AzureCspmConnector()


@pytest.fixture
def valid_creds() -> dict:
    return {
        "tenant_id": "test-tenant",
        "client_id": "test-client",
        "client_secret": "test-secret",
    }


TOKEN_URL = "https://login.microsoftonline.com/test-tenant/oauth2/v2.0/token"
SUB_URL = "https://management.azure.com/subscriptions?api-version=2020-01-01"


# ---------------------------------------------------------------------------
# authenticate
# ---------------------------------------------------------------------------

@respx.mock
def test_authenticate_success(azure_connector: AzureCspmConnector, valid_creds: dict):
    route = respx.post(TOKEN_URL).respond(
        200, json={"access_token": "fake-token", "expires_in": 3600}
    )
    session = azure_connector.authenticate(valid_creds)
    assert session.connector_name == "azure_cspm"
    assert route.called


@respx.mock
def test_authenticate_failure(azure_connector: AzureCspmConnector, valid_creds: dict):
    respx.post(TOKEN_URL).respond(401, json={"error": "invalid_client"})
    with pytest.raises(ConnectorAuthError):
        azure_connector.authenticate(valid_creds)


def test_authenticate_missing_credentials(azure_connector: AzureCspmConnector):
    with pytest.raises(ConnectorAuthError):
        azure_connector.authenticate({"tenant_id": "t"})


# ---------------------------------------------------------------------------
# fetch_findings
# ---------------------------------------------------------------------------

@respx.mock
def test_fetch_findings_policy(azure_connector: AzureCspmConnector, valid_creds: dict):
    respx.post(TOKEN_URL).respond(200, json={"access_token": "tok", "expires_in": 3600})
    respx.get(SUB_URL).respond(200, json={"value": [{"subscriptionId": "sub1"}]})
    policy_url = "https://management.azure.com/subscriptions/sub1/providers/Microsoft.PolicyInsights/policyStates/latest/queryResults?api-version=2019-10-01&$filter=complianceState%20eq%20'NonCompliant'"
    respx.get(policy_url).respond(
        200, json={"value": [{"resourceId": "r1", "complianceState": "NonCompliant"}]}
    )
    rec_url = "https://management.azure.com/subscriptions/sub1/providers/Microsoft.Security/assessments?api-version=2023-01-01"
    respx.get(rec_url).respond(200, json={"value": []})
    alert_url = "https://management.azure.com/subscriptions/sub1/providers/Microsoft.Security/alerts?api-version=2022-01-01"
    respx.get(alert_url).respond(200, json={"value": []})
    azure_connector.authenticate(valid_creds)
    findings = azure_connector.fetch_findings(datetime.now(timezone.utc), tenant_id="t1")
    assert any("policy" in f.id for f in findings)


@respx.mock
def test_fetch_findings_defender_recommendations(azure_connector: AzureCspmConnector, valid_creds: dict):
    respx.post(TOKEN_URL).respond(200, json={"access_token": "tok", "expires_in": 3600})
    respx.get(SUB_URL).respond(200, json={"value": [{"subscriptionId": "sub1"}]})
    policy_url = "https://management.azure.com/subscriptions/sub1/providers/Microsoft.PolicyInsights/policyStates/latest/queryResults?api-version=2019-10-01&$filter=complianceState%20eq%20'NonCompliant'"
    respx.get(policy_url).respond(200, json={"value": []})
    rec_url = "https://management.azure.com/subscriptions/sub1/providers/Microsoft.Security/assessments?api-version=2023-01-01"
    respx.get(rec_url).respond(200, json={"value": [{"id": "rec1", "name": "rec1", "properties": {"status": {"code": "Unhealthy"}}}]})
    alert_url = "https://management.azure.com/subscriptions/sub1/providers/Microsoft.Security/alerts?api-version=2022-01-01"
    respx.get(alert_url).respond(200, json={"value": []})
    azure_connector.authenticate(valid_creds)
    findings = azure_connector.fetch_findings(datetime.now(timezone.utc), tenant_id="t1")
    assert any("defender-rec" in f.id for f in findings)


@respx.mock
def test_fetch_findings_defender_alerts(azure_connector: AzureCspmConnector, valid_creds: dict):
    respx.post(TOKEN_URL).respond(200, json={"access_token": "tok", "expires_in": 3600})
    respx.get(SUB_URL).respond(200, json={"value": [{"subscriptionId": "sub1"}]})
    policy_url = "https://management.azure.com/subscriptions/sub1/providers/Microsoft.PolicyInsights/policyStates/latest/queryResults?api-version=2019-10-01&$filter=complianceState%20eq%20'NonCompliant'"
    respx.get(policy_url).respond(200, json={"value": []})
    rec_url = "https://management.azure.com/subscriptions/sub1/providers/Microsoft.Security/assessments?api-version=2023-01-01"
    respx.get(rec_url).respond(200, json={"value": []})
    alert_url = "https://management.azure.com/subscriptions/sub1/providers/Microsoft.Security/alerts?api-version=2022-01-01"
    respx.get(alert_url).respond(200, json={"value": [{"id": "alert1", "properties": {"severity": "High"}}]})
    azure_connector.authenticate(valid_creds)
    findings = azure_connector.fetch_findings(datetime.now(timezone.utc), tenant_id="t1")
    assert any("defender-alert" in f.id for f in findings)


def test_fetch_findings_not_authenticated(azure_connector: AzureCspmConnector):
    with pytest.raises(ConnectorFetchError) as exc_info:
        azure_connector.fetch_findings(datetime.now(timezone.utc))
    assert "not authenticated" in str(exc_info.value).lower()


# ---------------------------------------------------------------------------
# normalize
# ---------------------------------------------------------------------------

@respx.mock
def test_normalize_policy(azure_connector: AzureCspmConnector, valid_creds: dict):
    respx.post(TOKEN_URL).respond(200, json={"access_token": "tok", "expires_in": 3600})
    azure_connector.authenticate(valid_creds)
    from connectors.base.connector import RawFinding
    raw = RawFinding(
        id="policy:p1",
        source="azure_cspm",
        raw_data={
            "type": "policy",
            "data": {
                "resourceId": "r1",
                "complianceState": "NonCompliant",
                "resourceType": "Microsoft.Storage/storageAccounts",
            },
        },
        fetched_at=datetime.now(timezone.utc),
        tenant_id="t1",
    )
    record = azure_connector.normalize(raw)
    assert record.severity == "high"
    assert record.source == "azure_cspm"


@respx.mock
def test_normalize_defender_rec(azure_connector: AzureCspmConnector, valid_creds: dict):
    respx.post(TOKEN_URL).respond(200, json={"access_token": "tok", "expires_in": 3600})
    azure_connector.authenticate(valid_creds)
    from connectors.base.connector import RawFinding
    raw = RawFinding(
        id="defender-rec:r1",
        source="azure_cspm",
        raw_data={
            "type": "defender-rec",
            "data": {
                "id": "rec1",
                "name": "rec1",
                "properties": {"status": {"code": "Unhealthy"}, "displayName": "Test"},
            },
        },
        fetched_at=datetime.now(timezone.utc),
        tenant_id="t1",
    )
    record = azure_connector.normalize(raw)
    assert record.severity == "high"


@respx.mock
def test_normalize_defender_alert(azure_connector: AzureCspmConnector, valid_creds: dict):
    respx.post(TOKEN_URL).respond(200, json={"access_token": "tok", "expires_in": 3600})
    azure_connector.authenticate(valid_creds)
    from connectors.base.connector import RawFinding
    raw = RawFinding(
        id="defender-alert:a1",
        source="azure_cspm",
        raw_data={
            "type": "defender-alert",
            "data": {
                "id": "alert1",
                "properties": {"severity": "Medium", "alertDisplayName": "Alert"},
            },
        },
        fetched_at=datetime.now(timezone.utc),
        tenant_id="t1",
    )
    record = azure_connector.normalize(raw)
    assert record.severity == "medium"


# ---------------------------------------------------------------------------
# health_check
# ---------------------------------------------------------------------------

def test_health_check_ok(azure_connector: AzureCspmConnector):
    h = azure_connector.health_check()
    assert h.status == "ok"


def test_health_check_degraded(azure_connector: AzureCspmConnector):
    azure_connector._error_count = 3
    h = azure_connector.health_check()
    assert h.status == "degraded"


def test_empty_findings(azure_connector: AzureCspmConnector, valid_creds: dict):
    with respx.mock:
        respx.post(TOKEN_URL).respond(200, json={"access_token": "tok", "expires_in": 3600})
        respx.get(SUB_URL).respond(200, json={"value": []})
        azure_connector.authenticate(valid_creds)
        findings = azure_connector.fetch_findings(datetime.now(timezone.utc), tenant_id="t1")
        assert findings == []
