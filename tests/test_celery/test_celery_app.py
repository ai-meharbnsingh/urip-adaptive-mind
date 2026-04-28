"""
TDD — backend/services/celery_app.py — Celery application instance.

We don't need a live Redis broker for these tests; we exercise the Celery
app's configuration surface (broker URL, result backend, beat schedule,
task auto-discovery) and the task wrappers in eager/always-eager mode so
the task body executes synchronously in-process.

What's covered
--------------
- App instance exists at backend.services.celery_app.celery_app
- Broker + result-backend point at REDIS_URL (or a sane default)
- Beat schedule registers connector_pull (15m), scoring_recompute (1h),
  control_check (6h)
- All three task modules import cleanly and register their @app.task names
- Tasks run end-to-end with eager mode + mocked downstream services

INV-4 invariant: every assert checks a real value (cron seconds, task name
strings, computed return values), never just ``is not None``.
"""
from __future__ import annotations

import os

# Eager mode means .delay() / .apply_async() runs the task body inline.
# The Celery app reads CELERY_TASK_ALWAYS_EAGER at import time.
os.environ.setdefault("CELERY_TASK_ALWAYS_EAGER", "true")
os.environ.setdefault("URIP_FERNET_KEY", "M3JKpUVOfx1nPLQYMRrxnVZsJq3cJ5vXq7bOe6jfXok=")
os.environ.setdefault("DISABLE_CONNECTOR_SCHEDULER", "true")

import unittest.mock as mock

import pytest

# Module-level skip when celery is not installed. backend/services/celery_app.py
# tolerates the missing import (celery_app=None) so the rest of the app can
# still boot, but every test below dereferences celery_app.* — so this whole
# module must skip on a clean clone without celery. Pattern matches the same
# clean-clone guard used in tests/test_critfix_auth/test_audit_fix_critical.py.
from backend.services.celery_app import _CELERY_AVAILABLE  # noqa: E402

pytestmark = pytest.mark.skipif(
    not _CELERY_AVAILABLE,
    reason="celery package not installed — celery_app is None, all tests would AttributeError",
)


def test_celery_app_instance_exists_and_is_named():
    from backend.services.celery_app import celery_app

    # Celery's app.main is the canonical name string.
    assert celery_app.main == "urip"


def test_celery_app_broker_uses_redis_url():
    from backend.services.celery_app import celery_app

    broker = celery_app.conf.broker_url or ""
    backend = celery_app.conf.result_backend or ""
    # Default test environment has REDIS_URL=""; the app falls back to a
    # safe localhost broker URL so the worker can boot in dev without env
    # tweaks. Either way, broker and backend should agree.
    assert broker.startswith("redis://"), f"unexpected broker_url={broker!r}"
    assert backend.startswith("redis://"), f"unexpected result_backend={backend!r}"


def test_celery_app_registers_three_periodic_jobs():
    from backend.services.celery_app import celery_app

    schedule = celery_app.conf.beat_schedule or {}
    # Beat schedule keys are the human-friendly job names defined in our app.
    assert "connector-pull-every-15min" in schedule
    assert "scoring-recompute-hourly" in schedule
    assert "control-check-every-6h" in schedule

    # Cron / interval seconds — concrete numbers (INV-4: assert real values).
    cp = schedule["connector-pull-every-15min"]
    sr = schedule["scoring-recompute-hourly"]
    cc = schedule["control-check-every-6h"]

    # ``schedule`` may be a celery.schedules.schedule (interval) — its
    # ``.run_every.total_seconds()`` is the canonical interval.
    assert cp["schedule"].run_every.total_seconds() == 15 * 60
    assert sr["schedule"].run_every.total_seconds() == 60 * 60
    assert cc["schedule"].run_every.total_seconds() == 6 * 60 * 60


def test_celery_app_has_eager_mode_in_test_env():
    from backend.services.celery_app import celery_app

    # We toggled it via env before the import — verify the app honoured it.
    assert celery_app.conf.task_always_eager is True


def test_connector_pull_task_is_registered():
    from backend.services import celery_app as app_mod
    from backend.services.tasks import connector_pull_task  # noqa: F401

    names = set(app_mod.celery_app.tasks.keys())
    assert "backend.services.tasks.connector_pull_task.connector_pull_task" in names


def test_scoring_recompute_task_is_registered():
    from backend.services import celery_app as app_mod
    from backend.services.tasks import scoring_recompute_task  # noqa: F401

    names = set(app_mod.celery_app.tasks.keys())
    assert "backend.services.tasks.scoring_recompute_task.scoring_recompute_task" in names


def test_control_check_task_is_registered():
    from backend.services import celery_app as app_mod
    from backend.services.tasks import control_check_task  # noqa: F401

    names = set(app_mod.celery_app.tasks.keys())
    assert "backend.services.tasks.control_check_task.control_check_task" in names


# ─────────────────────────────────────────────────────────────────────────────
# End-to-end task invocations with mocked services (no broker, no DB).
# These tests prove the task wrappers actually call the underlying services
# with the expected arguments — they don't just exist.
# ─────────────────────────────────────────────────────────────────────────────


def test_connector_pull_task_invokes_runner(monkeypatch):
    """
    .delay(tenant_id, name) should run connector_runner.run_connector_for_tenant
    end-to-end (via eager mode) and return whatever the runner returned.
    """
    from backend.services.tasks import connector_pull_task as cpt

    called: dict = {}

    def _fake_runner(tenant_id: str, connector_name: str) -> dict:
        called["args"] = (tenant_id, connector_name)
        return {"ingested": 7, "skipped": 0, "tenant_id": tenant_id}

    # Patch the runner the task imports (must match the import path used in
    # connector_pull_task.py).
    monkeypatch.setattr(
        cpt, "run_connector_for_tenant", _fake_runner, raising=True,
    )

    result = cpt.connector_pull_task.delay(
        "tenant-abc", "tenable",
    ).get(timeout=5)

    assert called["args"] == ("tenant-abc", "tenable")
    assert result == {"ingested": 7, "skipped": 0, "tenant_id": "tenant-abc"}


def test_scoring_recompute_task_runs_for_each_tenant(monkeypatch):
    """
    The recompute task pulls every tenant id from the DB (mocked) and calls
    risk_aggregate_service.write_snapshot once per tenant.
    """
    from backend.services.tasks import scoring_recompute_task as srt

    monkeypatch.setattr(
        srt, "list_active_tenant_ids", lambda: ["t1", "t2", "t3"], raising=True,
    )
    seen: list[str] = []

    def _fake_recompute(tenant_id: str) -> dict:
        seen.append(tenant_id)
        return {"tenant_id": tenant_id, "open_risks": 42}

    monkeypatch.setattr(
        srt, "recompute_for_tenant", _fake_recompute, raising=True,
    )

    result = srt.scoring_recompute_task.delay().get(timeout=5)

    assert seen == ["t1", "t2", "t3"]
    assert result == {"tenants_processed": 3, "errors": 0}


def test_scoring_recompute_task_keeps_going_on_per_tenant_error(monkeypatch):
    """One bad tenant must NOT halt processing for the rest."""
    from backend.services.tasks import scoring_recompute_task as srt

    monkeypatch.setattr(
        srt, "list_active_tenant_ids", lambda: ["good1", "bad", "good2"], raising=True,
    )

    def _fake_recompute(tenant_id: str) -> dict:
        if tenant_id == "bad":
            raise RuntimeError("DB error")
        return {"tenant_id": tenant_id, "open_risks": 1}

    monkeypatch.setattr(
        srt, "recompute_for_tenant", _fake_recompute, raising=True,
    )

    result = srt.scoring_recompute_task.delay().get(timeout=5)

    assert result == {"tenants_processed": 2, "errors": 1}


def test_control_check_task_runs_for_each_tenant(monkeypatch):
    from backend.services.tasks import control_check_task as cct

    monkeypatch.setattr(
        cct, "list_compliance_tenant_ids", lambda: ["alpha", "beta"], raising=True,
    )
    invocations: list[str] = []

    def _fake_run_controls(tenant_id: str) -> dict:
        invocations.append(tenant_id)
        return {"tenant_id": tenant_id, "controls_run": 12, "passed": 10}

    monkeypatch.setattr(
        cct, "run_controls_for_tenant", _fake_run_controls, raising=True,
    )

    result = cct.control_check_task.delay().get(timeout=5)

    assert invocations == ["alpha", "beta"]
    assert result == {"tenants_processed": 2, "errors": 0}
