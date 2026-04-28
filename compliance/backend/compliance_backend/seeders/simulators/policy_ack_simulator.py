"""
policy_ack_simulator — synthesize PolicyAcknowledgment records.

Behavior:
  - For each policy in the tenant: ack ~85% of employees against the
    current_version, on a date distribution skewed toward the publish_at date
    (most acks happen within 60 days of publish).
  - For policies with prior versions: ~10-15% of employees have an ack
    against the OLD version but not the new one — these are "stale acks"
    that the UI marks as needing re-acknowledgment.
  - Signature is a SHA-256 hash of (user_id|version_id|timestamp).

Idempotency:
  Skips if any ack rows already exist for the tenant.

Reset is the master orchestrator's responsibility (mv to backup).
"""
from __future__ import annotations

import hashlib
import random
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from compliance_backend.models.policy import (
    Policy,
    PolicyVersion,
    PolicyAcknowledgment,
)
from compliance_backend.seeders.simulators._common import (
    generate_employees,
    make_rng,
    stable_uuid,
    now_utc,
)


def _signature(user_id: str, version_id: str, ts: datetime) -> str:
    """SHA-256 of canonical sign payload — emulates a real e-sign hash."""
    payload = f"{user_id}|{version_id}|{ts.isoformat()}"
    return hashlib.sha256(payload.encode()).hexdigest()


async def simulate_policy_acknowledgments(
    session: AsyncSession,
    *,
    tenant_id: str,
    employee_count: int = 50,
    ack_rate: float = 0.85,
    stale_rate: float = 0.12,
    seed: int = 42,
    skip_if_existing: bool = True,
) -> dict[str, int]:
    """
    Args:
        tenant_id:        Tenant scope.
        employee_count:   Synthetic employee population.
        ack_rate:         Fraction of employees who have acked the current version.
        stale_rate:       Fraction of employees who have an ack on an old version
                          but NOT on the current one (need re-ack).
        seed:             RNG seed.
        skip_if_existing: If any acks already exist for this tenant, no-op.

    Returns:
        Summary counts.
    """
    rng = make_rng(seed)

    if skip_if_existing:
        existing = (await session.execute(
            select(func.count()).select_from(PolicyAcknowledgment).where(
                PolicyAcknowledgment.tenant_id == tenant_id
            )
        )).scalar() or 0
        if existing > 0:
            return {
                "current_version_acks": 0,
                "stale_acks": 0,
                "skipped": existing,
                "tenant_id": tenant_id,
            }

    employees = generate_employees(rng, tenant_id, count=employee_count)

    # Pull tenant policies
    policies = (await session.execute(
        select(Policy).where(Policy.tenant_id == tenant_id, Policy.is_active.is_(True))
    )).scalars().all()
    if not policies:
        return {
            "current_version_acks": 0,
            "stale_acks": 0,
            "tenant_id": tenant_id,
            "warning": "no policies for tenant; nothing to ack",
        }

    current_acks = 0
    stale_acks = 0

    for policy in policies:
        versions = (await session.execute(
            select(PolicyVersion)
            .where(PolicyVersion.policy_id == policy.id)
            .order_by(PolicyVersion.version_number.asc())
        )).scalars().all()
        if not versions:
            continue

        current_version = (
            next((v for v in versions if v.id == policy.current_version_id), None)
            or versions[-1]  # fallback: highest version_number
        )
        old_versions = [v for v in versions if v.id != current_version.id]

        publish_anchor = current_version.published_at or now_utc()
        # Strip tz for naive datetime arithmetic compatibility
        if publish_anchor.tzinfo is not None:
            publish_anchor = publish_anchor.replace(tzinfo=None)

        for emp in employees:
            user_id = emp["user_id"]
            r = rng.random()

            if r < ack_rate:
                # Acked current version — date skewed within 60 days of publish
                day_offset = rng.randint(0, 60)
                ts = publish_anchor + timedelta(days=day_offset, hours=rng.randint(0, 23))
                if ts > now_utc():
                    ts = now_utc() - timedelta(hours=rng.randint(1, 240))
                ack = PolicyAcknowledgment(
                    id=stable_uuid(tenant_id, "ack", policy.id, current_version.id, user_id),
                    policy_version_id=current_version.id,
                    user_id=user_id,
                    tenant_id=tenant_id,
                    acknowledged_at=ts,
                    signature=_signature(user_id, current_version.id, ts),
                )
                session.add(ack)
                current_acks += 1
            elif r < ack_rate + stale_rate and old_versions:
                # Stale: acked an OLD version but not the new one
                old_v = rng.choice(old_versions)
                old_publish = old_v.published_at or (publish_anchor - timedelta(days=180))
                if old_publish.tzinfo is not None:
                    old_publish = old_publish.replace(tzinfo=None)
                ts = old_publish + timedelta(days=rng.randint(5, 90))
                if ts > now_utc():
                    ts = now_utc() - timedelta(days=rng.randint(60, 200))
                ack = PolicyAcknowledgment(
                    id=stable_uuid(tenant_id, "ack", policy.id, old_v.id, user_id),
                    policy_version_id=old_v.id,
                    user_id=user_id,
                    tenant_id=tenant_id,
                    acknowledged_at=ts,
                    signature=_signature(user_id, old_v.id, ts),
                )
                session.add(ack)
                stale_acks += 1
            # else: this employee has no ack — they show up in the
            # "policies awaiting acknowledgment" report.

    await session.flush()
    return {
        "current_version_acks": current_acks,
        "stale_acks": stale_acks,
        "skipped": 0,
        "tenant_id": tenant_id,
    }
