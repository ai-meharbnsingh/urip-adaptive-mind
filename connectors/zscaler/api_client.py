"""
Thin HTTPX client wrapper for Zscaler ZIA / ZTA / CASB API.

Handles:
- Authentication via /api/v1/authenticatedSession (cookie-based JSESSIONID)
- Cloud-specific base URLs (zscaler.net, zscalerone.net, zscalertwo.net, etc.)
- Request/response lifecycle
"""

from __future__ import annotations

import logging
from typing import Any, Optional

import httpx

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT = 30.0
CLOUD_URL_TEMPLATE = "https://zsapi.{cloud}.net"


class ZscalerAPIClient:
    """Synchronous HTTPX client for Zscaler APIs."""

    def __init__(
        self,
        api_key: str,
        username: str,
        password: str,
        cloud: str,
        timeout: float = DEFAULT_TIMEOUT,
    ) -> None:
        self.api_key = api_key
        self.username = username
        self.password = password
        self.cloud = cloud
        self.base_url = CLOUD_URL_TEMPLATE.format(cloud=cloud).rstrip("/")
        self.timeout = timeout
        self._client = httpx.Client(timeout=timeout, follow_redirects=True)
        self._jsessionid: Optional[str] = None

    def _auth_headers(self) -> dict[str, str]:
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "apiKey": self.api_key,
        }
        if self._jsessionid:
            headers["Cookie"] = f"JSESSIONID={self._jsessionid}"
        return headers

    def _request(self, method: str, path: str, **kwargs: Any) -> httpx.Response:
        url = f"{self.base_url}{path}"
        headers = self._auth_headers()
        if "headers" in kwargs:
            headers.update(kwargs.pop("headers"))
        logger.debug("Zscaler API %s %s", method, url)
        response = self._client.request(method, url, headers=headers, **kwargs)
        return response

    def authenticate(self) -> bool:
        """
        Authenticate and obtain JSESSIONID cookie.
        Returns True if successful, False otherwise.
        """
        try:
            resp = self._request(
                "POST",
                "/api/v1/authenticatedSession",
                json={
                    "apiKey": self.api_key,
                    "username": self.username,
                    "password": self.password,
                },
            )
            resp.raise_for_status()
            # Extract JSESSIONID from Set-Cookie header
            set_cookie = resp.headers.get("set-cookie", "")
            for part in set_cookie.split(";"):
                if "JSESSIONID=" in part:
                    self._jsessionid = part.split("JSESSIONID=")[1].strip()
                    break
            return True
        except httpx.HTTPStatusError as exc:
            logger.warning("Zscaler auth failed: %s", exc.response.status_code)
            return False
        except Exception:
            logger.exception("Zscaler auth error")
            return False

    def list_web_threats(self) -> dict[str, Any]:
        """Fetch web threats from /api/v1/threatIntel/threats."""
        resp = self._request("GET", "/api/v1/threatIntel/threats")
        resp.raise_for_status()
        return resp.json()

    def list_saas_apps(self) -> dict[str, Any]:
        """Fetch shadow SaaS apps from /api/v1/casb/saasApps."""
        resp = self._request("GET", "/api/v1/casb/saasApps")
        resp.raise_for_status()
        return resp.json()

    def list_admin_audit_logs(self) -> dict[str, Any]:
        """Fetch admin audit logs from /api/v1/users/admin/auditLogs."""
        resp = self._request("GET", "/api/v1/users/admin/auditLogs")
        resp.raise_for_status()
        return resp.json()

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> ZscalerAPIClient:
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()
