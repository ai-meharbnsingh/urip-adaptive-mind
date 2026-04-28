"""
Sync HTTPX client for GCP Security APIs.

Handles:
- OAuth2 JWT-bearer flow for service accounts
- Application Default Credentials (ADC) via GCE metadata server
- Simple exponential-backoff retry on HTTP 429
- Pagination helpers for SCC, Asset Inventory, and Recommender
"""

from __future__ import annotations

import logging
import time
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx
import jwt

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT = 30.0
DEFAULT_ADC_URL = (
    "http://metadata.google.internal/computeMetadata/v1/instance/service-accounts/default/token"
)
DEFAULT_TOKEN_URI = "https://oauth2.googleapis.com/token"
DEFAULT_SCOPE = "https://www.googleapis.com/auth/cloud-platform"


class GcpCspmApiClient:
    """Synchronous HTTPX client for GCP Security APIs."""

    def __init__(
        self,
        service_account_json: dict[str, Any] | None = None,
        project_id: str | None = None,
        timeout: float = DEFAULT_TIMEOUT,
    ) -> None:
        self.service_account_json = service_account_json
        self.project_id = project_id
        self.timeout = timeout
        self._access_token: str | None = None
        self._token_expires_at: datetime | None = None
        self._client = httpx.Client(timeout=timeout, follow_redirects=True)

    def _get_access_token(self) -> str:
        """Return a cached access token or fetch a new one."""
        if (
            self._access_token
            and self._token_expires_at
            and datetime.now(timezone.utc) < self._token_expires_at
        ):
            return self._access_token

        if self.service_account_json:
            token = self._get_token_from_service_account()
        else:
            token = self._get_token_from_metadata_server()

        self._access_token = token
        # Cache conservatively for 50 minutes
        self._token_expires_at = datetime.now(timezone.utc) + timedelta(seconds=3000)
        return token

    def _get_token_from_service_account(self) -> str:
        """Create a JWT assertion and exchange it for an access token."""
        sa = self.service_account_json
        if not sa:
            raise ValueError("service_account_json is required for the JWT flow")

        client_email = sa.get("client_email")
        private_key = sa.get("private_key")
        token_uri = sa.get("token_uri", DEFAULT_TOKEN_URI)

        if not client_email or not private_key:
            raise ValueError(
                "service_account_json must contain 'client_email' and 'private_key'"
            )

        now = int(time.time())
        payload = {
            "iss": client_email,
            "sub": client_email,
            "scope": DEFAULT_SCOPE,
            "aud": token_uri,
            "iat": now,
            "exp": now + 3600,
        }

        assertion = jwt.encode(payload, private_key, algorithm="RS256")

        resp = self._client.post(
            token_uri,
            data={
                "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
                "assertion": assertion,
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        resp.raise_for_status()
        data = resp.json()
        return str(data["access_token"])

    def _get_token_from_metadata_server(self) -> str:
        """Fetch an access token from the GCE metadata server (ADC)."""
        resp = self._client.get(
            DEFAULT_ADC_URL,
            headers={"Metadata-Flavor": "Google"},
            timeout=5.0,
        )
        resp.raise_for_status()
        data = resp.json()
        return str(data["access_token"])

    def _auth_header(self) -> dict[str, str]:
        token = self._get_access_token()
        return {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }

    def _request(self, method: str, url: str, **kwargs: Any) -> httpx.Response:
        headers = self._auth_header()
        if "headers" in kwargs:
            headers.update(kwargs.pop("headers"))

        retries = 0
        max_retries = 3
        while True:
            response = self._client.request(method, url, headers=headers, **kwargs)
            if response.status_code == 429 and retries < max_retries:
                retries += 1
                sleep_time = 2 ** retries
                logger.warning(
                    "GCP API rate limited (429), retrying in %ds...", sleep_time
                )
                time.sleep(sleep_time)
                continue
            response.raise_for_status()
            return response

    def validate_auth(self) -> bool:
        """Obtain an access token and return True if successful."""
        try:
            self._get_access_token()
            return True
        except Exception:
            logger.exception("GCP auth validation failed")
            return False

    def list_scc_findings(
        self, parent: str, page_size: int = 100
    ) -> list[dict[str, Any]]:
        """List Security Command Center findings for the given parent."""
        url = f"https://securitycenter.googleapis.com/v1/{parent}/findings"
        findings: list[dict[str, Any]] = []
        page_token: str | None = None

        while True:
            params: dict[str, Any] = {"pageSize": page_size}
            if page_token:
                params["pageToken"] = page_token

            resp = self._request("GET", url, params=params)
            data = resp.json()
            findings.extend(data.get("findings", []))
            page_token = data.get("nextPageToken")
            if not page_token:
                break

        return findings

    def list_assets(
        self, project_id: str, page_size: int = 100
    ) -> list[dict[str, Any]]:
        """List Cloud Asset Inventory assets for a project."""
        url = f"https://cloudasset.googleapis.com/v1/projects/{project_id}/assets"
        assets: list[dict[str, Any]] = []
        page_token: str | None = None

        while True:
            params: dict[str, Any] = {"pageSize": page_size}
            if page_token:
                params["pageToken"] = page_token

            resp = self._request("GET", url, params=params)
            data = resp.json()
            assets.extend(data.get("assets", []))
            page_token = data.get("nextPageToken")
            if not page_token:
                break

        return assets

    def list_recommender_recommendations(
        self,
        project_id: str,
        recommender: str = "google.cloud.security",
        page_size: int = 100,
    ) -> list[dict[str, Any]]:
        """List Recommender recommendations for a project."""
        url = (
            f"https://recommender.googleapis.com/v1/projects/{project_id}"
            f"/locations/-/recommenders/{recommender}/recommendations"
        )
        recommendations: list[dict[str, Any]] = []
        page_token: str | None = None

        while True:
            params: dict[str, Any] = {"pageSize": page_size}
            if page_token:
                params["pageToken"] = page_token

            resp = self._request("GET", url, params=params)
            data = resp.json()
            recommendations.extend(data.get("recommendations", []))
            page_token = data.get("nextPageToken")
            if not page_token:
                break

        return recommendations

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> GcpCspmApiClient:
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()
