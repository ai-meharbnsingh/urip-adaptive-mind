"""
Backfill seeder tests — link historical Risk rows to Asset rows.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.asset import Asset
from backend.models.risk import Risk
from backend.models.tenant import Tenant
from backend.seeders.backfill_assets import backfill_assets


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


def _legacy_risk(tenant_id, asset_label: str, score: float = 5.0) -> Risk:
    return Risk(
        id=uuid.uuid4(),
        risk_id=f"RISK-LEG-{uuid.uuid4().hex[:6]}",
        finding=f"Legacy finding on {asset_label}",
        source="vapt",
        domain="endpoint",
        cvss_score=score,
        severity="medium",
        asset=asset_label,
        owner_team="LegacyOwner",
        status="open",
        sla_deadline=datetime.now(timezone.utc),
        tenant_id=tenant_id,
        asset_id=None,  # legacy → not yet linked
        composite_score=score,
    )


class TestBackfill:
    async def test_creates_assets_and_links(self, db_session: AsyncSession):
        tenant = await _make_tenant(db_session, "bf-1")
        for name in ("legacy-1", "legacy-2", "legacy-1"):  # 2 unique hosts, 3 risks
            db_session.add(_legacy_risk(tenant.id, name))
        await db_session.commit()

        stats = await backfill_assets(db_session)

        assert stats["risks_processed"] == 3
        assert stats["assets_created"] == 2
        assert stats["risks_linked"] == 3

        # Two asset rows
        rows = (
            await db_session.execute(
                select(Asset).where(Asset.tenant_id == tenant.id)
            )
        ).scalars().all()
        assert len(rows) == 2
        assert {r.hostname for r in rows} == {"legacy-1", "legacy-2"}

        # All risks now linked
        linked = (
            await db_session.execute(
                select(Risk).where(Risk.tenant_id == tenant.id)
            )
        ).scalars().all()
        assert all(r.asset_id is not None for r in linked)

    async def test_idempotent(self, db_session: AsyncSession):
        tenant = await _make_tenant(db_session, "bf-2")
        db_session.add(_legacy_risk(tenant.id, "idem-host", score=8.0))
        await db_session.commit()

        s1 = await backfill_assets(db_session)
        s2 = await backfill_assets(db_session)

        assert s1["risks_linked"] == 1
        # Second pass finds no NULL asset_id rows
        assert s2["risks_processed"] == 0
        assert s2["assets_created"] == 0
        assert s2["risks_linked"] == 0

        rows = (
            await db_session.execute(
                select(Asset).where(Asset.tenant_id == tenant.id)
            )
        ).scalars().all()
        assert len(rows) == 1

    async def test_skips_risks_with_empty_asset_label(
        self, db_session: AsyncSession
    ):
        tenant = await _make_tenant(db_session, "bf-3")
        # Risk with empty asset string — cannot synthesize, must be skipped.
        r = Risk(
            id=uuid.uuid4(),
            risk_id="RISK-EMPTY-1",
            finding="No asset label",
            source="vapt",
            domain="endpoint",
            cvss_score=5.0,
            severity="medium",
            asset="",
            owner_team="x",
            status="open",
            sla_deadline=datetime.now(timezone.utc),
            tenant_id=tenant.id,
            asset_id=None,
        )
        db_session.add(r)
        await db_session.commit()

        stats = await backfill_assets(db_session)
        assert stats["risks_processed"] == 1
        assert stats["risks_linked"] == 0
        assert stats["assets_created"] == 0
