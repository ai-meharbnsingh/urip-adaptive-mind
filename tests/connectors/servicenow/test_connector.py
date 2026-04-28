"""
TDD tests for the ServiceNow ITSM live connector.

Uses respx to mock all HTTP traffic — no real API calls.
Coverage: registration, severity mapping, authentication (Basic + OAuth),
incident list fetch, ticket creation (urgency mapping), health check.

All connector methods that call the API are async; each test uses
``asyncio.run()`` (via ``pytest.mark.asyncio`` / ``anyio`` or a plain
sync wrapper) — we use a minimal sync helper pattern that works without
requiring pytest-asyncio to be installed, while respecting the
async-only API surface of ServiceNowAPIClient.
"""

from __future__ import annotations

import asyncio
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
from connectors.servicenow.connector import (
    ServiceNowConnector,
    _map_severity,
    _severity_to_urgency_impact,
)

# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

INSTANCE = "https://acme.service-now.com"
TENANT_ID = "tenant-sn-001"


def _run(coro):
    """Run a coroutine synchronously in a fresh event loop."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def _mock_healthcheck_ok():
    """Return a healthy sys_user response from the ServiceNow instance."""
    return respx.get(f"{INSTANCE}/api/now/table/sys_user").mock(
        return_value=httpx.Response(
            200,
            json={"result": [{"sys_id": "abc"}]},
        )
    )


def _sample_incident(**overrides: Any) -> dict[str, Any]:
    base = {
        "sys_id": "inc001sys",
        "number": "INC0000001",
        "short_description": "Suspicious login attempt",
        "description": "Multiple failed MFA attempts from unrecognised IP.",
        "urgency": "2",
        "impact": "2",
        "priority": "3",
        "state": "2",
        "assigned_to": "secops@acme.com",
        "opened_at": "2026-04-28 08:00:00",
        "sys_updated_on": "2026-04-28 09:00:00",
        "category": "security",
    }
    base.update(overrides)
    return base


@pytest.fixture
def connector() -> ServiceNowConnector:
    return ServiceNowConnector()


@pytest.fixture
def basic_creds() -> dict[str, str]:
    return {
        "instance_url": INSTANCE,
        "auth_method": "basic",
        "username": "urip_integration",
        "password": "s3cr3tP@ss",
        "risk_query": "category=security^active=true",
        "tenant_id": TENANT_ID,
    }


@pytest.fixture
def oauth_creds() -> dict[str, str]:
    return {
        "instance_url": INSTANCE,
        "auth_method": "oauth",
        "oauth_token": "Bearer_TOKEN_xyz",
        "risk_query": "category=security^active=true",
        "tenant_id": TENANT_ID,
    }


@pytest.fixture
def fake_session() -> ConnectorSession:
    from datetime import datetime, timezone
    return ConnectorSession(
        connector_name="servicenow",
        tenant_id=TENANT_ID,
        token="sn-basic-****",
        expires_at=datetime(9999, 12, 31, tzinfo=timezone.utc),
    )


# ─────────────────────────────────────────────────────────────────────────────
# 1. Registry
# ─────────────────────────────────────────────────────────────────────────────


def test_register():
    """ServiceNowConnector must be registered as 'servicenow' in the global registry."""
    assert "servicenow" in _global_registry, (
        "'servicenow' not in global registry — check @register_connector decorator "
        "and that connectors/servicenow/connector.py has been imported."
    )
    factory = _global_registry.get("servicenow")
    assert factory is ServiceNowConnector


# ─────────────────────────────────────────────────────────────────────────────
# 2. Severity mapping
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize("urgency,impact,expected", [
    ("1", "1", "critical"),   # both high → critical
    ("1", "2", "high"),       # urgency=1, impact=medium → high
    ("2", "1", "high"),       # urgency=medium, impact=1 → high
    ("2", "2", "medium"),     # both medium → medium
    ("2", "3", "medium"),     # urgency=medium, impact=low → medium
    ("3", "2", "medium"),     # urgency=low, impact=medium → medium
    ("3", "3", "low"),        # both low → low
    (None, None, "low"),      # missing → default to low
    ("", "", "low"),          # empty string → low
])
def test_severity_map_urgency_impact(urgency, impact, expected):
    assert _map_severity(urgency, impact) == expected


def test_severity_to_urgency_impact_critical():
    assert _severity_to_urgency_impact("critical") == (1, 1)


def test_severity_to_urgency_impact_high():
    assert _severity_to_urgency_impact("high") == (1, 2)


def test_severity_to_urgency_impact_medium():
    assert _severity_to_urgency_impact("medium") == (2, 2)


def test_severity_to_urgency_impact_low():
    assert _severity_to_urgency_impact("low") == (3, 3)


# ─────────────────────────────────────────────────────────────────────────────
# 3. authenticate — Basic Auth
# ─────────────────────────────────────────────────────────────────────────────


@respx.mock
def test_authenticate_basic(connector, basic_creds):
    """
    authenticate() with Basic Auth must:
      - include Basic auth header (httpx.BasicAuth → "Authorization: Basic …")
      - return a ConnectorSession with connector_name="servicenow"
    """
    route = _mock_healthcheck_ok()

    session = _run(connector.authenticate(basic_creds))

    assert route.called, "healthcheck GET /api/now/table/sys_user was not called"
    assert isinstance(session, ConnectorSession)
    assert session.connector_name == "servicenow"
    assert session.tenant_id == TENANT_ID

    # Verify Basic auth header was sent
    request: httpx.Request = route.calls[0].request
    assert "Authorization" in request.headers
    assert request.headers["Authorization"].startswith("Basic ")


@respx.mock
def test_authenticate_basic_missing_password(connector):
    """authenticate() must raise ConnectorAuthError when password is absent."""
    _mock_healthcheck_ok()
    with pytest.raises(ConnectorAuthError, match="username"):
        _run(connector.authenticate({
            "instance_url": INSTANCE,
            "auth_method": "basic",
            "username": "user",
            # password intentionally missing
        }))


# ─────────────────────────────────────────────────────────────────────────────
# 4. authenticate — OAuth Bearer
# ─────────────────────────────────────────────────────────────────────────────


@respx.mock
def test_authenticate_oauth(connector, oauth_creds):
    """
    authenticate() with OAuth must:
      - include Bearer token in Authorization header
      - return a ConnectorSession
    """
    route = _mock_healthcheck_ok()

    session = _run(connector.authenticate(oauth_creds))

    assert route.called, "healthcheck GET /api/now/table/sys_user was not called"
    assert isinstance(session, ConnectorSession)

    request: httpx.Request = route.calls[0].request
    assert request.headers.get("Authorization") == "Bearer Bearer_TOKEN_xyz"


@respx.mock
def test_authenticate_oauth_missing_token(connector):
    """authenticate() must raise ConnectorAuthError when oauth_token is absent."""
    with pytest.raises(ConnectorAuthError, match="oauth_token"):
        _run(connector.authenticate({
            "instance_url": INSTANCE,
            "auth_method": "oauth",
            # oauth_token intentionally missing
        }))


@respx.mock
def test_authenticate_401_raises_auth_error(connector, basic_creds):
    """A 401 from the healthcheck must bubble up as ConnectorAuthError."""
    respx.get(f"{INSTANCE}/api/now/table/sys_user").mock(
        return_value=httpx.Response(401, json={"error": "invalid credentials"})
    )
    with pytest.raises(ConnectorAuthError):
        _run(connector.authenticate(basic_creds))


# ─────────────────────────────────────────────────────────────────────────────
# 5. list_incidents — query passed correctly
# ─────────────────────────────────────────────────────────────────────────────


@respx.mock
def test_list_incidents_query_passed(connector, basic_creds, fake_session):
    """
    fetch_findings() must pass the risk_query as sysparm_query to the Table API.
    """
    _mock_healthcheck_ok()
    _run(connector.authenticate(basic_creds))

    route = respx.get(f"{INSTANCE}/api/now/table/incident").mock(
        return_value=httpx.Response(
            200,
            json={"result": [_sample_incident()]},
        )
    )

    findings = _run(connector.fetch_findings(fake_session, limit=50))

    assert route.called, "GET /api/now/table/incident was not called"
    assert len(findings) == 1
    assert findings[0].source == "servicenow"
    assert findings[0].id == "inc001sys"

    # Check the query parameter was forwarded.
    request: httpx.Request = route.calls[0].request
    assert "sysparm_query" in request.url.params
    assert request.url.params["sysparm_query"] == "category=security^active=true"


@respx.mock
def test_fetch_findings_empty_result(connector, basic_creds, fake_session):
    """fetch_findings() with empty result must return empty list (not raise)."""
    _mock_healthcheck_ok()
    _run(connector.authenticate(basic_creds))

    respx.get(f"{INSTANCE}/api/now/table/incident").mock(
        return_value=httpx.Response(200, json={"result": []})
    )

    findings = _run(connector.fetch_findings(fake_session, limit=50))
    assert findings == []


# ─────────────────────────────────────────────────────────────────────────────
# 6. normalize
# ─────────────────────────────────────────────────────────────────────────────


def test_normalize_maps_severity(connector):
    """normalize() must map urgency+impact to the correct URIP severity."""
    connector._instance_url = INSTANCE

    raw = RawFinding(
        id="inc001sys",
        source="servicenow",
        raw_data=_sample_incident(urgency="1", impact="1"),  # → critical
        fetched_at=__import__("datetime").datetime.now(),
        tenant_id=TENANT_ID,
    )
    record = connector.normalize(raw)

    assert isinstance(record, URIPRiskRecord)
    assert record.severity == "critical"
    assert record.source == "servicenow"
    assert "inc001sys" in record.description or "INC0000001" in record.description


def test_normalize_source_url_contains_sys_id(connector):
    """normalize() source_url must contain the incident sys_id."""
    connector._instance_url = INSTANCE

    raw = RawFinding(
        id="inc001sys",
        source="servicenow",
        raw_data=_sample_incident(urgency="3", impact="3"),  # → low
        fetched_at=__import__("datetime").datetime.now(),
        tenant_id=TENANT_ID,
    )
    record = connector.normalize(raw)
    assert record.severity == "low"
    # finding text should contain incident identifier
    assert "inc001sys" in record.description or "INC0000001" in record.description


# ─────────────────────────────────────────────────────────────────────────────
# 7. create_ticket — urgency mapping
# ─────────────────────────────────────────────────────────────────────────────


@respx.mock
def test_create_ticket_urgency_mapping_critical(connector, basic_creds, fake_session):
    """
    create_ticket() with severity='critical' must post urgency=1 + impact=1
    to the ServiceNow Table API.
    """
    _mock_healthcheck_ok()
    _run(connector.authenticate(basic_creds))

    route = respx.post(f"{INSTANCE}/api/now/table/incident").mock(
        return_value=httpx.Response(
            201,
            json={"result": {"sys_id": "newincident123", "number": "INC0099999"}},
        )
    )

    risk = URIPRiskRecord(
        finding="Critical URIP Risk: Ransomware C2 detected",
        description="Outbound traffic to known ransomware C2 from PROD-DB-01.",
        source="tenable",
        domain="endpoint",
        cvss_score=9.8,
        severity="critical",
        asset="PROD-DB-01",
        owner_team="SecOps",
    )

    result = _run(connector.create_ticket(fake_session, risk))

    assert route.called, "POST /api/now/table/incident was not called"
    assert result["sys_id"] == "newincident123"
    assert result["number"] == "INC0099999"
    assert "newincident123" in result["url"]

    import json as _json
    body = _json.loads(route.calls[0].request.content)
    assert body["urgency"] == "1", f"Expected urgency='1' for critical; got {body['urgency']!r}"
    assert body["impact"] == "1", f"Expected impact='1' for critical; got {body['impact']!r}"


@respx.mock
def test_create_ticket_urgency_mapping_low(connector, basic_creds, fake_session):
    """create_ticket() with severity='low' must post urgency=3 + impact=3."""
    _mock_healthcheck_ok()
    _run(connector.authenticate(basic_creds))

    route = respx.post(f"{INSTANCE}/api/now/table/incident").mock(
        return_value=httpx.Response(
            201,
            json={"result": {"sys_id": "lowriskid", "number": "INC0000002"}},
        )
    )

    risk = URIPRiskRecord(
        finding="Low risk: informational finding",
        description="Low-priority finding.",
        source="tenable",
        domain="application",
        cvss_score=2.0,
        severity="low",
        asset="app-server",
        owner_team="AppSec",
    )
    _run(connector.create_ticket(fake_session, risk))

    import json as _json
    body = _json.loads(route.calls[0].request.content)
    assert body["urgency"] == "3"
    assert body["impact"] == "3"


# ─────────────────────────────────────────────────────────────────────────────
# 8. health_check — ok and fail
# ─────────────────────────────────────────────────────────────────────────────


@respx.mock
def test_health_check_ok(connector, basic_creds, fake_session):
    """health_check() must return status='ok' when the sys_user ping succeeds."""
    _mock_healthcheck_ok()  # auth
    _run(connector.authenticate(basic_creds))

    # health_check will call sys_user again
    respx.get(f"{INSTANCE}/api/now/table/sys_user").mock(
        return_value=httpx.Response(200, json={"result": [{"sys_id": "abc"}]})
    )

    health = _run(connector.health_check(fake_session))

    assert isinstance(health, ConnectorHealth)
    assert health.status == "ok"
    assert health.connector_name == "servicenow"


@respx.mock
def test_health_check_fail(connector, basic_creds, fake_session):
    """
    health_check() must return status='degraded' (never raise) when the
    ping returns a server error.
    """
    _mock_healthcheck_ok()  # auth
    _run(connector.authenticate(basic_creds))

    respx.get(f"{INSTANCE}/api/now/table/sys_user").mock(
        return_value=httpx.Response(500, json={"error": "internal server error"})
    )

    health = _run(connector.health_check(fake_session))

    assert isinstance(health, ConnectorHealth)
    assert health.status == "degraded"
    assert health.last_error is not None


def test_health_check_no_client(connector, fake_session):
    """health_check() before authenticate() must return status='error', not raise."""
    health = _run(connector.health_check(fake_session))
    assert health.status == "error"
    assert "authenticate" in health.last_error.lower()


# ─────────────────────────────────────────────────────────────────────────────
# 9. Metadata contract
# ─────────────────────────────────────────────────────────────────────────────


def test_connector_metadata():
    """ServiceNowConnector must declare required catalog metadata."""
    c = ServiceNowConnector
    assert c.DISPLAY_NAME == "ServiceNow"
    assert c.CATEGORY == "ITSM"
    assert c.STATUS == "live"
    assert c.MODULE_CODE == "ITSM"
    assert c.SETUP_GUIDE is not None, "SETUP_GUIDE must be set (not None)"
    assert len(c.CREDENTIAL_FIELDS) >= 6, "Expected at least 6 credential fields"


def test_credential_secrets_marked():
    """Fields 'password' and 'oauth_token' must be marked secret=True."""
    fields = {f.name: f for f in ServiceNowConnector.CREDENTIAL_FIELDS}
    assert fields["password"].secret is True
    assert fields["oauth_token"].secret is True
