"""
Pydantic v2 models for GCP CSPM API responses.

Covers:
- Security Command Center findings
- Cloud Asset Inventory resources
- Security Recommender recommendations
"""

from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field


class GcpSccFinding(BaseModel):
    """Security Command Center finding."""

    model_config = ConfigDict(extra="allow")

    name: str
    state: Optional[str] = None
    severity: Optional[str] = None
    category: Optional[str] = None
    description: Optional[str] = None
    resourceName: Optional[str] = None
    eventTime: Optional[str] = None
    createTime: Optional[str] = None
    securityMarks: dict[str, Any] = Field(default_factory=dict)
    sourceProperties: dict[str, Any] = Field(default_factory=dict)


class GcpAsset(BaseModel):
    """Cloud Asset Inventory resource."""

    model_config = ConfigDict(extra="allow")

    name: str
    assetType: Optional[str] = None
    resource: Optional[dict[str, Any]] = None
    iamPolicy: Optional[dict[str, Any]] = None
    ancestors: list[str] = Field(default_factory=list)


class GcpRecommenderRecommendation(BaseModel):
    """Security Recommender recommendation."""

    model_config = ConfigDict(extra="allow")

    name: str
    description: Optional[str] = None
    recommenderSubtype: Optional[str] = None
    priority: Optional[str] = None
    content: dict[str, Any] = Field(default_factory=dict)
    stateInfo: dict[str, Any] = Field(default_factory=dict)
    lastRefreshTime: Optional[str] = None
    primaryImpact: dict[str, Any] = Field(default_factory=dict)
    associatedInsights: list[dict[str, Any]] = Field(default_factory=list)
