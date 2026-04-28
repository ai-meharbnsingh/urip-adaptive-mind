"""
Thin HTTPX client for AuthBridge BGV API.

Auth: Authorization: Bearer <api_token>
Base: https://api.authbridge.com (default)
"""
from __future__ import annotations

import logging
import time
from typing import Any

import httpx

logger = logging.getLogger(__name__)

DEFAULT_BASE_URL = "https://api.authbridge.com"
DEFAULT_TIMEOUT = 30.0
DEFAULT_MAX_REQUESTS_PER_MINUTE = 60  # AuthBridge enforces conservative limits


class AuthBridgeAPIClient:
    """Synchronous HTTPX client for AuthBridge."""

    def __init__(
        self,
        api_token: str,
        base_url: str = DEFAULT_BASE_URL,
        timeout: float = DEFAULT_TIMEOUT,
        max_requests_per_minute: int = DEFAULT_MAX_REQUESTS_PER_MINUTE,
    ) -> None:
        self.api_token = api_token
        self.base_url = base_url.rstrip("/")
        self._min_interval = 60.0 / max_requests_per_minute
        self._last_request_time: float | None = None
        self._client = httpx.Client(
            timeout=timeout,
            headers={
                "Authorization": f"Bearer {api_token}",
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
            resp = self._request("GET", "/v1/account")
            resp.raise_for_status()
            return True
        except httpx.HTTPStatusError:
            return False
        except Exception:
            logger.exception("AuthBridge auth validation error")
            return False

    def list_verifications(self, since_iso: str | None = None) -> list[dict[str, Any]]:
        params: dict[str, Any] = {}
        if since_iso:
            params["initiated_since"] = since_iso
        resp = self._request("GET", "/v1/verifications", params=params)
        resp.raise_for_status()
        body = resp.json()
        return body.get("data", body if isinstance(body, list) else [])

    def close(self) -> None:
        self._client.close()
