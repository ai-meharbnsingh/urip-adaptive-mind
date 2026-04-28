"""
Asset service tests — upsert/dedupe/category/score/pagination.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.asset import Asset
from backend.models.risk import Risk
from backend.models.tenant import Tenant
from backend.services import asset_service
from backend.services.asset_fingerprint_service import compute_asset_fingerprint
from backend.services.asset_service import AssetFilters, categorize_asset


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


# ─────────────────────────────────────────────────────────────────────────────
# upsert_asset
# ─────────────────────────────────────────────────────────────────────────────


class TestUpsertAsset:
    async def test_creates_new_asset(self, db_session: AsyncSession):
        tenant = await _make_tenant(db_session, "ups-new")
        raw = {
            "hostname": "web-01",
            "ip": "10.0.0.5",
            "mac": "aa:bb:cc:dd:ee:01",
            "device_type": "server",
            "device_category": "IT",
            "os_name": "Linux",
            "owner_team": "DevOps",
            "asset_tier": "T1",
        }
        asset = await asset_service.upsert_asset(
            db_session,
            tenant_id=tenant.id,
            raw_data=raw,
            source_connector="tenable",
        )
        await db_session.commit()
        await db_session.refresh(asset)

        assert asset.hostname == "web-01"
        assert asset.internal_ip == "10.0.0.5"
        assert asset.device_category == "IT"
        assert asset.asset_tier == "T1"
        assert "tenable" in asset.source_connectors

    async def test_dedupe_by_fingerprint(self, db_session: AsyncSession):
        tenant = await _make_tenant(db_session, "ups-dedupe")
        raw = {"hostname": "dup-host", "ip": "10.0.0.1", "mac": "aa:aa:aa:aa:aa:aa"}

        a1 = await asset_service.upsert_asset(
            db_session, tenant_id=tenant.id, raw_data=raw, source_connector="tenable"
        )
        await db_session.commit()
        original_id = a1.id
        original_discovered = a1.discovered_at

        # Same fingerprint, different connector
        a2 = await asset_service.upsert_asset(
            db_session,
            tenant_id=tenant.id,
            raw_data=raw,
            source_connector="sentinelone",
        )
        await db_session.commit()
        await db_session.refresh(a2)

        assert a2.id == original_id
        # Compare without tz info — SQLite does not preserve tzinfo on
        # roundtrip, but the underlying value is the same instant.
        def _strip_tz(dt):
            return dt.replace(tzinfo=None) if dt.tzinfo else dt

        assert _strip_tz(a2.discovered_at) == _strip_tz(original_discovered)
        assert _strip_tz(a2.last_seen) >= _strip_tz(original_discovered)
        # Source list now has both
        assert set(a2.source_connectors) == {"tenable", "sentinelone"}

        # Only one row total
        count = (
            await db_session.execute(
                select(Asset).where(Asset.tenant_id == tenant.id)
            )
        ).scalars().all()
        assert len(count) == 1

    async def test_fills_empty_fields_only(self, db_session: AsyncSession):
        tenant = await _make_tenant(db_session, "ups-fill")
        raw1 = {
            "hostname": "fill-host",
            "ip": "10.0.0.50",
            "mac": "ff:ff:ff:ff:ff:ff",
            "owner_team": "OriginalOwner",
        }
        a1 = await asset_service.upsert_asset(
            db_session,
            tenant_id=tenant.id,
            raw_data=raw1,
            source_connector="tenable",
        )
        await db_session.commit()

        # Subsequent upsert tries to overwrite owner_team but should be ignored,
        # while os_name (previously None) should be filled in.
        raw2 = {
            "hostname": "fill-host",
            "ip": "10.0.0.50",
            "mac": "ff:ff:ff:ff:ff:ff",
            "owner_team": "DifferentOwner",
            "os_name": "Linux",
        }
        a2 = await asset_service.upsert_asset(
            db_session,
            tenant_id=tenant.id,
            raw_data=raw2,
            source_connector="armis",
        )
        await db_session.commit()
        await db_session.refresh(a2)

        assert a2.owner_team == "OriginalOwner"  # not overwritten
        assert a2.os_name == "Linux"  # filled in

    async def test_revives_decommissioned_on_rediscovery(
        self, db_session: AsyncSession
    ):
        tenant = await _make_tenant(db_session, "ups-revive")
        raw = {"hostname": "revive-host", "ip": "10.0.0.99", "mac": "aa:00:00:00:00:00"}
        a1 = await asset_service.upsert_asset(
            db_session, tenant_id=tenant.id, raw_data=raw, source_connector="tenable"
        )
        await db_session.commit()

        a1.lifecycle_state = "decommissioned"
        await db_session.commit()

        a2 = await asset_service.upsert_asset(
            db_session, tenant_id=tenant.id, raw_data=raw, source_connector="tenable"
        )
        await db_session.commit()
        await db_session.refresh(a2)
        assert a2.lifecycle_state == "in_use"

    async def test_tenant_isolation_in_upsert(self, db_session: AsyncSession):
        tenant_a = await _make_tenant(db_session, "ups-iso-a")
        tenant_b = await _make_tenant(db_session, "ups-iso-b")
        raw = {"hostname": "shared-name", "ip": "10.1.1.1", "mac": "11:11:11:11:11:11"}

        a_a = await asset_service.upsert_asset(
            db_session, tenant_id=tenant_a.id, raw_data=raw, source_connector="x"
        )
        a_b = await asset_service.upsert_asset(
            db_session, tenant_id=tenant_b.id, raw_data=raw, source_connector="x"
        )
        await db_session.commit()

        # Same fingerprint, different tenants — must be separate rows
        assert a_a.id != a_b.id
        assert a_a.fingerprint_key == a_b.fingerprint_key

    async def test_hostname_only_still_creates_row(self, db_session: AsyncSession):
        # Backward compat: legacy connectors only know the hostname string.
        tenant = await _make_tenant(db_session, "ups-host-only")
        raw = {"hostname": "minimal-host"}
        a = await asset_service.upsert_asset(
            db_session, tenant_id=tenant.id, raw_data=raw, source_connector="legacy"
        )
        await db_session.commit()
        await db_session.refresh(a)
        assert a.hostname == "minimal-host"
        # Fingerprint must be deterministic and stable for hostname-only input.
        assert a.fingerprint_key == compute_asset_fingerprint(
            mac=None, hostname="minimal-host", ip=None
        )


# ─────────────────────────────────────────────────────────────────────────────
# categorize_asset
# ─────────────────────────────────────────────────────────────────────────────


class TestCategorizeAsset:
    def _make_asset(self, **kwargs) -> Asset:
        defaults = dict(
            id=uuid.uuid4(),
            tenant_id=uuid.uuid4(),
            fingerprint_key="x" * 64,
            hostname="x",
            lifecycle_state="in_use",
            discovered_at=datetime.now(timezone.utc),
            last_seen=datetime.now(timezone.utc),
            source_connectors=[],
            custom_tags={},
        )
        defaults.update(kwargs)
        return Asset(**defaults)

    def test_device_type_laptop_to_devices(self):
        assert categorize_asset(self._make_asset(device_type="laptop")) == "Devices"

    def test_device_type_cloud_workload(self):
        assert (
            categorize_asset(self._make_asset(device_type="cloud_workload"))
            == "Cloud Assets"
        )

    def test_device_type_saas_account(self):
        assert (
            categorize_asset(self._make_asset(device_type="saas_account"))
            == "Accounts"
        )

    def test_device_type_api(self):
        assert (
            categorize_asset(self._make_asset(device_type="api"))
            == "API Collections"
        )

    def test_easm_connector_to_internet_facing(self):
        a = self._make_asset(device_type=None, source_connectors=["easm"])
        assert categorize_asset(a) == "Internet-Facing Assets"

    def test_aws_connector_to_cloud(self):
        a = self._make_asset(device_type=None, source_connectors=["aws_cspm"])
        assert categorize_asset(a) == "Cloud Assets"

    def test_ms_entra_to_accounts(self):
        a = self._make_asset(device_type=None, source_connectors=["ms_entra"])
        assert categorize_asset(a) == "Accounts"

    def test_unknown_falls_back_to_devices(self):
        a = self._make_asset(device_type=None, source_connectors=[])
        assert categorize_asset(a) == "Devices"


# ─────────────────────────────────────────────────────────────────────────────
# compute_asset_risk_score
# ─────────────────────────────────────────────────────────────────────────────


class TestRiskScore:
    async def test_zero_when_no_risks(self, db_session: AsyncSession):
        tenant = await _make_tenant(db_session, "score-empty")
        a = await asset_service.upsert_asset(
            db_session,
            tenant_id=tenant.id,
            raw_data={"hostname": "score-empty"},
            source_connector="x",
        )
        await db_session.commit()
        score = await asset_service.compute_asset_risk_score(db_session, a)
        assert score == 0.0

    async def test_max_of_open_risks(self, db_session: AsyncSession):
        tenant = await _make_tenant(db_session, "score-max")
        a = await asset_service.upsert_asset(
            db_session,
            tenant_id=tenant.id,
            raw_data={"hostname": "score-max"},
            source_connector="x",
        )
        await db_session.commit()
        await db_session.refresh(a)

        for i, score in enumerate([5.0, 9.5, 7.2]):
            db_session.add(
                Risk(
                    id=uuid.uuid4(),
                    risk_id=f"RISK-SCORE-{i}",
                    finding=f"Risk {i}",
                    source="tenable",
                    domain="endpoint",
                    cvss_score=score,
                    severity="high",
                    asset="score-max",
                    owner_team="x",
                    status="open",
                    sla_deadline=datetime.now(timezone.utc),
                    tenant_id=tenant.id,
                    asset_id=a.id,
                    composite_score=score,
                )
            )
        await db_session.commit()

        score = await asset_service.compute_asset_risk_score(db_session, a)
        assert score == 9.5

    async def test_closed_risks_excluded(self, db_session: AsyncSession):
        tenant = await _make_tenant(db_session, "score-closed")
        a = await asset_service.upsert_asset(
            db_session,
            tenant_id=tenant.id,
            raw_data={"hostname": "score-closed"},
            source_connector="x",
        )
        await db_session.commit()
        await db_session.refresh(a)

        db_session.add(
            Risk(
                id=uuid.uuid4(),
                risk_id="RISK-CL-1",
                finding="Closed high",
                source="tenable",
                domain="endpoint",
                cvss_score=9.9,
                severity="critical",
                asset="score-closed",
                owner_team="x",
                status="closed",  # not open
                sla_deadline=datetime.now(timezone.utc),
                tenant_id=tenant.id,
                asset_id=a.id,
                composite_score=9.9,
            )
        )
        db_session.add(
            Risk(
                id=uuid.uuid4(),
                risk_id="RISK-CL-2",
                finding="Open medium",
                source="tenable",
                domain="endpoint",
                cvss_score=4.0,
                severity="medium",
                asset="score-closed",
                owner_team="x",
                status="open",
                sla_deadline=datetime.now(timezone.utc),
                tenant_id=tenant.id,
                asset_id=a.id,
                composite_score=4.0,
            )
        )
        await db_session.commit()

        score = await asset_service.compute_asset_risk_score(db_session, a)
        assert score == 4.0  # closed 9.9 ignored

    async def test_falls_back_to_cvss_when_composite_null(
        self, db_session: AsyncSession
    ):
        tenant = await _make_tenant(db_session, "score-fallback")
        a = await asset_service.upsert_asset(
            db_session,
            tenant_id=tenant.id,
            raw_data={"hostname": "score-fallback"},
            source_connector="x",
        )
        await db_session.commit()
        await db_session.refresh(a)

        db_session.add(
            Risk(
                id=uuid.uuid4(),
                risk_id="RISK-FB-1",
                finding="No composite",
                source="tenable",
                domain="endpoint",
                cvss_score=7.5,
                severity="high",
                asset="score-fallback",
                owner_team="x",
                status="open",
                sla_deadline=datetime.now(timezone.utc),
                tenant_id=tenant.id,
                asset_id=a.id,
                composite_score=None,
            )
        )
        await db_session.commit()
        score = await asset_service.compute_asset_risk_score(db_session, a)
        assert score == 7.5


# ─────────────────────────────────────────────────────────────────────────────
# list_assets_paginated + count_by_category
# ─────────────────────────────────────────────────────────────────────────────


class TestListPaginated:
    async def test_pagination_and_filter(self, db_session: AsyncSession):
        tenant = await _make_tenant(db_session, "list-pag")
        # Build 5 assets
        for i in range(5):
            await asset_service.upsert_asset(
                db_session,
                tenant_id=tenant.id,
                raw_data={
                    "hostname": f"list-{i}",
                    "ip": f"10.0.0.{i}",
                    "mac": f"aa:00:00:00:00:0{i}",
                    "device_category": "IT" if i % 2 == 0 else "OT",
                    "asset_tier": "T1" if i == 0 else "T3",
                },
                source_connector="tenable",
            )
        await db_session.commit()

        rows, total = await asset_service.list_assets_paginated(
            db_session, tenant.id, AssetFilters(), page=1, limit=3
        )
        assert total == 5
        assert len(rows) == 3

        # Filter device_category=IT (i=0,2,4 → 3 rows)
        rows_it, total_it = await asset_service.list_assets_paginated(
            db_session,
            tenant.id,
            AssetFilters(device_category="IT"),
            page=1,
            limit=20,
        )
        assert total_it == 3

        # Filter asset_tier T1 (i=0 only)
        rows_t1, total_t1 = await asset_service.list_assets_paginated(
            db_session,
            tenant.id,
            AssetFilters(asset_tier="T1"),
            page=1,
            limit=20,
        )
        assert total_t1 == 1

    async def test_search_filter(self, db_session: AsyncSession):
        tenant = await _make_tenant(db_session, "list-search")
        for h in ("alpha-prd", "beta-prd", "alpha-dev"):
            await asset_service.upsert_asset(
                db_session,
                tenant_id=tenant.id,
                raw_data={"hostname": h, "ip": "10.0.1.0", "mac": h},
                source_connector="tenable",
            )
        await db_session.commit()
        rows, total = await asset_service.list_assets_paginated(
            db_session,
            tenant.id,
            AssetFilters(search="alpha"),
            page=1,
            limit=20,
        )
        assert total == 2
        assert {r.hostname for r in rows} == {"alpha-prd", "alpha-dev"}

    async def test_tenant_isolation_in_list(self, db_session: AsyncSession):
        tenant_a = await _make_tenant(db_session, "list-iso-a")
        tenant_b = await _make_tenant(db_session, "list-iso-b")
        await asset_service.upsert_asset(
            db_session,
            tenant_id=tenant_a.id,
            raw_data={"hostname": "iso-a-host"},
            source_connector="x",
        )
        await asset_service.upsert_asset(
            db_session,
            tenant_id=tenant_b.id,
            raw_data={"hostname": "iso-b-host"},
            source_connector="x",
        )
        await db_session.commit()

        rows_a, total_a = await asset_service.list_assets_paginated(
            db_session, tenant_a.id, AssetFilters(), 1, 50
        )
        assert {r.hostname for r in rows_a} == {"iso-a-host"}
        assert total_a == 1


class TestCountByCategory:
    async def test_counts_buckets_correctly(self, db_session: AsyncSession):
        tenant = await _make_tenant(db_session, "cnt-bk")
        rows = [
            ({"hostname": "lap-1", "device_type": "laptop"}, "x"),
            ({"hostname": "srv-1", "device_type": "server"}, "x"),
            ({"hostname": "ws-1", "device_type": "cloud_workload"}, "x"),
            ({"hostname": "api-1", "device_type": "api"}, "x"),
            ({"hostname": "easm-1"}, "easm"),
        ]
        for raw, source in rows:
            await asset_service.upsert_asset(
                db_session,
                tenant_id=tenant.id,
                raw_data=raw,
                source_connector=source,
            )
        await db_session.commit()

        counts = await asset_service.count_by_category(db_session, tenant.id)
        assert counts["Devices"] == 2          # lap + server
        assert counts["Cloud Assets"] == 1
        assert counts["API Collections"] == 1
        assert counts["Internet-Facing Assets"] == 1


# ─────────────────────────────────────────────────────────────────────────────
# get_asset_with_risks + timeline
# ─────────────────────────────────────────────────────────────────────────────


class TestGetWithRisks:
    async def test_bundles_open_risks(self, db_session: AsyncSession):
        tenant = await _make_tenant(db_session, "bundle")
        asset = await asset_service.upsert_asset(
            db_session,
            tenant_id=tenant.id,
            raw_data={"hostname": "bundle-host"},
            source_connector="tenable",
        )
        await db_session.commit()
        await db_session.refresh(asset)

        for i, sev in enumerate(("critical", "high", "low")):
            db_session.add(
                Risk(
                    id=uuid.uuid4(),
                    risk_id=f"RISK-B-{i}",
                    finding=f"Bundle risk {i}",
                    source="tenable",
                    domain="endpoint",
                    cvss_score=9.0 - i,
                    severity=sev,
                    asset="bundle-host",
                    owner_team="x",
                    status="open",
                    sla_deadline=datetime.now(timezone.utc),
                    tenant_id=tenant.id,
                    asset_id=asset.id,
                    composite_score=9.0 - i,
                )
            )
        await db_session.commit()

        bundle = await asset_service.get_asset_with_risks(
            db_session, tenant.id, asset.id
        )
        assert bundle is not None
        assert bundle.risk_count == 3
        assert bundle.max_score == 9.0
        assert "tenable" in bundle.sources

    async def test_returns_none_for_other_tenant(
        self, db_session: AsyncSession
    ):
        tenant_a = await _make_tenant(db_session, "bdl-a")
        tenant_b = await _make_tenant(db_session, "bdl-b")
        asset = await asset_service.upsert_asset(
            db_session,
            tenant_id=tenant_a.id,
            raw_data={"hostname": "bdl-host"},
            source_connector="x",
        )
        await db_session.commit()
        bundle = await asset_service.get_asset_with_risks(
            db_session, tenant_b.id, asset.id
        )
        assert bundle is None


class TestTimeline:
    async def test_includes_discovery_and_risk_events(
        self, db_session: AsyncSession
    ):
        tenant = await _make_tenant(db_session, "tl")
        asset = await asset_service.upsert_asset(
            db_session,
            tenant_id=tenant.id,
            raw_data={"hostname": "tl-host"},
            source_connector="x",
        )
        await db_session.commit()
        await db_session.refresh(asset)

        db_session.add(
            Risk(
                id=uuid.uuid4(),
                risk_id="RISK-TL-1",
                finding="Open timeline risk",
                source="tenable",
                domain="endpoint",
                cvss_score=8.0,
                severity="high",
                asset="tl-host",
                owner_team="x",
                status="open",
                sla_deadline=datetime.now(timezone.utc),
                tenant_id=tenant.id,
                asset_id=asset.id,
                composite_score=8.0,
            )
        )
        db_session.add(
            Risk(
                id=uuid.uuid4(),
                risk_id="RISK-TL-2",
                finding="Closed timeline risk",
                source="tenable",
                domain="endpoint",
                cvss_score=5.0,
                severity="medium",
                asset="tl-host",
                owner_team="x",
                status="resolved",
                sla_deadline=datetime.now(timezone.utc),
                tenant_id=tenant.id,
                asset_id=asset.id,
                composite_score=5.0,
            )
        )
        await db_session.commit()

        events = await asset_service.get_asset_timeline(
            db_session, tenant.id, asset.id
        )
        types = [e.event_type for e in events]
        assert "discovered" in types
        assert "risk_added" in types
        assert "risk_resolved" in types
        # discovered must be first chronologically
        assert events[0].event_type == "discovered"
