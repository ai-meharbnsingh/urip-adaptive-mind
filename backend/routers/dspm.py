"""
DSPM router — Project_33a §13 LIVE (MVP scaffold).

Endpoints
---------
GET  /api/dspm/data-assets              — list discovered data stores
POST /api/dspm/data-assets              — create a data asset (manual seed)
GET  /api/dspm/sensitive-discoveries    — list sensitive-data hits
GET  /api/dspm/access-paths             — list (identity → asset) edges
POST /api/dspm/scan                     — trigger ingest from cloud_assets payload

All endpoints are gated on the DSPM module subscription (12th license module).
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
from backend.schemas.dspm import (
    DataAssetCreateRequest,
    DataAssetItem,
    DataAssetListResponse,
    AccessPathItem,
    AccessPathListResponse,
    ScanRequest,
    ScanResponse,
    SensitiveDiscoveryItem,
    SensitiveDiscoveryListResponse,
)
from backend.services.dspm import (
    create_data_asset,
    ingest_from_cloud_assets,
    list_access_paths,
    list_data_assets,
    list_sensitive_discoveries,
)

logger = logging.getLogger(__name__)

router = APIRouter(dependencies=[Depends(require_module("DSPM"))])


# --------------------------------------------------------------------------- #
@router.get("/data-assets", response_model=DataAssetListResponse)
async def get_data_assets(
    store_type: Optional[str] = Query(default=None),
    classification: Optional[str] = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
    current_user: Any = Depends(role_required("ciso")),
) -> DataAssetListResponse:
    tenant_id = TenantContext.get()
    try:
        rows = await list_data_assets(
            db, tenant_id,
            store_type=store_type,
            classification=classification,
            limit=limit,
            offset=offset,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    return DataAssetListResponse(
        items=[DataAssetItem.model_validate(r, from_attributes=True) for r in rows],
        total=len(rows),
        limit=limit,
        offset=offset,
    )


@router.post("/data-assets", response_model=DataAssetItem, status_code=201)
async def post_data_asset(
    payload: DataAssetCreateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: Any = Depends(role_required("ciso")),
) -> DataAssetItem:
    tenant_id = TenantContext.get()
    try:
        asset = await create_data_asset(
            db, tenant_id,
            store_type=payload.store_type,
            location=payload.location,
            data_classification=payload.data_classification,
            sensitive_data_types=payload.sensitive_data_types,
            owner=payload.owner,
            notes=payload.notes,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    await db.commit()
    await db.refresh(asset)
    return DataAssetItem.model_validate(asset, from_attributes=True)


@router.get("/sensitive-discoveries", response_model=SensitiveDiscoveryListResponse)
async def get_sensitive_discoveries(
    data_asset_id: Optional[uuid.UUID] = Query(default=None),
    severity: Optional[str] = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
    current_user: Any = Depends(role_required("ciso")),
) -> SensitiveDiscoveryListResponse:
    tenant_id = TenantContext.get()
    rows = await list_sensitive_discoveries(
        db, tenant_id,
        data_asset_id=data_asset_id,
        severity=severity,
        limit=limit,
        offset=offset,
    )
    return SensitiveDiscoveryListResponse(
        items=[SensitiveDiscoveryItem.model_validate(r, from_attributes=True) for r in rows],
        total=len(rows),
    )


@router.get("/access-paths", response_model=AccessPathListResponse)
async def get_access_paths(
    data_asset_id: Optional[uuid.UUID] = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
    current_user: Any = Depends(role_required("ciso")),
) -> AccessPathListResponse:
    tenant_id = TenantContext.get()
    rows = await list_access_paths(
        db, tenant_id,
        data_asset_id=data_asset_id,
        limit=limit,
        offset=offset,
    )
    return AccessPathListResponse(
        items=[AccessPathItem.model_validate(r, from_attributes=True) for r in rows],
        total=len(rows),
    )


@router.post("/scan", response_model=ScanResponse)
async def post_scan(
    payload: ScanRequest,
    db: AsyncSession = Depends(get_db),
    current_user: Any = Depends(role_required("ciso")),
) -> ScanResponse:
    """
    Manual / connector-driven ingest path.  Accepts a list of cloud assets
    (CSPM / collaboration shape) and seeds DataAsset rows.
    """
    tenant_id = TenantContext.get()
    rows = await ingest_from_cloud_assets(
        db, tenant_id,
        cloud_assets=[ca.model_dump() for ca in payload.cloud_assets],
        source=payload.source,
    )
    await db.commit()
    for r in rows:
        await db.refresh(r)
    return ScanResponse(
        ingested=len(rows),
        assets=[DataAssetItem.model_validate(r, from_attributes=True) for r in rows],
    )
