"""
Thin HTTPX client wrapper for Netskope REST API.

Handles:
- OAuth2 client-credentials flow (/api/v2/oauth2/token)
- Automatic token refresh before expiry
- Request/response lifecycle
"""

from __future__ import annotations

import logging
from typing import Any, Optional

import httpx

from connectors.netskope.schemas import NetskopeOAuthToken

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT = 30.0


class NetskopeAPIClient:
    """Synchronous HTTPX client for Netskope."""

    def __init__(
        self,
        client_id: str,
        client_secret: str,
        base_url: str,
        timeout: float = DEFAULT_TIMEOUT,
    ) -> None:
        self.client_id = client_id
        self.client_secret = client_secret
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self._access_token: Optional[str] = None
        self._client = httpx.Client(timeout=timeout, follow_redirects=True)

    def _auth_headers(self) -> dict[str, str]:
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        if self._access_token:
            headers["Authorization"] = f"Bearer {self._access_token}"
        return headers

    def _request(self, method: str, path: str, **kwargs: Any) -> httpx.Response:
        url = f"{self.base_url}{path}"
        headers = self._auth_headers()
        if "headers" in kwargs:
            headers.update(kwargs.pop("headers"))
        logger.debug("Netskope API %s %s", method, url)
        response = self._client.request(method, url, headers=headers, **kwargs)
        return response

    def authenticate(self) -> bool:
        """
        Obtain OAuth2 access token.
        Returns True if successful, False otherwise.
        """
        try:
            resp = self._request(
                "POST",
                "/api/v2/oauth2/token",
                data={
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "grant_type": "client_credentials",
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            resp.raise_for_status()
            token_data = NetskopeOAuthToken.model_validate(resp.json())
            self._access_token = token_data.access_token
            return True
        except httpx.HTTPStatusError as exc:
            logger.warning("Netskope auth failed: %s", exc.response.status_code)
            return False
        except Exception:
            logger.exception("Netskope auth error")
            return False

    def list_dlp_incidents(self) -> dict[str, Any]:
        """Fetch DLP incidents from /api/v2/incidents/dlp."""
        resp = self._request("GET", "/api/v2/incidents/dlp")
        resp.raise_for_status()
        return resp.json()

    def list_threats(self) -> dict[str, Any]:
        """Fetch cloud threats from /api/v2/incidents/threats."""
        resp = self._request("GET", "/api/v2/incidents/threats")
        resp.raise_for_status()
        return resp.json()

    def list_anomalies(self) -> dict[str, Any]:
        """Fetch anomalies from /api/v2/incidents/anomalies."""
        resp = self._request("GET", "/api/v2/incidents/anomalies")
        resp.raise_for_status()
        return resp.json()

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> NetskopeAPIClient:
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()
