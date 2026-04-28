"""
connectors/snyk/schemas.py — Pydantic v2 models for Snyk REST API v2024-10-15.

Covers:
- SnykIssue   — individual vulnerability finding from /rest/orgs/{org_id}/issues
- SnykProject — project record from /rest/orgs/{org_id}/projects

Snyk REST API uses a JSON:API-flavoured response shape:
  {
    "data": [
      {
        "id": "<uuid>",
        "type": "issue",
        "attributes": { ... },
        "relationships": { ... }
      }
    ]
  }

We model only the fields that URIP normalizes to keep the schema slim;
extra fields are allowed via ``model_config = ConfigDict(extra="allow")``.
"""

from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field


# ─────────────────────────────────────────────────────────────────────────────
# Nested helpers — SnykIssue attributes
# ─────────────────────────────────────────────────────────────────────────────


class SnykProblem(BaseModel):
    """One entry in attributes.problems[] (CVE reference, CWE, GHSA, …)."""

    model_config = ConfigDict(extra="allow")

    id: Optional[str] = None          # e.g. "CVE-2021-44228"
    source: Optional[str] = None      # e.g. "NVD", "GHSA"
    url: Optional[str] = None
    disclosed_at: Optional[str] = None
    discovered_at: Optional[str] = None


class SnykDependency(BaseModel):
    """Package identity inside coordinates[].representations[].dependency."""

    model_config = ConfigDict(extra="allow")

    package_name: Optional[str] = None
    package_version: Optional[str] = None


class SnykRepresentation(BaseModel):
    """One entry in coordinates[].representations[]."""

    model_config = ConfigDict(extra="allow")

    dependency: Optional[SnykDependency] = None
    resource: Optional[dict[str, Any]] = None  # IaC resource representation


class SnykCoordinate(BaseModel):
    """One entry in attributes.coordinates[]."""

    model_config = ConfigDict(extra="allow")

    remedies: Optional[list[dict[str, Any]]] = Field(default_factory=list)
    representations: list[SnykRepresentation] = Field(default_factory=list)


class SnykIssueAttributes(BaseModel):
    """
    ``attributes`` block inside a Snyk issue object.

    Only the fields consumed by SnykConnector.normalize() are declared here;
    all other vendor fields pass through via ``extra="allow"``.
    """

    model_config = ConfigDict(extra="allow")

    title: Optional[str] = None
    effective_severity_level: Optional[str] = None  # critical|high|medium|low
    status: Optional[str] = None                    # open|resolved|ignored
    type: Optional[str] = None                      # sast|open_source|container|iac
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    problems: list[SnykProblem] = Field(default_factory=list)
    coordinates: list[SnykCoordinate] = Field(default_factory=list)


# ─────────────────────────────────────────────────────────────────────────────
# SnykIssue — top-level data object
# ─────────────────────────────────────────────────────────────────────────────


class SnykIssue(BaseModel):
    """
    Single Snyk issue from GET /rest/orgs/{org_id}/issues.

    JSON:API shape:
      { "id": "…", "type": "issue", "attributes": { … }, "relationships": { … } }
    """

    model_config = ConfigDict(extra="allow")

    id: str
    type: Optional[str] = None
    attributes: SnykIssueAttributes = Field(default_factory=SnykIssueAttributes)
    relationships: Optional[dict[str, Any]] = None


# ─────────────────────────────────────────────────────────────────────────────
# Nested helpers — SnykProject attributes
# ─────────────────────────────────────────────────────────────────────────────


class SnykProjectAttributes(BaseModel):
    """``attributes`` block inside a Snyk project object."""

    model_config = ConfigDict(extra="allow")

    name: Optional[str] = None
    target_file: Optional[str] = None    # e.g. "package-lock.json"
    type: Optional[str] = None           # e.g. "npm", "docker", "k8sconfig"
    status: Optional[str] = None         # active|inactive
    created: Optional[str] = None
    tags: list[dict[str, str]] = Field(default_factory=list)


# ─────────────────────────────────────────────────────────────────────────────
# SnykProject — top-level data object
# ─────────────────────────────────────────────────────────────────────────────


class SnykProject(BaseModel):
    """
    Single Snyk project from GET /rest/orgs/{org_id}/projects.

    JSON:API shape:
      { "id": "…", "type": "project", "attributes": { … } }
    """

    model_config = ConfigDict(extra="allow")

    id: str
    type: Optional[str] = None
    attributes: SnykProjectAttributes = Field(default_factory=SnykProjectAttributes)
