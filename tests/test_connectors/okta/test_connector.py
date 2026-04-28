"""
TDD tests for the Okta Workforce Identity live connector.

Uses respx to mock all HTTP traffic — no real API calls.

Coverage (13 tests):
  1.  test_register                             — "okta" key in global registry
  2.  test_authenticate_with_valid_token        — SSWS header verified
  3.  test_authenticate_invalid_token_raises_auth_error  — 401 raises
  4.  test_fetch_system_log_events              — mock /api/v1/logs response
  5.  test_fetch_respects_since_parameter       — since= ISO8601 in URL
  6.  test_fetch_handles_pagination             — Link header cursor
  7.  test_normalize_account_lock_severity_high
  8.  test_normalize_policy_deny_severity_medium
  9.  test_normalize_admin_app_access_severity_high
  10. test_normalize_default_severity_low
  11. test_health_check_ok                      — 200 from /me
  12. test_health_check_degraded                — 5xx from /me
  13. test_credential_secrets_marked            — api_token has secret=True
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from urllib.parse import parse_qs, urlparse

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
from connectors.okta.connector import OktaConnector, _map_severity, _parse_event_types_from_filter
from connectors.okta.schemas import OktaSystemLogEvent

# ─────────────────────────────────────────────────────────────────────────────
# Constants
# ─────────────────────────────────────────────────────────────────────────────

DOMAIN = "urip-test.okta.com"
BASE = f"https://{DOMAIN}"

# ─────────────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────────────


@pytest.fixture
def connector() -> OktaConnector:
    return OktaConnector()


@pytest.fixture
def valid_creds() -> dict[str, str]:
    return {
        "domain": DOMAIN,
        "api_token": "00FAKE_SSWS_TOKEN",
        "log_event_filter": (
            'eventType eq "user.account.lock" or '
            'eventType eq "user.session.access_admin_app" or '
            'eventType eq "policy.evaluate_sign_on"'
        ),
        "tenant_id": "tenant-okta-test",
    }


# ─────────────────────────────────────────────────────────────────────────────
# Helpers — sample payloads
# ─────────────────────────────────────────────────────────────────────────────


def _me_response(user_id: str = "00u1abc123") -> dict[str, Any]:
    return {
        "id": user_id,
        "login": "svc-urip@corp.example.com",
        "status": "ACTIVE",
        "profile": {"login": "svc-urip@corp.example.com", "email": "svc-urip@corp.example.com"},
    }


def _log_event(
    uuid: str = "aaa-bbb-ccc",
    event_type: str = "user.account.lock",
    severity: str = "WARN",
    outcome_result: str = "FAILURE",
    actor_email: str = "attacker@evil.com",
) -> dict[str, Any]:
    return {
        "uuid": uuid,
        "published": "2026-04-28T09:15:42.000Z",
        "eventType": event_type,
        "severity": severity,
        "displayMessage": f"Event: {event_type}",
        "actor": {
            "id": "00u1actor",
            "type": "User",
            "alternateId": actor_email,
            "displayName": "Test Actor",
        },
        "target": [
            {
                "id": "00u1target",
                "type": "User",
                "alternateId": "victim@corp.com",
                "displayName": "Victim User",
            }
        ],
        "outcome": {"result": outcome_result, "reason": "LOCKED_OUT"},
        "client": {},
    }


def _raw_finding(event: dict[str, Any]) -> RawFinding:
    return RawFinding(
        id=event["uuid"],
        source="okta",
        raw_data=event,
        fetched_at=datetime.now(timezone.utc),
        tenant_id="tenant-okta-test",
    )


# ─────────────────────────────────────────────────────────────────────────────
# 1. Registration
# ─────────────────────────────────────────────────────────────────────────────


class TestOktaRegistration:
    def test_register(self):
        """OktaConnector must be registered under the 'okta' key."""
        assert "okta" in _global_registry, (
            "'okta' not found in registry — check that connector_loader imports "
            "connectors.okta.connector"
        )
        factory = _global_registry.get("okta")
        instance = factory()
        assert isinstance(instance, OktaConnector)

    def test_metadata(self):
        """Catalog metadata must be populated correctly."""
        assert OktaConnector.NAME == "okta"
        assert OktaConnector.DISPLAY_NAME == "Okta Workforce Identity"
        assert OktaConnector.CATEGORY == "IDENTITY"
        assert OktaConnector.STATUS == "live"
        assert OktaConnector.MODULE_CODE == "IDENTITY"
        assert OktaConnector.RISK_INDEX_DOMAIN == "identity"
        assert "Okta Workforce Identity Cloud" in (OktaConnector.SUPPORTED_PRODUCTS or [])


# ─────────────────────────────────────────────────────────────────────────────
# 2. Authentication — valid token
# ─────────────────────────────────────────────────────────────────────────────


class TestOktaAuthenticate:
    @respx.mock
    def test_authenticate_with_valid_token(
        self, connector: OktaConnector, valid_creds: dict
    ) -> None:
        """SSWS token must appear in the Authorization header."""
        route = respx.get(f"{BASE}/api/v1/users/me").mock(
            return_value=httpx.Response(200, json=_me_response())
        )
        session = connector.authenticate(valid_creds)

        assert isinstance(session, ConnectorSession)
        assert session.connector_name == "okta"
        assert session.tenant_id == "tenant-okta-test"
        assert "okta-ssws" in session.token
        assert route.called

        # Verify the SSWS header
        sent_request = route.calls[0].request
        auth_header = sent_request.headers.get("authorization", "")
        assert auth_header == f"SSWS {valid_creds['api_token']}", (
            f"Expected SSWS header, got: {auth_header!r}"
        )

    @respx.mock
    def test_authenticate_invalid_token_raises_auth_error(
        self, connector: OktaConnector, valid_creds: dict
    ) -> None:
        """401 response from /api/v1/users/me must raise ConnectorAuthError."""
        respx.get(f"{BASE}/api/v1/users/me").mock(
            return_value=httpx.Response(
                401,
                json={"errorCode": "E0000011", "errorSummary": "Invalid token provided"},
            )
        )
        with pytest.raises(ConnectorAuthError):
            connector.authenticate(valid_creds)

    @respx.mock
    def test_authenticate_403_raises_auth_error(
        self, connector: OktaConnector, valid_creds: dict
    ) -> None:
        """403 response must also raise ConnectorAuthError."""
        respx.get(f"{BASE}/api/v1/users/me").mock(
            return_value=httpx.Response(
                403,
                json={"errorCode": "E0000006", "errorSummary": "You do not have permission"},
            )
        )
        with pytest.raises(ConnectorAuthError):
            connector.authenticate(valid_creds)

    def test_authenticate_missing_domain_raises(self, connector: OktaConnector) -> None:
        with pytest.raises(ConnectorAuthError, match="domain"):
            connector.authenticate({"api_token": "tok"})

    def test_authenticate_missing_token_raises(self, connector: OktaConnector) -> None:
        with pytest.raises(ConnectorAuthError, match="api_token"):
            connector.authenticate({"domain": DOMAIN})


# ─────────────────────────────────────────────────────────────────────────────
# 3. fetch_findings — System Log events
# ─────────────────────────────────────────────────────────────────────────────


class TestOktaFetchFindings:
    @respx.mock
    def test_fetch_system_log_events(
        self, connector: OktaConnector, valid_creds: dict
    ) -> None:
        """fetch_findings must call GET /api/v1/logs and return RawFinding objects."""
        respx.get(f"{BASE}/api/v1/users/me").mock(
            return_value=httpx.Response(200, json=_me_response())
        )
        log_route = respx.get(f"{BASE}/api/v1/logs").mock(
            return_value=httpx.Response(
                200,
                json=[
                    _log_event("uuid-001", "user.account.lock"),
                    _log_event("uuid-002", "policy.evaluate_sign_on"),
                ],
                headers={"Content-Type": "application/json"},
            )
        )

        connector.authenticate(valid_creds)
        findings = connector.fetch_findings(
            since=datetime(2026, 4, 1, tzinfo=timezone.utc),
            tenant_id="tenant-okta-test",
        )

        assert len(findings) == 2
        assert findings[0].source == "okta"
        assert findings[0].id == "uuid-001"
        assert findings[1].id == "uuid-002"
        assert findings[0].tenant_id == "tenant-okta-test"
        assert log_route.called

    @respx.mock
    def test_fetch_respects_since_parameter(
        self, connector: OktaConnector, valid_creds: dict
    ) -> None:
        """The `since` datetime must appear as ISO8601 in the query string."""
        respx.get(f"{BASE}/api/v1/users/me").mock(
            return_value=httpx.Response(200, json=_me_response())
        )
        log_route = respx.get(f"{BASE}/api/v1/logs").mock(
            return_value=httpx.Response(200, json=[_log_event("uuid-since")])
        )

        since_dt = datetime(2026, 4, 20, 12, 0, 0, tzinfo=timezone.utc)
        connector.authenticate(valid_creds)
        connector.fetch_findings(since=since_dt)

        assert log_route.called
        # Inspect the URL that was sent
        sent_url = str(log_route.calls[0].request.url)
        assert "since=" in sent_url, f"Expected 'since=' in URL, got: {sent_url}"
        assert "2026-04-20" in sent_url, (
            f"Expected ISO date 2026-04-20 in URL, got: {sent_url}"
        )

    @respx.mock
    def test_fetch_handles_pagination(
        self, connector: OktaConnector, valid_creds: dict
    ) -> None:
        """A Link: <next_url>; rel='next' header must trigger a second request."""
        import re as _re

        respx.get(f"{BASE}/api/v1/users/me").mock(
            return_value=httpx.Response(200, json=_me_response())
        )

        page1_url = f"{BASE}/api/v1/logs"
        page2_url = f"{BASE}/api/v1/logs?after=cursor_abc"

        # First page (matches path /api/v1/logs with query params) — has a Link next header
        respx.get(url__regex=r"/api/v1/logs").mock(
            side_effect=[
                httpx.Response(
                    200,
                    json=[_log_event("uuid-page1")],
                    headers={
                        "Content-Type": "application/json",
                        "link": f'<{page2_url}>; rel="next", <{page1_url}>; rel="self"',
                    },
                ),
                # Second page — no next header
                httpx.Response(
                    200,
                    json=[_log_event("uuid-page2")],
                    headers={"Content-Type": "application/json"},
                ),
            ]
        )

        connector.authenticate(valid_creds)
        findings = connector.fetch_findings(
            since=datetime(2026, 4, 1, tzinfo=timezone.utc)
        )

        assert len(findings) == 2
        ids = {f.id for f in findings}
        assert "uuid-page1" in ids
        assert "uuid-page2" in ids

    def test_fetch_not_authenticated_raises(self, connector: OktaConnector) -> None:
        with pytest.raises(ConnectorFetchError, match="not authenticated"):
            connector.fetch_findings(since=datetime.now(timezone.utc))

    @respx.mock
    def test_fetch_5xx_raises(
        self, connector: OktaConnector, valid_creds: dict
    ) -> None:
        respx.get(f"{BASE}/api/v1/users/me").mock(
            return_value=httpx.Response(200, json=_me_response())
        )
        respx.get(f"{BASE}/api/v1/logs").mock(
            return_value=httpx.Response(503, text="Service Unavailable")
        )
        connector.authenticate(valid_creds)
        with pytest.raises(ConnectorFetchError):
            connector.fetch_findings(since=datetime.now(timezone.utc))


# ─────────────────────────────────────────────────────────────────────────────
# 4. Normalization — severity mapping
# ─────────────────────────────────────────────────────────────────────────────


class TestOktaNormalize:
    def test_normalize_account_lock_severity_high(
        self, connector: OktaConnector
    ) -> None:
        """user.account.lock must map to severity='high'."""
        connector._domain = DOMAIN
        raw = _raw_finding(_log_event("u1", "user.account.lock"))
        record = connector.normalize(raw)
        assert isinstance(record, URIPRiskRecord)
        assert record.severity == "high", (
            f"user.account.lock should be 'high', got {record.severity!r}"
        )
        assert record.source == "okta"
        assert record.domain == "identity"

    def test_normalize_policy_deny_severity_medium(
        self, connector: OktaConnector
    ) -> None:
        """policy.evaluate_sign_on with outcome.DENY must map to severity='medium'."""
        connector._domain = DOMAIN
        raw = _raw_finding(
            _log_event("u2", "policy.evaluate_sign_on", outcome_result="DENY")
        )
        record = connector.normalize(raw)
        assert record.severity == "medium", (
            f"policy.evaluate_sign_on/DENY should be 'medium', got {record.severity!r}"
        )

    def test_normalize_admin_app_access_severity_high(
        self, connector: OktaConnector
    ) -> None:
        """user.session.access_admin_app must map to severity='high'."""
        connector._domain = DOMAIN
        raw = _raw_finding(_log_event("u3", "user.session.access_admin_app"))
        record = connector.normalize(raw)
        assert record.severity == "high", (
            f"user.session.access_admin_app should be 'high', got {record.severity!r}"
        )

    def test_normalize_default_severity_low(
        self, connector: OktaConnector
    ) -> None:
        """Unmapped event types must map to severity='low'."""
        connector._domain = DOMAIN
        raw = _raw_finding(_log_event("u4", "user.lifecycle.activate"))
        record = connector.normalize(raw)
        assert record.severity == "low", (
            f"user.lifecycle.activate should be 'low', got {record.severity!r}"
        )

    def test_normalize_policy_allow_severity_low(
        self, connector: OktaConnector
    ) -> None:
        """policy.evaluate_sign_on with outcome SUCCESS (not DENY) must be 'low'."""
        connector._domain = DOMAIN
        raw = _raw_finding(
            _log_event("u5", "policy.evaluate_sign_on", outcome_result="SUCCESS")
        )
        record = connector.normalize(raw)
        assert record.severity == "low"

    def test_normalize_app_membership_add_severity_high(
        self, connector: OktaConnector
    ) -> None:
        """application.user_membership.add must map to severity='high'."""
        connector._domain = DOMAIN
        raw = _raw_finding(_log_event("u6", "application.user_membership.add"))
        record = connector.normalize(raw)
        assert record.severity == "high"

    def test_normalize_source_url_in_description(
        self, connector: OktaConnector
    ) -> None:
        """The Okta admin log URL must appear in the description for traceability."""
        connector._domain = DOMAIN
        event_uuid = "abcd-1234-efgh-5678"
        raw = _raw_finding(_log_event(event_uuid, "user.account.lock"))
        record = connector.normalize(raw)
        assert event_uuid in (record.description or ""), (
            "Event UUID should appear in the description"
        )
        expected_url = f"https://{DOMAIN}/admin/logs?eventId={event_uuid}"
        assert expected_url in (record.description or ""), (
            f"Expected source URL {expected_url!r} in description"
        )

    def test_normalize_owner_team(self, connector: OktaConnector) -> None:
        """owner_team must be set to the IAM team label."""
        connector._domain = DOMAIN
        raw = _raw_finding(_log_event("u7", "user.account.lock"))
        record = connector.normalize(raw)
        assert record.owner_team == "Identity & Access Management"


# ─────────────────────────────────────────────────────────────────────────────
# 5. health_check
# ─────────────────────────────────────────────────────────────────────────────


class TestOktaHealthCheck:
    def test_health_check_before_authenticate_ok(
        self, connector: OktaConnector
    ) -> None:
        """Fresh connector returns ok with error_count=0."""
        health = connector.health_check()
        assert isinstance(health, ConnectorHealth)
        assert health.connector_name == "okta"
        assert health.status == "ok"
        assert health.error_count == 0
        assert health.last_run is None

    @respx.mock
    def test_health_check_ok(
        self, connector: OktaConnector, valid_creds: dict
    ) -> None:
        """health_check returns ok when /api/v1/users/me responds 200."""
        respx.get(f"{BASE}/api/v1/users/me").mock(
            return_value=httpx.Response(200, json=_me_response())
        )
        connector.authenticate(valid_creds)

        respx.get(f"{BASE}/api/v1/users/me").mock(
            return_value=httpx.Response(200, json=_me_response())
        )
        health = connector.health_check()
        assert health.status == "ok"

    @respx.mock
    def test_health_check_degraded(
        self, connector: OktaConnector, valid_creds: dict
    ) -> None:
        """health_check returns degraded on 5xx and must NOT raise."""
        respx.get(f"{BASE}/api/v1/users/me").mock(
            side_effect=[
                httpx.Response(200, json=_me_response()),  # authenticate call
                httpx.Response(503, text="Service Unavailable"),  # health_check call
            ]
        )
        connector.authenticate(valid_creds)
        health = connector.health_check()
        # Must not raise — degrade instead
        assert health.status in ("degraded", "error")
        assert health.last_error is not None


# ─────────────────────────────────────────────────────────────────────────────
# 6. Credential field metadata
# ─────────────────────────────────────────────────────────────────────────────


class TestOktaCredentialFields:
    def test_credential_secrets_marked(self) -> None:
        """api_token must have secret=True."""
        fields_by_name = {f.name: f for f in OktaConnector.CREDENTIAL_FIELDS}
        assert "api_token" in fields_by_name, "api_token field not found"
        assert fields_by_name["api_token"].secret is True, (
            "api_token field must have secret=True"
        )

    def test_domain_field_required(self) -> None:
        """domain field must be required."""
        fields_by_name = {f.name: f for f in OktaConnector.CREDENTIAL_FIELDS}
        assert fields_by_name["domain"].required is True

    def test_api_token_field_required(self) -> None:
        """api_token field must be required."""
        fields_by_name = {f.name: f for f in OktaConnector.CREDENTIAL_FIELDS}
        assert fields_by_name["api_token"].required is True


# ─────────────────────────────────────────────────────────────────────────────
# 7. Helper unit tests
# ─────────────────────────────────────────────────────────────────────────────


class TestOktaHelpers:
    def test_parse_event_types_from_filter(self) -> None:
        """_parse_event_types_from_filter must extract all event type strings."""
        filter_expr = (
            'eventType eq "user.account.lock" or '
            'eventType eq "user.session.access_admin_app" or '
            'eventType eq "policy.evaluate_sign_on"'
        )
        result = _parse_event_types_from_filter(filter_expr)
        assert "user.account.lock" in result
        assert "user.session.access_admin_app" in result
        assert "policy.evaluate_sign_on" in result
        assert len(result) == 3

    def test_parse_event_types_empty_filter(self) -> None:
        """Empty / unparseable filter returns empty list."""
        assert _parse_event_types_from_filter("") == []
        assert _parse_event_types_from_filter("junk") == []
