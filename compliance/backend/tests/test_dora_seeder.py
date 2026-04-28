"""
TDD — DORA (Digital Operational Resilience Act, EU 2022/2554) seeder tests.
"""
import pytest
from sqlalchemy import select, func

from compliance_backend.models.framework import Framework, FrameworkVersion, Control
from compliance_backend.seeders.dora import seed_dora, ALL_DORA_CONTROLS


@pytest.mark.anyio
async def test_dora_seeder_loads_framework(db_session):
    await seed_dora(db_session)
    result = await db_session.execute(
        select(Framework).where(Framework.short_code == "DORA")
    )
    framework = result.scalars().first()
    assert framework is not None
    assert "DORA" in framework.name or "Digital Operational Resilience" in framework.name


@pytest.mark.anyio
async def test_dora_seeder_loads_at_least_50_controls(db_session):
    await seed_dora(db_session)

    result = await db_session.execute(
        select(Framework).where(Framework.short_code == "DORA")
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

    assert total >= 50, f"DORA loaded only {total} controls, expected >= 50"


@pytest.mark.anyio
async def test_dora_covers_key_categories(db_session):
    """DORA must cover the four pillars: ICT Risk Mgmt, Incident Mgmt, Resilience Testing, Third-Party Risk."""
    await seed_dora(db_session)
    result = await db_session.execute(
        select(Framework).where(Framework.short_code == "DORA")
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

    expected = {
        "ICT Risk Management",
        "ICT Incident Management",
        "Resilience Testing",
        "Third-Party Risk",
    }
    missing = expected - all_categories
    assert not missing, f"DORA missing categories: {missing}"


@pytest.mark.anyio
async def test_dora_control_codes_unique(db_session):
    await seed_dora(db_session)
    result = await db_session.execute(
        select(Framework).where(Framework.short_code == "DORA")
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
        assert len(codes) == len(set(codes)), "Duplicate DORA control codes"


@pytest.mark.anyio
async def test_dora_seeder_is_idempotent(db_session):
    await seed_dora(db_session)
    await seed_dora(db_session)
    result = await db_session.execute(
        select(func.count()).select_from(Framework).where(Framework.short_code == "DORA")
    )
    assert result.scalar() == 1


def test_dora_static_data_has_at_least_50_controls():
    assert len(ALL_DORA_CONTROLS) >= 50
