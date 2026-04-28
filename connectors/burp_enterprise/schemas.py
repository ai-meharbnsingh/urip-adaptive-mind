"""
Pydantic v2 models for Burp Suite Enterprise REST API responses.

Covers:
- Scan records
- Issue / finding records
"""

from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field


class BurpScan(BaseModel):
    """Represents a Burp Suite Enterprise scan."""

    model_config = ConfigDict(extra="allow")

    id: str
    name: Optional[str] = None
    status: Optional[str] = None  # succeeded, failed, paused, queued, running
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    target_url: Optional[str] = None
    scan_config_id: Optional[str] = None


class BurpIssue(BaseModel):
    """Represents a Burp Suite Enterprise scan issue / finding."""

    model_config = ConfigDict(extra="allow")

    id: str
    scan_id: Optional[str] = None
    issue_type: Optional[str] = None  # XSS, SQLi, etc.
    severity: Optional[str] = None  # critical, high, medium, low, info
    confidence: Optional[str] = None  # certain, firm, tentative
    path: Optional[str] = None
    url: Optional[str] = None
    description: Optional[str] = None
    remediation: Optional[str] = None


class BurpListResponse(BaseModel):
    """Generic list response wrapper."""

    model_config = ConfigDict(extra="allow")

    data: list[dict[str, Any]] = Field(default_factory=list)
    total_count: int = 0
