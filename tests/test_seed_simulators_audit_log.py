"""
TDD tests — backend/seed_simulators/audit_log_activity_simulator.

Verifies:
  - Creates AuditLog rows with realistic action mix.
  - Times distributed over the configured window.
  - User-attributed (FK to users).
  - Tenant isolation; idempotent.
"""
from __future__ import annotations

import os
import uuid
from datetime import datetime, timedelta, timezone

# Set Fernet key BEFORE importing crypto
os.environ.setdefault(
    "URIP_FERNET_KEY",
    "M3JKpUVOfx1nPLQYMRrxnVZsJq3cJ5vXq7bOe6jfXok=",
)

import pytest
from sqlalchemy import select, func

from backend.models.audit_log import AuditLog
from backend.models.tenant import Tenant
from backend.models.user import User
from backend.seed_simulators.audit_log_activity_simulator import (
    simulate_audit_log_activity,
)


@pytest.mark.anyio
async def test_creates_audit_log_rows(db_session, default_tenant, auth_headers):
    summary = await simulate_audit_log_activity(
        db_session,
        tenant_id=default_tenant.id,
        days=30,
        events_per_day=10,
        seed=42,
    )
    assert summary["created"] >= 30 * 5  # at least events_per_day/2

    rows = (await db_session.execute(
        select(AuditLog).where(AuditLog.tenant_id == default_tenant.id)
    )).scalars().all()
    assert len(rows) > 0


@pytest.mark.anyio
async def test_action_mix_realistic(db_session, default_tenant, auth_headers):
    await simulate_audit_log_activity(
        db_session, tenant_id=default_tenant.id, days=30, events_per_day=15, seed=42
    )
    rows = (await db_session.execute(
        select(AuditLog).where(AuditLog.tenant_id == default_tenant.id)
    )).scalars().all()
    actions = {r.action for r in rows}
    # Should include at least: login, view_dashboard, view_risk
    assert "login" in actions
    assert any(a in actions for a in ("view_dashboard", "view_risk", "comment_on_risk"))


@pytest.mark.anyio
async def test_dates_span_window(db_session, default_tenant, auth_headers):
    await simulate_audit_log_activity(
        db_session, tenant_id=default_tenant.id, days=60, events_per_day=10, seed=42
    )
    rows = (await db_session.execute(
        select(AuditLog).where(AuditLog.tenant_id == default_tenant.id)
    )).scalars().all()
    earliest = min(r.created_at for r in rows)
    latest = max(r.created_at for r in rows)
    span = (latest - earliest).days
    assert span >= 30, f"events span only {span} days; expected >=30"


@pytest.mark.anyio
async def test_user_id_attributed(db_session, default_tenant, auth_headers):
    await simulate_audit_log_activity(
        db_session, tenant_id=default_tenant.id, days=10, events_per_day=10, seed=42
    )
    rows = (await db_session.execute(
        select(AuditLog).where(AuditLog.tenant_id == default_tenant.id).limit(20)
    )).scalars().all()
    for r in rows:
        assert r.user_id is not None


@pytest.mark.anyio
async def test_tenant_isolation(db_session, default_tenant, auth_headers):
    other_tenant = Tenant(
        id=uuid.uuid4(),
        name="Other Tenant",
        slug="other-test-audit",
        domain="other-audit.test",
        is_active=True,
        settings={},
    )
    db_session.add(other_tenant)
    await db_session.commit()

    await simulate_audit_log_activity(
        db_session, tenant_id=default_tenant.id, days=10, events_per_day=10, seed=42
    )
    other_count = (await db_session.execute(
        select(func.count()).select_from(AuditLog).where(
            AuditLog.tenant_id == other_tenant.id
        )
    )).scalar()
    assert other_count == 0


@pytest.mark.anyio
async def test_idempotent_rerun(db_session, default_tenant, auth_headers):
    await simulate_audit_log_activity(
        db_session, tenant_id=default_tenant.id, days=10, events_per_day=8, seed=42
    )
    first = (await db_session.execute(
        select(func.count()).select_from(AuditLog).where(
            AuditLog.tenant_id == default_tenant.id
        )
    )).scalar()
    await simulate_audit_log_activity(
        db_session, tenant_id=default_tenant.id, days=10, events_per_day=8, seed=42
    )
    second = (await db_session.execute(
        select(func.count()).select_from(AuditLog).where(
            AuditLog.tenant_id == default_tenant.id
        )
    )).scalar()
    assert first == second
