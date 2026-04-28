"""
Pydantic v2 models for CyberArk PAM connector.

RE-baseline:
- Auth token is a plain text string.
- Log/event feeds are modeled as a list of events under `data`.
"""

from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field


class CyberArkEvent(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: str
    event_type: str
    severity: Optional[str] = None  # critical|high|medium|low
    user: Optional[str] = None
    asset: Optional[str] = None
    message: Optional[str] = None


class CyberArkEventsResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    data: list[dict[str, Any]] = Field(default_factory=list)

