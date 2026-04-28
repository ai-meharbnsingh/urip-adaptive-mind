"""ZTNA Pydantic v2 schemas — Project_33a §13 (MVP scaffold)."""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from backend.models.ztna import DECISION_VALUES, POSTURE_REQUIREMENT_VALUES


class PolicyCreateRequest(BaseModel):
    policy_name: str = Field(..., min_length=1, max_length=255)
    target_app: str = Field(..., min_length=1, max_length=255)
    identity_required: bool = True
    mfa_required: bool = True
    device_posture_required: Optional[list[str]] = None
    source_provider: Optional[str] = None

    def model_post_init(self, __context) -> None:  # type: ignore[override]
        if self.device_posture_required:
            bad = [v for v in self.device_posture_required if v not in POSTURE_REQUIREMENT_VALUES]
            if bad:
                raise ValueError(
                    f"device_posture_required must be subset of {sorted(POSTURE_REQUIREMENT_VALUES)}"
                )


class PolicyItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tenant_id: uuid.UUID
    policy_name: str
    target_app: str
    identity_required: bool
    mfa_required: bool
    device_posture_required: Optional[list[str]] = None
    source_provider: Optional[str] = None
    last_evaluated_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime


class PolicyListResponse(BaseModel):
    items: list[PolicyItem]
    total: int


class AccessDecisionItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tenant_id: uuid.UUID
    policy_id: Optional[uuid.UUID] = None
    user_identity: str
    target_app: str
    decision: str
    reason: Optional[str] = None
    source_ip: Optional[str] = None
    decided_at: datetime


class AccessDecisionListResponse(BaseModel):
    items: list[AccessDecisionItem]
    total: int


class PostureViolationItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tenant_id: uuid.UUID
    user_identity: str
    device_id: Optional[str] = None
    failed_requirement: str
    severity: str
    detected_at: datetime
    remediated: bool


class PostureViolationListResponse(BaseModel):
    items: list[PostureViolationItem]
    total: int
