"""
Pydantic v2 models for GTB Endpoint Protector REST API responses.

Covers:
- DLP policy violation records
- USB block event records
- Exfiltration attempt records
"""

from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field


class GTBViolation(BaseModel):
    """Represents a DLP policy violation."""

    model_config = ConfigDict(extra="allow")

    id: str
    policy_name: Optional[str] = None
    severity: Optional[str] = None  # critical, high, medium, low
    endpoint_name: Optional[str] = None
    user_name: Optional[str] = None
    channel: Optional[str] = None  # email, web, usb, print, cloud
    file_name: Optional[str] = None
    action_taken: Optional[str] = None  # blocked, alerted, encrypted
    detected_at: Optional[str] = None


class GTBUSBEvent(BaseModel):
    """Represents a USB block event."""

    model_config = ConfigDict(extra="allow")

    id: str
    endpoint_name: Optional[str] = None
    user_name: Optional[str] = None
    device_id: Optional[str] = None
    device_type: Optional[str] = None
    action: Optional[str] = None  # blocked, allowed
    occurred_at: Optional[str] = None


class GTBExfilEvent(BaseModel):
    """Represents an exfiltration attempt."""

    model_config = ConfigDict(extra="allow")

    id: str
    endpoint_name: Optional[str] = None
    user_name: Optional[str] = None
    destination: Optional[str] = None
    channel: Optional[str] = None
    file_count: int = 0
    total_size_bytes: int = 0
    detected_at: Optional[str] = None


class GTBListResponse(BaseModel):
    """Generic list response wrapper."""

    model_config = ConfigDict(extra="allow")

    data: list[dict[str, Any]] = Field(default_factory=list)
    total_count: int = 0
