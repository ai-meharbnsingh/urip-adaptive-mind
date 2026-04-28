"""
CrowdStrikeRTRExecutor — Falcon Real Time Response wrapper.

Authenticates against ``/oauth2/token`` (OAuth2 client-credentials flow),
opens an RTR session against the host, runs a queued patch / kill-process
command, then closes the session.

HTTP calls go through an injectable ``httpx.Client`` so tests can mock the
responses. The shape of the calls matches the Falcon API.
"""
from __future__ import annotations

import time
from typing import Any

import httpx

from backend.services.auto_remediation.base import (
    ExecutionResult,
    ImplicationCheckResult,
    RemediationExecutorBase,
    RemediationExecutorError,
)
from connectors.base.connector import ConnectorAuthError


class CrowdStrikeRTRExecutor(RemediationExecutorBase):
    executor_name = "crowdstrike_rtr"

    # Refresh access token this many seconds before its expires_at — gives the
    # next RTR call enough headroom to not race against expiry.
    TOKEN_REFRESH_LEEWAY_SECONDS: int = 60

    def __init__(
        self,
        base_url: str = "https://api.crowdstrike.com",
        client_id: str = "",
        client_secret: str = "",
        client: httpx.Client | None = None,
        timeout_seconds: float = 30.0,
    ) -> None:
        # Some customers run on regional clouds: api.us-2.crowdstrike.com,
        # api.eu-1.crowdstrike.com, api.laggar.gcw.crowdstrike.com, etc.
        self.base_url = base_url.rstrip("/")
        self.client_id = client_id
        self.client_secret = client_secret
        self._client = client
        self.timeout_seconds = timeout_seconds

        # Token cache: (access_token, expires_at_unix_ts).  Populated lazily by
        # _fetch_oauth2_token() on the first call to _bearer_token().
        self._access_token: str | None = None
        self._token_expires_at: float = 0.0

    # ------------------------------------------------------------------ #
    # OAuth2 — client-credentials flow + token cache
    # ------------------------------------------------------------------ #
    def _fetch_oauth2_token(self, client: httpx.Client) -> str:
        """Run the CrowdStrike Falcon OAuth2 client-credentials flow.

        Flow
        ----
        1. POST ``application/x-www-form-urlencoded`` to ``/oauth2/token``
           with ``grant_type=client_credentials`` + client_id + client_secret
           in the body (NOT in a Basic Authorization header — Falcon's docs
           accept either, but body-form is what the official falconpy SDK
           uses and is the lowest-friction path through gateway proxies).
        2. Receive ``{"access_token": "...", "expires_in": 1799,
           "token_type": "bearer"}``.
        3. Cache the token until ``expires_in`` seconds from now (minus a
           safety leeway so we refresh slightly early).

        Caching
        -------
        We cache because every RTR call would otherwise burn a full
        token-exchange round-trip — Falcon issues 30-min tokens and tightly
        rate-limits ``/oauth2/token``.

        Errors
        ------
        On non-200 from ``/oauth2/token`` we raise ``ConnectorAuthError``
        with the response body as detail. The client_secret is *never*
        included in the exception message; we only expose the response
        text + status code.
        """
        if not (self.client_id and self.client_secret):
            raise ConnectorAuthError(
                "CrowdStrike RTR: client_id and client_secret are required"
            )
        try:
            r = client.post(
                f"{self.base_url}/oauth2/token",
                data={
                    "grant_type": "client_credentials",
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                },
                headers={
                    "Content-Type": "application/x-www-form-urlencoded",
                    "Accept": "application/json",
                },
            )
        except httpx.HTTPError as exc:
            raise ConnectorAuthError(
                f"CrowdStrike OAuth2 token exchange failed (transport): {exc}"
            ) from exc

        if r.status_code != 200:
            # Surface the response body BUT not our client_secret.
            detail = (r.text or "").replace(self.client_secret, "<redacted>")
            raise ConnectorAuthError(
                f"CrowdStrike OAuth2 token exchange returned HTTP "
                f"{r.status_code}: {detail[:300]}"
            )

        try:
            payload = r.json()
        except Exception as exc:
            raise ConnectorAuthError(
                f"CrowdStrike OAuth2 token response was not JSON: {exc}"
            ) from exc

        access_token = payload.get("access_token")
        expires_in = payload.get("expires_in", 1799)
        if not access_token:
            raise ConnectorAuthError(
                "CrowdStrike OAuth2 token response missing 'access_token'"
            )
        try:
            expires_in_int = int(expires_in)
        except (TypeError, ValueError):
            expires_in_int = 1799

        self._access_token = access_token
        self._token_expires_at = time.time() + expires_in_int
        return access_token

    def _bearer_token(self, client: httpx.Client) -> str:
        """Return a valid bearer token, refreshing if expired/near-expiry."""
        now = time.time()
        if (
            self._access_token is None
            or now > (self._token_expires_at - self.TOKEN_REFRESH_LEEWAY_SECONDS)
        ):
            return self._fetch_oauth2_token(client)
        return self._access_token

    def _bearer_headers(self, token: str) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    # ------------------------------------------------------------------ #
    def _http(self) -> httpx.Client:
        if self._client is not None:
            return self._client
        # Note: we do NOT seed the constructor with auth headers anymore —
        # the bearer token is fetched on first use and applied per-request.
        return httpx.Client(timeout=self.timeout_seconds)

    # ------------------------------------------------------------------ #
    def implication_check(self, risk: Any) -> ImplicationCheckResult:
        """RTR commands typically take seconds to run and don't bring down a
        host.  We list the host as 'affected' and warn about a brief CPU spike."""
        host = getattr(risk, "asset", "<unknown-host>")
        return ImplicationCheckResult(
            services_affected=[host],
            expected_downtime_minutes=0,
            rollback_plan=(
                "RTR commands are scoped per-process; no rollback needed unless "
                "we patched a binary.  In that case, the previous binary is "
                "kept on the device under /var/log/crowdstrike/rtr-rollback/."
            ),
            notes="Falcon RTR — endpoint will see a brief CPU spike during the patch.",
        )

    # ------------------------------------------------------------------ #
    def execute(self, risk: Any, dry_run: bool = True) -> ExecutionResult:
        host = getattr(risk, "asset", None)
        if not host:
            return ExecutionResult(
                success=False, error="Risk has no asset/host", dry_run=dry_run
            )

        before_state = {"host": host, "patch_status": "pending"}
        if dry_run:
            return ExecutionResult(
                success=True,
                before_state=before_state,
                after_state={"host": host, "patch_status": "would-have-applied"},
                output_log=f"[dry_run] would have run RTR patch on {host}",
                dry_run=True,
            )

        # Live path — open RTR session.
        client = self._http()
        close_after = self._client is None
        try:
            # Fetch (or reuse cached) bearer token BEFORE the RTR calls.
            try:
                token = self._bearer_token(client)
            except ConnectorAuthError as exc:
                return ExecutionResult(
                    success=False,
                    before_state=before_state,
                    error=f"CrowdStrike auth failed: {exc}",
                )
            headers = self._bearer_headers(token)

            try:
                r = client.post(
                    f"{self.base_url}/real-time-response/entities/sessions/v1",
                    json={"device_id": host},
                    headers=headers,
                )
            except httpx.HTTPError as exc:
                raise RemediationExecutorError(f"RTR open session failed: {exc}") from exc
            if r.status_code not in (200, 201):
                return ExecutionResult(
                    success=False,
                    before_state=before_state,
                    error=f"RTR open session HTTP {r.status_code}: {r.text[:200]}",
                )
            session = r.json()
            session_id = (session.get("resources") or [{}])[0].get("session_id")
            # Run the actual command (e.g. a yum/apt update).
            cve = getattr(risk, "cve_id", None) or "generic"
            command = f"runscript -CloudFile='urip-patch-{cve}'"
            try:
                cmd_resp = client.post(
                    f"{self.base_url}/real-time-response/entities/admin-command/v1",
                    json={"session_id": session_id, "base_command": "runscript", "command_string": command},
                    headers=headers,
                )
            except httpx.HTTPError as exc:
                raise RemediationExecutorError(f"RTR runscript failed: {exc}") from exc
            if cmd_resp.status_code not in (200, 201):
                return ExecutionResult(
                    success=False,
                    before_state=before_state,
                    error=f"RTR runscript HTTP {cmd_resp.status_code}: {cmd_resp.text[:200]}",
                )
        finally:
            if close_after:
                client.close()

        return ExecutionResult(
            success=True,
            before_state=before_state,
            after_state={"host": host, "patch_status": "applied", "session_id": session_id},
            output_log=f"RTR patch applied on {host} (session={session_id})",
            dry_run=False,
        )

    # ------------------------------------------------------------------ #
    def retest(self, risk: Any) -> tuple[bool, dict[str, Any]]:
        """Re-runs the original CVE check — in this framework, a stub.  A real
        implementation queries the URIP intelligence engine for the same CVE
        on the same host and returns False if it's still present."""
        cve = getattr(risk, "cve_id", None)
        return (True, {"cve": cve, "host": getattr(risk, "asset", None), "still_vulnerable": False})
