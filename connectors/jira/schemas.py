"""
Pydantic v2 models for Jira Cloud / Data Center REST API v3 responses.

Covers:
- JiraIssue — individual issue record from /rest/api/3/issue/{key}
- JiraSearchResponse — paginated results from /rest/api/3/search
- JiraTransitionResponse — available transitions from /rest/api/3/issue/{key}/transitions
- JiraCreateIssueResponse — response from POST /rest/api/3/issue
"""

from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field


# ─────────────────────────────────────────────────────────────────────────────
# Nested field models
# ─────────────────────────────────────────────────────────────────────────────


class JiraStatus(BaseModel):
    model_config = ConfigDict(extra="allow")

    name: Optional[str] = None
    statusCategory: Optional[dict[str, Any]] = None


class JiraPriority(BaseModel):
    model_config = ConfigDict(extra="allow")

    name: Optional[str] = None
    iconUrl: Optional[str] = None


class JiraUser(BaseModel):
    model_config = ConfigDict(extra="allow")

    accountId: Optional[str] = None
    displayName: Optional[str] = None
    emailAddress: Optional[str] = None


class JiraIssueFields(BaseModel):
    """Fields sub-object returned inside a Jira issue."""

    model_config = ConfigDict(extra="allow")

    summary: Optional[str] = None
    status: Optional[JiraStatus] = None
    priority: Optional[JiraPriority] = None
    assignee: Optional[JiraUser] = None
    reporter: Optional[JiraUser] = None
    created: Optional[str] = None
    updated: Optional[str] = None
    description: Optional[Any] = None  # ADF or plain string
    labels: list[str] = Field(default_factory=list)


class JiraIssue(BaseModel):
    """
    Single Jira issue — returned by GET /rest/api/3/issue/{key}
    and embedded in search results.
    """

    model_config = ConfigDict(extra="allow")

    id: str
    key: str
    self: Optional[str] = None
    fields: Optional[JiraIssueFields] = None


class JiraSearchResponse(BaseModel):
    """
    Paginated results from POST /rest/api/3/search.
    """

    model_config = ConfigDict(extra="allow")

    total: int = 0
    startAt: int = 0
    maxResults: int = 50
    issues: list[JiraIssue] = Field(default_factory=list)


class JiraCreateIssueResponse(BaseModel):
    """Response from POST /rest/api/3/issue."""

    model_config = ConfigDict(extra="allow")

    id: str
    key: str
    self: Optional[str] = None


class JiraTransition(BaseModel):
    """One available transition."""

    model_config = ConfigDict(extra="allow")

    id: str
    name: Optional[str] = None


class JiraTransitionsResponse(BaseModel):
    """Response from GET /rest/api/3/issue/{key}/transitions."""

    model_config = ConfigDict(extra="allow")

    transitions: list[JiraTransition] = Field(default_factory=list)


class JiraMyselfResponse(BaseModel):
    """Response from GET /rest/api/3/myself."""

    model_config = ConfigDict(extra="allow")

    accountId: Optional[str] = None
    displayName: Optional[str] = None
    emailAddress: Optional[str] = None
    active: bool = True
