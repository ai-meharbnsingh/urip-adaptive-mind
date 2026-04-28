"""
Async HTTPX client for HashiCorp Vault HTTP API v1.

Authentication
--------------
Token-based:  X-Vault-Token: {token}
Namespace:    X-Vault-Namespace: {namespace}   (Enterprise multi-tenancy only)

All methods are async and use httpx.AsyncClient.

Special status codes for /v1/sys/health
-----------------------------------------
200 → active + unsealed           (healthy)
429 → standby node                (healthy)
472 → disaster recovery secondary (degraded)
473 → performance standby         (healthy)
501 → not initialized             (critical)
503 → sealed                      (critical)

Vault HTTP API reference: https://developer.hashicorp.com/vault/api-docs
"""

from __future__ import annotations

import logging
from typing import Any, Optional

import httpx

from connectors.base.connector import ConnectorAuthError, ConnectorFetchError

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT = 30.0

# Health status codes that are considered "healthy" — Vault node is reachable
# and can serve secrets.
_HEALTHY_STATUS_CODES = {200, 429, 473}

# Health status codes indicating a degraded but reachable node.
_DEGRADED_STATUS_CODES = {472}

# Health status codes indicating a critical / unusable node.
_CRITICAL_STATUS_CODES = {501, 503}


class VaultAPIClient:
    """
    Thin async HTTPX wrapper for HashiCorp Vault HTTP API v1.

    Parameters
    ----------
    vault_addr : str
        Root URL of the Vault instance, e.g. "https://vault.your-org.com:8200".
    token : str
        Vault token (X-Vault-Token header).  Read-only ACL recommended.
    namespace : str, optional
        Vault Enterprise namespace path, e.g. "admin/teamA".
        When set, the X-Vault-Namespace header is added to every request.
    timeout : float
        HTTP request timeout in seconds (default 30).
    """

    def __init__(
        self,
        vault_addr: str,
        token: str,
        namespace: Optional[str] = None,
        timeout: float = DEFAULT_TIMEOUT,
    ) -> None:
        self.vault_addr = vault_addr.rstrip("/")
        self.token = token
        self.namespace = namespace or ""
        self.timeout = timeout

        self._client = httpx.AsyncClient(timeout=timeout, follow_redirects=True)

    # ─────────────────────────────────────────────────────────────────────────
    # Internal helpers
    # ─────────────────────────────────────────────────────────────────────────

    def _auth_headers(self) -> dict[str, str]:
        headers: dict[str, str] = {
            "X-Vault-Token": self.token,
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        if self.namespace:
            headers["X-Vault-Namespace"] = self.namespace
        return headers

    async def _request(
        self,
        method: str,
        path: str,
        **kwargs: Any,
    ) -> httpx.Response:
        """
        Send a request and handle common Vault error codes.

        NOTE: /v1/sys/health returns non-200 status codes intentionally
        (429, 473, etc.) — callers must handle those themselves without
        calling this method, or catch the exceptions and recheck.
        """
        url = f"{self.vault_addr}{path}"
        headers = self._auth_headers()
        if "headers" in kwargs:
            headers.update(kwargs.pop("headers"))

        logger.debug("Vault API %s %s", method, url)
        response = await self._client.request(method, url, headers=headers, **kwargs)

        if response.status_code == 403:
            raise ConnectorAuthError(
                f"Vault auth failed — HTTP 403 for {url}. "
                "Check token capabilities and namespace configuration."
            )
        if response.status_code >= 500:
            raise ConnectorFetchError(
                f"Vault server error — HTTP {response.status_code} for {url}: "
                f"{response.text[:300]}"
            )

        return response

    # ─────────────────────────────────────────────────────────────────────────
    # Public API methods
    # ─────────────────────────────────────────────────────────────────────────

    async def list_audit_devices(self) -> dict[str, Any]:
        """
        List all audit devices registered in Vault.

        GET /v1/sys/audit

        Returns an empty dict {} when no audit devices are configured —
        callers should treat that as "audit logging disabled".

        Returns
        -------
        dict
            Map of mount path → audit device object.
        """
        resp = await self._request("GET", "/v1/sys/audit")
        resp.raise_for_status()
        return resp.json()

    async def list_auth_methods(self) -> dict[str, Any]:
        """
        Enumerate all auth backends (methods) enabled in Vault.

        GET /v1/sys/auth

        Returns
        -------
        dict
            Map of mount path → auth method object.
            Each value includes: type, accessor, description, options.
        """
        resp = await self._request("GET", "/v1/sys/auth")
        resp.raise_for_status()
        return resp.json()

    async def list_policies(self) -> dict[str, Any]:
        """
        List all ACL policies in Vault.

        GET /v1/sys/policies/acl

        Returns
        -------
        dict
            {"keys": ["default", "root", "urip-readonly", …]}
        """
        resp = await self._request("GET", "/v1/sys/policies/acl")
        resp.raise_for_status()
        return resp.json()

    async def get_token_info(self) -> dict[str, Any]:
        """
        Retrieve metadata for the currently-authenticated token.

        GET /v1/auth/token/lookup-self

        Used to verify token validity and inspect attached policies —
        critical for detecting root-policy tokens.

        Returns
        -------
        dict
            {"data": {"id": "…", "policies": ["default", "urip-readonly"], …}}
        """
        resp = await self._request("GET", "/v1/auth/token/lookup-self")
        resp.raise_for_status()
        return resp.json()

    async def list_secret_engines(self) -> dict[str, Any]:
        """
        List all secret engine mount points.

        GET /v1/sys/mounts

        Returns
        -------
        dict
            Map of mount path → mount object.
            Each value includes: type, description, options (e.g. version for kv).
        """
        resp = await self._request("GET", "/v1/sys/mounts")
        resp.raise_for_status()
        return resp.json()

    async def healthcheck(self) -> dict[str, Any]:
        """
        Check Vault's health status.

        GET /v1/sys/health

        This endpoint intentionally returns various non-200 status codes:
            200  → active + unsealed              (healthy)
            429  → standby                        (healthy)
            472  → DR secondary                   (degraded)
            473  → performance standby            (healthy)
            501  → not initialized                (critical)
            503  → sealed                         (critical)

        We treat 200/429/473 as healthy, 472 as degraded, 501/503 as critical.
        This method NEVER raises — it always returns a dict with a
        "urip_health_status" key: "healthy" | "degraded" | "critical".

        Returns
        -------
        dict
            Raw Vault health JSON enriched with "urip_health_status".
        """
        url = f"{self.vault_addr}/v1/sys/health"
        headers = self._auth_headers()

        try:
            response = await self._client.get(url, headers=headers)
        except httpx.RequestError as exc:
            logger.warning("Vault healthcheck request error: %s", exc)
            return {
                "urip_health_status": "critical",
                "error": str(exc),
                "initialized": False,
                "sealed": True,
            }

        status_code = response.status_code

        # Parse JSON body (Vault always returns JSON for /sys/health)
        try:
            data: dict[str, Any] = response.json()
        except Exception:
            data = {}

        if status_code in _HEALTHY_STATUS_CODES:
            data["urip_health_status"] = "healthy"
        elif status_code in _DEGRADED_STATUS_CODES:
            data["urip_health_status"] = "degraded"
        else:
            # 501 (not initialized) or 503 (sealed) or unexpected codes
            data["urip_health_status"] = "critical"

        data["urip_http_status"] = status_code
        return data

    async def close(self) -> None:
        """Close the underlying httpx.AsyncClient."""
        await self._client.aclose()

    async def __aenter__(self) -> "VaultAPIClient":
        return self

    async def __aexit__(self, *args: Any) -> None:
        await self.close()
