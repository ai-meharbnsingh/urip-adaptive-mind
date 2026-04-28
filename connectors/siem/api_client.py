"""
SIEM API client with per-adapter auth handling.

Supports:
- Splunk: REST API /services/search/jobs/export (basic auth or bearer token)
- Elastic: _search API with API key auth
- QRadar: /api/ariel/searches endpoint with SEC token auth
"""

from __future__ import annotations

import json
import logging
import time
from typing import Any, Optional

import httpx

logger = logging.getLogger(__name__)
DEFAULT_TIMEOUT = 30.0


class SplunkAPIClient:
    """Synchronous HTTPX client for Splunk."""

    def __init__(
        self,
        base_url: str,
        auth_token: Optional[str] = None,
        username: Optional[str] = None,
        password: Optional[str] = None,
        timeout: float = DEFAULT_TIMEOUT,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        headers: dict[str, str] = {}
        auth = None
        if auth_token:
            headers["Authorization"] = f"Bearer {auth_token}"
        elif username and password:
            auth = (username, password)
        self._client = httpx.Client(timeout=timeout, headers=headers, auth=auth, follow_redirects=True)

    def validate_auth(self) -> bool:
        try:
            resp = self._client.get(f"{self.base_url}/services/server/info")
            resp.raise_for_status()
            return True
        except Exception:
            logger.exception("Splunk auth validation failed")
            return False

    def search(self, query: str, **kwargs: Any) -> list[dict[str, Any]]:
        """Run a Splunk search and return result rows."""
        # Use export endpoint for simplicity in tests
        data = {
            "search": query if query.startswith("search ") else f"search {query}",
            "output_mode": "json",
            " earliest_time": kwargs.get("earliest_time", "-15m"),
        }
        resp = self._client.post(f"{self.base_url}/services/search/jobs/export", data=data)
        resp.raise_for_status()
        results: list[dict[str, Any]] = []
        for line in resp.text.strip().splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                results.append(json.loads(line))
            except json.JSONDecodeError:
                continue
        return results

    def close(self) -> None:
        self._client.close()


class ElasticAPIClient:
    """Synchronous HTTPX client for Elastic."""

    def __init__(
        self,
        base_url: str,
        api_key: str,
        timeout: float = DEFAULT_TIMEOUT,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        headers = {
            "Authorization": f"ApiKey {api_key}",
            "Content-Type": "application/json",
        }
        self._client = httpx.Client(timeout=timeout, headers=headers, follow_redirects=True)

    def validate_auth(self) -> bool:
        try:
            resp = self._client.get(f"{self.base_url}/_cluster/health")
            resp.raise_for_status()
            return True
        except Exception:
            logger.exception("Elastic auth validation failed")
            return False

    def search(self, query_dsl: dict[str, Any], index: str = "*") -> list[dict[str, Any]]:
        """Run an Elastic query and return hits."""
        resp = self._client.post(f"{self.base_url}/{index}/_search", json=query_dsl)
        resp.raise_for_status()
        data = resp.json()
        return data.get("hits", {}).get("hits", [])

    def close(self) -> None:
        self._client.close()


class QRadarAPIClient:
    """Synchronous HTTPX client for IBM QRadar."""

    def __init__(
        self,
        base_url: str,
        sec_token: str,
        timeout: float = DEFAULT_TIMEOUT,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        headers = {
            "SEC": sec_token,
            "Accept": "application/json",
            "Content-Type": "application/json",
            "Version": "17.0",
        }
        self._client = httpx.Client(timeout=timeout, headers=headers, follow_redirects=True)

    def validate_auth(self) -> bool:
        try:
            resp = self._client.get(f"{self.base_url}/api/system/about")
            resp.raise_for_status()
            return True
        except Exception:
            logger.exception("QRadar auth validation failed")
            return False

    def search(self, ariel_query: str) -> list[dict[str, Any]]:
        """Create an Ariel search, poll to completion, and return events."""
        # Create search
        resp = self._client.post(
            f"{self.base_url}/api/ariel/searches",
            data={"query_expression": ariel_query},
        )
        resp.raise_for_status()
        search_id = resp.json().get("search_id")
        if not search_id:
            return []

        # Poll status
        for _ in range(30):
            status_resp = self._client.get(f"{self.base_url}/api/ariel/searches/{search_id}")
            status_resp.raise_for_status()
            status = status_resp.json().get("status", "").upper()
            if status == "COMPLETED":
                break
            if status in ("ERROR", "CANCELED"):
                logger.error("QRadar search %s failed with status %s", search_id, status)
                return []
            time.sleep(1)
        else:
            logger.error("QRadar search %s did not complete in time", search_id)
            return []

        # Fetch results
        results_resp = self._client.get(
            f"{self.base_url}/api/ariel/searches/{search_id}/results",
        )
        results_resp.raise_for_status()
        data = results_resp.json()
        return data.get("events", data.get("results", []))

    def close(self) -> None:
        self._client.close()
