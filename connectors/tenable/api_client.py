"""
Thin HTTPX client wrapper for Tenable.io Vulnerability Management API.

Handles:
- Authentication via X-ApiKeys header
- Rate-limit throttling (default 1000 req/hour to leave headroom)
- Request/response lifecycle
"""

from __future__ import annotations

import logging
import time
from typing import Any, Optional

import httpx

logger = logging.getLogger(__name__)

DEFAULT_BASE_URL = "https://cloud.tenable.com"
DEFAULT_TIMEOUT = 30.0
# Tenable.io default = 1500 req/hour. We throttle at 1000 to leave headroom
# for other integrations and bursts.
DEFAULT_MAX_REQUESTS_PER_HOUR = 1000


class TenableAPIClient:
    """Synchronous HTTPX client for Tenable.io."""

    def __init__(
        self,
        access_key: str,
        secret_key: str,
        base_url: str = DEFAULT_BASE_URL,
        timeout: float = DEFAULT_TIMEOUT,
        max_requests_per_hour: int = DEFAULT_MAX_REQUESTS_PER_HOUR,
    ) -> None:
        self.access_key = access_key
        self.secret_key = secret_key
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
            "X-ApiKeys": f"accessKey={self.access_key}; secretKey={self.secret_key}",
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
        logger.debug("Tenable API %s %s", method, url)
        response = self._client.request(method, url, **kwargs)
        return response

    def validate_auth(self) -> bool:
        """
        Validate credentials by calling GET /scans with a small limit.
        Returns True if 200, False if 401/403/429 or any other error.
        """
        try:
            resp = self._request("GET", "/scans", params={"limit": 1})
            resp.raise_for_status()
            return True
        except httpx.HTTPStatusError as exc:
            logger.warning(
                "Tenable auth validation failed: %s", exc.response.status_code
            )
            return False
        except Exception:
            logger.exception("Tenable auth validation error")
            return False

    def list_assets(self, limit: int = 100, offset: int = 0) -> dict[str, Any]:
        """Fetch assets from /workbenches/assets."""
        resp = self._request(
            "GET",
            "/workbenches/assets",
            params={"limit": limit, "offset": offset},
        )
        resp.raise_for_status()
        return resp.json()

    def list_asset_vulnerabilities(
        self,
        asset_uuid: str,
        limit: int = 100,
        offset: int = 0,
    ) -> dict[str, Any]:
        """Fetch vulnerabilities for a specific asset."""
        resp = self._request(
            "GET",
            f"/workbenches/assets/{asset_uuid}/vulnerabilities",
            params={"limit": limit, "offset": offset},
        )
        resp.raise_for_status()
        return resp.json()

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> TenableAPIClient:
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()
