"""
backend/services/tasks/scoring_recompute_task.py — Hourly Celery task that
recomputes the RiskScoreSummary snapshot for every active tenant.

The task itself is intentionally a thin orchestration wrapper:

  1. ``list_active_tenant_ids`` returns the set of tenants we should
     process (any tenant with at least one row in tenant_subscriptions).
  2. ``recompute_for_tenant(tenant_id)`` opens a service-managed DB
     session, runs ``RiskAggregateService.write_snapshot``, and returns a
     small status dict.

Both functions are exposed at module level so unit tests can mock them
without spinning up Postgres or the broker.

Why these two helpers exist
---------------------------
- Tests need to verify the task processes EVERY tenant and keeps going
  on errors.  Having dedicated functions to mock keeps the test
  surface narrow and avoids re-mocking SQLAlchemy.
- The same helpers can be reused from a maintenance CLI that reruns
  scoring after a backfill.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from typing import Any

from backend.services.celery_app import celery_app


logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Service-layer helpers (test seam)
# ─────────────────────────────────────────────────────────────────────────────


def list_active_tenant_ids() -> list[str]:
    """Return all tenant ids with at least one subscription row."""
    return asyncio.run(_list_active_tenant_ids_async())


async def _list_active_tenant_ids_async() -> list[str]:
    from sqlalchemy import select

    from backend.database import async_session
    from backend.models.subscription import TenantSubscription

    async with async_session() as db:
        rows = (
            await db.execute(select(TenantSubscription.tenant_id).distinct())
        ).all()
    return [str(r[0]) for r in rows]


def recompute_for_tenant(tenant_id: str) -> dict[str, Any]:
    """Recompute the scoring snapshot for one tenant."""
    return asyncio.run(_recompute_for_tenant_async(tenant_id))


async def _recompute_for_tenant_async(tenant_id: str) -> dict[str, Any]:
    from backend.database import async_session
    from backend.services.risk_aggregate_service import RiskAggregateService

    tenant_uuid = uuid.UUID(str(tenant_id))
    async with async_session() as db:
        svc = RiskAggregateService(db)
        snap = await svc.write_snapshot(tenant_uuid)
    return {
        "tenant_id": tenant_id,
        "open_risks": int(getattr(snap, "open_risks_total", 0) or 0),
    }


# ─────────────────────────────────────────────────────────────────────────────
# Task
# ─────────────────────────────────────────────────────────────────────────────


@celery_app.task(
    name="backend.services.tasks.scoring_recompute_task.scoring_recompute_task",
    bind=False,
)
def scoring_recompute_task() -> dict[str, Any]:
    """Recompute ``RiskScoreSummary`` for every active tenant."""
    tenant_ids = list_active_tenant_ids()
    processed = 0
    errors = 0
    for tid in tenant_ids:
        try:
            recompute_for_tenant(tid)
            processed += 1
        except Exception:
            logger.exception(
                "scoring_recompute_task: tenant %s failed; continuing", tid,
            )
            errors += 1
    return {"tenants_processed": processed, "errors": errors}


__all__ = [
    "scoring_recompute_task",
    "list_active_tenant_ids",
    "recompute_for_tenant",
]
