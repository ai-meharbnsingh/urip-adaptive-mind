"""
TDD — HIPAA seeder tests.

Tests verify the HIPAA Security Rule seeder loads at least 40 controls
covering all 4 safeguard categories (Administrative, Physical, Technical,
Organizational / Documentation).
"""
import pytest
from sqlalchemy import select, func

from compliance_backend.models.framework import Framework, FrameworkVersion, Control
from compliance_backend.seeders.hipaa import seed_hipaa, ALL_HIPAA_CONTROLS


@pytest.mark.anyio
async def test_hipaa_seeder_loads_framework(db_session):
    """HIPAA seeder creates the HIPAA framework record."""
    await seed_hipaa(db_session)
    result = await db_session.execute(
        select(Framework).where(Framework.short_code == "HIPAA")
    )
    framework = result.scalars().first()
    assert framework is not None, "HIPAA framework not found after seeding"
    assert "HIPAA" in framework.name


@pytest.mark.anyio
async def test_hipaa_seeder_loads_at_least_40_controls(db_session):
    """HIPAA seeder must load at least 40 controls."""
    await seed_hipaa(db_session)

    result = await db_session.execute(
        select(Framework).where(Framework.short_code == "HIPAA")
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

    assert total_controls >= 40, (
        f"HIPAA seeder loaded only {total_controls} controls, expected >= 40"
    )


@pytest.mark.anyio
async def test_hipaa_covers_all_4_safeguard_categories(db_session):
    """HIPAA must cover Administrative, Physical, Technical, and Organizational safeguards."""
    await seed_hipaa(db_session)

    result = await db_session.execute(
        select(Framework).where(Framework.short_code == "HIPAA")
    )
    framework = result.scalars().first()
    assert framework is not None

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

    expected_categories = {
        "Administrative Safeguards",
        "Physical Safeguards",
        "Technical Safeguards",
        "Organizational Requirements",
    }
    missing = expected_categories - all_categories
    assert not missing, f"HIPAA missing safeguard categories: {missing}"


@pytest.mark.anyio
async def test_hipaa_control_codes_use_cfr_identifiers(db_session):
    """HIPAA control codes must use 45 CFR Part 164 identifiers."""
    await seed_hipaa(db_session)

    result = await db_session.execute(
        select(Framework).where(Framework.short_code == "HIPAA")
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
        for control in controls:
            assert control.control_code.startswith("164."), (
                f"HIPAA control_code '{control.control_code}' does not start with '164.'"
            )


@pytest.mark.anyio
async def test_hipaa_control_codes_unique_within_version(db_session):
    """HIPAA control codes must be unique within a framework version."""
    await seed_hipaa(db_session)

    result = await db_session.execute(
        select(Framework).where(Framework.short_code == "HIPAA")
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
            f"Duplicate control codes in HIPAA: {[c for c in codes if codes.count(c) > 1]}"
        )


@pytest.mark.anyio
async def test_hipaa_seeder_is_idempotent(db_session):
    """Running HIPAA seeder twice must not create duplicate records."""
    await seed_hipaa(db_session)
    await seed_hipaa(db_session)

    result = await db_session.execute(
        select(func.count()).select_from(Framework).where(Framework.short_code == "HIPAA")
    )
    count = result.scalar()
    assert count == 1, f"Expected exactly 1 HIPAA framework, got {count} after double-seeding"


def test_hipaa_static_data_has_at_least_40_controls():
    """Static data list must contain >= 40 entries before any DB operation."""
    assert len(ALL_HIPAA_CONTROLS) >= 40, (
        f"ALL_HIPAA_CONTROLS has only {len(ALL_HIPAA_CONTROLS)} entries, need >= 40"
    )
