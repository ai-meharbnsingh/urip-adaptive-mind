"""
Rule: password_policy_meets_baseline — P2B.3

Checks that the tenant's password policy meets the minimum baseline:
  - Minimum length >= 12 characters
  - Maximum age <= 90 days (0 = no expiry policy, which is acceptable for MFA-enforced tenants)
  - Complexity: requires uppercase, lowercase, digits, special chars

Maps to:
  SOC 2:    CC6.1
  ISO 27001: 5.17 (Authentication information)

tenant_config keys used:
  password_min_length (int)       — minimum password length
  password_max_age_days (int)     — max days before password expires (0 = none)
  password_complexity_enabled (bool) — uppercase+lowercase+digit+special required

TODO: Integrate with URIP IAM connector to fetch actual IdP password policy settings.
"""
from compliance_backend.services.control_rules import register_control_rule
from compliance_backend.services.control_rules.base import (
    BaseControlRule,
    ControlContext,
    ControlCheckResult,
    EvidenceSpec,
)

MIN_LENGTH = 12
MAX_AGE_DAYS = 90


@register_control_rule("password_policy_meets_baseline")
class PasswordPolicyRule(BaseControlRule):
    name = "Password Policy Meets Baseline"
    description = (
        "Verifies that the tenant password policy requires minimum length >= 12, "
        "complexity enabled, and maximum age <= 90 days."
    )

    def check(self, tenant_id: str, context: ControlContext) -> ControlCheckResult:
        cfg = context.tenant_config
        min_length = cfg.get("password_min_length", 0)
        max_age = cfg.get("password_max_age_days", 0)
        complexity = cfg.get("password_complexity_enabled", False)

        evidence = [
            EvidenceSpec(
                type="config",
                content={
                    "password_min_length": min_length,
                    "password_max_age_days": max_age,
                    "password_complexity_enabled": complexity,
                },
                metadata={"rule": "password_policy_meets_baseline", "tenant_id": tenant_id},
            )
        ]

        failures = []
        if min_length < MIN_LENGTH:
            failures.append(
                f"Password minimum length is {min_length}, must be >= {MIN_LENGTH}."
            )
        if not complexity:
            failures.append("Password complexity (uppercase+lowercase+digit+special) is not enabled.")
        if max_age != 0 and max_age > MAX_AGE_DAYS:
            failures.append(
                f"Password maximum age is {max_age} days, must be <= {MAX_AGE_DAYS} or 0 (no expiry)."
            )

        if failures:
            return ControlCheckResult(
                status="fail",
                evidence=evidence,
                failure_reason=" ".join(failures),
            )

        return ControlCheckResult(status="pass", evidence=evidence)
