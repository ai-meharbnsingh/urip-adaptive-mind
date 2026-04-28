"""
shared.events.topics — Event bus topic constants and Pydantic v2 payload schemas

Topic naming convention:
  <service>.<entity>.<action>

Topics:
  urip.risk.created           — URIP emits when a new risk is ingested
  urip.risk.resolved          — URIP emits when a risk is closed/accepted/verified
  urip.connector.synced       — URIP emits after a connector pull completes
  compliance.control.failed   — Compliance emits when a control check fails
  compliance.policy.expiring  — Compliance emits when a policy is near expiry

Usage:
    from shared.events.topics import TOPIC_RISK_CREATED, RiskCreatedPayload

    payload = RiskCreatedPayload(
        risk_id="...",
        tenant_id="...",
        severity="critical",
        source="crowdstrike",
        finding="RCE in nginx",
        cvss_score=9.8,
        created_at=datetime.now(timezone.utc).isoformat(),
    )
    await redis_client.publish(TOPIC_RISK_CREATED, payload.model_dump())
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, field_validator

# ---------------------------------------------------------------------------
# Topic constants
# ---------------------------------------------------------------------------

TOPIC_RISK_CREATED: str = "urip.risk.created"
TOPIC_RISK_RESOLVED: str = "urip.risk.resolved"
TOPIC_CONNECTOR_SYNCED: str = "urip.connector.synced"
TOPIC_CONTROL_FAILED: str = "compliance.control.failed"
TOPIC_POLICY_EXPIRING: str = "compliance.policy.expiring"


# ---------------------------------------------------------------------------
# Payload schemas — Pydantic v2
# ---------------------------------------------------------------------------


class RiskCreatedPayload(BaseModel):
    """Emitted by URIP on urip.risk.created."""

    risk_id: str
    tenant_id: str
    severity: str
    source: str
    finding: str
    cvss_score: float
    created_at: str  # ISO-8601 string for cross-service compat

    @field_validator("cvss_score", mode="before")
    @classmethod
    def validate_cvss(cls, v):
        return float(v)


class RiskResolvedPayload(BaseModel):
    """Emitted by URIP on urip.risk.resolved."""

    risk_id: str
    tenant_id: str
    resolved_by: str
    resolved_at: str  # ISO-8601
    resolution: str


class ConnectorSyncedPayload(BaseModel):
    """Emitted by URIP on urip.connector.synced after a pull completes."""

    connector_id: str
    tenant_id: str
    connector_type: str
    risks_imported: int
    synced_at: str  # ISO-8601


class ControlFailedPayload(BaseModel):
    """Emitted by Compliance on compliance.control.failed."""

    control_id: str
    tenant_id: str
    control_name: str
    framework: str
    failed_at: str  # ISO-8601
    details: Optional[str] = None


class PolicyExpiringPayload(BaseModel):
    """Emitted by Compliance on compliance.policy.expiring."""

    policy_id: str
    tenant_id: str
    policy_name: str
    expires_at: str  # ISO-8601
    days_remaining: int
