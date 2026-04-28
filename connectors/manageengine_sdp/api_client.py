"""
Thin HTTPX client wrapper for ManageEngine ServiceDesk Plus REST API v3.

Handles:
- OAuth2 token refresh (client_id + client_secret + refresh_token)
- Auth Token (older) authentication via authtoken header
- Bidirectional ticket creation (POST /api/v3/requests)
- Request/response lifecycle
"""

from __future__ import annotations

import logging
from typing import Any, Optional

import httpx

from connectors.manageengine_sdp.schemas import ManageEngineSdpOAuthToken

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT = 30.0


class ManageEngineSdpAPIClient:
    """Synchronous HTTPX client for ManageEngine SDP."""

    def __init__(
        self,
        auth_method: str,
        base_url: str,
        client_id: Optional[str] = None,
        client_secret: Optional[str] = None,
        refresh_token: Optional[str] = None,
        auth_token: Optional[str] = None,
        timeout: float = DEFAULT_TIMEOUT,
    ) -> None:
        self.auth_method = auth_method.lower()
        self.base_url = base_url.rstrip("/")
        self.client_id = client_id
        self.client_secret = client_secret
        self.refresh_token = refresh_token
        self.auth_token = auth_token
        self.timeout = timeout
        self._access_token: Optional[str] = None
        self._client = httpx.Client(timeout=timeout, follow_redirects=True)

    def _auth_headers(self) -> dict[str, str]:
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        if self.auth_method == "oauth" and self._access_token:
            headers["Authorization"] = f"Bearer {self._access_token}"
        elif self.auth_method == "token" and self.auth_token:
            headers["authtoken"] = self.auth_token
        return headers

    def _request(self, method: str, path: str, **kwargs: Any) -> httpx.Response:
        url = f"{self.base_url}{path}"
        headers = self._auth_headers()
        if "headers" in kwargs:
            headers.update(kwargs.pop("headers"))
        logger.debug("ManageEngine SDP API %s %s", method, url)
        response = self._client.request(method, url, headers=headers, **kwargs)
        return response

    def authenticate(self) -> bool:
        """
        Authenticate based on auth_method.
        Returns True if successful, False otherwise.
        """
        if self.auth_method == "oauth":
            return self._authenticate_oauth()
        elif self.auth_method == "token":
            # Auth token is assumed valid; no separate validation step
            return bool(self.auth_token)
        return False

    def _authenticate_oauth(self) -> bool:
        try:
            resp = self._client.post(
                f"{self.base_url}/api/v3/token",
                data={
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "refresh_token": self.refresh_token,
                    "grant_type": "refresh_token",
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            resp.raise_for_status()
            token_data = ManageEngineSdpOAuthToken.model_validate(resp.json())
            self._access_token = token_data.access_token
            return True
        except httpx.HTTPStatusError as exc:
            logger.warning("ManageEngine SDP auth failed: %s", exc.response.status_code)
            return False
        except Exception:
            logger.exception("ManageEngine SDP auth error")
            return False

    def list_requests(self) -> dict[str, Any]:
        """Fetch tickets from /api/v3/requests."""
        resp = self._request("GET", "/api/v3/requests")
        resp.raise_for_status()
        return resp.json()

    def create_request(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Create a ticket via POST /api/v3/requests."""
        resp = self._request("POST", "/api/v3/requests", json=payload)
        resp.raise_for_status()
        return resp.json()

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> ManageEngineSdpAPIClient:
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()
