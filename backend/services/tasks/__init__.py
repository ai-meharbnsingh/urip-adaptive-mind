"""
backend.services.tasks — Celery task modules.

Each periodic task lives in its own module so the worker can import them
explicitly via ``celery_app.include`` and so individual tasks can be
mocked / replaced in tests without dragging in unrelated dependencies.

Modules
-------
- connector_pull_task     — per-(tenant, connector) ingest fan-out.
- scoring_recompute_task  — re-runs risk_aggregate_service across all tenants.
- control_check_task      — re-runs compliance.control_engine across all tenants.
"""
