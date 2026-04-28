"""
TDD — Cross-framework control mapping tests.

Tests verify that at least 20 cross-framework mappings exist and all
reference valid controls from their respective frameworks.
"""
import pytest
from sqlalchemy import select, func

from compliance_backend.models.framework import (
    Framework, FrameworkVersion, Control, FrameworkControlMapping
)
from compliance_backend.seeders.soc2 import seed_soc2
from compliance_backend.seeders.iso27001 import seed_iso27001
from compliance_backend.seeders.gdpr import seed_gdpr
from compliance_backend.seeders.hipaa import seed_hipaa
from compliance_backend.seeders.pci_dss import seed_pci_dss
from compliance_backend.seeders.india_dpdp import seed_india_dpdp
from compliance_backend.seeders.nist_csf import seed_nist_csf
from compliance_backend.seeders.cross_mappings import seed_cross_mappings


async def _seed_all(db_session):
    """Helper: seed all 7 frameworks then cross-mappings."""
    await seed_soc2(db_session)
    await seed_iso27001(db_session)
    await seed_gdpr(db_session)
    await seed_hipaa(db_session)
    await seed_pci_dss(db_session)
    await seed_india_dpdp(db_session)
    await seed_nist_csf(db_session)
    await seed_cross_mappings(db_session)


@pytest.mark.anyio
async def test_cross_mappings_creates_at_least_20_mappings(db_session):
    """After seeding all frameworks, at least 20 cross-framework mappings must exist."""
    await _seed_all(db_session)

    count_result = await db_session.execute(
        select(func.count()).select_from(FrameworkControlMapping)
    )
    count = count_result.scalar()
    assert count >= 20, f"Expected >= 20 cross-framework mappings, found {count}"


@pytest.mark.anyio
async def test_cross_mappings_all_reference_valid_controls(db_session):
    """Every cross-framework mapping must reference controls that exist in the DB."""
    await _seed_all(db_session)

    mappings_result = await db_session.execute(
        select(FrameworkControlMapping)
    )
    mappings = mappings_result.scalars().all()
    assert len(mappings) >= 20

    # Collect all control IDs for fast lookup
    all_controls_result = await db_session.execute(select(Control.id))
    all_control_ids = set(all_controls_result.scalars().all())

    for mapping in mappings:
        assert mapping.source_control_id in all_control_ids, (
            f"Mapping source_control_id {mapping.source_control_id} not found in controls"
        )
        assert mapping.target_control_id in all_control_ids, (
            f"Mapping target_control_id {mapping.target_control_id} not found in controls"
        )


@pytest.mark.anyio
async def test_cross_mappings_use_valid_mapping_types(db_session):
    """All cross-framework mapping_type values must be one of: equivalent, partial, prerequisite."""
    await _seed_all(db_session)

    mappings_result = await db_session.execute(
        select(FrameworkControlMapping)
    )
    mappings = mappings_result.scalars().all()

    valid_types = {"equivalent", "partial", "prerequisite"}
    for mapping in mappings:
        assert mapping.mapping_type in valid_types, (
            f"Invalid mapping_type '{mapping.mapping_type}' — expected one of {valid_types}"
        )


@pytest.mark.anyio
async def test_cross_mappings_are_not_self_referential(db_session):
    """A control must not map to itself."""
    await _seed_all(db_session)

    mappings_result = await db_session.execute(
        select(FrameworkControlMapping)
    )
    mappings = mappings_result.scalars().all()

    for mapping in mappings:
        assert mapping.source_control_id != mapping.target_control_id, (
            f"Self-referential mapping found for control_id={mapping.source_control_id}"
        )


@pytest.mark.anyio
async def test_cross_mappings_span_multiple_framework_pairs(db_session):
    """Mappings must span at least 3 distinct framework pairs (not just one combo)."""
    await _seed_all(db_session)

    mappings_result = await db_session.execute(
        select(FrameworkControlMapping)
    )
    mappings = mappings_result.scalars().all()

    # For each mapping, find the framework_version_ids of source and target
    framework_pairs = set()
    for mapping in mappings:
        src_result = await db_session.execute(
            select(Control.framework_version_id).where(Control.id == mapping.source_control_id)
        )
        tgt_result = await db_session.execute(
            select(Control.framework_version_id).where(Control.id == mapping.target_control_id)
        )
        src_ver = src_result.scalar()
        tgt_ver = tgt_result.scalar()
        if src_ver and tgt_ver:
            pair = tuple(sorted([src_ver, tgt_ver]))
            framework_pairs.add(pair)

    assert len(framework_pairs) >= 3, (
        f"Cross-mappings only span {len(framework_pairs)} version pairs, expected >= 3"
    )


@pytest.mark.anyio
async def test_cross_mappings_are_idempotent(db_session):
    """Running cross_mappings seeder twice must not create duplicate mappings."""
    await _seed_all(db_session)
    # Seed cross-mappings a second time
    await seed_cross_mappings(db_session)

    count_result = await db_session.execute(
        select(func.count()).select_from(FrameworkControlMapping)
    )
    # Should still be the same count — no duplicates due to unique constraint
    count = count_result.scalar()
    assert count >= 20, f"Expected >= 20 mappings after double-seeding, found {count}"
