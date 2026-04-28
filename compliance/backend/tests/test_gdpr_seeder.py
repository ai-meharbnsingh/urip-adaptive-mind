"""
TDD — GDPR seeder tests.

Tests verify the GDPR seeder loads correct framework data covering
GDPR Articles 5-39 (data protection principles, rights, obligations).
"""
import pytest
from sqlalchemy import select, func

from compliance_backend.models.framework import Framework, FrameworkVersion, Control
from compliance_backend.seeders.gdpr import seed_gdpr, ALL_GDPR_CONTROLS


@pytest.mark.anyio
async def test_gdpr_seeder_loads_framework(db_session):
    """GDPR seeder creates the GDPR framework record."""
    await seed_gdpr(db_session)
    result = await db_session.execute(
        select(Framework).where(Framework.short_code == "GDPR")
    )
    framework = result.scalars().first()
    assert framework is not None, "GDPR framework not found after seeding"
    assert "GDPR" in framework.name or "General Data Protection" in framework.name


@pytest.mark.anyio
async def test_gdpr_seeder_loads_at_least_35_controls(db_session):
    """GDPR seeder must load at least 35 controls."""
    await seed_gdpr(db_session)

    result = await db_session.execute(
        select(Framework).where(Framework.short_code == "GDPR")
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

    assert total_controls >= 35, (
        f"GDPR seeder loaded only {total_controls} controls, expected >= 35"
    )


@pytest.mark.anyio
async def test_gdpr_controls_have_article_references(db_session):
    """All GDPR control codes must contain Article references (Art. prefix)."""
    await seed_gdpr(db_session)

    result = await db_session.execute(
        select(Framework).where(Framework.short_code == "GDPR")
    )
    framework = result.scalars().first()
    assert framework is not None

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
            assert control.control_code.startswith("Art."), (
                f"GDPR control_code '{control.control_code}' does not start with 'Art.'"
            )


@pytest.mark.anyio
async def test_gdpr_covers_key_categories(db_session):
    """GDPR seeder must cover core category groups."""
    await seed_gdpr(db_session)

    result = await db_session.execute(
        select(Framework).where(Framework.short_code == "GDPR")
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
        "Data Protection Principles",
        "Rights of Data Subjects",
        "Controller Obligations",
    }
    missing = expected_categories - all_categories
    assert not missing, f"GDPR missing key categories: {missing}"


@pytest.mark.anyio
async def test_gdpr_control_codes_unique_within_version(db_session):
    """GDPR control codes must be unique within a framework version."""
    await seed_gdpr(db_session)

    result = await db_session.execute(
        select(Framework).where(Framework.short_code == "GDPR")
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
            f"Duplicate control codes in GDPR: {[c for c in codes if codes.count(c) > 1]}"
        )


@pytest.mark.anyio
async def test_gdpr_seeder_is_idempotent(db_session):
    """Running GDPR seeder twice must not create duplicate framework records."""
    await seed_gdpr(db_session)
    await seed_gdpr(db_session)

    result = await db_session.execute(
        select(func.count()).select_from(Framework).where(Framework.short_code == "GDPR")
    )
    count = result.scalar()
    assert count == 1, f"Expected exactly 1 GDPR framework, got {count} after double-seeding"


def test_gdpr_static_data_has_at_least_35_controls():
    """Static data list must contain >= 35 entries before any DB operation."""
    assert len(ALL_GDPR_CONTROLS) >= 35, (
        f"ALL_GDPR_CONTROLS has only {len(ALL_GDPR_CONTROLS)} entries, need >= 35"
    )
