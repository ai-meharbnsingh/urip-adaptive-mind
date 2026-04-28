"""
Thin HTTPX client wrapper for ManageEngine MDM REST API.

Handles:
- Authentication via API token header
- Rate-limit throttling
- Request/response lifecycle
"""

from __future__ import annotations

import logging
import time
from typing import Any, Optional

import httpx

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT = 30.0
DEFAULT_MAX_REQUESTS_PER_HOUR = 2000


class ManageEngineMDMAPIClient:
    """Synchronous HTTPX client for ManageEngine MDM."""

    def __init__(
        self,
        base_url: str,
        api_token: str,
        timeout: float = DEFAULT_TIMEOUT,
        max_requests_per_hour: int = DEFAULT_MAX_REQUESTS_PER_HOUR,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_token = api_token
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
            "Authorization": f"Bearer {self.api_token}",
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
        logger.debug("ManageEngine MDM API %s %s", method, url)
        response = self._client.request(method, url, **kwargs)
        return response

    def validate_auth(self) -> bool:
        """
        Validate credentials by calling GET /api/v1/mdm/devices with a small limit.
        Returns True if 200, False otherwise.
        """
        try:
            resp = self._request("GET", "/api/v1/mdm/devices", params={"limit": 1})
            resp.raise_for_status()
            return True
        except httpx.HTTPStatusError as exc:
            logger.warning(
                "ManageEngine MDM auth validation failed: %s", exc.response.status_code
            )
            return False
        except Exception:
            logger.exception("ManageEngine MDM auth validation error")
            return False

    def list_devices(self, limit: int = 100, offset: int = 0) -> dict[str, Any]:
        """Fetch mobile devices from /api/v1/mdm/devices."""
        resp = self._request(
            "GET",
            "/api/v1/mdm/devices",
            params={"limit": limit, "offset": offset},
        )
        resp.raise_for_status()
        return resp.json()

    def list_lost_stolen_events(self, limit: int = 100, offset: int = 0) -> dict[str, Any]:
        """Fetch lost/stolen events from /api/v1/mdm/lost_stolen."""
        resp = self._request(
            "GET",
            "/api/v1/mdm/lost_stolen",
            params={"limit": limit, "offset": offset},
        )
        resp.raise_for_status()
        return resp.json()

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> ManageEngineMDMAPIClient:
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()
