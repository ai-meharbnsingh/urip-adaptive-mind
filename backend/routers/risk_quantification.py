"""
Risk Quantification (FAIR) router — Project_33a §13 LIVE
(MVP scaffold, 16th license module).

Endpoints
---------
GET  /api/risk-quantification/{risk_id}      — latest assessment for a single risk
POST /api/risk-quantification/{risk_id}      — record a new assessment
GET  /api/risk-quantification/aggregate      — total ALE + top-N risks
GET  /api/risk-quantification/assumptions    — current FAIR assumptions
POST /api/risk-quantification/assumptions    — update assumptions (history preserved)
"""
from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from backend.middleware.module_gate import require_module
from backend.middleware.rbac import role_required
from backend.middleware.tenant import TenantContext
from backend.schemas.risk_quantification import (
    AggregateResponse,
    AssessmentCreateRequest,
    AssessmentItem,
    AssumptionsItem,
    AssumptionsUpdateRequest,
)
from backend.services.risk_quantification import (
    aggregate,
    get_assessment_by_risk_id,
    get_assumptions,
    list_assessments,
    record_assessment,
    upsert_assumptions,
)

logger = logging.getLogger(__name__)

router = APIRouter(dependencies=[Depends(require_module("RISK_QUANT"))])


def _to_item(row) -> AssessmentItem:
    return AssessmentItem(
        risk_id=row.risk_id,
        risk_label=row.risk_label,
        loss_event_frequency=row.loss_event_frequency,
        loss_magnitude_usd=float(row.loss_magnitude_usd),
        annual_loss_exposure_usd=float(row.annual_loss_exposure_usd),
        components=row.components,
        computed_at=row.computed_at,
    )


# --------------------------------------------------------------------------- #
@router.get("/aggregate", response_model=AggregateResponse)
async def get_aggregate(
    top_n: int = Query(default=10, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: Any = Depends(role_required("ciso")),
) -> AggregateResponse:
    tenant_id = TenantContext.get()
    payload = await aggregate(db, tenant_id, top_n=top_n)
    return AggregateResponse(
        total_ale_usd=payload["total_ale_usd"],
        risk_count=payload["risk_count"],
        top_risks=[
            AssessmentItem(
                risk_id=r["risk_id"],
                risk_label=r["risk_label"],
                loss_event_frequency=r["loss_event_frequency"],
                loss_magnitude_usd=r["loss_magnitude_usd"],
                annual_loss_exposure_usd=r["annual_loss_exposure_usd"],
                components=r["components"],
                computed_at=r["computed_at"],
            )
            for r in payload["top_risks"]
        ],
    )


# --------------------------------------------------------------------------- #
@router.get("/assumptions", response_model=AssumptionsItem)
async def get_assumptions_endpoint(
    db: AsyncSession = Depends(get_db),
    current_user: Any = Depends(role_required("ciso")),
) -> AssumptionsItem:
    tenant_id = TenantContext.get()
    a = await get_assumptions(db, tenant_id)
    return AssumptionsItem(
        data_record_value_usd=float(a.data_record_value_usd),
        breach_response_cost_usd=float(a.breach_response_cost_usd),
        regulatory_fine_probability=float(a.regulatory_fine_probability),
        regulatory_fine_amount_usd=float(a.regulatory_fine_amount_usd),
        brand_damage_estimate_usd=float(a.brand_damage_estimate_usd),
        notes=getattr(a, "notes", None),
    )


@router.post("/assumptions", response_model=AssumptionsItem, status_code=201)
async def post_assumptions(
    payload: AssumptionsUpdateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: Any = Depends(role_required("ciso")),
) -> AssumptionsItem:
    tenant_id = TenantContext.get()
    try:
        a = await upsert_assumptions(
            db, tenant_id,
            data_record_value_usd=payload.data_record_value_usd,
            breach_response_cost_usd=payload.breach_response_cost_usd,
            regulatory_fine_probability=payload.regulatory_fine_probability,
            regulatory_fine_amount_usd=payload.regulatory_fine_amount_usd,
            brand_damage_estimate_usd=payload.brand_damage_estimate_usd,
            notes=payload.notes,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    await db.commit()
    await db.refresh(a)
    return AssumptionsItem(
        data_record_value_usd=float(a.data_record_value_usd),
        breach_response_cost_usd=float(a.breach_response_cost_usd),
        regulatory_fine_probability=float(a.regulatory_fine_probability),
        regulatory_fine_amount_usd=float(a.regulatory_fine_amount_usd),
        brand_damage_estimate_usd=float(a.brand_damage_estimate_usd),
        notes=a.notes,
    )


# --------------------------------------------------------------------------- #
@router.get("/{risk_id}", response_model=AssessmentItem)
async def get_assessment(
    risk_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: Any = Depends(role_required("ciso")),
) -> AssessmentItem:
    tenant_id = TenantContext.get()
    row = await get_assessment_by_risk_id(db, tenant_id, risk_id)
    if row is None:
        raise HTTPException(status_code=404, detail=f"No FAIR assessment for risk {risk_id!r}")
    return _to_item(row)


@router.post("/{risk_id}", response_model=AssessmentItem, status_code=201)
async def post_assessment(
    risk_id: str,
    payload: AssessmentCreateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: Any = Depends(role_required("ciso")),
) -> AssessmentItem:
    tenant_id = TenantContext.get()
    if payload.risk_id != risk_id:
        raise HTTPException(status_code=422, detail="risk_id in path and body must match")
    try:
        row = await record_assessment(
            db, tenant_id,
            risk_id=payload.risk_id,
            risk_label=payload.risk_label,
            loss_event_frequency=payload.loss_event_frequency,
            records_at_risk=payload.records_at_risk,
            extra_loss_usd=payload.extra_loss_usd,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    await db.commit()
    await db.refresh(row)
    return _to_item(row)
