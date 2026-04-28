"""
AnsibleExecutor — wraps `ansible-runner` (or `ansible-playbook`) as a subprocess.

Why a subprocess instead of an in-process import?
  - ansible-runner internally imports the Ansible engine which mutates global
    state (signal handlers, asyncio loop, plugin registry).  Importing it in
    a long-running FastAPI worker has historically caused worker hangs +
    plugin-cache poisoning.  Running it out-of-process gives a clean
    interpreter per execution and makes the timeout enforceable via the
    standard `subprocess.run(..., timeout=N)` mechanism.
  - Running it as a subprocess also bounds the blast radius: if a playbook
    blows up the interpreter, the FastAPI worker survives.

Tests inject a `runner=` callable so the real subprocess never runs.
"""
from __future__ import annotations

import json
import logging
import shlex
import subprocess
import time
from pathlib import Path
from typing import Any, Callable

from backend.services.auto_remediation.base import (
    ExecutionResult,
    ImplicationCheckResult,
    RemediationExecutorBase,
)

logger = logging.getLogger(__name__)


# Default subprocess runner — overridden in tests.
def _default_runner(cmd: list[str], timeout_seconds: int) -> subprocess.CompletedProcess:
    return subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=timeout_seconds,
        check=False,
    )


class AnsibleExecutor(RemediationExecutorBase):
    executor_name = "ansible"

    def __init__(
        self,
        playbook_path: str,
        inventory_path: str | None = None,
        extra_vars: dict[str, Any] | None = None,
        timeout_seconds: int = 600,
        runner: Callable[[list[str], int], subprocess.CompletedProcess] | None = None,
    ) -> None:
        self.playbook_path = playbook_path
        self.inventory_path = inventory_path
        self.extra_vars = extra_vars or {}
        self.timeout_seconds = timeout_seconds
        self._runner = runner or _default_runner

    # ------------------------------------------------------------------ #
    def implication_check(self, risk: Any) -> ImplicationCheckResult:
        # Ansible playbook implications are domain-specific.  We surface a
        # conservative default that the caller (UI) can refine via
        # tenant-config overrides.
        return ImplicationCheckResult(
            services_affected=[getattr(risk, "asset", "<unknown>")],
            expected_downtime_minutes=5,
            rollback_plan=(
                "Run the inverse playbook (same path with `-rollback` suffix) "
                "OR restore the host from snapshot.  Ansible itself does NOT "
                "guarantee atomicity — ensure your playbook is idempotent."
            ),
            notes=f"Playbook: {self.playbook_path}",
        )

    # ------------------------------------------------------------------ #
    def execute(self, risk: Any, dry_run: bool = True) -> ExecutionResult:
        host = getattr(risk, "asset", None)
        before_state = {"host": host, "playbook": self.playbook_path}
        if dry_run:
            return ExecutionResult(
                success=True,
                before_state=before_state,
                after_state={"host": host, "playbook_status": "would-have-applied"},
                output_log="[dry_run] would have run ansible-playbook with --check",
                dry_run=True,
            )

        cmd = ["ansible-playbook", self.playbook_path]
        if self.inventory_path:
            cmd.extend(["-i", self.inventory_path])
        if self.extra_vars:
            cmd.extend(["--extra-vars", json.dumps(self.extra_vars)])

        started = time.monotonic()
        try:
            proc = self._runner(cmd, self.timeout_seconds)
        except subprocess.TimeoutExpired as exc:
            return ExecutionResult(
                success=False,
                before_state=before_state,
                error=f"Ansible timed out after {self.timeout_seconds}s",
                output_log=str(exc.stdout or "")[-2000:],
            )
        except FileNotFoundError as exc:
            return ExecutionResult(
                success=False,
                before_state=before_state,
                error=f"ansible-playbook binary not found: {exc}",
            )

        elapsed_ms = int((time.monotonic() - started) * 1000)
        success = proc.returncode == 0
        return ExecutionResult(
            success=success,
            before_state=before_state,
            after_state={
                "host": host,
                "returncode": proc.returncode,
                "elapsed_ms": elapsed_ms,
            },
            output_log=(proc.stdout or "") + (proc.stderr or ""),
            error=None if success else f"ansible-playbook exited with {proc.returncode}",
            dry_run=False,
        )
