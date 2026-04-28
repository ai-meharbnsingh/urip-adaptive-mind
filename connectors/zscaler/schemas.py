"""
Pydantic v2 models for Zscaler ZIA / ZTA / CASB API responses.

Covers:
- Web threat records from /api/v1/threatIntel/threats
- Shadow SaaS app records from /api/v1/casb/saasApps
- Admin audit logs from /api/v1/users/admin/auditLogs
"""

from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field


class ZscalerWebThreat(BaseModel):
    """Represents a web threat detected by Zscaler."""

    model_config = ConfigDict(extra="allow")

    id: str
    threat_name: Optional[str] = None
    url: Optional[str] = None
    severity: str = "medium"  # critical | high | medium | low
    category: str = "web_threat"
    device: Optional[str] = None
    timestamp: Optional[str] = None
    action: Optional[str] = None


class ZscalerShadowSaaS(BaseModel):
    """Represents an unsanctioned SaaS application discovered by CASB."""

    model_config = ConfigDict(extra="allow")

    id: str
    name: Optional[str] = None
    category: Optional[str] = None
    risk_score: Optional[int] = None
    users: int = 0
    sanctioned: bool = False


class ZscalerAdminAuditLog(BaseModel):
    """Represents an admin audit log entry."""

    model_config = ConfigDict(extra="allow")

    id: str
    admin_user: Optional[str] = None
    action: Optional[str] = None
    resource: Optional[str] = None
    severity: str = "medium"
    timestamp: Optional[str] = None


class ZscalerThreatsResponse(BaseModel):
    """Top-level response from GET /threatIntel/threats."""

    model_config = ConfigDict(extra="allow")

    threats: list[ZscalerWebThreat] = Field(default_factory=list)


class ZscalerSaasAppsResponse(BaseModel):
    """Top-level response from GET /casb/saasApps."""

    model_config = ConfigDict(extra="allow")

    saasApps: list[ZscalerShadowSaaS] = Field(default_factory=list)


class ZscalerAuditLogsResponse(BaseModel):
    """Top-level response from GET /users/admin/auditLogs."""

    model_config = ConfigDict(extra="allow")

    auditLogs: list[ZscalerAdminAuditLog] = Field(default_factory=list)
