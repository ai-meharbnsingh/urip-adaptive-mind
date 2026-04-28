"""
TDD tests for the CloudSEK live connector.

Uses respx to mock all HTTP traffic — no real API calls.
Coverage: authentication, fetch+pagination per product, normalization,
severity mapping, domain mapping, rate-limit handling, tenant isolation,
enabled_products filtering, health check, error handling (401/403/5xx).
"""

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
from connectors.cloudsek.connector import CloudSekConnector
from connectors.cloudsek.severity_map import CLOUDSEK_ALERT_TYPE_TO_URIP_SEVERITY


# ─────────────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture
def connector() -> CloudSekConnector:
    return CloudSekConnector()


@pytest.fixture
def valid_credentials() -> dict[str, Any]:
    return {
        "api_key": "cs-test-api-key-123",
        "org_id": "org-abc-123",
        "tenant_id": "tenant-cloudsek",
        "api_base": "https://api.cloudsek.com",
        "max_requests_per_minute": 1_000_000,
    }


@pytest.fixture
def custom_base_url() -> str:
    return "https://cloudsek-white-label.example.com"


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _mock_xvigil_alert(
    alert_id: str = "xvigil-001",
    alert_type: str = "leaked_credentials",
    title: str = "Test XVigil Alert",
    asset: dict[str, Any] | None = None,
    threat_actor: str | None = None,
    weaponized: bool = False,
) -> dict[str, Any]:
    return {
        "id": alert_id,
        "alert_type": alert_type,
        "title": title,
        "severity": "critical",
        "asset": asset or {"email": "user@acme.in", "domain": "acme.in"},
        "threat_actor": threat_actor,
        "weaponized": weaponized,
        "created_at": "2024-01-15T10:30:00Z",
        "status": "open",
    }


def _mock_bevigil_finding(
    finding_id: str = "bevigil-001",
    alert_type: str = "hardcoded_secret",
    title: str = "Test BeVigil Finding",
    asset: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "id": finding_id,
        "alert_type": alert_type,
        "title": title,
        "severity": "critical",
        "asset": asset or {"package_name": "com.acme.mobile", "platform": "android"},
        "created_at": "2024-01-15T10:30:00Z",
        "status": "open",
    }


def _mock_svigil_risk(
    risk_id: str = "svigil-001",
    alert_type: str = "vendor_cert_expired",
    title: str = "Test SVigil Risk",
    asset: dict[str, Any] | None = None,
    cvss_score: float | None = None,
) -> dict[str, Any]:
    return {
        "id": risk_id,
        "alert_type": alert_type,
        "title": title,
        "severity": "medium",
        "asset": asset or {"vendor_name": "Acme Cloud"},
        "cvss_score": cvss_score,
        "created_at": "2024-01-15T10:30:00Z",
        "status": "open",
    }


def _mock_paginated_response(
    items: list[dict[str, Any]],
    next_cursor: str | None = None,
    total_items: int = 0,
) -> dict[str, Any]:
    return {
        "data": items,
        "pagination": {
            "next_cursor": next_cursor,
            "total_items": total_items or len(items),
        },
    }


def _auth_route(base_url: str) -> str:
    return f"{base_url}/v1/health"


def _setup_auth_mock(base_url: str) -> None:
    respx.get(_auth_route(base_url)).mock(
        return_value=httpx.Response(200, json={"status": "healthy"})
    )


# ─────────────────────────────────────────────────────────────────────────────
# Tests: Authentication
# ─────────────────────────────────────────────────────────────────────────────

class TestCloudSEKAuthentication:
    @respx.mock
    def test_authenticate_success(self, connector: CloudSekConnector, valid_credentials: dict):
        base = valid_credentials["api_base"]
        route = respx.get(_auth_route(base)).mock(
            return_value=httpx.Response(200, json={"status": "healthy"})
        )
        session = connector.authenticate(valid_credentials)
        assert isinstance(session, ConnectorSession)
        assert session.connector_name == "cloudsek"
        assert session.tenant_id == "tenant-cloudsek"
        assert route.called

    @respx.mock
    def test_authenticate_failure_invalid_keys(self, connector: CloudSekConnector):
        respx.get("https://api.cloudsek.com/v1/health").mock(
            return_value=httpx.Response(401, json={"error": "Unauthorized"})
        )
        with pytest.raises(ConnectorAuthError):
            connector.authenticate({
                "api_key": "bad",
                "org_id": "bad",
                "tenant_id": "t",
                "max_requests_per_minute": 1_000_000,
            })

    def test_authenticate_failure_missing_api_key(self, connector: CloudSekConnector):
        with pytest.raises(ConnectorAuthError):
            connector.authenticate({"org_id": "org-123"})

    def test_authenticate_failure_missing_org_id(self, connector: CloudSekConnector):
        with pytest.raises(ConnectorAuthError):
            connector.authenticate({"api_key": "key-123"})

    @respx.mock
    def test_authenticate_uses_custom_base_url(
        self, connector: CloudSekConnector, custom_base_url: str
    ):
        route = respx.get(f"{custom_base_url}/v1/health").mock(
            return_value=httpx.Response(200, json={"status": "healthy"})
        )
        connector.authenticate({
            "api_key": "key",
            "org_id": "org",
            "api_base": custom_base_url,
            "tenant_id": "t",
            "max_requests_per_minute": 1_000_000,
        })
        assert route.called


# ─────────────────────────────────────────────────────────────────────────────
# Tests: Fetch findings per product
# ─────────────────────────────────────────────────────────────────────────────

class TestCloudSEKFetchFindings:
    @respx.mock
    def test_fetch_xvigil_alerts(self, connector: CloudSekConnector, valid_credentials: dict):
        base = valid_credentials["api_base"]
        _setup_auth_mock(base)
        respx.get(f"{base}/v1/xvigil/alerts").mock(
            return_value=httpx.Response(
                200,
                json=_mock_paginated_response([
                    _mock_xvigil_alert("xv-1", alert_type="leaked_credentials", title="Creds leaked"),
                ]),
            )
        )
        respx.get(f"{base}/v1/bevigil/findings").mock(
            return_value=httpx.Response(200, json=_mock_paginated_response([]))
        )
        respx.get(f"{base}/v1/svigil/risks").mock(
            return_value=httpx.Response(200, json=_mock_paginated_response([]))
        )
        connector.authenticate(valid_credentials)
        findings = connector.fetch_findings(
            since=datetime(2024, 1, 1, tzinfo=timezone.utc),
            tenant_id="tenant-cloudsek",
        )
        xvigil_findings = [f for f in findings if f.raw_data.get("_product") == "xvigil"]
        assert len(xvigil_findings) == 1
        assert xvigil_findings[0].id == "xv-1"

    @respx.mock
    def test_fetch_bevigil_findings(self, connector: CloudSekConnector, valid_credentials: dict):
        base = valid_credentials["api_base"]
        _setup_auth_mock(base)
        respx.get(f"{base}/v1/xvigil/alerts").mock(
            return_value=httpx.Response(200, json=_mock_paginated_response([]))
        )
        respx.get(f"{base}/v1/bevigil/findings").mock(
            return_value=httpx.Response(
                200,
                json=_mock_paginated_response([
                    _mock_bevigil_finding("bv-1", alert_type="hardcoded_secret", title="Key in APK"),
                ]),
            )
        )
        respx.get(f"{base}/v1/svigil/risks").mock(
            return_value=httpx.Response(200, json=_mock_paginated_response([]))
        )
        connector.authenticate(valid_credentials)
        findings = connector.fetch_findings(
            since=datetime(2024, 1, 1, tzinfo=timezone.utc),
            tenant_id="tenant-cloudsek",
        )
        bevigil_findings = [f for f in findings if f.raw_data.get("_product") == "bevigil"]
        assert len(bevigil_findings) == 1
        assert bevigil_findings[0].id == "bv-1"

    @respx.mock
    def test_fetch_svigil_risks(self, connector: CloudSekConnector, valid_credentials: dict):
        base = valid_credentials["api_base"]
        _setup_auth_mock(base)
        respx.get(f"{base}/v1/xvigil/alerts").mock(
            return_value=httpx.Response(200, json=_mock_paginated_response([]))
        )
        respx.get(f"{base}/v1/bevigil/findings").mock(
            return_value=httpx.Response(200, json=_mock_paginated_response([]))
        )
        respx.get(f"{base}/v1/svigil/risks").mock(
            return_value=httpx.Response(
                200,
                json=_mock_paginated_response([
                    _mock_svigil_risk("sv-1", alert_type="vendor_cert_expired", title="Cert expired"),
                ]),
            )
        )
        connector.authenticate(valid_credentials)
        findings = connector.fetch_findings(
            since=datetime(2024, 1, 1, tzinfo=timezone.utc),
            tenant_id="tenant-cloudsek",
        )
        svigil_findings = [f for f in findings if f.raw_data.get("_product") == "svigil"]
        assert len(svigil_findings) == 1
        assert svigil_findings[0].id == "sv-1"


# ─────────────────────────────────────────────────────────────────────────────
# Tests: Pagination
# ─────────────────────────────────────────────────────────────────────────────

class TestCloudSEKPagination:
    @respx.mock
    def test_pagination_cursor_follows_multiple_pages(self, connector: CloudSekConnector, valid_credentials: dict):
        base = valid_credentials["api_base"]
        _setup_auth_mock(base)

        call_count = 0

        def _xvigil_handler(request: httpx.Request):
            nonlocal call_count
            call_count += 1
            cursor = request.url.params.get("cursor")
            if cursor is None:
                return httpx.Response(
                    200,
                    json=_mock_paginated_response(
                        [_mock_xvigil_alert("xv-page1", alert_type="dark_web_mention")],
                        next_cursor="page2",
                        total_items=2,
                    ),
                )
            elif cursor == "page2":
                return httpx.Response(
                    200,
                    json=_mock_paginated_response(
                        [_mock_xvigil_alert("xv-page2", alert_type="dark_web_mention")],
                        next_cursor=None,
                        total_items=2,
                    ),
                )
            return httpx.Response(400, json={"error": "unexpected cursor"})

        respx.get(f"{base}/v1/xvigil/alerts").mock(side_effect=_xvigil_handler)
        respx.get(f"{base}/v1/bevigil/findings").mock(
            return_value=httpx.Response(200, json=_mock_paginated_response([]))
        )
        respx.get(f"{base}/v1/svigil/risks").mock(
            return_value=httpx.Response(200, json=_mock_paginated_response([]))
        )

        connector.authenticate(valid_credentials)
        findings = connector.fetch_findings(
            since=datetime(2024, 1, 1, tzinfo=timezone.utc),
            tenant_id="tenant-cloudsek",
        )
        assert len(findings) == 2
        assert {f.id for f in findings} == {"xv-page1", "xv-page2"}
        assert call_count == 2


# ─────────────────────────────────────────────────────────────────────────────
# Tests: Rate limit
# ─────────────────────────────────────────────────────────────────────────────

class TestCloudSEKRateLimit:
    @respx.mock
    def test_rate_limit_retry_after_respected(self, connector: CloudSekConnector, valid_credentials: dict):
        base = valid_credentials["api_base"]
        _setup_auth_mock(base)

        call_count = 0

        def _xvigil_with_rate_limit(request: httpx.Request):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return httpx.Response(
                    429,
                    headers={"Retry-After": "0"},
                    json={"error": "Rate limited"},
                )
            return httpx.Response(
                200,
                json=_mock_paginated_response([
                    _mock_xvigil_alert("xv-rl", alert_type="brand_abuse"),
                ]),
            )

        respx.get(f"{base}/v1/xvigil/alerts").mock(side_effect=_xvigil_with_rate_limit)
        respx.get(f"{base}/v1/bevigil/findings").mock(
            return_value=httpx.Response(200, json=_mock_paginated_response([]))
        )
        respx.get(f"{base}/v1/svigil/risks").mock(
            return_value=httpx.Response(200, json=_mock_paginated_response([]))
        )

        connector.authenticate(valid_credentials)
        findings = connector.fetch_findings(
            since=datetime(2024, 1, 1, tzinfo=timezone.utc),
            tenant_id="tenant-cloudsek",
        )
        assert len(findings) == 1
        assert findings[0].id == "xv-rl"
        assert call_count == 2


# ─────────────────────────────────────────────────────────────────────────────
# Tests: Severity mapping
# ─────────────────────────────────────────────────────────────────────────────

class TestCloudSEKSeverityMapping:
    def test_severity_leaked_credentials_critical(self, connector: CloudSekConnector):
        raw = RawFinding(
            id="t-1",
            source="cloudsek",
            raw_data={
                "_product": "xvigil",
                "alert_type": "leaked_credentials",
                "title": "Leaked creds",
                "asset": {"email": "a@b.com"},
            },
            fetched_at=datetime.now(timezone.utc),
            tenant_id="t1",
        )
        record = connector.normalize(raw)
        assert record.severity == "critical"

    def test_severity_brand_abuse_high(self, connector: CloudSekConnector):
        raw = RawFinding(
            id="t-2",
            source="cloudsek",
            raw_data={
                "_product": "xvigil",
                "alert_type": "brand_abuse",
                "title": "Fake site",
                "asset": {"domain": "evil.com"},
            },
            fetched_at=datetime.now(timezone.utc),
            tenant_id="t1",
        )
        record = connector.normalize(raw)
        assert record.severity == "high"

    def test_severity_dark_web_mention_medium(self, connector: CloudSekConnector):
        raw = RawFinding(
            id="t-3",
            source="cloudsek",
            raw_data={
                "_product": "xvigil",
                "alert_type": "dark_web_mention",
                "title": "Mention",
                "asset": {"domain": "acme.in"},
            },
            fetched_at=datetime.now(timezone.utc),
            tenant_id="t1",
        )
        record = connector.normalize(raw)
        assert record.severity == "medium"

    def test_severity_hardcoded_secret_critical(self, connector: CloudSekConnector):
        raw = RawFinding(
            id="t-4",
            source="cloudsek",
            raw_data={
                "_product": "bevigil",
                "alert_type": "hardcoded_secret",
                "title": "Secret in APK",
                "asset": {"package_name": "com.acme.mobile"},
            },
            fetched_at=datetime.now(timezone.utc),
            tenant_id="t1",
        )
        record = connector.normalize(raw)
        assert record.severity == "critical"

    def test_severity_exposed_s3_high(self, connector: CloudSekConnector):
        raw = RawFinding(
            id="t-5",
            source="cloudsek",
            raw_data={
                "_product": "bevigil",
                "alert_type": "exposed_s3_bucket",
                "title": "S3 open",
                "asset": {"url": "s3://bucket"},
            },
            fetched_at=datetime.now(timezone.utc),
            tenant_id="t1",
        )
        record = connector.normalize(raw)
        assert record.severity == "high"

    def test_severity_unauth_endpoint_high(self, connector: CloudSekConnector):
        raw = RawFinding(
            id="t-5b",
            source="cloudsek",
            raw_data={
                "_product": "bevigil",
                "alert_type": "unauth_endpoint",
                "title": "Open endpoint",
                "asset": {"url": "https://api.test/admin"},
            },
            fetched_at=datetime.now(timezone.utc),
            tenant_id="t1",
        )
        record = connector.normalize(raw)
        assert record.severity == "high"

    def test_severity_vendor_cve_high(self, connector: CloudSekConnector):
        raw = RawFinding(
            id="t-6",
            source="cloudsek",
            raw_data={
                "_product": "svigil",
                "alert_type": "vendor_critical_cve",
                "title": "Vendor CVE",
                "asset": {"vendor_name": "Acme"},
                "cvss_score": 9.8,
            },
            fetched_at=datetime.now(timezone.utc),
            tenant_id="t1",
        )
        record = connector.normalize(raw)
        assert record.severity == "high"

    def test_severity_vendor_cert_expired_medium(self, connector: CloudSekConnector):
        raw = RawFinding(
            id="t-7",
            source="cloudsek",
            raw_data={
                "_product": "svigil",
                "alert_type": "vendor_cert_expired",
                "title": "Cert expired",
                "asset": {"vendor_name": "Acme"},
            },
            fetched_at=datetime.now(timezone.utc),
            tenant_id="t1",
        )
        record = connector.normalize(raw)
        assert record.severity == "medium"

    def test_severity_unknown_defaults_medium(self, connector: CloudSekConnector):
        raw = RawFinding(
            id="t-8",
            source="cloudsek",
            raw_data={
                "_product": "xvigil",
                "alert_type": "unknown_alert_type",
                "title": "Unknown",
                "asset": {},
            },
            fetched_at=datetime.now(timezone.utc),
            tenant_id="t1",
        )
        record = connector.normalize(raw)
        assert record.severity == "medium"


# ─────────────────────────────────────────────────────────────────────────────
# Tests: Domain mapping
# ─────────────────────────────────────────────────────────────────────────────

class TestCloudSEKDomainMapping:
    def test_domain_xvigil_external_threat(self, connector: CloudSekConnector):
        raw = RawFinding(
            id="d-1",
            source="cloudsek",
            raw_data={"_product": "xvigil", "alert_type": "brand_abuse", "title": "T", "asset": {}},
            fetched_at=datetime.now(timezone.utc),
            tenant_id="t1",
        )
        record = connector.normalize(raw)
        assert record.domain == "external_threat"

    def test_domain_bevigil_application(self, connector: CloudSekConnector):
        raw = RawFinding(
            id="d-2",
            source="cloudsek",
            raw_data={
                "_product": "bevigil",
                "alert_type": "exposed_api",
                "title": "T",
                "asset": {"platform": "web"},
            },
            fetched_at=datetime.now(timezone.utc),
            tenant_id="t1",
        )
        record = connector.normalize(raw)
        assert record.domain == "application"

    def test_domain_bevigil_mobile(self, connector: CloudSekConnector):
        raw = RawFinding(
            id="d-3",
            source="cloudsek",
            raw_data={
                "_product": "bevigil",
                "alert_type": "hardcoded_secret",
                "title": "T",
                "asset": {"platform": "android"},
            },
            fetched_at=datetime.now(timezone.utc),
            tenant_id="t1",
        )
        record = connector.normalize(raw)
        assert record.domain == "mobile"

    def test_domain_svigil_supply_chain(self, connector: CloudSekConnector):
        raw = RawFinding(
            id="d-4",
            source="cloudsek",
            raw_data={"_product": "svigil", "alert_type": "vendor_cert_expired", "title": "T", "asset": {}},
            fetched_at=datetime.now(timezone.utc),
            tenant_id="t1",
        )
        record = connector.normalize(raw)
        assert record.domain == "supply_chain"


# ─────────────────────────────────────────────────────────────────────────────
# Tests: Tenant isolation
# ─────────────────────────────────────────────────────────────────────────────

class TestCloudSEKTenantIsolation:
    @respx.mock
    def test_tenant_isolation_different_credentials(self, connector: CloudSekConnector):
        base = "https://api.cloudsek.com"
        respx.get(f"{base}/v1/health").mock(
            return_value=httpx.Response(200, json={"status": "healthy"})
        )
        respx.get(f"{base}/v1/xvigil/alerts").mock(
            return_value=httpx.Response(
                200,
                json=_mock_paginated_response([
                    _mock_xvigil_alert("xv-tenant-a", alert_type="leaked_credentials"),
                ]),
            )
        )
        respx.get(f"{base}/v1/bevigil/findings").mock(
            return_value=httpx.Response(200, json=_mock_paginated_response([]))
        )
        respx.get(f"{base}/v1/svigil/risks").mock(
            return_value=httpx.Response(200, json=_mock_paginated_response([]))
        )

        creds_a = {
            "api_key": "key-a",
            "org_id": "org-a",
            "tenant_id": "tenant-a",
            "max_requests_per_minute": 1_000_000,
        }
        connector.authenticate(creds_a)
        findings_a = connector.fetch_findings(
            since=datetime(2024, 1, 1, tzinfo=timezone.utc),
            tenant_id="tenant-a",
        )
        assert all(f.tenant_id == "tenant-a" for f in findings_a)
        assert findings_a[0].id == "xv-tenant-a"


# ─────────────────────────────────────────────────────────────────────────────
# Tests: enabled_products subset
# ─────────────────────────────────────────────────────────────────────────────

class TestCloudSEKEnabledProducts:
    @respx.mock
    def test_enabled_products_subset_only_calls_enabled_endpoints(self, connector: CloudSekConnector):
        base = "https://api.cloudsek.com"
        respx.get(f"{base}/v1/health").mock(
            return_value=httpx.Response(200, json={"status": "healthy"})
        )
        xvigil_route = respx.get(f"{base}/v1/xvigil/alerts").mock(
            return_value=httpx.Response(200, json=_mock_paginated_response([]))
        )
        bevigil_route = respx.get(f"{base}/v1/bevigil/findings").mock(
            return_value=httpx.Response(200, json=_mock_paginated_response([]))
        )
        svigil_route = respx.get(f"{base}/v1/svigil/risks").mock(
            return_value=httpx.Response(200, json=_mock_paginated_response([]))
        )

        creds = {
            "api_key": "key",
            "org_id": "org",
            "tenant_id": "t",
            "enabled_products": ["xvigil"],
            "max_requests_per_minute": 1_000_000,
        }
        connector.authenticate(creds)
        connector.fetch_findings(
            since=datetime(2024, 1, 1, tzinfo=timezone.utc),
            tenant_id="t",
        )
        assert xvigil_route.called
        assert not bevigil_route.called
        assert not svigil_route.called


# ─────────────────────────────────────────────────────────────────────────────
# Tests: Health check
# ─────────────────────────────────────────────────────────────────────────────

class TestCloudSEKHealthCheck:
    def test_health_check_ok(self, connector: CloudSekConnector):
        health = connector.health_check()
        assert isinstance(health, ConnectorHealth)
        assert health.connector_name == "cloudsek"
        assert health.status == "ok"
        assert health.error_count == 0

    def test_health_check_degraded_after_errors(self, connector: CloudSekConnector):
        connector._error_count = 2
        health = connector.health_check()
        assert health.status == "degraded"
        assert health.error_count == 2

    def test_health_check_error_after_many_errors(self, connector: CloudSekConnector):
        connector._error_count = 5
        health = connector.health_check()
        assert health.status == "error"
        assert health.error_count == 5

    @respx.mock
    def test_health_check_tracks_products_enabled(self, connector: CloudSekConnector, valid_credentials: dict):
        respx.get("https://api.cloudsek.com/v1/health").mock(
            return_value=httpx.Response(200, json={"status": "healthy"})
        )
        creds_with_products = {
            **valid_credentials,
            "enabled_products": ["xvigil", "bevigil"],
        }
        connector.authenticate(creds_with_products)
        assert connector._products_enabled == ["xvigil", "bevigil"]


# ─────────────────────────────────────────────────────────────────────────────
# Tests: Error handling
# ─────────────────────────────────────────────────────────────────────────────

class TestCloudSEKErrorHandling:
    @respx.mock
    def test_error_401_on_fetch(self, connector: CloudSekConnector, valid_credentials: dict):
        base = valid_credentials["api_base"]
        _setup_auth_mock(base)
        respx.get(f"{base}/v1/xvigil/alerts").mock(
            return_value=httpx.Response(401, json={"error": "Unauthorized"})
        )
        connector.authenticate(valid_credentials)
        with pytest.raises(ConnectorFetchError):
            connector.fetch_findings(
                since=datetime(2024, 1, 1, tzinfo=timezone.utc),
                tenant_id="tenant-cloudsek",
            )

    @respx.mock
    def test_error_403_on_fetch(self, connector: CloudSekConnector, valid_credentials: dict):
        base = valid_credentials["api_base"]
        _setup_auth_mock(base)
        respx.get(f"{base}/v1/xvigil/alerts").mock(
            return_value=httpx.Response(403, json={"error": "Forbidden"})
        )
        connector.authenticate(valid_credentials)
        with pytest.raises(ConnectorFetchError):
            connector.fetch_findings(
                since=datetime(2024, 1, 1, tzinfo=timezone.utc),
                tenant_id="tenant-cloudsek",
            )

    @respx.mock
    def test_error_5xx_on_fetch(self, connector: CloudSekConnector, valid_credentials: dict):
        base = valid_credentials["api_base"]
        _setup_auth_mock(base)
        respx.get(f"{base}/v1/xvigil/alerts").mock(
            return_value=httpx.Response(503, json={"error": "Service Unavailable"})
        )
        connector.authenticate(valid_credentials)
        with pytest.raises(ConnectorFetchError):
            connector.fetch_findings(
                since=datetime(2024, 1, 1, tzinfo=timezone.utc),
                tenant_id="tenant-cloudsek",
            )

    def test_fetch_findings_not_authenticated(self, connector: CloudSekConnector):
        with pytest.raises(ConnectorFetchError):
            connector.fetch_findings(since=datetime.now(timezone.utc))


# ─────────────────────────────────────────────────────────────────────────────
# Tests: Normalization extras
# ─────────────────────────────────────────────────────────────────────────────

class TestCloudSEKNormalizeExtras:
    def test_normalize_exploit_status_active_when_weaponized(self, connector: CloudSekConnector):
        raw = RawFinding(
            id="e-1",
            source="cloudsek",
            raw_data={
                "_product": "xvigil",
                "alert_type": "dark_web_mention",
                "title": "Weaponized mention",
                "asset": {"domain": "acme.in"},
                "weaponized": True,
            },
            fetched_at=datetime.now(timezone.utc),
            tenant_id="t1",
        )
        record = connector.normalize(raw)
        assert record.exploit_status == "active"

    def test_normalize_apt_groups_in_description(self, connector: CloudSekConnector):
        raw = RawFinding(
            id="e-2",
            source="cloudsek",
            raw_data={
                "_product": "xvigil",
                "alert_type": "leaked_credentials",
                "title": "Creds",
                "asset": {"email": "a@b.com"},
                "threat_actor": "APT41",
            },
            fetched_at=datetime.now(timezone.utc),
            tenant_id="t1",
        )
        record = connector.normalize(raw)
        assert "APT41" in record.description

    def test_normalize_includes_finding_title(self, connector: CloudSekConnector):
        raw = RawFinding(
            id="e-3",
            source="cloudsek",
            raw_data={
                "_product": "bevigil",
                "alert_type": "hardcoded_secret",
                "title": "AWS key in APK",
                "asset": {"package_name": "com.acme.mobile"},
            },
            fetched_at=datetime.now(timezone.utc),
            tenant_id="t1",
        )
        record = connector.normalize(raw)
        assert record.finding == "AWS key in APK"

    def test_normalize_sets_source_cloudsek(self, connector: CloudSekConnector):
        raw = RawFinding(
            id="e-4",
            source="cloudsek",
            raw_data={
                "_product": "svigil",
                "alert_type": "vendor_cert_expired",
                "title": "T",
                "asset": {"vendor_name": "V"},
            },
            fetched_at=datetime.now(timezone.utc),
            tenant_id="t1",
        )
        record = connector.normalize(raw)
        assert record.source == "cloudsek"
