"""
TDD — ISO/IEC 42001:2023 (AI Management System) seeder tests.

Tests verify the ISO 42001 seeder loads the AI management system framework
covering Annex A controls (AI policy, AI lifecycle, data, system development,
monitoring, etc.).
"""
import pytest
from sqlalchemy import select, func

from compliance_backend.models.framework import Framework, FrameworkVersion, Control
from compliance_backend.seeders.iso42001 import seed_iso42001, ALL_ISO42001_CONTROLS


@pytest.mark.anyio
async def test_iso42001_seeder_loads_framework(db_session):
    """ISO 42001 seeder creates the framework record."""
    await seed_iso42001(db_session)
    result = await db_session.execute(
        select(Framework).where(Framework.short_code == "ISO42001")
    )
    framework = result.scalars().first()
    assert framework is not None, "ISO 42001 framework not found after seeding"
    assert "42001" in framework.name


@pytest.mark.anyio
async def test_iso42001_seeder_loads_at_least_40_controls(db_session):
    """ISO 42001 seeder must load at least 40 Annex A controls."""
    await seed_iso42001(db_session)

    result = await db_session.execute(
        select(Framework).where(Framework.short_code == "ISO42001")
    )
    framework = result.scalars().first()
    assert framework is not None

    version_result = await db_session.execute(
        select(FrameworkVersion).where(FrameworkVersion.framework_id == framework.id)
    )
    versions = version_result.scalars().all()

    total = 0
    for v in versions:
        cnt_result = await db_session.execute(
            select(func.count()).where(Control.framework_version_id == v.id)
        )
        total += cnt_result.scalar()

    assert total >= 40, f"ISO 42001 loaded only {total} controls, expected >= 40"


@pytest.mark.anyio
async def test_iso42001_control_codes_unique_within_version(db_session):
    await seed_iso42001(db_session)

    result = await db_session.execute(
        select(Framework).where(Framework.short_code == "ISO42001")
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
        codes = [c.control_code for c in controls_result.scalars().all()]
        assert len(codes) == len(set(codes)), "Duplicate ISO 42001 control codes"


@pytest.mark.anyio
async def test_iso42001_seeder_is_idempotent(db_session):
    await seed_iso42001(db_session)
    await seed_iso42001(db_session)
    result = await db_session.execute(
        select(func.count()).select_from(Framework).where(Framework.short_code == "ISO42001")
    )
    assert result.scalar() == 1


def test_iso42001_static_data_has_at_least_40_controls():
    assert len(ALL_ISO42001_CONTROLS) >= 40, (
        f"ALL_ISO42001_CONTROLS has only {len(ALL_ISO42001_CONTROLS)} entries, need >= 40"
    )
