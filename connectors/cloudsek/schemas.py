"""
Pydantic v2 models for CloudSEK API responses.

Covers:
- XVigil alerts from /v1/xvigil/alerts
- BeVigil findings from /v1/bevigil/findings
- SVigil risks from /v1/svigil/risks

All models use ConfigDict(extra='allow') so new fields added by CloudSEK
in the future do not cause deserialization failures.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field


class CloudSEKAsset(BaseModel):
    """Nested asset object common across CloudSEK products."""

    model_config = ConfigDict(extra="allow")

    email: Optional[str] = None
    domain: Optional[str] = None
    package_name: Optional[str] = None
    platform: Optional[str] = None
    url: Optional[str] = None
    vendor_name: Optional[str] = None


class CloudSEKAlertBase(BaseModel):
    """Fields common to XVigil, BeVigil, and SVigil records."""

    model_config = ConfigDict(extra="allow")

    id: str
    alert_type: str
    title: str
    severity: str
    created_at: Optional[datetime] = None
    status: Optional[str] = None
    threat_actor: Optional[str] = None
    description: Optional[str] = None
    asset: Optional[CloudSEKAsset] = None
    # Internal field injected by the connector to track product line
    _product: Optional[str] = None


class XVigilAlert(CloudSEKAlertBase):
    """Dark-web monitoring alert: leaked creds, brand abuse, fake apps, etc."""

    # XVigil-specific enrichments
    breach_source: Optional[str] = None
    leaked_data_types: list[str] = Field(default_factory=list)


class BeVigilFinding(CloudSEKAlertBase):
    """Mobile / web attack-surface finding: hardcoded secrets, exposed APIs, etc."""

    # BeVigil-specific enrichments
    app_store: Optional[str] = None
    scan_type: Optional[str] = None


class SVigilRisk(CloudSEKAlertBase):
    """Supply-chain vendor risk: critical CVEs, expired certifications, etc."""

    # SVigil-specific enrichments
    cvss_score: Optional[float] = None
    vendor_tier: Optional[str] = None
    certification_type: Optional[str] = None


class CloudSEKPagination(BaseModel):
    """Cursor-based pagination wrapper."""

    model_config = ConfigDict(extra="allow")

    next_cursor: Optional[str] = None
    total_items: int = 0


class CloudSEKResponse(BaseModel):
    """Top-level list response from all CloudSEK product endpoints."""

    model_config = ConfigDict(extra="allow")

    data: list[dict[str, Any]] = Field(default_factory=list)
    pagination: CloudSEKPagination = Field(default_factory=CloudSEKPagination)
