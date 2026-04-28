"""
Thin HTTPX client for KnowBe4 Reporting API.

Auth: Authorization: Bearer <api_key>
Base: https://us.api.knowbe4.com (or eu.api.knowbe4.com for EU pod)
Rate-limit: ~4 req/s — we throttle conservatively at 240 req/min.
"""
from __future__ import annotations

import logging
import time
from typing import Any

import httpx

logger = logging.getLogger(__name__)

DEFAULT_BASE_URL = "https://us.api.knowbe4.com"
DEFAULT_TIMEOUT = 30.0
DEFAULT_MAX_REQUESTS_PER_MINUTE = 240


class KnowBe4APIClient:
    """Synchronous HTTPX client for KnowBe4 Reporting API."""

    def __init__(
        self,
        api_key: str,
        base_url: str = DEFAULT_BASE_URL,
        timeout: float = DEFAULT_TIMEOUT,
        max_requests_per_minute: int = DEFAULT_MAX_REQUESTS_PER_MINUTE,
    ) -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.max_requests_per_minute = max_requests_per_minute
        self._min_interval = 60.0 / max_requests_per_minute
        self._last_request_time: float | None = None
        self._client = httpx.Client(
            timeout=timeout,
            headers=self._auth_headers(),
            follow_redirects=True,
        )

    def _auth_headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Accept": "application/json",
        }

    def _throttle(self) -> None:
        if self._last_request_time is not None:
            elapsed = time.time() - self._last_request_time
            if elapsed < self._min_interval:
                time.sleep(self._min_interval - elapsed)
        self._last_request_time = time.time()

    def _request(self, method: str, path: str, **kwargs: Any) -> httpx.Response:
        self._throttle()
        url = f"{self.base_url}{path}"
        logger.debug("KnowBe4 API %s %s", method, url)
        response = self._client.request(method, url, **kwargs)
        if response.status_code == 429:
            retry_after = response.headers.get("Retry-After")
            if retry_after:
                try:
                    time.sleep(float(retry_after))
                    self._throttle()
                    response = self._client.request(method, url, **kwargs)
                except ValueError:
                    pass
        return response

    def validate_auth(self) -> bool:
        try:
            resp = self._request("GET", "/v1/account")
            resp.raise_for_status()
            return True
        except httpx.HTTPStatusError:
            return False
        except Exception:
            logger.exception("KnowBe4 auth validation error")
            return False

    def list_training_enrollments(self, since_iso: str | None = None) -> list[dict[str, Any]]:
        """List training enrollments. Returns a flat list of enrollment dicts."""
        params: dict[str, Any] = {}
        if since_iso:
            params["modified_since"] = since_iso
        resp = self._request("GET", "/v1/training/enrollments", params=params)
        resp.raise_for_status()
        body = resp.json()
        # KnowBe4 returns either a list directly or {"data": [...]}
        if isinstance(body, list):
            return body
        return body.get("data", [])

    def list_phishing_recipients(self, since_iso: str | None = None) -> list[dict[str, Any]]:
        """List per-recipient phishing campaign results."""
        params: dict[str, Any] = {}
        if since_iso:
            params["delivered_since"] = since_iso
        resp = self._request(
            "GET", "/v1/phishing/security_tests/recipients", params=params
        )
        resp.raise_for_status()
        body = resp.json()
        if isinstance(body, list):
            return body
        return body.get("data", [])

    def close(self) -> None:
        self._client.close()
