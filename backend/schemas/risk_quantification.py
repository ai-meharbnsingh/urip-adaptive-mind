"""Risk Quantification (FAIR) schemas — Project_33a §13 (MVP scaffold)."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field


class AssessmentCreateRequest(BaseModel):
    risk_id: str = Field(..., min_length=1, max_length=64)
    risk_label: str = Field(..., min_length=1, max_length=255)
    loss_event_frequency: float = Field(..., ge=0)
    records_at_risk: int = Field(default=0, ge=0)
    extra_loss_usd: float = Field(default=0.0, ge=0)


class AssessmentItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    risk_id: str
    risk_label: str
    loss_event_frequency: float
    loss_magnitude_usd: float
    annual_loss_exposure_usd: float
    components: Optional[dict[str, Any]] = None
    computed_at: datetime


class AssumptionsItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    data_record_value_usd: float
    breach_response_cost_usd: float
    regulatory_fine_probability: float
    regulatory_fine_amount_usd: float
    brand_damage_estimate_usd: float
    notes: Optional[str] = None


class AssumptionsUpdateRequest(BaseModel):
    data_record_value_usd: Optional[float] = Field(default=None, ge=0)
    breach_response_cost_usd: Optional[float] = Field(default=None, ge=0)
    regulatory_fine_probability: Optional[float] = Field(default=None, ge=0, le=1)
    regulatory_fine_amount_usd: Optional[float] = Field(default=None, ge=0)
    brand_damage_estimate_usd: Optional[float] = Field(default=None, ge=0)
    notes: Optional[str] = None


class AggregateResponse(BaseModel):
    total_ale_usd: float
    risk_count: int
    top_risks: list[AssessmentItem]
