"""
Rule: mfa_enforced — P2B.3

Checks that multi-factor authentication (MFA) is enforced for all users
in the tenant's primary IdP.

Maps to:
  SOC 2:    CC6.1 (Logical Access Controls)
  ISO 27001: 8.5 (Secure authentication)

tenant_config keys used:
  mfa_enabled (bool, required) — whether MFA is enabled at tenant level
  mfa_enforcement (str, optional) — "all_users" | "admins_only" | "optional"

TODO: Integrate with URIP IAM connector to verify actual IdP MFA settings
      rather than relying solely on tenant_config.
"""
from compliance_backend.services.control_rules import register_control_rule
from compliance_backend.services.control_rules.base import (
    BaseControlRule,
    ControlContext,
    ControlCheckResult,
    EvidenceSpec,
)


@register_control_rule("mfa_enforced")
class MfaEnforcedRule(BaseControlRule):
    name = "MFA Enforced"
    description = (
        "Verifies that multi-factor authentication is enforced for all tenant users "
        "in the primary identity provider."
    )

    def check(self, tenant_id: str, context: ControlContext) -> ControlCheckResult:
        cfg = context.tenant_config
        mfa_enabled = cfg.get("mfa_enabled", False)
        enforcement = cfg.get("mfa_enforcement", "optional")

        evidence = [
            EvidenceSpec(
                type="config",
                content={"mfa_enabled": mfa_enabled, "mfa_enforcement": enforcement},
                metadata={"rule": "mfa_enforced", "tenant_id": tenant_id},
            )
        ]

        if not mfa_enabled:
            return ControlCheckResult(
                status="fail",
                evidence=evidence,
                failure_reason=(
                    "MFA is not enabled for this tenant. "
                    "Enable MFA in the identity provider settings."
                ),
            )

        if enforcement != "all_users":
            return ControlCheckResult(
                status="fail",
                evidence=evidence,
                failure_reason=(
                    f"MFA enforcement is set to '{enforcement}' but must be 'all_users' "
                    "to satisfy CC6.1 / ISO 8.5."
                ),
            )

        return ControlCheckResult(status="pass", evidence=evidence)
