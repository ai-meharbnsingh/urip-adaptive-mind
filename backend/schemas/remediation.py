from datetime import date, datetime

from pydantic import BaseModel


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

    class Config:
        from_attributes = True
