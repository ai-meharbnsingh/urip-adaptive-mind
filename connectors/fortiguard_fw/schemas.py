"""
Pydantic v2 models for Fortinet Fortiguard firewall connector.

RE-baseline:
- CEF event parsing result
- Blocked threats from REST API
"""

from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field


class CEFEvent(BaseModel):
    model_config = ConfigDict(extra="allow")

    signature_id: str
    name: str
    severity: int = 0
    extensions: dict[str, Any] = Field(default_factory=dict)


class FortiBlockedThreat(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: str
    srcip: Optional[str] = None
    dstip: Optional[str] = None
    action: Optional[str] = None
    severity: Optional[str] = None  # high|medium|low|critical


class FortiBlockedThreatsResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    results: list[dict[str, Any]] = Field(default_factory=list)

