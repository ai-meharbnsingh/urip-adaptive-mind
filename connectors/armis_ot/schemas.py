"""
Pydantic v2 models for the Armis OT connector.

These schemas are intentionally minimal RE-baseline shapes to support:
- OT asset inventory
- Vulnerabilities
- Risk events
"""

from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field


class ArmisAsset(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: str
    name: Optional[str] = None
    site: Optional[str] = None
    criticality: Optional[int] = None  # 1..5 (vendor-specific)
    ip: Optional[str] = None
    mac: Optional[str] = None
    vendor: Optional[str] = None
    model: Optional[str] = None


class ArmisVulnerability(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: str
    asset_id: str
    title: str
    cvss: Optional[float] = None
    cve: Optional[str] = None
    severity: Optional[str] = None  # critical|high|medium|low


class ArmisRiskEvent(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: str
    asset_id: str
    event_type: str
    risk_level: Optional[str] = None  # critical|high|medium|low
    message: Optional[str] = None


class ArmisListResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    data: list[dict[str, Any]] = Field(default_factory=list)

