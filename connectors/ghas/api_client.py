"""
Async HTTPX client for GitHub Advanced Security (GHAS) REST API v3.

Authentication
--------------
Bearer token — Personal Access Token (classic or fine-grained) or GitHub App token.
Required PAT scopes: security_events, read:org

GitHub REST API reference:
  https://docs.github.com/en/rest

For GitHub Enterprise Server, pass a custom api_url, e.g.:
  https://github.your-company.com/api/v3
"""

from __future__ import annotations

import logging
import re
from datetime import datetime
from typing import Any, Optional

import httpx

from connectors.base.connector import ConnectorAuthError, ConnectorFetchError

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT = 30.0
_GITHUB_API_VERSION = "2022-11-28"
_MAX_RESULTS = 1000   # safety cap — prevent runaway pagination
_PER_PAGE = 100       # GitHub max per page for these endpoints


# ─────────────────────────────────────────────────────────────────────────────
# Pagination helper
# ─────────────────────────────────────────────────────────────────────────────


def _next_link(link_header: str | None) -> str | None:
    """
    Parse GitHub's Link: rel="next" header and return the next-page URL.

    Example header value:
      <https://api.github.com/orgs/myorg/code-scanning/alerts?page=2>; rel="next",
      <https://api.github.com/orgs/myorg/code-scanning/alerts?page=5>; rel="last"

    Returns the bare URL string or None if no next page exists.
    """
    if not link_header:
        return None
    # Each segment looks like: <url>; rel="relation"
    for segment in link_header.split(","):
        segment = segment.strip()
        match = re.match(r'<([^>]+)>;\s*rel="next"', segment)
        if match:
            return match.group(1)
    return None


# ─────────────────────────────────────────────────────────────────────────────
# Client
# ─────────────────────────────────────────────────────────────────────────────


class GhasAPIClient:
    """
    Thin async HTTPX wrapper for GitHub REST API v3 — GHAS security alert endpoints.

    Parameters
    ----------
    org : str
        GitHub organization name (e.g. "my-company").
    token : str
        Personal Access Token or GitHub App token.
        Classic PAT scopes required: security_events, read:org
    api_url : str
        GitHub API root URL. Default "https://api.github.com".
        For GHE Server use: https://github.your-company.com/api/v3
    timeout : float
        HTTP request timeout in seconds (default 30).
    """

    def __init__(
        self,
        org: str,
        token: str,
        api_url: str = "https://api.github.com",
        timeout: float = DEFAULT_TIMEOUT,
    ) -> None:
        self.org = org
        self.token = token
        self.api_url = api_url.rstrip("/")
        self.timeout = timeout

        self._client = httpx.AsyncClient(timeout=timeout, follow_redirects=True)

    # ─────────────────────────────────────────────────────────────────────────
    # Internal helpers
    # ─────────────────────────────────────────────────────────────────────────

    def _auth_headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": _GITHUB_API_VERSION,
        }

    async def _request(
        self,
        method: str,
        url: str,
        **kwargs: Any,
    ) -> httpx.Response:
        """Send one request and handle common GitHub error codes."""
        headers = self._auth_headers()
        if "headers" in kwargs:
            headers.update(kwargs.pop("headers"))

        logger.debug("GHAS API %s %s", method, url)
        response = await self._client.request(method, url, headers=headers, **kwargs)

        if response.status_code in (401, 403):
            raise ConnectorAuthError(
                f"GHAS auth failed — HTTP {response.status_code} for {url}. "
                "Check token scopes (security_events + read:org) and organization access."
            )
        if response.status_code >= 500:
            raise ConnectorFetchError(
                f"GHAS server error — HTTP {response.status_code} for {url}: "
                f"{response.text[:300]}"
            )

        return response

    async def _paginate(
        self,
        initial_url: str,
        params: dict[str, Any],
    ) -> list[dict[str, Any]]:
        """
        Follow Link: rel="next" headers until exhausted or _MAX_RESULTS reached.

        Parameters
        ----------
        initial_url : str
            Absolute URL for the first page (no per_page added here; include in params).
        params : dict
            Query params for the FIRST page only — subsequent pages come from the
            Link header which already has all params embedded.

        Returns
        -------
        list[dict]
            All items concatenated across pages, capped at _MAX_RESULTS.
        """
        results: list[dict[str, Any]] = []
        url: str | None = initial_url
        first_page = True

        while url and len(results) < _MAX_RESULTS:
            if first_page:
                resp = await self._request("GET", url, params=params)
                first_page = False
            else:
                resp = await self._request("GET", url)

            resp.raise_for_status()
            page_data = resp.json()
            if not isinstance(page_data, list):
                break
            results.extend(page_data)
            url = _next_link(resp.headers.get("link"))

        return results[:_MAX_RESULTS]

    # ─────────────────────────────────────────────────────────────────────────
    # Public API methods
    # ─────────────────────────────────────────────────────────────────────────

    async def list_code_scanning_alerts(
        self,
        since: Optional[datetime] = None,
        state: str = "open",
    ) -> list[dict[str, Any]]:
        """
        List code scanning alerts for the organization.

        GET /orgs/{org}/code-scanning/alerts?state=open&sort=updated&direction=desc

        Parameters
        ----------
        since : datetime, optional
            If provided, only return alerts updated at or after this timestamp.
            Note: GitHub does not support a native `since` filter on this endpoint;
            filtering is done client-side after pagination.
        state : str
            Alert state filter — "open", "dismissed", "auto-dismissed", or "fixed".

        Returns
        -------
        list[dict]
            Raw GitHub API alert objects (up to _MAX_RESULTS).
        """
        url = f"{self.api_url}/orgs/{self.org}/code-scanning/alerts"
        params: dict[str, Any] = {
            "state": state,
            "sort": "updated",
            "direction": "desc",
            "per_page": _PER_PAGE,
        }
        alerts = await self._paginate(url, params)

        if since is not None:
            since_utc = since if since.tzinfo else since.replace(tzinfo=__import__("datetime").timezone.utc)
            filtered = []
            for alert in alerts:
                updated = alert.get("updated_at") or alert.get("created_at")
                if updated:
                    try:
                        from datetime import datetime as dt, timezone
                        alert_dt = dt.fromisoformat(updated.replace("Z", "+00:00"))
                        if alert_dt >= since_utc:
                            filtered.append(alert)
                    except ValueError:
                        filtered.append(alert)
                else:
                    filtered.append(alert)
            return filtered

        return alerts

    async def list_secret_scanning_alerts(
        self,
        since: Optional[datetime] = None,
        state: str = "open",
    ) -> list[dict[str, Any]]:
        """
        List secret scanning alerts for the organization.

        GET /orgs/{org}/secret-scanning/alerts?state=open

        Parameters
        ----------
        since : datetime, optional
            Client-side filter on `updated_at`.
        state : str
            "open" or "resolved".
        """
        url = f"{self.api_url}/orgs/{self.org}/secret-scanning/alerts"
        params: dict[str, Any] = {
            "state": state,
            "per_page": _PER_PAGE,
        }
        alerts = await self._paginate(url, params)

        if since is not None:
            since_utc = since if since.tzinfo else since.replace(tzinfo=__import__("datetime").timezone.utc)
            filtered = []
            for alert in alerts:
                updated = alert.get("updated_at") or alert.get("created_at")
                if updated:
                    try:
                        from datetime import datetime as dt, timezone
                        alert_dt = dt.fromisoformat(updated.replace("Z", "+00:00"))
                        if alert_dt >= since_utc:
                            filtered.append(alert)
                    except ValueError:
                        filtered.append(alert)
                else:
                    filtered.append(alert)
            return filtered

        return alerts

    async def list_dependabot_alerts(
        self,
        since: Optional[datetime] = None,
        state: str = "open",
    ) -> list[dict[str, Any]]:
        """
        List Dependabot alerts for the organization.

        GET /orgs/{org}/dependabot/alerts?state=open

        Parameters
        ----------
        since : datetime, optional
            Client-side filter on `updated_at`.
        state : str
            "open", "dismissed", "fixed", "auto-dismissed".
        """
        url = f"{self.api_url}/orgs/{self.org}/dependabot/alerts"
        params: dict[str, Any] = {
            "state": state,
            "per_page": _PER_PAGE,
        }
        alerts = await self._paginate(url, params)

        if since is not None:
            since_utc = since if since.tzinfo else since.replace(tzinfo=__import__("datetime").timezone.utc)
            filtered = []
            for alert in alerts:
                updated = alert.get("updated_at") or alert.get("auto_dismissed_at") or alert.get("created_at")
                if updated:
                    try:
                        from datetime import datetime as dt, timezone
                        alert_dt = dt.fromisoformat(updated.replace("Z", "+00:00"))
                        if alert_dt >= since_utc:
                            filtered.append(alert)
                    except ValueError:
                        filtered.append(alert)
                else:
                    filtered.append(alert)
            return filtered

        return alerts

    async def healthcheck(self) -> dict[str, Any]:
        """
        Verify token + org access.

        GET /orgs/{org}

        Returns the GitHub org JSON on success. Raises ConnectorAuthError on
        401/403 and ConnectorFetchError on 5xx.
        """
        url = f"{self.api_url}/orgs/{self.org}"
        resp = await self._request("GET", url)
        if resp.status_code == 404:
            raise ConnectorFetchError(
                f"GHAS: organization '{self.org}' not found — check org name."
            )
        resp.raise_for_status()
        return resp.json()

    async def close(self) -> None:
        """Close the underlying httpx.AsyncClient."""
        await self._client.aclose()

    async def __aenter__(self) -> "GhasAPIClient":
        return self

    async def __aexit__(self, *args: Any) -> None:
        await self.close()
