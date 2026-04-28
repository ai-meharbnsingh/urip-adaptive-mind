"""Attack path schemas — Project_33a §13 (MVP scaffold)."""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


class CriticalPathItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tenant_id: uuid.UUID
    source_node_id: uuid.UUID
    target_node_id: uuid.UUID
    hop_count: int
    risk_score: float
    is_critical: bool
    path_node_ids: list[str]
    mitre_chain: Optional[list[str]] = None
    computed_at: datetime


class CriticalPathListResponse(BaseModel):
    items: list[CriticalPathItem]
    total: int


class PathNodeView(BaseModel):
    id: str
    label: str
    node_type: str
    is_internet_exposed: bool
    asset_tier: Optional[int] = None


class PathDetailsResponse(BaseModel):
    id: str
    hop_count: int
    risk_score: float
    is_critical: bool
    mitre_chain: Optional[list[str]] = None
    computed_at: datetime
    nodes: list[PathNodeView]


class RecomputeResponse(BaseModel):
    status: str
    paths_computed: int
    critical_paths: int
