"""
Pydantic v2 models for ManageEngine ServiceDesk Plus REST API v3 responses.

Covers:
- Ticket (request) records from /api/v3/requests
- OAuth token response from /api/v3/token
"""

from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field


class ManageEngineSdpTicket(BaseModel):
    """Represents a ServiceDesk Plus ticket (request)."""

    model_config = ConfigDict(extra="allow")

    id: str
    subject: Optional[str] = None
    description: Optional[str] = None
    priority: Optional[str] = None  # Critical | High | Medium | Low
    category: Optional[str] = None
    requester: Optional[str] = None
    status: Optional[str] = None
    created_time: Optional[str] = None


class ManageEngineSdpRequestsResponse(BaseModel):
    """Top-level response from GET /api/v3/requests."""

    model_config = ConfigDict(extra="allow")

    requests: list[ManageEngineSdpTicket] = Field(default_factory=list)


class ManageEngineSdpOAuthToken(BaseModel):
    """OAuth token response from /api/v3/token."""

    model_config = ConfigDict(extra="allow")

    access_token: str
    token_type: str = "Bearer"
    expires_in: int = 3600


class ManageEngineSdpCreateTicketResponse(BaseModel):
    """Response from POST /api/v3/requests."""

    model_config = ConfigDict(extra="allow")

    request: dict[str, Any] = Field(default_factory=dict)
