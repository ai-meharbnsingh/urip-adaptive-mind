from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


class RiskSummarySnapshot(BaseModel):
    id: str
    tenant_id: str
    snapshot_at: Optional[datetime]
    total_risks: int
    critical_count: int
    high_count: int
    medium_count: int
    low_count: int
    info_count: int
    exploit_active_count: int
    kev_active_count: int
    mean_ttr_hours: Optional[float]
    mean_composite_score: Optional[float]
    top_sources: list[dict[str, Any]] = Field(default_factory=list)
    module_breakdown: dict[str, Any] = Field(default_factory=dict)
    created_at: Optional[datetime]


class RiskSummaryTrendResponse(BaseModel):
    items: list[RiskSummarySnapshot]
    total: int
