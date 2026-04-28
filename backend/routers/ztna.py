"""
ZTNA router — Project_33a §13 LIVE (MVP scaffold, 14th license module).

Endpoints
---------
GET  /api/ztna/policies              — list policies
POST /api/ztna/policies              — create policy
GET  /api/ztna/access-decisions      — list audit log
GET  /api/ztna/posture-violations    — list posture failures
"""
from __future__ import annotations

import logging
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from backend.middleware.module_gate import require_module
from backend.middleware.rbac import role_required
from backend.middleware.tenant import TenantContext
from backend.schemas.ztna import (
    AccessDecisionItem,
    AccessDecisionListResponse,
    PolicyCreateRequest,
    PolicyItem,
    PolicyListResponse,
    PostureViolationItem,
    PostureViolationListResponse,
)
from backend.services.ztna import (
    create_policy,
    list_access_decisions,
    list_policies,
    list_posture_violations,
)

logger = logging.getLogger(__name__)

router = APIRouter(dependencies=[Depends(require_module("ZTNA"))])


@router.get("/policies", response_model=PolicyListResponse)
async def get_policies(
    target_app: Optional[str] = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
    current_user: Any = Depends(role_required("ciso")),
) -> PolicyListResponse:
    tenant_id = TenantContext.get()
    rows = await list_policies(db, tenant_id, target_app=target_app, limit=limit, offset=offset)
    return PolicyListResponse(
        items=[PolicyItem.model_validate(r, from_attributes=True) for r in rows],
        total=len(rows),
    )


@router.post("/policies", response_model=PolicyItem, status_code=201)
async def post_policy(
    payload: PolicyCreateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: Any = Depends(role_required("ciso")),
) -> PolicyItem:
    tenant_id = TenantContext.get()
    try:
        p = await create_policy(
            db, tenant_id,
            policy_name=payload.policy_name,
            target_app=payload.target_app,
            identity_required=payload.identity_required,
            mfa_required=payload.mfa_required,
            device_posture_required=payload.device_posture_required,
            source_provider=payload.source_provider,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    await db.commit()
    await db.refresh(p)
    return PolicyItem.model_validate(p, from_attributes=True)


@router.get("/access-decisions", response_model=AccessDecisionListResponse)
async def get_access_decisions(
    decision: Optional[str] = Query(default=None),
    target_app: Optional[str] = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
    current_user: Any = Depends(role_required("ciso")),
) -> AccessDecisionListResponse:
    tenant_id = TenantContext.get()
    rows = await list_access_decisions(
        db, tenant_id, decision=decision, target_app=target_app, limit=limit, offset=offset,
    )
    return AccessDecisionListResponse(
        items=[AccessDecisionItem.model_validate(r, from_attributes=True) for r in rows],
        total=len(rows),
    )


@router.get("/posture-violations", response_model=PostureViolationListResponse)
async def get_posture_violations(
    severity: Optional[str] = Query(default=None),
    remediated: Optional[bool] = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
    current_user: Any = Depends(role_required("ciso")),
) -> PostureViolationListResponse:
    tenant_id = TenantContext.get()
    rows = await list_posture_violations(
        db, tenant_id, severity=severity, remediated=remediated, limit=limit, offset=offset,
    )
    return PostureViolationListResponse(
        items=[PostureViolationItem.model_validate(r, from_attributes=True) for r in rows],
        total=len(rows),
    )
