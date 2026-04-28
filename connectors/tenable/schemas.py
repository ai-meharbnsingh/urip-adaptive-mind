"""
Pydantic v2 models for Tenable.io API responses.

Covers:
- Asset records from /workbenches/assets
- Vulnerability records from /workbenches/assets/{uuid}/vulnerabilities
"""

from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field


class TenableAsset(BaseModel):
    """Represents a Tenable asset (host)."""

    model_config = ConfigDict(extra="allow")

    id: str
    uuid: Optional[str] = None
    hostname: Optional[str] = None
    ipv4: list[str] = Field(default_factory=list)
    operating_system: list[str] = Field(default_factory=list)
    fqdn: Optional[str] = None
    mac_address: Optional[str] = None
    agent_uuid: Optional[str] = None


class TenableVulnerability(BaseModel):
    """Represents a vulnerability plugin instance on an asset."""

    model_config = ConfigDict(extra="allow")

    plugin_id: int
    plugin_name: str
    severity: int = 0  # 0=info, 1=low, 2=medium, 3=high, 4=critical
    vulnerability_state: Optional[str] = None
    cvss_base_score: Optional[float] = None
    cvss3_base_score: Optional[float] = None
    cvss3_temporal_score: Optional[float] = None
    vpr_score: Optional[float] = None
    cve: list[str] = Field(default_factory=list)
    count: int = 1
    asset: Optional[TenableAsset] = None
    synopsis: Optional[str] = None
    solution: Optional[str] = None
    see_also: list[str] = Field(default_factory=list)
    risk_factor: Optional[str] = None


class TenableVulnerabilitiesResponse(BaseModel):
    """Response wrapper for vulnerability listing endpoints."""

    model_config = ConfigDict(extra="allow")

    vulnerabilities: list[TenableVulnerability] = Field(default_factory=list)
    total_vulnerability_count: int = 0
    total_asset_count: int = 0


class TenableAssetsResponse(BaseModel):
    """Response wrapper for asset listing endpoints."""

    model_config = ConfigDict(extra="allow")

    assets: list[TenableAsset] = Field(default_factory=list)
