"""
TDD — Builtin control rule tests (P2B.3.5)

Tests each of the 10 built-in rules for:
  - Expected pass with valid config
  - Expected fail with invalid config (and useful failure_reason)
  - Inconclusive cases (where applicable)
  - Tenant isolation (tenant_id stored in evidence metadata)
  - failure_reason is non-empty and descriptive on fail
"""
import pytest

from compliance_backend.services.control_rules import load_builtin_rules, get_rule
from compliance_backend.services.control_rules.base import ControlContext


# Ensure all builtins are loaded before tests run
load_builtin_rules()


def _ctx(**kwargs) -> ControlContext:
    return ControlContext(tenant_config=kwargs)


TENANT_A = "tenant-rule-test-a"
TENANT_B = "tenant-rule-test-b"


# ---------------------------------------------------------------------------
# 1. mfa_enforced
# ---------------------------------------------------------------------------

class TestMfaEnforcedRule:
    def test_pass_when_mfa_all_users(self):
        rule = get_rule("mfa_enforced")
        result = rule.check(TENANT_A, _ctx(mfa_enabled=True, mfa_enforcement="all_users"))
        assert result.status == "pass"

    def test_fail_when_mfa_disabled(self):
        rule = get_rule("mfa_enforced")
        result = rule.check(TENANT_A, _ctx(mfa_enabled=False))
        assert result.status == "fail"
        assert result.failure_reason
        assert "MFA" in result.failure_reason

    def test_fail_when_enforcement_not_all_users(self):
        rule = get_rule("mfa_enforced")
        result = rule.check(TENANT_A, _ctx(mfa_enabled=True, mfa_enforcement="admins_only"))
        assert result.status == "fail"
        assert "admins_only" in result.failure_reason

    def test_evidence_contains_config(self):
        rule = get_rule("mfa_enforced")
        result = rule.check(TENANT_A, _ctx(mfa_enabled=True, mfa_enforcement="all_users"))
        assert len(result.evidence) == 1
        assert result.evidence[0].type == "config"

    def test_tenant_id_in_evidence_metadata(self):
        rule = get_rule("mfa_enforced")
        result = rule.check(TENANT_B, _ctx(mfa_enabled=True, mfa_enforcement="all_users"))
        assert result.evidence[0].metadata.get("tenant_id") == TENANT_B


# ---------------------------------------------------------------------------
# 2. password_policy_meets_baseline
# ---------------------------------------------------------------------------

class TestPasswordPolicyRule:
    GOOD_CFG = dict(
        password_min_length=14,
        password_max_age_days=60,
        password_complexity_enabled=True,
    )

    def test_pass_with_good_policy(self):
        rule = get_rule("password_policy_meets_baseline")
        result = rule.check(TENANT_A, _ctx(**self.GOOD_CFG))
        assert result.status == "pass"

    def test_fail_short_min_length(self):
        rule = get_rule("password_policy_meets_baseline")
        result = rule.check(TENANT_A, _ctx(password_min_length=8, password_complexity_enabled=True))
        assert result.status == "fail"
        assert "length" in result.failure_reason.lower()

    def test_fail_no_complexity(self):
        rule = get_rule("password_policy_meets_baseline")
        result = rule.check(TENANT_A, _ctx(password_min_length=14, password_complexity_enabled=False))
        assert result.status == "fail"
        assert "complexity" in result.failure_reason.lower()

    def test_fail_age_too_long(self):
        rule = get_rule("password_policy_meets_baseline")
        result = rule.check(
            TENANT_A,
            _ctx(password_min_length=14, password_complexity_enabled=True, password_max_age_days=200),
        )
        assert result.status == "fail"
        assert "200" in result.failure_reason

    def test_pass_no_expiry_policy(self):
        """max_age=0 means no expiry policy — acceptable (SOC 2 allows with MFA)."""
        rule = get_rule("password_policy_meets_baseline")
        result = rule.check(
            TENANT_A,
            _ctx(password_min_length=14, password_complexity_enabled=True, password_max_age_days=0),
        )
        assert result.status == "pass"


# ---------------------------------------------------------------------------
# 3. encryption_at_rest_configured
# ---------------------------------------------------------------------------

class TestEncryptionAtRestRule:
    def test_pass_when_enabled_aes256(self):
        rule = get_rule("encryption_at_rest_configured")
        result = rule.check(
            TENANT_A,
            _ctx(encryption_at_rest_enabled=True, encryption_algorithm="AES-256"),
        )
        assert result.status == "pass"

    def test_pass_when_enabled_no_algorithm_specified(self):
        """If algorithm is not specified, only check that enabled=True."""
        rule = get_rule("encryption_at_rest_configured")
        result = rule.check(TENANT_A, _ctx(encryption_at_rest_enabled=True))
        assert result.status == "pass"

    def test_fail_when_disabled(self):
        rule = get_rule("encryption_at_rest_configured")
        result = rule.check(TENANT_A, _ctx(encryption_at_rest_enabled=False))
        assert result.status == "fail"
        assert "not enabled" in result.failure_reason

    def test_fail_when_unapproved_algorithm(self):
        rule = get_rule("encryption_at_rest_configured")
        result = rule.check(
            TENANT_A,
            _ctx(encryption_at_rest_enabled=True, encryption_algorithm="DES"),
        )
        assert result.status == "fail"
        assert "DES" in result.failure_reason


# ---------------------------------------------------------------------------
# 4. audit_logging_enabled
# ---------------------------------------------------------------------------

class TestAuditLoggingRule:
    def test_pass_when_enabled_with_sufficient_retention(self):
        rule = get_rule("audit_logging_enabled")
        result = rule.check(
            TENANT_A,
            _ctx(audit_logging_enabled=True, log_retention_days=400),
        )
        assert result.status == "pass"

    def test_fail_when_logging_disabled(self):
        rule = get_rule("audit_logging_enabled")
        result = rule.check(
            TENANT_A,
            _ctx(audit_logging_enabled=False, log_retention_days=400),
        )
        assert result.status == "fail"
        assert "not enabled" in result.failure_reason

    def test_fail_when_retention_too_short(self):
        rule = get_rule("audit_logging_enabled")
        result = rule.check(
            TENANT_A,
            _ctx(audit_logging_enabled=True, log_retention_days=90),
        )
        assert result.status == "fail"
        assert "90" in result.failure_reason

    def test_evidence_type_is_log(self):
        rule = get_rule("audit_logging_enabled")
        result = rule.check(
            TENANT_A,
            _ctx(audit_logging_enabled=True, log_retention_days=400),
        )
        assert result.evidence[0].type == "log"


# ---------------------------------------------------------------------------
# 5. access_review_completed
# ---------------------------------------------------------------------------

class TestAccessReviewRule:
    def test_pass_when_recent_review(self):
        rule = get_rule("access_review_completed")
        result = rule.check(
            TENANT_A,
            _ctx(last_access_review_days_ago=30, access_review_cycle_days=90),
        )
        assert result.status == "pass"

    def test_fail_when_no_review_ever(self):
        rule = get_rule("access_review_completed")
        result = rule.check(TENANT_A, _ctx(last_access_review_days_ago=-1))
        assert result.status == "fail"
        assert "never" in result.failure_reason.lower()

    def test_fail_when_overdue(self):
        rule = get_rule("access_review_completed")
        result = rule.check(
            TENANT_A,
            _ctx(last_access_review_days_ago=120, access_review_cycle_days=90),
        )
        assert result.status == "fail"
        assert "120" in result.failure_reason


# ---------------------------------------------------------------------------
# 6. incident_response_plan_documented
# ---------------------------------------------------------------------------

class TestIncidentResponsePlanRule:
    def test_pass_when_plan_exists_and_tested(self):
        rule = get_rule("incident_response_plan_documented")
        result = rule.check(
            TENANT_A,
            _ctx(
                incident_response_plan_exists=True,
                irp_last_tested_days_ago=100,
                irp_test_cycle_days=365,
            ),
        )
        assert result.status == "pass"

    def test_fail_when_plan_missing(self):
        rule = get_rule("incident_response_plan_documented")
        result = rule.check(
            TENANT_A,
            _ctx(incident_response_plan_exists=False, irp_last_tested_days_ago=30),
        )
        assert result.status == "fail"
        assert "plan" in result.failure_reason.lower()

    def test_fail_when_never_tested(self):
        rule = get_rule("incident_response_plan_documented")
        result = rule.check(
            TENANT_A,
            _ctx(incident_response_plan_exists=True, irp_last_tested_days_ago=-1),
        )
        assert result.status == "fail"
        assert "never" in result.failure_reason.lower()

    def test_evidence_type_is_document(self):
        rule = get_rule("incident_response_plan_documented")
        result = rule.check(
            TENANT_A,
            _ctx(incident_response_plan_exists=True, irp_last_tested_days_ago=100),
        )
        assert result.evidence[0].type == "document"


# ---------------------------------------------------------------------------
# 7. backup_configured
# ---------------------------------------------------------------------------

class TestBackupConfiguredRule:
    def test_pass_with_good_config(self):
        rule = get_rule("backup_configured")
        result = rule.check(
            TENANT_A,
            _ctx(backups_enabled=True, backup_retention_days=90, backup_tested_days_ago=30),
        )
        assert result.status == "pass"

    def test_fail_when_disabled(self):
        rule = get_rule("backup_configured")
        result = rule.check(TENANT_A, _ctx(backups_enabled=False, backup_retention_days=90))
        assert result.status == "fail"
        assert "not enabled" in result.failure_reason

    def test_fail_when_retention_too_short(self):
        rule = get_rule("backup_configured")
        result = rule.check(
            TENANT_A,
            _ctx(backups_enabled=True, backup_retention_days=7, backup_tested_days_ago=10),
        )
        assert result.status == "fail"
        assert "7" in result.failure_reason

    def test_fail_when_never_tested(self):
        rule = get_rule("backup_configured")
        result = rule.check(
            TENANT_A,
            _ctx(backups_enabled=True, backup_retention_days=90, backup_tested_days_ago=-1),
        )
        assert result.status == "fail"
        assert "never" in result.failure_reason.lower()


# ---------------------------------------------------------------------------
# 8. vulnerability_scanning_active
# ---------------------------------------------------------------------------

class TestVulnerabilityScanningRule:
    def test_pass_when_clean(self):
        rule = get_rule("vulnerability_scanning_active")
        result = rule.check(
            TENANT_A,
            _ctx(
                vuln_scanning_enabled=True,
                last_scan_days_ago=10,
                critical_vulns_unresolved=0,
                scan_frequency_days=30,
            ),
        )
        assert result.status == "pass"

    def test_fail_when_scanning_disabled(self):
        rule = get_rule("vulnerability_scanning_active")
        result = rule.check(TENANT_A, _ctx(vuln_scanning_enabled=False))
        assert result.status == "fail"
        assert "not enabled" in result.failure_reason

    def test_fail_when_critical_vulns_present(self):
        rule = get_rule("vulnerability_scanning_active")
        result = rule.check(
            TENANT_A,
            _ctx(
                vuln_scanning_enabled=True,
                last_scan_days_ago=5,
                critical_vulns_unresolved=3,
            ),
        )
        assert result.status == "fail"
        assert "3" in result.failure_reason

    def test_fail_when_scan_overdue(self):
        rule = get_rule("vulnerability_scanning_active")
        result = rule.check(
            TENANT_A,
            _ctx(
                vuln_scanning_enabled=True,
                last_scan_days_ago=60,
                critical_vulns_unresolved=0,
                scan_frequency_days=30,
            ),
        )
        assert result.status == "fail"
        assert "60" in result.failure_reason


# ---------------------------------------------------------------------------
# 9. vendor_risk_review_current
# ---------------------------------------------------------------------------

class TestVendorRiskReviewRule:
    def test_pass_all_current(self):
        rule = get_rule("vendor_risk_review_current")
        result = rule.check(
            TENANT_A,
            _ctx(critical_vendor_count=5, vendors_with_overdue_review=0),
        )
        assert result.status == "pass"

    def test_fail_when_overdue(self):
        rule = get_rule("vendor_risk_review_current")
        result = rule.check(
            TENANT_A,
            _ctx(critical_vendor_count=5, vendors_with_overdue_review=2),
        )
        assert result.status == "fail"
        assert "2" in result.failure_reason

    def test_inconclusive_when_no_vendors(self):
        rule = get_rule("vendor_risk_review_current")
        result = rule.check(TENANT_A, _ctx(critical_vendor_count=0))
        assert result.status == "inconclusive"
        assert result.failure_reason  # should explain why inconclusive

    def test_evidence_type_is_document(self):
        rule = get_rule("vendor_risk_review_current")
        result = rule.check(
            TENANT_A,
            _ctx(critical_vendor_count=5, vendors_with_overdue_review=0),
        )
        assert result.evidence[0].type == "document"


# ---------------------------------------------------------------------------
# 10. security_training_completed
# ---------------------------------------------------------------------------

class TestSecurityTrainingRule:
    def test_pass_all_trained(self):
        rule = get_rule("security_training_completed")
        result = rule.check(
            TENANT_A,
            _ctx(total_employees=50, employees_training_current=50),
        )
        assert result.status == "pass"

    def test_fail_when_not_everyone_trained(self):
        rule = get_rule("security_training_completed")
        result = rule.check(
            TENANT_A,
            _ctx(total_employees=50, employees_training_current=40),
        )
        assert result.status == "fail"
        assert "10" in result.failure_reason  # 50 - 40 shortfall
        assert "80.0%" in result.failure_reason  # 40/50 = 80%

    def test_inconclusive_when_no_employees(self):
        rule = get_rule("security_training_completed")
        result = rule.check(TENANT_A, _ctx(total_employees=0))
        assert result.status == "inconclusive"

    def test_tenant_isolation_via_metadata(self):
        """Different tenant calls should not bleed into each other's evidence."""
        rule = get_rule("security_training_completed")
        r1 = rule.check(TENANT_A, _ctx(total_employees=10, employees_training_current=10))
        r2 = rule.check(TENANT_B, _ctx(total_employees=10, employees_training_current=10))
        assert r1.evidence[0].metadata.get("tenant_id") == TENANT_A
        assert r2.evidence[0].metadata.get("tenant_id") == TENANT_B
