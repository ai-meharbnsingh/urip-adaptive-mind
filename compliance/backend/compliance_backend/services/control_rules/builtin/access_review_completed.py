"""
Rule: access_review_completed — P2B.3

Checks that an access review (user access certification) has been completed
within the required review cycle.

Maps to:
  SOC 2:    CC6.2 (Access removal / review)
  ISO 27001: 5.18 (Access rights)

tenant_config keys used:
  last_access_review_days_ago (int)   — days since last access review was completed
  access_review_cycle_days (int)      — required review cycle (default 90 days)

TODO: Integrate with URIP access review workflow module to pull last_access_review_days_ago
      automatically from the task completion record.
"""
from compliance_backend.services.control_rules import register_control_rule
from compliance_backend.services.control_rules.base import (
    BaseControlRule,
    ControlContext,
    ControlCheckResult,
    EvidenceSpec,
)

DEFAULT_REVIEW_CYCLE_DAYS = 90


@register_control_rule("access_review_completed")
class AccessReviewCompletedRule(BaseControlRule):
    name = "Access Review Completed"
    description = (
        "Verifies that a user access review (certification) has been completed "
        "within the required cycle (default: every 90 days)."
    )

    def check(self, tenant_id: str, context: ControlContext) -> ControlCheckResult:
        cfg = context.tenant_config
        # -1 means no review ever done
        last_review_days_ago = cfg.get("last_access_review_days_ago", -1)
        cycle_days = cfg.get("access_review_cycle_days", DEFAULT_REVIEW_CYCLE_DAYS)

        evidence = [
            EvidenceSpec(
                type="ticket",
                content={
                    "last_access_review_days_ago": last_access_review_days_ago,
                    "access_review_cycle_days": cycle_days,
                },
                metadata={"rule": "access_review_completed", "tenant_id": tenant_id},
            )
            for last_access_review_days_ago in [last_review_days_ago]
        ]

        if last_review_days_ago == -1:
            return ControlCheckResult(
                status="fail",
                evidence=evidence,
                failure_reason=(
                    "Access review has never been completed for this tenant. "
                    "Complete an initial access review immediately."
                ),
            )

        if last_review_days_ago > cycle_days:
            return ControlCheckResult(
                status="fail",
                evidence=evidence,
                failure_reason=(
                    f"Last access review was {last_review_days_ago} days ago, "
                    f"but must be completed every {cycle_days} days."
                ),
            )

        return ControlCheckResult(status="pass", evidence=evidence)
