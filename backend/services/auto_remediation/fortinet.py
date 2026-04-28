"""
FortinetExecutor — Fortiguard / FortiOS firewall rule update via REST API.

Common use-case: a malicious IP from threat-intel needs to be blocked at the
edge.  We POST the IP into a `block-list` address group and (optionally)
ensure a deny policy referencing the group exists.
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


class FortinetExecutor(RemediationExecutorBase):
    executor_name = "fortinet"

    def __init__(
        self,
        base_url: str = "",
        api_token: str = "",
        block_group_name: str = "urip-blocklist",
        client: httpx.Client | None = None,
        timeout_seconds: float = 15.0,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_token = api_token
        self.block_group_name = block_group_name
        self._client = client
        self.timeout_seconds = timeout_seconds

    def _http(self) -> httpx.Client:
        if self._client is not None:
            return self._client
        return httpx.Client(timeout=self.timeout_seconds)

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_token}",
            "Content-Type": "application/json",
        }

    # ------------------------------------------------------------------ #
    def implication_check(self, risk: Any) -> ImplicationCheckResult:
        # Adding an IP to a block-list rarely affects internal services unless
        # the IP is mistakenly an internal CDN.  We surface that risk explicitly.
        return ImplicationCheckResult(
            services_affected=["edge_firewall"],
            expected_downtime_minutes=0,
            rollback_plan=(
                "Remove the address-group entry via the same FortiOS API. "
                "If a legitimate service was blocked, traffic resumes within "
                "the firewall's session-table TTL (default 60s)."
            ),
            notes=(
                "Confirm the IP is not part of an internal CDN allow-list. "
                "The block takes effect on the next packet from that source."
            ),
        )

    # ------------------------------------------------------------------ #
    def execute(self, risk: Any, dry_run: bool = True) -> ExecutionResult:
        # `risk.indicator_value` would be set on threat-intel risks; fallback
        # to risk.asset for legacy callers.
        ip = (
            getattr(risk, "indicator_value", None)
            or getattr(risk, "asset", None)
        )
        if not ip:
            return ExecutionResult(
                success=False, error="Risk has no IP/indicator value", dry_run=dry_run
            )
        before_state = {"ip": ip, "block_group": self.block_group_name, "blocked": False}
        if dry_run:
            return ExecutionResult(
                success=True,
                before_state=before_state,
                after_state={"ip": ip, "block_group": self.block_group_name, "blocked": "would-have-blocked"},
                output_log=f"[dry_run] would have added {ip} to {self.block_group_name}",
                dry_run=True,
            )

        client = self._http()
        close_after = self._client is None
        try:
            url = f"{self.base_url}/api/v2/cmdb/firewall/addrgrp/{self.block_group_name}/member"
            try:
                resp = client.post(url, json={"name": ip}, headers=self._headers())
            except httpx.HTTPError as exc:
                raise RemediationExecutorError(f"FortiOS API failed: {exc}") from exc
        finally:
            if close_after:
                client.close()
        if resp.status_code not in (200, 201):
            return ExecutionResult(
                success=False,
                before_state=before_state,
                error=f"FortiOS HTTP {resp.status_code}: {resp.text[:200]}",
            )
        return ExecutionResult(
            success=True,
            before_state=before_state,
            after_state={"ip": ip, "block_group": self.block_group_name, "blocked": True},
            output_log=f"Added {ip} to FortiOS group {self.block_group_name}",
            dry_run=False,
        )
