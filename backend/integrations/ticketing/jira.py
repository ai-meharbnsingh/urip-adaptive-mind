"""
JiraProvider — Atlassian Cloud REST API v3 adapter.

Auth model
----------
Atlassian Cloud REST API uses Basic auth with `email:api_token` Base64-encoded
in the Authorization header.  Self-hosted Server / Data Center can also be
addressed via PAT (`Bearer <token>`).  We accept the already-encoded token
verbatim — the caller is responsible for picking the right scheme — and just
prepend `Basic ` if the token contains a `:` (heuristic: PATs never contain `:`).

Configurable
------------
- base_url        e.g.  https://acme.atlassian.net
- project_key     e.g.  "URIP"
- issue_type      "Bug" | "Task" | "Vulnerability" — depends on Jira config
- closed_statuses normalised mapping of vendor "Done"/"Closed"/"Won't Fix" → URIP
                  TicketStatus.RESOLVED / CLOSED.
"""
from __future__ import annotations

import base64
from typing import Any

import httpx

from backend.integrations.ticketing.base import (
    TicketCreateResult,
    TicketStatus,
    TicketingProviderBase,
    TicketingProviderError,
)


# Jira's vendor status names → URIP canonical status.  We normalise here so
# the rest of URIP never sees raw vendor strings.  "In Progress" can mean
# anything between "assignee assigned" and "in code review", but for risk
# lifecycle purposes only OPEN / IN_PROGRESS / RESOLVED / CLOSED matter.
JIRA_STATUS_MAP = {
    "to do": TicketStatus.OPEN,
    "open": TicketStatus.OPEN,
    "backlog": TicketStatus.OPEN,
    "in progress": TicketStatus.IN_PROGRESS,
    "in review": TicketStatus.IN_PROGRESS,
    "in dev": TicketStatus.IN_PROGRESS,
    "done": TicketStatus.RESOLVED,
    "resolved": TicketStatus.RESOLVED,
    "fixed": TicketStatus.RESOLVED,
    "closed": TicketStatus.CLOSED,
    "won't fix": TicketStatus.CLOSED,
    "cancelled": TicketStatus.CLOSED,
    "reopened": TicketStatus.REOPENED,
}


def _normalise_status(vendor_status: str | None) -> str:
    if not vendor_status:
        return TicketStatus.UNKNOWN
    return JIRA_STATUS_MAP.get(vendor_status.strip().lower(), TicketStatus.UNKNOWN)


class JiraProvider(TicketingProviderBase):
    provider_name = "jira"

    def __init__(
        self,
        base_url: str,
        auth_token: str,
        project_key: str,
        issue_type: str = "Bug",
        timeout_seconds: float = 15.0,
        client: httpx.Client | None = None,
    ) -> None:
        if not base_url:
            raise ValueError("base_url required")
        if not auth_token:
            raise ValueError("auth_token required")
        if not project_key:
            raise ValueError("project_key required")
        self.base_url = base_url.rstrip("/")
        self.auth_token = auth_token
        self.project_key = project_key
        self.issue_type = issue_type
        self.timeout_seconds = timeout_seconds
        # Allow injection for tests (respx-style mocking).
        self._client = client

    # ------------------------------------------------------------------ #
    def _http(self) -> httpx.Client:
        if self._client is not None:
            return self._client
        return httpx.Client(
            timeout=self.timeout_seconds,
            headers=self._headers(),
        )

    def _headers(self) -> dict[str, str]:
        token = self.auth_token
        # Heuristic: if the token contains a colon, it's "email:api_token" and
        # needs Basic-encoding.  Otherwise treat as a Bearer/PAT.
        if ":" in token:
            encoded = base64.b64encode(token.encode("utf-8")).decode("ascii")
            auth_header = f"Basic {encoded}"
        else:
            auth_header = f"Bearer {token}"
        return {
            "Authorization": auth_header,
            "Accept": "application/json",
            "Content-Type": "application/json",
        }

    # ------------------------------------------------------------------ #
    def create_ticket(self, risk: Any) -> TicketCreateResult:
        url = f"{self.base_url}/rest/api/3/issue"
        body = {
            "fields": {
                "project": {"key": self.project_key},
                "summary": self._build_summary(risk),
                "description": self._build_description(risk),
                "issuetype": {"name": self.issue_type},
            }
        }
        try:
            client = self._http()
            close_after = self._client is None
            try:
                resp = client.post(url, json=body, headers=self._headers())
            finally:
                if close_after:
                    client.close()
            if resp.status_code not in (200, 201):
                raise TicketingProviderError(
                    f"Jira create_ticket HTTP {resp.status_code}: {resp.text[:300]}"
                )
            data = resp.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise TicketingProviderError(f"Jira create_ticket failed: {exc}") from exc

        ticket_id = data.get("key") or data.get("id")
        if not ticket_id:
            raise TicketingProviderError(f"Jira create_ticket: no key in response: {data!r}")
        ticket_url = f"{self.base_url}/browse/{ticket_id}"
        return TicketCreateResult(ticket_id=str(ticket_id), ticket_url=ticket_url, raw=data)

    # ------------------------------------------------------------------ #
    def update_ticket(
        self, ticket_id: str, *, status: str | None = None, comment: str | None = None
    ) -> dict[str, Any]:
        out: dict[str, Any] = {}
        client = self._http()
        close_after = self._client is None
        try:
            if comment:
                comment_url = f"{self.base_url}/rest/api/3/issue/{ticket_id}/comment"
                try:
                    resp = client.post(
                        comment_url, json={"body": comment}, headers=self._headers()
                    )
                except httpx.HTTPError as exc:
                    raise TicketingProviderError(f"Jira add comment failed: {exc}") from exc
                if resp.status_code not in (200, 201):
                    raise TicketingProviderError(
                        f"Jira add comment HTTP {resp.status_code}: {resp.text[:300]}"
                    )
                out["comment"] = resp.json()
            if status:
                # Jira doesn't allow direct status PUT — must use transitions API.
                transitions_url = f"{self.base_url}/rest/api/3/issue/{ticket_id}/transitions"
                try:
                    tlist_resp = client.get(transitions_url, headers=self._headers())
                except httpx.HTTPError as exc:
                    raise TicketingProviderError(
                        f"Jira list transitions failed: {exc}"
                    ) from exc
                if tlist_resp.status_code != 200:
                    raise TicketingProviderError(
                        f"Jira list transitions HTTP {tlist_resp.status_code}: {tlist_resp.text[:300]}"
                    )
                target = status.strip().lower()
                transition_id = None
                for t in (tlist_resp.json() or {}).get("transitions", []) or []:
                    if (t.get("to", {}).get("name", "") or "").strip().lower() == target:
                        transition_id = t.get("id")
                        break
                if transition_id is None:
                    raise TicketingProviderError(
                        f"Jira transition not found for status {status!r}"
                    )
                try:
                    presp = client.post(
                        transitions_url,
                        json={"transition": {"id": transition_id}},
                        headers=self._headers(),
                    )
                except httpx.HTTPError as exc:
                    raise TicketingProviderError(
                        f"Jira do_transition failed: {exc}"
                    ) from exc
                if presp.status_code not in (200, 204):
                    raise TicketingProviderError(
                        f"Jira do_transition HTTP {presp.status_code}: {presp.text[:300]}"
                    )
                out["status"] = status
        finally:
            if close_after:
                client.close()
        return out

    # ------------------------------------------------------------------ #
    def get_ticket_status(self, ticket_id: str) -> str:
        url = f"{self.base_url}/rest/api/3/issue/{ticket_id}?fields=status"
        client = self._http()
        close_after = self._client is None
        try:
            try:
                resp = client.get(url, headers=self._headers())
            except httpx.HTTPError as exc:
                raise TicketingProviderError(f"Jira get_ticket_status failed: {exc}") from exc
            if resp.status_code != 200:
                raise TicketingProviderError(
                    f"Jira get_ticket_status HTTP {resp.status_code}"
                )
            data = resp.json()
        finally:
            if close_after:
                client.close()
        vendor_status = (
            ((data.get("fields") or {}).get("status") or {}).get("name")
        )
        return _normalise_status(vendor_status)

    # ------------------------------------------------------------------ #
    def close_ticket(self, ticket_id: str, resolution: str = "Done") -> dict[str, Any]:
        # Closing in Jira == transition to "Done" (or whatever the project
        # configured).  We default to "Done" but allow override.
        return self.update_ticket(ticket_id, status=resolution, comment="Closed by URIP")
