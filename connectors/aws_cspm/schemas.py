"""
Pydantic v2 models for AWS CSPM API responses.
"""
from __future__ import annotations

from typing import Any, Optional
from pydantic import BaseModel, ConfigDict, Field


class AwsConfigRuleCompliance(BaseModel):
    model_config = ConfigDict(extra="allow")
    ConfigRuleName: str
    ComplianceType: str  # COMPLIANT | NON_COMPLIANT | NOT_APPLICABLE | INSUFFICIENT_DATA
    ConfigRuleArn: Optional[str] = None
    ConfigRuleId: Optional[str] = None


class AwsSecurityHubFinding(BaseModel):
    model_config = ConfigDict(extra="allow")
    Id: str
    Title: Optional[str] = None
    Description: Optional[str] = None
    Severity: dict[str, Any] = Field(default_factory=dict)
    Types: list[str] = Field(default_factory=list)
    Resources: list[dict[str, Any]] = Field(default_factory=list)
    ProductArn: Optional[str] = None
    RecordState: Optional[str] = None
    Workflow: dict[str, Any] = Field(default_factory=dict)


class AwsGuardDutyFinding(BaseModel):
    model_config = ConfigDict(extra="allow")
    Id: str
    Title: Optional[str] = None
    Description: Optional[str] = None
    Severity: float = 0.0
    Type: Optional[str] = None
    Resource: dict[str, Any] = Field(default_factory=dict)
    Service: dict[str, Any] = Field(default_factory=dict)


class AwsAccessAnalyzerFinding(BaseModel):
    model_config = ConfigDict(extra="allow")
    id: str
    status: Optional[str] = None
    resourceType: Optional[str] = None
    resource: Optional[str] = None
    principal: dict[str, Any] = Field(default_factory=dict)
    action: dict[str, Any] = Field(default_factory=dict)
    isPublic: bool = False
