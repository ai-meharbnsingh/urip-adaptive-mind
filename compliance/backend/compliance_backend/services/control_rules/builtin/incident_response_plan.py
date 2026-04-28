"""
Rule: incident_response_plan_documented — P2B.3

Checks that the tenant has a documented and tested incident response plan (IRP).

Maps to:
  SOC 2:    CC7.3, CC7.4, CC7.5 (Incident response)
  ISO 27001: 5.26 (Response to information security incidents)

tenant_config keys used:
  incident_response_plan_exists (bool)  — whether an IRP document exists
  irp_last_tested_days_ago (int)        — days since last IRP tabletop/exercise (-1 = never)
  irp_test_cycle_days (int, optional)   — required test cycle (default 365 days)

TODO: Integrate with URIP document management to auto-detect IRP existence
      via policy module (P2B.5).
"""
from compliance_backend.services.control_rules import register_control_rule
from compliance_backend.services.control_rules.base import (
    BaseControlRule,
    ControlContext,
    ControlCheckResult,
    EvidenceSpec,
)

DEFAULT_TEST_CYCLE_DAYS = 365


@register_control_rule("incident_response_plan_documented")
class IncidentResponsePlanRule(BaseControlRule):
    name = "Incident Response Plan Documented and Tested"
    description = (
        "Verifies that an incident response plan exists and has been tested "
        "within the required cycle (default: annually)."
    )

    def check(self, tenant_id: str, context: ControlContext) -> ControlCheckResult:
        cfg = context.tenant_config
        plan_exists = cfg.get("incident_response_plan_exists", False)
        last_tested = cfg.get("irp_last_tested_days_ago", -1)
        cycle_days = cfg.get("irp_test_cycle_days", DEFAULT_TEST_CYCLE_DAYS)

        evidence = [
            EvidenceSpec(
                type="document",
                content={
                    "incident_response_plan_exists": plan_exists,
                    "irp_last_tested_days_ago": last_tested,
                    "irp_test_cycle_days": cycle_days,
                },
                metadata={"rule": "incident_response_plan_documented", "tenant_id": tenant_id},
            )
        ]

        failures = []
        if not plan_exists:
            failures.append("Incident response plan document does not exist.")
        if last_tested == -1:
            failures.append("Incident response plan has never been tested.")
        elif last_tested > cycle_days:
            failures.append(
                f"IRP last tested {last_tested} days ago; must be tested every {cycle_days} days."
            )

        if failures:
            return ControlCheckResult(
                status="fail",
                evidence=evidence,
                failure_reason=" ".join(failures),
            )

        return ControlCheckResult(status="pass", evidence=evidence)
