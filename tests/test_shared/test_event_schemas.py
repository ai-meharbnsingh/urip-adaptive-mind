"""
TDD: shared.events.topics — topic constants + Pydantic v2 payload schemas

Tests:
  - topic constants have expected string values
  - each payload schema validates correctly with valid data
  - each payload schema rejects invalid/missing required fields
"""

import uuid
from datetime import datetime, timezone

import pytest

# RED until shared/events/topics.py exists
from shared.events.topics import (
    TOPIC_RISK_CREATED,
    TOPIC_RISK_RESOLVED,
    TOPIC_CONNECTOR_SYNCED,
    TOPIC_CONTROL_FAILED,
    TOPIC_POLICY_EXPIRING,
    RiskCreatedPayload,
    RiskResolvedPayload,
    ConnectorSyncedPayload,
    ControlFailedPayload,
    PolicyExpiringPayload,
)


class TestTopicConstants:
    def test_risk_created_topic(self):
        assert TOPIC_RISK_CREATED == "urip.risk.created"

    def test_risk_resolved_topic(self):
        assert TOPIC_RISK_RESOLVED == "urip.risk.resolved"

    def test_connector_synced_topic(self):
        assert TOPIC_CONNECTOR_SYNCED == "urip.connector.synced"

    def test_control_failed_topic(self):
        assert TOPIC_CONTROL_FAILED == "compliance.control.failed"

    def test_policy_expiring_topic(self):
        assert TOPIC_POLICY_EXPIRING == "compliance.policy.expiring"


class TestRiskCreatedPayload:
    def _valid(self):
        return {
            "risk_id": str(uuid.uuid4()),
            "tenant_id": str(uuid.uuid4()),
            "severity": "critical",
            "source": "crowdstrike",
            "finding": "Critical RCE in nginx",
            "cvss_score": 9.8,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

    def test_valid_payload(self):
        p = RiskCreatedPayload(**self._valid())
        assert p.severity == "critical"
        assert p.cvss_score == 9.8

    def test_missing_required_field_raises(self):
        data = self._valid()
        data.pop("risk_id")
        with pytest.raises(Exception):  # ValidationError
            RiskCreatedPayload(**data)

    def test_invalid_cvss_score_raises(self):
        data = self._valid()
        data["cvss_score"] = "not-a-number"
        with pytest.raises(Exception):
            RiskCreatedPayload(**data)


class TestRiskResolvedPayload:
    def _valid(self):
        return {
            "risk_id": str(uuid.uuid4()),
            "tenant_id": str(uuid.uuid4()),
            "resolved_by": str(uuid.uuid4()),
            "resolved_at": datetime.now(timezone.utc).isoformat(),
            "resolution": "Patch applied",
        }

    def test_valid_payload(self):
        p = RiskResolvedPayload(**self._valid())
        assert p.resolution == "Patch applied"

    def test_missing_resolved_by_raises(self):
        data = self._valid()
        data.pop("resolved_by")
        with pytest.raises(Exception):
            RiskResolvedPayload(**data)


class TestConnectorSyncedPayload:
    def _valid(self):
        return {
            "connector_id": str(uuid.uuid4()),
            "tenant_id": str(uuid.uuid4()),
            "connector_type": "crowdstrike",
            "risks_imported": 42,
            "synced_at": datetime.now(timezone.utc).isoformat(),
        }

    def test_valid_payload(self):
        p = ConnectorSyncedPayload(**self._valid())
        assert p.risks_imported == 42

    def test_negative_risks_count_allowed(self):
        """risks_imported 0 is valid (no new risks this sync)."""
        data = self._valid()
        data["risks_imported"] = 0
        p = ConnectorSyncedPayload(**data)
        assert p.risks_imported == 0


class TestControlFailedPayload:
    def _valid(self):
        return {
            "control_id": str(uuid.uuid4()),
            "tenant_id": str(uuid.uuid4()),
            "control_name": "MFA Enforcement",
            "framework": "ISO27001",
            "failed_at": datetime.now(timezone.utc).isoformat(),
            "details": "MFA not enabled for 3 admin accounts",
        }

    def test_valid_payload(self):
        p = ControlFailedPayload(**self._valid())
        assert p.framework == "ISO27001"

    def test_missing_control_name_raises(self):
        data = self._valid()
        data.pop("control_name")
        with pytest.raises(Exception):
            ControlFailedPayload(**data)


class TestPolicyExpiringPayload:
    def _valid(self):
        return {
            "policy_id": str(uuid.uuid4()),
            "tenant_id": str(uuid.uuid4()),
            "policy_name": "Acceptable Use Policy",
            "expires_at": datetime.now(timezone.utc).isoformat(),
            "days_remaining": 14,
        }

    def test_valid_payload(self):
        p = PolicyExpiringPayload(**self._valid())
        assert p.days_remaining == 14

    def test_missing_expires_at_raises(self):
        data = self._valid()
        data.pop("expires_at")
        with pytest.raises(Exception):
            PolicyExpiringPayload(**data)

    def test_days_remaining_zero_is_valid(self):
        """Zero days remaining = policy expired today — still valid payload."""
        data = self._valid()
        data["days_remaining"] = 0
        p = PolicyExpiringPayload(**data)
        assert p.days_remaining == 0
