"""
Pydantic v2 models for Microsoft Graph API responses (M365 Collaboration).

Covers:
- SharePoint sites from /sites
- OneDrive drives/permissions from /users/{id}/drive
- Teams from /teams
- OAuth2 token response
"""

from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field


class M365OAuthToken(BaseModel):
    """OAuth2 token response from login.microsoftonline.com."""

    model_config = ConfigDict(extra="allow")

    token_type: str = "Bearer"
    expires_in: int = 3600
    access_token: str


class M365SharePointSite(BaseModel):
    """Represents a SharePoint site."""

    model_config = ConfigDict(extra="allow")

    id: str
    name: Optional[str] = None
    webUrl: Optional[str] = None
    displayName: Optional[str] = None
    sharepointIds: Optional[dict[str, Any]] = None
    isPersonalSite: Optional[bool] = None


class M365OneDrivePermission(BaseModel):
    """Represents a permission on a OneDrive item."""

    model_config = ConfigDict(extra="allow")

    id: str
    roles: list[str] = Field(default_factory=list)
    link: Optional[dict[str, Any]] = None
    grantedTo: Optional[dict[str, Any]] = None
    grantedToIdentities: list[dict[str, Any]] = Field(default_factory=list)


class M365OneDriveDrive(BaseModel):
    """Represents a OneDrive drive."""

    model_config = ConfigDict(extra="allow")

    id: str
    name: Optional[str] = None
    driveType: Optional[str] = None
    owner: Optional[dict[str, Any]] = None
    permissions: list[M365OneDrivePermission] = Field(default_factory=list)


class M365User(BaseModel):
    """Represents a Microsoft 365 user."""

    model_config = ConfigDict(extra="allow")

    id: str
    displayName: Optional[str] = None
    userPrincipalName: Optional[str] = None
    mail: Optional[str] = None


class M365Team(BaseModel):
    """Represents a Microsoft Teams team."""

    model_config = ConfigDict(extra="allow")

    id: str
    displayName: Optional[str] = None
    description: Optional[str] = None
    visibility: Optional[str] = None  # public, private, hiddenMembership
    isArchived: Optional[bool] = None


class M365GraphListResponse(BaseModel):
    """Generic Microsoft Graph list response with pagination."""

    model_config = ConfigDict(extra="allow")

    value: list[dict[str, Any]] = Field(default_factory=list)
    odata_nextLink: Optional[str] = Field(default=None, alias="@odata.nextLink")
