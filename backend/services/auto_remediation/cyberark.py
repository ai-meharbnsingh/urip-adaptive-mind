"""
CyberArkExecutor — credential rotation via the CyberArk REST API.

Used when a risk indicates a credential has been compromised (e.g., a leaked
password from threat-intel, a public Git secret).  We instruct CyberArk to
rotate the affected account.

In production, the API endpoint is:
    POST /PasswordVault/API/Accounts/{accountId}/Change

For this slice, the call is HTTP-mocked.
"""
from __future__ import annotations

from typing import Any

import httpx

from backend.services.auto_remediation.base import (
    ExecutionResult,
    ImplicationCheckResult,
    RemediationExecutorBase,
    RemediationExecutorError,
)


class CyberArkExecutor(RemediationExecutorBase):
    executor_name = "cyberark"

    def __init__(
        self,
        base_url: str = "",
        auth_token: str = "",
        client: httpx.Client | None = None,
        timeout_seconds: float = 30.0,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.auth_token = auth_token
        self._client = client
        self.timeout_seconds = timeout_seconds

    def _http(self) -> httpx.Client:
        if self._client is not None:
            return self._client
        return httpx.Client(timeout=self.timeout_seconds)

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": self.auth_token,
            "Content-Type": "application/json",
        }

    # ------------------------------------------------------------------ #
    def implication_check(self, risk: Any) -> ImplicationCheckResult:
        # Credential rotation breaks any application that has the old creds
        # cached.  Conservative estimate: 5 minutes of partial downtime per
        # rotated account while consumers reload.
        account = getattr(risk, "asset", "<unknown-account>")
        return ImplicationCheckResult(
            services_affected=[f"cyberark_account:{account}"],
            expected_downtime_minutes=5,
            rollback_plan=(
                "CyberArk auto-versions every credential.  Roll back via "
                "/PasswordVault/API/Accounts/{accountId}/RestoreVersion."
            ),
            notes="Confirm downstream consumers can pick up the new creds quickly.",
        )

    # ------------------------------------------------------------------ #
    def execute(self, risk: Any, dry_run: bool = True) -> ExecutionResult:
        account_id = getattr(risk, "cyberark_account_id", None) or getattr(risk, "asset", None)
        if not account_id:
            return ExecutionResult(
                success=False, error="Risk has no cyberark_account_id/asset", dry_run=dry_run
            )

        before_state = {"account_id": account_id, "rotated": False}
        if dry_run:
            return ExecutionResult(
                success=True,
                before_state=before_state,
                after_state={"account_id": account_id, "rotated": "would-have-rotated"},
                output_log=f"[dry_run] would have rotated CyberArk account {account_id}",
                dry_run=True,
            )

        client = self._http()
        close_after = self._client is None
        try:
            url = f"{self.base_url}/PasswordVault/API/Accounts/{account_id}/Change"
            try:
                resp = client.post(url, json={"ChangeImmediately": True}, headers=self._headers())
            except httpx.HTTPError as exc:
                raise RemediationExecutorError(f"CyberArk API failed: {exc}") from exc
        finally:
            if close_after:
                client.close()

        if resp.status_code not in (200, 201, 204):
            return ExecutionResult(
                success=False,
                before_state=before_state,
                error=f"CyberArk HTTP {resp.status_code}: {resp.text[:200]}",
            )
        return ExecutionResult(
            success=True,
            before_state=before_state,
            after_state={"account_id": account_id, "rotated": True},
            output_log=f"CyberArk credential rotated for account {account_id}",
            dry_run=False,
        )
