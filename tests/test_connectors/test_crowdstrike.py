"""
TDD tests for the CrowdStrike Falcon live connector.

Covers Falcon Spotlight (VM), Falcon Surface (EASM), and Falcon Cloud (CNAPP).

Uses respx to mock all HTTP traffic — no real API calls.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import httpx
import pytest
import respx

from connectors.base.connector import (
    CONNECTOR_CATEGORIES,
    ConnectorAuthError,
    ConnectorFetchError,
    ConnectorHealth,
    ConnectorSession,
    CredentialFieldSpec,
    RawFinding,
    URIPRiskRecord,
)
from connectors.crowdstrike.connector import CrowdStrikeConnector


BASE_US1 = "https://api.crowdstrike.com"
TOKEN_PATH = "/oauth2/token"


# ─────────────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture
def connector() -> CrowdStrikeConnector:
    return CrowdStrikeConnector()


@pytest.fixture
def valid_credentials() -> dict[str, Any]:
    return {
        "client_id": "CSID-1234",
        "client_secret": "CSSECRET-9876",
        "base_url": BASE_US1,
        "tenant_id": "tenant-cs",
        "enabled_products": ["falcon_spotlight", "falcon_easm", "falcon_cnapp"],
    }


def _mock_token_route(base_url: str = BASE_US1, token: str = "tok-abc-123") -> respx.Route:
    return respx.post(f"{base_url}{TOKEN_PATH}").mock(
        return_value=httpx.Response(
            200,
            json={
                "access_token": token,
                "token_type": "bearer",
                "expires_in": 1799,
            },
        )
    )


def _mock_spotlight_query(
    base_url: str = BASE_US1,
    ids: list[str] | None = None,
    next_offset: str | None = None,
) -> respx.Route:
    return respx.get(f"{base_url}/spotlight/queries/vulnerabilities/v1").mock(
        return_value=httpx.Response(
            200,
            json={
                "resources": ids if ids is not None else [],
                "meta": {"pagination": {"offset": next_offset, "total": len(ids or [])}},
            },
        )
    )


def _spotlight_resource(
    rid: str = "spv-1",
    cve: str = "CVE-2024-1111",
    expert_severity: int = 90,
    hostname: str = "ws-001",
    asset_criticality: str = "Critical",
) -> dict[str, Any]:
    return {
        "id": rid,
        "cve": {
            "id": cve,
            "exploit_status": 60,
            "exprt_rating": "CRITICAL",
            "description": f"Test CVE {cve}",
        },
        "host_info": {
            "hostname": hostname,
            "local_ip": "10.0.0.5",
            "agent_id": "agent-xyz-1",
            "tags": [f"FalconGroupingTags/Criticality:{asset_criticality}"],
        },
        "exprt_score": expert_severity,
    }


def _easm_asset(
    aid: str = "easm-1",
    risk: str = "high",
    asset_value: str = "exposed.example.com",
) -> dict[str, Any]:
    return {
        "id": aid,
        "asset_value": asset_value,
        "asset_type": "domain",
        "risk_severity": risk,
        "exposure_type": "exposed_admin_interface",
        "first_seen": "2024-08-01T00:00:00Z",
        "tags": ["external", "production"],
        "exprt_score": 75,
    }


def _cnapp_finding(
    fid: str = "cnapp-1",
    severity: str = "high",
    cloud: str = "aws",
    resource: str = "arn:aws:s3:::public-bucket",
) -> dict[str, Any]:
    return {
        "id": fid,
        "title": "Public S3 bucket",
        "severity": severity,
        "exprt_score": 85,
        "cloud_provider": cloud,
        "resource_id": resource,
        "policy_id": "CIS-S3-1",
        "description": "Bucket is publicly readable",
    }


# ─────────────────────────────────────────────────────────────────────────────
# 1. METADATA assertions (8 required class attrs)
# ─────────────────────────────────────────────────────────────────────────────

class TestCrowdStrikeMetadata:
    def test_all_eight_metadata_attrs_set(self):
        assert CrowdStrikeConnector.DISPLAY_NAME == "CrowdStrike Falcon"
        assert CrowdStrikeConnector.CATEGORY == "EDR"
        assert CrowdStrikeConnector.CATEGORY in CONNECTOR_CATEGORIES
        assert CrowdStrikeConnector.SHORT_DESCRIPTION
        assert isinstance(CrowdStrikeConnector.SHORT_DESCRIPTION, str)
        assert CrowdStrikeConnector.STATUS == "live"
        assert CrowdStrikeConnector.VENDOR_DOCS_URL
        assert CrowdStrikeConnector.VENDOR_DOCS_URL.startswith("https://")
        assert CrowdStrikeConnector.SUPPORTED_PRODUCTS == [
            "falcon_spotlight", "falcon_easm", "falcon_cnapp",
        ]
        assert CrowdStrikeConnector.MODULE_CODE == "EDR"
        assert isinstance(CrowdStrikeConnector.CREDENTIAL_FIELDS, list)
        assert len(CrowdStrikeConnector.CREDENTIAL_FIELDS) >= 3
        for f in CrowdStrikeConnector.CREDENTIAL_FIELDS:
            assert isinstance(f, CredentialFieldSpec)
        # Required credential fields present
        names = [f.name for f in CrowdStrikeConnector.CREDENTIAL_FIELDS]
        assert "client_id" in names
        assert "client_secret" in names

    def test_registered_in_global_registry(self):
        from connectors.base.registry import _global_registry
        assert "crowdstrike" in _global_registry
        cls = _global_registry.get("crowdstrike")
        assert cls is CrowdStrikeConnector


# ─────────────────────────────────────────────────────────────────────────────
# 2. OAuth2 token acquisition + cache
# ─────────────────────────────────────────────────────────────────────────────

class TestCrowdStrikeOAuth:
    @respx.mock
    def test_oauth_token_acquired_on_authenticate(
        self, connector: CrowdStrikeConnector, valid_credentials: dict
    ):
        token_route = _mock_token_route()
        # Spotlight is queried by validate_auth (HEAD-style probe — we use a cheap call)
        respx.get(f"{BASE_US1}/spotlight/queries/vulnerabilities/v1").mock(
            return_value=httpx.Response(
                200, json={"resources": [], "meta": {"pagination": {"offset": "", "total": 0}}}
            )
        )
        session = connector.authenticate(valid_credentials)
        assert isinstance(session, ConnectorSession)
        assert session.connector_name == "crowdstrike"
        assert token_route.called

    @respx.mock
    def test_oauth_token_cached_between_calls(
        self, connector: CrowdStrikeConnector, valid_credentials: dict
    ):
        token_route = _mock_token_route()
        respx.get(f"{BASE_US1}/spotlight/queries/vulnerabilities/v1").mock(
            return_value=httpx.Response(
                200, json={"resources": [], "meta": {"pagination": {"offset": "", "total": 0}}}
            )
        )
        respx.get(f"{BASE_US1}/falcon-surface/queries/external-assets/v1").mock(
            return_value=httpx.Response(
                200, json={"resources": [], "meta": {"pagination": {"offset": "", "total": 0}}}
            )
        )
        respx.get(f"{BASE_US1}/cnapp/queries/findings/v1").mock(
            return_value=httpx.Response(
                200, json={"resources": [], "meta": {"pagination": {"offset": "", "total": 0}}}
            )
        )
        connector.authenticate(valid_credentials)
        connector.fetch_findings(
            since=datetime(2024, 1, 1, tzinfo=timezone.utc),
            tenant_id="tenant-cs",
        )
        # OAuth was called once during authenticate; cache means fetch should not re-acquire
        assert token_route.call_count == 1

    @respx.mock
    def test_oauth_invalid_credentials_raises_auth_error(
        self, connector: CrowdStrikeConnector
    ):
        respx.post(f"{BASE_US1}{TOKEN_PATH}").mock(
            return_value=httpx.Response(401, json={"errors": [{"message": "bad creds"}]})
        )
        with pytest.raises(ConnectorAuthError):
            connector.authenticate(
                {
                    "client_id": "bad",
                    "client_secret": "bad",
                    "base_url": BASE_US1,
                    "tenant_id": "t",
                }
            )

    def test_oauth_missing_client_id(self, connector: CrowdStrikeConnector):
        with pytest.raises(ConnectorAuthError):
            connector.authenticate(
                {"client_secret": "x", "base_url": BASE_US1}
            )

    def test_oauth_missing_client_secret(self, connector: CrowdStrikeConnector):
        with pytest.raises(ConnectorAuthError):
            connector.authenticate(
                {"client_id": "x", "base_url": BASE_US1}
            )

    @respx.mock
    def test_oauth_refresh_on_401(
        self, connector: CrowdStrikeConnector, valid_credentials: dict
    ):
        """When a downstream API returns 401, the client should refresh the token and retry."""
        # Authenticate with first token
        token_calls = []

        def _token_handler(request: httpx.Request):
            token_calls.append(1)
            tok = f"tok-v{len(token_calls)}"
            return httpx.Response(
                200,
                json={"access_token": tok, "token_type": "bearer", "expires_in": 1799},
            )

        respx.post(f"{BASE_US1}{TOKEN_PATH}").mock(side_effect=_token_handler)

        spotlight_calls = []

        def _spotlight_handler(request: httpx.Request):
            spotlight_calls.append(request.headers.get("authorization"))
            if len(spotlight_calls) == 1:
                # First call returns 401 -> trigger refresh
                return httpx.Response(401, json={"errors": [{"message": "expired"}]})
            return httpx.Response(
                200, json={"resources": [], "meta": {"pagination": {"offset": "", "total": 0}}}
            )

        respx.get(f"{BASE_US1}/spotlight/queries/vulnerabilities/v1").mock(
            side_effect=_spotlight_handler
        )
        respx.get(f"{BASE_US1}/falcon-surface/queries/external-assets/v1").mock(
            return_value=httpx.Response(
                200, json={"resources": [], "meta": {"pagination": {"offset": "", "total": 0}}}
            )
        )
        respx.get(f"{BASE_US1}/cnapp/queries/findings/v1").mock(
            return_value=httpx.Response(
                200, json={"resources": [], "meta": {"pagination": {"offset": "", "total": 0}}}
            )
        )

        connector.authenticate(valid_credentials)
        connector.fetch_findings(
            since=datetime(2024, 1, 1, tzinfo=timezone.utc),
            tenant_id="tenant-cs",
        )
        # Two token acquisitions (auth + refresh after 401)
        assert len(token_calls) == 2
        # Spotlight retried with new token
        assert len(spotlight_calls) == 2


# ─────────────────────────────────────────────────────────────────────────────
# 3. Per-product fetch + 'enabled_products' subset filtering
# ─────────────────────────────────────────────────────────────────────────────

class TestCrowdStrikeFetchProducts:
    @respx.mock
    def test_fetch_falcon_spotlight_only(
        self, connector: CrowdStrikeConnector
    ):
        _mock_token_route()
        # Spotlight: queries returns IDs, then details endpoint returns full vulns
        respx.get(f"{BASE_US1}/spotlight/queries/vulnerabilities/v1").mock(
            return_value=httpx.Response(
                200,
                json={
                    "resources": ["spv-1", "spv-2"],
                    "meta": {"pagination": {"offset": "", "total": 2}},
                },
            )
        )
        respx.get(f"{BASE_US1}/spotlight/entities/vulnerabilities/v2").mock(
            return_value=httpx.Response(
                200,
                json={
                    "resources": [
                        _spotlight_resource("spv-1"),
                        _spotlight_resource("spv-2", cve="CVE-2024-2222", expert_severity=70),
                    ],
                },
            )
        )

        creds = {
            "client_id": "cid",
            "client_secret": "cs",
            "base_url": BASE_US1,
            "enabled_products": ["falcon_spotlight"],
            "tenant_id": "t1",
        }
        connector.authenticate(creds)
        findings = connector.fetch_findings(
            since=datetime(2024, 1, 1, tzinfo=timezone.utc),
            tenant_id="t1",
        )
        assert len(findings) == 2
        assert all(f.source == "crowdstrike:falcon_spotlight" for f in findings)
        assert {f.id for f in findings} == {"spv-1", "spv-2"}

    @respx.mock
    def test_fetch_falcon_easm_only(self, connector: CrowdStrikeConnector):
        _mock_token_route()
        respx.get(f"{BASE_US1}/falcon-surface/queries/external-assets/v1").mock(
            return_value=httpx.Response(
                200,
                json={
                    "resources": [_easm_asset("easm-A"), _easm_asset("easm-B", risk="critical")],
                    "meta": {"pagination": {"offset": "", "total": 2}},
                },
            )
        )

        creds = {
            "client_id": "cid",
            "client_secret": "cs",
            "base_url": BASE_US1,
            "enabled_products": ["falcon_easm"],
            "tenant_id": "t1",
        }
        connector.authenticate(creds)
        findings = connector.fetch_findings(
            since=datetime(2024, 1, 1, tzinfo=timezone.utc),
            tenant_id="t1",
        )
        assert len(findings) == 2
        assert all(f.source == "crowdstrike:falcon_easm" for f in findings)

    @respx.mock
    def test_fetch_falcon_cnapp_only(self, connector: CrowdStrikeConnector):
        _mock_token_route()
        respx.get(f"{BASE_US1}/cnapp/queries/findings/v1").mock(
            return_value=httpx.Response(
                200,
                json={
                    "resources": [_cnapp_finding("c-1"), _cnapp_finding("c-2", severity="critical")],
                    "meta": {"pagination": {"offset": "", "total": 2}},
                },
            )
        )

        creds = {
            "client_id": "cid",
            "client_secret": "cs",
            "base_url": BASE_US1,
            "enabled_products": ["falcon_cnapp"],
            "tenant_id": "t1",
        }
        connector.authenticate(creds)
        findings = connector.fetch_findings(
            since=datetime(2024, 1, 1, tzinfo=timezone.utc),
            tenant_id="t1",
        )
        assert len(findings) == 2
        assert all(f.source == "crowdstrike:falcon_cnapp" for f in findings)

    @respx.mock
    def test_enabled_products_subset_filters_endpoints(
        self, connector: CrowdStrikeConnector
    ):
        """When only spotlight is enabled, EASM + CNAPP endpoints must NOT be hit."""
        _mock_token_route()
        spotlight_q = respx.get(f"{BASE_US1}/spotlight/queries/vulnerabilities/v1").mock(
            return_value=httpx.Response(
                200, json={"resources": [], "meta": {"pagination": {"offset": "", "total": 0}}}
            )
        )
        easm_route = respx.get(f"{BASE_US1}/falcon-surface/queries/external-assets/v1").mock(
            return_value=httpx.Response(
                200, json={"resources": [], "meta": {"pagination": {"offset": "", "total": 0}}}
            )
        )
        cnapp_route = respx.get(f"{BASE_US1}/cnapp/queries/findings/v1").mock(
            return_value=httpx.Response(
                200, json={"resources": [], "meta": {"pagination": {"offset": "", "total": 0}}}
            )
        )

        creds = {
            "client_id": "cid",
            "client_secret": "cs",
            "base_url": BASE_US1,
            "enabled_products": ["falcon_spotlight"],
            "tenant_id": "t1",
        }
        connector.authenticate(creds)
        connector.fetch_findings(since=datetime(2024, 1, 1, tzinfo=timezone.utc), tenant_id="t1")

        assert spotlight_q.called
        assert not easm_route.called
        assert not cnapp_route.called


# ─────────────────────────────────────────────────────────────────────────────
# 4. Pagination across multiple pages (Spotlight uses meta.pagination.offset)
# ─────────────────────────────────────────────────────────────────────────────

class TestCrowdStrikePagination:
    @respx.mock
    def test_spotlight_pagination_two_pages(self, connector: CrowdStrikeConnector):
        _mock_token_route()

        page_calls = []

        def _q_handler(request: httpx.Request):
            offset = request.url.params.get("offset", "")
            page_calls.append(offset)
            if not offset:
                return httpx.Response(
                    200,
                    json={
                        "resources": ["spv-1"],
                        "meta": {"pagination": {"offset": "abcdef", "total": 2}},
                    },
                )
            elif offset == "abcdef":
                return httpx.Response(
                    200,
                    json={
                        "resources": ["spv-2"],
                        "meta": {"pagination": {"offset": "", "total": 2}},
                    },
                )
            return httpx.Response(400)

        respx.get(f"{BASE_US1}/spotlight/queries/vulnerabilities/v1").mock(side_effect=_q_handler)

        def _details_handler(request: httpx.Request):
            ids = request.url.params.get_list("ids") or []
            return httpx.Response(
                200,
                json={"resources": [_spotlight_resource(rid=i, cve=f"CVE-2024-{i}") for i in ids]},
            )

        respx.get(f"{BASE_US1}/spotlight/entities/vulnerabilities/v2").mock(
            side_effect=_details_handler
        )

        creds = {
            "client_id": "cid", "client_secret": "cs", "base_url": BASE_US1,
            "enabled_products": ["falcon_spotlight"], "tenant_id": "t1",
        }
        connector.authenticate(creds)
        findings = connector.fetch_findings(
            since=datetime(2024, 1, 1, tzinfo=timezone.utc), tenant_id="t1",
        )
        assert len(findings) == 2
        assert len(page_calls) == 2


# ─────────────────────────────────────────────────────────────────────────────
# 5. ExPRT severity mapping
# ─────────────────────────────────────────────────────────────────────────────

class TestCrowdStrikeSeverityMapping:
    @pytest.mark.parametrize(
        "exprt,expected",
        [
            (95, "critical"),
            (80, "critical"),
            (79, "high"),
            (60, "high"),
            (59, "medium"),
            (30, "medium"),
            (29, "low"),
            (0, "low"),
        ],
    )
    def test_exprt_to_urip_severity_mapping(
        self, connector: CrowdStrikeConnector, exprt: int, expected: str
    ):
        raw = RawFinding(
            id=f"sp-{exprt}",
            source="crowdstrike:falcon_spotlight",
            raw_data=_spotlight_resource(rid=f"sp-{exprt}", expert_severity=exprt),
            fetched_at=datetime.now(timezone.utc),
            tenant_id="t1",
        )
        record = connector.normalize(raw)
        assert record.severity == expected


# ─────────────────────────────────────────────────────────────────────────────
# 6. Normalization correctness
# ─────────────────────────────────────────────────────────────────────────────

class TestCrowdStrikeNormalize:
    def test_normalize_spotlight_includes_hostname_and_ip(
        self, connector: CrowdStrikeConnector
    ):
        raw_resource = _spotlight_resource(
            rid="spv-100",
            cve="CVE-2024-9999",
            expert_severity=92,
            hostname="finance-srv-01",
            asset_criticality="Critical",
        )
        raw = RawFinding(
            id="spv-100",
            source="crowdstrike:falcon_spotlight",
            raw_data=raw_resource,
            fetched_at=datetime.now(timezone.utc),
            tenant_id="t1",
        )
        record = connector.normalize(raw)
        assert isinstance(record, URIPRiskRecord)
        assert record.severity == "critical"
        assert record.cve_id == "CVE-2024-9999"
        assert "finance-srv-01" in record.asset
        assert record.source == "crowdstrike:falcon_spotlight"
        assert record.domain == "endpoint"
        assert record.asset_tier == 1  # Critical asset → tier 1

    def test_normalize_easm_finding(self, connector: CrowdStrikeConnector):
        raw = RawFinding(
            id="easm-X",
            source="crowdstrike:falcon_easm",
            raw_data=_easm_asset("easm-X", risk="high", asset_value="exposed.test.com"),
            fetched_at=datetime.now(timezone.utc),
            tenant_id="t1",
        )
        record = connector.normalize(raw)
        assert record.source == "crowdstrike:falcon_easm"
        assert record.domain == "external_attack_surface"
        assert "exposed.test.com" in record.asset
        # exprt_score=75 → high
        assert record.severity == "high"

    def test_normalize_cnapp_misconfig(self, connector: CrowdStrikeConnector):
        raw = RawFinding(
            id="cnapp-Z",
            source="crowdstrike:falcon_cnapp",
            raw_data=_cnapp_finding(
                "cnapp-Z", severity="high", cloud="aws",
                resource="arn:aws:s3:::leaky-bucket",
            ),
            fetched_at=datetime.now(timezone.utc),
            tenant_id="t1",
        )
        record = connector.normalize(raw)
        assert record.source == "crowdstrike:falcon_cnapp"
        assert record.domain == "cloud"
        assert "leaky-bucket" in record.asset
        # exprt_score=85 → critical
        assert record.severity == "critical"


# ─────────────────────────────────────────────────────────────────────────────
# 7. Tenant isolation
# ─────────────────────────────────────────────────────────────────────────────

class TestCrowdStrikeTenantIsolation:
    @respx.mock
    def test_tenants_with_different_credentials_do_not_share_data(self):
        # Tenant A on US-1
        _mock_token_route(BASE_US1, token="tokA")
        respx.get(f"{BASE_US1}/spotlight/queries/vulnerabilities/v1").mock(
            return_value=httpx.Response(
                200, json={"resources": [], "meta": {"pagination": {"offset": "", "total": 0}}}
            )
        )

        # Tenant B on EU-1
        BASE_EU1 = "https://api.eu-1.crowdstrike.com"
        _mock_token_route(BASE_EU1, token="tokB")
        respx.get(f"{BASE_EU1}/spotlight/queries/vulnerabilities/v1").mock(
            return_value=httpx.Response(
                200, json={"resources": [], "meta": {"pagination": {"offset": "", "total": 0}}}
            )
        )

        a = CrowdStrikeConnector()
        sess_a = a.authenticate(
            {"client_id": "A", "client_secret": "AS", "base_url": BASE_US1,
             "enabled_products": ["falcon_spotlight"], "tenant_id": "tenant-a"}
        )
        a.fetch_findings(
            since=datetime(2024, 1, 1, tzinfo=timezone.utc), tenant_id="tenant-a",
        )

        b = CrowdStrikeConnector()
        sess_b = b.authenticate(
            {"client_id": "B", "client_secret": "BS", "base_url": BASE_EU1,
             "enabled_products": ["falcon_spotlight"], "tenant_id": "tenant-b"}
        )
        b.fetch_findings(
            since=datetime(2024, 1, 1, tzinfo=timezone.utc), tenant_id="tenant-b",
        )

        assert sess_a.tenant_id == "tenant-a"
        assert sess_b.tenant_id == "tenant-b"


# ─────────────────────────────────────────────────────────────────────────────
# 8. Health check
# ─────────────────────────────────────────────────────────────────────────────

class TestCrowdStrikeHealth:
    def test_health_check_fresh_connector_ok(self, connector: CrowdStrikeConnector):
        h = connector.health_check()
        assert isinstance(h, ConnectorHealth)
        assert h.connector_name == "crowdstrike"
        assert h.status == "ok"
        assert h.last_run is None
        assert h.error_count == 0

    @respx.mock
    def test_health_check_degraded_after_some_errors(
        self, connector: CrowdStrikeConnector, valid_credentials: dict
    ):
        _mock_token_route()
        respx.get(f"{BASE_US1}/spotlight/queries/vulnerabilities/v1").mock(
            return_value=httpx.Response(500, json={"errors": [{"message": "boom"}]})
        )
        respx.get(f"{BASE_US1}/falcon-surface/queries/external-assets/v1").mock(
            return_value=httpx.Response(500, json={"errors": [{"message": "boom"}]})
        )
        respx.get(f"{BASE_US1}/cnapp/queries/findings/v1").mock(
            return_value=httpx.Response(500, json={"errors": [{"message": "boom"}]})
        )
        connector.authenticate(valid_credentials)
        for _ in range(3):
            try:
                connector.fetch_findings(
                    since=datetime(2024, 1, 1, tzinfo=timezone.utc), tenant_id="t",
                )
            except ConnectorFetchError:
                pass
        h = connector.health_check()
        assert h.status == "degraded"
        assert h.error_count >= 1

    @respx.mock
    def test_health_check_last_run_after_success(
        self, connector: CrowdStrikeConnector, valid_credentials: dict
    ):
        _mock_token_route()
        respx.get(f"{BASE_US1}/spotlight/queries/vulnerabilities/v1").mock(
            return_value=httpx.Response(
                200, json={"resources": [], "meta": {"pagination": {"offset": "", "total": 0}}}
            )
        )
        respx.get(f"{BASE_US1}/falcon-surface/queries/external-assets/v1").mock(
            return_value=httpx.Response(
                200, json={"resources": [], "meta": {"pagination": {"offset": "", "total": 0}}}
            )
        )
        respx.get(f"{BASE_US1}/cnapp/queries/findings/v1").mock(
            return_value=httpx.Response(
                200, json={"resources": [], "meta": {"pagination": {"offset": "", "total": 0}}}
            )
        )
        connector.authenticate(valid_credentials)
        connector.fetch_findings(
            since=datetime(2024, 1, 1, tzinfo=timezone.utc), tenant_id="tenant-cs",
        )
        h = connector.health_check()
        assert h.last_run is not None
