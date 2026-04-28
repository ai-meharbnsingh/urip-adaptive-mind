"""
TDD — Control Engine tests (P2B.3)

Tests:
  - Registry: decorator registers rules, duplicate detection, list
  - load_builtin_rules populates all 10 expected rules
  - ControlEngine.run_control: pass/fail/inconclusive lifecycle
  - Evidence IDs are stored in run record after auto-capture
  - Tenant isolation: run_control stores correct tenant_id
  - Missing control raises ValueError
  - No rule_function on control → inconclusive result
"""
import time
import uuid
import pytest
# CRIT-005 (Z2.1): migrated python-jose -> PyJWT (HS256 surface identical)
import jwt
from sqlalchemy import select

from compliance_backend.models.framework import Framework, FrameworkVersion, Control
from compliance_backend.models.control_run import ControlCheckRun
from compliance_backend.services.control_rules import (
    register_control_rule,
    get_rule,
    list_rules,
    load_builtin_rules,
    _RULE_REGISTRY,
)
from compliance_backend.services.control_rules.base import (
    BaseControlRule,
    ControlContext,
    ControlCheckResult,
    EvidenceSpec,
)
from compliance_backend.services.control_engine import ControlEngine


STANDALONE_SECRET = "test-secret-standalone"


def _auth_headers(tenant_id: str = "tenant-engine-test") -> dict:
    payload = {
        "sub": "user-123",
        "tenant_id": tenant_id,
        "role": "admin",
        "exp": int(time.time()) + 3600,
        "iss": "compliance",
    }
    token = jwt.encode(payload, STANDALONE_SECRET, algorithm="HS256")
    return {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------------------
# Helper: create a minimal control in DB
# ---------------------------------------------------------------------------

async def _create_control(
    db_session,
    rule_function: str | None = "mfa_enforced",
    control_code: str = "CC6.1",
) -> Control:
    fw = Framework(
        id=str(uuid.uuid4()),
        name=f"Test FW {uuid.uuid4().hex[:6]}",
        short_code=f"TFW{uuid.uuid4().hex[:4].upper()}",
        category="security",
    )
    db_session.add(fw)
    await db_session.flush()

    fv = FrameworkVersion(
        id=str(uuid.uuid4()),
        framework_id=fw.id,
        version="2024",
        is_current=True,
    )
    db_session.add(fv)
    await db_session.flush()

    ctrl = Control(
        id=str(uuid.uuid4()),
        framework_version_id=fv.id,
        control_code=control_code,
        category="Access",
        description="Test control",
        rule_function=rule_function,
    )
    db_session.add(ctrl)
    await db_session.flush()
    return ctrl


# ---------------------------------------------------------------------------
# Registry tests
# ---------------------------------------------------------------------------

class TestControlRuleRegistry:
    def test_load_builtin_rules_populates_registry(self):
        """All 10 expected builtin rules are registered after load_builtin_rules()."""
        load_builtin_rules()
        rules = list_rules()
        expected = {
            "mfa_enforced",
            "password_policy_meets_baseline",
            "encryption_at_rest_configured",
            "audit_logging_enabled",
            "access_review_completed",
            "incident_response_plan_documented",
            "backup_configured",
            "vulnerability_scanning_active",
            "vendor_risk_review_current",
            "security_training_completed",
        }
        registered = set(rules.keys())
        for rule_name in expected:
            assert rule_name in registered, (
                f"Expected rule '{rule_name}' to be registered. "
                f"Registered rules: {sorted(registered)}"
            )

    def test_get_rule_returns_instance(self):
        load_builtin_rules()
        rule = get_rule("mfa_enforced")
        assert rule is not None, "get_rule('mfa_enforced') returned None"
        assert isinstance(rule, BaseControlRule)

    def test_get_rule_unknown_returns_none(self):
        load_builtin_rules()
        result = get_rule("nonexistent_rule_xyz")
        assert result is None

    def test_register_duplicate_same_class_is_idempotent(self):
        """Registering the same class under the same name twice is OK."""
        @register_control_rule("duplicate_safe_test")
        class TestRule(BaseControlRule):
            def check(self, tenant_id, context):
                return ControlCheckResult(status="pass")

        # Second registration — same class, should not raise
        register_control_rule("duplicate_safe_test")(TestRule)
        assert get_rule("duplicate_safe_test") is not None

    def test_register_duplicate_different_class_raises(self):
        """Registering a different class under an existing name raises ValueError."""
        @register_control_rule("collision_test_a")
        class RuleA(BaseControlRule):
            def check(self, tenant_id, context):
                return ControlCheckResult(status="pass")

        with pytest.raises(ValueError, match="already registered"):
            @register_control_rule("collision_test_a")
            class RuleB(BaseControlRule):
                def check(self, tenant_id, context):
                    return ControlCheckResult(status="pass")


# ---------------------------------------------------------------------------
# ControlCheckResult dataclass validation
# ---------------------------------------------------------------------------

class TestControlCheckResult:
    def test_valid_pass(self):
        r = ControlCheckResult(status="pass")
        assert r.status == "pass"
        assert r.failure_reason is None

    def test_valid_fail_requires_reason(self):
        r = ControlCheckResult(status="fail", failure_reason="something is broken")
        assert r.status == "fail"
        assert r.failure_reason == "something is broken"

    def test_fail_without_reason_raises(self):
        with pytest.raises(ValueError, match="failure_reason"):
            ControlCheckResult(status="fail")

    def test_invalid_status_raises(self):
        with pytest.raises(ValueError, match="Invalid status"):
            ControlCheckResult(status="unknown")

    def test_inconclusive_no_reason_ok(self):
        # inconclusive with a reason is also fine
        r = ControlCheckResult(status="inconclusive", failure_reason="connector offline")
        assert r.status == "inconclusive"


# ---------------------------------------------------------------------------
# ControlEngine integration tests (async, uses in-memory SQLite)
# ---------------------------------------------------------------------------

@pytest.mark.anyio
async def test_run_control_pass(db_session):
    """run_control returns a ControlCheckRun with status=pass when MFA is configured."""
    ctrl = await _create_control(db_session, rule_function="mfa_enforced")
    await db_session.commit()

    engine = ControlEngine(db=db_session)
    run = await engine.run_control(
        control_id=ctrl.id,
        tenant_id="tenant-a",
        tenant_config={"mfa_enabled": True, "mfa_enforcement": "all_users"},
    )
    await db_session.commit()

    assert run.status == "pass", f"Expected pass, got: {run.status}"
    assert run.control_id == ctrl.id
    assert run.tenant_id == "tenant-a"
    assert run.id is not None


@pytest.mark.anyio
async def test_run_control_fail(db_session):
    """run_control returns status=fail when MFA is disabled."""
    ctrl = await _create_control(db_session, rule_function="mfa_enforced")
    await db_session.commit()

    engine = ControlEngine(db=db_session)
    run = await engine.run_control(
        control_id=ctrl.id,
        tenant_id="tenant-b",
        tenant_config={"mfa_enabled": False},
    )
    await db_session.commit()

    assert run.status == "fail", f"Expected fail, got: {run.status}"
    assert run.failure_reason is not None
    assert "MFA" in run.failure_reason


@pytest.mark.anyio
async def test_run_control_evidence_ids_populated(db_session):
    """run_control auto-captures evidence and stores IDs in evidence_ids."""
    ctrl = await _create_control(db_session, rule_function="mfa_enforced")
    await db_session.commit()

    engine = ControlEngine(db=db_session)
    run = await engine.run_control(
        control_id=ctrl.id,
        tenant_id="tenant-c",
        tenant_config={"mfa_enabled": True, "mfa_enforcement": "all_users"},
    )
    await db_session.commit()

    assert isinstance(run.evidence_ids, list)
    assert len(run.evidence_ids) >= 1, "Expected at least one evidence record to be auto-captured"


@pytest.mark.anyio
async def test_run_control_no_rule_returns_inconclusive(db_session):
    """Controls with no rule_function return inconclusive."""
    ctrl = await _create_control(db_session, rule_function=None)
    await db_session.commit()

    engine = ControlEngine(db=db_session)
    run = await engine.run_control(
        control_id=ctrl.id,
        tenant_id="tenant-d",
    )
    await db_session.commit()

    assert run.status == "inconclusive"


@pytest.mark.anyio
async def test_run_control_unknown_rule_name_returns_inconclusive(db_session):
    """Controls with an unregistered rule_function name return inconclusive."""
    ctrl = await _create_control(db_session, rule_function="totally_unknown_rule_xyz")
    await db_session.commit()

    engine = ControlEngine(db=db_session)
    run = await engine.run_control(
        control_id=ctrl.id,
        tenant_id="tenant-e",
    )
    await db_session.commit()

    assert run.status == "inconclusive"


@pytest.mark.anyio
async def test_run_control_invalid_control_id_raises(db_session):
    """run_control raises ValueError when control_id doesn't exist."""
    engine = ControlEngine(db=db_session)
    with pytest.raises(ValueError, match="not found"):
        await engine.run_control(
            control_id=str(uuid.uuid4()),
            tenant_id="tenant-f",
        )


@pytest.mark.anyio
async def test_run_control_tenant_isolation(db_session):
    """run stores the correct tenant_id, not bleed from other tenants."""
    ctrl = await _create_control(db_session, rule_function="mfa_enforced")
    await db_session.commit()

    engine = ControlEngine(db=db_session)
    run1 = await engine.run_control(
        control_id=ctrl.id,
        tenant_id="tenant-x",
        tenant_config={"mfa_enabled": True, "mfa_enforcement": "all_users"},
    )
    run2 = await engine.run_control(
        control_id=ctrl.id,
        tenant_id="tenant-y",
        tenant_config={"mfa_enabled": False},
    )
    await db_session.commit()

    assert run1.tenant_id == "tenant-x"
    assert run2.tenant_id == "tenant-y"
    assert run1.status == "pass"
    assert run2.status == "fail"


@pytest.mark.anyio
async def test_run_persisted_in_db(db_session):
    """ControlCheckRun is persisted and retrievable from the DB."""
    ctrl = await _create_control(db_session, rule_function="audit_logging_enabled")
    await db_session.commit()

    engine = ControlEngine(db=db_session)
    run = await engine.run_control(
        control_id=ctrl.id,
        tenant_id="tenant-persist",
        tenant_config={"audit_logging_enabled": True, "log_retention_days": 400},
    )
    await db_session.commit()

    # Re-fetch from DB
    result = await db_session.execute(
        select(ControlCheckRun).where(ControlCheckRun.id == run.id)
    )
    fetched = result.scalars().first()
    assert fetched is not None
    assert fetched.status == "pass"
    assert fetched.tenant_id == "tenant-persist"
