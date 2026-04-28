"""
Thin HTTPX client for OnGrid BGV API.

Auth: Authorization: Bearer <api_key> + X-API-Key (some endpoints require both)
Base: https://api.ongrid.in (default)
"""
from __future__ import annotations

import logging
import time
from typing import Any

import httpx

logger = logging.getLogger(__name__)

DEFAULT_BASE_URL = "https://api.ongrid.in"
DEFAULT_TIMEOUT = 30.0
DEFAULT_MAX_REQUESTS_PER_MINUTE = 60


class OnGridAPIClient:
    """Synchronous HTTPX client for OnGrid."""

    def __init__(
        self,
        api_key: str,
        base_url: str = DEFAULT_BASE_URL,
        timeout: float = DEFAULT_TIMEOUT,
        max_requests_per_minute: int = DEFAULT_MAX_REQUESTS_PER_MINUTE,
    ) -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self._min_interval = 60.0 / max_requests_per_minute
        self._last_request_time: float | None = None
        self._client = httpx.Client(
            timeout=timeout,
            headers={
                "Authorization": f"Bearer {api_key}",
                "X-API-Key": api_key,
                "Accept": "application/json",
            },
            follow_redirects=True,
        )

    def _throttle(self) -> None:
        if self._last_request_time is not None:
            elapsed = time.time() - self._last_request_time
            if elapsed < self._min_interval:
                time.sleep(self._min_interval - elapsed)
        self._last_request_time = time.time()

    def _request(self, method: str, path: str, **kwargs: Any) -> httpx.Response:
        self._throttle()
        url = f"{self.base_url}{path}"
        return self._client.request(method, url, **kwargs)

    def validate_auth(self) -> bool:
        try:
            resp = self._request("GET", "/v1/me")
            resp.raise_for_status()
            return True
        except httpx.HTTPStatusError:
            return False
        except Exception:
            logger.exception("OnGrid auth validation error")
            return False

    def list_checks(self, since_iso: str | None = None) -> list[dict[str, Any]]:
        params: dict[str, Any] = {}
        if since_iso:
            params["initiated_since"] = since_iso
        resp = self._request("GET", "/v1/checks", params=params)
        resp.raise_for_status()
        body = resp.json()
        # OnGrid returns {"results": [...]} per their docs
        return body.get("results", body.get("data", body if isinstance(body, list) else []))

    def close(self) -> None:
        self._client.close()
