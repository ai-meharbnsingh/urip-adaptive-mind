"""
Asset model tests — schema, CRUD, tenant isolation, FK from Risk.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.middleware.tenant import TenantContext, _tenant_id_var
from backend.models.asset import (
    ASSET_CATEGORIES,
    ASSET_TIERS,
    BUSINESS_CRITICALITY_VALUES,
    DEVICE_CATEGORIES,
    LIFECYCLE_STATES,
    Asset,
)
from backend.models.risk import Risk
from backend.models.tenant import Tenant
from backend.services.tenant_query import apply_tenant_filter


@pytest.fixture
def reset_tenant_context():
    token = _tenant_id_var.set(None)
    yield
    _tenant_id_var.reset(token)


async def _make_tenant(db: AsyncSession, slug: str) -> Tenant:
    t = Tenant(
        id=uuid.uuid4(),
        name=f"Tenant {slug}",
        slug=slug,
        domain=f"{slug}.test",
        is_active=True,
        settings={},
    )
    db.add(t)
    await db.commit()
    await db.refresh(t)
    return t


class TestAssetConstants:
    def test_device_categories(self):
        assert DEVICE_CATEGORIES == ("IT", "OT", "IoT", "SaaS")

    def test_asset_tiers(self):
        assert ASSET_TIERS == ("T1", "T2", "T3", "T4")

    def test_lifecycle_states_includes_required(self):
        for s in ("in_use", "decommissioned", "lost", "under_review"):
            assert s in LIFECYCLE_STATES

    def test_asset_categories_match_blueprint(self):
        # MASTER_BLUEPRINT.md §6b.1 — Devices / Internet-Facing / Accounts /
        # Applications / Cloud Assets / API Collections.
        for c in (
            "Devices",
            "Internet-Facing Assets",
            "Accounts",
            "Applications",
            "Cloud Assets",
            "API Collections",
        ):
            assert c in ASSET_CATEGORIES

    def test_business_criticality_values(self):
        assert BUSINESS_CRITICALITY_VALUES == ("critical", "high", "medium", "low")


class TestAssetCRUD:
    async def test_insert_minimal(self, db_session: AsyncSession):
        tenant = await _make_tenant(db_session, "asset-min")
        a = Asset(
            id=uuid.uuid4(),
            tenant_id=tenant.id,
            fingerprint_key="a" * 64,
            hostname="server-01",
            discovered_at=datetime.now(timezone.utc),
            last_seen=datetime.now(timezone.utc),
        )
        db_session.add(a)
        await db_session.commit()
        await db_session.refresh(a)

        assert a.id is not None
        assert a.lifecycle_state == "in_use"  # default
        assert a.source_connectors == []
        assert a.custom_tags == {}

    async def test_insert_full_record(self, db_session: AsyncSession):
        tenant = await _make_tenant(db_session, "asset-full")
        a = Asset(
            id=uuid.uuid4(),
            tenant_id=tenant.id,
            fingerprint_key="b" * 64,
            hostname="prod-sap-01",
            internal_ip="10.0.1.5",
            external_ip="203.0.113.5",
            mac_address="aa:bb:cc:dd:ee:ff",
            device_type="server",
            device_category="IT",
            os_name="Linux",
            os_version="Ubuntu 22.04",
            endpoint_group="prod-fleet",
            asset_group="finance-cluster",
            last_user="admin@x.test",
            owner_team="Infrastructure",
            asset_tier="T1",
            business_criticality="critical",
            asset_risk_score=8.7,
            lifecycle_state="in_use",
            discovered_at=datetime.now(timezone.utc),
            last_seen=datetime.now(timezone.utc),
            source_connectors=["tenable", "armis"],
            custom_tags={"cost_center": "FIN-42", "env": "prod"},
            notes="Hosts the SAP HANA finance instance.",
        )
        db_session.add(a)
        await db_session.commit()
        await db_session.refresh(a)

        fetched = (
            await db_session.execute(select(Asset).where(Asset.id == a.id))
        ).scalar_one()
        assert fetched.hostname == "prod-sap-01"
        assert fetched.asset_tier == "T1"
        assert fetched.custom_tags == {"cost_center": "FIN-42", "env": "prod"}
        assert "tenable" in fetched.source_connectors

    async def test_lifecycle_transitions(self, db_session: AsyncSession):
        tenant = await _make_tenant(db_session, "asset-lc")
        a = Asset(
            id=uuid.uuid4(),
            tenant_id=tenant.id,
            fingerprint_key="c" * 64,
            hostname="lc-host",
            discovered_at=datetime.now(timezone.utc),
            last_seen=datetime.now(timezone.utc),
        )
        db_session.add(a)
        await db_session.commit()

        a.lifecycle_state = "decommissioned"
        await db_session.commit()
        await db_session.refresh(a)
        assert a.lifecycle_state == "decommissioned"


class TestAssetTenantIsolation:
    async def test_apply_tenant_filter_excludes_other_tenant(
        self, db_session: AsyncSession, reset_tenant_context
    ):
        tenant_a = await _make_tenant(db_session, "iso-asset-a")
        tenant_b = await _make_tenant(db_session, "iso-asset-b")

        for tid, host in (
            (tenant_a.id, "host-a"),
            (tenant_b.id, "host-b"),
        ):
            db_session.add(
                Asset(
                    id=uuid.uuid4(),
                    tenant_id=tid,
                    fingerprint_key=f"{host}-fp".ljust(64, "x"),
                    hostname=host,
                    discovered_at=datetime.now(timezone.utc),
                    last_seen=datetime.now(timezone.utc),
                )
            )
        await db_session.commit()

        TenantContext.set(tenant_a.id)
        rows_a = (
            await db_session.execute(apply_tenant_filter(select(Asset), Asset))
        ).scalars().all()
        assert {r.hostname for r in rows_a} == {"host-a"}

        TenantContext.set(tenant_b.id)
        rows_b = (
            await db_session.execute(apply_tenant_filter(select(Asset), Asset))
        ).scalars().all()
        assert {r.hostname for r in rows_b} == {"host-b"}


class TestRiskAssetFK:
    async def test_risk_can_link_to_asset(self, db_session: AsyncSession):
        tenant = await _make_tenant(db_session, "fk-link")
        asset = Asset(
            id=uuid.uuid4(),
            tenant_id=tenant.id,
            fingerprint_key="d" * 64,
            hostname="risk-host",
            discovered_at=datetime.now(timezone.utc),
            last_seen=datetime.now(timezone.utc),
        )
        db_session.add(asset)
        await db_session.commit()
        await db_session.refresh(asset)

        risk = Risk(
            id=uuid.uuid4(),
            risk_id="RISK-2026-FK01",
            finding="Test FK link",
            source="tenable",
            domain="endpoint",
            cvss_score=9.0,
            severity="high",
            asset="risk-host",
            owner_team="IT",
            status="open",
            sla_deadline=datetime.now(timezone.utc),
            tenant_id=tenant.id,
            asset_id=asset.id,
        )
        db_session.add(risk)
        await db_session.commit()
        await db_session.refresh(risk)

        assert risk.asset_id == asset.id

    async def test_risk_asset_id_optional(self, db_session: AsyncSession):
        tenant = await _make_tenant(db_session, "fk-opt")
        risk = Risk(
            id=uuid.uuid4(),
            risk_id="RISK-2026-FK02",
            finding="Legacy risk without asset",
            source="tenable",
            domain="endpoint",
            cvss_score=5.0,
            severity="medium",
            asset="orphan-host",
            owner_team="IT",
            status="open",
            sla_deadline=datetime.now(timezone.utc),
            tenant_id=tenant.id,
            asset_id=None,
        )
        db_session.add(risk)
        await db_session.commit()
        await db_session.refresh(risk)
        assert risk.asset_id is None
