"""
Pydantic v2 models for CERT-In advisories.

Covers:
- Parsed RSS item
- Scraped HTML advisory row
- Unified advisory shape used by the connector
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class CertInAdvisory(BaseModel):
    """Unified CERT-In advisory record, whether sourced from RSS or HTML scrape."""

    model_config = ConfigDict(extra="allow")

    cert_in_id: str
    title: str
    severity: str = "Medium"  # Critical / High / Medium / Low
    affected_products: list[str] = Field(default_factory=list)
    cve_refs: list[str] = Field(default_factory=list)
    description: Optional[str] = None
    mitigation: Optional[str] = None
    published_at: Optional[datetime] = None
    source_url: Optional[str] = None
