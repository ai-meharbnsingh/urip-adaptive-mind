"""
TDD — India DPDP Act 2023 seeder tests.

Tests verify the India Digital Personal Data Protection Act 2023 seeder
loads at least 25 controls with proper section references.
"""
import pytest
from sqlalchemy import select, func

from compliance_backend.models.framework import Framework, FrameworkVersion, Control
from compliance_backend.seeders.india_dpdp import seed_india_dpdp, ALL_DPDP_CONTROLS


@pytest.mark.anyio
async def test_india_dpdp_seeder_loads_framework(db_session):
    """India DPDP seeder creates the framework record."""
    await seed_india_dpdp(db_session)
    result = await db_session.execute(
        select(Framework).where(Framework.short_code == "DPDP")
    )
    framework = result.scalars().first()
    assert framework is not None, "India DPDP framework not found after seeding"
    assert "DPDP" in framework.name or "Digital Personal Data" in framework.name


@pytest.mark.anyio
async def test_india_dpdp_seeder_loads_at_least_25_controls(db_session):
    """India DPDP seeder must load at least 25 controls."""
    await seed_india_dpdp(db_session)

    result = await db_session.execute(
        select(Framework).where(Framework.short_code == "DPDP")
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

    assert total_controls >= 25, (
        f"India DPDP seeder loaded only {total_controls} controls, expected >= 25"
    )


@pytest.mark.anyio
async def test_india_dpdp_controls_have_section_references(db_session):
    """India DPDP control codes must use Section references (Sec. prefix)."""
    await seed_india_dpdp(db_session)

    result = await db_session.execute(
        select(Framework).where(Framework.short_code == "DPDP")
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
            assert control.control_code.startswith("Sec."), (
                f"DPDP control_code '{control.control_code}' does not start with 'Sec.'"
            )


@pytest.mark.anyio
async def test_india_dpdp_covers_key_categories(db_session):
    """India DPDP must cover lawful processing, rights, and obligations."""
    await seed_india_dpdp(db_session)

    result = await db_session.execute(
        select(Framework).where(Framework.short_code == "DPDP")
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

    expected_categories = {
        "Lawful Processing",
        "Rights of Data Principals",
        "Obligations of Data Fiduciary",
    }
    missing = expected_categories - all_categories
    assert not missing, f"India DPDP missing categories: {missing}"


@pytest.mark.anyio
async def test_india_dpdp_control_codes_unique_within_version(db_session):
    """India DPDP control codes must be unique within a framework version."""
    await seed_india_dpdp(db_session)

    result = await db_session.execute(
        select(Framework).where(Framework.short_code == "DPDP")
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
            f"Duplicate control codes in India DPDP: {[c for c in codes if codes.count(c) > 1]}"
        )


@pytest.mark.anyio
async def test_india_dpdp_seeder_is_idempotent(db_session):
    """Running India DPDP seeder twice must not create duplicate records."""
    await seed_india_dpdp(db_session)
    await seed_india_dpdp(db_session)

    result = await db_session.execute(
        select(func.count()).select_from(Framework).where(Framework.short_code == "DPDP")
    )
    count = result.scalar()
    assert count == 1, f"Expected exactly 1 DPDP framework, got {count} after double-seeding"


def test_india_dpdp_static_data_has_at_least_25_controls():
    """Static data list must contain >= 25 entries before any DB operation."""
    assert len(ALL_DPDP_CONTROLS) >= 25, (
        f"ALL_DPDP_CONTROLS has only {len(ALL_DPDP_CONTROLS)} entries, need >= 25"
    )
