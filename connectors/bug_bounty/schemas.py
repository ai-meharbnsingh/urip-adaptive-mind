"""
Pydantic v2 models for Bug Bounty connector.

Covers:
- HackerOne report
- Bugcrowd submission
- Common normalized shape
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field


class HackerOneReport(BaseModel):
    """HackerOne REST API report object."""

    model_config = ConfigDict(extra="allow")

    id: str
    attributes: dict[str, Any] = Field(default_factory=dict)


class BugcrowdSubmission(BaseModel):
    """Bugcrowd REST API submission object."""

    model_config = ConfigDict(extra="allow")

    id: str
    attributes: dict[str, Any] = Field(default_factory=dict)


class BugBountyCommon(BaseModel):
    """Common normalized bug bounty finding."""

    model_config = ConfigDict(extra="allow")

    platform: str
    report_id: str
    title: str
    severity: str = "medium"
    state: Optional[str] = None
    asset: Optional[str] = None
    weakness: Optional[str] = None
    remediation_recommendation: Optional[str] = None
    submitted_at: Optional[datetime] = None
    raw: dict[str, Any] = Field(default_factory=dict)
