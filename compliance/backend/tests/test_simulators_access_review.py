"""
TDD tests — access_review_simulator.

Verifies:
  - Creates AccessReviewCampaign per quarter (4 per year).
  - Decisions: keep/revoke split ~95/5.
  - Mix of completed and in-progress campaigns.
  - Reviewer assignments populated.
  - Tenant isolation; idempotent.
"""
from __future__ import annotations

import pytest
from sqlalchemy import select, func

from compliance_backend.seeders.simulators.sim_models import (
    AccessReviewCampaign,
    AccessReviewDecision,
)
from compliance_backend.seeders.simulators.access_review_simulator import (
    simulate_access_reviews,
)


@pytest.mark.anyio
async def test_simulator_creates_campaigns_and_decisions(db_session):
    summary = await simulate_access_reviews(
        db_session, tenant_id="sim-tenant-a", quarters_back=4, users_per_campaign=20, seed=42
    )
    assert summary["campaigns"] >= 4
    assert summary["decisions"] >= 80


@pytest.mark.anyio
async def test_keep_revoke_split(db_session):
    await simulate_access_reviews(
        db_session, tenant_id="sim-tenant-a", quarters_back=4, users_per_campaign=50, seed=42
    )
    decisions = (await db_session.execute(
        select(AccessReviewDecision)
        .join(AccessReviewCampaign, AccessReviewDecision.campaign_id == AccessReviewCampaign.id)
        .where(
            AccessReviewCampaign.tenant_id == "sim-tenant-a",
            AccessReviewDecision.decision.in_(["keep", "revoke"]),
        )
    )).scalars().all()
    keep = sum(1 for d in decisions if d.decision == "keep")
    revoke = sum(1 for d in decisions if d.decision == "revoke")
    total = keep + revoke
    assert total > 0
    keep_pct = keep / total
    # Target ~95% keep
    assert 0.85 <= keep_pct <= 0.99, f"keep% = {keep_pct:.2f}"


@pytest.mark.anyio
async def test_pending_decisions_for_in_progress_campaign(db_session):
    summary = await simulate_access_reviews(
        db_session,
        tenant_id="sim-tenant-a",
        quarters_back=4,
        users_per_campaign=20,
        seed=42,
    )
    in_prog = (await db_session.execute(
        select(AccessReviewCampaign).where(
            AccessReviewCampaign.tenant_id == "sim-tenant-a",
            AccessReviewCampaign.status == "in_progress",
        )
    )).scalars().all()
    assert len(in_prog) >= 1
    for c in in_prog:
        decisions = (await db_session.execute(
            select(AccessReviewDecision).where(AccessReviewDecision.campaign_id == c.id)
        )).scalars().all()
        pending = [d for d in decisions if d.decision == "pending"]
        assert len(pending) > 0


@pytest.mark.anyio
async def test_completed_decisions_have_decided_at(db_session):
    await simulate_access_reviews(
        db_session, tenant_id="sim-tenant-a", quarters_back=4, users_per_campaign=20, seed=42
    )
    completed_decisions = (await db_session.execute(
        select(AccessReviewDecision).where(AccessReviewDecision.decision != "pending")
    )).scalars().all()
    for d in completed_decisions[:20]:
        assert d.decided_at is not None
        assert d.decided_by_user_id is not None


@pytest.mark.anyio
async def test_revoke_decisions_have_justification(db_session):
    await simulate_access_reviews(
        db_session, tenant_id="sim-tenant-a", quarters_back=4, users_per_campaign=50, seed=42
    )
    revokes = (await db_session.execute(
        select(AccessReviewDecision)
        .join(AccessReviewCampaign, AccessReviewDecision.campaign_id == AccessReviewCampaign.id)
        .where(
            AccessReviewCampaign.tenant_id == "sim-tenant-a",
            AccessReviewDecision.decision == "revoke",
        )
    )).scalars().all()
    if revokes:
        for r in revokes:
            assert r.justification, "revoke must have justification"
            assert len(r.justification) > 10


@pytest.mark.anyio
async def test_tenant_isolation(db_session):
    await simulate_access_reviews(db_session, tenant_id="sim-tenant-a", quarters_back=2, users_per_campaign=10, seed=42)
    await simulate_access_reviews(db_session, tenant_id="sim-tenant-b", quarters_back=2, users_per_campaign=10, seed=42)
    a = (await db_session.execute(
        select(func.count()).select_from(AccessReviewCampaign).where(
            AccessReviewCampaign.tenant_id == "sim-tenant-a"
        )
    )).scalar()
    b = (await db_session.execute(
        select(func.count()).select_from(AccessReviewCampaign).where(
            AccessReviewCampaign.tenant_id == "sim-tenant-b"
        )
    )).scalar()
    assert a > 0 and b > 0
    assert a == b


@pytest.mark.anyio
async def test_idempotent_rerun(db_session):
    await simulate_access_reviews(db_session, tenant_id="sim-tenant-a", quarters_back=2, users_per_campaign=10, seed=42)
    first = (await db_session.execute(
        select(func.count()).select_from(AccessReviewCampaign).where(
            AccessReviewCampaign.tenant_id == "sim-tenant-a"
        )
    )).scalar()
    await simulate_access_reviews(db_session, tenant_id="sim-tenant-a", quarters_back=2, users_per_campaign=10, seed=42)
    second = (await db_session.execute(
        select(func.count()).select_from(AccessReviewCampaign).where(
            AccessReviewCampaign.tenant_id == "sim-tenant-a"
        )
    )).scalar()
    assert first == second
