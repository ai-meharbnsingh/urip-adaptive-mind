"""ServiceNowProvider — unit tests with httpx MockTransport (offline)."""
from __future__ import annotations

import dataclasses
from datetime import datetime, timezone

import httpx
import pytest

from backend.integrations.ticketing import TicketStatus
from backend.integrations.ticketing.base import TicketingProviderError
from backend.integrations.ticketing.servicenow import ServiceNowProvider


@dataclasses.dataclass
class FakeRisk:
    risk_id: str = "RISK-2026-002"
    finding: str = "SQLi in /api/orders"
    description: str = "Untrusted input concat'd into ORDER BY"
    severity: str = "high"
    cvss_score: float = 8.1
    owner_team: str = "AppSec"
    asset: str = "orders.acme.com"
    cve_id: str | None = None
    composite_score: float = 7.5
    sla_deadline: datetime = datetime(2026, 6, 1, tzinfo=timezone.utc)


def _mock_transport(handler):
    return httpx.Client(transport=httpx.MockTransport(handler))


def test_create_ticket_returns_number_and_sys_id():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert "/api/now/table/incident" in str(request.url)
        return httpx.Response(
            201,
            json={
                "result": {
                    "number": "INC0010234",
                    "sys_id": "abc123def456abc123def456abc123de",
                }
            },
        )

    client = _mock_transport(handler)
    provider = ServiceNowProvider(
        base_url="https://acme.service-now.com",
        auth_token="user:pass",
        client=client,
    )
    result = provider.create_ticket(FakeRisk())
    assert result.ticket_id == "INC0010234"
    assert result.ticket_url is not None and "abc123def456abc123def456abc123de" in result.ticket_url


def test_create_ticket_raises_on_5xx():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="Internal error")

    client = _mock_transport(handler)
    provider = ServiceNowProvider(
        base_url="https://acme.service-now.com",
        auth_token="user:pass",
        client=client,
    )
    with pytest.raises(TicketingProviderError):
        provider.create_ticket(FakeRisk())


def test_get_ticket_status_state_6_is_resolved():
    """ServiceNow state 6 = Resolved → URIP TicketStatus.RESOLVED."""
    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "GET" and "?sysparm_query" in str(request.url):
            return httpx.Response(
                200,
                json={"result": [{"sys_id": "abc123def456abc123def456abc123de"}]},
            )
        if request.method == "GET" and "abc123def456" in str(request.url):
            return httpx.Response(
                200, json={"result": {"state": "6", "number": "INC0010234"}}
            )
        return httpx.Response(404)

    client = _mock_transport(handler)
    provider = ServiceNowProvider(
        base_url="https://acme.service-now.com",
        auth_token="u:p",
        client=client,
    )
    assert provider.get_ticket_status("INC0010234") == TicketStatus.RESOLVED


def test_get_ticket_status_state_2_is_in_progress():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "GET" and "?sysparm_query" in str(request.url):
            return httpx.Response(
                200,
                json={"result": [{"sys_id": "abc123def456abc123def456abc123de"}]},
            )
        if request.method == "GET" and "abc123def456" in str(request.url):
            return httpx.Response(200, json={"result": {"state": "2"}})
        return httpx.Response(404)

    client = _mock_transport(handler)
    provider = ServiceNowProvider(
        base_url="https://acme.service-now.com",
        auth_token="u:p",
        client=client,
    )
    assert provider.get_ticket_status("INC0010234") == TicketStatus.IN_PROGRESS


def test_close_ticket_sends_state_7_and_comment():
    payloads = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "GET" and "?sysparm_query" in str(request.url):
            return httpx.Response(
                200,
                json={"result": [{"sys_id": "abc123def456abc123def456abc123de"}]},
            )
        if request.method == "PATCH":
            payloads.append(request.read().decode())
            return httpx.Response(200, json={"result": {}})
        return httpx.Response(404)

    client = _mock_transport(handler)
    provider = ServiceNowProvider(
        base_url="https://acme.service-now.com",
        auth_token="u:p",
        client=client,
    )
    provider.close_ticket("INC0010234", resolution="Auto-remediated by URIP")
    assert len(payloads) == 1
    # httpx JSON has no spaces between : and value → match the unspaced form.
    assert '"state":"7"' in payloads[0]
    assert "Auto-remediated" in payloads[0]
