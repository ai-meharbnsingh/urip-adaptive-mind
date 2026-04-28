"""
TDD — PCI DSS v4.0 seeder tests.

Tests verify the PCI DSS v4.0 seeder loads at least 60 controls
covering all 12 main requirements with sub-requirements.
"""
import pytest
from sqlalchemy import select, func

from compliance_backend.models.framework import Framework, FrameworkVersion, Control
from compliance_backend.seeders.pci_dss import seed_pci_dss, ALL_PCI_CONTROLS


@pytest.mark.anyio
async def test_pci_dss_seeder_loads_framework(db_session):
    """PCI DSS seeder creates the PCI DSS framework record."""
    await seed_pci_dss(db_session)
    result = await db_session.execute(
        select(Framework).where(Framework.short_code == "PCIDSS")
    )
    framework = result.scalars().first()
    assert framework is not None, "PCI DSS framework not found after seeding"
    assert "PCI" in framework.name


@pytest.mark.anyio
async def test_pci_dss_seeder_loads_at_least_60_controls(db_session):
    """PCI DSS seeder must load at least 60 controls."""
    await seed_pci_dss(db_session)

    result = await db_session.execute(
        select(Framework).where(Framework.short_code == "PCIDSS")
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
        f"PCI DSS seeder loaded only {total_controls} controls, expected >= 60"
    )


@pytest.mark.anyio
async def test_pci_dss_covers_all_12_requirements(db_session):
    """PCI DSS v4.0 must cover all 12 main requirements."""
    await seed_pci_dss(db_session)

    result = await db_session.execute(
        select(Framework).where(Framework.short_code == "PCIDSS")
    )
    framework = result.scalars().first()
    assert framework is not None

    version_result = await db_session.execute(
        select(FrameworkVersion).where(FrameworkVersion.framework_id == framework.id)
    )
    versions = version_result.scalars().all()

    # Collect all control codes and check top-level requirements 1–12
    all_codes = []
    for version in versions:
        codes_result = await db_session.execute(
            select(Control.control_code).where(Control.framework_version_id == version.id)
        )
        all_codes.extend(codes_result.scalars().all())

    found_requirements = set()
    for code in all_codes:
        # code like "1.1.1" or "12.3.4" — first segment is the main requirement
        top = code.split(".")[0]
        if top.isdigit():
            found_requirements.add(int(top))

    expected_reqs = set(range(1, 13))
    missing = expected_reqs - found_requirements
    assert not missing, f"PCI DSS missing top-level requirements: {missing}"


@pytest.mark.anyio
async def test_pci_dss_control_codes_use_v4_numbering(db_session):
    """PCI DSS control codes must use numeric dotted notation (e.g., 1.1.1)."""
    await seed_pci_dss(db_session)

    result = await db_session.execute(
        select(Framework).where(Framework.short_code == "PCIDSS")
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
        for control in controls:
            parts = control.control_code.split(".")
            assert len(parts) >= 2, (
                f"PCI DSS control_code '{control.control_code}' should have at least 2 numeric segments"
            )
            assert all(p.isdigit() for p in parts), (
                f"PCI DSS control_code '{control.control_code}' has non-numeric segments"
            )


@pytest.mark.anyio
async def test_pci_dss_control_codes_unique_within_version(db_session):
    """PCI DSS control codes must be unique within a framework version."""
    await seed_pci_dss(db_session)

    result = await db_session.execute(
        select(Framework).where(Framework.short_code == "PCIDSS")
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
            f"Duplicate control codes in PCI DSS: {[c for c in codes if codes.count(c) > 1]}"
        )


@pytest.mark.anyio
async def test_pci_dss_seeder_is_idempotent(db_session):
    """Running PCI DSS seeder twice must not create duplicate records."""
    await seed_pci_dss(db_session)
    await seed_pci_dss(db_session)

    result = await db_session.execute(
        select(func.count()).select_from(Framework).where(Framework.short_code == "PCIDSS")
    )
    count = result.scalar()
    assert count == 1, f"Expected exactly 1 PCI DSS framework, got {count} after double-seeding"


def test_pci_dss_static_data_has_at_least_60_controls():
    """Static data list must contain >= 60 entries before any DB operation."""
    assert len(ALL_PCI_CONTROLS) >= 60, (
        f"ALL_PCI_CONTROLS has only {len(ALL_PCI_CONTROLS)} entries, need >= 60"
    )
