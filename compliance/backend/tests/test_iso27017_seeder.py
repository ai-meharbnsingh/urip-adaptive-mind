"""
TDD — ISO/IEC 27017 (Cloud Security) seeder tests.
"""
import pytest
from sqlalchemy import select, func

from compliance_backend.models.framework import Framework, FrameworkVersion, Control
from compliance_backend.seeders.iso27017 import seed_iso27017, ALL_ISO27017_CONTROLS


@pytest.mark.anyio
async def test_iso27017_seeder_loads_framework(db_session):
    await seed_iso27017(db_session)
    result = await db_session.execute(
        select(Framework).where(Framework.short_code == "ISO27017")
    )
    framework = result.scalars().first()
    assert framework is not None
    assert "27017" in framework.name


@pytest.mark.anyio
async def test_iso27017_seeder_loads_at_least_37_controls(db_session):
    await seed_iso27017(db_session)
    result = await db_session.execute(
        select(Framework).where(Framework.short_code == "ISO27017")
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

    assert total >= 37, f"ISO 27017 loaded only {total} controls, expected >= 37"


@pytest.mark.anyio
async def test_iso27017_control_codes_unique(db_session):
    await seed_iso27017(db_session)
    result = await db_session.execute(
        select(Framework).where(Framework.short_code == "ISO27017")
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
        assert len(codes) == len(set(codes)), "Duplicate ISO 27017 control codes"


@pytest.mark.anyio
async def test_iso27017_seeder_is_idempotent(db_session):
    await seed_iso27017(db_session)
    await seed_iso27017(db_session)
    result = await db_session.execute(
        select(func.count()).select_from(Framework).where(Framework.short_code == "ISO27017")
    )
    assert result.scalar() == 1


def test_iso27017_static_data_has_at_least_37_controls():
    assert len(ALL_ISO27017_CONTROLS) >= 37
