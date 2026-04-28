"""
auto_remediation router — admin endpoints for the Phase 2 framework.

    POST /api/auto-remediation/{risk_id}/check     — implication-check only
    POST /api/auto-remediation/{risk_id}/execute   — implication-check + execute
    GET  /api/auto-remediation/executions          — past audit log

All endpoints require an authenticated tenant admin (role check).  The
`execute` endpoint enforces the approval gate (see auto_remediation_service).
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from backend.middleware.auth import get_current_user
from backend.models.audit_log import AuditLog
from backend.models.auto_remediation import AutoRemediationExecution
from backend.models.risk import Risk
from backend.models.user import User
from backend.services.auto_remediation_service import (
    ApprovalRequiredError,
    execute_with_approval_gate,
    implication_check,
    list_executions,
    retest_after_execution,
    select_executor,
)

router = APIRouter()


# --------------------------------------------------------------------------- #
class ImplicationOut(BaseModel):
    executor: str
    services_affected: list[str]
    expected_downtime_minutes: int
    rollback_plan: str
    notes: str


class ExecuteIn(BaseModel):
    dry_run: bool = False
    # If the tenant has the risk's category pre-approved this can be omitted.
    explicit_approval: bool = Field(default=False, description="Set True to confirm human approval.")


class ExecutionOut(BaseModel):
    id: str
    risk_id: str
    executor_name: str
    status: str
    dry_run: bool
    services_affected: list[str] | None
    expected_downtime_minutes: int | None
    rollback_plan: str | None
    before_state: dict[str, Any] | None
    after_state: dict[str, Any] | None
    retest_passed: bool | None
    error_message: str | None
    auto_approved: bool
    started_at: datetime
    completed_at: datetime | None

    @classmethod
    def from_model(cls, e: AutoRemediationExecution) -> "ExecutionOut":
        return cls(
            id=str(e.id),
            risk_id=str(e.risk_id),
            executor_name=e.executor_name,
            status=e.status,
            dry_run=e.dry_run,
            services_affected=e.services_affected,
            expected_downtime_minutes=e.expected_downtime_minutes,
            rollback_plan=e.rollback_plan,
            before_state=e.before_state,
            after_state=e.after_state,
            retest_passed=e.retest_passed,
            error_message=e.error_message,
            auto_approved=e.auto_approved,
            started_at=e.started_at,
            completed_at=e.completed_at,
        )


# --------------------------------------------------------------------------- #
def _require_admin(user: User) -> uuid.UUID:
    if user.role not in ("ciso", "admin", "tenant_admin", "super_admin"):
        raise HTTPException(status_code=403, detail="Admin role required")
    if user.tenant_id is None:
        raise HTTPException(status_code=400, detail="User has no tenant scope")
    return user.tenant_id


async def _get_tenant_risk(
    db: AsyncSession, tenant_id: uuid.UUID, risk_id: uuid.UUID
) -> Risk:
    q = await db.execute(
        select(Risk).where(Risk.id == risk_id, Risk.tenant_id == tenant_id)
    )
    risk = q.scalar_one_or_none()
    if risk is None:
        raise HTTPException(status_code=404, detail="Risk not found")
    return risk


# --------------------------------------------------------------------------- #
@router.post("/{risk_id}/check", response_model=ImplicationOut)
async def check_endpoint(
    risk_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ImplicationOut:
    tenant_id = _require_admin(user)
    risk = await _get_tenant_risk(db, tenant_id, risk_id)
    executor = select_executor(risk)
    if executor is None:
        raise HTTPException(
            status_code=400,
            detail=f"No auto-remediation executor available for risk source {risk.source!r}",
        )
    impl = implication_check(executor, risk)
    return ImplicationOut(
        executor=executor.executor_name,
        services_affected=impl.services_affected,
        expected_downtime_minutes=impl.expected_downtime_minutes,
        rollback_plan=impl.rollback_plan,
        notes=impl.notes,
    )


# --------------------------------------------------------------------------- #
@router.post("/{risk_id}/execute", response_model=ExecutionOut)
async def execute_endpoint(
    risk_id: uuid.UUID,
    payload: ExecuteIn,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ExecutionOut:
    tenant_id = _require_admin(user)
    risk = await _get_tenant_risk(db, tenant_id, risk_id)
    executor = select_executor(risk)
    if executor is None:
        raise HTTPException(
            status_code=400,
            detail=f"No auto-remediation executor for risk source {risk.source!r}",
        )

    approver_user_id = user.id if payload.explicit_approval else None
    try:
        execution, result = await execute_with_approval_gate(
            db, risk,
            executor=executor,
            approver_user_id=approver_user_id,
            dry_run=payload.dry_run,
        )
    except ApprovalRequiredError as exc:
        raise HTTPException(status_code=403, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    # Retest only on a successful non-dry-run execution.
    if result.success and not payload.dry_run:
        await retest_after_execution(db, execution, risk, executor)

    # Audit log — record execute action with approver + dry-run flag.
    db.add(
        AuditLog(
            id=uuid.uuid4(),
            user_id=user.id,
            tenant_id=tenant_id,
            action="auto_remediation_execute",
            resource_type="auto_remediation_execution",
            resource_id=execution.id,
            details={
                "risk_id": str(risk.id),
                "executor": executor.executor_name,
                "dry_run": bool(payload.dry_run),
                "approver_user_id": str(approver_user_id) if approver_user_id else None,
                "status": execution.status,
                "auto_approved": bool(execution.auto_approved),
            },
        )
    )
    await db.commit()
    return ExecutionOut.from_model(execution)


# --------------------------------------------------------------------------- #
@router.get("/executions", response_model=list[ExecutionOut])
async def list_executions_endpoint(
    risk_id: Optional[uuid.UUID] = None,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[ExecutionOut]:
    tenant_id = _require_admin(user)
    rows = await list_executions(db, tenant_id, risk_id=risk_id)
    return [ExecutionOut.from_model(r) for r in rows]


# --------------------------------------------------------------------------- #
@router.get("/runs")
async def list_runs_endpoint(
    per_page: int = 20,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """UI-friendly view of recent auto-remediation runs for domain-workflow.html.

    Same data as /executions but flattened to the column names the
    frontend table renders: run_id, action, asset, result, created_at.
    """
    tenant_id = _require_admin(user)
    rows = await list_executions(db, tenant_id, risk_id=None)

    # Pull the human-readable asset string off each execution's Risk row.
    risk_ids = [r.risk_id for r in rows[:per_page]]
    asset_map: dict[uuid.UUID, str] = {}
    if risk_ids:
        from backend.models.risk import Risk
        risk_q = select(Risk).where(Risk.id.in_(risk_ids))
        if hasattr(Risk, "tenant_id"):
            risk_q = risk_q.where(Risk.tenant_id == tenant_id)
        for risk in (await db.execute(risk_q)).scalars().all():
            asset_map[risk.id] = risk.asset

    items = []
    for e in rows[:per_page]:
        items.append({
            "run_id": str(e.id)[:8],
            "action": e.executor_name,
            "asset": asset_map.get(e.risk_id, "—"),
            "result": e.status,
            "created_at": e.started_at.isoformat() if e.started_at else None,
        })
    return {"items": items, "total": len(rows)}
