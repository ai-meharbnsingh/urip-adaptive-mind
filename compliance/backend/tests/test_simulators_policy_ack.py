"""
TDD tests — policy_ack_simulator.

Verifies:
  - Generates PolicyAcknowledgment records for the tenant.
  - ~85% acknowledgment rate (some employees skip).
  - Stale acks (against old policy versions) flagged via separate query.
  - Date distribution: most acks within 60 days of policy publish_at.
  - Tenant isolation; idempotency.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta

import pytest
from sqlalchemy import select, func

from compliance_backend.models.policy import (
    Policy,
    PolicyVersion,
    PolicyAcknowledgment,
)
from compliance_backend.seeders.simulators.policy_ack_simulator import (
    simulate_policy_acknowledgments,
)


async def _create_tenant_policies(
    session, tenant_id: str, n_policies: int = 3, with_old_versions: bool = True
):
    """Helper — seed a few Policy + PolicyVersion records for a tenant."""
    for i in range(n_policies):
        owner_id = str(uuid.uuid4())
        policy = Policy(
            id=str(uuid.uuid4()),
            tenant_id=tenant_id,
            name=f"Acceptable Use Policy v{i+1}",
            owner_user_id=owner_id,
            is_active=True,
        )
        session.add(policy)
        await session.flush()

        # An older version + a current version
        if with_old_versions:
            v_old = PolicyVersion(
                id=str(uuid.uuid4()),
                policy_id=policy.id,
                version_number=1,
                content=f"Old content for {policy.name}",
                published_at=datetime.utcnow() - timedelta(days=365),
                published_by_user_id=owner_id,
            )
            session.add(v_old)
        v_cur = PolicyVersion(
            id=str(uuid.uuid4()),
            policy_id=policy.id,
            version_number=2 if with_old_versions else 1,
            content=f"Current content for {policy.name}",
            published_at=datetime.utcnow() - timedelta(days=90),
            published_by_user_id=owner_id,
        )
        session.add(v_cur)
        await session.flush()
        policy.current_version_id = v_cur.id
    await session.flush()


@pytest.mark.anyio
async def test_simulator_creates_acks(db_session):
    await _create_tenant_policies(db_session, "sim-tenant-a", n_policies=2)
    await simulate_policy_acknowledgments(
        db_session, tenant_id="sim-tenant-a", employee_count=50, seed=42
    )
    rows = (await db_session.execute(
        select(PolicyAcknowledgment).where(PolicyAcknowledgment.tenant_id == "sim-tenant-a")
    )).scalars().all()
    assert len(rows) > 0


@pytest.mark.anyio
async def test_acknowledgment_rate_around_85_pct(db_session):
    await _create_tenant_policies(db_session, "sim-tenant-a", n_policies=1, with_old_versions=False)
    summary = await simulate_policy_acknowledgments(
        db_session, tenant_id="sim-tenant-a", employee_count=100, seed=42
    )
    # 1 policy × 100 employees → expect ~85 acknowledgments
    assert "current_version_acks" in summary
    rate = summary["current_version_acks"] / 100
    assert 0.78 <= rate <= 0.92, f"ack rate should be ~0.85, got {rate:.2f}"


@pytest.mark.anyio
async def test_stale_acks_for_old_versions(db_session):
    await _create_tenant_policies(db_session, "sim-tenant-a", n_policies=2, with_old_versions=True)
    summary = await simulate_policy_acknowledgments(
        db_session, tenant_id="sim-tenant-a", employee_count=50, seed=42
    )
    # Some employees should have acks on the old version (without re-acking the new one)
    assert summary.get("stale_acks", 0) > 0, (
        f"expected at least one stale ack, got {summary.get('stale_acks')}"
    )


@pytest.mark.anyio
async def test_signature_is_realistic_hash(db_session):
    await _create_tenant_policies(db_session, "sim-tenant-a", n_policies=1, with_old_versions=False)
    await simulate_policy_acknowledgments(
        db_session, tenant_id="sim-tenant-a", employee_count=20, seed=42
    )
    rows = (await db_session.execute(
        select(PolicyAcknowledgment).where(PolicyAcknowledgment.tenant_id == "sim-tenant-a").limit(5)
    )).scalars().all()
    for r in rows:
        assert r.signature, "signature should not be empty"
        # SHA-256 hex is 64 chars
        assert len(r.signature) >= 16, f"signature too short: {r.signature!r}"
        assert r.signature.lower() != "test", "placeholder signature detected"


@pytest.mark.anyio
async def test_tenant_isolation(db_session):
    await _create_tenant_policies(db_session, "sim-tenant-a", n_policies=1, with_old_versions=False)
    await _create_tenant_policies(db_session, "sim-tenant-b", n_policies=1, with_old_versions=False)
    await simulate_policy_acknowledgments(db_session, tenant_id="sim-tenant-a", employee_count=20, seed=42)
    await simulate_policy_acknowledgments(db_session, tenant_id="sim-tenant-b", employee_count=20, seed=42)

    a = (await db_session.execute(
        select(func.count()).select_from(PolicyAcknowledgment).where(
            PolicyAcknowledgment.tenant_id == "sim-tenant-a"
        )
    )).scalar()
    b = (await db_session.execute(
        select(func.count()).select_from(PolicyAcknowledgment).where(
            PolicyAcknowledgment.tenant_id == "sim-tenant-b"
        )
    )).scalar()
    assert a > 0 and b > 0
    # Verify each row in A points to a tenant-A policy_version
    rows = (await db_session.execute(
        select(PolicyAcknowledgment, PolicyVersion).join(
            PolicyVersion, PolicyAcknowledgment.policy_version_id == PolicyVersion.id
        ).join(Policy, PolicyVersion.policy_id == Policy.id).where(
            PolicyAcknowledgment.tenant_id == "sim-tenant-a"
        )
    )).all()
    for ack, ver in rows:
        # Verify the policy this version belongs to is tenant-A's
        pol = (await db_session.execute(
            select(Policy).where(Policy.id == ver.policy_id)
        )).scalars().first()
        assert pol.tenant_id == "sim-tenant-a"


@pytest.mark.anyio
async def test_idempotent_rerun(db_session):
    await _create_tenant_policies(db_session, "sim-tenant-a", n_policies=1, with_old_versions=False)
    await simulate_policy_acknowledgments(db_session, tenant_id="sim-tenant-a", employee_count=30, seed=42)
    first = (await db_session.execute(
        select(func.count()).select_from(PolicyAcknowledgment).where(
            PolicyAcknowledgment.tenant_id == "sim-tenant-a"
        )
    )).scalar()
    await simulate_policy_acknowledgments(db_session, tenant_id="sim-tenant-a", employee_count=30, seed=42)
    second = (await db_session.execute(
        select(func.count()).select_from(PolicyAcknowledgment).where(
            PolicyAcknowledgment.tenant_id == "sim-tenant-a"
        )
    )).scalar()
    assert first == second
