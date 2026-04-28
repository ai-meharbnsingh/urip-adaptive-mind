"""
Pydantic v2 models for GitHub Advanced Security (GHAS) API responses.

Covers three alert types surfaced by the GHAS connector:
  - GhasCodeScanningAlert   — /orgs/{org}/code-scanning/alerts
  - GhasSecretScanningAlert — /orgs/{org}/secret-scanning/alerts
  - GhasDependabotAlert     — /orgs/{org}/dependabot/alerts

All models use ``extra="allow"`` so that new GitHub API fields are preserved
in raw_data without raising validation errors.
"""

from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field


# ─────────────────────────────────────────────────────────────────────────────
# Code Scanning
# ─────────────────────────────────────────────────────────────────────────────


class GhasCodeScanningRule(BaseModel):
    """Rule metadata embedded in a code-scanning alert."""

    model_config = ConfigDict(extra="allow")

    id: Optional[str] = None
    severity: Optional[str] = None                       # "error" | "warning" | "note"
    security_severity_level: Optional[str] = None        # "critical" | "high" | "medium" | "low" | None


class GhasCodeScanningLocation(BaseModel):
    """File location of the most recent alert instance."""

    model_config = ConfigDict(extra="allow")

    path: Optional[str] = None
    start_line: Optional[int] = None
    end_line: Optional[int] = None
    start_column: Optional[int] = None
    end_column: Optional[int] = None


class GhasCodeScanningInstance(BaseModel):
    """Most recent instance of a code-scanning alert."""

    model_config = ConfigDict(extra="allow")

    location: Optional[GhasCodeScanningLocation] = None
    ref: Optional[str] = None
    state: Optional[str] = None


class GhasCodeScanningAlert(BaseModel):
    """
    GitHub Code Scanning alert.

    Key fields (from /orgs/{org}/code-scanning/alerts):
      number                          — numeric alert ID
      state                           — "open" | "dismissed" | "auto-dismissed" | "fixed"
      rule.id                         — CodeQL rule ID (e.g. "java/sql-injection")
      rule.severity                   — "error" | "warning" | "note"
      rule.security_severity_level    — "critical" | "high" | "medium" | "low" | None
      most_recent_instance.location.path — affected file path
      html_url                        — canonical GitHub UI link
    """

    model_config = ConfigDict(extra="allow")

    number: int
    state: Optional[str] = None
    rule: Optional[GhasCodeScanningRule] = None
    most_recent_instance: Optional[GhasCodeScanningInstance] = None
    html_url: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


# ─────────────────────────────────────────────────────────────────────────────
# Secret Scanning
# ─────────────────────────────────────────────────────────────────────────────


class GhasSecretScanningAlert(BaseModel):
    """
    GitHub Secret Scanning alert.

    Key fields (from /orgs/{org}/secret-scanning/alerts):
      number                   — numeric alert ID
      state                    — "open" | "resolved"
      secret_type              — machine-readable type (e.g. "github_personal_access_token")
      secret_type_display_name — human-readable type ("GitHub Personal Access Token")
      html_url                 — canonical GitHub UI link
    """

    model_config = ConfigDict(extra="allow")

    number: int
    state: Optional[str] = None
    secret_type: Optional[str] = None
    secret_type_display_name: Optional[str] = None
    html_url: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


# ─────────────────────────────────────────────────────────────────────────────
# Dependabot
# ─────────────────────────────────────────────────────────────────────────────


class GhasDependabotPackage(BaseModel):
    """Package details inside a Dependabot vulnerability."""

    model_config = ConfigDict(extra="allow")

    ecosystem: Optional[str] = None
    name: Optional[str] = None


class GhasDependabotVulnerability(BaseModel):
    """Vulnerability block inside a Dependabot alert."""

    model_config = ConfigDict(extra="allow")

    package: Optional[GhasDependabotPackage] = None
    severity: Optional[str] = None
    vulnerable_version_range: Optional[str] = None
    first_patched_version: Optional[Any] = None


class GhasDependabotAdvisory(BaseModel):
    """GitHub Security Advisory embedded in a Dependabot alert."""

    model_config = ConfigDict(extra="allow")

    ghsa_id: Optional[str] = None
    cve_id: Optional[str] = None
    summary: Optional[str] = None
    severity: Optional[str] = None                  # "critical" | "high" | "medium" | "low"
    cvss_score: Optional[float] = None


class GhasDependabotAlert(BaseModel):
    """
    GitHub Dependabot (SCA) alert.

    Key fields (from /orgs/{org}/dependabot/alerts):
      number                                     — numeric alert ID
      state                                      — "open" | "dismissed" | "fixed" | "auto-dismissed"
      security_advisory.severity                 — "critical" | "high" | "medium" | "low"
      security_vulnerability.package.name        — e.g. "lodash"
      security_vulnerability.vulnerable_version_range — e.g. "< 4.17.21"
      html_url                                   — canonical GitHub UI link
    """

    model_config = ConfigDict(extra="allow")

    number: int
    state: Optional[str] = None
    security_advisory: Optional[GhasDependabotAdvisory] = None
    security_vulnerability: Optional[GhasDependabotVulnerability] = None
    html_url: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
