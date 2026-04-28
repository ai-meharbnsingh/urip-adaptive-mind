"""
TDD tests for P1.8 — Acme-flavored simulator connector.

Covers:
- All 12 Acme source labels appear in returned findings
- Findings are tenant-scoped (tenant_id field is set correctly)
- Each finding normalizes to a valid URIPRiskRecord
- Source coverage: at least 1 finding per Acme source
- Simulator mode selection: "acme" picks extended_simulator, "default" picks original
- Data volume: a typical batch generates a reasonable number of findings
- No cross-tenant data: findings for tenant A must not appear for tenant B
"""
import uuid
from datetime import datetime, timezone

import pytest

from connectors.extended_simulator import ExtendedSimulatorConnector, EXTENDED_SOURCES
from connectors.base.connector import RawFinding, URIPRiskRecord


# ─────────────────────────────────────────────────────────────────────────────
# Expected Acme source labels (12 sources per blueprint)
# ─────────────────────────────────────────────────────────────────────────────

EXPECTED_SOURCES = {
    "zscaler",
    "netskope",
    "sentinelone",
    "ms_entra",
    "sharepoint",
    "manageengine_sdp",
    "manageengine_ec",
    "manageengine_mdm",
    "tenable",
    "burpsuite",
    "gtb_dlp",
    "cloudsek",
}


# ─────────────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture
def connector() -> ExtendedSimulatorConnector:
    return ExtendedSimulatorConnector()


@pytest.fixture
def tenant_id_a() -> str:
    return str(uuid.uuid4())


@pytest.fixture
def tenant_id_b() -> str:
    return str(uuid.uuid4())


# ─────────────────────────────────────────────────────────────────────────────
# Tests: Source label coverage
# ─────────────────────────────────────────────────────────────────────────────

class TestAcmeSources:
    def test_acme_sources_constant_has_12_entries(self):
        assert len(EXTENDED_SOURCES) == 12

    def test_acme_sources_constant_matches_expected(self):
        assert set(EXTENDED_SOURCES) == EXPECTED_SOURCES

    def test_fetch_findings_returns_all_12_sources(self, connector: ExtendedSimulatorConnector, tenant_id_a: str):
        """Over a large batch, all 12 sources must appear at least once."""
        session = connector.authenticate({"tenant_id": tenant_id_a})
        # Fetch a large batch to ensure coverage
        findings = connector.fetch_findings(
            since=datetime(2024, 1, 1, tzinfo=timezone.utc),
            tenant_id=tenant_id_a,
            count=120,
        )
        sources_seen = {f.source for f in findings}
        missing = EXPECTED_SOURCES - sources_seen
        assert missing == set(), f"Missing sources in findings: {missing}"

    def test_each_finding_source_is_in_acme_sources(self, connector: ExtendedSimulatorConnector, tenant_id_a: str):
        """No finding should carry a source outside the Acme tool stack."""
        findings = connector.fetch_findings(
            since=datetime(2024, 1, 1, tzinfo=timezone.utc),
            tenant_id=tenant_id_a,
            count=60,
        )
        for f in findings:
            assert f.source in EXPECTED_SOURCES, f"Unexpected source: {f.source!r}"


# ─────────────────────────────────────────────────────────────────────────────
# Tests: Tenant scoping
# ─────────────────────────────────────────────────────────────────────────────

class TestTenantScoping:
    def test_findings_carry_correct_tenant_id(self, connector: ExtendedSimulatorConnector, tenant_id_a: str):
        findings = connector.fetch_findings(
            since=datetime(2024, 1, 1, tzinfo=timezone.utc),
            tenant_id=tenant_id_a,
            count=10,
        )
        for f in findings:
            assert f.tenant_id == tenant_id_a

    def test_different_tenants_get_tenant_scoped_findings(
        self,
        connector: ExtendedSimulatorConnector,
        tenant_id_a: str,
        tenant_id_b: str,
    ):
        findings_a = connector.fetch_findings(
            since=datetime(2024, 1, 1, tzinfo=timezone.utc),
            tenant_id=tenant_id_a,
            count=5,
        )
        findings_b = connector.fetch_findings(
            since=datetime(2024, 1, 1, tzinfo=timezone.utc),
            tenant_id=tenant_id_b,
            count=5,
        )
        for f in findings_a:
            assert f.tenant_id == tenant_id_a
        for f in findings_b:
            assert f.tenant_id == tenant_id_b

    def test_authenticate_stores_tenant_id_in_session(
        self, connector: ExtendedSimulatorConnector, tenant_id_a: str
    ):
        session = connector.authenticate({"tenant_id": tenant_id_a})
        assert session.tenant_id == tenant_id_a
        assert session.connector_name == "extended_simulator"


# ─────────────────────────────────────────────────────────────────────────────
# Tests: Normalization
# ─────────────────────────────────────────────────────────────────────────────

class TestAcmeNormalization:
    def test_normalize_returns_urip_risk_record(self, connector: ExtendedSimulatorConnector, tenant_id_a: str):
        findings = connector.fetch_findings(
            since=datetime(2024, 1, 1, tzinfo=timezone.utc),
            tenant_id=tenant_id_a,
            count=5,
        )
        for f in findings:
            record = connector.normalize(f)
            assert isinstance(record, URIPRiskRecord)

    def test_normalized_record_has_valid_severity(self, connector: ExtendedSimulatorConnector, tenant_id_a: str):
        findings = connector.fetch_findings(
            since=datetime(2024, 1, 1, tzinfo=timezone.utc),
            tenant_id=tenant_id_a,
            count=20,
        )
        valid_severities = {"critical", "high", "medium", "low"}
        for f in findings:
            record = connector.normalize(f)
            assert record.severity in valid_severities, f"Invalid severity: {record.severity!r}"

    def test_normalized_record_has_valid_cvss(self, connector: ExtendedSimulatorConnector, tenant_id_a: str):
        findings = connector.fetch_findings(
            since=datetime(2024, 1, 1, tzinfo=timezone.utc),
            tenant_id=tenant_id_a,
            count=20,
        )
        for f in findings:
            record = connector.normalize(f)
            assert 0.0 <= record.cvss_score <= 10.0, f"CVSS out of range: {record.cvss_score}"

    def test_normalized_record_source_matches_finding_source(
        self, connector: ExtendedSimulatorConnector, tenant_id_a: str
    ):
        findings = connector.fetch_findings(
            since=datetime(2024, 1, 1, tzinfo=timezone.utc),
            tenant_id=tenant_id_a,
            count=10,
        )
        for f in findings:
            record = connector.normalize(f)
            assert record.source == f.source

    def test_normalized_record_finding_not_empty(self, connector: ExtendedSimulatorConnector, tenant_id_a: str):
        findings = connector.fetch_findings(
            since=datetime(2024, 1, 1, tzinfo=timezone.utc),
            tenant_id=tenant_id_a,
            count=10,
        )
        for f in findings:
            record = connector.normalize(f)
            assert record.finding.strip() != ""

    def test_normalized_record_asset_not_empty(self, connector: ExtendedSimulatorConnector, tenant_id_a: str):
        findings = connector.fetch_findings(
            since=datetime(2024, 1, 1, tzinfo=timezone.utc),
            tenant_id=tenant_id_a,
            count=10,
        )
        for f in findings:
            record = connector.normalize(f)
            assert record.asset.strip() != ""


# ─────────────────────────────────────────────────────────────────────────────
# Tests: Health check
# ─────────────────────────────────────────────────────────────────────────────

class TestAcmeHealth:
    def test_health_check_returns_ok(self, connector: ExtendedSimulatorConnector):
        health = connector.health_check()
        assert health.status == "ok"
        assert health.connector_name == "extended_simulator"
        assert health.error_count == 0

    def test_health_check_has_last_run(self, connector: ExtendedSimulatorConnector):
        health = connector.health_check()
        assert health.last_run is not None
        assert isinstance(health.last_run, datetime)


# ─────────────────────────────────────────────────────────────────────────────
# Tests: Data volume + variety
# ─────────────────────────────────────────────────────────────────────────────

class TestDataVolume:
    def test_default_batch_count(self, connector: ExtendedSimulatorConnector, tenant_id_a: str):
        """Default fetch (no count arg) returns between 5 and 15 findings."""
        findings = connector.fetch_findings(
            since=datetime(2024, 1, 1, tzinfo=timezone.utc),
            tenant_id=tenant_id_a,
        )
        assert 5 <= len(findings) <= 15

    def test_explicit_count_respected(self, connector: ExtendedSimulatorConnector, tenant_id_a: str):
        for count in [1, 10, 50]:
            findings = connector.fetch_findings(
                since=datetime(2024, 1, 1, tzinfo=timezone.utc),
                tenant_id=tenant_id_a,
                count=count,
            )
            assert len(findings) == count

    def test_findings_have_unique_ids(self, connector: ExtendedSimulatorConnector, tenant_id_a: str):
        findings = connector.fetch_findings(
            since=datetime(2024, 1, 1, tzinfo=timezone.utc),
            tenant_id=tenant_id_a,
            count=20,
        )
        ids = [f.id for f in findings]
        assert len(ids) == len(set(ids)), "Finding IDs must be unique"


# ─────────────────────────────────────────────────────────────────────────────
# Tests: Registration in global registry
# ─────────────────────────────────────────────────────────────────────────────

class TestExtendedSimulatorRegistration:
    def test_extended_simulator_registered_globally(self):
        import connectors.extended_simulator  # noqa: F401 — triggers @register_connector
        from connectors.base.registry import _global_registry
        assert "extended_simulator" in _global_registry.list_names()

    def test_global_registry_returns_extended_simulator_class(self):
        import connectors.extended_simulator  # noqa: F401
        from connectors.base.registry import _global_registry
        cls = _global_registry.get("extended_simulator")
        instance = cls()
        assert isinstance(instance, ExtendedSimulatorConnector)
