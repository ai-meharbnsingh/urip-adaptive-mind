"""
Async HTTPX client for the Okta Core API (Workforce Identity Cloud).

Authentication
--------------
Okta uses SSWS token auth — every request carries:
    Authorization: SSWS <api_token>

The token is generated in the Okta admin console:
    Security → API → Tokens → Create Token

All methods are async and use httpx.AsyncClient.

Okta API reference:
  https://developer.okta.com/docs/reference/core-okta-api/
"""

from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from typing import Any, Optional

import httpx

from connectors.base.connector import ConnectorAuthError, ConnectorFetchError

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT = 30.0

# Default System Log event types that are security-relevant for URIP.
DEFAULT_LOG_EVENT_TYPES: list[str] = [
    "user.account.lock",
    "user.session.access_admin_app",
    "policy.evaluate_sign_on",
    "application.user_membership.add",
    "application.user_membership.remove",
]


def _parse_next_link(link_header: str | None) -> str | None:
    """
    Extract the 'next' cursor URL from an Okta Link header.

    Okta uses RFC 5988 link headers:
        <https://…/api/v1/users?after=cursor>; rel="next",
        <https://…/api/v1/users?limit=200>; rel="self"

    Returns the bare URL string (with cursor) or None if no next page.
    """
    if not link_header:
        return None
    # Match the URL inside angle brackets followed by rel="next"
    match = re.search(r'<([^>]+)>;\s*rel="next"', link_header)
    return match.group(1) if match else None


class OktaAPIClient:
    """
    Thin async HTTPX wrapper for the Okta Core API.

    Parameters
    ----------
    domain : str
        Okta tenant domain, e.g. ``your-org.okta.com``.
        Do NOT include ``https://`` or a trailing slash.
    api_token : str
        Okta API token (SSWS token).
    timeout : float
        HTTP request timeout in seconds (default 30).
    """

    def __init__(
        self,
        domain: str,
        api_token: str,
        timeout: float = DEFAULT_TIMEOUT,
    ) -> None:
        self.domain = domain.strip().rstrip("/")
        # Normalize: strip any scheme the user accidentally included
        self.domain = re.sub(r"^https?://", "", self.domain)
        self.api_token = api_token
        self.timeout = timeout
        self._base_url = f"https://{self.domain}"

        self._client = httpx.AsyncClient(
            timeout=timeout,
            follow_redirects=True,
        )

    # ─────────────────────────────────────────────────────────────────────────
    # Internal helpers
    # ─────────────────────────────────────────────────────────────────────────

    def _auth_headers(self) -> dict[str, str]:
        return {
            "Authorization": f"SSWS {self.api_token}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        }

    async def _request(
        self,
        method: str,
        path: str,
        **kwargs: Any,
    ) -> httpx.Response:
        """Send a single request and handle Okta error codes."""
        # Accept absolute URLs (for pagination cursors) or paths
        if path.startswith("http"):
            url = path
        else:
            url = f"{self._base_url}{path}"

        headers = self._auth_headers()
        if "headers" in kwargs:
            headers.update(kwargs.pop("headers"))

        logger.debug("Okta API %s %s", method, url)
        response = await self._client.request(method, url, headers=headers, **kwargs)

        if response.status_code in (401, 403):
            raise ConnectorAuthError(
                f"Okta auth failed — HTTP {response.status_code} for {url}. "
                "Verify the SSWS token has not expired and has the required scopes."
            )
        if response.status_code >= 500:
            raise ConnectorFetchError(
                f"Okta server error — HTTP {response.status_code} for {url}: "
                f"{response.text[:300]}"
            )

        return response

    # ─────────────────────────────────────────────────────────────────────────
    # Public API methods
    # ─────────────────────────────────────────────────────────────────────────

    async def list_users(
        self,
        limit: int = 200,
        since: datetime | None = None,
    ) -> list[dict[str, Any]]:
        """
        Paginate through all Okta users.

        GET /api/v1/users?limit={limit}[&filter=lastUpdated gt "..."]

        Uses the ``Link: <url>; rel="next"`` header for cursor-based pagination.

        Parameters
        ----------
        limit : int
            Page size (default 200, Okta max 200).
        since : datetime, optional
            If provided, adds a filter ``lastUpdated gt "ISO8601"`` so only
            users updated after this timestamp are returned.

        Returns
        -------
        list[dict]
            Flat list of Okta user objects across all pages.
        """
        params: dict[str, Any] = {"limit": min(limit, 200)}
        if since is not None:
            ts = since.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")
            params["filter"] = f'lastUpdated gt "{ts}"'

        all_users: list[dict[str, Any]] = []
        # First request uses the path + params; subsequent requests use the cursor URL directly
        resp = await self._request("GET", "/api/v1/users", params=params)
        resp.raise_for_status()
        all_users.extend(resp.json() if isinstance(resp.json(), list) else [])

        next_url = _parse_next_link(resp.headers.get("link"))
        while next_url:
            resp = await self._request("GET", next_url)
            resp.raise_for_status()
            page = resp.json()
            if isinstance(page, list):
                all_users.extend(page)
            next_url = _parse_next_link(resp.headers.get("link"))

        return all_users

    async def list_apps(
        self,
        user_id: str | None = None,
    ) -> list[dict[str, Any]]:
        """
        List applications or a user's app assignments.

        If ``user_id`` is given:
            GET /api/v1/users/{user_id}/appLinks  — returns AppLink objects
        Otherwise:
            GET /api/v1/apps  — returns Application objects (paginated)

        Returns
        -------
        list[dict]
        """
        if user_id:
            resp = await self._request("GET", f"/api/v1/users/{user_id}/appLinks")
            resp.raise_for_status()
            return resp.json()

        # Paginate through all apps
        all_apps: list[dict[str, Any]] = []
        resp = await self._request("GET", "/api/v1/apps", params={"limit": 200})
        resp.raise_for_status()
        all_apps.extend(resp.json() if isinstance(resp.json(), list) else [])

        next_url = _parse_next_link(resp.headers.get("link"))
        while next_url:
            resp = await self._request("GET", next_url)
            resp.raise_for_status()
            page = resp.json()
            if isinstance(page, list):
                all_apps.extend(page)
            next_url = _parse_next_link(resp.headers.get("link"))

        return all_apps

    async def get_factors(self, user_id: str) -> list[dict[str, Any]]:
        """
        Return the MFA factors enrolled for a specific user.

        GET /api/v1/users/{user_id}/factors

        Parameters
        ----------
        user_id : str
            Okta user ID (e.g. ``00u1abcd2EFGhijk3456``).

        Returns
        -------
        list[dict]
            List of Okta Factor objects (factorType, provider, status, …).
        """
        resp = await self._request("GET", f"/api/v1/users/{user_id}/factors")
        resp.raise_for_status()
        return resp.json()

    async def list_system_log(
        self,
        since: datetime,
        types: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        """
        Pull events from the Okta System Log.

        GET /api/v1/logs?since={ISO8601}[&filter=eventType eq "..."]

        Okta's System Log uses cursor pagination via the ``Link`` header.
        When ``types`` is provided, an Okta filter expression is constructed
        by OR-ing ``eventType eq "..."`` predicates.

        Parameters
        ----------
        since : datetime
            Fetch events published after this timestamp.
        types : list[str], optional
            If supplied, restricts the query to these event types.
            Defaults to ``DEFAULT_LOG_EVENT_TYPES`` when None.

        Returns
        -------
        list[dict]
            Flat list of Okta System Log event objects.
        """
        event_types = types if types is not None else DEFAULT_LOG_EVENT_TYPES

        since_iso = since.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")
        params: dict[str, Any] = {
            "since": since_iso,
            "limit": 1000,
        }

        if event_types:
            filter_expr = " or ".join(
                f'eventType eq "{t}"' for t in event_types
            )
            params["filter"] = filter_expr

        all_events: list[dict[str, Any]] = []
        resp = await self._request("GET", "/api/v1/logs", params=params)
        resp.raise_for_status()
        all_events.extend(resp.json() if isinstance(resp.json(), list) else [])

        next_url = _parse_next_link(resp.headers.get("link"))
        while next_url:
            resp = await self._request("GET", next_url)
            resp.raise_for_status()
            page = resp.json()
            if isinstance(page, list):
                all_events.extend(page)
            next_url = _parse_next_link(resp.headers.get("link"))

        return all_events

    async def healthcheck(self) -> dict[str, Any]:
        """
        Verify that the API token is valid.

        GET /api/v1/users/me

        Returns the current user's profile dict.
        Raises ConnectorAuthError on 401/403.
        """
        resp = await self._request("GET", "/api/v1/users/me")
        resp.raise_for_status()
        return resp.json()

    async def close(self) -> None:
        """Close the underlying httpx.AsyncClient."""
        await self._client.aclose()

    async def __aenter__(self) -> "OktaAPIClient":
        return self

    async def __aexit__(self, *args: Any) -> None:
        await self.close()
