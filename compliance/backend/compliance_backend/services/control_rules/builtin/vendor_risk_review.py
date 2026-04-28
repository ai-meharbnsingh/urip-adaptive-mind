"""
Rule: vendor_risk_review_current — P2B.3

Checks that vendor/third-party risk assessments are up to date for
critical vendors.

Maps to:
  SOC 2:    CC9.2 (Vendor risk management)
  ISO 27001: 5.19 (Information security in supplier relationships)

tenant_config keys used:
  critical_vendor_count (int)         — number of critical vendors
  vendors_with_overdue_review (int)   — number with overdue risk reviews
  vendor_review_cycle_days (int)      — required review frequency (default 365)

TODO: Integrate with URIP Vendor Risk module (P2B.7) to auto-count
      overdue vendor reviews from the vendor_risk_assessments table.
"""
from compliance_backend.services.control_rules import register_control_rule
from compliance_backend.services.control_rules.base import (
    BaseControlRule,
    ControlContext,
    ControlCheckResult,
    EvidenceSpec,
)

DEFAULT_VENDOR_CYCLE_DAYS = 365


@register_control_rule("vendor_risk_review_current")
class VendorRiskReviewRule(BaseControlRule):
    name = "Vendor Risk Review Current"
    description = (
        "Verifies that all critical vendors have an up-to-date risk assessment "
        "completed within the required review cycle."
    )

    def check(self, tenant_id: str, context: ControlContext) -> ControlCheckResult:
        cfg = context.tenant_config
        total_critical = cfg.get("critical_vendor_count", 0)
        overdue = cfg.get("vendors_with_overdue_review", 0)
        cycle_days = cfg.get("vendor_review_cycle_days", DEFAULT_VENDOR_CYCLE_DAYS)

        evidence = [
            EvidenceSpec(
                type="document",
                content={
                    "critical_vendor_count": total_critical,
                    "vendors_with_overdue_review": overdue,
                    "vendor_review_cycle_days": cycle_days,
                },
                metadata={"rule": "vendor_risk_review_current", "tenant_id": tenant_id},
            )
        ]

        if total_critical == 0:
            # No critical vendors registered → inconclusive (may indicate missing data)
            return ControlCheckResult(
                status="inconclusive",
                evidence=evidence,
                failure_reason=(
                    "No critical vendors are registered. "
                    "Add critical vendors to the vendor risk register before this control can be assessed."
                ),
            )

        if overdue > 0:
            return ControlCheckResult(
                status="fail",
                evidence=evidence,
                failure_reason=(
                    f"{overdue} of {total_critical} critical vendor(s) have risk assessments "
                    f"overdue (review cycle: {cycle_days} days)."
                ),
            )

        return ControlCheckResult(status="pass", evidence=evidence)
