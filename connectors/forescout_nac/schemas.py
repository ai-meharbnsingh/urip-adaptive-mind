"""
Pydantic v2 models for the Network Access Control connector (Forescout + Cisco ISE).

RE-baseline minimal shapes:
- Forescout: OAuth2 token, alerts, events, devices
- Cisco ISE: ERS endpoint search result
"""

from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field


class ForescoutOAuthToken(BaseModel):
    model_config = ConfigDict(extra="allow")

    access_token: str
    expires_in: int = 3600
    token_type: Optional[str] = "Bearer"


class ForescoutAlert(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: str
    type: str
    severity: Optional[str] = None
    device: Optional[str] = None


class ForescoutEvent(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: str
    event_type: str
    severity: Optional[str] = None
    device: Optional[str] = None


class ForescoutDevice(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: str
    mac: Optional[str] = None
    classification: Optional[str] = None


class ForescoutListResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    data: list[dict[str, Any]] = Field(default_factory=list)


class CiscoISEEndpointSearchResult(BaseModel):
    model_config = ConfigDict(extra="allow")

    SearchResult: dict[str, Any] = Field(default_factory=dict)

