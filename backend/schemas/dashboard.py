from datetime import datetime

from pydantic import BaseModel, ConfigDict


class SlaBreachItem(BaseModel):
    risk_id: str
    finding: str
    severity: str
    sla_deadline: str


class DashboardKPIs(BaseModel):
    total_open: int
    critical: int
    high: int
    medium: int
    low: int
    accepted: int
    actively_exploited: int = 0
    ioc_matches: int = 0
    dark_web_alerts: int = 0
    sla_breaching: list[SlaBreachItem]


class ChartData(BaseModel):
    labels: list[str]
    data: list[int]


class TrendDataset(BaseModel):
    label: str
    data: list[int]


class TrendData(BaseModel):
    labels: list[str]
    datasets: list[TrendDataset]


class AlertItem(BaseModel):
    id: str
    risk_id: str
    finding: str
    source: str
    cvss_score: float
    severity: str
    status: str
    asset: str

    model_config = ConfigDict(from_attributes=True)
