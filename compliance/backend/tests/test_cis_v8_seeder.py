"""
TDD — CIS Controls v8 seeder tests.
"""
import pytest
from sqlalchemy import select, func

from compliance_backend.models.framework import Framework, FrameworkVersion, Control
from compliance_backend.seeders.cis_v8 import seed_cis_v8, ALL_CIS_V8_CONTROLS


@pytest.mark.anyio
async def test_cis_v8_seeder_loads_framework(db_session):
    await seed_cis_v8(db_session)
    result = await db_session.execute(
        select(Framework).where(Framework.short_code == "CISV8")
    )
    framework = result.scalars().first()
    assert framework is not None
    assert "CIS" in framework.name


@pytest.mark.anyio
async def test_cis_v8_seeder_loads_at_least_110_controls(db_session):
    await seed_cis_v8(db_session)
    result = await db_session.execute(
        select(Framework).where(Framework.short_code == "CISV8")
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

    assert total >= 110, f"CIS v8 loaded only {total} controls, expected >= 110"


@pytest.mark.anyio
async def test_cis_v8_control_codes_unique(db_session):
    await seed_cis_v8(db_session)
    result = await db_session.execute(
        select(Framework).where(Framework.short_code == "CISV8")
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
        assert len(codes) == len(set(codes)), "Duplicate CIS v8 control codes"


@pytest.mark.anyio
async def test_cis_v8_covers_18_control_families(db_session):
    """CIS v8 has 18 control families. Verify at least 15 distinct categories present."""
    await seed_cis_v8(db_session)
    result = await db_session.execute(
        select(Framework).where(Framework.short_code == "CISV8")
    )
    framework = result.scalars().first()
    version_result = await db_session.execute(
        select(FrameworkVersion).where(FrameworkVersion.framework_id == framework.id)
    )
    versions = version_result.scalars().all()
    all_categories = set()
    for v in versions:
        cats_result = await db_session.execute(
            select(Control.category).where(Control.framework_version_id == v.id).distinct()
        )
        all_categories.update(cats_result.scalars().all())
    assert len(all_categories) >= 15, (
        f"CIS v8 has only {len(all_categories)} control families, expected at least 15"
    )


@pytest.mark.anyio
async def test_cis_v8_seeder_is_idempotent(db_session):
    await seed_cis_v8(db_session)
    await seed_cis_v8(db_session)
    result = await db_session.execute(
        select(func.count()).select_from(Framework).where(Framework.short_code == "CISV8")
    )
    assert result.scalar() == 1


def test_cis_v8_static_data_has_at_least_110_controls():
    assert len(ALL_CIS_V8_CONTROLS) >= 110
