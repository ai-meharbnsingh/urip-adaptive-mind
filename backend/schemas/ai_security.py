"""AI Security Pydantic v2 schemas — Project_33a §13 (MVP scaffold)."""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field

from backend.models.ai_security import GOVERNANCE_FRAMEWORKS, PROVIDER_VALUES


class AIModelCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    provider: str
    purpose: Optional[str] = None
    training_data_summary: Optional[str] = None
    deployment_endpoints: Optional[list[str]] = None
    risk_level: str = Field(default="medium")

    def model_post_init(self, __context) -> None:  # type: ignore[override]
        if self.provider not in PROVIDER_VALUES:
            raise ValueError(f"provider must be one of {sorted(PROVIDER_VALUES)}")
        if self.risk_level not in {"critical", "high", "medium", "low"}:
            raise ValueError("risk_level must be one of critical/high/medium/low")


class AIModelItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tenant_id: uuid.UUID
    name: str
    provider: str
    purpose: Optional[str] = None
    training_data_summary: Optional[str] = None
    deployment_endpoints: Optional[list[str]] = None
    risk_level: str
    last_audited_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime


class AIModelListResponse(BaseModel):
    items: list[AIModelItem]
    total: int


# --------------------------------------------------------------------------- #
class PromptInjectionUploadRequest(BaseModel):
    prompt_excerpt: str = Field(..., min_length=1, max_length=4000)
    ai_model_id: Optional[uuid.UUID] = None
    detection_source: str = Field(default="manual_upload")
    severity: str = Field(default="medium")
    blocked: bool = False
    metadata: Optional[dict[str, Any]] = None


class PromptInjectionItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tenant_id: uuid.UUID
    ai_model_id: Optional[uuid.UUID] = None
    prompt_excerpt: str
    detection_source: str
    severity: str
    blocked: bool
    detected_at: datetime
    metadata_json: Optional[dict[str, Any]] = None


class PromptInjectionListResponse(BaseModel):
    items: list[PromptInjectionItem]
    total: int


# --------------------------------------------------------------------------- #
class GovernanceAssessmentItem(BaseModel):
    model_id: str
    model_name: Optional[str]
    framework: str
    score: int
    assessed_at: datetime


class GovernanceStatusResponse(BaseModel):
    total_models: int
    framework_averages: dict[str, Optional[float]]
    per_model_assessments: list[GovernanceAssessmentItem]
