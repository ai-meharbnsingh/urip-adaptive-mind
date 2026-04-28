"""
Tests for GCP CSPM connector.

Uses respx to mock HTTPX calls to GCP APIs.
"""
from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import patch

import pytest
import respx

from connectors.gcp_cspm.connector import GcpCspmConnector
from connectors.gcp_cspm.api_client import GcpCspmApiClient
from connectors.base.connector import ConnectorAuthError, ConnectorFetchError


@pytest.fixture
def gcp_connector() -> GcpCspmConnector:
    return GcpCspmConnector()


@pytest.fixture
def valid_creds() -> dict:
    return {
        "service_account_json": {
            "type": "service_account",
            "client_email": "test@project.iam.gserviceaccount.com",
            "private_key": "fake-key",
            "token_uri": "https://oauth2.googleapis.com/token",
            "project_id": "test-project",
        }
    }


# ---------------------------------------------------------------------------
# authenticate
# ---------------------------------------------------------------------------

def test_authenticate_success(gcp_connector: GcpCspmConnector, valid_creds: dict):
    with patch.object(GcpCspmApiClient, "_get_access_token", return_value="fake-token"):
        session = gcp_connector.authenticate(valid_creds)
        assert session.connector_name == "gcp_cspm"


def test_authenticate_failure(gcp_connector: GcpCspmConnector, valid_creds: dict):
    with patch.object(GcpCspmApiClient, "_get_access_token", side_effect=Exception("auth failed")):
        with pytest.raises(ConnectorAuthError):
            gcp_connector.authenticate(valid_creds)


def test_authenticate_missing_credentials(gcp_connector: GcpCspmConnector):
    with pytest.raises(ConnectorAuthError):
        gcp_connector.authenticate({})


# ---------------------------------------------------------------------------
# fetch_findings
# ---------------------------------------------------------------------------

@respx.mock
def test_fetch_findings_scc(gcp_connector: GcpCspmConnector, valid_creds: dict):
    respx.get("https://securitycenter.googleapis.com/v1/projects/test-project/sources/-/findings?pageSize=100").respond(
        200, json={"findings": [{"name": "scc-1", "state": "ACTIVE", "severity": "HIGH"}]}
    )
    respx.get("https://cloudasset.googleapis.com/v1/projects/test-project/assets?pageSize=100").respond(200, json={"assets": []})
    respx.get("https://recommender.googleapis.com/v1/projects/test-project/locations/-/recommenders/google.cloud.security/recommendations?pageSize=100").respond(200, json={"recommendations": []})
    with patch.object(GcpCspmApiClient, "_get_access_token", return_value="fake-token"):
        gcp_connector.authenticate(valid_creds)
        findings = gcp_connector.fetch_findings(datetime.now(timezone.utc), tenant_id="t1")
    assert any("scc" in f.id for f in findings)


@respx.mock
def test_fetch_findings_assets(gcp_connector: GcpCspmConnector, valid_creds: dict):
    respx.get("https://securitycenter.googleapis.com/v1/projects/test-project/sources/-/findings?pageSize=100").respond(200, json={"findings": []})
    respx.get("https://cloudasset.googleapis.com/v1/projects/test-project/assets?pageSize=100").respond(
        200, json={"assets": [{"name": "asset-1", "assetType": "compute.googleapis.com/Instance"}]}
    )
    respx.get("https://recommender.googleapis.com/v1/projects/test-project/locations/-/recommenders/google.cloud.security/recommendations?pageSize=100").respond(200, json={"recommendations": []})
    with patch.object(GcpCspmApiClient, "_get_access_token", return_value="fake-token"):
        gcp_connector.authenticate(valid_creds)
        findings = gcp_connector.fetch_findings(datetime.now(timezone.utc), tenant_id="t1")
    assert any("asset" in f.id for f in findings)


@respx.mock
def test_fetch_findings_recommender(gcp_connector: GcpCspmConnector, valid_creds: dict):
    respx.get("https://securitycenter.googleapis.com/v1/projects/test-project/sources/-/findings?pageSize=100").respond(200, json={"findings": []})
    respx.get("https://cloudasset.googleapis.com/v1/projects/test-project/assets?pageSize=100").respond(200, json={"assets": []})
    respx.get("https://recommender.googleapis.com/v1/projects/test-project/locations/-/recommenders/google.cloud.security/recommendations?pageSize=100").respond(
        200, json={"recommendations": [{"name": "rec-1", "priority": "P1"}]}
    )
    with patch.object(GcpCspmApiClient, "_get_access_token", return_value="fake-token"):
        gcp_connector.authenticate(valid_creds)
        findings = gcp_connector.fetch_findings(datetime.now(timezone.utc), tenant_id="t1")
    assert any("recommender" in f.id for f in findings)


def test_fetch_findings_not_authenticated(gcp_connector: GcpCspmConnector):
    with pytest.raises(ConnectorFetchError) as exc_info:
        gcp_connector.fetch_findings(datetime.now(timezone.utc))
    assert "not authenticated" in str(exc_info.value).lower()


# ---------------------------------------------------------------------------
# normalize
# ---------------------------------------------------------------------------

def test_normalize_scc(gcp_connector: GcpCspmConnector, valid_creds: dict):
    with patch.object(GcpCspmApiClient, "_get_access_token", return_value="fake-token"):
        gcp_connector.authenticate(valid_creds)
    from connectors.base.connector import RawFinding
    raw = RawFinding(
        id="scc:scc-1",
        source="gcp_cspm",
        raw_data={
            "type": "scc",
            "data": {"name": "scc-1", "state": "ACTIVE", "severity": "CRITICAL", "category": "Test"},
        },
        fetched_at=datetime.now(timezone.utc),
        tenant_id="t1",
    )
    record = gcp_connector.normalize(raw)
    assert record.severity == "critical"
    assert record.source == "gcp_cspm"


def test_normalize_asset(gcp_connector: GcpCspmConnector, valid_creds: dict):
    with patch.object(GcpCspmApiClient, "_get_access_token", return_value="fake-token"):
        gcp_connector.authenticate(valid_creds)
    from connectors.base.connector import RawFinding
    raw = RawFinding(
        id="asset:asset-1",
        source="gcp_cspm",
        raw_data={
            "type": "asset",
            "data": {"name": "asset-1", "assetType": "compute.googleapis.com/Instance", "iamPolicy": {"bindings": []}},
        },
        fetched_at=datetime.now(timezone.utc),
        tenant_id="t1",
    )
    record = gcp_connector.normalize(raw)
    assert record.severity in ("medium", "low")


def test_normalize_recommender(gcp_connector: GcpCspmConnector, valid_creds: dict):
    with patch.object(GcpCspmApiClient, "_get_access_token", return_value="fake-token"):
        gcp_connector.authenticate(valid_creds)
    from connectors.base.connector import RawFinding
    raw = RawFinding(
        id="recommender:rec-1",
        source="gcp_cspm",
        raw_data={
            "type": "recommender",
            "data": {"name": "rec-1", "priority": "P2", "description": "Fix"},
        },
        fetched_at=datetime.now(timezone.utc),
        tenant_id="t1",
    )
    record = gcp_connector.normalize(raw)
    assert record.severity == "high"


# ---------------------------------------------------------------------------
# health_check
# ---------------------------------------------------------------------------

def test_health_check_ok(gcp_connector: GcpCspmConnector):
    h = gcp_connector.health_check()
    assert h.status == "ok"


def test_health_check_degraded(gcp_connector: GcpCspmConnector):
    gcp_connector._error_count = 4
    h = gcp_connector.health_check()
    assert h.status == "degraded"


@respx.mock
def test_empty_findings(gcp_connector: GcpCspmConnector, valid_creds: dict):
    respx.get("https://securitycenter.googleapis.com/v1/projects/test-project/sources/-/findings").respond(200, json={"findings": []})
    respx.get("https://cloudasset.googleapis.com/v1/projects/test-project/assets").respond(200, json={"assets": []})
    respx.get("https://recommender.googleapis.com/v1/projects/test-project/locations/-/recommenders/google.cloud.security/recommendations").respond(200, json={"recommendations": []})
    with patch.object(GcpCspmApiClient, "_get_access_token", return_value="fake-token"):
        gcp_connector.authenticate(valid_creds)
        findings = gcp_connector.fetch_findings(datetime.now(timezone.utc), tenant_id="t1")
    assert findings == []
