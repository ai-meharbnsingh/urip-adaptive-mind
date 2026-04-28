"""
Thin HTTPX client wrapper for CloudSEK API.

Handles:
- Authentication via Authorization: Bearer <api_key> + X-Org-Id: <org_id>
- Cursor-based pagination helpers
- Rate-limit throttling (default 200 req/hour conservative)
- Retry-After header honoring on HTTP 429
- Request/response lifecycle

Design note: BaseConnector.fetch_findings is synchronous, so this client
uses httpx.Client (sync). Retry-After sleep blocks the scheduler thread,
which is acceptable for connector polling ticks.
"""

from __future__ import annotations

import logging
import time
from typing import Any, Optional

import httpx

logger = logging.getLogger(__name__)

DEFAULT_BASE_URL = "https://api.cloudsek.com"
DEFAULT_TIMEOUT = 30.0
# CloudSEK documented rate limit is ~200 req/hour for most tenants.
# We default to 200 req/hour to stay safely under the ceiling.
DEFAULT_MAX_REQUESTS_PER_HOUR = 200


class CloudSEKAPIClient:
    """Synchronous HTTPX client for CloudSEK XVigil + BeVigil + SVigil APIs."""

    def __init__(
        self,
        api_key: str,
        org_id: str,
        base_url: str = DEFAULT_BASE_URL,
        timeout: float = DEFAULT_TIMEOUT,
        max_requests_per_hour: int = DEFAULT_MAX_REQUESTS_PER_HOUR,
    ) -> None:
        self.api_key = api_key
        self.org_id = org_id
        self.base_url = base_url.rstrip("/")
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
            "Authorization": f"Bearer {self.api_key}",
            "X-Org-Id": self.org_id,
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
        """Execute a request with throttling and Retry-After handling."""
        self._throttle()
        url = f"{self.base_url}{path}"
        logger.debug("CloudSEK API %s %s", method, url)
        response = self._client.request(method, url, **kwargs)

        # Honor Retry-After on rate-limit responses
        if response.status_code == 429:
            retry_after = response.headers.get("Retry-After")
            if retry_after is not None:
                try:
                    sleep_seconds = float(retry_after)
                    logger.warning(
                        "CloudSEK rate limited (429). Sleeping %s seconds per Retry-After.",
                        sleep_seconds,
                    )
                    time.sleep(sleep_seconds)
                    # Retry once after sleeping
                    self._throttle()
                    response = self._client.request(method, url, **kwargs)
                except ValueError:
                    logger.warning("CloudSEK returned non-numeric Retry-After: %s", retry_after)

        return response

    def validate_auth(self) -> bool:
        """
        Validate credentials by calling GET /v1/health.
        Returns True if 200, False on any HTTP error or exception.
        """
        try:
            resp = self._request("GET", "/v1/health")
            resp.raise_for_status()
            return True
        except httpx.HTTPStatusError as exc:
            logger.warning(
                "CloudSEK auth validation failed: %s", exc.response.status_code
            )
            return False
        except Exception:
            logger.exception("CloudSEK auth validation error")
            return False

    def list_xvigil_alerts(
        self,
        since: Optional[str] = None,
        cursor: Optional[str] = None,
        limit: int = 100,
    ) -> dict[str, Any]:
        """Fetch XVigil alerts with optional time filter and cursor pagination."""
        params: dict[str, Any] = {"limit": limit}
        if since:
            params["since"] = since
        if cursor:
            params["cursor"] = cursor
        resp = self._request("GET", "/v1/xvigil/alerts", params=params)
        resp.raise_for_status()
        return resp.json()

    def list_bevigil_findings(
        self,
        since: Optional[str] = None,
        cursor: Optional[str] = None,
        limit: int = 100,
    ) -> dict[str, Any]:
        """Fetch BeVigil findings with optional time filter and cursor pagination."""
        params: dict[str, Any] = {"limit": limit}
        if since:
            params["since"] = since
        if cursor:
            params["cursor"] = cursor
        resp = self._request("GET", "/v1/bevigil/findings", params=params)
        resp.raise_for_status()
        return resp.json()

    def list_svigil_risks(
        self,
        since: Optional[str] = None,
        cursor: Optional[str] = None,
        limit: int = 100,
    ) -> dict[str, Any]:
        """Fetch SVigil risks with optional time filter and cursor pagination."""
        params: dict[str, Any] = {"limit": limit}
        if since:
            params["since"] = since
        if cursor:
            params["cursor"] = cursor
        resp = self._request("GET", "/v1/svigil/risks", params=params)
        resp.raise_for_status()
        return resp.json()

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> CloudSEKAPIClient:
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()
