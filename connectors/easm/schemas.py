"""
Pydantic v2 models for the generic EASM connector's three sub-adapters
(Censys, Shodan, Detectify).

All models use ``extra='allow'`` so the connector keeps working when vendors
add new fields server-side.

We model only the fields we actually consume; everything else is preserved
through ``extra='allow'`` and forwarded into ``RawFinding.raw_data`` for
optional downstream consumers.
"""

from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field


# ─────────────────────────────────────────────────────────────────────────────
# Censys (search.censys.io v2)
# ─────────────────────────────────────────────────────────────────────────────


class CensysService(BaseModel):
    model_config = ConfigDict(extra="allow")

    port: Optional[int] = None
    service_name: Optional[str] = None
    transport_protocol: Optional[str] = None
    extended_service_name: Optional[str] = None


class CensysRisk(BaseModel):
    model_config = ConfigDict(extra="allow")

    severity: Optional[str] = None  # "low" | "medium" | "high" | "critical"


class CensysHit(BaseModel):
    model_config = ConfigDict(extra="allow")

    ip: Optional[str] = None
    name: Optional[str] = None
    services: list[CensysService] = Field(default_factory=list)
    risk: CensysRisk = Field(default_factory=CensysRisk)


class CensysLinks(BaseModel):
    model_config = ConfigDict(extra="allow")

    next: Optional[str] = ""


class CensysResult(BaseModel):
    model_config = ConfigDict(extra="allow")

    hits: list[CensysHit] = Field(default_factory=list)
    links: CensysLinks = Field(default_factory=CensysLinks)


class CensysSearchResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    result: CensysResult = Field(default_factory=CensysResult)


# ─────────────────────────────────────────────────────────────────────────────
# Shodan
# ─────────────────────────────────────────────────────────────────────────────


class ShodanBanner(BaseModel):
    model_config = ConfigDict(extra="allow")

    port: Optional[int] = None
    product: Optional[str] = None
    version: Optional[str] = None
    http: Optional[dict[str, Any]] = None


class ShodanHostResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    ip_str: Optional[str] = None
    ports: list[int] = Field(default_factory=list)
    data: list[ShodanBanner] = Field(default_factory=list)
    vulns: list[str] = Field(default_factory=list)


# ─────────────────────────────────────────────────────────────────────────────
# Detectify
# ─────────────────────────────────────────────────────────────────────────────


class DetectifyFinding(BaseModel):
    model_config = ConfigDict(extra="allow")

    uuid: str
    title: Optional[str] = None
    severity: Optional[str] = None
    found_at: Optional[str] = None
    url: Optional[str] = None
    category: Optional[str] = None
    confirmed: Optional[bool] = None


class DetectifyFindingsResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    findings: list[DetectifyFinding] = Field(default_factory=list)
    next_cursor: Optional[str] = ""
