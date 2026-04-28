"""
TDD — ISO/IEC 27018 (Cloud Privacy / PII) seeder tests.
"""
import pytest
from sqlalchemy import select, func

from compliance_backend.models.framework import Framework, FrameworkVersion, Control
from compliance_backend.seeders.iso27018 import seed_iso27018, ALL_ISO27018_CONTROLS


@pytest.mark.anyio
async def test_iso27018_seeder_loads_framework(db_session):
    await seed_iso27018(db_session)
    result = await db_session.execute(
        select(Framework).where(Framework.short_code == "ISO27018")
    )
    framework = result.scalars().first()
    assert framework is not None
    assert "27018" in framework.name


@pytest.mark.anyio
async def test_iso27018_seeder_loads_at_least_25_controls(db_session):
    await seed_iso27018(db_session)
    result = await db_session.execute(
        select(Framework).where(Framework.short_code == "ISO27018")
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

    assert total >= 25, f"ISO 27018 loaded only {total} controls, expected >= 25"


@pytest.mark.anyio
async def test_iso27018_control_codes_unique(db_session):
    await seed_iso27018(db_session)
    result = await db_session.execute(
        select(Framework).where(Framework.short_code == "ISO27018")
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
        assert len(codes) == len(set(codes)), "Duplicate ISO 27018 control codes"


@pytest.mark.anyio
async def test_iso27018_seeder_is_idempotent(db_session):
    await seed_iso27018(db_session)
    await seed_iso27018(db_session)
    result = await db_session.execute(
        select(func.count()).select_from(Framework).where(Framework.short_code == "ISO27018")
    )
    assert result.scalar() == 1


def test_iso27018_static_data_has_at_least_25_controls():
    assert len(ALL_ISO27018_CONTROLS) >= 25
