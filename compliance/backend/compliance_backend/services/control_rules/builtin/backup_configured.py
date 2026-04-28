"""
Rule: backup_configured — P2B.3

Checks that automated backups are configured and meet the retention baseline.

Maps to:
  SOC 2:    A1.2 (Backup and recovery)
  ISO 27001: 8.13 (Information backup)

tenant_config keys used:
  backups_enabled (bool)          — whether automated backups are turned on
  backup_retention_days (int)     — how many days backups are kept
  backup_tested_days_ago (int)    — days since last backup restore test (-1 = never)

Baseline: backups must be retained >= 30 days and tested within 365 days.

TODO: Integrate with URIP cloud connector to verify actual backup configs
      on AWS RDS, GCP Cloud SQL, Azure SQL.
"""
from compliance_backend.services.control_rules import register_control_rule
from compliance_backend.services.control_rules.base import (
    BaseControlRule,
    ControlContext,
    ControlCheckResult,
    EvidenceSpec,
)

MIN_RETENTION_DAYS = 30
MAX_TEST_CYCLE_DAYS = 365


@register_control_rule("backup_configured")
class BackupConfiguredRule(BaseControlRule):
    name = "Automated Backup Configured"
    description = (
        "Verifies that automated backups are enabled with at least 30 days retention "
        "and restore tested within the past 365 days."
    )

    def check(self, tenant_id: str, context: ControlContext) -> ControlCheckResult:
        cfg = context.tenant_config
        backups_enabled = cfg.get("backups_enabled", False)
        retention_days = cfg.get("backup_retention_days", 0)
        tested_days_ago = cfg.get("backup_tested_days_ago", -1)

        evidence = [
            EvidenceSpec(
                type="config",
                content={
                    "backups_enabled": backups_enabled,
                    "backup_retention_days": retention_days,
                    "backup_tested_days_ago": tested_days_ago,
                },
                metadata={"rule": "backup_configured", "tenant_id": tenant_id},
            )
        ]

        failures = []
        if not backups_enabled:
            failures.append("Automated backups are not enabled.")
        if retention_days < MIN_RETENTION_DAYS:
            failures.append(
                f"Backup retention is {retention_days} days; minimum required is {MIN_RETENTION_DAYS}."
            )
        if tested_days_ago == -1:
            failures.append("Backup restore has never been tested.")
        elif tested_days_ago > MAX_TEST_CYCLE_DAYS:
            failures.append(
                f"Backup restore last tested {tested_days_ago} days ago; "
                f"must be tested every {MAX_TEST_CYCLE_DAYS} days."
            )

        if failures:
            return ControlCheckResult(
                status="fail",
                evidence=evidence,
                failure_reason=" ".join(failures),
            )

        return ControlCheckResult(status="pass", evidence=evidence)
