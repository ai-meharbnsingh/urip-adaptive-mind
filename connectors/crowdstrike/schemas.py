"""
Pydantic v2 models for CrowdStrike Falcon API responses.

Covers:
- OAuth2 token response (/oauth2/token)
- Falcon Spotlight (VM)            — /spotlight/queries|entities/vulnerabilities/v{1,2}
- Falcon Surface (EASM)            — /falcon-surface/queries/external-assets/v1
- Falcon CNAPP (cloud findings)    — /cnapp/queries/findings/v1

All models use ``extra='allow'`` so the connector keeps working when CrowdStrike
adds new fields server-side.
"""

from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field


# ─────────────────────────────────────────────────────────────────────────────
# OAuth
# ─────────────────────────────────────────────────────────────────────────────


class OAuthTokenResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    access_token: str
    token_type: str = "bearer"
    expires_in: int = 1799


# ─────────────────────────────────────────────────────────────────────────────
# Falcon Spotlight (VM) — vulnerability records
# ─────────────────────────────────────────────────────────────────────────────


class SpotlightCVE(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: Optional[str] = None
    exploit_status: Optional[int] = None
    exprt_rating: Optional[str] = None
    description: Optional[str] = None


class SpotlightHostInfo(BaseModel):
    model_config = ConfigDict(extra="allow")

    hostname: Optional[str] = None
    local_ip: Optional[str] = None
    agent_id: Optional[str] = None
    tags: list[str] = Field(default_factory=list)


class SpotlightVulnerability(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: str
    cve: SpotlightCVE = Field(default_factory=SpotlightCVE)
    host_info: SpotlightHostInfo = Field(default_factory=SpotlightHostInfo)
    exprt_score: Optional[int] = None


class SpotlightPagination(BaseModel):
    model_config = ConfigDict(extra="allow")

    offset: Optional[str] = ""
    total: int = 0


class SpotlightQueryMeta(BaseModel):
    model_config = ConfigDict(extra="allow")

    pagination: SpotlightPagination = Field(default_factory=SpotlightPagination)


class SpotlightQueryResponse(BaseModel):
    """GET /spotlight/queries/vulnerabilities/v1 returns IDs only."""

    model_config = ConfigDict(extra="allow")

    resources: list[str] = Field(default_factory=list)
    meta: SpotlightQueryMeta = Field(default_factory=SpotlightQueryMeta)


class SpotlightEntitiesResponse(BaseModel):
    """GET /spotlight/entities/vulnerabilities/v2 returns full records."""

    model_config = ConfigDict(extra="allow")

    resources: list[SpotlightVulnerability] = Field(default_factory=list)


# ─────────────────────────────────────────────────────────────────────────────
# Falcon Surface (EASM)
# ─────────────────────────────────────────────────────────────────────────────


class EASMAsset(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: str
    asset_value: Optional[str] = None
    asset_type: Optional[str] = None
    risk_severity: Optional[str] = None
    exposure_type: Optional[str] = None
    first_seen: Optional[str] = None
    tags: list[str] = Field(default_factory=list)
    exprt_score: Optional[int] = None


class EASMResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    resources: list[EASMAsset] = Field(default_factory=list)
    meta: SpotlightQueryMeta = Field(default_factory=SpotlightQueryMeta)


# ─────────────────────────────────────────────────────────────────────────────
# Falcon CNAPP (cloud)
# ─────────────────────────────────────────────────────────────────────────────


class CNAPPFinding(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: str
    title: Optional[str] = None
    severity: Optional[str] = None
    exprt_score: Optional[int] = None
    cloud_provider: Optional[str] = None
    resource_id: Optional[str] = None
    policy_id: Optional[str] = None
    description: Optional[str] = None


class CNAPPResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    resources: list[CNAPPFinding] = Field(default_factory=list)
    meta: SpotlightQueryMeta = Field(default_factory=SpotlightQueryMeta)
