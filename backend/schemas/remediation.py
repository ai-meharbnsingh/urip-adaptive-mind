from datetime import date, datetime

from pydantic import BaseModel, ConfigDict


class RemediationCreate(BaseModel):
    risk_id: str
    title: str
    description: str | None = None
    assigned_to: str | None = None
    priority: str = "medium"
    due_date: date | None = None
    jira_key: str | None = None


class RemediationUpdate(BaseModel):
    status: str | None = None
    assigned_to: str | None = None
    jira_key: str | None = None
    due_date: date | None = None


class RemediationRead(BaseModel):
    id: str
    risk_id: str
    title: str
    description: str | None = None
    assigned_to: str | None = None
    status: str
    priority: str
    due_date: date | None = None
    jira_key: str | None = None
    completed_at: datetime | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class RemediationRiskDetail(BaseModel):
    risk_id: str | None = None
    finding: str | None = None
    severity: str | None = None
    asset: str | None = None
    sla_deadline: str | None = None


class RemediationListItem(RemediationRead):
    risk_detail: RemediationRiskDetail | None = None


class RemediationListResponse(BaseModel):
    items: list[RemediationListItem]
    total: int
    page: int
    pages: int
