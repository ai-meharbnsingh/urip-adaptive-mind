from pydantic import BaseModel, ConfigDict, field_validator


class ReportRequest(BaseModel):
    report_type: str  # executive, ciso, board
    format: str = "pdf"  # pdf, excel

    @field_validator("report_type")
    @classmethod
    def _validate_type(cls, v: str) -> str:
        v = v.lower()
        if v not in {"executive", "ciso", "board"}:
            raise ValueError("report_type must be one of executive|ciso|board")
        return v

    @field_validator("format")
    @classmethod
    def _validate_format(cls, v: str) -> str:
        v = v.lower()
        if v not in {"pdf", "excel"}:
            raise ValueError("format must be one of pdf|excel")
        return v


class CertInAdvisory(BaseModel):
    id: str
    advisory_id: str
    title: str
    published_date: str
    severity: str
    response_status: str

    model_config = ConfigDict(from_attributes=True)


class ScheduledReport(BaseModel):
    name: str
    frequency: str
    recipients: list[str]
    next_run: str
    status: str
