from datetime import datetime

from pydantic import BaseModel


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

    class Config:
        from_attributes = True
