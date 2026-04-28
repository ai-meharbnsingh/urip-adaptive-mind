"""
HTTPX clients for the three EASM sub-adapters: Censys, Shodan, Detectify.

Each adapter is a thin per-provider client.  The top-level ``EasmConnector``
constructs exactly ONE of them based on ``credentials['easm_provider']``.

Design notes
------------
- Sync ``httpx.Client`` to match the other URIP connectors.
- Per-provider auth flows are kept distinct because the providers are very
  different in shape:
    * Censys   → ``Authorization: Bearer <token>`` header + cursor pagination
    * Shodan   → API key in the **query string** (``?key=...``)
    * Detectify→ ``Authorization: Bearer <token>`` + per-domain findings paths
- The connector validates the ``monitor_*`` scope BEFORE calling these clients
  so we never pull "the entire internet" — we only query configured assets.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

import httpx

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT = 30.0

# Default base URLs (configurable per tenant)
CENSYS_DEFAULT_BASE = "https://search.censys.io"
SHODAN_DEFAULT_BASE = "https://api.shodan.io"
DETECTIFY_DEFAULT_BASE = "https://api.detectify.com"


# ─────────────────────────────────────────────────────────────────────────────
# Censys
# ─────────────────────────────────────────────────────────────────────────────


class CensysClient:
    """Censys Search API v2."""

    def __init__(self, api_token: str, base_url: str = CENSYS_DEFAULT_BASE,
                 timeout: float = DEFAULT_TIMEOUT) -> None:
        self.api_token = api_token
        self.base_url = base_url.rstrip("/")
        self._client = httpx.Client(
            timeout=timeout,
            headers={
                "Authorization": f"Bearer {api_token}",
                "Accept": "application/json",
            },
            follow_redirects=True,
        )

    def validate_auth(self) -> bool:
        try:
            r = self._client.get(f"{self.base_url}/api/v2/account")
            return r.status_code == 200
        except Exception:
            logger.exception("Censys auth validation error")
            return False

    def search_hosts(
        self,
        query: str,
        cursor: Optional[str] = None,
        per_page: int = 100,
    ) -> dict[str, Any]:
        params: dict[str, Any] = {"q": query, "per_page": per_page}
        if cursor:
            params["cursor"] = cursor
        r = self._client.get(f"{self.base_url}/api/v2/hosts/search", params=params)
        r.raise_for_status()
        return r.json()

    def close(self) -> None:
        self._client.close()


# ─────────────────────────────────────────────────────────────────────────────
# Shodan
# ─────────────────────────────────────────────────────────────────────────────


class ShodanClient:
    """Shodan REST API."""

    def __init__(self, api_key: str, base_url: str = SHODAN_DEFAULT_BASE,
                 timeout: float = DEFAULT_TIMEOUT) -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self._client = httpx.Client(
            timeout=timeout,
            follow_redirects=True,
            headers={"Accept": "application/json"},
        )

    def validate_auth(self) -> bool:
        try:
            r = self._client.get(
                f"{self.base_url}/api-info", params={"key": self.api_key}
            )
            return r.status_code == 200
        except Exception:
            logger.exception("Shodan auth validation error")
            return False

    def host_lookup(self, ip: str) -> dict[str, Any]:
        r = self._client.get(
            f"{self.base_url}/shodan/host/{ip}", params={"key": self.api_key}
        )
        r.raise_for_status()
        return r.json()

    def close(self) -> None:
        self._client.close()


# ─────────────────────────────────────────────────────────────────────────────
# Detectify
# ─────────────────────────────────────────────────────────────────────────────


class DetectifyClient:
    """Detectify Surface Monitoring REST v3."""

    def __init__(self, api_token: str, base_url: str = DETECTIFY_DEFAULT_BASE,
                 timeout: float = DEFAULT_TIMEOUT) -> None:
        self.api_token = api_token
        self.base_url = base_url.rstrip("/")
        self._client = httpx.Client(
            timeout=timeout,
            headers={
                "Authorization": f"Bearer {api_token}",
                "Accept": "application/json",
            },
            follow_redirects=True,
        )

    def validate_auth(self) -> bool:
        try:
            r = self._client.get(f"{self.base_url}/rest/v3/domains/")
            return r.status_code == 200
        except Exception:
            logger.exception("Detectify auth validation error")
            return False

    def list_findings(
        self,
        domain: str,
        cursor: Optional[str] = None,
    ) -> dict[str, Any]:
        params: dict[str, Any] = {}
        if cursor:
            params["cursor"] = cursor
        r = self._client.get(
            f"{self.base_url}/rest/v3/domains/{domain}/findings",
            params=params,
        )
        r.raise_for_status()
        return r.json()

    def close(self) -> None:
        self._client.close()
