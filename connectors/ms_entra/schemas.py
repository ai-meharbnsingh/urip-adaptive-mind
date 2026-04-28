"""
Pydantic v2 models for Microsoft Graph API responses (Identity Protection).

Covers:
- Risky users from /identityProtection/riskyUsers
- Risk detections from /identityProtection/riskDetections
- Risky sign-ins from /auditLogs/signIns
- CA policy results from /identityProtection/conditionalAccessPolicyResults
"""

from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field


class MsEntraRiskyUser(BaseModel):
    """Represents a risky user record."""

    model_config = ConfigDict(extra="allow")

    id: str
    userPrincipalName: Optional[str] = None
    riskState: Optional[str] = None
    riskLevel: Optional[str] = None


class MsEntraRiskDetection(BaseModel):
    """Represents an Entra ID risk detection."""

    model_config = ConfigDict(extra="allow")

    id: str
    userPrincipalName: Optional[str] = None
    riskEventType: Optional[str] = None
    riskLevel: Optional[str] = None
    riskState: Optional[str] = None
    detectedDateTime: Optional[str] = None


class MsEntraRiskySignIn(BaseModel):
    """Represents a risky sign-in record."""

    model_config = ConfigDict(extra="allow")

    id: str
    userPrincipalName: Optional[str] = None
    riskLevelDuringSignIn: Optional[str] = None
    riskState: Optional[str] = None
    createdDateTime: Optional[str] = None


class MsEntraCAPolicyResult(BaseModel):
    """Represents a conditional access policy evaluation result."""

    model_config = ConfigDict(extra="allow")

    id: str
    policyName: Optional[str] = None
    result: Optional[str] = None
    userPrincipalName: Optional[str] = None
    createdDateTime: Optional[str] = None


class MsEntraGraphListResponse(BaseModel):
    """Generic Microsoft Graph list response with pagination."""

    model_config = ConfigDict(extra="allow")

    value: list[dict[str, Any]] = Field(default_factory=list)
    odata_nextLink: Optional[str] = Field(default=None, alias="@odata.nextLink")


class MsEntraOAuthToken(BaseModel):
    """OAuth2 token response from login.microsoftonline.com."""

    model_config = ConfigDict(extra="allow")

    token_type: str = "Bearer"
    expires_in: int = 3600
    access_token: str
