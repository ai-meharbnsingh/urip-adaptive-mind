"""
Async httpx client + syslog parser for Fortinet Fortiguard / FortiGate.

Capabilities (RE-baseline):
- Parse CEF syslog lines into structured events
- Optional REST API fetch for blocked threats (and a lightweight status check)
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
        self._thread = threading.Thread(target=self._run, name="forti-async-runner", daemon=True)
        self._thread.start()

    def _run(self) -> None:
        asyncio.set_event_loop(self._loop)
        self._loop.run_forever()

    def run(self, coro, timeout: float = 30.0):
        fut = asyncio.run_coroutine_threadsafe(coro, self._loop)
        return fut.result(timeout=timeout)


_RUNNER = _AsyncRunner()


def parse_cef_line(line: str) -> dict[str, Any] | None:
    """
    Parse a CEF syslog line (minimal implementation).

    Example:
      CEF:0|Fortinet|FortiGate|7.4|100|Blocked Threat|8 src=10.0.0.1 dst=1.1.1.1 act=blocked cat=ips
    """
    if "CEF:" not in line:
        return None
    cef_start = line.find("CEF:")
    cef = line[cef_start:]
    parts = cef.split("|", 7)
    if len(parts) < 7:
        return None
    # parts: CEF:Version, Device Vendor, Device Product, Device Version, Signature ID, Name, Severity+extensions
    signature_id = parts[4].strip()
    name = parts[5].strip()
    sev_and_ext = parts[6]
    try:
        sev_str, *rest = sev_and_ext.split(" ", 1)
        severity = int(sev_str.strip())
        extensions_blob = rest[0] if rest else ""
    except Exception:
        severity = 0
        extensions_blob = ""

    extensions: dict[str, Any] = {}
    for token in extensions_blob.split():
        if "=" not in token:
            continue
        k, v = token.split("=", 1)
        extensions[k] = v

    return {
        "signature_id": signature_id,
        "name": name,
        "severity": severity,
        "extensions": extensions,
    }


class FortiGuardAPIClient:
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
            self.request_json("GET", "/api/v2/monitor/system/status")
            return True
        except httpx.HTTPStatusError as exc:
            logger.warning("FortiGate auth validation failed: %s", exc.response.status_code)
            return False
        except Exception:
            logger.exception("FortiGate auth validation failed")
            return False

    def list_blocked_threats(self) -> dict[str, Any]:
        return self.request_json("GET", "/api/v2/monitor/firewall/blocked-threats")

    def close(self) -> None:
        try:
            _RUNNER.run(self._client.aclose())
        except Exception:
            return

