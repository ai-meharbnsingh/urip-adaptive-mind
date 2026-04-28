"""
JiraProvider — unit tests with httpx MockTransport (offline).

We never hit a real Atlassian instance; we wire a MockTransport that asserts
the provider sends what we expect and returns canned responses.
"""
from __future__ import annotations

import dataclasses
from datetime import datetime, timezone

import httpx
import pytest

from backend.integrations.ticketing import TicketStatus
from backend.integrations.ticketing.base import TicketingProviderError
from backend.integrations.ticketing.jira import JiraProvider


# -- A fake Risk-shaped object — tests never hit the DB.
@dataclasses.dataclass
class FakeRisk:
    risk_id: str = "RISK-2026-001"
    finding: str = "Apache log4j RCE"
    description: str = "Critical RCE in log4j 2.14"
    severity: str = "critical"
    cvss_score: float = 9.8
    owner_team: str = "Infrastructure"
    asset: str = "web-01.test"
    cve_id: str = "CVE-2021-44228"
    composite_score: float = 9.5
    sla_deadline: datetime = datetime(2026, 5, 1, tzinfo=timezone.utc)


def _mock_transport(handler):
    return httpx.Client(transport=httpx.MockTransport(handler))


# --------------------------------------------------------------------------- #
def test_create_ticket_returns_ticket_id_and_url():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["method"] = request.method
        captured["body"] = request.read().decode()
        return httpx.Response(
            201,
            json={"id": "10001", "key": "URIP-42", "self": "..."},
        )

    client = _mock_transport(handler)
    provider = JiraProvider(
        base_url="https://acme.atlassian.net",
        auth_token="user@example.com:apitoken",
        project_key="URIP",
        client=client,
    )
    result = provider.create_ticket(FakeRisk())

    assert result.ticket_id == "URIP-42"
    assert result.ticket_url == "https://acme.atlassian.net/browse/URIP-42"
    assert "/rest/api/3/issue" in captured["url"]
    assert captured["method"] == "POST"
    # Payload contains the project key and a properly built summary.
    # Note: httpx JSON serialization has no spaces — "key":"URIP" not "key": "URIP".
    assert "URIP" in captured["body"]
    assert "RISK-2026-001" in captured["body"]
    assert "log4j" in captured["body"]


def test_create_ticket_raises_on_4xx():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, text="Unauthorized")

    client = _mock_transport(handler)
    provider = JiraProvider(
        base_url="https://acme.atlassian.net",
        auth_token="bad",
        project_key="URIP",
        client=client,
    )
    with pytest.raises(TicketingProviderError):
        provider.create_ticket(FakeRisk())


def test_get_ticket_status_normalises_done_to_resolved():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200, json={"fields": {"status": {"name": "Done"}}}
        )

    client = _mock_transport(handler)
    provider = JiraProvider(
        base_url="https://acme.atlassian.net",
        auth_token="x:y",
        project_key="URIP",
        client=client,
    )
    assert provider.get_ticket_status("URIP-42") == TicketStatus.RESOLVED


def test_get_ticket_status_normalises_in_progress():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200, json={"fields": {"status": {"name": "In Progress"}}}
        )

    client = _mock_transport(handler)
    provider = JiraProvider(
        base_url="https://acme.atlassian.net",
        auth_token="x:y",
        project_key="URIP",
        client=client,
    )
    assert provider.get_ticket_status("URIP-42") == TicketStatus.IN_PROGRESS


def test_update_ticket_with_comment_and_transition():
    seen_paths = []

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        seen_paths.append((request.method, path))
        if request.method == "POST" and path.endswith("/comment"):
            return httpx.Response(201, json={"id": "c1"})
        if request.method == "GET" and path.endswith("/transitions"):
            return httpx.Response(
                200,
                json={
                    "transitions": [
                        {"id": "31", "to": {"name": "Done"}},
                        {"id": "11", "to": {"name": "To Do"}},
                    ]
                },
            )
        if request.method == "POST" and path.endswith("/transitions"):
            return httpx.Response(204)
        return httpx.Response(404)

    client = _mock_transport(handler)
    provider = JiraProvider(
        base_url="https://acme.atlassian.net",
        auth_token="x:y",
        project_key="URIP",
        client=client,
    )
    out = provider.update_ticket("URIP-42", status="Done", comment="hello")
    # comment + GET transitions + POST transitions (3 calls)
    assert len(seen_paths) == 3
    assert out["status"] == "Done"


def test_close_ticket_calls_transition_to_done():
    transitions_called = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST" and request.url.path.endswith("/comment"):
            return httpx.Response(201, json={"id": "c1"})
        if request.method == "GET" and request.url.path.endswith("/transitions"):
            return httpx.Response(
                200, json={"transitions": [{"id": "31", "to": {"name": "Done"}}]}
            )
        if request.method == "POST" and request.url.path.endswith("/transitions"):
            transitions_called["count"] += 1
            return httpx.Response(204)
        return httpx.Response(404)

    client = _mock_transport(handler)
    provider = JiraProvider(
        base_url="https://acme.atlassian.net",
        auth_token="x:y",
        project_key="URIP",
        client=client,
    )
    provider.close_ticket("URIP-42")
    assert transitions_called["count"] == 1
