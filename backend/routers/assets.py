"""
backend/routers/assets.py — Asset REST API.

All endpoints:
  - require an authenticated user (JWT)
  - require the CORE module to be active for the caller's tenant
  - are tenant-scoped via TenantContext

Endpoints
---------
  GET    /api/assets                — paginated list with filters
  GET    /api/assets/categories     — counts per high-level UI category
  GET    /api/assets/{id}           — single asset + bundled open risks
  PATCH  /api/assets/{id}           — admin: update editable fields
  GET    /api/assets/{id}/risks     — paginated open-risk list for this asset
  GET    /api/assets/{id}/timeline  — chronological event timeline
"""
from __future__ import annotations

import math
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from backend.middleware.auth import get_current_user
from backend.middleware.module_gate import require_module
from backend.middleware.rbac import role_required
from backend.middleware.tenant import TenantContext
from backend.models.asset import (
    ASSET_CATEGORIES,
    ASSET_TIERS,
    BUSINESS_CRITICALITY_VALUES,
    DEVICE_CATEGORIES,
    LIFECYCLE_STATES,
    Asset,
)
from backend.models.audit_log import AuditLog
from backend.models.risk import Risk
from backend.models.user import User
from backend.schemas.asset import (
    AssetCategoryCounts,
    AssetListResponse,
    AssetRead,
    AssetRisksListResponse,
    AssetRiskRead,
    AssetTimelineEvent,
    AssetTimelineResponse,
    AssetUpdate,
    AssetWithRisksResponse,
)
from backend.services import asset_service
from backend.services.asset_service import AssetFilters


# Router-level CORE gate (every asset endpoint requires the CORE module).
router = APIRouter(dependencies=[Depends(require_module("CORE"))])

require_admin = role_required("ciso")


def _risk_to_slim(r: Risk) -> AssetRiskRead:
    return AssetRiskRead(
        id=str(r.id),
        risk_id=r.risk_id,
        finding=r.finding,
        description=r.description,
        source=r.source,
        domain=r.domain,
        severity=r.severity,
        cvss_score=float(r.cvss_score),
        composite_score=(
            float(r.composite_score) if r.composite_score is not None else None
        ),
        status=r.status,
        created_at=r.created_at,
        updated_at=r.updated_at,
    )


# ─────────────────────────────────────────────────────────────────────────────
# List + categories
# ─────────────────────────────────────────────────────────────────────────────


@router.get("/categories", response_model=AssetCategoryCounts)
async def asset_categories(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return per-category counts for dashboard widgets."""
    tenant_id = TenantContext.get()
    counts = await asset_service.count_by_category(db, tenant_id)
    return AssetCategoryCounts(counts=counts, total=sum(counts.values()))


@router.get("", response_model=AssetListResponse)
async def list_assets(
    device_category: Optional[str] = Query(default=None, max_length=10),
    asset_tier: Optional[str] = Query(default=None, max_length=2),
    owner_team: Optional[str] = Query(default=None, max_length=200),
    has_critical_risks: Optional[bool] = Query(default=None),
    custom_tag: Optional[str] = Query(default=None, max_length=200),
    search: Optional[str] = Query(default=None, max_length=200),
    lifecycle_state: Optional[str] = Query(default=None, max_length=20),
    category: Optional[str] = Query(default=None, max_length=40),
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=20, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Paginated, filtered, tenant-scoped asset list."""
    tenant_id = TenantContext.get()

    # Light validation (422 on bad enum values)
    if device_category is not None and device_category.upper() not in (
        "IT",
        "OT",
        "IOT",
        "SAAS",
    ):
        raise HTTPException(
            status_code=422,
            detail=f"device_category must be one of {DEVICE_CATEGORIES}",
        )
    if asset_tier is not None and asset_tier.upper() not in ASSET_TIERS:
        raise HTTPException(
            status_code=422, detail=f"asset_tier must be one of {ASSET_TIERS}"
        )
    if lifecycle_state is not None and lifecycle_state.lower() not in LIFECYCLE_STATES:
        raise HTTPException(
            status_code=422,
            detail=f"lifecycle_state must be one of {LIFECYCLE_STATES}",
        )
    if category is not None and category not in ASSET_CATEGORIES:
        raise HTTPException(
            status_code=422,
            detail=f"category must be one of {ASSET_CATEGORIES}",
        )

    filters = AssetFilters(
        device_category=device_category,
        asset_tier=asset_tier,
        owner_team=owner_team,
        has_critical_risks=has_critical_risks,
        custom_tag=custom_tag,
        search=search,
        lifecycle_state=lifecycle_state,
        category=category,
    )

    rows, total = await asset_service.list_assets_paginated(
        db, tenant_id, filters, page=page, limit=limit
    )

    pages = math.ceil(total / limit) if total else 0
    items = [
        AssetRead.from_orm_with_category(a, asset_service.categorize_asset(a))
        for a in rows
    ]
    return AssetListResponse(
        items=items, total=int(total), page=page, pages=pages, limit=limit
    )


# ─────────────────────────────────────────────────────────────────────────────
# Single-asset endpoints
# ─────────────────────────────────────────────────────────────────────────────


def _parse_uuid(asset_id: str) -> uuid.UUID:
    try:
        return uuid.UUID(asset_id)
    except (ValueError, TypeError):
        raise HTTPException(status_code=422, detail=f"Invalid asset id: {asset_id!r}")


@router.get("/{asset_id}", response_model=AssetWithRisksResponse)
async def get_asset(
    asset_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    tenant_id = TenantContext.get()
    aid = _parse_uuid(asset_id)
    bundle = await asset_service.get_asset_with_risks(db, tenant_id, aid)
    if bundle is None:
        raise HTTPException(status_code=404, detail="Asset not found")

    return AssetWithRisksResponse(
        asset=AssetRead.from_orm_with_category(
            bundle.asset, asset_service.categorize_asset(bundle.asset)
        ),
        open_risks=[_risk_to_slim(r) for r in bundle.open_risks],
        risk_count=bundle.risk_count,
        max_score=bundle.max_score,
        sources=bundle.sources,
    )


@router.patch("/{asset_id}", response_model=AssetRead)
async def update_asset(
    asset_id: str,
    data: AssetUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """Admin-only update of editable asset fields."""
    tenant_id = TenantContext.get()
    aid = _parse_uuid(asset_id)
    asset = (
        await db.execute(
            select(Asset).where(Asset.id == aid, Asset.tenant_id == tenant_id)
        )
    ).scalar_one_or_none()
    if asset is None:
        raise HTTPException(status_code=404, detail="Asset not found")

    # Validate enums on the update path so a 422 is returned cleanly.
    if data.business_criticality is not None and data.business_criticality not in BUSINESS_CRITICALITY_VALUES:
        raise HTTPException(
            status_code=422,
            detail=f"business_criticality must be one of {BUSINESS_CRITICALITY_VALUES}",
        )
    if data.asset_tier is not None and data.asset_tier.upper() not in ASSET_TIERS:
        raise HTTPException(
            status_code=422, detail=f"asset_tier must be one of {ASSET_TIERS}"
        )
    if data.lifecycle_state is not None and data.lifecycle_state.lower() not in LIFECYCLE_STATES:
        raise HTTPException(
            status_code=422,
            detail=f"lifecycle_state must be one of {LIFECYCLE_STATES}",
        )

    changes: dict = {}
    if data.custom_tags is not None:
        asset.custom_tags = data.custom_tags
        changes["custom_tags"] = data.custom_tags
    if data.owner_team is not None:
        asset.owner_team = data.owner_team
        changes["owner_team"] = data.owner_team
    if data.business_criticality is not None:
        asset.business_criticality = data.business_criticality
        changes["business_criticality"] = data.business_criticality
    if data.notes is not None:
        asset.notes = data.notes
        changes["notes"] = data.notes
    if data.asset_tier is not None:
        asset.asset_tier = data.asset_tier.upper()
        changes["asset_tier"] = asset.asset_tier
    if data.lifecycle_state is not None:
        asset.lifecycle_state = data.lifecycle_state.lower()
        changes["lifecycle_state"] = asset.lifecycle_state

    if not changes:
        raise HTTPException(status_code=422, detail="No fields supplied to update.")

    db.add(
        AuditLog(
            user_id=current_user.id,
            action="asset_updated",
            resource_type="asset",
            resource_id=asset.id,
            details={"changes": changes},
            tenant_id=tenant_id,
        )
    )
    await db.commit()
    await db.refresh(asset)
    return AssetRead.from_orm_with_category(asset, asset_service.categorize_asset(asset))


@router.get("/{asset_id}/risks", response_model=AssetRisksListResponse)
async def list_asset_risks(
    asset_id: str,
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=20, ge=1, le=200),
    status_filter: Optional[str] = Query(default="open", alias="status", max_length=20),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    tenant_id = TenantContext.get()
    aid = _parse_uuid(asset_id)

    asset = (
        await db.execute(
            select(Asset).where(Asset.id == aid, Asset.tenant_id == tenant_id)
        )
    ).scalar_one_or_none()
    if asset is None:
        raise HTTPException(status_code=404, detail="Asset not found")

    base = select(Risk).where(Risk.asset_id == aid, Risk.tenant_id == tenant_id)
    count_q = select(func.count()).select_from(Risk).where(
        Risk.asset_id == aid, Risk.tenant_id == tenant_id
    )
    if status_filter and status_filter.lower() != "all":
        base = base.where(Risk.status == status_filter.lower())
        count_q = count_q.where(Risk.status == status_filter.lower())

    total = (await db.execute(count_q)).scalar() or 0
    base = base.order_by(
        func.coalesce(Risk.composite_score, Risk.cvss_score).desc(),
        Risk.created_at.desc(),
    )
    base = base.offset((page - 1) * limit).limit(limit)
    rows = (await db.execute(base)).scalars().all()
    pages = math.ceil(total / limit) if total else 0
    return AssetRisksListResponse(
        items=[_risk_to_slim(r) for r in rows],
        total=int(total),
        page=page,
        pages=pages,
        limit=limit,
    )


@router.get("/{asset_id}/timeline", response_model=AssetTimelineResponse)
async def asset_timeline(
    asset_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    tenant_id = TenantContext.get()
    aid = _parse_uuid(asset_id)

    asset = (
        await db.execute(
            select(Asset).where(Asset.id == aid, Asset.tenant_id == tenant_id)
        )
    ).scalar_one_or_none()
    if asset is None:
        raise HTTPException(status_code=404, detail="Asset not found")

    events = await asset_service.get_asset_timeline(db, tenant_id, aid)
    return AssetTimelineResponse(
        items=[
            AssetTimelineEvent(
                event_type=e.event_type,
                timestamp=e.timestamp,
                summary=e.summary,
                risk_id=e.risk_id,
            )
            for e in events
        ],
        total=len(events),
    )
