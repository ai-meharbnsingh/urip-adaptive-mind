"""
backend/seeders/backfill_assets.py — One-time backfill: link historical
Risk rows to their (newly-created) Asset rows.

Behaviour
---------
- Idempotent — running twice has the same effect as running once.
- Iterates every Risk row with non-empty `asset` string AND asset_id IS NULL.
- For each such risk, finds OR creates a matching Asset row (per tenant)
  using the same fingerprint scheme (asset_fingerprint_service) as the live
  ingest path.  When the only asset metadata available is a hostname-like
  string (the legacy `asset` column), MAC and IP are passed as None — the
  fingerprint is still deterministic and stable.
- Updates Risk.asset_id and refreshes Asset.last_seen so the rolled-up
  asset_risk_score makes sense afterwards.

Usage
-----
    python -m backend.seeders.backfill_assets
or, called as a function from a migration:
    await backfill_assets(db_session)
"""
from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import async_session
from backend.models.asset import Asset
from backend.models.risk import Risk
from backend.services.asset_fingerprint_service import compute_asset_fingerprint
from backend.services.asset_service import refresh_asset_risk_score

logger = logging.getLogger(__name__)


async def backfill_assets(db: AsyncSession) -> dict[str, int]:
    """
    Walk all Risk rows lacking an asset_id and ensure each is linked to an
    Asset.  Returns a small stats dict for the caller to log/report.
    """
    stats = {"risks_processed": 0, "assets_created": 0, "risks_linked": 0}

    # Pull every (tenant_id, asset, asset_id) triple where asset_id is NULL.
    # We iterate in modest pages so a tenant with hundreds of thousands of
    # legacy risks doesn't blow memory.
    page_size = 500
    last_id: uuid.UUID | None = None
    seen_assets: dict[tuple[uuid.UUID, str], uuid.UUID] = {}

    while True:
        q = (
            select(Risk)
            .where(Risk.asset_id.is_(None))
            .order_by(Risk.id.asc())
            .limit(page_size)
        )
        if last_id is not None:
            q = q.where(Risk.id > last_id)
        rows = (await db.execute(q)).scalars().all()
        if not rows:
            break
        last_id = rows[-1].id

        for risk in rows:
            stats["risks_processed"] += 1
            asset_label = (risk.asset or "").strip()
            if not asset_label:
                continue  # cannot synthesize an asset without identity

            fp = compute_asset_fingerprint(mac=None, hostname=asset_label, ip=None)
            cache_key = (risk.tenant_id, fp)
            asset_id = seen_assets.get(cache_key)

            if asset_id is None:
                existing = (
                    await db.execute(
                        select(Asset).where(
                            Asset.tenant_id == risk.tenant_id,
                            Asset.fingerprint_key == fp,
                        )
                    )
                ).scalar_one_or_none()
                if existing is not None:
                    asset_id = existing.id
                else:
                    now = datetime.now(timezone.utc)
                    new_asset = Asset(
                        id=uuid.uuid4(),
                        tenant_id=risk.tenant_id,
                        fingerprint_key=fp,
                        hostname=asset_label,
                        owner_team=risk.owner_team,
                        asset_tier=(
                            f"T{risk.asset_tier}"
                            if isinstance(risk.asset_tier, int)
                            and 1 <= risk.asset_tier <= 4
                            else None
                        ),
                        lifecycle_state="in_use",
                        discovered_at=risk.created_at or now,
                        last_seen=risk.updated_at or now,
                        source_connectors=[risk.source] if risk.source else [],
                        custom_tags={},
                    )
                    db.add(new_asset)
                    await db.flush()
                    asset_id = new_asset.id
                    stats["assets_created"] += 1

                seen_assets[cache_key] = asset_id

            risk.asset_id = asset_id
            stats["risks_linked"] += 1

        await db.commit()

    # Refresh asset_risk_score on every asset we touched / created.
    for (tenant_id, _fp), aid in seen_assets.items():
        a = (
            await db.execute(select(Asset).where(Asset.id == aid))
        ).scalar_one_or_none()
        if a is not None:
            await refresh_asset_risk_score(db, a)
    await db.commit()

    return stats


async def _main() -> None:
    logging.basicConfig(level=logging.INFO)
    async with async_session() as session:
        stats = await backfill_assets(session)
        logger.info("Backfill complete: %s", stats)


if __name__ == "__main__":  # pragma: no cover — CLI entry point
    asyncio.run(_main())
