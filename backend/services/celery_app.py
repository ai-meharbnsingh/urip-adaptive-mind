"""
backend/services/celery_app.py — Celery application factory.

Celery is OPTIONAL at import time.  The try/except around `from celery import
Celery` means that backend.main (and any module that imports backend.services)
can be imported in environments where celery is not installed — for example a
minimal CI environment or a unit-test run that does not exercise task dispatch.
The runtime guard in ``make_celery_app()`` fires only when the Celery app is
actually *constructed* (i.e. when a worker, beat scheduler, or task-dispatch
call reaches that function), so ``from backend.services import celery_app``
succeeds but yields ``None`` when celery is absent.

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
from typing import TYPE_CHECKING

from backend.config import settings

# ---------------------------------------------------------------------------
# Optional celery import — keeps the module importable in minimal environments
# ---------------------------------------------------------------------------
try:
    from celery import Celery
    from celery.schedules import schedule as _interval_schedule

    _CELERY_AVAILABLE = True
except ImportError:
    _CELERY_AVAILABLE = False
    Celery = None  # type: ignore[assignment,misc]
    _interval_schedule = None  # type: ignore[assignment]

if TYPE_CHECKING:
    # For type checkers (mypy / pyright) only — not executed at runtime.
    from celery import Celery as _CeleryType  # noqa: F401


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


def make_celery_app() -> "Celery":
    """Build the configured Celery app.

    Raises RuntimeError when called in an environment where celery is not
    installed.  Set URIP_CELERY_OPTIONAL=1 to skip celery task dispatch
    gracefully in tests that do not exercise the worker path.
    """
    if not _CELERY_AVAILABLE:
        raise RuntimeError(
            "celery is not installed — run `pip install -r requirements.txt`. "
            "If you're running tests without celery, set "
            "URIP_CELERY_OPTIONAL=1 to skip celery tasks gracefully."
        )

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


# ---------------------------------------------------------------------------
# Module-level singleton — ``celery -A backend.services.celery_app`` looks
# for an attribute called ``celery_app`` (or ``app``) on the target module.
#
# When celery is NOT installed, celery_app is None.  Any code that calls
# make_celery_app() directly (e.g. a task module) will get the RuntimeError
# above at the moment it tries to construct the app, not at import time.
# ---------------------------------------------------------------------------
celery_app = make_celery_app() if _CELERY_AVAILABLE else None
app = celery_app  # alias for ``-A backend.services.celery_app`` convention


# ---------------------------------------------------------------------------
# Distributed event subscriber — wire workers into the cross-pod event bus
# (Gemini round-D follow-up: Celery workers were not subscribed; events
# published by FastAPI pods didn't reach worker handlers in multi-instance
# deploys).  Spawned at worker_ready signal so it runs in the worker process
# (not on the FastAPI side which already starts its own subscriber).  Gated
# by URIP_DISTRIBUTED_EVENTS so it stays a no-op in single-instance dev.
# ---------------------------------------------------------------------------
if _CELERY_AVAILABLE and celery_app is not None:
    from celery.signals import worker_ready  # type: ignore

    @worker_ready.connect
    def _start_redis_event_subscriber_in_worker(sender=None, **_kwargs):
        if os.environ.get("URIP_DISTRIBUTED_EVENTS", "").lower() not in (
            "1", "true", "yes",
        ):
            return
        try:
            import asyncio
            from shared.events.bus import get_event_bus
            from shared.events.redis_subscriber import (
                start_redis_event_subscriber,
            )
            redis_url = settings.REDIS_URL or "redis://redis:6379/0"
            asyncio.get_event_loop().run_until_complete(
                start_redis_event_subscriber(get_event_bus(), redis_url)
            )
            logger.info(
                "celery_app: redis event subscriber started in worker"
            )
        except Exception as exc:  # pragma: no cover — best-effort
            logger.warning(
                "celery_app: redis event subscriber failed in worker: %s",
                exc,
            )


__all__ = ["celery_app", "app", "make_celery_app"]
