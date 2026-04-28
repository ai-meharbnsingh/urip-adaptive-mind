"""
Thin HTTPX client wrapper for Burp Suite Enterprise REST API.

Handles:
- Authentication via API key header
- Rate-limit throttling
- Request/response lifecycle
- Supports both REST /api/v2 and GraphQL /graphql
"""

from __future__ import annotations

import logging
import time
from typing import Any, Optional

import httpx

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT = 30.0
DEFAULT_MAX_REQUESTS_PER_HOUR = 1000


class BurpEnterpriseAPIClient:
    """Synchronous HTTPX client for Burp Suite Enterprise."""

    def __init__(
        self,
        base_url: str,
        api_key: str,
        timeout: float = DEFAULT_TIMEOUT,
        max_requests_per_hour: int = DEFAULT_MAX_REQUESTS_PER_HOUR,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout
        self.max_requests_per_hour = max_requests_per_hour
        self._min_interval = 3600.0 / max_requests_per_hour
        self._last_request_time: Optional[float] = None
        self._client = httpx.Client(
            timeout=timeout,
            headers=self._auth_headers(),
            follow_redirects=True,
        )

    def _auth_headers(self) -> dict[str, str]:
        return {
            "Authorization": self.api_key,
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    def _throttle(self) -> None:
        """Enforce inter-request delay to respect rate limits."""
        if self._last_request_time is not None:
            elapsed = time.time() - self._last_request_time
            if elapsed < self._min_interval:
                sleep_time = self._min_interval - elapsed
                time.sleep(sleep_time)
        self._last_request_time = time.time()

    def _request(self, method: str, path: str, **kwargs: Any) -> httpx.Response:
        self._throttle()
        url = f"{self.base_url}{path}"
        logger.debug("Burp Enterprise API %s %s", method, url)
        response = self._client.request(method, url, **kwargs)
        return response

    def validate_auth(self) -> bool:
        """
        Validate credentials by calling GET /api/v2/scans with a small limit.
        Returns True if 200, False otherwise.
        """
        try:
            resp = self._request("GET", "/api/v2/scans", params={"limit": 1})
            resp.raise_for_status()
            return True
        except httpx.HTTPStatusError as exc:
            logger.warning(
                "Burp Enterprise auth validation failed: %s", exc.response.status_code
            )
            return False
        except Exception:
            logger.exception("Burp Enterprise auth validation error")
            return False

    def list_scans(self, limit: int = 100, offset: int = 0) -> dict[str, Any]:
        """Fetch scans from /api/v2/scans."""
        resp = self._request(
            "GET",
            "/api/v2/scans",
            params={"limit": limit, "offset": offset},
        )
        resp.raise_for_status()
        return resp.json()

    def list_issues(self, scan_id: str, limit: int = 100, offset: int = 0) -> dict[str, Any]:
        """Fetch issues for a scan from /api/v2/scans/{scan_id}/issues."""
        resp = self._request(
            "GET",
            f"/api/v2/scans/{scan_id}/issues",
            params={"limit": limit, "offset": offset},
        )
        resp.raise_for_status()
        return resp.json()

    def graphql_query(self, query: str, variables: Optional[dict] = None) -> dict[str, Any]:
        """Execute a GraphQL query against /graphql."""
        payload: dict[str, Any] = {"query": query}
        if variables:
            payload["variables"] = variables
        resp = self._request("POST", "/graphql", json=payload)
        resp.raise_for_status()
        return resp.json()

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> BurpEnterpriseAPIClient:
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()
