"""
Rule: audit_logging_enabled — P2B.3

Checks that audit logging is enabled and that logs are retained for the
required minimum period.

Maps to:
  SOC 2:    CC7.2 (Monitoring for anomalous activity)
  ISO 27001: 8.15 (Logging), 8.16 (Monitoring activities)

tenant_config keys used:
  audit_logging_enabled (bool)       — whether audit logging is turned on
  log_retention_days (int)           — how many days logs are retained
  log_immutable (bool, optional)     — whether logs are write-protected / WORM

Baseline: logs must be retained >= 365 days (SOC 2 / ISO 27001 expectation).

TODO: Integrate with URIP logging connector (AWS CloudTrail / GCP Cloud Logging)
      to verify actual log pipeline settings.
"""
from compliance_backend.services.control_rules import register_control_rule
from compliance_backend.services.control_rules.base import (
    BaseControlRule,
    ControlContext,
    ControlCheckResult,
    EvidenceSpec,
)

MIN_RETENTION_DAYS = 365


@register_control_rule("audit_logging_enabled")
class AuditLoggingEnabledRule(BaseControlRule):
    name = "Audit Logging Enabled"
    description = (
        "Verifies that audit logging is enabled and logs are retained for "
        "at least 365 days."
    )

    def check(self, tenant_id: str, context: ControlContext) -> ControlCheckResult:
        cfg = context.tenant_config
        logging_enabled = cfg.get("audit_logging_enabled", False)
        retention_days = cfg.get("log_retention_days", 0)

        evidence = [
            EvidenceSpec(
                type="log",
                content={
                    "audit_logging_enabled": logging_enabled,
                    "log_retention_days": retention_days,
                },
                metadata={"rule": "audit_logging_enabled", "tenant_id": tenant_id},
            )
        ]

        failures = []
        if not logging_enabled:
            failures.append("Audit logging is not enabled.")
        if retention_days < MIN_RETENTION_DAYS:
            failures.append(
                f"Log retention is {retention_days} days, minimum required is "
                f"{MIN_RETENTION_DAYS} days."
            )

        if failures:
            return ControlCheckResult(
                status="fail",
                evidence=evidence,
                failure_reason=" ".join(failures),
            )

        return ControlCheckResult(status="pass", evidence=evidence)
