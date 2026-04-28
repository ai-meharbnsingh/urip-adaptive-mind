"""
backend/schemas/asset.py — Pydantic v2 response/request models for the
Asset REST API.
"""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from backend.models.asset import (
    ASSET_CATEGORIES,
    ASSET_TIERS,
    BUSINESS_CRITICALITY_VALUES,
    DEVICE_CATEGORIES,
    LIFECYCLE_STATES,
    Asset,
)


# Re-export for router-level Query() Literal typing.
DEVICE_CATEGORIES_LIT = DEVICE_CATEGORIES
ASSET_TIERS_LIT = ASSET_TIERS
ASSET_CATEGORIES_LIT = ASSET_CATEGORIES
LIFECYCLE_STATES_LIT = LIFECYCLE_STATES
BUSINESS_CRITICALITY_LIT = BUSINESS_CRITICALITY_VALUES


class AssetRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    tenant_id: str
    fingerprint_key: str
    # Identification
    hostname: str | None = None
    internal_ip: str | None = None
    external_ip: str | None = None
    mac_address: str | None = None
    # Classification
    device_type: str | None = None
    device_category: str | None = None
    os_name: str | None = None
    os_version: str | None = None
    # Organisational
    endpoint_group: str | None = None
    asset_group: str | None = None
    last_user: str | None = None
    owner_team: str | None = None
    # Risk
    asset_tier: str | None = None
    business_criticality: str | None = None
    asset_risk_score: float | None = None
    # Lifecycle
    lifecycle_state: str
    discovered_at: datetime
    last_seen: datetime
    source_connectors: list[str] = Field(default_factory=list)
    # Custom + audit
    custom_tags: dict = Field(default_factory=dict)
    notes: str | None = None
    created_at: datetime
    updated_at: datetime
    # Derived (populated by routers via asset_service.categorize_asset)
    category: str | None = None

    @classmethod
    def from_orm_with_category(cls, asset: Asset, category: str) -> "AssetRead":
        return cls(
            id=str(asset.id),
            tenant_id=str(asset.tenant_id),
            fingerprint_key=asset.fingerprint_key,
            hostname=asset.hostname,
            internal_ip=asset.internal_ip,
            external_ip=asset.external_ip,
            mac_address=asset.mac_address,
            device_type=asset.device_type,
            device_category=asset.device_category,
            os_name=asset.os_name,
            os_version=asset.os_version,
            endpoint_group=asset.endpoint_group,
            asset_group=asset.asset_group,
            last_user=asset.last_user,
            owner_team=asset.owner_team,
            asset_tier=asset.asset_tier,
            business_criticality=asset.business_criticality,
            asset_risk_score=(
                float(asset.asset_risk_score)
                if asset.asset_risk_score is not None
                else None
            ),
            lifecycle_state=asset.lifecycle_state,
            discovered_at=asset.discovered_at,
            last_seen=asset.last_seen,
            source_connectors=list(asset.source_connectors or []),
            custom_tags=dict(asset.custom_tags or {}),
            notes=asset.notes,
            created_at=asset.created_at,
            updated_at=asset.updated_at,
            category=category,
        )


class AssetListResponse(BaseModel):
    items: list[AssetRead]
    total: int
    page: int
    pages: int
    limit: int


class AssetUpdate(BaseModel):
    """Fields editable from the UI (PATCH /api/assets/{id})."""

    custom_tags: dict | None = None
    owner_team: str | None = Field(default=None, max_length=100)
    business_criticality: str | None = None
    notes: str | None = None
    asset_tier: str | None = None
    lifecycle_state: str | None = None


class AssetRiskRead(BaseModel):
    """Slim Risk projection for /api/assets/{id}/risks and /detail."""

    id: str
    risk_id: str
    finding: str
    description: str | None = None
    source: str
    domain: str
    severity: str
    cvss_score: float
    composite_score: float | None = None
    status: str
    created_at: datetime
    updated_at: datetime


class AssetWithRisksResponse(BaseModel):
    asset: AssetRead
    open_risks: list[AssetRiskRead]
    risk_count: int
    max_score: float
    sources: list[str]


class AssetRisksListResponse(BaseModel):
    items: list[AssetRiskRead]
    total: int
    page: int
    pages: int
    limit: int


class AssetCategoryCounts(BaseModel):
    counts: dict[str, int]
    total: int


class AssetTimelineEvent(BaseModel):
    event_type: str
    timestamp: datetime
    summary: str
    risk_id: str | None = None


class AssetTimelineResponse(BaseModel):
    items: list[AssetTimelineEvent]
    total: int
