from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class ComplianceNotification(BaseModel):
    topic: str = Field(..., description="The event topic (e.g., compliance.control.failed)")
    payload: dict[str, Any] = Field(..., description="The event payload")
    received_at: datetime = Field(..., description="When the notification was received")


class NotificationListResponse(BaseModel):
    items: list[ComplianceNotification]
    total: int
    tenant_id: str


class NotificationClearResponse(BaseModel):
    cleared: bool
    tenant_id: str
