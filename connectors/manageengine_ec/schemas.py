"""
Pydantic v2 models for ManageEngine Endpoint Central API responses.

Covers:
- Computer / endpoint records
- Missing patch records
- Compliance score records
"""

from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field


class MECComputer(BaseModel):
    """Represents an endpoint managed by Endpoint Central."""

    model_config = ConfigDict(extra="allow")

    id: str
    name: Optional[str] = None
    ip_address: Optional[str] = None
    os: Optional[str] = None
    patch_status: Optional[str] = None  # compliant, non_compliant, unknown
    last_scan_time: Optional[str] = None
    compliance_score: Optional[float] = None


class MECMissingPatch(BaseModel):
    """Represents a missing patch on an endpoint."""

    model_config = ConfigDict(extra="allow")

    id: str
    computer_id: Optional[str] = None
    computer_name: Optional[str] = None
    patch_id: Optional[str] = None
    patch_name: Optional[str] = None
    severity: Optional[str] = None  # critical, important, moderate, low
    release_date: Optional[str] = None


class MECComplianceRecord(BaseModel):
    """Represents a compliance score record."""

    model_config = ConfigDict(extra="allow")

    computer_id: str
    computer_name: Optional[str] = None
    compliance_score: float = 0.0
    missing_critical_patches: int = 0
    missing_important_patches: int = 0


class MECListResponse(BaseModel):
    """Generic list response wrapper."""

    model_config = ConfigDict(extra="allow")

    data: list[dict[str, Any]] = Field(default_factory=list)
    total_count: int = 0
