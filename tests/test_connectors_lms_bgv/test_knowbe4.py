"""
TDD tests for the KnowBe4 connector.

Coverage:
- Authenticate validates API key
- fetch_findings pulls user training enrollments + phishing simulation results
- Incomplete training (status != "completed") becomes a finding
- Finding cites ISO 27001 A.6.3 + SOC 2 CC1.4
- Failed phishing simulation also becomes a finding
- normalize → URIPRiskRecord
- health_check
- Class metadata + SETUP_GUIDE present
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import httpx
import pytest
import respx

from connectors.base.connector import (
    ConnectorAuthError,
    ConnectorFetchError,
    ConnectorHealth,
    ConnectorSession,
    RawFinding,
    URIPRiskRecord,
)
from connectors.knowbe4.connector import KnowBe4Connector


@pytest.fixture
def connector() -> KnowBe4Connector:
    return KnowBe4Connector()


@pytest.fixture
def valid_credentials() -> dict[str, Any]:
    return {
        "api_key": "kb4-secret-token",
        "api_base": "https://us.api.knowbe4.com",
        "tenant_id": "tenant-kb4",
    }


# ─────────────────────────────────────────────────────────────────────────────
# Metadata + SETUP_GUIDE
# ─────────────────────────────────────────────────────────────────────────────


class TestMetadata:
    def test_class_metadata(self):
        assert KnowBe4Connector.NAME == "knowbe4"
        assert KnowBe4Connector.DISPLAY_NAME
        assert KnowBe4Connector.CATEGORY
        assert KnowBe4Connector.SHORT_DESCRIPTION
        assert KnowBe4Connector.STATUS in ("live", "building", "simulated", "roadmap")
        assert KnowBe4Connector.MODULE_CODE
        assert KnowBe4Connector.CREDENTIAL_FIELDS
        assert KnowBe4Connector.SETUP_GUIDE is not None

    def test_setup_guide_validates(self):
        problems = KnowBe4Connector.SETUP_GUIDE.validate()
        assert problems == [], f"SETUP_GUIDE validation problems: {problems}"


# ─────────────────────────────────────────────────────────────────────────────
# Authenticate
# ─────────────────────────────────────────────────────────────────────────────


class TestAuthenticate:
    def test_missing_api_key_raises(self, connector):
        with pytest.raises(ConnectorAuthError):
            connector.authenticate({})

    @respx.mock
    def test_valid_credentials_succeeds(self, connector, valid_credentials):
        respx.get("https://us.api.knowbe4.com/v1/account").mock(
            return_value=httpx.Response(200, json={"id": 999, "name": "Acme"})
        )
        session = connector.authenticate(valid_credentials)
        assert isinstance(session, ConnectorSession)
        assert session.connector_name == "knowbe4"
        assert session.tenant_id == "tenant-kb4"

    @respx.mock
    def test_invalid_credentials_raises(self, connector, valid_credentials):
        respx.get("https://us.api.knowbe4.com/v1/account").mock(
            return_value=httpx.Response(401, json={"error": "unauthorized"})
        )
        with pytest.raises(ConnectorAuthError):
            connector.authenticate(valid_credentials)


# ─────────────────────────────────────────────────────────────────────────────
# Fetch findings
# ─────────────────────────────────────────────────────────────────────────────


class TestFetchFindings:
    @respx.mock
    def test_fetch_pulls_incomplete_training_and_failed_phishing(
        self, connector, valid_credentials
    ):
        # Auth
        respx.get("https://us.api.knowbe4.com/v1/account").mock(
            return_value=httpx.Response(200, json={"id": 999})
        )

        # Training enrollments — one incomplete, one completed
        respx.get("https://us.api.knowbe4.com/v1/training/enrollments").mock(
            return_value=httpx.Response(
                200,
                json=[
                    {
                        "id": "tr-1",
                        "user": {"email": "alice@acme.com", "id": 1, "first_name": "Alice"},
                        "module_name": "Annual Security Awareness",
                        "status": "in_progress",
                        "enrollment_date": "2026-01-01T00:00:00Z",
                        "due_date": "2026-04-01T00:00:00Z",
                    },
                    {
                        "id": "tr-2",
                        "user": {"email": "bob@acme.com", "id": 2, "first_name": "Bob"},
                        "module_name": "Annual Security Awareness",
                        "status": "completed",
                        "enrollment_date": "2026-01-01T00:00:00Z",
                        "completion_date": "2026-02-15T00:00:00Z",
                    },
                ],
            )
        )

        # Phishing campaign results — Alice failed, Bob passed
        respx.get(
            "https://us.api.knowbe4.com/v1/phishing/security_tests/recipients"
        ).mock(
            return_value=httpx.Response(
                200,
                json=[
                    {
                        "id": "ph-1",
                        "user": {"email": "alice@acme.com", "first_name": "Alice"},
                        "campaign_name": "Q1 2026 Phishing",
                        "clicked": True,
                        "reported": False,
                        "delivered_at": "2026-03-01T10:00:00Z",
                    },
                    {
                        "id": "ph-2",
                        "user": {"email": "bob@acme.com", "first_name": "Bob"},
                        "campaign_name": "Q1 2026 Phishing",
                        "clicked": False,
                        "reported": True,
                        "delivered_at": "2026-03-01T10:00:00Z",
                    },
                ],
            )
        )

        connector.authenticate(valid_credentials)
        findings = connector.fetch_findings(
            since=datetime(2026, 1, 1, tzinfo=timezone.utc),
            tenant_id="tenant-kb4",
        )

        # Expect 2 findings: incomplete training (Alice) + failed phishing (Alice)
        # Bob is excluded (completed training, didn't click).
        assert len(findings) == 2
        kinds = sorted([f.raw_data.get("_kind") for f in findings])
        assert kinds == ["phishing_failed", "training_incomplete"]


# ─────────────────────────────────────────────────────────────────────────────
# Normalize
# ─────────────────────────────────────────────────────────────────────────────


class TestNormalize:
    def test_normalize_incomplete_training_cites_iso_and_soc2(self, connector):
        raw = RawFinding(
            id="tr-1",
            source="knowbe4",
            raw_data={
                "_kind": "training_incomplete",
                "id": "tr-1",
                "user": {"email": "alice@acme.com", "first_name": "Alice"},
                "module_name": "Annual Security Awareness",
                "status": "in_progress",
                "due_date": "2026-04-01T00:00:00Z",
            },
            fetched_at=datetime.now(timezone.utc),
            tenant_id="tenant-kb4",
        )
        record = connector.normalize(raw)
        assert isinstance(record, URIPRiskRecord)
        assert record.source == "knowbe4"
        # Compliance citations live in description so they survive end-to-end.
        assert "A.6.3" in record.description
        assert "CC1.4" in record.description
        # Incomplete training is medium severity by default
        assert record.severity in ("low", "medium")
        assert record.asset == "alice@acme.com"

    def test_normalize_failed_phishing_high_severity(self, connector):
        raw = RawFinding(
            id="ph-1",
            source="knowbe4",
            raw_data={
                "_kind": "phishing_failed",
                "id": "ph-1",
                "user": {"email": "alice@acme.com"},
                "campaign_name": "Q1 2026 Phishing",
                "clicked": True,
                "reported": False,
            },
            fetched_at=datetime.now(timezone.utc),
            tenant_id="tenant-kb4",
        )
        record = connector.normalize(raw)
        assert record.severity == "high"
        assert "phishing" in record.finding.lower()
        assert record.asset == "alice@acme.com"


# ─────────────────────────────────────────────────────────────────────────────
# Health check
# ─────────────────────────────────────────────────────────────────────────────


class TestHealthCheck:
    def test_initial_state_is_ok(self, connector):
        h = connector.health_check()
        assert isinstance(h, ConnectorHealth)
        assert h.status == "ok"
        assert h.error_count == 0
