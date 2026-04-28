"""
TDD — EU AI Act (Regulation 2024/1689) seeder tests.
"""
import pytest
from sqlalchemy import select, func

from compliance_backend.models.framework import Framework, FrameworkVersion, Control
from compliance_backend.seeders.eu_ai_act import seed_eu_ai_act, ALL_EU_AI_ACT_CONTROLS


@pytest.mark.anyio
async def test_eu_ai_act_seeder_loads_framework(db_session):
    await seed_eu_ai_act(db_session)
    result = await db_session.execute(
        select(Framework).where(Framework.short_code == "EUAIACT")
    )
    framework = result.scalars().first()
    assert framework is not None
    assert "AI Act" in framework.name or "AI" in framework.name


@pytest.mark.anyio
async def test_eu_ai_act_seeder_loads_at_least_30_controls(db_session):
    await seed_eu_ai_act(db_session)

    result = await db_session.execute(
        select(Framework).where(Framework.short_code == "EUAIACT")
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

    assert total >= 30, f"EU AI Act loaded only {total} controls, expected >= 30"


@pytest.mark.anyio
async def test_eu_ai_act_control_codes_unique(db_session):
    await seed_eu_ai_act(db_session)
    result = await db_session.execute(
        select(Framework).where(Framework.short_code == "EUAIACT")
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
        assert len(codes) == len(set(codes)), "Duplicate EU AI Act control codes"


@pytest.mark.anyio
async def test_eu_ai_act_codes_reference_articles(db_session):
    """All EU AI Act control codes should reference Article numbers."""
    await seed_eu_ai_act(db_session)
    result = await db_session.execute(
        select(Framework).where(Framework.short_code == "EUAIACT")
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
        for c in controls_result.scalars().all():
            assert c.control_code.startswith("Art."), (
                f"EU AI Act control_code '{c.control_code}' must start with 'Art.'"
            )


@pytest.mark.anyio
async def test_eu_ai_act_seeder_is_idempotent(db_session):
    await seed_eu_ai_act(db_session)
    await seed_eu_ai_act(db_session)
    result = await db_session.execute(
        select(func.count()).select_from(Framework).where(Framework.short_code == "EUAIACT")
    )
    assert result.scalar() == 1


def test_eu_ai_act_static_data_has_at_least_30_controls():
    assert len(ALL_EU_AI_ACT_CONTROLS) >= 30
