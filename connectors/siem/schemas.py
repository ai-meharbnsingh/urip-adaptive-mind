"""
Pydantic v2 models for Generic SIEM/SoC connector.

Covers:
- Common normalized event wrapper
- Per-adapter raw shapes (Splunk, Elastic, QRadar)
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field


class SiemCommonEvent(BaseModel):
    """Common fields extracted from any SIEM adapter."""

    model_config = ConfigDict(extra="allow")

    event_id: str
    timestamp: Optional[datetime] = None
    severity: str = "medium"  # native severity label
    message: Optional[str] = None
    source_host: Optional[str] = None
    domain_hint: Optional[str] = None
    raw: dict[str, Any] = Field(default_factory=dict)


class SplunkEvent(BaseModel):
    """Raw Splunk event from /services/search/jobs/export."""

    model_config = ConfigDict(extra="allow")

    _time: Optional[str] = None
    source: Optional[str] = None
    host: Optional[str] = None
    event_id: Optional[str] = None
    severity: Optional[str] = None
    message: Optional[str] = None
    domain_hint: Optional[str] = None


class ElasticHit(BaseModel):
    """Raw Elastic hit from _search."""

    model_config = ConfigDict(extra="allow")

    _id: str
    _source: dict[str, Any] = Field(default_factory=dict)


class QRadarEvent(BaseModel):
    """Raw QRadar event from /api/ariel/searches/{search_id}/results."""

    model_config = ConfigDict(extra="allow")

    id: Optional[str] = None
    starttime: Optional[int] = None  # epoch ms
    severity: Optional[int] = None
    eventname: Optional[str] = None
    sourceip: Optional[str] = None
    domain_hint: Optional[str] = None
    message: Optional[str] = None
