"""
RemediationExecutorBase — abstract contract for any auto-remediation executor.

Each executor implements:

    implication_check(risk)  -> ImplicationCheckResult
    execute(risk, dry_run=…) -> ExecutionResult

The service layer drives the workflow:

    1. Pick the right executor based on the risk source/finding_type.
    2. Run implication_check — show the impact to the human.
    3. Get human approval (or pre-approved category).
    4. Call execute(dry_run=False).
    5. Re-test (run the original detection again) — close risk if clean.
"""
from __future__ import annotations

import abc
from dataclasses import dataclass, field
from typing import Any


class RemediationExecutorError(Exception):
    """Wraps any executor-side failure."""


@dataclass
class ImplicationCheckResult:
    services_affected: list[str] = field(default_factory=list)
    expected_downtime_minutes: int = 0
    rollback_plan: str = ""
    notes: str = ""


@dataclass
class ExecutionResult:
    success: bool
    before_state: dict[str, Any] = field(default_factory=dict)
    after_state: dict[str, Any] = field(default_factory=dict)
    output_log: str = ""
    error: str | None = None
    dry_run: bool = False


class RemediationExecutorBase(abc.ABC):
    executor_name: str = "base"

    @abc.abstractmethod
    def implication_check(self, risk: Any) -> ImplicationCheckResult:
        ...

    @abc.abstractmethod
    def execute(self, risk: Any, dry_run: bool = True) -> ExecutionResult:
        ...

    # Optional: subclass overrides if it can re-test the original detection.
    def retest(self, risk: Any) -> tuple[bool, dict[str, Any]]:
        """Default: cannot retest; service layer falls back to manual."""
        return False, {"reason": "executor does not implement retest()"}
