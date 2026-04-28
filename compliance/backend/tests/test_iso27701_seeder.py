"""
TDD — ISO/IEC 27701 (Privacy Information Management System) seeder tests.
"""
import pytest
from sqlalchemy import select, func

from compliance_backend.models.framework import Framework, FrameworkVersion, Control
from compliance_backend.seeders.iso27701 import seed_iso27701, ALL_ISO27701_CONTROLS


@pytest.mark.anyio
async def test_iso27701_seeder_loads_framework(db_session):
    await seed_iso27701(db_session)
    result = await db_session.execute(
        select(Framework).where(Framework.short_code == "ISO27701")
    )
    framework = result.scalars().first()
    assert framework is not None
    assert "27701" in framework.name


@pytest.mark.anyio
async def test_iso27701_seeder_loads_at_least_50_controls(db_session):
    await seed_iso27701(db_session)
    result = await db_session.execute(
        select(Framework).where(Framework.short_code == "ISO27701")
    )
    framework = result.scalars().first()
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

    assert total >= 50, f"ISO 27701 loaded only {total} controls, expected >= 50"


@pytest.mark.anyio
async def test_iso27701_control_codes_unique(db_session):
    await seed_iso27701(db_session)
    result = await db_session.execute(
        select(Framework).where(Framework.short_code == "ISO27701")
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
        assert len(codes) == len(set(codes)), "Duplicate ISO 27701 control codes"


@pytest.mark.anyio
async def test_iso27701_seeder_is_idempotent(db_session):
    await seed_iso27701(db_session)
    await seed_iso27701(db_session)
    result = await db_session.execute(
        select(func.count()).select_from(Framework).where(Framework.short_code == "ISO27701")
    )
    assert result.scalar() == 1


def test_iso27701_static_data_has_at_least_50_controls():
    assert len(ALL_ISO27701_CONTROLS) >= 50
