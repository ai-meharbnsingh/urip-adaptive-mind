"""
Pydantic v2 models for ManageEngine MDM API responses.

Covers:
- Mobile device records
- Compliance / jailbreak records
- Lost/stolen device events
"""

from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field


class MEMDevice(BaseModel):
    """Represents a mobile device managed by ManageEngine MDM."""

    model_config = ConfigDict(extra="allow")

    id: str
    device_name: Optional[str] = None
    user_name: Optional[str] = None
    platform: Optional[str] = None  # iOS, Android, Windows
    os_version: Optional[str] = None
    is_jailbroken: Optional[bool] = False
    compliance_status: Optional[str] = None  # compliant, non_compliant
    enrollment_status: Optional[str] = None
    last_contact_time: Optional[str] = None


class MEMLostStolenEvent(BaseModel):
    """Represents a lost or stolen device event."""

    model_config = ConfigDict(extra="allow")

    id: str
    device_id: Optional[str] = None
    device_name: Optional[str] = None
    event_type: Optional[str] = None  # lost, stolen, recovered
    reported_at: Optional[str] = None
    reported_by: Optional[str] = None


class MEMListResponse(BaseModel):
    """Generic list response wrapper."""

    model_config = ConfigDict(extra="allow")

    data: list[dict[str, Any]] = Field(default_factory=list)
    total_count: int = 0
