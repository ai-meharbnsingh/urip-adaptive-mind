"""
Attack path router — Project_33a §13 LIVE (MVP scaffold, 15th license module).

Endpoints
---------
GET  /api/attack-paths/critical             — top critical paths
GET  /api/attack-paths/{path_id}/details    — full path with node labels
POST /api/attack-paths/recompute            — recompute graph (BFS)
"""
from __future__ import annotations

import logging
import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from backend.middleware.module_gate import require_module
from backend.middleware.rbac import role_required
from backend.middleware.tenant import TenantContext
from backend.schemas.attack_path import (
    CriticalPathItem,
    CriticalPathListResponse,
    PathDetailsResponse,
    RecomputeResponse,
)
from backend.services.attack_path import (
    get_path_details,
    list_critical_paths,
    recompute_paths,
)

logger = logging.getLogger(__name__)

router = APIRouter(dependencies=[Depends(require_module("ATTACK_PATH"))])


@router.get("/critical", response_model=CriticalPathListResponse)
async def get_critical_paths(
    only_critical: bool = Query(default=True),
    limit: int = Query(default=50, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
    current_user: Any = Depends(role_required("ciso")),
) -> CriticalPathListResponse:
    tenant_id = TenantContext.get()
    rows = await list_critical_paths(db, tenant_id, only_critical=only_critical, limit=limit)
    return CriticalPathListResponse(
        items=[CriticalPathItem.model_validate(r, from_attributes=True) for r in rows],
        total=len(rows),
    )


@router.get("/{path_id}/details", response_model=PathDetailsResponse)
async def get_details(
    path_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: Any = Depends(role_required("ciso")),
) -> PathDetailsResponse:
    tenant_id = TenantContext.get()
    payload = await get_path_details(db, tenant_id, path_id)
    if payload is None:
        raise HTTPException(status_code=404, detail="Attack path not found.")
    return PathDetailsResponse(**payload)


@router.post("/recompute", response_model=RecomputeResponse)
async def post_recompute(
    max_hops: int = Query(default=5, ge=1, le=10),
    db: AsyncSession = Depends(get_db),
    current_user: Any = Depends(role_required("ciso")),
) -> RecomputeResponse:
    tenant_id = TenantContext.get()
    paths = await recompute_paths(db, tenant_id, max_hops=max_hops)
    await db.commit()
    return RecomputeResponse(
        status="ok",
        paths_computed=len(paths),
        critical_paths=sum(1 for p in paths if p.is_critical),
    )
