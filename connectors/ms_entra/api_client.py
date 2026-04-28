"""
Thin HTTPX client wrapper for Microsoft Graph API.

Handles:
- OAuth2 client credentials flow against login.microsoftonline.com
- Graph API throttling (Retry-After header)
- Pagination via @odata.nextLink
- Request/response lifecycle
"""

from __future__ import annotations

import logging
import time
from typing import Any, Optional

import httpx

from connectors.ms_entra.schemas import MsEntraOAuthToken

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT = 30.0
GRAPH_BASE = "https://graph.microsoft.com/v1.0"
TOKEN_URL_TEMPLATE = (
    "https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token"
)


class MsEntraAPIClient:
    """Synchronous HTTPX client for Microsoft Graph."""

    def __init__(
        self,
        tenant_id: str,
        client_id: str,
        client_secret: str,
        timeout: float = DEFAULT_TIMEOUT,
    ) -> None:
        self.tenant_id = tenant_id
        self.client_id = client_id
        self.client_secret = client_secret
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
        url = f"{GRAPH_BASE}{path}"
        headers = self._auth_headers()
        if "headers" in kwargs:
            headers.update(kwargs.pop("headers"))
        logger.debug("MS Graph API %s %s", method, url)
        response = self._client.request(method, url, headers=headers, **kwargs)
        return response

    def _handle_throttle(self, response: httpx.Response) -> bool:
        """
        If response is 429, sleep for Retry-After seconds and return True.
        Otherwise return False.
        """
        if response.status_code == 429:
            retry_after = response.headers.get("Retry-After")
            if retry_after:
                sleep_seconds = int(retry_after)
                logger.warning(
                    "MS Graph throttled. Sleeping %d seconds.", sleep_seconds
                )
                time.sleep(sleep_seconds)
                return True
        return False

    def authenticate(self) -> bool:
        """
        Obtain OAuth2 access token via client credentials flow.
        Returns True if successful, False otherwise.
        """
        token_url = TOKEN_URL_TEMPLATE.format(tenant_id=self.tenant_id)
        try:
            resp = self._client.post(
                token_url,
                data={
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "grant_type": "client_credentials",
                    "scope": "https://graph.microsoft.com/.default",
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            resp.raise_for_status()
            token_data = MsEntraOAuthToken.model_validate(resp.json())
            self._access_token = token_data.access_token
            return True
        except httpx.HTTPStatusError as exc:
            logger.warning("MS Entra auth failed: %s", exc.response.status_code)
            return False
        except Exception:
            logger.exception("MS Entra auth error")
            return False

    def _get_list(self, path: str, params: Optional[dict] = None) -> dict[str, Any]:
        """
        Fetch a paginated Graph list endpoint.
        Follows @odata.nextLink until exhausted.
        Returns merged dict with all values.
        """
        all_values: list[dict[str, Any]] = []
        next_link: Optional[str] = None

        while True:
            if next_link:
                # nextLink is absolute URL
                resp = self._client.get(next_link, headers=self._auth_headers())
            else:
                resp = self._request("GET", path, params=params)

            if self._handle_throttle(resp):
                # Retry once after throttling
                if next_link:
                    resp = self._client.get(next_link, headers=self._auth_headers())
                else:
                    resp = self._request("GET", path, params=params)

            resp.raise_for_status()
            data = resp.json()
            values = data.get("value", [])
            all_values.extend(values)

            next_link = data.get("@odata.nextLink")
            if not next_link:
                break

        return {"value": all_values}

    def list_risky_users(self) -> dict[str, Any]:
        """Fetch risky users from /identityProtection/riskyUsers."""
        return self._get_list("/identityProtection/riskyUsers")

    def list_risk_detections(self) -> dict[str, Any]:
        """Fetch risk detections from /identityProtection/riskDetections."""
        return self._get_list("/identityProtection/riskDetections")

    def list_risky_signins(self) -> dict[str, Any]:
        """Fetch risky sign-ins from /auditLogs/signIns with filter."""
        return self._get_list(
            "/auditLogs/signIns",
            params={"$filter": "riskLevelDuringSignIn ne 'none'"},
        )

    def list_ca_policy_results(self) -> dict[str, Any]:
        """Fetch CA policy results from /identityProtection/conditionalAccessPolicyResults."""
        return self._get_list("/identityProtection/conditionalAccessPolicyResults")

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> MsEntraAPIClient:
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()
