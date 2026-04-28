"""
backend/services/tasks/control_check_task.py — Periodic Celery task that
re-evaluates compliance controls for every tenant that has the
COMPLIANCE module enabled.

Runs on a 6-hour interval. The compliance backend lives in a separate
package (``compliance/backend/compliance_backend``) but URIP exposes it
via the unified API gateway, so we reuse its ControlEngine here.

Module-level seams
------------------
- ``list_compliance_tenant_ids()`` — tenants with COMPLIANCE module on.
- ``run_controls_for_tenant(tenant_id)`` — runs the engine for one tenant.

Tests mock both seams so they can run without the compliance DB.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from backend.services.celery_app import celery_app


logger = logging.getLogger(__name__)


def list_compliance_tenant_ids() -> list[str]:
    """Tenants with COMPLIANCE module enabled."""
    return asyncio.run(_list_compliance_tenant_ids_async())


async def _list_compliance_tenant_ids_async() -> list[str]:
    from sqlalchemy import select

    from backend.database import async_session
    from backend.models.subscription import TenantSubscription

    async with async_session() as db:
        rows = (
            await db.execute(
                select(TenantSubscription.tenant_id)
                .where(
                    TenantSubscription.module_code == "COMPLIANCE",
                    TenantSubscription.is_enabled.is_(True),
                )
                .distinct()
            )
        ).all()
    return [str(r[0]) for r in rows]


def run_controls_for_tenant(tenant_id: str) -> dict[str, Any]:
    """Run every active control for one tenant."""
    return asyncio.run(_run_controls_for_tenant_async(tenant_id))


async def _run_controls_for_tenant_async(tenant_id: str) -> dict[str, Any]:
    """
    Iterate the tenant's active controls and evaluate each via the
    compliance ControlEngine. We import the engine lazily so tenants
    without the compliance dependencies installed don't break the import.
    """
    try:
        from compliance.backend.compliance_backend.services.control_engine import (
            ControlEngine,
        )
    except Exception:
        logger.warning(
            "control_check_task: compliance package unavailable; skipping tenant %s",
            tenant_id,
        )
        return {"tenant_id": tenant_id, "controls_run": 0, "passed": 0, "skipped": True}

    # The compliance backend has its own session factory under
    # ``compliance.backend.compliance_backend.database``. We open a session
    # there and ask the engine for its active control IDs.
    try:
        from compliance.backend.compliance_backend.database import async_session as _csession  # type: ignore
    except Exception:
        logger.warning(
            "control_check_task: compliance DB module not importable; skipping",
        )
        return {"tenant_id": tenant_id, "controls_run": 0, "passed": 0, "skipped": True}

    controls_run = 0
    passed = 0
    async with _csession() as db:
        engine = ControlEngine(db=db, tenant_id=str(tenant_id))
        try:
            active_controls = await engine.list_active_control_ids()  # type: ignore[attr-defined]
        except AttributeError:
            # Older engine API — fall back to no-op rather than crash the task.
            return {"tenant_id": tenant_id, "controls_run": 0, "passed": 0, "skipped": True}

        for control_id in active_controls:
            try:
                outcome = await engine.run_control(control_id)
                controls_run += 1
                if getattr(outcome, "status", None) == "pass":
                    passed += 1
            except Exception:
                logger.exception(
                    "control_check_task: control %s failed for tenant %s",
                    control_id, tenant_id,
                )

    return {
        "tenant_id": tenant_id,
        "controls_run": controls_run,
        "passed": passed,
    }


@celery_app.task(
    name="backend.services.tasks.control_check_task.control_check_task",
    bind=False,
)
def control_check_task() -> dict[str, Any]:
    """Re-run compliance controls for every COMPLIANCE-enabled tenant."""
    tenant_ids = list_compliance_tenant_ids()
    processed = 0
    errors = 0
    for tid in tenant_ids:
        try:
            run_controls_for_tenant(tid)
            processed += 1
        except Exception:
            logger.exception(
                "control_check_task: tenant %s failed; continuing", tid,
            )
            errors += 1
    return {"tenants_processed": processed, "errors": errors}


__all__ = [
    "control_check_task",
    "list_compliance_tenant_ids",
    "run_controls_for_tenant",
]
