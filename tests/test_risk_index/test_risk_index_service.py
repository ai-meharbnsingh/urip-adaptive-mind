"""
Tests for RiskIndexService — TrendAI-style 0-100 Cyber Risk Index.

Covers:
  - 0-100 score correctness across various tenant data shapes
  - Level cutoffs exactly at 30 / 60 / 80
  - 3 sub-indexes (Exposure / Attack / Security Configuration) per source category
  - 5-bucket domain breakdown (Devices / Internet-Facing / Accounts / Applications / Cloud Assets)
  - Empty tenant returns 0 + level=low
  - Tenant isolation (tenant A's risks don't affect tenant B's index)

INV-4: Tests actually execute service code against the in-memory SQLite DB.
INV-6: Test expectations are NEVER changed to make tests pass.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest

from backend.models.risk import Risk
from backend.services.risk_index_service import (
    DomainBreakdown,
    RiskIndex,
    RiskIndexService,
    Subindex,
    Subindexes,
    classify_level,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_risk(
    tenant_id: uuid.UUID,
    severity: str = "high",
    status: str = "open",
    source: str = "crowdstrike",
    domain: str = "network",
    composite_score: float | None = 7.0,
    in_kev_catalog: bool = False,
) -> Risk:
    now = datetime.now(timezone.utc)
    return Risk(
        id=uuid.uuid4(),
        risk_id=f"RISK-IDX-{uuid.uuid4().hex[:6].upper()}",
        finding=f"Risk-index test finding {uuid.uuid4().hex[:4]}",
        source=source,
        domain=domain,
        cvss_score=7.5,
        severity=severity,
        asset="server.test",
        owner_team="Security",
        status=status,
        sla_deadline=now + timedelta(days=7),
        tenant_id=tenant_id,
        composite_score=composite_score,
        in_kev_catalog=in_kev_catalog,
    )


# ---------------------------------------------------------------------------
# classify_level — pure function
# ---------------------------------------------------------------------------


def test_classify_level_low_at_zero():
    assert classify_level(0.0) == "low"


def test_classify_level_low_just_below_30():
    assert classify_level(29.99) == "low"


def test_classify_level_medium_at_exactly_30():
    """Cutoff at 30: anything >= 30 and < 60 is medium."""
    assert classify_level(30.0) == "medium"


def test_classify_level_high_at_exactly_60():
    """Cutoff at 60: anything >= 60 and < 80 is high."""
    assert classify_level(60.0) == "high"


def test_classify_level_critical_at_exactly_80():
    """Cutoff at 80: anything >= 80 is critical."""
    assert classify_level(80.0) == "critical"


def test_classify_level_critical_at_max():
    assert classify_level(100.0) == "critical"


# ---------------------------------------------------------------------------
# compute_risk_index_0_100
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_compute_index_empty_tenant_returns_zero(db_session, default_tenant):
    """Empty tenant → score = 0.0, level = low."""
    svc = RiskIndexService(db_session)
    idx = await svc.compute_risk_index_0_100(default_tenant.id)
    assert isinstance(idx, RiskIndex)
    assert idx.score == 0.0
    assert idx.level == "low"
    assert idx.color_code == "green"


@pytest.mark.asyncio
async def test_compute_index_base_score_only(db_session, default_tenant):
    """Single low-severity open risk with composite_score=2.0 → base = 2.0 * 10 = 20.0 → low."""
    tid = default_tenant.id
    db_session.add(_make_risk(tid, severity="low", composite_score=2.0))
    await db_session.commit()

    svc = RiskIndexService(db_session)
    idx = await svc.compute_risk_index_0_100(tid)

    # base = mean(2.0) * 10 = 20.0; no severity bonus (low has no weight); no KEV
    assert idx.score == 20.0
    assert idx.level == "low"


@pytest.mark.asyncio
async def test_compute_index_severity_bonus_critical(db_session, default_tenant):
    """Two critical risks bump base score: critical_count * 0.5 added."""
    tid = default_tenant.id
    # Two critical risks with composite_score=5.0 → base = 50.0
    db_session.add(_make_risk(tid, severity="critical", composite_score=5.0))
    db_session.add(_make_risk(tid, severity="critical", composite_score=5.0))
    await db_session.commit()

    svc = RiskIndexService(db_session)
    idx = await svc.compute_risk_index_0_100(tid)

    # base = 5.0 * 10 = 50.0; critical_bonus = 2 * 0.5 = 1.0 → 51.0
    assert idx.score == 51.0
    assert idx.level == "medium"


@pytest.mark.asyncio
async def test_compute_index_severity_bonus_high(db_session, default_tenant):
    """High-severity bonus: high_count * 0.2."""
    tid = default_tenant.id
    for _ in range(5):
        db_session.add(_make_risk(tid, severity="high", composite_score=6.0))
    await db_session.commit()

    svc = RiskIndexService(db_session)
    idx = await svc.compute_risk_index_0_100(tid)

    # base = 6.0 * 10 = 60.0; high_bonus = 5 * 0.2 = 1.0 → 61.0
    assert idx.score == 61.0
    assert idx.level == "high"


@pytest.mark.asyncio
async def test_compute_index_kev_bonus(db_session, default_tenant):
    """KEV active count bonus: kev_count * 1.0 added."""
    tid = default_tenant.id
    db_session.add(_make_risk(tid, severity="medium", composite_score=4.0, in_kev_catalog=True))
    db_session.add(_make_risk(tid, severity="medium", composite_score=4.0, in_kev_catalog=True))
    db_session.add(_make_risk(tid, severity="medium", composite_score=4.0, in_kev_catalog=True))
    await db_session.commit()

    svc = RiskIndexService(db_session)
    idx = await svc.compute_risk_index_0_100(tid)

    # base = 4.0 * 10 = 40.0; KEV bonus = 3 * 1.0 = 3.0 → 43.0
    assert idx.score == 43.0
    assert idx.level == "medium"


@pytest.mark.asyncio
async def test_compute_index_capped_at_100(db_session, default_tenant):
    """Score is capped at 100 even if formula exceeds."""
    tid = default_tenant.id
    # 30 critical risks all with composite=10.0 + KEV
    for _ in range(30):
        db_session.add(_make_risk(
            tid, severity="critical", composite_score=10.0, in_kev_catalog=True
        ))
    await db_session.commit()

    svc = RiskIndexService(db_session)
    idx = await svc.compute_risk_index_0_100(tid)

    # base = 100; +15 critical_bonus +30 KEV → way over, capped at 100
    assert idx.score == 100.0
    assert idx.level == "critical"
    assert idx.color_code == "red"


@pytest.mark.asyncio
async def test_compute_index_excludes_closed_risks(db_session, default_tenant):
    """Closed risks must NOT contribute to the index."""
    tid = default_tenant.id
    # One open low risk
    db_session.add(_make_risk(tid, severity="low", status="open", composite_score=1.0))
    # Many closed criticals — should NOT count
    for _ in range(5):
        db_session.add(_make_risk(
            tid, severity="critical", status="closed", composite_score=10.0,
            in_kev_catalog=True,
        ))
    await db_session.commit()

    svc = RiskIndexService(db_session)
    idx = await svc.compute_risk_index_0_100(tid)

    # Only the single open low: base = 1 * 10 = 10 → low
    assert idx.score == 10.0
    assert idx.level == "low"


@pytest.mark.asyncio
async def test_compute_index_tenant_isolation(db_session, default_tenant):
    """Other tenants' risks must never affect this tenant's index."""
    from backend.models.tenant import Tenant
    tid_a = default_tenant.id

    other = Tenant(
        id=uuid.uuid4(), name="Other", slug="other-tenant",
        domain="other.test", is_active=True, settings={},
    )
    db_session.add(other)
    await db_session.commit()

    # Other tenant has 10 critical KEV risks
    for _ in range(10):
        db_session.add(_make_risk(
            other.id, severity="critical", composite_score=10.0, in_kev_catalog=True,
        ))
    # Default tenant has 1 low risk
    db_session.add(_make_risk(tid_a, severity="low", composite_score=2.0))
    await db_session.commit()

    svc = RiskIndexService(db_session)
    idx_a = await svc.compute_risk_index_0_100(tid_a)
    idx_b = await svc.compute_risk_index_0_100(other.id)

    assert idx_a.score == 20.0
    assert idx_a.level == "low"
    # Other tenant: base 100 + 5 critical bonus + 10 kev → capped at 100
    assert idx_b.score == 100.0
    assert idx_b.level == "critical"


# ---------------------------------------------------------------------------
# compute_subindexes
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_compute_subindexes_exposure_attack_security(db_session, default_tenant):
    """Each subindex aggregates its own connector source bucket independently."""
    tid = default_tenant.id

    # Exposure: tenable / easm / cloudsek (per task; cloudsek -> attack actually,
    # tenable + easm are the canonical exposure sources)
    db_session.add(_make_risk(tid, source="tenable", composite_score=8.0, severity="high"))
    db_session.add(_make_risk(tid, source="easm", composite_score=6.0, severity="medium"))
    # Attack: sentinelone / crowdstrike / siem / gtb / ms_entra
    db_session.add(_make_risk(tid, source="sentinelone", composite_score=5.0, severity="medium"))
    db_session.add(_make_risk(tid, source="crowdstrike", composite_score=7.0, severity="high"))
    # Security configuration: aws_cspm / azure_cspm / gcp_cspm / manageengine_ec / manageengine_mdm / fortiguard_fw
    db_session.add(_make_risk(tid, source="aws_cspm", composite_score=4.0, severity="medium"))
    await db_session.commit()

    svc = RiskIndexService(db_session)
    subs = await svc.compute_subindexes(tid)

    assert isinstance(subs, Subindexes)
    assert isinstance(subs.exposure, Subindex)
    assert isinstance(subs.attack, Subindex)
    assert isinstance(subs.security_config, Subindex)

    # Exposure: mean(8,6) * 10 = 70 → high
    assert subs.exposure.score == 70.0
    assert subs.exposure.level == "high"
    assert subs.exposure.contributing_count == 2
    # Attack: mean(5,7) * 10 = 60 → high (60 cutoff)
    assert subs.attack.score == 60.0
    assert subs.attack.level == "high"
    assert subs.attack.contributing_count == 2
    # Security config: mean(4) * 10 = 40 → medium
    assert subs.security_config.score == 40.0
    assert subs.security_config.level == "medium"
    assert subs.security_config.contributing_count == 1


@pytest.mark.asyncio
async def test_compute_subindexes_zero_when_empty_bucket(db_session, default_tenant):
    """A subindex with no contributing risks is 0.0 / low / 0."""
    tid = default_tenant.id
    # Only a tenable risk → exposure populated, others empty
    db_session.add(_make_risk(tid, source="tenable", composite_score=5.0))
    await db_session.commit()

    svc = RiskIndexService(db_session)
    subs = await svc.compute_subindexes(tid)

    assert subs.exposure.contributing_count == 1
    assert subs.attack.contributing_count == 0
    assert subs.attack.score == 0.0
    assert subs.attack.level == "low"
    assert subs.security_config.contributing_count == 0
    assert subs.security_config.score == 0.0


@pytest.mark.asyncio
async def test_compute_subindexes_excludes_closed(db_session, default_tenant):
    """Closed risks excluded from subindexes."""
    tid = default_tenant.id
    db_session.add(_make_risk(tid, source="tenable", composite_score=10.0, status="closed"))
    db_session.add(_make_risk(tid, source="tenable", composite_score=3.0, status="open"))
    await db_session.commit()

    svc = RiskIndexService(db_session)
    subs = await svc.compute_subindexes(tid)
    # Only the open one (3.0) contributes: 3.0 * 10 = 30
    assert subs.exposure.contributing_count == 1
    assert subs.exposure.score == 30.0


# ---------------------------------------------------------------------------
# compute_domain_breakdown
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_compute_domain_breakdown_5_buckets(db_session, default_tenant):
    """5 buckets: devices, internet_facing, accounts, applications, cloud_assets."""
    tid = default_tenant.id

    # Devices: VM/EDR/UEM/MDM
    db_session.add(_make_risk(tid, source="crowdstrike", composite_score=7.0, severity="high"))
    db_session.add(_make_risk(tid, source="sentinelone", composite_score=8.0, severity="critical"))
    db_session.add(_make_risk(tid, source="tenable", composite_score=6.0, severity="medium"))
    db_session.add(_make_risk(tid, source="manageengine_mdm", composite_score=5.0, severity="medium"))
    # Internet-facing: EASM
    db_session.add(_make_risk(tid, source="easm", composite_score=9.0, severity="critical"))
    # Accounts: Identity / PAM
    db_session.add(_make_risk(tid, source="ms_entra", composite_score=4.0, severity="medium"))
    db_session.add(_make_risk(tid, source="cyberark_pam", composite_score=3.0, severity="low"))
    # Applications: DAST/Application
    db_session.add(_make_risk(tid, source="burp_enterprise", composite_score=7.5, severity="high"))
    db_session.add(_make_risk(tid, source="bug_bounty", composite_score=6.5, severity="medium"))
    # Cloud assets: CSPM
    db_session.add(_make_risk(tid, source="aws_cspm", composite_score=8.5, severity="critical"))
    db_session.add(_make_risk(tid, source="azure_cspm", composite_score=7.0, severity="high"))
    await db_session.commit()

    svc = RiskIndexService(db_session)
    breakdown = await svc.compute_domain_breakdown(tid)

    assert isinstance(breakdown, DomainBreakdown)

    assert breakdown.devices.total == 4
    assert breakdown.devices.critical_count == 1
    assert breakdown.devices.high_count == 1

    assert breakdown.internet_facing.total == 1
    assert breakdown.internet_facing.critical_count == 1

    assert breakdown.accounts.total == 2
    assert breakdown.accounts.critical_count == 0

    assert breakdown.applications.total == 2
    assert breakdown.applications.high_count == 1

    assert breakdown.cloud_assets.total == 2
    assert breakdown.cloud_assets.critical_count == 1
    assert breakdown.cloud_assets.high_count == 1


@pytest.mark.asyncio
async def test_compute_domain_breakdown_empty(db_session, default_tenant):
    """Empty tenant: every bucket is zero."""
    tid = default_tenant.id
    svc = RiskIndexService(db_session)
    breakdown = await svc.compute_domain_breakdown(tid)

    for bucket in (
        breakdown.devices,
        breakdown.internet_facing,
        breakdown.accounts,
        breakdown.applications,
        breakdown.cloud_assets,
    ):
        assert bucket.total == 0
        assert bucket.critical_count == 0
        assert bucket.high_count == 0
        assert bucket.mean_score == 0.0
        assert bucket.level == "low"


@pytest.mark.asyncio
async def test_compute_domain_breakdown_uses_risk_domain_field_first(db_session, default_tenant):
    """If Risk.domain explicitly set to a recognised value, that wins over connector category fallback."""
    tid = default_tenant.id
    # Source is crowdstrike (would map to Devices via category) but domain says "cloud"
    # The expected behaviour: an explicit Risk.domain value matches its bucket if it
    # cleanly maps. Otherwise fall back to source-based mapping.
    db_session.add(_make_risk(tid, source="crowdstrike", domain="cloud", composite_score=5.0))
    await db_session.commit()

    svc = RiskIndexService(db_session)
    breakdown = await svc.compute_domain_breakdown(tid)

    # Risk.domain="cloud" maps cleanly → cloud_assets bucket
    assert breakdown.cloud_assets.total == 1
    assert breakdown.devices.total == 0


@pytest.mark.asyncio
async def test_compute_domain_breakdown_tenant_isolation(db_session, default_tenant):
    """Tenant B's risks must not appear in Tenant A's breakdown."""
    from backend.models.tenant import Tenant

    tid_a = default_tenant.id
    other = Tenant(
        id=uuid.uuid4(), name="Other", slug="other-bk",
        domain="other-bk.test", is_active=True, settings={},
    )
    db_session.add(other)
    await db_session.commit()

    db_session.add(_make_risk(tid_a, source="crowdstrike", composite_score=5.0))
    db_session.add(_make_risk(other.id, source="crowdstrike", composite_score=5.0))
    db_session.add(_make_risk(other.id, source="aws_cspm", composite_score=5.0))
    await db_session.commit()

    svc = RiskIndexService(db_session)
    bk_a = await svc.compute_domain_breakdown(tid_a)
    bk_b = await svc.compute_domain_breakdown(other.id)

    assert bk_a.devices.total == 1
    assert bk_a.cloud_assets.total == 0
    assert bk_b.devices.total == 1
    assert bk_b.cloud_assets.total == 1


# ---------------------------------------------------------------------------
# Connector RISK_INDEX_DOMAIN attribute backfill
# ---------------------------------------------------------------------------


def test_base_connector_has_risk_index_domain_attr():
    from connectors.base.connector import BaseConnector
    assert hasattr(BaseConnector, "RISK_INDEX_DOMAIN")
    # Default is None
    assert BaseConnector.RISK_INDEX_DOMAIN is None


def test_aws_cspm_risk_index_domain_is_security_config():
    from connectors.aws_cspm.connector import AwsCspmConnector
    assert AwsCspmConnector.RISK_INDEX_DOMAIN == "security_config"


def test_tenable_risk_index_domain_is_exposure():
    from connectors.tenable.connector import TenableConnector
    assert TenableConnector.RISK_INDEX_DOMAIN == "exposure"


def test_easm_risk_index_domain_is_exposure():
    from connectors.easm.connector import EasmConnector
    assert EasmConnector.RISK_INDEX_DOMAIN == "exposure"


def test_sentinelone_risk_index_domain_is_attack():
    from connectors.sentinelone.connector import SentinelOneConnector
    assert SentinelOneConnector.RISK_INDEX_DOMAIN == "attack"


def test_crowdstrike_risk_index_domain_is_attack():
    from connectors.crowdstrike.connector import CrowdStrikeConnector
    assert CrowdStrikeConnector.RISK_INDEX_DOMAIN == "attack"


def test_ms_entra_risk_index_domain_is_attack():
    from connectors.ms_entra.connector import MsEntraConnector
    assert MsEntraConnector.RISK_INDEX_DOMAIN == "attack"


def test_siem_risk_index_domain_is_attack():
    from connectors.siem.connector import SiemConnector
    assert SiemConnector.RISK_INDEX_DOMAIN == "attack"


def test_gtb_risk_index_domain_is_attack():
    from connectors.gtb.connector import GTBConnector
    assert GTBConnector.RISK_INDEX_DOMAIN == "attack"


def test_azure_cspm_risk_index_domain_is_security_config():
    from connectors.azure_cspm.connector import AzureCspmConnector
    assert AzureCspmConnector.RISK_INDEX_DOMAIN == "security_config"


def test_gcp_cspm_risk_index_domain_is_security_config():
    from connectors.gcp_cspm.connector import GcpCspmConnector
    assert GcpCspmConnector.RISK_INDEX_DOMAIN == "security_config"


def test_manageengine_ec_risk_index_domain_is_security_config():
    from connectors.manageengine_ec.connector import ManageEngineECConnector
    assert ManageEngineECConnector.RISK_INDEX_DOMAIN == "security_config"


def test_manageengine_mdm_risk_index_domain_is_security_config():
    from connectors.manageengine_mdm.connector import ManageEngineMDMConnector
    assert ManageEngineMDMConnector.RISK_INDEX_DOMAIN == "security_config"


def test_fortiguard_fw_risk_index_domain_is_security_config():
    from connectors.fortiguard_fw.connector import FortiguardFirewallConnector
    assert FortiguardFirewallConnector.RISK_INDEX_DOMAIN == "security_config"
