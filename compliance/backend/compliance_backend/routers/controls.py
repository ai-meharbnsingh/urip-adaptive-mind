"""
Control check run API — P2B.3.

Endpoints:
  GET  /controls/runs              — list recent runs (filter by tenant, control, status)
  POST /controls/{id}/run          — trigger a control check on demand
  GET  /controls/{id}/runs/{run_id} — run detail with evidence IDs

All endpoints require authentication (require_tenant extracts tenant_id from JWT).
Tenant isolation: a tenant can only see their own runs.

CRIT-006 — caller MUST NOT influence rule inputs:
  POST /controls/{id}/run NEVER accepts tenant_config or connector_data from
  the request body. The control engine derives them server-side from the
  TenantConfig + ConnectorPull tables. This stops a tenant from forging a
  passing audit run by injecting custom inputs.
"""
from typing import List, Optional

import math
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from compliance_backend.database import get_async_session
from compliance_backend.middleware.auth import require_auth
from compliance_backend.middleware.tenant import require_tenant
from compliance_backend.models.control_run import ControlCheckRun
from compliance_backend.services.audit_writer import write_audit
from compliance_backend.services.control_engine import ControlEngine

router = APIRouter(prefix="/controls", tags=["controls"])


# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------

class ControlRunOut(BaseModel):
    id: str
    control_id: str
    tenant_id: str
    run_at: str
    status: str
    evidence_ids: Optional[List[str]]
    failure_reason: Optional[str]

    model_config = {"from_attributes": True}


class PaginatedRuns(BaseModel):
    items: List[ControlRunOut]
    total: int
    page: int
    limit: int
    pages: int


class TriggerRunRequest(BaseModel):
    """Body for POST /controls/{id}/run.

    CRIT-006 fix — this body intentionally does NOT carry tenant_config or
    connector_data. Those inputs are server-side state and must NEVER be
    supplied by the caller. Pydantic's `extra="forbid"` rejects requests
    that try to smuggle them in, so the security regression is loud rather
    than silent.

    Only `audit_period` (an evidence-tagging label) is accepted from the
    caller; it cannot influence the rule's pass/fail outcome.
    """
    audit_period: Optional[str] = None
    model_config = ConfigDict(extra="forbid")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _run_out(run: ControlCheckRun) -> ControlRunOut:
    return ControlRunOut(
        id=run.id,
        control_id=run.control_id,
        tenant_id=run.tenant_id,
        run_at=run.run_at.isoformat(),
        status=run.status,
        evidence_ids=run.evidence_ids or [],
        failure_reason=run.failure_reason,
    )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("/runs", response_model=PaginatedRuns)
async def list_runs(
    control_id: Optional[str] = Query(None, description="Filter by control ID"),
    run_status: Optional[str] = Query(None, alias="status", description="Filter by status"),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    tenant_id: str = Depends(require_tenant),
    session: AsyncSession = Depends(get_async_session),
) -> PaginatedRuns:
    """
    List recent control check runs for the authenticated tenant.

    Results are ordered by run_at descending (most recent first).
    """
    filters = [ControlCheckRun.tenant_id == tenant_id]
    if control_id:
        filters.append(ControlCheckRun.control_id == control_id)
    if run_status:
        filters.append(ControlCheckRun.status == run_status)

    where_clause = and_(*filters)

    count_result = await session.execute(
        select(func.count()).select_from(ControlCheckRun).where(where_clause)
    )
    total = count_result.scalar() or 0

    offset = (page - 1) * limit
    rows_result = await session.execute(
        select(ControlCheckRun)
        .where(where_clause)
        .order_by(ControlCheckRun.run_at.desc())
        .offset(offset)
        .limit(limit)
    )
    runs = rows_result.scalars().all()
    pages = math.ceil(total / limit) if total > 0 else 1

    return PaginatedRuns(
        items=[_run_out(r) for r in runs],
        total=total,
        page=page,
        limit=limit,
        pages=pages,
    )


@router.post("/{control_id}/run", response_model=ControlRunOut, status_code=status.HTTP_201_CREATED)
async def trigger_run(
    control_id: str,
    body: TriggerRunRequest = TriggerRunRequest(),
    claims: dict = Depends(require_auth),
    tenant_id: str = Depends(require_tenant),
    session: AsyncSession = Depends(get_async_session),
) -> ControlRunOut:
    """
    Trigger an on-demand control check for the authenticated tenant.

    Executes the rule synchronously and returns the run result immediately.
    For large-scale scheduled runs, the control_engine scheduler handles batching.
    """
    engine = ControlEngine(db=session)
    try:
        # CRIT-006: do NOT forward caller-supplied tenant_config / connector_data.
        # ControlEngine.run_control derives them from server-side state
        # (TenantConfig + ConnectorPull tables) when not provided.
        run = await engine.run_control(
            control_id=control_id,
            tenant_id=tenant_id,
            audit_period=body.audit_period,
        )
        await write_audit(
            session,
            tenant_id=tenant_id,
            user_id=claims.get("sub", "unknown"),
            action="control_run_triggered",
            resource_type="control_run",
            resource_id=run.id,
            details={
                "control_id": control_id,
                "status": run.status,
                "audit_period": body.audit_period,
            },
        )
        await session.commit()
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        )
    return _run_out(run)


@router.get("/{control_id}/runs/{run_id}", response_model=ControlRunOut)
async def get_run(
    control_id: str,
    run_id: str,
    tenant_id: str = Depends(require_tenant),
    session: AsyncSession = Depends(get_async_session),
) -> ControlRunOut:
    """
    Fetch a single control check run by ID.

    Enforces tenant isolation — a tenant can only fetch their own runs.
    """
    result = await session.execute(
        select(ControlCheckRun).where(
            and_(
                ControlCheckRun.id == run_id,
                ControlCheckRun.control_id == control_id,
                ControlCheckRun.tenant_id == tenant_id,
            )
        )
    )
    run = result.scalars().first()
    if run is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Run '{run_id}' not found for control '{control_id}'.",
        )
    return _run_out(run)
