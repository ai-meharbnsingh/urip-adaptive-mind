"""
Bug Bounty API client for HackerOne + Bugcrowd.

Handles:
- HackerOne: REST API /v1/reports with API token auth
- Bugcrowd: REST API /submissions with API token auth
"""

from __future__ import annotations

import logging
from typing import Any, Optional

import httpx

logger = logging.getLogger(__name__)
DEFAULT_TIMEOUT = 30.0


class HackerOneAPIClient:
    """Synchronous HTTPX client for HackerOne API."""

    def __init__(
        self,
        api_token: str,
        program_handle: Optional[str] = None,
        timeout: float = DEFAULT_TIMEOUT,
    ) -> None:
        self.api_token = api_token
        self.program_handle = program_handle
        self.timeout = timeout
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
            resp = self._client.get("https://api.hackerone.com/v1/me")
            resp.raise_for_status()
            return True
        except Exception:
            logger.exception("HackerOne auth validation failed")
            return False

    def list_reports(self, since: Optional[str] = None) -> list[dict[str, Any]]:
        """Fetch reports for the program handle."""
        params: dict[str, Any] = {}
        if self.program_handle:
            params["program_handle[]"] = self.program_handle
        if since:
            params["created_at__gt"] = since
        resp = self._client.get("https://api.hackerone.com/v1/reports", params=params)
        resp.raise_for_status()
        return resp.json().get("data", [])

    def close(self) -> None:
        self._client.close()


class BugcrowdAPIClient:
    """Synchronous HTTPX client for Bugcrowd API."""

    def __init__(
        self,
        api_token: str,
        timeout: float = DEFAULT_TIMEOUT,
    ) -> None:
        self.api_token = api_token
        self.timeout = timeout
        self._client = httpx.Client(
            timeout=timeout,
            headers={
                "Authorization": f"Token {api_token}",
                "Accept": "application/json",
            },
            follow_redirects=True,
        )

    def validate_auth(self) -> bool:
        try:
            resp = self._client.get("https://api.bugcrowd.com/user")
            resp.raise_for_status()
            return True
        except Exception:
            logger.exception("Bugcrowd auth validation failed")
            return False

    def list_submissions(self, since: Optional[str] = None) -> list[dict[str, Any]]:
        """Fetch submissions."""
        params: dict[str, Any] = {}
        if since:
            params["filter[submitted]"] = f"gt:{since}"
        resp = self._client.get("https://api.bugcrowd.com/submissions", params=params)
        resp.raise_for_status()
        return resp.json().get("submissions", [])

    def close(self) -> None:
        self._client.close()
