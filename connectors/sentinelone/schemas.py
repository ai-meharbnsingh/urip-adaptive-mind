"""
Pydantic v2 models for SentinelOne Singularity API responses.

Covers:
- Threat records from /web/api/v2.1/threats
- Agent records from /web/api/v2.1/agents
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field


class SentinelOneAgent(BaseModel):
    """Represents a SentinelOne endpoint agent."""

    model_config = ConfigDict(extra="allow")

    id: str
    computer_name: str
    os_name: Optional[str] = None
    is_active: bool = True
    last_logged_in_user_name: Optional[str] = None
    group_id: Optional[str] = None
    site_id: Optional[str] = None
    machine_type: Optional[str] = None
    version: Optional[str] = None


class SentinelOneThreatInfo(BaseModel):
    """Nested threat metadata."""

    model_config = ConfigDict(extra="allow")

    threat_name: Optional[str] = None
    confidence_level: Optional[str] = None
    storyline: Optional[str] = None
    analyst_verdict: Optional[str] = None


class SentinelOneThreat(BaseModel):
    """Represents a SentinelOne threat detection."""

    model_config = ConfigDict(extra="allow")

    id: str
    agent_id: Optional[str] = None
    agent_name: Optional[str] = None
    agent_os: Optional[str] = None
    classification: Optional[str] = None
    mitigated_status: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    threat_info: SentinelOneThreatInfo = Field(default_factory=SentinelOneThreatInfo)
    file_path: Optional[str] = None
    file_display_name: Optional[str] = None
    file_sha1: Optional[str] = None


class SentinelOnePagination(BaseModel):
    """Cursor-based pagination wrapper."""

    model_config = ConfigDict(extra="allow")

    next_cursor: Optional[str] = None
    total_items: int = 0


class SentinelOneThreatsResponse(BaseModel):
    """Top-level response from GET /threats."""

    model_config = ConfigDict(extra="allow")

    data: list[SentinelOneThreat] = Field(default_factory=list)
    pagination: SentinelOnePagination = Field(default_factory=SentinelOnePagination)


class SentinelOneAgentsResponse(BaseModel):
    """Top-level response from GET /agents."""

    model_config = ConfigDict(extra="allow")

    data: list[SentinelOneAgent] = Field(default_factory=list)
    pagination: SentinelOnePagination = Field(default_factory=SentinelOnePagination)
