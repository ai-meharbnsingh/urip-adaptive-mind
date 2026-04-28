"""
Rule: security_training_completed — P2B.3

Checks that all employees have completed the required security awareness training
within the annual cycle.

Maps to:
  SOC 2:    CC1.4 (Commitment to competence)
  ISO 27001: 6.3 (Awareness), 6.4 (Training)

tenant_config keys used:
  total_employees (int)                      — total employee count
  employees_training_current (int)           — employees with current (within-cycle) training
  security_training_cycle_days (int)         — required cycle (default 365)
  min_completion_percentage (float)          — required completion % (default 100.0)

TODO: Integrate with URIP LMS connector to auto-fetch training completion data
      from the connected learning management system.
"""
from compliance_backend.services.control_rules import register_control_rule
from compliance_backend.services.control_rules.base import (
    BaseControlRule,
    ControlContext,
    ControlCheckResult,
    EvidenceSpec,
)

DEFAULT_CYCLE_DAYS = 365
DEFAULT_MIN_COMPLETION_PCT = 100.0


@register_control_rule("security_training_completed")
class SecurityTrainingCompletedRule(BaseControlRule):
    name = "Security Awareness Training Completed"
    description = (
        "Verifies that all employees have completed security awareness training "
        "within the annual cycle (default: 100% completion required)."
    )

    def check(self, tenant_id: str, context: ControlContext) -> ControlCheckResult:
        cfg = context.tenant_config
        total = cfg.get("total_employees", 0)
        completed = cfg.get("employees_training_current", 0)
        cycle_days = cfg.get("security_training_cycle_days", DEFAULT_CYCLE_DAYS)
        min_pct = cfg.get("min_completion_percentage", DEFAULT_MIN_COMPLETION_PCT)

        evidence = [
            EvidenceSpec(
                type="document",
                content={
                    "total_employees": total,
                    "employees_training_current": completed,
                    "security_training_cycle_days": cycle_days,
                    "min_completion_percentage": min_pct,
                },
                metadata={"rule": "security_training_completed", "tenant_id": tenant_id},
            )
        ]

        if total == 0:
            return ControlCheckResult(
                status="inconclusive",
                evidence=evidence,
                failure_reason=(
                    "No employees are registered in the system. "
                    "Connect the LMS or HR system to track training completion."
                ),
            )

        completion_pct = (completed / total) * 100.0
        if completion_pct < min_pct:
            shortfall = total - completed
            return ControlCheckResult(
                status="fail",
                evidence=evidence,
                failure_reason=(
                    f"{shortfall} employee(s) have not completed security awareness training "
                    f"({completion_pct:.1f}% complete, {min_pct:.0f}% required). "
                    f"Training cycle: {cycle_days} days."
                ),
            )

        return ControlCheckResult(status="pass", evidence=evidence)
