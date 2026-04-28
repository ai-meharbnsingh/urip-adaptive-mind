"""
TDD — Full seeder run_all test.

Verifies all 15 frameworks load without conflict when run together,
and that each has the expected minimum control count.
"""
import pytest
from sqlalchemy import select, func

from compliance_backend.models.framework import Framework, FrameworkVersion, Control
# Original 7
from compliance_backend.seeders.soc2 import seed_soc2
from compliance_backend.seeders.iso27001 import seed_iso27001
from compliance_backend.seeders.gdpr import seed_gdpr
from compliance_backend.seeders.hipaa import seed_hipaa
from compliance_backend.seeders.pci_dss import seed_pci_dss
from compliance_backend.seeders.india_dpdp import seed_india_dpdp
from compliance_backend.seeders.nist_csf import seed_nist_csf
# New 8 (Phase 2C)
from compliance_backend.seeders.iso42001 import seed_iso42001
from compliance_backend.seeders.eu_ai_act import seed_eu_ai_act
from compliance_backend.seeders.dora import seed_dora
from compliance_backend.seeders.nis2 import seed_nis2
from compliance_backend.seeders.iso27017 import seed_iso27017
from compliance_backend.seeders.iso27018 import seed_iso27018
from compliance_backend.seeders.iso27701 import seed_iso27701
from compliance_backend.seeders.cis_v8 import seed_cis_v8
# Cross mappings
from compliance_backend.seeders.cross_mappings import seed_cross_mappings


# Minimum control counts each framework must contribute.
EXPECTED_MINIMUMS = {
    # Original 7
    "SOC2": 30,
    "ISO27001": 50,
    "GDPR": 35,
    "HIPAA": 40,
    "PCIDSS": 60,
    "DPDP": 25,
    "NISTCSF": 60,
    # New 8 (Phase 2C)
    "ISO42001": 40,
    "EUAIACT": 30,
    "DORA": 50,
    "NIS2": 80,
    "ISO27017": 37,
    "ISO27018": 25,
    "ISO27701": 50,
    "CISV8": 110,
}


async def _seed_all_15(session):
    """Seed all 15 frameworks (original 7 + new 8) plus cross-mappings."""
    # Original 7
    await seed_soc2(session)
    await seed_iso27001(session)
    await seed_gdpr(session)
    await seed_hipaa(session)
    await seed_pci_dss(session)
    await seed_india_dpdp(session)
    await seed_nist_csf(session)
    # New 8
    await seed_iso42001(session)
    await seed_eu_ai_act(session)
    await seed_dora(session)
    await seed_nis2(session)
    await seed_iso27017(session)
    await seed_iso27018(session)
    await seed_iso27701(session)
    await seed_cis_v8(session)
    # Cross-mappings (must run after all framework seeders)
    await seed_cross_mappings(session)


@pytest.mark.anyio
async def test_all_15_frameworks_load_without_conflict(db_session):
    """All 15 framework seeders run without errors or DB conflicts."""
    await _seed_all_15(db_session)

    for short_code in EXPECTED_MINIMUMS:
        result = await db_session.execute(
            select(Framework).where(Framework.short_code == short_code)
        )
        fw = result.scalars().first()
        assert fw is not None, f"Framework {short_code} not found after seeding all 15 seeders"


@pytest.mark.anyio
async def test_all_frameworks_meet_minimum_control_counts(db_session):
    """Every framework meets its minimum control count requirement."""
    await _seed_all_15(db_session)

    for short_code, minimum in EXPECTED_MINIMUMS.items():
        fw_result = await db_session.execute(
            select(Framework).where(Framework.short_code == short_code)
        )
        framework = fw_result.scalars().first()
        assert framework is not None, f"Framework {short_code} not found"

        ver_result = await db_session.execute(
            select(FrameworkVersion).where(FrameworkVersion.framework_id == framework.id)
        )
        versions = ver_result.scalars().all()

        total = 0
        for version in versions:
            cnt_result = await db_session.execute(
                select(func.count()).where(Control.framework_version_id == version.id)
            )
            total += cnt_result.scalar()

        assert total >= minimum, (
            f"{short_code}: expected >= {minimum} controls, found {total}"
        )


@pytest.mark.anyio
async def test_short_codes_are_unique_across_all_frameworks(db_session):
    """Each framework short_code must be unique in the DB."""
    await _seed_all_15(db_session)

    codes_result = await db_session.execute(select(Framework.short_code))
    codes = codes_result.scalars().all()
    # Filter to only the 15 we expect — other tests may have seeded extras into the
    # session-scoped DB. Within our 15 we should have no duplicates.
    expected = set(EXPECTED_MINIMUMS.keys())
    target = [c for c in codes if c in expected]
    assert len(target) == len(set(target)), (
        f"Duplicate short_codes found among expected 15: "
        f"{[c for c in target if target.count(c) > 1]}"
    )


@pytest.mark.anyio
async def test_running_all_seeders_twice_is_idempotent(db_session):
    """Running all 15 seeders twice must not create any duplicate records."""
    for _ in range(2):
        await _seed_all_15(db_session)

    # Each of the 15 target short_codes must appear exactly once (idempotency)
    for short_code in EXPECTED_MINIMUMS:
        count_result = await db_session.execute(
            select(func.count()).select_from(Framework).where(Framework.short_code == short_code)
        )
        count = count_result.scalar()
        assert count == 1, (
            f"Expected exactly 1 '{short_code}' framework after double-seeding, found {count}"
        )


@pytest.mark.anyio
async def test_total_control_count_at_least_846(db_session):
    """The 15 seeded frameworks must contribute at least 846 controls in total."""
    await _seed_all_15(db_session)

    total = 0
    for short_code in EXPECTED_MINIMUMS:
        fw_result = await db_session.execute(
            select(Framework).where(Framework.short_code == short_code)
        )
        framework = fw_result.scalars().first()
        ver_result = await db_session.execute(
            select(FrameworkVersion).where(FrameworkVersion.framework_id == framework.id)
        )
        versions = ver_result.scalars().all()
        for version in versions:
            cnt_result = await db_session.execute(
                select(func.count()).where(Control.framework_version_id == version.id)
            )
            total += cnt_result.scalar()

    assert total >= 846, (
        f"Total controls across 15 frameworks = {total}, expected >= 846"
    )


@pytest.mark.anyio
async def test_cross_mappings_include_new_framework_links(db_session):
    """At least 30 cross-mappings must touch the new 8 frameworks."""
    from compliance_backend.models.framework import FrameworkControlMapping
    await _seed_all_15(db_session)

    new_codes = {"ISO42001", "EUAIACT", "DORA", "NIS2", "ISO27017", "ISO27018", "ISO27701", "CISV8"}

    # Build a map of control_id -> framework short_code
    fw_q = await db_session.execute(
        select(Framework.id, Framework.short_code, FrameworkVersion.id)
        .join(FrameworkVersion, FrameworkVersion.framework_id == Framework.id)
    )
    version_to_code = {ver_id: code for _, code, ver_id in fw_q.all()}

    ctrl_q = await db_session.execute(select(Control.id, Control.framework_version_id))
    ctrl_to_code = {
        cid: version_to_code.get(vid) for cid, vid in ctrl_q.all()
    }

    map_q = await db_session.execute(
        select(FrameworkControlMapping.source_control_id, FrameworkControlMapping.target_control_id)
    )
    rows = map_q.all()

    new_touching = [
        (s, t) for s, t in rows
        if (ctrl_to_code.get(s) in new_codes) or (ctrl_to_code.get(t) in new_codes)
    ]
    assert len(new_touching) >= 30, (
        f"Expected >= 30 cross-mappings touching the new frameworks, found {len(new_touching)}"
    )
