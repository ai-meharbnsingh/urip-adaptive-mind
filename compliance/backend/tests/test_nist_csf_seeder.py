"""
TDD — NIST CSF 2.0 seeder tests.

Tests verify the NIST Cybersecurity Framework 2.0 seeder loads at least 60
controls covering all 6 Functions (Govern, Identify, Protect, Detect,
Respond, Recover).
"""
import pytest
from sqlalchemy import select, func

from compliance_backend.models.framework import Framework, FrameworkVersion, Control
from compliance_backend.seeders.nist_csf import seed_nist_csf, ALL_NIST_CSF_CONTROLS


@pytest.mark.anyio
async def test_nist_csf_seeder_loads_framework(db_session):
    """NIST CSF seeder creates the NIST CSF framework record."""
    await seed_nist_csf(db_session)
    result = await db_session.execute(
        select(Framework).where(Framework.short_code == "NISTCSF")
    )
    framework = result.scalars().first()
    assert framework is not None, "NIST CSF framework not found after seeding"
    assert "NIST" in framework.name


@pytest.mark.anyio
async def test_nist_csf_seeder_loads_at_least_60_controls(db_session):
    """NIST CSF 2.0 seeder must load at least 60 controls."""
    await seed_nist_csf(db_session)

    result = await db_session.execute(
        select(Framework).where(Framework.short_code == "NISTCSF")
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

    assert total_controls >= 60, (
        f"NIST CSF 2.0 seeder loaded only {total_controls} controls, expected >= 60"
    )


@pytest.mark.anyio
async def test_nist_csf_covers_all_6_functions(db_session):
    """NIST CSF 2.0 must cover all 6 Functions: Govern, Identify, Protect, Detect, Respond, Recover."""
    await seed_nist_csf(db_session)

    result = await db_session.execute(
        select(Framework).where(Framework.short_code == "NISTCSF")
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

    expected_functions = {"Govern", "Identify", "Protect", "Detect", "Respond", "Recover"}
    missing = expected_functions - all_categories
    assert not missing, f"NIST CSF 2.0 missing Functions: {missing}"


@pytest.mark.anyio
async def test_nist_csf_control_codes_use_csf_ids(db_session):
    """NIST CSF control codes must use CSF 2.0 IDs (e.g., GV.OC-01, ID.AM-01)."""
    await seed_nist_csf(db_session)

    result = await db_session.execute(
        select(Framework).where(Framework.short_code == "NISTCSF")
    )
    framework = result.scalars().first()

    version_result = await db_session.execute(
        select(FrameworkVersion).where(FrameworkVersion.framework_id == framework.id)
    )
    versions = version_result.scalars().all()

    valid_prefixes = {"GV.", "ID.", "PR.", "DE.", "RS.", "RC."}
    for version in versions:
        controls_result = await db_session.execute(
            select(Control).where(Control.framework_version_id == version.id)
        )
        controls = controls_result.scalars().all()
        for control in controls:
            prefix_ok = any(control.control_code.startswith(p) for p in valid_prefixes)
            assert prefix_ok, (
                f"NIST CSF control_code '{control.control_code}' does not match any expected prefix {valid_prefixes}"
            )


@pytest.mark.anyio
async def test_nist_csf_control_codes_unique_within_version(db_session):
    """NIST CSF control codes must be unique within a framework version."""
    await seed_nist_csf(db_session)

    result = await db_session.execute(
        select(Framework).where(Framework.short_code == "NISTCSF")
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
            f"Duplicate control codes in NIST CSF: {[c for c in codes if codes.count(c) > 1]}"
        )


@pytest.mark.anyio
async def test_nist_csf_seeder_is_idempotent(db_session):
    """Running NIST CSF seeder twice must not create duplicate records."""
    await seed_nist_csf(db_session)
    await seed_nist_csf(db_session)

    result = await db_session.execute(
        select(func.count()).select_from(Framework).where(Framework.short_code == "NISTCSF")
    )
    count = result.scalar()
    assert count == 1, f"Expected exactly 1 NIST CSF framework, got {count} after double-seeding"


def test_nist_csf_static_data_has_at_least_60_controls():
    """Static data list must contain >= 60 entries before any DB operation."""
    assert len(ALL_NIST_CSF_CONTROLS) >= 60, (
        f"ALL_NIST_CSF_CONTROLS has only {len(ALL_NIST_CSF_CONTROLS)} entries, need >= 60"
    )
