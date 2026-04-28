"""
DSPM Pydantic v2 schemas — Project_33a §13 LIVE (MVP scaffold).
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from backend.models.dspm import DATA_CLASSIFICATION_VALUES, STORE_TYPE_VALUES


# --------------------------------------------------------------------------- #
class DataAssetCreateRequest(BaseModel):
    store_type: str = Field(..., description="One of: database/file_system/object_storage/saas")
    location: str = Field(..., min_length=1, max_length=500)
    data_classification: str = Field(default="internal")
    sensitive_data_types: Optional[list[str]] = None
    owner: Optional[str] = Field(default=None, max_length=255)
    notes: Optional[str] = None

    def model_post_init(self, __context) -> None:  # type: ignore[override]
        if self.store_type not in STORE_TYPE_VALUES:
            raise ValueError(
                f"store_type must be one of {sorted(STORE_TYPE_VALUES)}"
            )
        if self.data_classification not in DATA_CLASSIFICATION_VALUES:
            raise ValueError(
                f"data_classification must be one of {sorted(DATA_CLASSIFICATION_VALUES)}"
            )


class DataAssetItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tenant_id: uuid.UUID
    store_type: str
    location: str
    data_classification: str
    sensitive_data_types: Optional[list[str]] = None
    owner: Optional[str] = None
    last_scanned_at: Optional[datetime] = None
    notes: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class DataAssetListResponse(BaseModel):
    items: list[DataAssetItem]
    total: int
    limit: int
    offset: int


# --------------------------------------------------------------------------- #
class SensitiveDiscoveryItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tenant_id: uuid.UUID
    data_asset_id: uuid.UUID
    sensitive_type: str
    severity: str
    sample_count: Optional[int] = None
    evidence: Optional[dict] = None
    detected_at: datetime


class SensitiveDiscoveryListResponse(BaseModel):
    items: list[SensitiveDiscoveryItem]
    total: int


# --------------------------------------------------------------------------- #
class AccessPathItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tenant_id: uuid.UUID
    data_asset_id: uuid.UUID
    identity: str
    identity_type: str
    access_type: str
    granted_via: Optional[str] = None
    last_evaluated_at: datetime


class AccessPathListResponse(BaseModel):
    items: list[AccessPathItem]
    total: int


# --------------------------------------------------------------------------- #
class CloudAssetIngestItem(BaseModel):
    """Loose shape — connector authors fill in resource_type + name."""
    resource_type: str
    name: str
    owner: Optional[str] = None
    data_classification: Optional[str] = None
    sensitive_data_types: Optional[list[str]] = None


class ScanRequest(BaseModel):
    cloud_assets: list[CloudAssetIngestItem]
    source: str = Field(default="cspm", description="cspm | collaboration")


class ScanResponse(BaseModel):
    ingested: int
    assets: list[DataAssetItem]
