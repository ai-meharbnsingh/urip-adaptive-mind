"""
backend/services/tasks/connector_pull_task.py — Celery task that pulls
findings from a single (tenant, connector) pair and ingests them into the
URIP risk database.

Two callables are exposed:

  connector_pull_task(tenant_id, connector_name)
      The unit-of-work task. Idempotent: running it twice in a row only
      adds new findings (the de-dup happens in connector_runner).

  connector_pull_fanout()
      The Beat-scheduled entrypoint. Every 15 minutes it asks the DB for
      every (tenant, connector) credential pair and queues one
      ``connector_pull_task`` per pair so they can run in parallel.

The actual ingest logic lives in run_connector_for_tenant — this is the
seam tests mock.  No DB session is opened in the eager test path because
the helper is fully patched.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from backend.services.celery_app import celery_app


logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Service-layer helpers (test seam — patch these in unit tests).
# ─────────────────────────────────────────────────────────────────────────────


def run_connector_for_tenant(tenant_id: str, connector_name: str) -> dict[str, Any]:
    """
    Authenticate the named connector for the given tenant, fetch the last
    15 minutes of findings, normalize each one, and persist via the
    universal Intelligence Engine ingest pipeline (de-dup + enrichment).

    Returns a small status dict ``{"tenant_id", "connector", "ingested",
    "skipped", "errors"}``. Errors during normalisation are counted, not
    raised — a single bad finding shouldn't abort the entire pull.

    This is a thin wrapper around the same code path used by the
    /api/connectors/{name}/run REST endpoint; we factor it out here so the
    Celery worker shares one implementation with the API.
    """
    # Imported lazily so test-time monkey-patching of this module attribute
    # works even if the heavy backend import chain isn't loaded.
    from backend.services._connector_pull_runner import run_connector_pull

    return asyncio.run(run_connector_pull(tenant_id, connector_name))


def list_pending_connector_jobs() -> list[tuple[str, str]]:
    """
    Return the list of (tenant_id, connector_name) pairs that have stored
    credentials (i.e. are configured to be polled).
    """
    from backend.services._connector_pull_runner import list_configured_pairs

    return asyncio.run(list_configured_pairs())


# ─────────────────────────────────────────────────────────────────────────────
# Tasks
# ─────────────────────────────────────────────────────────────────────────────


@celery_app.task(
    name="backend.services.tasks.connector_pull_task.connector_pull_task",
    bind=True,
    max_retries=3,
    default_retry_delay=60,
)
def connector_pull_task(self, tenant_id: str, connector_name: str) -> dict[str, Any]:  # type: ignore[no-untyped-def]
    """Per-(tenant, connector) ingest task."""
    try:
        return run_connector_for_tenant(tenant_id, connector_name)
    except Exception as exc:  # pragma: no cover — surfaced via Celery retry
        logger.exception(
            "connector_pull_task failed (tenant=%s, connector=%s)",
            tenant_id, connector_name,
        )
        raise self.retry(exc=exc) from exc


@celery_app.task(
    name="backend.services.tasks.connector_pull_task.connector_pull_fanout",
    bind=False,
)
def connector_pull_fanout() -> dict[str, Any]:
    """
    Beat-scheduled task. Lists every configured (tenant, connector) pair
    and queues a ``connector_pull_task`` for each. The fan-out task itself
    returns quickly so the beat tick stays cheap.
    """
    pairs = list_pending_connector_jobs()
    queued = 0
    for tenant_id, connector_name in pairs:
        connector_pull_task.delay(tenant_id, connector_name)
        queued += 1
    return {"queued": queued, "pairs": pairs}


__all__ = [
    "connector_pull_task",
    "connector_pull_fanout",
    "run_connector_for_tenant",
    "list_pending_connector_jobs",
]
