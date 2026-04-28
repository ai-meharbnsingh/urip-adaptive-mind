"""
ServiceNowProvider — REST Table API adapter.

Auth model
----------
ServiceNow Table API supports basic auth (username:password) and OAuth bearer
tokens.  Like Jira, we accept the already-encoded auth_token verbatim and
detect Basic vs Bearer by the presence of `:`.

State / number mapping
----------------------
ServiceNow incident state is a numeric enum.  The numbers vary slightly by
instance config; the OOTB defaults are:

   1 = New
   2 = In Progress
   3 = On Hold
   6 = Resolved
   7 = Closed
   8 = Cancelled

We map these to URIP TicketStatus values; if a tenant has customised the state
field they can pass `state_map=` to override.
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


DEFAULT_STATE_MAP: dict[str, str] = {
    "1": TicketStatus.OPEN,
    "2": TicketStatus.IN_PROGRESS,
    "3": TicketStatus.IN_PROGRESS,
    "6": TicketStatus.RESOLVED,
    "7": TicketStatus.CLOSED,
    "8": TicketStatus.CLOSED,
}

# Reverse map for set-from-URIP-status (best-effort defaults).
URIP_TO_STATE = {
    TicketStatus.OPEN: "1",
    TicketStatus.IN_PROGRESS: "2",
    TicketStatus.RESOLVED: "6",
    TicketStatus.CLOSED: "7",
}


# Severity mapping (URIP "critical/high/medium/low" → ServiceNow impact 1-3).
SEVERITY_TO_IMPACT = {
    "critical": "1",
    "high": "1",
    "medium": "2",
    "low": "3",
}


class ServiceNowProvider(TicketingProviderBase):
    provider_name = "servicenow"

    def __init__(
        self,
        base_url: str,
        auth_token: str,
        table: str = "incident",
        timeout_seconds: float = 15.0,
        state_map: dict[str, str] | None = None,
        client: httpx.Client | None = None,
    ) -> None:
        if not base_url:
            raise ValueError("base_url required")
        if not auth_token:
            raise ValueError("auth_token required")
        self.base_url = base_url.rstrip("/")
        self.auth_token = auth_token
        self.table = table or "incident"
        self.timeout_seconds = timeout_seconds
        self.state_map = state_map or DEFAULT_STATE_MAP
        self._client = client

    # ------------------------------------------------------------------ #
    def _http(self) -> httpx.Client:
        if self._client is not None:
            return self._client
        return httpx.Client(timeout=self.timeout_seconds, headers=self._headers())

    def _headers(self) -> dict[str, str]:
        token = self.auth_token
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
        url = f"{self.base_url}/api/now/table/{self.table}"
        sev = (getattr(risk, "severity", "") or "").lower()
        impact = SEVERITY_TO_IMPACT.get(sev, "2")
        body = {
            "short_description": self._build_summary(risk),
            "description": self._build_description(risk),
            "category": "vulnerability",
            "impact": impact,
            "urgency": impact,
            # `correlation_id` lets us look the ticket back up by URIP risk_id.
            "correlation_id": getattr(risk, "risk_id", None) or "",
            "correlation_display": "URIP Risk",
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
                    f"ServiceNow create HTTP {resp.status_code}: {resp.text[:300]}"
                )
            data = resp.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise TicketingProviderError(f"ServiceNow create failed: {exc}") from exc

        result_payload = data.get("result", {}) if isinstance(data, dict) else {}
        # Prefer "number" (e.g. "INC0010234") over sys_id (UUID).
        ticket_id = (
            result_payload.get("number")
            or result_payload.get("sys_id")
            or data.get("number")
            or data.get("sys_id")
        )
        if not ticket_id:
            raise TicketingProviderError(f"ServiceNow create: no number in response: {data!r}")
        ticket_url = (
            f"{self.base_url}/{self.table}.do?sys_id={result_payload.get('sys_id', '')}"
            if result_payload.get("sys_id")
            else None
        )
        return TicketCreateResult(ticket_id=str(ticket_id), ticket_url=ticket_url, raw=data)

    # ------------------------------------------------------------------ #
    def _lookup_sys_id(self, ticket_id: str) -> str:
        """Look up sys_id by ticket number; returns the number itself if it
        already looks like a sys_id (32-char hex)."""
        if len(ticket_id) == 32 and all(c in "0123456789abcdef" for c in ticket_id.lower()):
            return ticket_id
        url = f"{self.base_url}/api/now/table/{self.table}"
        client = self._http()
        close_after = self._client is None
        try:
            try:
                resp = client.get(
                    url,
                    params={"sysparm_query": f"number={ticket_id}", "sysparm_limit": "1"},
                    headers=self._headers(),
                )
            except httpx.HTTPError as exc:
                raise TicketingProviderError(f"ServiceNow lookup failed: {exc}") from exc
        finally:
            if close_after:
                client.close()
        if resp.status_code != 200:
            raise TicketingProviderError(
                f"ServiceNow lookup HTTP {resp.status_code}"
            )
        rows = (resp.json() or {}).get("result") or []
        if not rows:
            raise TicketingProviderError(f"ServiceNow ticket not found: {ticket_id}")
        return rows[0].get("sys_id", ticket_id)

    # ------------------------------------------------------------------ #
    def update_ticket(
        self, ticket_id: str, *, status: str | None = None, comment: str | None = None
    ) -> dict[str, Any]:
        sys_id = self._lookup_sys_id(ticket_id)
        url = f"{self.base_url}/api/now/table/{self.table}/{sys_id}"
        body: dict[str, Any] = {}
        if status:
            state_num = URIP_TO_STATE.get(status.lower())
            if state_num is None:
                # Allow raw vendor state numbers too.
                state_num = status
            body["state"] = state_num
        if comment:
            body["comments"] = comment
        if not body:
            return {}
        client = self._http()
        close_after = self._client is None
        try:
            try:
                resp = client.patch(url, json=body, headers=self._headers())
            except httpx.HTTPError as exc:
                raise TicketingProviderError(f"ServiceNow update failed: {exc}") from exc
        finally:
            if close_after:
                client.close()
        if resp.status_code not in (200, 204):
            raise TicketingProviderError(
                f"ServiceNow update HTTP {resp.status_code}: {resp.text[:300]}"
            )
        try:
            return resp.json() or {}
        except ValueError:
            return {}

    # ------------------------------------------------------------------ #
    def get_ticket_status(self, ticket_id: str) -> str:
        sys_id = self._lookup_sys_id(ticket_id)
        url = f"{self.base_url}/api/now/table/{self.table}/{sys_id}"
        client = self._http()
        close_after = self._client is None
        try:
            try:
                resp = client.get(url, headers=self._headers())
            except httpx.HTTPError as exc:
                raise TicketingProviderError(
                    f"ServiceNow get_status failed: {exc}"
                ) from exc
        finally:
            if close_after:
                client.close()
        if resp.status_code != 200:
            raise TicketingProviderError(
                f"ServiceNow get_status HTTP {resp.status_code}"
            )
        result = (resp.json() or {}).get("result") or {}
        state_num = str(result.get("state", ""))
        return self.state_map.get(state_num, TicketStatus.UNKNOWN)

    # ------------------------------------------------------------------ #
    def close_ticket(self, ticket_id: str, resolution: str = "Closed by URIP") -> dict[str, Any]:
        return self.update_ticket(
            ticket_id, status=TicketStatus.CLOSED, comment=resolution
        )
