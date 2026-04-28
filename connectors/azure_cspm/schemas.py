"""
Pydantic v2 models for Azure CSPM API responses.

Covers:
- Azure Policy compliance states
- Microsoft Defender for Cloud recommendations
- Microsoft Defender for Cloud alerts
- Azure Resource Graph query result rows
"""

from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field


class AzurePolicyCompliance(BaseModel):
    """Azure Policy compliance state record."""

    model_config = ConfigDict(extra="allow")

    subscriptionId: Optional[str] = None
    resourceGroup: Optional[str] = None
    resourceId: Optional[str] = None
    policyAssignmentId: Optional[str] = None
    policyAssignmentName: Optional[str] = None
    policyDefinitionId: Optional[str] = None
    policyDefinitionName: Optional[str] = None
    policyDefinitionReferenceId: Optional[str] = None
    complianceState: Optional[str] = None
    timestamp: Optional[str] = None
    resourceType: Optional[str] = None
    resourceLocation: Optional[str] = None


class AzureDefenderRecommendation(BaseModel):
    """Microsoft Defender for Cloud recommendation (assessment)."""

    model_config = ConfigDict(extra="allow")

    id: Optional[str] = None
    name: Optional[str] = None
    type: Optional[str] = None
    properties: dict[str, Any] = Field(default_factory=dict)


class AzureDefenderAlert(BaseModel):
    """Microsoft Defender for Cloud alert."""

    model_config = ConfigDict(extra="allow")

    id: Optional[str] = None
    name: Optional[str] = None
    type: Optional[str] = None
    properties: dict[str, Any] = Field(default_factory=dict)


class AzureResourceGraphResult(BaseModel):
    """Azure Resource Graph query result row."""

    model_config = ConfigDict(extra="allow")

    id: Optional[str] = None
    name: Optional[str] = None
    type: Optional[str] = None
    resourceGroup: Optional[str] = None
    subscriptionId: Optional[str] = None
    properties: dict[str, Any] = Field(default_factory=dict)
    tags: dict[str, Any] = Field(default_factory=dict)
