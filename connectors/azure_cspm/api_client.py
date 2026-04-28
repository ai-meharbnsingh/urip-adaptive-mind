"""
Sync HTTPX client for Azure Management and Resource Graph APIs.

Handles:
- OAuth2 client_credentials authentication
- Token caching with automatic refresh
- Simple retry on HTTP 429 (rate limit)
"""

from __future__ import annotations

import logging
import time
from typing import Any, Optional

import httpx

logger = logging.getLogger(__name__)

DEFAULT_BASE_URL = "https://management.azure.com"
DEFAULT_TIMEOUT = 30.0
TOKEN_ENDPOINT_TEMPLATE = (
    "https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token"
)


class AzureCspmApiClient:
    """Synchronous HTTPX client for Azure CSPM APIs."""

    def __init__(
        self,
        tenant_id: str,
        client_id: str,
        client_secret: str,
        base_url: str = DEFAULT_BASE_URL,
        timeout: float = DEFAULT_TIMEOUT,
    ) -> None:
        self.tenant_id = tenant_id
        self.client_id = client_id
        self.client_secret = client_secret
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self._access_token: Optional[str] = None
        self._token_expires_at: float = 0.0
        self._client = httpx.Client(timeout=timeout, follow_redirects=True)

    def _get_access_token(self) -> str:
        """Fetch or refresh an Azure AD access token via client_credentials."""
        now = time.time()
        if self._access_token and now < (self._token_expires_at - 60):
            return self._access_token

        token_url = TOKEN_ENDPOINT_TEMPLATE.format(tenant_id=self.tenant_id)
        payload = {
            "grant_type": "client_credentials",
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "scope": "https://management.azure.com/.default",
        }
        resp = self._client.post(token_url, data=payload)
        resp.raise_for_status()
        data = resp.json()
        self._access_token = data["access_token"]
        expires_in = data.get("expires_in", 3600)
        self._token_expires_at = now + expires_in
        logger.debug("Azure AD token obtained, expires in %s seconds", expires_in)
        return self._access_token

    def _auth_headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._get_access_token()}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    def _request(self, method: str, path: str, **kwargs: Any) -> httpx.Response:
        """Execute an HTTP request with simple 429 retry."""
        url = (
            f"{self.base_url}{path}"
            if path.startswith("/")
            else f"{self.base_url}/{path}"
        )
        headers = kwargs.pop("headers", {})
        headers.update(self._auth_headers())
        logger.debug("Azure API %s %s", method, url)
        response = self._client.request(method, url, headers=headers, **kwargs)
        if response.status_code == 429:
            retry_after = int(response.headers.get("Retry-After", 2))
            logger.warning(
                "Azure API rate limited (429). Retrying after %s seconds.", retry_after
            )
            time.sleep(retry_after)
            response = self._client.request(method, url, headers=headers, **kwargs)
        return response

    def validate_auth(self) -> bool:
        """Validate credentials by obtaining an access token."""
        try:
            self._get_access_token()
            return True
        except httpx.HTTPStatusError as exc:
            logger.warning("Azure auth validation failed: %s", exc.response.status_code)
            return False
        except Exception:
            logger.exception("Azure auth validation error")
            return False

    def _list_subscriptions(self) -> list[str]:
        """Return subscription IDs accessible to the service principal."""
        resp = self._request("GET", "/subscriptions?api-version=2020-01-01")
        resp.raise_for_status()
        data = resp.json()
        return [
            s["subscriptionId"]
            for s in data.get("value", [])
            if "subscriptionId" in s
        ]

    def list_policy_compliance(self) -> list[dict[str, Any]]:
        """Fetch non-compliant Azure Policy states per subscription."""
        results: list[dict[str, Any]] = []
        for sub_id in self._list_subscriptions():
            path = (
                f"/subscriptions/{sub_id}/providers/Microsoft.PolicyInsights/"
                f"policyStates/latest/queryResults?api-version=2019-10-01"
                f"&$filter=complianceState eq 'NonCompliant'"
            )
            resp = self._request("GET", path)
            resp.raise_for_status()
            data = resp.json()
            for item in data.get("value", []):
                item["subscriptionId"] = item.get("subscriptionId") or sub_id
                results.append(item)
        return results

    def list_defender_recommendations(self) -> list[dict[str, Any]]:
        """Fetch Defender for Cloud recommendations per subscription."""
        results: list[dict[str, Any]] = []
        for sub_id in self._list_subscriptions():
            path = (
                f"/subscriptions/{sub_id}/providers/Microsoft.Security/"
                f"assessments?api-version=2023-01-01"
            )
            resp = self._request("GET", path)
            resp.raise_for_status()
            data = resp.json()
            for item in data.get("value", []):
                item["subscriptionId"] = item.get("subscriptionId") or sub_id
                results.append(item)
        return results

    def list_defender_alerts(self) -> list[dict[str, Any]]:
        """Fetch Defender for Cloud alerts per subscription."""
        results: list[dict[str, Any]] = []
        for sub_id in self._list_subscriptions():
            path = (
                f"/subscriptions/{sub_id}/providers/Microsoft.Security/"
                f"alerts?api-version=2022-01-01"
            )
            resp = self._request("GET", path)
            resp.raise_for_status()
            data = resp.json()
            for item in data.get("value", []):
                item["subscriptionId"] = item.get("subscriptionId") or sub_id
                results.append(item)
        return results

    def query_resource_graph(self, query: str) -> list[dict[str, Any]]:
        """Execute a KQL query against Azure Resource Graph."""
        payload = {"query": query}
        resp = self._request(
            "POST",
            "/providers/Microsoft.ResourceGraph/resources?api-version=2021-03-01",
            json=payload,
        )
        resp.raise_for_status()
        data = resp.json()
        return data.get("data", [])

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> AzureCspmApiClient:
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()
