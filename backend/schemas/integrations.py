from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


class IntegrationHealthResponse(BaseModel):
    status: str = Field(..., description="Connected | Not configured | Error")
    connector: str
    last_check: Optional[datetime] = None
    health_status: Optional[str] = None
    detail: Optional[str] = None
