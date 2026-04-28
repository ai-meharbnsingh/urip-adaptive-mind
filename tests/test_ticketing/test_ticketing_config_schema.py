"""
Tenant ticketing-config Pydantic schema + pre-flight validation tests.

The tenant pastes a config blob into the admin UI; before saving it we run a
Pydantic validator and an HTTP pre-flight ping so the user gets immediate
feedback ("HTTP 401 from Atlassian — verify your API token").
"""
from __future__ import annotations

import httpx
import pytest

from backend.integrations.ticketing.config_schema import (
    TicketingConfig,
    validate_ticketing_config,
    preflight_ticketing_config,
)


# --------------------------------------------------------------------------- #
# Schema: required fields, provider enum, URL validation
# --------------------------------------------------------------------------- #
def test_jira_config_minimum_fields():
    cfg = TicketingConfig(
        provider="jira",
        base_url="https://acme.atlassian.net",
        auth_token="user@x.com:apitoken",
        project_key="URIP",
    )
    assert cfg.provider == "jira"
    assert cfg.project_key == "URIP"


def test_servicenow_config_minimum_fields():
    cfg = TicketingConfig(
        provider="servicenow",
        base_url="https://acme.service-now.com",
        auth_token="abc123",
        table="incident",
    )
    assert cfg.provider == "servicenow"
    assert cfg.table == "incident"


def test_jira_config_rejects_missing_project_key():
    with pytest.raises(Exception):  # ValidationError
        TicketingConfig(
            provider="jira",
            base_url="https://acme.atlassian.net",
            auth_token="x",
        )


def test_unknown_provider_rejected():
    with pytest.raises(Exception):
        TicketingConfig(
            provider="unknown",
            base_url="https://x.example.com",
            auth_token="x",
        )


def test_base_url_must_be_https():
    with pytest.raises(Exception):
        TicketingConfig(
            provider="jira",
            base_url="ftp://nope.example.com",
            auth_token="x",
            project_key="URIP",
        )


def test_validate_ticketing_config_returns_normalised():
    out = validate_ticketing_config(
        {
            "provider": "Jira",  # case-insensitive
            "base_url": "https://acme.atlassian.net/",  # trailing slash
            "auth_token": "x:y",
            "project_key": "urip",
        }
    )
    assert out.provider == "jira"
    assert out.base_url == "https://acme.atlassian.net"
    assert out.project_key == "URIP"  # uppercased per Jira convention


def test_validate_ticketing_config_raises_on_bad_input():
    with pytest.raises(Exception):
        validate_ticketing_config({"provider": "jira"})  # missing base_url etc.


# --------------------------------------------------------------------------- #
# Pre-flight: ping API + verify project_key
# --------------------------------------------------------------------------- #
def test_preflight_ok_when_jira_returns_project():
    def handler(request: httpx.Request) -> httpx.Response:
        # The pre-flight should hit /rest/api/3/project/<key>
        if "/project/URIP" in request.url.path:
            return httpx.Response(200, json={"key": "URIP", "id": "10001"})
        if "/myself" in request.url.path:
            return httpx.Response(200, json={"accountId": "abc"})
        return httpx.Response(404)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    cfg = TicketingConfig(
        provider="jira",
        base_url="https://acme.atlassian.net",
        auth_token="user:token",
        project_key="URIP",
    )
    result = preflight_ticketing_config(cfg, http_client=client)
    assert result.ok is True
    assert "URIP" in (result.message or "")


def test_preflight_jira_fails_on_unknown_project():
    def handler(request: httpx.Request) -> httpx.Response:
        if "/project/" in request.url.path:
            return httpx.Response(404, text="No project found")
        return httpx.Response(200, json={"accountId": "x"})

    client = httpx.Client(transport=httpx.MockTransport(handler))
    cfg = TicketingConfig(
        provider="jira",
        base_url="https://acme.atlassian.net",
        auth_token="user:token",
        project_key="DOESNOTEXIST",
    )
    result = preflight_ticketing_config(cfg, http_client=client)
    assert result.ok is False
    assert "404" in (result.message or "") or "not found" in (result.message or "").lower()


def test_preflight_jira_fails_on_401():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, text="auth required")

    client = httpx.Client(transport=httpx.MockTransport(handler))
    cfg = TicketingConfig(
        provider="jira",
        base_url="https://acme.atlassian.net",
        auth_token="bad",
        project_key="URIP",
    )
    result = preflight_ticketing_config(cfg, http_client=client)
    assert result.ok is False
    assert "401" in (result.message or "") or "auth" in (result.message or "").lower()


def test_preflight_servicenow_ok():
    def handler(request: httpx.Request) -> httpx.Response:
        if "/api/now/table/incident" in request.url.path:
            return httpx.Response(200, json={"result": []})
        return httpx.Response(404)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    cfg = TicketingConfig(
        provider="servicenow",
        base_url="https://acme.service-now.com",
        auth_token="bearer-token",
        table="incident",
    )
    result = preflight_ticketing_config(cfg, http_client=client)
    assert result.ok is True


def test_preflight_servicenow_fails_on_500():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="boom")

    client = httpx.Client(transport=httpx.MockTransport(handler))
    cfg = TicketingConfig(
        provider="servicenow",
        base_url="https://acme.service-now.com",
        auth_token="bearer-token",
        table="incident",
    )
    result = preflight_ticketing_config(cfg, http_client=client)
    assert result.ok is False


# --------------------------------------------------------------------------- #
# Webhook secret optional; default is empty string (means signature off).
# --------------------------------------------------------------------------- #
def test_webhook_secret_defaults_to_empty():
    cfg = TicketingConfig(
        provider="jira",
        base_url="https://acme.atlassian.net",
        auth_token="x",
        project_key="URIP",
    )
    assert cfg.webhook_secret == ""


def test_webhook_secret_passes_through():
    cfg = TicketingConfig(
        provider="jira",
        base_url="https://acme.atlassian.net",
        auth_token="x",
        project_key="URIP",
        webhook_secret="hmac-shared-secret",
    )
    assert cfg.webhook_secret == "hmac-shared-secret"
