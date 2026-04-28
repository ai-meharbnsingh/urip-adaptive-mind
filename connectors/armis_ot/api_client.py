"""
Async httpx client for Armis OT cloud REST API.

Note: BaseConnector is sync, but the scheduler runs inside an event loop.
To avoid `asyncio.run()` (illegal in a running loop), this client executes async
requests in a dedicated daemon thread with its own loop.
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
        self._thread = threading.Thread(target=self._run, name="armis-async-runner", daemon=True)
        self._thread.start()

    def _run(self) -> None:
        asyncio.set_event_loop(self._loop)
        self._loop.run_forever()

    def run(self, coro, timeout: float = 30.0):
        fut = asyncio.run_coroutine_threadsafe(coro, self._loop)
        return fut.result(timeout=timeout)

    def stop(self) -> None:
        try:
            self._loop.call_soon_threadsafe(self._loop.stop)
        except Exception:
            return


_RUNNER = _AsyncRunner()


class ArmisOTAPIClient:
    def __init__(
        self,
        *,
        base_url: str,
        api_token: str,
        timeout: float = 30.0,
        transport: Optional[httpx.BaseTransport] = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_token = api_token
        self._client = httpx.AsyncClient(
            timeout=timeout,
            transport=transport,
            headers={
                "Authorization": f"Bearer {api_token}",
                "Accept": "application/json",
                "Content-Type": "application/json",
            },
            follow_redirects=True,
        )

    async def _request_json(self, method: str, path: str, **kwargs: Any) -> dict[str, Any]:
        url = f"{self.base_url}{path}"
        resp = await self._client.request(method, url, **kwargs)
        resp.raise_for_status()
        return resp.json()

    def request_json(self, method: str, path: str, **kwargs: Any) -> dict[str, Any]:
        return _RUNNER.run(self._request_json(method, path, **kwargs))

    def validate_auth(self) -> bool:
        try:
            self.request_json("GET", "/api/v1/me")
            return True
        except httpx.HTTPStatusError as exc:
            logger.warning("Armis auth validation failed: %s", exc.response.status_code)
            return False
        except Exception:
            logger.exception("Armis auth validation failed")
            return False

    def list_assets(self) -> dict[str, Any]:
        return self.request_json("GET", "/api/v1/assets")

    def list_vulnerabilities(self) -> dict[str, Any]:
        return self.request_json("GET", "/api/v1/vulnerabilities")

    def list_risk_events(self) -> dict[str, Any]:
        return self.request_json("GET", "/api/v1/risk-events")

    def close(self) -> None:
        try:
            _RUNNER.run(self._client.aclose())
        except Exception:
            return

