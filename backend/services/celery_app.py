"""
backend/services/celery_app.py — Celery application factory.

Wires up the URIP Celery app with Redis as both broker and result backend,
auto-discovers task modules under backend.services.tasks, and registers a
beat schedule with three periodic jobs:

    connector-pull-every-15min    → pulls findings from every configured
                                    (tenant, connector) pair
    scoring-recompute-hourly      → recomputes RiskScoreSummary snapshots
    control-check-every-6h        → re-evaluates compliance controls

Operational notes
-----------------
- Broker / backend URL is read from settings.REDIS_URL. When unset (the
  default in dev / tests), we fall back to redis://localhost:6379/0 so the
  worker can still boot — this keeps `celery -A backend.services.celery_app
  worker` runnable without an explicit env var.
- For tests we honour CELERY_TASK_ALWAYS_EAGER=true so .delay() runs the
  task body inline and tests don't need a real broker.
- Tasks are intentionally "thin wrappers" over service-layer functions so
  the same code path is reachable from a FastAPI endpoint, a unit test,
  and the Celery worker.
"""

from __future__ import annotations

import logging
import os

from celery import Celery
from celery.schedules import schedule as _interval_schedule

from backend.config import settings


logger = logging.getLogger(__name__)


def _default_redis_url() -> str:
    """
    Return the broker URL, preferring settings.REDIS_URL but falling back to
    a localhost default so the worker can boot in dev without env tweaks.
    """
    if settings.REDIS_URL:
        return settings.REDIS_URL
    return "redis://localhost:6379/0"


def _coerce_bool(env_value: str | None) -> bool:
    if env_value is None:
        return False
    return env_value.strip().lower() in {"1", "true", "yes", "on"}


def make_celery_app() -> Celery:
    """Build the configured Celery app."""
    broker_url = _default_redis_url()

    app = Celery(
        "urip",
        broker=broker_url,
        backend=broker_url,
        # auto-discovery scans these packages for ``tasks.py`` modules — we
        # use an explicit ``include`` list since our tasks live in their
        # own per-task modules.
        include=[
            "backend.services.tasks.connector_pull_task",
            "backend.services.tasks.scoring_recompute_task",
            "backend.services.tasks.control_check_task",
        ],
    )

    # ── Common config ───────────────────────────────────────────────────
    app.conf.update(
        # Serialization — JSON only for safety (no pickle).
        task_serializer="json",
        accept_content=["json"],
        result_serializer="json",
        timezone="UTC",
        enable_utc=True,
        # Resilience knobs — keep retries reasonable so a flaky vendor API
        # doesn't pile up jobs in the broker.
        task_acks_late=True,
        task_reject_on_worker_lost=True,
        worker_prefetch_multiplier=1,
        # Result expiration — periodic jobs don't need to keep results
        # around forever.
        result_expires=24 * 60 * 60,
    )

    # ── Eager mode for tests ────────────────────────────────────────────
    if _coerce_bool(os.environ.get("CELERY_TASK_ALWAYS_EAGER")):
        app.conf.update(
            task_always_eager=True,
            task_eager_propagates=True,
        )

    # ── Beat schedule ───────────────────────────────────────────────────
    # The three periodic jobs are configured here so a single source of
    # truth controls how often they run. We reference the task body by
    # its full dotted name (``backend.services.tasks.<module>.<task>``)
    # so the beat scheduler picks the registered task even before the
    # task module has been imported by an entry point.
    app.conf.beat_schedule = {
        "connector-pull-every-15min": {
            "task": "backend.services.tasks.connector_pull_task.connector_pull_fanout",
            "schedule": _interval_schedule(run_every=15 * 60),
        },
        "scoring-recompute-hourly": {
            "task": "backend.services.tasks.scoring_recompute_task.scoring_recompute_task",
            "schedule": _interval_schedule(run_every=60 * 60),
        },
        "control-check-every-6h": {
            "task": "backend.services.tasks.control_check_task.control_check_task",
            "schedule": _interval_schedule(run_every=6 * 60 * 60),
        },
    }

    return app


# Module-level singleton — ``celery -A backend.services.celery_app`` looks
# for an attribute called ``celery_app`` (or ``app``) on the target module.
celery_app = make_celery_app()
app = celery_app  # alias for ``-A backend.services.celery_app`` convention


__all__ = ["celery_app", "app", "make_celery_app"]
