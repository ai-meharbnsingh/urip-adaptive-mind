"""
Base classes for the control rule plugin system — P2B.3.

Every automated control rule must:
  1. Subclass BaseControlRule
  2. Implement check(tenant_id, context) -> ControlCheckResult
  3. Be decorated with @register_control_rule("rule_name") in __init__.py

ControlContext carries all data available to a rule:
  - tenant_config: dict of tenant-specific configuration values
    (pulled from tenant's settings at rule execution time)
  - connector_data: dict of data from URIP connectors
    (TODO: full URIP connector integration is out of scope — marked as TODO below)

ControlCheckResult is the return value:
  - status: "pass" | "fail" | "inconclusive"
  - evidence: list of EvidenceSpec dicts describing evidence to capture
  - failure_reason: human-readable explanation (required when status == "fail")
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class ControlContext:
    """
    Context passed into every control rule check.

    tenant_config: key-value pairs from tenant settings
      (e.g. {"mfa_enabled": True, "password_min_length": 14})

    connector_data: raw data fetched from URIP connectors
      (e.g. {"iam_users": [...], "s3_buckets": [...]})
      TODO: P2B.3 — integrate with URIP connector service to populate this
            automatically before each scheduled check run. Currently rules use
            dummy deterministic logic based on tenant_config only.
    """
    tenant_config: Dict[str, Any] = field(default_factory=dict)
    connector_data: Dict[str, Any] = field(default_factory=dict)


@dataclass
class EvidenceSpec:
    """
    Specification for a piece of evidence that a rule wants captured.

    The control engine passes these to evidence_service.capture_evidence()
    after the check() call returns.

    type: screenshot | config | log | ticket | document
    content: raw content bytes / string / dict to store
    metadata: extra context (source tool, region, etc.)
    """
    type: str
    content: Any
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ControlCheckResult:
    """
    Return value from a control rule's check() method.

    status:
        "pass"         — control is satisfied
        "fail"         — control is not satisfied; failure_reason is required
        "inconclusive" — could not determine (e.g. connector unavailable)

    evidence: list of EvidenceSpec items to capture automatically
    failure_reason: human-readable explanation; None when status == "pass"
    """
    status: str  # "pass" | "fail" | "inconclusive"
    evidence: List[EvidenceSpec] = field(default_factory=list)
    failure_reason: Optional[str] = None

    def __post_init__(self) -> None:
        valid_statuses = {"pass", "fail", "inconclusive"}
        if self.status not in valid_statuses:
            raise ValueError(
                f"Invalid status '{self.status}'. Must be one of {valid_statuses}"
            )
        if self.status == "fail" and not self.failure_reason:
            raise ValueError(
                "failure_reason is required when status == 'fail'"
            )


class BaseControlRule(ABC):
    """
    Abstract base class for all control rule plugins.

    Subclass this, implement check(), and decorate with @register_control_rule.
    """

    #: Human-readable name for display in the UI / reports
    name: str = ""
    #: Short description of what the rule checks
    description: str = ""

    @abstractmethod
    def check(self, tenant_id: str, context: ControlContext) -> ControlCheckResult:
        """
        Run the control check for the given tenant.

        Args:
            tenant_id: The tenant being checked (for scoping / logging)
            context: ControlContext with tenant_config + connector_data

        Returns:
            ControlCheckResult with status, evidence specs, and optional failure_reason

        NOTE: Rules should NEVER raise exceptions for expected failure conditions —
        return status="fail" instead. Raise only for programming errors.
        """
        ...
