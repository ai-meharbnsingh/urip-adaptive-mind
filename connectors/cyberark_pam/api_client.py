"""
Async httpx client for CyberArk PVWA REST API (PAM).

Supports:
- API key logon
- Session token reuse and single-logon / single-logoff per fetch (refcounted)
"""

from __future__ import annotations

import asyncio
import logging
import threading
from contextlib import contextmanager
from typing import Any, Optional

import httpx

logger = logging.getLogger(__name__)


class _AsyncRunner:
    def __init__(self) -> None:
        self._loop = asyncio.new_event_loop()
        self._thread = threading.Thread(target=self._run, name="cyberark-async-runner", daemon=True)
        self._thread.start()

    def _run(self) -> None:
        asyncio.set_event_loop(self._loop)
        self._loop.run_forever()

    def run(self, coro, timeout: float = 30.0):
        fut = asyncio.run_coroutine_threadsafe(coro, self._loop)
        return fut.result(timeout=timeout)


_RUNNER = _AsyncRunner()


class CyberArkAPIClient:
    def __init__(
        self,
        *,
        base_url: str,
        api_key: str,
        timeout: float = 30.0,
        transport: Optional[httpx.BaseTransport] = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self._token: str | None = None
        self._refcount = 0
        self._lock = threading.Lock()
        self._client = httpx.AsyncClient(
            timeout=timeout,
            transport=transport,
            headers={"Accept": "application/json"},
            follow_redirects=True,
        )

    async def _request(self, method: str, url: str, **kwargs: Any) -> httpx.Response:
        return await self._client.request(method, url, **kwargs)

    def _auth_headers(self) -> dict[str, str]:
        if not self._token:
            return {"Accept": "application/json"}
        return {"Authorization": self._token, "Accept": "application/json"}

    def logon(self) -> str:
        url = f"{self.base_url}/PasswordVault/API/Auth/APIKey/Logon"
        resp = _RUNNER.run(
            self._request(
                "POST",
                url,
                headers={"x-api-key": self.api_key, "Accept": "application/json"},
            )
        )
        resp.raise_for_status()
        token = resp.text.strip().strip('"')
        self._token = token
        return token

    def logoff(self) -> None:
        if not self._token:
            return
        url = f"{self.base_url}/PasswordVault/API/Auth/Logoff"
        try:
            resp = _RUNNER.run(self._request("POST", url, headers=self._auth_headers()))
            resp.raise_for_status()
        finally:
            self._token = None

    @contextmanager
    def session(self):
        with self._lock:
            # Only log on if we don't already have a token. This allows
            # authenticate() to establish the session once and fetch_findings()
            # to reuse it without a second logon (TDD expectation).
            if self._refcount == 0 and not self._token:
                self.logon()
            self._refcount += 1
        try:
            yield
        finally:
            with self._lock:
                self._refcount -= 1
                if self._refcount <= 0:
                    self._refcount = 0
                    self.logoff()

    def validate_auth(self) -> bool:
        try:
            # Lightweight validation: logon succeeds and yields a token.
            # We intentionally keep the token for immediate reuse by
            # fetch_findings(); fetch_findings() logs off at the end of its run.
            self.logon()
            return bool(self._token)
        except httpx.HTTPStatusError as exc:
            logger.warning("CyberArk auth validation failed: %s", exc.response.status_code)
            return False
        except Exception:
            logger.exception("CyberArk auth validation failed")
            return False

    def _get_json(self, path: str) -> dict[str, Any]:
        url = f"{self.base_url}{path}"
        resp = _RUNNER.run(self._request("GET", url, headers=self._auth_headers()))
        resp.raise_for_status()
        return resp.json()

    def list_vault_access(self) -> dict[str, Any]:
        return self._get_json("/PasswordVault/API/Logs/VaultAccess")

    def list_privileged_sessions(self) -> dict[str, Any]:
        return self._get_json("/PasswordVault/API/Logs/PrivilegedSessions")

    def list_credentials_usage(self) -> dict[str, Any]:
        return self._get_json("/PasswordVault/API/Logs/CredentialsUsage")

    def close(self) -> None:
        try:
            _RUNNER.run(self._client.aclose())
        except Exception:
            return
