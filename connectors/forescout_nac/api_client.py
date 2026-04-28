"""
Async httpx clients for NAC sources:
- Forescout eyeSight REST API (OAuth2)
- Cisco ISE ERS API (basic auth)

Executed via a dedicated async runner thread to remain safe when called from
the backend's running event loop.
"""

from __future__ import annotations

import asyncio
import logging
import threading
from typing import Any, Optional

import httpx

logger = logging.getLogger(__name__)


class _AsyncRunner:
    def __init__(self) -> None:
        self._loop = asyncio.new_event_loop()
        self._thread = threading.Thread(target=self._run, name="nac-async-runner", daemon=True)
        self._thread.start()

    def _run(self) -> None:
        asyncio.set_event_loop(self._loop)
        self._loop.run_forever()

    def run(self, coro, timeout: float = 30.0):
        fut = asyncio.run_coroutine_threadsafe(coro, self._loop)
        return fut.result(timeout=timeout)


_RUNNER = _AsyncRunner()


class ForescoutAPIClient:
    def __init__(
        self,
        *,
        base_url: str,
        client_id: str,
        client_secret: str,
        timeout: float = 30.0,
        transport: Optional[httpx.BaseTransport] = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.client_id = client_id
        self.client_secret = client_secret
        self._access_token: str | None = None
        self._client = httpx.AsyncClient(
            timeout=timeout,
            transport=transport,
            follow_redirects=True,
        )

    async def _request_json(self, method: str, url: str, **kwargs: Any) -> dict[str, Any]:
        resp = await self._client.request(method, url, **kwargs)
        resp.raise_for_status()
        return resp.json()

    def _auth_headers(self) -> dict[str, str]:
        if not self._access_token:
            return {"Accept": "application/json"}
        return {
            "Authorization": f"Bearer {self._access_token}",
            "Accept": "application/json",
        }

    def fetch_token(self) -> dict[str, Any]:
        url = f"{self.base_url}/oauth2/token"
        data = {
            "grant_type": "client_credentials",
            "client_id": self.client_id,
            "client_secret": self.client_secret,
        }
        token_json = _RUNNER.run(self._request_json("POST", url, data=data))
        self._access_token = token_json.get("access_token")
        return token_json

    def validate_auth(self) -> bool:
        try:
            url = f"{self.base_url}/api/v1/me"
            _RUNNER.run(self._request_json("GET", url, headers=self._auth_headers()))
            return True
        except httpx.HTTPStatusError as exc:
            logger.warning("Forescout auth validation failed: %s", exc.response.status_code)
            return False
        except Exception:
            logger.exception("Forescout auth validation failed")
            return False

    def list_alerts(self) -> dict[str, Any]:
        url = f"{self.base_url}/api/v1/alerts"
        return _RUNNER.run(self._request_json("GET", url, headers=self._auth_headers()))

    def list_events(self) -> dict[str, Any]:
        url = f"{self.base_url}/api/v1/events"
        return _RUNNER.run(self._request_json("GET", url, headers=self._auth_headers()))

    def list_devices(self) -> dict[str, Any]:
        url = f"{self.base_url}/api/v1/devices"
        return _RUNNER.run(self._request_json("GET", url, headers=self._auth_headers()))

    def close(self) -> None:
        try:
            _RUNNER.run(self._client.aclose())
        except Exception:
            return


class CiscoISEAPIClient:
    def __init__(
        self,
        *,
        base_url: str,
        username: str,
        password: str,
        timeout: float = 30.0,
        transport: Optional[httpx.BaseTransport] = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self._client = httpx.AsyncClient(
            timeout=timeout,
            transport=transport,
            auth=(username, password),
            headers={"Accept": "application/json"},
            follow_redirects=True,
        )

    async def _request_json(self, method: str, url: str, **kwargs: Any) -> dict[str, Any]:
        resp = await self._client.request(method, url, **kwargs)
        resp.raise_for_status()
        return resp.json()

    def validate_auth(self) -> bool:
        try:
            url = f"{self.base_url}/ers/config/endpoint?size=1&page=1"
            _RUNNER.run(self._request_json("GET", url))
            return True
        except httpx.HTTPStatusError as exc:
            logger.warning("Cisco ISE auth validation failed: %s", exc.response.status_code)
            return False
        except Exception:
            logger.exception("Cisco ISE auth validation failed")
            return False

    def list_endpoints(self, *, size: int = 50, page: int = 1) -> dict[str, Any]:
        url = f"{self.base_url}/ers/config/endpoint?size={size}&page={page}"
        return _RUNNER.run(self._request_json("GET", url))

    def close(self) -> None:
        try:
            _RUNNER.run(self._client.aclose())
        except Exception:
            return

