"""
Pydantic v2 models for Email Security connector.

Covers:
- Google Workspace Alert Center alert
- Microsoft 365 Defender alert via Graph Security API
- Common normalized shape
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field


class GoogleWorkspaceAlert(BaseModel):
    """Google Workspace Alert Center API alert."""

    model_config = ConfigDict(extra="allow")

    alertId: str
    createTime: Optional[datetime] = None
    customerId: Optional[str] = None
    type: Optional[str] = None
    source: Optional[str] = None
    severity: Optional[str] = None
    data: dict[str, Any] = Field(default_factory=dict)


class M365DefenderAlert(BaseModel):
    """Microsoft Graph Security API alert."""

    model_config = ConfigDict(extra="allow")

    id: str
    title: Optional[str] = None
    category: Optional[str] = None
    severity: Optional[str] = None
    createdDateTime: Optional[datetime] = None
    description: Optional[str] = None
    recommendedActions: Optional[str] = None
    azureTenantId: Optional[str] = None


class EmailSecurityCommon(BaseModel):
    """Common normalized email security finding."""

    model_config = ConfigDict(extra="allow")

    provider: str
    alert_id: str
    alert_type: Optional[str] = None
    severity: str = "medium"
    description: Optional[str] = None
    created_at: Optional[datetime] = None
    recommended_action: Optional[str] = None
    raw: dict[str, Any] = Field(default_factory=dict)
