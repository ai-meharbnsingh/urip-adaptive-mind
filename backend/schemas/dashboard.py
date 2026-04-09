from datetime import datetime

from pydantic import BaseModel


class DashboardKPIs(BaseModel):
    total_open: int
    critical: int
    high: int
    medium: int
    low: int
    accepted: int
    sla_breaching: list[dict]


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

    class Config:
        from_attributes = True
