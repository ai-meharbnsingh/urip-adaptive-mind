"""
AI Security router — Project_33a §13 LIVE (MVP scaffold, 13th license module).

Endpoints
---------
GET  /api/ai-security/models                 — list AI models in inventory
POST /api/ai-security/models                 — register a new model
GET  /api/ai-security/prompt-injections      — list detected attacks
POST /api/ai-security/prompt-injections      — manual upload OR webhook ingest
GET  /api/ai-security/governance-status      — aggregate governance posture
"""
from __future__ import annotations

import logging
import uuid
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from backend.middleware.module_gate import require_module
from backend.middleware.rbac import role_required
from backend.middleware.tenant import TenantContext
from backend.schemas.ai_security import (
    AIModelCreateRequest,
    AIModelItem,
    AIModelListResponse,
    GovernanceStatusResponse,
    PromptInjectionItem,
    PromptInjectionListResponse,
    PromptInjectionUploadRequest,
)
from backend.services.ai_security import (
    aggregate_governance_status,
    create_ai_model,
    list_ai_models,
    list_prompt_injections,
    record_prompt_injection,
)

logger = logging.getLogger(__name__)

router = APIRouter(dependencies=[Depends(require_module("AI_SECURITY"))])


# --------------------------------------------------------------------------- #
@router.get("/models", response_model=AIModelListResponse)
async def get_models(
    provider: Optional[str] = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
    current_user: Any = Depends(role_required("ciso")),
) -> AIModelListResponse:
    tenant_id = TenantContext.get()
    try:
        rows = await list_ai_models(db, tenant_id, provider=provider, limit=limit, offset=offset)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    return AIModelListResponse(
        items=[AIModelItem.model_validate(r, from_attributes=True) for r in rows],
        total=len(rows),
    )


@router.post("/models", response_model=AIModelItem, status_code=201)
async def post_model(
    payload: AIModelCreateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: Any = Depends(role_required("ciso")),
) -> AIModelItem:
    tenant_id = TenantContext.get()
    try:
        m = await create_ai_model(
            db, tenant_id,
            name=payload.name,
            provider=payload.provider,
            purpose=payload.purpose,
            training_data_summary=payload.training_data_summary,
            deployment_endpoints=payload.deployment_endpoints,
            risk_level=payload.risk_level,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    await db.commit()
    await db.refresh(m)
    return AIModelItem.model_validate(m, from_attributes=True)


@router.get("/prompt-injections", response_model=PromptInjectionListResponse)
async def get_prompt_injections(
    ai_model_id: Optional[uuid.UUID] = Query(default=None),
    severity: Optional[str] = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
    current_user: Any = Depends(role_required("ciso")),
) -> PromptInjectionListResponse:
    tenant_id = TenantContext.get()
    rows = await list_prompt_injections(
        db, tenant_id,
        ai_model_id=ai_model_id, severity=severity, limit=limit, offset=offset,
    )
    return PromptInjectionListResponse(
        items=[PromptInjectionItem.model_validate(r, from_attributes=True) for r in rows],
        total=len(rows),
    )


@router.post("/prompt-injections", response_model=PromptInjectionItem, status_code=201)
async def post_prompt_injection(
    payload: PromptInjectionUploadRequest,
    db: AsyncSession = Depends(get_db),
    current_user: Any = Depends(role_required("ciso")),
) -> PromptInjectionItem:
    """Manual upload OR placeholder webhook ingest path."""
    tenant_id = TenantContext.get()
    try:
        ev = await record_prompt_injection(
            db, tenant_id,
            prompt_excerpt=payload.prompt_excerpt,
            ai_model_id=payload.ai_model_id,
            detection_source=payload.detection_source,
            severity=payload.severity,
            blocked=payload.blocked,
            metadata=payload.metadata,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    await db.commit()
    await db.refresh(ev)
    return PromptInjectionItem.model_validate(ev, from_attributes=True)


@router.get("/governance-status", response_model=GovernanceStatusResponse)
async def get_governance_status(
    db: AsyncSession = Depends(get_db),
    current_user: Any = Depends(role_required("ciso")),
) -> GovernanceStatusResponse:
    tenant_id = TenantContext.get()
    payload = await aggregate_governance_status(db, tenant_id)
    return GovernanceStatusResponse(**payload)
