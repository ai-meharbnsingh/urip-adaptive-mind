"""
Async HTTPX client for the ServiceNow Table API.

Handles:
- Basic Auth (username + password) via httpx.BasicAuth
- OAuth Bearer Token via Authorization header
- CRUD operations on the /api/now/table/incident endpoint
- Lightweight healthcheck via GET /api/now/table/sys_user?sysparm_limit=1

Design decisions
----------------
- Fully async (httpx.AsyncClient) — all public methods are coroutines.
- ConnectorAuthError raised for 401/403 (bad creds — non-retryable).
- ConnectorFetchError raised for 5xx (server-side — caller may retry).
- 30-second timeout applied globally; caller responsible for circuit-breaking.
- close() must be awaited when the client is no longer needed — the connector
  calls this in its finally block or the auth session teardown.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

import httpx

from connectors.base.connector import ConnectorAuthError, ConnectorFetchError

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT = 30.0


class ServiceNowAPIClient:
    """Async HTTPX client for the ServiceNow Table API (Utah / Vancouver / Washington / Xanadu)."""

    def __init__(
        self,
        instance_url: str,
        username: Optional[str] = None,
        password: Optional[str] = None,
        oauth_token: Optional[str] = None,
        timeout: float = DEFAULT_TIMEOUT,
    ) -> None:
        """
        Parameters
        ----------
        instance_url : str
            Base URL of the ServiceNow tenant, e.g. https://your-tenant.service-now.com
        username : str, optional
            Basic Auth username — required when oauth_token is not provided.
        password : str, optional
            Basic Auth password — required when oauth_token is not provided.
        oauth_token : str, optional
            OAuth 2.0 Bearer token — takes priority over Basic Auth when provided.
        timeout : float
            Request timeout in seconds (default: 30).
        """
        self._instance_url = instance_url.rstrip("/")
        self._oauth_token = oauth_token
        self._timeout = timeout

        # Build the underlying async client once; reuse across calls.
        if oauth_token:
            # OAuth Bearer — inject via custom header; no BasicAuth.
            self._client = httpx.AsyncClient(
                timeout=timeout,
                follow_redirects=True,
                headers={
                    "Authorization": f"Bearer {oauth_token}",
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                },
            )
        elif username and password:
            self._client = httpx.AsyncClient(
                timeout=timeout,
                follow_redirects=True,
                auth=httpx.BasicAuth(username, password),
                headers={
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                },
            )
        else:
            raise ValueError(
                "ServiceNowAPIClient requires either (username + password) "
                "or oauth_token."
            )

    # ─────────────────────────────────────────────────────────────────────────
    # Internal helpers
    # ─────────────────────────────────────────────────────────────────────────

    def _url(self, path: str) -> str:
        return f"{self._instance_url}{path}"

    async def _request(
        self,
        method: str,
        path: str,
        **kwargs: Any,
    ) -> httpx.Response:
        url = self._url(path)
        logger.debug("ServiceNow API %s %s", method, url)
        resp = await self._client.request(method, url, **kwargs)
        if resp.status_code in (401, 403):
            raise ConnectorAuthError(
                f"ServiceNow returned {resp.status_code} — check credentials "
                f"or instance URL. Response: {resp.text[:200]}"
            )
        if resp.status_code >= 500:
            raise ConnectorFetchError(
                f"ServiceNow server error {resp.status_code}: {resp.text[:200]}"
            )
        resp.raise_for_status()
        return resp

    # ─────────────────────────────────────────────────────────────────────────
    # Public API
    # ─────────────────────────────────────────────────────────────────────────

    async def list_incidents(
        self,
        query: str,
        fields: Optional[list[str]] = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """
        GET /api/now/table/incident — return the ``result`` array.

        Parameters
        ----------
        query : str
            ServiceNow encoded query string, e.g. "category=security^active=true".
        fields : list[str], optional
            Comma-joined list of fields to return (sysparm_fields).
            When None, all fields are returned.
        limit : int
            Maximum records to return (sysparm_limit, default 50).

        Returns
        -------
        list[dict]
            Raw incident dicts from the ``result`` key of the API response.
        """
        params: dict[str, Any] = {
            "sysparm_query": query,
            "sysparm_limit": limit,
        }
        if fields:
            params["sysparm_fields"] = ",".join(fields)

        resp = await self._request("GET", "/api/now/table/incident", params=params)
        payload = resp.json()
        return payload.get("result", [])

    async def get_incident(self, sys_id: str) -> dict[str, Any]:
        """
        GET /api/now/table/incident/{sys_id} — return the incident dict.

        Parameters
        ----------
        sys_id : str
            ServiceNow sys_id of the incident record.
        """
        resp = await self._request("GET", f"/api/now/table/incident/{sys_id}")
        payload = resp.json()
        return payload.get("result", payload)

    async def create_incident(
        self,
        short_description: str,
        description: str,
        urgency: int = 3,
        impact: int = 3,
        category: str = "security",
        caller_id: Optional[str] = None,
    ) -> dict[str, Any]:
        """
        POST /api/now/table/incident — create a new incident.

        Parameters
        ----------
        short_description : str
            One-line summary (maps to the ``short_description`` field).
        description : str
            Detailed body text.
        urgency : int
            1=High, 2=Medium, 3=Low (ServiceNow convention).
        impact : int
            1=High, 2=Medium, 3=Low (ServiceNow convention).
        category : str
            Ticket category, default "security".
        caller_id : str, optional
            sys_id or username of the caller (requester).

        Returns
        -------
        dict
            The created incident record from ``result``.
        """
        body: dict[str, Any] = {
            "short_description": short_description,
            "description": description,
            "urgency": str(urgency),
            "impact": str(impact),
            "category": category,
        }
        if caller_id:
            body["caller_id"] = caller_id

        resp = await self._request("POST", "/api/now/table/incident", json=body)
        payload = resp.json()
        return payload.get("result", payload)

    async def update_incident(
        self,
        sys_id: str,
        fields: dict[str, Any],
    ) -> dict[str, Any]:
        """
        PATCH /api/now/table/incident/{sys_id} — update arbitrary fields.

        Parameters
        ----------
        sys_id : str
            ServiceNow sys_id of the incident to update.
        fields : dict
            Fields to patch (partial update).

        Returns
        -------
        dict
            The updated incident record from ``result``.
        """
        resp = await self._request(
            "PATCH",
            f"/api/now/table/incident/{sys_id}",
            json=fields,
        )
        payload = resp.json()
        return payload.get("result", payload)

    async def healthcheck(self) -> dict[str, Any]:
        """
        Lightweight connectivity check — GET /api/now/table/sys_user?sysparm_limit=1.

        Returns the raw response payload (``result`` list) on success.
        Raises ConnectorAuthError or ConnectorFetchError on failure.
        """
        resp = await self._request(
            "GET",
            "/api/now/table/sys_user",
            params={"sysparm_limit": 1, "sysparm_fields": "sys_id"},
        )
        return resp.json()

    async def close(self) -> None:
        """Close the underlying httpx.AsyncClient. Always await this on teardown."""
        await self._client.aclose()

    # Context-manager support for use in `async with` blocks.
    async def __aenter__(self) -> "ServiceNowAPIClient":
        return self

    async def __aexit__(self, *args: Any) -> None:
        await self.close()
