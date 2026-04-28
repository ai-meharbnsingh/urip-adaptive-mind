"""shared.events — Event bus topic constants, payload schemas, and Redis client."""

from shared.events.bus import (
    InProcessEventBus,
    get_event_bus,
    reset_event_bus,
)
from shared.events.topics import (
    TOPIC_CONNECTOR_SYNCED,
    TOPIC_CONTROL_FAILED,
    TOPIC_POLICY_EXPIRING,
    TOPIC_RISK_CREATED,
    TOPIC_RISK_RESOLVED,
    ConnectorSyncedPayload,
    ControlFailedPayload,
    PolicyExpiringPayload,
    RiskCreatedPayload,
    RiskResolvedPayload,
)

__all__ = [
    # Topic constants
    "TOPIC_RISK_CREATED",
    "TOPIC_RISK_RESOLVED",
    "TOPIC_CONNECTOR_SYNCED",
    "TOPIC_CONTROL_FAILED",
    "TOPIC_POLICY_EXPIRING",
    # Payload schemas
    "RiskCreatedPayload",
    "RiskResolvedPayload",
    "ConnectorSyncedPayload",
    "ControlFailedPayload",
    "PolicyExpiringPayload",
    # In-process bus
    "InProcessEventBus",
    "get_event_bus",
    "reset_event_bus",
]
