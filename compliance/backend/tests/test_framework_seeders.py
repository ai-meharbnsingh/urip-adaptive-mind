"""
TDD — framework seeder tests.

Tests written BEFORE seeder implementation.
"""
import pytest
from sqlalchemy import select, func

from compliance_backend.models.framework import Framework, FrameworkVersion, Control
from compliance_backend.seeders.soc2 import seed_soc2
from compliance_backend.seeders.iso27001 import seed_iso27001


@pytest.mark.anyio
async def test_soc2_seeder_loads_framework(db_session):
    """SOC 2 seeder creates the SOC 2 framework record."""
    await seed_soc2(db_session)
    result = await db_session.execute(
        select(Framework).where(Framework.short_code == "SOC2")
    )
    framework = result.scalars().first()
    assert framework is not None, "SOC 2 framework not found after seeding"
    assert framework.name == "SOC 2"


@pytest.mark.anyio
async def test_soc2_seeder_loads_at_least_30_controls(db_session):
    """SOC 2 seeder must load at least 30 controls."""
    await seed_soc2(db_session)

    # Get SOC2 framework
    result = await db_session.execute(
        select(Framework).where(Framework.short_code == "SOC2")
    )
    framework = result.scalars().first()
    assert framework is not None

    # Count controls via framework version
    version_result = await db_session.execute(
        select(FrameworkVersion).where(FrameworkVersion.framework_id == framework.id)
    )
    versions = version_result.scalars().all()
    assert len(versions) >= 1, "SOC2 must have at least one framework version"

    total_controls = 0
    for version in versions:
        count_result = await db_session.execute(
            select(func.count()).where(Control.framework_version_id == version.id)
        )
        total_controls += count_result.scalar()

    assert total_controls >= 30, (
        f"SOC 2 seeder loaded only {total_controls} controls, expected >= 30"
    )


@pytest.mark.anyio
async def test_soc2_control_codes_unique_within_version(db_session):
    """Control codes must be unique within a given framework version."""
    await seed_soc2(db_session)

    result = await db_session.execute(
        select(Framework).where(Framework.short_code == "SOC2")
    )
    framework = result.scalars().first()

    version_result = await db_session.execute(
        select(FrameworkVersion).where(FrameworkVersion.framework_id == framework.id)
    )
    versions = version_result.scalars().all()

    for version in versions:
        controls_result = await db_session.execute(
            select(Control).where(Control.framework_version_id == version.id)
        )
        controls = controls_result.scalars().all()
        codes = [c.control_code for c in controls]
        assert len(codes) == len(set(codes)), (
            f"Duplicate control codes found in SOC2 version {version.version}: {set(c for c in codes if codes.count(c) > 1)}"
        )


@pytest.mark.anyio
async def test_soc2_covers_all_5_trust_categories(db_session):
    """SOC 2 must cover all 5 Trust Services categories."""
    await seed_soc2(db_session)

    result = await db_session.execute(
        select(Framework).where(Framework.short_code == "SOC2")
    )
    framework = result.scalars().first()

    version_result = await db_session.execute(
        select(FrameworkVersion).where(FrameworkVersion.framework_id == framework.id)
    )
    versions = version_result.scalars().all()

    # Collect all categories across versions
    all_categories = set()
    for version in versions:
        cats_result = await db_session.execute(
            select(Control.category).where(Control.framework_version_id == version.id).distinct()
        )
        all_categories.update(cats_result.scalars().all())

    expected_categories = {"Security", "Availability", "Processing Integrity", "Confidentiality", "Privacy"}
    missing = expected_categories - all_categories
    assert not missing, f"SOC 2 missing Trust Services categories: {missing}"


@pytest.mark.anyio
async def test_iso27001_seeder_loads_framework(db_session):
    """ISO 27001 seeder creates the ISO 27001:2022 framework record."""
    await seed_iso27001(db_session)
    result = await db_session.execute(
        select(Framework).where(Framework.short_code == "ISO27001")
    )
    framework = result.scalars().first()
    assert framework is not None, "ISO 27001 framework not found after seeding"
    assert "27001" in framework.name


@pytest.mark.anyio
async def test_iso27001_seeder_loads_at_least_50_controls(db_session):
    """ISO 27001:2022 seeder must load at least 50 Annex A controls."""
    await seed_iso27001(db_session)

    result = await db_session.execute(
        select(Framework).where(Framework.short_code == "ISO27001")
    )
    framework = result.scalars().first()
    assert framework is not None

    version_result = await db_session.execute(
        select(FrameworkVersion).where(FrameworkVersion.framework_id == framework.id)
    )
    versions = version_result.scalars().all()
    assert len(versions) >= 1

    total_controls = 0
    for version in versions:
        count_result = await db_session.execute(
            select(func.count()).where(Control.framework_version_id == version.id)
        )
        total_controls += count_result.scalar()

    assert total_controls >= 50, (
        f"ISO 27001 seeder loaded only {total_controls} controls, expected >= 50"
    )


@pytest.mark.anyio
async def test_iso27001_control_codes_unique_within_version(db_session):
    """ISO 27001 control codes must be unique within a framework version."""
    await seed_iso27001(db_session)

    result = await db_session.execute(
        select(Framework).where(Framework.short_code == "ISO27001")
    )
    framework = result.scalars().first()

    version_result = await db_session.execute(
        select(FrameworkVersion).where(FrameworkVersion.framework_id == framework.id)
    )
    versions = version_result.scalars().all()

    for version in versions:
        controls_result = await db_session.execute(
            select(Control).where(Control.framework_version_id == version.id)
        )
        controls = controls_result.scalars().all()
        codes = [c.control_code for c in controls]
        assert len(codes) == len(set(codes)), (
            f"Duplicate control codes in ISO 27001 version {version.version}"
        )


@pytest.mark.anyio
async def test_iso27001_covers_all_4_annex_categories(db_session):
    """ISO 27001:2022 Annex A has 4 control categories."""
    await seed_iso27001(db_session)

    result = await db_session.execute(
        select(Framework).where(Framework.short_code == "ISO27001")
    )
    framework = result.scalars().first()

    version_result = await db_session.execute(
        select(FrameworkVersion).where(FrameworkVersion.framework_id == framework.id)
    )
    versions = version_result.scalars().all()

    all_categories = set()
    for version in versions:
        cats_result = await db_session.execute(
            select(Control.category).where(Control.framework_version_id == version.id).distinct()
        )
        all_categories.update(cats_result.scalars().all())

    expected_categories = {"Organizational", "People", "Physical", "Technological"}
    missing = expected_categories - all_categories
    assert not missing, f"ISO 27001 missing Annex A categories: {missing}"


@pytest.mark.anyio
async def test_seeders_are_idempotent(db_session):
    """Running seeders twice must not create duplicate records."""
    await seed_soc2(db_session)
    await seed_soc2(db_session)

    result = await db_session.execute(
        select(func.count()).select_from(Framework).where(Framework.short_code == "SOC2")
    )
    count = result.scalar()
    assert count == 1, f"Expected exactly 1 SOC2 framework, got {count} after double-seeding"
