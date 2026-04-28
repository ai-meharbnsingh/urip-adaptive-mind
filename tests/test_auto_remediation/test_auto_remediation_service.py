"""auto_remediation_service — integration with DB + executors (mocked)."""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.risk import Risk
from backend.models.tenant import Tenant
from backend.models.user import User
from backend.services.auto_remediation.base import (
    ExecutionResult,
    ImplicationCheckResult,
    RemediationExecutorBase,
)
from backend.services.auto_remediation_service import (
    ApprovalRequiredError,
    execute_with_approval_gate,
    is_pre_approved,
    list_executions,
    retest_after_execution,
    select_executor,
)


# --------------------------------------------------------------------------- #
class MockExecutor(RemediationExecutorBase):
    executor_name = "mock_exec"

    def __init__(self, success: bool = True, retest_pass: bool = True) -> None:
        self.success = success
        self.retest_pass = retest_pass
        self.calls: list[str] = []

    def implication_check(self, risk):
        self.calls.append("check")
        return ImplicationCheckResult(
            services_affected=["svc1"], expected_downtime_minutes=2,
            rollback_plan="reverse-it", notes="test",
        )

    def execute(self, risk, dry_run=True):
        self.calls.append(f"execute(dry={dry_run})")
        return ExecutionResult(
            success=self.success,
            before_state={"v": "before"},
            after_state={"v": "after"},
            output_log="ok" if self.success else "fail",
            error=None if self.success else "boom",
            dry_run=dry_run,
        )

    def retest(self, risk):
        return self.retest_pass, {"checked": True}


# --------------------------------------------------------------------------- #
@pytest_asyncio.fixture
async def admin_user_for_remediation(db_session: AsyncSession, default_tenant):
    user = User(
        id=uuid.uuid4(),
        email="rem-admin@test.co",
        hashed_password="x",
        full_name="Remediation Admin",
        role="ciso",
        team="Sec",
        is_active=True,
        tenant_id=default_tenant.id,
    )
    db_session.add(user)
    await db_session.commit()
    return user


@pytest_asyncio.fixture
async def open_risk(db_session: AsyncSession, default_tenant):
    risk = Risk(
        id=uuid.uuid4(),
        risk_id="RISK-AR-001",
        finding="CVE-2024-1234 RCE",
        source="crowdstrike",
        domain="application",
        cvss_score=9.0,
        severity="critical",
        asset="srv-01",
        owner_team="Infra",
        status="open",
        sla_deadline=datetime.now(timezone.utc) + timedelta(days=7),
        tenant_id=default_tenant.id,
        cve_id="CVE-2024-1234",
    )
    db_session.add(risk)
    await db_session.commit()
    await db_session.refresh(risk)
    return risk


# --------------------------------------------------------------------------- #
def test_select_executor_picks_crowdstrike_for_endpoint_source():
    risk = type("R", (), {"source": "crowdstrike", "finding": "x", "asset": "h1"})()
    ex = select_executor(risk)
    assert ex is not None
    assert ex.executor_name == "crowdstrike_rtr"


def test_select_executor_picks_fortinet_for_threat_intel():
    risk = type("R", (), {"source": "threat_intel", "finding": "x", "asset": "1.2.3.4"})()
    ex = select_executor(risk)
    assert ex is not None
    assert ex.executor_name == "fortinet"


def test_select_executor_picks_cyberark_for_credential_risk():
    risk = type("R", (), {"source": "soc", "finding": "Leaked credential on github"})()
    ex = select_executor(risk)
    assert ex is not None
    assert ex.executor_name == "cyberark"


# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_execute_blocked_when_no_approver_and_not_preapproved(
    db_session: AsyncSession, open_risk
):
    executor = MockExecutor()
    with pytest.raises(ApprovalRequiredError):
        await execute_with_approval_gate(
            db_session, open_risk, executor=executor,
            approver_user_id=None, force=False,
        )


@pytest.mark.asyncio
async def test_execute_with_explicit_approver_succeeds(
    db_session: AsyncSession, open_risk, admin_user_for_remediation
):
    executor = MockExecutor()
    row, result = await execute_with_approval_gate(
        db_session, open_risk, executor=executor,
        approver_user_id=admin_user_for_remediation.id, dry_run=False,
    )
    await db_session.commit()
    assert result.success
    assert row.status == "succeeded"
    assert row.approver_user_id == admin_user_for_remediation.id
    assert row.auto_approved is False
    assert row.before_state == {"v": "before"}


@pytest.mark.asyncio
async def test_execute_dry_run_marks_status_dry_run(
    db_session: AsyncSession, open_risk, admin_user_for_remediation
):
    executor = MockExecutor()
    row, result = await execute_with_approval_gate(
        db_session, open_risk, executor=executor,
        approver_user_id=admin_user_for_remediation.id, dry_run=True,
    )
    await db_session.commit()
    assert result.dry_run
    assert row.status == "dry_run"
    assert row.dry_run is True


@pytest.mark.asyncio
async def test_pre_approved_category_runs_without_approver(
    db_session: AsyncSession, default_tenant
):
    # Configure tenant to pre-approve ssl_expired.
    default_tenant.settings = {
        **(default_tenant.settings or {}),
        "auto_remediation_categories": ["ssl_expired"],
    }
    await db_session.commit()

    risk = Risk(
        id=uuid.uuid4(),
        risk_id="RISK-AR-SSL",
        finding="SSL cert expired on www.acme.com",
        source="easm",
        domain="network",
        cvss_score=5.0,
        severity="medium",
        asset="www.acme.com",
        owner_team="Web",
        status="open",
        sla_deadline=datetime.now(timezone.utc) + timedelta(days=7),
        tenant_id=default_tenant.id,
    )
    db_session.add(risk)
    await db_session.commit()

    pre = await is_pre_approved(db_session, risk)
    assert pre is True

    executor = MockExecutor()
    row, _ = await execute_with_approval_gate(
        db_session, risk, executor=executor, approver_user_id=None, dry_run=False,
    )
    await db_session.commit()
    assert row.auto_approved is True
    assert row.approver_user_id is None


@pytest.mark.asyncio
async def test_failed_execution_persists_error_message(
    db_session: AsyncSession, open_risk, admin_user_for_remediation
):
    executor = MockExecutor(success=False)
    row, result = await execute_with_approval_gate(
        db_session, open_risk, executor=executor,
        approver_user_id=admin_user_for_remediation.id, dry_run=False,
    )
    await db_session.commit()
    assert not result.success
    assert row.status == "failed"
    assert row.error_message == "boom"


# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_retest_after_execution_closes_risk_when_clean(
    db_session: AsyncSession, open_risk, admin_user_for_remediation
):
    executor = MockExecutor()
    row, _ = await execute_with_approval_gate(
        db_session, open_risk, executor=executor,
        approver_user_id=admin_user_for_remediation.id, dry_run=False,
    )
    passed, details = await retest_after_execution(db_session, row, open_risk, executor)
    await db_session.commit()
    assert passed
    await db_session.refresh(open_risk)
    assert open_risk.status == "resolved"
    assert row.retest_passed is True


@pytest.mark.asyncio
async def test_retest_failure_keeps_risk_open(
    db_session: AsyncSession, open_risk, admin_user_for_remediation
):
    executor = MockExecutor(retest_pass=False)
    row, _ = await execute_with_approval_gate(
        db_session, open_risk, executor=executor,
        approver_user_id=admin_user_for_remediation.id, dry_run=False,
    )
    await retest_after_execution(db_session, row, open_risk, executor)
    await db_session.commit()
    await db_session.refresh(open_risk)
    assert open_risk.status == "open"
    assert row.retest_passed is False


# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_list_executions_filters_by_tenant_and_risk(
    db_session: AsyncSession, default_tenant, open_risk, admin_user_for_remediation
):
    executor = MockExecutor()
    await execute_with_approval_gate(
        db_session, open_risk, executor=executor,
        approver_user_id=admin_user_for_remediation.id, dry_run=True,
    )
    await db_session.commit()
    rows = await list_executions(db_session, default_tenant.id)
    assert len(rows) == 1
    rows_filtered = await list_executions(
        db_session, default_tenant.id, risk_id=open_risk.id
    )
    assert len(rows_filtered) == 1
