"""
TDD tests for P1.6 Connector Framework Abstraction.

Covers:
- Abstract Connector base class contract (authenticate, fetch_findings, normalize, health_check)
- ConnectorRegistry: @register_connector decorator + lookup
- ConnectorScheduler: async periodic tick — calls fetch_findings for each registered, enabled connector
- Simulator connector registered and returning normalized URIPRiskRecord-compatible dicts
"""
import asyncio
import uuid
from datetime import datetime, timezone
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ─── Base class / registry ────────────────────────────────────────────────────
from connectors.base.connector import (
    BaseConnector,
    ConnectorHealth,
    ConnectorSession,
    RawFinding,
    URIPRiskRecord,
)
from connectors.base.registry import ConnectorRegistry, register_connector
from connectors.base.scheduler import ConnectorScheduler


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

class _ConcreteConnector(BaseConnector):
    """Minimal concrete implementation — used to verify abstract contract."""

    NAME = "test_connector"

    def authenticate(self, tenant_credentials: dict) -> ConnectorSession:
        return ConnectorSession(
            connector_name=self.NAME,
            tenant_id=tenant_credentials.get("tenant_id", "test-tenant"),
            token="test-token",
            expires_at=datetime.now(timezone.utc),
        )

    def fetch_findings(self, since: datetime) -> list[RawFinding]:
        return [
            RawFinding(
                id="FIND-001",
                source=self.NAME,
                raw_data={
                    "cve_id": "CVE-2024-0001",
                    "title": "Test Vulnerability",
                    "cvss": 7.5,
                    "severity": "high",
                    "asset": "test-server-01",
                    "domain": "endpoint",
                },
                fetched_at=datetime.now(timezone.utc),
                tenant_id="test-tenant",
            )
        ]

    def normalize(self, raw: RawFinding) -> URIPRiskRecord:
        d = raw.raw_data
        return URIPRiskRecord(
            finding=d["title"],
            description=f"[{d['cve_id']}] {d['title']}",
            source=raw.source,
            domain=d["domain"],
            cvss_score=d["cvss"],
            severity=d["severity"],
            asset=d["asset"],
            owner_team="Infra Team",
            cve_id=d["cve_id"],
        )

    def health_check(self) -> ConnectorHealth:
        return ConnectorHealth(
            connector_name=self.NAME,
            status="ok",
            last_run=datetime.now(timezone.utc),
            error_count=0,
        )


# ─────────────────────────────────────────────────────────────────────────────
# Tests: BaseConnector abstract interface
# ─────────────────────────────────────────────────────────────────────────────

class TestBaseConnectorInterface:
    def test_cannot_instantiate_abstract_base(self):
        """BaseConnector is abstract — must not instantiate directly."""
        with pytest.raises(TypeError):
            BaseConnector()  # type: ignore[abstract]

    def test_concrete_connector_instantiates(self):
        c = _ConcreteConnector()
        assert c is not None

    def test_authenticate_returns_connector_session(self):
        c = _ConcreteConnector()
        session = c.authenticate({"tenant_id": "tenant-abc"})
        assert isinstance(session, ConnectorSession)
        assert session.connector_name == "test_connector"
        assert session.tenant_id == "tenant-abc"
        assert session.token == "test-token"

    def test_fetch_findings_returns_list_of_raw_findings(self):
        c = _ConcreteConnector()
        since = datetime(2024, 1, 1, tzinfo=timezone.utc)
        findings = c.fetch_findings(since)
        assert isinstance(findings, list)
        assert len(findings) >= 1
        assert isinstance(findings[0], RawFinding)

    def test_raw_finding_has_required_fields(self):
        c = _ConcreteConnector()
        findings = c.fetch_findings(datetime.now(timezone.utc))
        f = findings[0]
        assert f.id == "FIND-001"
        assert f.source == "test_connector"
        assert isinstance(f.raw_data, dict)
        assert isinstance(f.fetched_at, datetime)
        assert f.tenant_id == "test-tenant"

    def test_normalize_returns_urip_risk_record(self):
        c = _ConcreteConnector()
        findings = c.fetch_findings(datetime.now(timezone.utc))
        record = c.normalize(findings[0])
        assert isinstance(record, URIPRiskRecord)
        assert record.finding == "Test Vulnerability"
        assert record.source == "test_connector"
        assert record.cvss_score == 7.5
        assert record.severity == "high"
        assert record.domain == "endpoint"
        assert record.cve_id == "CVE-2024-0001"

    def test_urip_risk_record_fields_align_with_risk_model(self):
        """URIPRiskRecord must have all fields required by the Risk SQLAlchemy model."""
        record = URIPRiskRecord(
            finding="Some finding",
            description="Some description",
            source="test_connector",
            domain="cloud",
            cvss_score=9.8,
            severity="critical",
            asset="test-asset",
            owner_team="Cloud Team",
            cve_id=None,
        )
        # Fields that map directly to Risk columns
        assert hasattr(record, "finding")
        assert hasattr(record, "description")
        assert hasattr(record, "source")
        assert hasattr(record, "domain")
        assert hasattr(record, "cvss_score")
        assert hasattr(record, "severity")
        assert hasattr(record, "asset")
        assert hasattr(record, "owner_team")
        assert hasattr(record, "cve_id")

    def test_health_check_returns_connector_health(self):
        c = _ConcreteConnector()
        health = c.health_check()
        assert isinstance(health, ConnectorHealth)
        assert health.connector_name == "test_connector"
        assert health.status in ("ok", "degraded", "error")
        assert isinstance(health.error_count, int)

    def test_connector_health_ok_status(self):
        c = _ConcreteConnector()
        health = c.health_check()
        assert health.status == "ok"
        assert health.error_count == 0
        assert health.last_run is not None

    def test_connector_health_error_state(self):
        """ConnectorHealth can represent an error state."""
        health = ConnectorHealth(
            connector_name="bad_connector",
            status="error",
            last_run=None,
            error_count=5,
            last_error="Connection refused",
        )
        assert health.status == "error"
        assert health.error_count == 5
        assert health.last_error == "Connection refused"
        assert health.last_run is None


# ─────────────────────────────────────────────────────────────────────────────
# Tests: ConnectorRegistry
# ─────────────────────────────────────────────────────────────────────────────

class TestConnectorRegistry:
    def setup_method(self):
        """Each test gets a fresh registry."""
        self.registry = ConnectorRegistry()

    def test_register_and_lookup(self):
        self.registry.register("my_connector", _ConcreteConnector)
        cls = self.registry.get("my_connector")
        assert cls is _ConcreteConnector

    def test_lookup_unknown_raises_key_error(self):
        with pytest.raises(KeyError):
            self.registry.get("nonexistent_connector")

    def test_list_names_returns_registered(self):
        self.registry.register("alpha", _ConcreteConnector)
        self.registry.register("beta", _ConcreteConnector)
        names = self.registry.list_names()
        assert "alpha" in names
        assert "beta" in names

    def test_double_registration_raises_value_error(self):
        self.registry.register("dup", _ConcreteConnector)
        with pytest.raises(ValueError):
            self.registry.register("dup", _ConcreteConnector)

    def test_register_connector_decorator_registers_with_global_registry(self):
        """@register_connector("name") adds to the module-level registry."""
        @register_connector("decorated_test_connector")
        class _Decorated(_ConcreteConnector):
            NAME = "decorated_test_connector"

        from connectors.base.registry import _global_registry
        assert "decorated_test_connector" in _global_registry.list_names()

    def test_instantiate_registered_connector(self):
        self.registry.register("my_connector2", _ConcreteConnector)
        cls = self.registry.get("my_connector2")
        instance = cls()
        assert isinstance(instance, BaseConnector)


# ─────────────────────────────────────────────────────────────────────────────
# Tests: ConnectorScheduler
# ─────────────────────────────────────────────────────────────────────────────

class TestConnectorScheduler:
    """Test the scheduler's tick semantics without real async I/O."""

    @pytest.mark.asyncio
    async def test_tick_calls_fetch_and_normalize_for_enabled_connector(self):
        """A scheduler tick must call fetch_findings + normalize for each enabled connector."""
        connector_instance = _ConcreteConnector()
        connector_instance.fetch_findings = MagicMock(wraps=connector_instance.fetch_findings)
        connector_instance.normalize = MagicMock(wraps=connector_instance.normalize)

        registry = ConnectorRegistry()
        registry.register("test_connector", lambda: connector_instance)

        tenant_config = {
            "tenant_id": str(uuid.uuid4()),
            "enabled_connectors": ["test_connector"],
            "simulator_mode": "off",
            "connector_credentials": {
                "test_connector": {"tenant_id": "tenant-xyz"},
            },
        }

        scheduler = ConnectorScheduler(registry=registry)
        results = await scheduler.tick(tenant_config)

        connector_instance.fetch_findings.assert_called_once()
        assert connector_instance.normalize.call_count >= 1
        assert len(results) >= 1
        for r in results:
            assert isinstance(r, URIPRiskRecord)

    @pytest.mark.asyncio
    async def test_tick_skips_disabled_connectors(self):
        """A connector not in enabled_connectors must not be called."""
        connector_instance = _ConcreteConnector()
        connector_instance.fetch_findings = MagicMock(wraps=connector_instance.fetch_findings)

        registry = ConnectorRegistry()
        registry.register("disabled_conn", lambda: connector_instance)

        tenant_config = {
            "tenant_id": str(uuid.uuid4()),
            "enabled_connectors": [],  # nothing enabled
            "connector_credentials": {},
        }

        scheduler = ConnectorScheduler(registry=registry)
        results = await scheduler.tick(tenant_config)

        connector_instance.fetch_findings.assert_not_called()
        assert results == []

    @pytest.mark.asyncio
    async def test_tick_returns_empty_for_empty_findings(self):
        """If a connector returns no findings, tick result is empty list."""
        connector_instance = _ConcreteConnector()
        connector_instance.fetch_findings = MagicMock(return_value=[])

        registry = ConnectorRegistry()
        registry.register("empty_conn", lambda: connector_instance)

        tenant_config = {
            "tenant_id": str(uuid.uuid4()),
            "enabled_connectors": ["empty_conn"],
            "connector_credentials": {"empty_conn": {}},
        }

        scheduler = ConnectorScheduler(registry=registry)
        results = await scheduler.tick(tenant_config)
        assert results == []

    @pytest.mark.asyncio
    async def test_tick_handles_connector_error_gracefully(self):
        """If one connector raises, others still run; erroring one is skipped."""
        good_connector = _ConcreteConnector()
        bad_connector = _ConcreteConnector()
        bad_connector.fetch_findings = MagicMock(side_effect=RuntimeError("API down"))

        registry = ConnectorRegistry()
        registry.register("good_conn", lambda: good_connector)
        registry.register("bad_conn", lambda: bad_connector)

        tenant_config = {
            "tenant_id": str(uuid.uuid4()),
            "enabled_connectors": ["good_conn", "bad_conn"],
            "connector_credentials": {
                "good_conn": {"tenant_id": "t"},
                "bad_conn": {"tenant_id": "t"},
            },
        }

        scheduler = ConnectorScheduler(registry=registry)
        results = await scheduler.tick(tenant_config)
        # Good connector's findings still come through
        assert len(results) >= 1


# ─────────────────────────────────────────────────────────────────────────────
# Tests: Simulator connector registered in global registry
# ─────────────────────────────────────────────────────────────────────────────

class TestSimulatorConnectorRegistration:
    def test_simulator_registered_in_global_registry(self):
        """backend.simulator must register itself as 'simulator' via the framework."""
        # Importing the module triggers registration
        import connectors.simulator_connector  # noqa: F401
        from connectors.base.registry import _global_registry
        assert "simulator" in _global_registry.list_names()

    def test_simulator_connector_returns_normalized_findings(self):
        from connectors.base.registry import _global_registry
        import connectors.simulator_connector  # noqa: F401

        cls = _global_registry.get("simulator")
        instance = cls()
        since = datetime(2024, 1, 1, tzinfo=timezone.utc)
        findings = instance.fetch_findings(since)
        assert len(findings) > 0

        record = instance.normalize(findings[0])
        assert isinstance(record, URIPRiskRecord)
        assert record.source in (
            "crowdstrike", "easm", "cnapp", "armis", "vapt",
            "threat_intel", "cert_in", "bug_bounty", "soc",
        )
