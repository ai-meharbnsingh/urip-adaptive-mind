from datetime import datetime

from pydantic import BaseModel, ConfigDict


class AcceptanceCreate(BaseModel):
    risk_id: str
    justification: str
    compensating_controls: list[str] | None = None
    residual_risk: str | None = None


class AcceptanceAction(BaseModel):
    reason: str | None = None


class AcceptanceRead(BaseModel):
    id: str
    risk_id: str
    requested_by: str
    justification: str
    compensating_controls: list | dict | None = None
    residual_risk: str | None = None
    recommendation: str | None = None
    status: str
    reviewed_by: str | None = None
    review_date: datetime | None = None
    review_period_days: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AcceptanceRiskDetail(BaseModel):
    risk_id: str | None = None
    finding: str | None = None
    cvss_score: float | None = None
    severity: str | None = None
    asset: str | None = None
    domain: str | None = None


class AcceptanceListItem(AcceptanceRead):
    risk_detail: AcceptanceRiskDetail | None = None
    requester_name: str | None = None
    requester_team: str | None = None


class AcceptanceActionResponse(BaseModel):
    status: str
    acceptance_id: str
