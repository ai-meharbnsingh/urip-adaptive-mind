"""
TDD — NIS2 Directive (EU 2022/2555) seeder tests.
"""
import pytest
from sqlalchemy import select, func

from compliance_backend.models.framework import Framework, FrameworkVersion, Control
from compliance_backend.seeders.nis2 import seed_nis2, ALL_NIS2_CONTROLS


@pytest.mark.anyio
async def test_nis2_seeder_loads_framework(db_session):
    await seed_nis2(db_session)
    result = await db_session.execute(
        select(Framework).where(Framework.short_code == "NIS2")
    )
    framework = result.scalars().first()
    assert framework is not None
    assert "NIS2" in framework.name or "Network and Information" in framework.name


@pytest.mark.anyio
async def test_nis2_seeder_loads_at_least_80_controls(db_session):
    await seed_nis2(db_session)

    result = await db_session.execute(
        select(Framework).where(Framework.short_code == "NIS2")
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

    assert total >= 80, f"NIS2 loaded only {total} controls, expected >= 80"


@pytest.mark.anyio
async def test_nis2_control_codes_unique(db_session):
    await seed_nis2(db_session)
    result = await db_session.execute(
        select(Framework).where(Framework.short_code == "NIS2")
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
        assert len(codes) == len(set(codes)), "Duplicate NIS2 control codes"


@pytest.mark.anyio
async def test_nis2_seeder_is_idempotent(db_session):
    await seed_nis2(db_session)
    await seed_nis2(db_session)
    result = await db_session.execute(
        select(func.count()).select_from(Framework).where(Framework.short_code == "NIS2")
    )
    assert result.scalar() == 1


def test_nis2_static_data_has_at_least_80_controls():
    assert len(ALL_NIS2_CONTROLS) >= 80
