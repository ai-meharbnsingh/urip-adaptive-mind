"""
Pydantic v2 response schemas for the /api/risk-index router.

These shapes mirror the dataclasses defined in
``backend.services.risk_index_service`` but are the public API contract
the frontend consumes.  Keeping them in a dedicated schemas module avoids
leaking SQLAlchemy / dataclass internals into the OpenAPI spec.
"""
from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

LevelLiteral = Literal["low", "medium", "high", "critical"]


class RiskIndexOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    score: float = Field(..., description="0-100 cyber risk index for this tenant")
    level: LevelLiteral
    color_code: str = Field(..., description="green | yellow | orange | red")


class SubindexOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    score: float
    level: LevelLiteral
    contributing_count: int


class SubindexesOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    exposure: SubindexOut
    attack: SubindexOut
    security_config: SubindexOut


class DomainBucketOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    name: str
    total: int
    critical_count: int
    high_count: int
    mean_score: float
    level: LevelLiteral


class DomainBreakdownOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    devices: DomainBucketOut
    internet_facing: DomainBucketOut
    accounts: DomainBucketOut
    applications: DomainBucketOut
    cloud_assets: DomainBucketOut


class RiskIndexDashboardOut(BaseModel):
    """Top-strip dashboard payload — single GET returns the full picture."""

    score: float
    level: LevelLiteral
    color_code: str
    subindexes: SubindexesOut
    domains: DomainBreakdownOut


class TopRiskOut(BaseModel):
    """One row in the drill-down lists (sub-index / domain detail endpoints)."""

    risk_id: str
    finding: str
    source: str
    severity: str
    composite_score: Optional[float] = None
    asset: str
    domain: Optional[str] = None


class SubindexDetailOut(BaseModel):
    """GET /api/risk-index/subindexes/{name} response."""

    name: str
    score: float
    level: LevelLiteral
    contributing_count: int
    top_risks: list[TopRiskOut]


class DomainDetailOut(BaseModel):
    """GET /api/risk-index/domains/{name} response."""

    name: str
    total: int
    critical_count: int
    high_count: int
    mean_score: float
    level: LevelLiteral
    top_risks: list[TopRiskOut]


class RiskIndexTrendPointOut(BaseModel):
    """One historical snapshot row (subset of RiskScoreSummary)."""

    snapshot_at: Optional[str] = None
    index_0_100: Optional[float] = None
    level: Optional[str] = None
    subindex_exposure: Optional[float] = None
    subindex_attack: Optional[float] = None
    subindex_security_config: Optional[float] = None
    domain_devices_count: Optional[int] = None
    domain_internet_facing_count: Optional[int] = None
    domain_accounts_count: Optional[int] = None
    domain_applications_count: Optional[int] = None
    domain_cloud_assets_count: Optional[int] = None
