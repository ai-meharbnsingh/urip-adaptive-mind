"""
HTTPX client for CrowdStrike Falcon APIs.

Implements:
- OAuth2 client-credentials grant against /oauth2/token (token cached in-process)
- Automatic retry-with-refresh on HTTP 401 (single retry)
- Retry-After honoring on HTTP 429
- Endpoints for Spotlight (VM), Surface (EASM), and CNAPP (cloud)

Design notes
------------
- Sync ``httpx.Client`` to match the rest of the URIP connector layer.
- Token is acquired lazily on first request (or eagerly via ``ensure_token()``
  during validate_auth).
- The 401-retry loop is intentionally limited to one retry per call to avoid
  infinite loops if credentials are truly bad.
"""

from __future__ import annotations

import logging
import time
from typing import Any, Optional

import httpx

from connectors.crowdstrike.schemas import OAuthTokenResponse

logger = logging.getLogger(__name__)

DEFAULT_BASE_URL = "https://api.crowdstrike.com"
DEFAULT_TIMEOUT = 30.0

# Falcon's published rate limit on data endpoints is 6,000 req/min — well above
# anything URIP polls, so we don't pre-throttle. We DO honor Retry-After.

VALID_BASE_URLS = (
    "https://api.crowdstrike.com",            # US-1
    "https://api.us-2.crowdstrike.com",       # US-2
    "https://api.eu-1.crowdstrike.com",       # EU-1
    "https://api.laggar.gcw.crowdstrike.com", # GovCloud
)


class CrowdStrikeAPIClient:
    """Synchronous HTTPX client for CrowdStrike Falcon."""

    def __init__(
        self,
        client_id: str,
        client_secret: str,
        base_url: str = DEFAULT_BASE_URL,
        timeout: float = DEFAULT_TIMEOUT,
    ) -> None:
        self.client_id = client_id
        self.client_secret = client_secret
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self._token: Optional[str] = None
        self._token_expires_at: float = 0.0
        self._client = httpx.Client(
            timeout=timeout,
            follow_redirects=True,
            headers={
                "Accept": "application/json",
            },
        )

    # ─── OAuth ──────────────────────────────────────────────────────────────

    def acquire_token(self) -> str:
        """Run the client-credentials OAuth flow and cache the resulting bearer token."""
        url = f"{self.base_url}/oauth2/token"
        resp = self._client.post(
            url,
            data={
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "grant_type": "client_credentials",
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        if resp.status_code != 200:
            logger.warning(
                "CrowdStrike OAuth failed: %s %s", resp.status_code, resp.text[:200]
            )
            raise httpx.HTTPStatusError(
                f"OAuth failed: {resp.status_code}",
                request=resp.request,
                response=resp,
            )
        parsed = OAuthTokenResponse.model_validate(resp.json())
        self._token = parsed.access_token
        # Refresh 30s before actual expiry to be safe
        self._token_expires_at = time.time() + max(parsed.expires_in - 30, 60)
        return self._token

    def ensure_token(self) -> str:
        if not self._token or time.time() >= self._token_expires_at:
            return self.acquire_token()
        return self._token

    def _auth_headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.ensure_token()}",
            "Accept": "application/json",
        }

    # ─── Generic request with 401-refresh + Retry-After ─────────────────────

    def _request(self, method: str, path: str, **kwargs: Any) -> httpx.Response:
        url = f"{self.base_url}{path}"
        headers = kwargs.pop("headers", {}) or {}
        headers.update(self._auth_headers())

        resp = self._client.request(method, url, headers=headers, **kwargs)

        # 401 → refresh token once and retry
        if resp.status_code == 401:
            logger.info("CrowdStrike 401 — refreshing token and retrying once")
            self._token = None
            headers.update(self._auth_headers())
            resp = self._client.request(method, url, headers=headers, **kwargs)

        # 429 → respect Retry-After, retry once
        if resp.status_code == 429:
            retry_after = resp.headers.get("Retry-After")
            try:
                wait_s = float(retry_after) if retry_after else 1.0
            except ValueError:
                wait_s = 1.0
            logger.warning("CrowdStrike rate limited — sleeping %.1fs", wait_s)
            time.sleep(wait_s)
            resp = self._client.request(method, url, headers=headers, **kwargs)

        return resp

    # ─── Falcon Spotlight (VM) ──────────────────────────────────────────────

    def query_spotlight_vulnerabilities(
        self,
        offset: str = "",
        limit: int = 100,
        filter_str: Optional[str] = None,
    ) -> dict[str, Any]:
        """Phase 1 of Spotlight: returns vulnerability IDs."""
        params: dict[str, Any] = {"limit": limit}
        if offset:
            params["offset"] = offset
        if filter_str:
            params["filter"] = filter_str
        resp = self._request("GET", "/spotlight/queries/vulnerabilities/v1", params=params)
        resp.raise_for_status()
        return resp.json()

    def get_spotlight_vulnerability_details(self, ids: list[str]) -> dict[str, Any]:
        """Phase 2 of Spotlight: hydrate IDs into full vulnerability records."""
        if not ids:
            return {"resources": []}
        # CrowdStrike supports repeated 'ids' query params or a single comma-list.
        resp = self._request(
            "GET",
            "/spotlight/entities/vulnerabilities/v2",
            params=[("ids", i) for i in ids],
        )
        resp.raise_for_status()
        return resp.json()

    # ─── Falcon Surface (EASM) ──────────────────────────────────────────────

    def query_external_assets(
        self,
        offset: str = "",
        limit: int = 100,
    ) -> dict[str, Any]:
        params: dict[str, Any] = {"limit": limit}
        if offset:
            params["offset"] = offset
        resp = self._request(
            "GET", "/falcon-surface/queries/external-assets/v1", params=params
        )
        resp.raise_for_status()
        return resp.json()

    # ─── Falcon CNAPP ───────────────────────────────────────────────────────

    def query_cnapp_findings(
        self,
        offset: str = "",
        limit: int = 100,
    ) -> dict[str, Any]:
        params: dict[str, Any] = {"limit": limit}
        if offset:
            params["offset"] = offset
        resp = self._request("GET", "/cnapp/queries/findings/v1", params=params)
        resp.raise_for_status()
        return resp.json()

    # ─── Validation / lifecycle ─────────────────────────────────────────────

    def validate_auth(self) -> bool:
        """Validate by trying to acquire a token. Returns True on success."""
        try:
            self.acquire_token()
            return True
        except httpx.HTTPStatusError as exc:
            logger.warning("CrowdStrike auth validation HTTP error: %s", exc.response.status_code)
            return False
        except Exception:
            logger.exception("CrowdStrike auth validation error")
            return False

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "CrowdStrikeAPIClient":
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()
