"""
Bidirectional ticketing providers (Jira / ServiceNow).

Public API
----------
    TicketingProviderBase            — abstract contract every provider implements
    JiraProvider                     — Atlassian Cloud REST API v3
    ServiceNowProvider               — ServiceNow Table API (incident table)
    TicketCreateResult               — typed return for create_ticket
    TicketStatus                     — enum-ish status string set
    get_provider(provider_name, …)   — factory; resolves "jira"|"servicenow" → instance

Bidirectional flow:
    URIP Risk created  → ticketing_service.on_risk_assigned(risk)
                       → provider.create_ticket(risk)              (URIP → external)
    Jira/ServiceNow ticket closed
                       → webhook → on_ticket_status_changed(...)
                       → updates Risk.status                       (external → URIP)
    Provider down? `poll_ticket_statuses()` periodic fallback.

URIP_Blueprint v3 §5.1 / §5b.1.
"""
from __future__ import annotations

from backend.integrations.ticketing.base import (
    TicketCreateResult,
    TicketStatus,
    TicketingProviderBase,
    TicketingProviderError,
)
from backend.integrations.ticketing.jira import JiraProvider
from backend.integrations.ticketing.servicenow import ServiceNowProvider


def get_provider(
    provider_name: str,
    *,
    base_url: str,
    auth_token: str,
    project_key: str | None = None,
    issue_type: str = "Bug",
    table: str = "incident",
) -> TicketingProviderBase:
    """Factory: resolve "jira"/"servicenow" string → concrete provider."""
    name = (provider_name or "").strip().lower()
    if name == "jira":
        if not project_key:
            raise ValueError("project_key is required for Jira provider")
        return JiraProvider(
            base_url=base_url,
            auth_token=auth_token,
            project_key=project_key,
            issue_type=issue_type,
        )
    if name in ("servicenow", "snow", "service_now"):
        return ServiceNowProvider(
            base_url=base_url,
            auth_token=auth_token,
            table=table,
        )
    raise ValueError(f"Unknown ticketing provider: {provider_name!r}")


__all__ = [
    "JiraProvider",
    "ServiceNowProvider",
    "TicketCreateResult",
    "TicketStatus",
    "TicketingProviderBase",
    "TicketingProviderError",
    "get_provider",
]
