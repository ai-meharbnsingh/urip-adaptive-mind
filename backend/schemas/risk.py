from datetime import datetime

from pydantic import BaseModel


class RiskCreate(BaseModel):
    finding: str
    description: str | None = None
    source: str
    domain: str
    cvss_score: float
    severity: str
    asset: str
    owner_team: str
    cve_id: str | None = None
    epss_score: float | None = None
    in_kev_catalog: bool = False
    exploit_status: str | None = None
    asset_tier: int | None = None
    composite_score: float | None = None


class RiskUpdate(BaseModel):
    status: str | None = None
    owner_team: str | None = None
    assigned_to: str | None = None
    jira_ticket: str | None = None


class RiskRead(BaseModel):
    id: str
    risk_id: str
    finding: str
    description: str | None = None
    source: str
    domain: str
    cvss_score: float
    severity: str
    asset: str
    owner_team: str
    assigned_to: str | None = None
    status: str
    sla_deadline: datetime
    jira_ticket: str | None = None
    cve_id: str | None = None
    epss_score: float | None = None
    epss_percentile: float | None = None
    in_kev_catalog: bool = False
    exploit_status: str | None = None
    asset_tier: int | None = None
    composite_score: float | None = None
    apt_groups: list[dict] | None = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class RiskListResponse(BaseModel):
    items: list[RiskRead]
    total: int
    page: int
    pages: int


class AssignRequest(BaseModel):
    user_id: str
