"""
compliance_score_simulator — generate ComplianceScoreSnapshot trend.

Behavior:
  - For each Framework × each day in the window, write one snapshot.
  - Score follows a smooth ramp from `start_score` (default 65.0) to
    `end_score` (default 87.0) plus minor day-to-day jitter (±1.5).
  - pass_count + fail_count are derived from the score and a synthetic
    total_applicable (the actual control count for the framework).
  - inconclusive_count is small (~3-5% of total) — does not enter denominator.

Idempotency: skip if any snapshots exist for tenant.
"""
from __future__ import annotations

import math
import random
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from compliance_backend.models.framework import Framework, FrameworkVersion, Control
from compliance_backend.models.score_snapshot import ComplianceScoreSnapshot
from compliance_backend.seeders.simulators._common import (
    make_rng,
    stable_uuid,
    now_utc,
)


def _ramp_score(t: float, start: float, end: float, jitter: float, rng: random.Random) -> float:
    """
    Smooth interpolation start → end at fraction t in [0, 1] + small jitter.
    Slightly S-curve so the climb feels organic rather than linear.
    """
    # Smooth-step function
    s = t * t * (3 - 2 * t)
    base = start + (end - start) * s
    return max(0.0, min(100.0, base + rng.uniform(-jitter, jitter)))


async def simulate_compliance_score_history(
    session: AsyncSession,
    *,
    tenant_id: str,
    days: int = 90,
    start_score: float = 65.0,
    end_score: float = 87.0,
    jitter: float = 1.5,
    seed: int = 42,
    skip_if_existing: bool = True,
) -> dict[str, int]:
    """
    Generate `days` daily snapshots per framework for a tenant.

    Args:
        tenant_id:        Tenant scope.
        days:             How many days of history (default 90).
        start_score:      Score at day -days (default 65.0).
        end_score:        Score at day 0 / today (default 87.0).
        jitter:           ±jitter on top of the ramp (default 1.5).
        seed:             RNG seed.
        skip_if_existing: No-op if any snapshots exist for tenant.
    """
    rng = make_rng(seed)

    if skip_if_existing:
        existing = (await session.execute(
            select(func.count()).select_from(ComplianceScoreSnapshot).where(
                ComplianceScoreSnapshot.tenant_id == tenant_id
            )
        )).scalar() or 0
        if existing > 0:
            return {
                "snapshots": 0,
                "frameworks": 0,
                "skipped": existing,
                "tenant_id": tenant_id,
            }

    frameworks = (await session.execute(select(Framework))).scalars().all()
    if not frameworks:
        return {
            "snapshots": 0,
            "frameworks": 0,
            "tenant_id": tenant_id,
            "warning": "no frameworks; run framework seeders first",
        }

    snapshots_created = 0
    today = datetime.utcnow().replace(hour=12, minute=0, second=0, microsecond=0)

    for fw in frameworks:
        # Get total controls for this framework
        versions = (await session.execute(
            select(FrameworkVersion).where(FrameworkVersion.framework_id == fw.id)
        )).scalars().all()
        total_controls = 0
        for v in versions:
            cnt = (await session.execute(
                select(func.count()).select_from(Control).where(
                    Control.framework_version_id == v.id
                )
            )).scalar() or 0
            total_controls += cnt
        if total_controls == 0:
            continue

        for d in range(days):
            day_offset = days - d - 1  # day 0 = oldest, day N = today
            snapshot_date = today - timedelta(days=day_offset)
            t = d / max(1, days - 1)
            score = _ramp_score(t, start_score, end_score, jitter, rng)

            # Inconclusive ~ 3-7% of total
            inconclusive = max(0, int(total_controls * rng.uniform(0.03, 0.07)))
            total_applicable = total_controls - inconclusive
            pass_count = int(round(total_applicable * (score / 100.0)))
            fail_count = total_applicable - pass_count

            snap = ComplianceScoreSnapshot(
                id=stable_uuid(tenant_id, "score_snap", fw.id, str(snapshot_date.date())),
                tenant_id=tenant_id,
                framework_id=fw.id,
                snapshot_date=snapshot_date,
                score=round(score, 2),
                pass_count=pass_count,
                fail_count=fail_count,
                inconclusive_count=inconclusive,
                total_applicable=total_applicable,
            )
            session.add(snap)
            snapshots_created += 1

    await session.flush()
    return {
        "snapshots": snapshots_created,
        "frameworks": len(frameworks),
        "skipped": 0,
        "tenant_id": tenant_id,
    }
