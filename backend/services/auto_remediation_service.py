"""
auto_remediation_service — orchestrates the Phase 2 framework.

Workflow

    select_executor(risk)              → pick an executor based on risk source
    implication_check(...)             → returns services_affected + downtime
    execute_with_approval_gate(...)    → enforces approver_user_id (or pre-approved)
    log_execution(...)                 → writes the immutable audit row
    retest_after_execution(risk)       → re-runs the original detection

Approval gate (URIP_Blueprint v3 §4.2)
--------------------------------------
Risks are NOT auto-executed by default.  Tenants whitelist categories under
`tenant.settings["auto_remediation_categories"]`; only those categories run
without a human approver:

    {
        "auto_remediation_categories": ["ssl_expired", "missing_dmarc"]
    }

For all other risks, `execute_with_approval_gate` requires an
`approver_user_id` AND the implication-check result to be present.
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.auto_remediation import AutoRemediationExecution
from backend.models.risk import Risk
from backend.models.tenant import Tenant
from backend.services.auto_remediation import (
    ExecutionResult,
    ImplicationCheckResult,
    RemediationExecutorBase,
)
from backend.services.auto_remediation.crowdstrike_rtr import CrowdStrikeRTRExecutor
from backend.services.auto_remediation.cyberark import CyberArkExecutor
from backend.services.auto_remediation.fortinet import FortinetExecutor

logger = logging.getLogger(__name__)


# --------------------------------------------------------------------------- #
class ApprovalRequiredError(Exception):
    """Raised when execute is called without approver_user_id and the risk
    category is NOT in the tenant's auto_remediation_categories list."""


# --------------------------------------------------------------------------- #
def select_executor(risk: Risk) -> RemediationExecutorBase | None:
    """
    Default executor mapping.  Tenants can override via a registered factory
    callback in the future; for the framework slice we use a static map.

        risk.source = 'crowdstrike' / endpoint CVE      → CrowdStrikeRTR
        risk.source = 'threat_intel'                    → Fortinet (block IP)
        risk.source = 'pam' / risk.finding contains "credential"
                                                        → CyberArk
        otherwise                                       → None (no executor)
    """
    src = (getattr(risk, "source", "") or "").lower()
    finding = (getattr(risk, "finding", "") or "").lower()
    # Credential rotation takes precedence — a leaked-credential SOC alert
    # should rotate via CyberArk, not block at the firewall.
    if src in ("pam", "cyberark") or "credential" in finding:
        return CyberArkExecutor()
    if src in ("crowdstrike", "edr", "endpoint"):
        return CrowdStrikeRTRExecutor()
    if src in ("threat_intel", "ioc", "soc"):
        return FortinetExecutor()
    return None


# --------------------------------------------------------------------------- #
def _category_for_risk(risk: Risk) -> str:
    """Heuristic: map a risk to a category string used in tenant whitelist."""
    finding = (getattr(risk, "finding", "") or "").lower()
    if "ssl" in finding and ("expired" in finding or "expiry" in finding):
        return "ssl_expired"
    if "dmarc" in finding:
        return "missing_dmarc"
    src = (getattr(risk, "source", "") or "").lower()
    return src or "uncategorised"


async def is_pre_approved(
    db: AsyncSession, risk: Risk
) -> bool:
    q = await db.execute(select(Tenant).where(Tenant.id == risk.tenant_id))
    tenant = q.scalar_one_or_none()
    if tenant is None:
        return False
    cats = (tenant.settings or {}).get("auto_remediation_categories") or []
    return _category_for_risk(risk) in cats


# --------------------------------------------------------------------------- #
def implication_check(
    executor: RemediationExecutorBase, risk: Risk
) -> ImplicationCheckResult:
    return executor.implication_check(risk)


# --------------------------------------------------------------------------- #
async def execute_with_approval_gate(
    db: AsyncSession,
    risk: Risk,
    *,
    executor: RemediationExecutorBase | None = None,
    approver_user_id: uuid.UUID | None = None,
    force: bool = False,
    dry_run: bool = False,
) -> tuple[AutoRemediationExecution, ExecutionResult]:
    """
    Run the full pipeline: implication check → approval gate → execute → log.

    `force=True` lets a tenant pre-approve specific categories — but at least
    one of (approver_user_id, force, pre-approved-category) must be true.
    """
    if executor is None:
        executor = select_executor(risk)
    if executor is None:
        raise ValueError(f"No executor available for risk {risk.risk_id}")

    pre_approved = False
    if approver_user_id is None and not force:
        pre_approved = await is_pre_approved(db, risk)
        if not pre_approved:
            raise ApprovalRequiredError(
                f"Risk {risk.risk_id} is not pre-approved; pass approver_user_id"
            )

    impl = executor.implication_check(risk)
    started = datetime.now(timezone.utc)
    result = executor.execute(risk, dry_run=dry_run)

    row = AutoRemediationExecution(
        id=uuid.uuid4(),
        tenant_id=risk.tenant_id,
        risk_id=risk.id,
        executor_name=executor.executor_name,
        status="dry_run" if dry_run else ("succeeded" if result.success else "failed"),
        dry_run=dry_run,
        services_affected=impl.services_affected,
        expected_downtime_minutes=impl.expected_downtime_minutes,
        rollback_plan=impl.rollback_plan,
        before_state=result.before_state,
        after_state=result.after_state,
        approver_user_id=approver_user_id,
        auto_approved=pre_approved or force,
        error_message=result.error,
        started_at=started,
        completed_at=datetime.now(timezone.utc),
    )
    db.add(row)
    await db.flush()
    return row, result


# --------------------------------------------------------------------------- #
async def retest_after_execution(
    db: AsyncSession,
    execution: AutoRemediationExecution,
    risk: Risk,
    executor: RemediationExecutorBase,
) -> tuple[bool, dict[str, Any]]:
    passed, details = executor.retest(risk)
    execution.retest_passed = bool(passed)
    execution.retest_details = details
    if passed and risk.status not in ("resolved", "closed"):
        risk.status = "resolved"
    await db.flush()
    return passed, details


# --------------------------------------------------------------------------- #
async def list_executions(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    *,
    risk_id: uuid.UUID | None = None,
    limit: int = 100,
) -> list[AutoRemediationExecution]:
    stmt = select(AutoRemediationExecution).where(
        AutoRemediationExecution.tenant_id == tenant_id
    )
    if risk_id is not None:
        stmt = stmt.where(AutoRemediationExecution.risk_id == risk_id)
    stmt = stmt.order_by(AutoRemediationExecution.started_at.desc()).limit(limit)
    q = await db.execute(stmt)
    return list(q.scalars().all())
