"""
connectors/snyk/api_client.py — Async HTTPX client for Snyk REST API v2024-10-15.

Authentication
--------------
All requests use the ``Authorization: token {api_token}`` header.

Snyk REST API reference (v2024-10-15):
  https://apidocs.snyk.io/?version=2024-10-15

Pagination
----------
Snyk REST API paginates via a cursor embedded in ``links.next``.  The cursor
is an opaque URL — we follow it verbatim until there are no more pages or we
hit the cap of 1000 results.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Optional

import httpx

from connectors.base.connector import ConnectorAuthError, ConnectorFetchError

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT = 30.0
_API_VERSION = "2024-10-15"
_MAX_RESULTS_CAP = 1000


class SnykAPIClient:
    """
    Thin async HTTPX wrapper for Snyk REST API v2024-10-15.

    Parameters
    ----------
    org_id : str
        Snyk organization UUID (visible in Snyk → Settings → General →
        Organization ID).
    api_token : str
        Snyk API token (Snyk → Account Settings → API Token).
    api_url : str
        Base URL for the Snyk API.  Defaults to ``https://api.snyk.io``.
        Override for EU (``https://api.eu.snyk.io``) or AU
        (``https://api.au.snyk.io``) tenants.
    timeout : float
        HTTP request timeout in seconds (default 30).
    """

    def __init__(
        self,
        org_id: str,
        api_token: str,
        api_url: str = "https://api.snyk.io",
        timeout: float = DEFAULT_TIMEOUT,
    ) -> None:
        self.org_id = org_id
        self.api_token = api_token
        self.api_url = api_url.rstrip("/")
        self.timeout = timeout
        self._client = httpx.AsyncClient(timeout=timeout, follow_redirects=True)

    # ─────────────────────────────────────────────────────────────────────────
    # Internal helpers
    # ─────────────────────────────────────────────────────────────────────────

    def _auth_headers(self) -> dict[str, str]:
        return {
            "Authorization": f"token {self.api_token}",
            "Content-Type": "application/json",
            "Accept": "application/vnd.api+json",
        }

    async def _request(
        self,
        method: str,
        path: str,
        **kwargs: Any,
    ) -> httpx.Response:
        """Send a request, raise on 401 or 5xx."""
        url = f"{self.api_url}{path}"
        headers = self._auth_headers()
        if "headers" in kwargs:
            headers.update(kwargs.pop("headers"))

        logger.debug("Snyk API %s %s", method, url)
        response = await self._client.request(method, url, headers=headers, **kwargs)

        if response.status_code == 401:
            raise ConnectorAuthError(
                f"Snyk authentication failed — HTTP 401 for {url}. "
                "Verify your API token in Snyk → Account Settings → API Token."
            )
        if response.status_code >= 500:
            raise ConnectorFetchError(
                f"Snyk server error — HTTP {response.status_code} for {url}: "
                f"{response.text[:300]}"
            )

        return response

    # ─────────────────────────────────────────────────────────────────────────
    # Public API methods
    # ─────────────────────────────────────────────────────────────────────────

    async def list_issues(
        self,
        since: Optional[datetime] = None,
        severity: Optional[list[str]] = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """
        Fetch issues for the configured organization.

        GET /rest/orgs/{org_id}/issues?version=2024-10-15&…

        Snyk paginates via ``data`` array + ``links.next`` cursor URL.
        We follow pages until exhausted or the cap of 1000 results is reached.

        Parameters
        ----------
        since : datetime, optional
            Only return issues created/updated on or after this timestamp
            (ISO-8601 ``starting_after`` filter).
        severity : list[str], optional
            Filter by effective severity levels
            (e.g. ``["critical", "high"]``).
        limit : int
            Per-page limit (default 100, max 100 per Snyk docs).

        Returns
        -------
        list[dict]
            Flattened list of raw Snyk issue objects from ``data[]``.
        """
        params: dict[str, Any] = {
            "version": _API_VERSION,
            "limit": min(limit, 100),
        }
        if since is not None:
            params["starting_after"] = since.isoformat()
        if severity:
            params["effective_severity_level"] = ",".join(severity)

        path = f"/rest/orgs/{self.org_id}/issues"
        results: list[dict[str, Any]] = []

        while True:
            resp = await self._request("GET", path, params=params)
            resp.raise_for_status()
            body = resp.json()

            data = body.get("data", [])
            results.extend(data)

            if len(results) >= _MAX_RESULTS_CAP:
                logger.warning(
                    "Snyk: hit %d-result cap — truncating response.", _MAX_RESULTS_CAP
                )
                results = results[:_MAX_RESULTS_CAP]
                break

            # Follow cursor pagination
            next_url: Optional[str] = (body.get("links") or {}).get("next")
            if not next_url:
                break

            # The next_url is a full URL including the path+params; parse it.
            parsed = httpx.URL(next_url)
            path = parsed.path
            params = dict(parsed.params)

        logger.info(
            "Snyk: fetched %d issues for org %s", len(results), self.org_id
        )
        return results

    async def list_projects(self) -> list[dict[str, Any]]:
        """
        List all projects in the organization.

        GET /rest/orgs/{org_id}/projects?version=2024-10-15

        Returns
        -------
        list[dict]
            Flattened list of raw Snyk project objects from ``data[]``.
        """
        path = f"/rest/orgs/{self.org_id}/projects"
        params: dict[str, Any] = {"version": _API_VERSION, "limit": 100}
        results: list[dict[str, Any]] = []

        while True:
            resp = await self._request("GET", path, params=params)
            resp.raise_for_status()
            body = resp.json()

            data = body.get("data", [])
            results.extend(data)

            next_url: Optional[str] = (body.get("links") or {}).get("next")
            if not next_url:
                break

            parsed = httpx.URL(next_url)
            path = parsed.path
            params = dict(parsed.params)

        logger.info(
            "Snyk: fetched %d projects for org %s", len(results), self.org_id
        )
        return results

    async def get_target_for_issue(self, issue_id: str) -> dict[str, Any]:
        """
        Retrieve the target (repository / image / IaC file) for a given issue.

        GET /rest/orgs/{org_id}/issues/{issue_id}/relationships/target?version=2024-10-15

        Parameters
        ----------
        issue_id : str
            Snyk issue UUID.

        Returns
        -------
        dict
            Raw JSON body from the API (``data`` sub-object).
        """
        path = (
            f"/rest/orgs/{self.org_id}/issues/{issue_id}/relationships/target"
        )
        resp = await self._request("GET", path, params={"version": _API_VERSION})
        resp.raise_for_status()
        return resp.json()

    async def healthcheck(self) -> dict[str, Any]:
        """
        Verify token validity and org access.

        GET /rest/orgs/{org_id}?version=2024-10-15

        Returns the raw org JSON on success.

        Raises
        ------
        ConnectorAuthError
            If the token is invalid or lacks access to the org.
        ConnectorFetchError
            On 5xx server errors.
        """
        path = f"/rest/orgs/{self.org_id}"
        resp = await self._request("GET", path, params={"version": _API_VERSION})
        if resp.status_code == 404:
            raise ConnectorAuthError(
                f"Snyk org {self.org_id!r} not found — verify the Organization ID "
                "in Snyk → Settings → General → Organization ID."
            )
        resp.raise_for_status()
        return resp.json()

    async def close(self) -> None:
        """Close the underlying httpx.AsyncClient."""
        await self._client.aclose()

    async def __aenter__(self) -> "SnykAPIClient":
        return self

    async def __aexit__(self, *args: Any) -> None:
        await self.close()
