"""
Thin HTTPX client wrapper for SentinelOne Singularity API.

Handles:
- Authentication via Authorization: ApiToken <token> header
- Cursor-based pagination helpers
- Rate-limit throttling (default 200 req/min conservative)
- Request/response lifecycle
"""

from __future__ import annotations

import logging
import time
from typing import Any, Optional

import httpx

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT = 30.0
# SentinelOne rate limits vary by tier; we default to 200 req/min
# to stay well under typical ceilings.
DEFAULT_MAX_REQUESTS_PER_MINUTE = 200


class SentinelOneAPIClient:
    """Synchronous HTTPX client for SentinelOne Singularity."""

    def __init__(
        self,
        api_token: str,
        base_url: str,
        timeout: float = DEFAULT_TIMEOUT,
        max_requests_per_minute: int = DEFAULT_MAX_REQUESTS_PER_MINUTE,
    ) -> None:
        self.api_token = api_token
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.max_requests_per_minute = max_requests_per_minute
        self._min_interval = 60.0 / max_requests_per_minute
        self._last_request_time: Optional[float] = None
        self._client = httpx.Client(
            timeout=timeout,
            headers=self._auth_headers(),
            follow_redirects=True,
        )

    def _auth_headers(self) -> dict[str, str]:
        return {
            "Authorization": f"ApiToken {self.api_token}",
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
        logger.debug("SentinelOne API %s %s", method, url)
        response = self._client.request(method, url, **kwargs)
        return response

    def validate_auth(self) -> bool:
        """
        Validate token by calling GET /web/api/v2.1/system/info.
        Returns True if 200, False on any HTTP error or exception.
        """
        try:
            resp = self._request("GET", "/web/api/v2.1/system/info")
            resp.raise_for_status()
            return True
        except httpx.HTTPStatusError as exc:
            logger.warning(
                "SentinelOne auth validation failed: %s", exc.response.status_code
            )
            return False
        except Exception:
            logger.exception("SentinelOne auth validation error")
            return False

    def list_threats(
        self,
        since: Optional[str] = None,
        limit: int = 100,
        cursor: Optional[str] = None,
    ) -> dict[str, Any]:
        """Fetch threats with optional time filter and cursor pagination."""
        params: dict[str, Any] = {"limit": limit}
        if since:
            params["createdAt__gte"] = since
        if cursor:
            params["cursor"] = cursor
        resp = self._request("GET", "/web/api/v2.1/threats", params=params)
        resp.raise_for_status()
        return resp.json()

    def list_agents(
        self,
        limit: int = 100,
        cursor: Optional[str] = None,
    ) -> dict[str, Any]:
        """Fetch agents with cursor pagination."""
        params: dict[str, Any] = {"limit": limit}
        if cursor:
            params["cursor"] = cursor
        resp = self._request("GET", "/web/api/v2.1/agents", params=params)
        resp.raise_for_status()
        return resp.json()

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> SentinelOneAPIClient:
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()
