"""
Pydantic v2 models for Netskope CASB + DLP API responses.

Covers:
- DLP incidents from /api/v2/incidents/dlp
- Cloud threats from /api/v2/incidents/threats
- Anomalies from /api/v2/incidents/anomalies
"""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class NetskopeDlpIncident(BaseModel):
    """Represents a DLP policy violation incident."""

    model_config = ConfigDict(extra="allow")

    id: str
    incident_name: Optional[str] = None
    severity: str = "medium"
    user: Optional[str] = None
    app: Optional[str] = None
    timestamp: Optional[str] = None
    policy: Optional[str] = None


class NetskopeThreat(BaseModel):
    """Represents a cloud threat detection."""

    model_config = ConfigDict(extra="allow")

    id: str
    threat_name: Optional[str] = None
    severity: str = "medium"
    user: Optional[str] = None
    app: Optional[str] = None
    timestamp: Optional[str] = None
    malware_type: Optional[str] = None


class NetskopeAnomaly(BaseModel):
    """Represents a user/entity behavior anomaly."""

    model_config = ConfigDict(extra="allow")

    id: str
    anomaly_name: Optional[str] = None
    severity: str = "medium"
    user: Optional[str] = None
    app: Optional[str] = None
    timestamp: Optional[str] = None
    anomaly_type: Optional[str] = None


class NetskopeOAuthToken(BaseModel):
    """OAuth2 token response."""

    model_config = ConfigDict(extra="allow")

    access_token: str
    token_type: str = "Bearer"
    expires_in: int = 3600


class NetskopeIncidentsResponse(BaseModel):
    """Generic incidents list response wrapper."""

    model_config = ConfigDict(extra="allow")

    data: list[dict] = Field(default_factory=list)
