"""
Auto-Remediation Phase 2 — executor framework (URIP_Blueprint v3 §4.2).

Public API
----------
    RemediationExecutorBase       — abstract contract every executor implements
    ExecutionResult               — typed return type
    ImplicationCheckResult        — typed return for implication_check
    CrowdStrikeRTRExecutor        — endpoint patches via Falcon RTR
    AnsibleExecutor               — wraps ansible-runner (subprocess, out-of-process)
    FortinetExecutor              — Fortiguard firewall rule update via FortiOS API
    CyberArkExecutor              — credential rotation via CyberArk REST
    get_executor(name, **cfg)     — factory

Why a framework instead of live integrations
--------------------------------------------
The roadmap commitment is a Phase 2 *framework*: executors can be assembled
from real adapters, but live calls to actual production CrowdStrike / Ansible
/ Fortinet / CyberArk endpoints are out-of-scope for this slice.  Each
executor exposes the four-method contract; tests inject a mock and verify
that the SHAPE of the call is correct.
"""
from __future__ import annotations

from backend.services.auto_remediation.base import (
    ExecutionResult,
    ImplicationCheckResult,
    RemediationExecutorBase,
    RemediationExecutorError,
)
from backend.services.auto_remediation.ansible import AnsibleExecutor
from backend.services.auto_remediation.crowdstrike_rtr import CrowdStrikeRTRExecutor
from backend.services.auto_remediation.cyberark import CyberArkExecutor
from backend.services.auto_remediation.fortinet import FortinetExecutor


def get_executor(executor_name: str, **kwargs) -> RemediationExecutorBase:
    """Factory: name → instance."""
    name = (executor_name or "").strip().lower()
    if name in ("crowdstrike", "crowdstrike_rtr", "rtr"):
        return CrowdStrikeRTRExecutor(**kwargs)
    if name in ("ansible", "ansible-runner"):
        return AnsibleExecutor(**kwargs)
    if name in ("fortinet", "fortigate", "fortios"):
        return FortinetExecutor(**kwargs)
    if name in ("cyberark", "cyber-ark"):
        return CyberArkExecutor(**kwargs)
    raise ValueError(f"Unknown executor: {executor_name!r}")


__all__ = [
    "AnsibleExecutor",
    "CrowdStrikeRTRExecutor",
    "CyberArkExecutor",
    "ExecutionResult",
    "FortinetExecutor",
    "ImplicationCheckResult",
    "RemediationExecutorBase",
    "RemediationExecutorError",
    "get_executor",
]
