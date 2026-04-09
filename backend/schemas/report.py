from pydantic import BaseModel


class ReportRequest(BaseModel):
    report_type: str  # executive, ciso, board
    format: str = "pdf"  # pdf, excel


class CertInAdvisory(BaseModel):
    id: str
    advisory_id: str
    title: str
    published_date: str
    severity: str
    response_status: str

    class Config:
        from_attributes = True
