"""
access_review_simulator — quarterly access review campaigns + decisions.

Behavior:
  - For each of the last `quarters_back` quarters, create one campaign per
    in-scope system (AWS, Azure AD, GitHub, Salesforce, Okta).
  - Each campaign covers `users_per_campaign` employees with one entitlement each.
  - Decisions: 95% keep / 5% revoke for completed campaigns; 100% pending for the
    most recent (in-progress) campaign.
  - Campaign status:
      - oldest quarter → completed
      - middle quarters → completed
      - most recent quarter → in_progress (some decisions pending)

Idempotency: skip if any campaigns exist for tenant.
"""
from __future__ import annotations

import random
from datetime import date, datetime, timedelta
from typing import Optional

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from compliance_backend.seeders.simulators.sim_models import (
    AccessReviewCampaign,
    AccessReviewDecision,
)
from compliance_backend.seeders.simulators._common import (
    generate_employees,
    make_rng,
    stable_uuid,
    now_utc,
)


SCOPED_SYSTEMS = [
    ("AWS Production Account", ["AdministratorAccess", "PowerUserAccess", "ReadOnlyAccess", "BillingAccess"]),
    ("Azure AD Privileged Roles", ["Global Administrator", "Privileged Role Administrator", "Conditional Access Administrator"]),
    ("GitHub Organization adverb-corp", ["Owner", "Member", "Outside Collaborator"]),
    ("Salesforce CRM Production", ["System Administrator", "Standard User", "Sales Manager"]),
    ("Okta Workforce Identity", ["Super Admin", "Org Admin", "Read-Only Admin"]),
]

REVOKE_REASONS = [
    "Employee transitioned to a different team — entitlement no longer required for new role.",
    "Quarterly access analytics shows zero usage in the past 90 days — applying least-privilege.",
    "Role consolidation: equivalent access already provided by group membership.",
    "Employee on extended leave — temporary revocation pending return-to-work.",
    "Separation of duties conflict identified — moving to read-only equivalent.",
    "Project ended — access was provisioned for time-bounded engagement.",
]


def _quarter_label(d: date) -> str:
    q = (d.month - 1) // 3 + 1
    return f"{d.year}-Q{q}"


def _quarter_start(year: int, q: int) -> date:
    return date(year, (q - 1) * 3 + 1, 1)


def _quarters_back(now: datetime, n: int) -> list[tuple[int, int]]:
    """Return list of (year, quarter) for the last n completed quarters + current."""
    cur_q = (now.month - 1) // 3 + 1
    cur_year = now.year
    out = []
    for i in range(n):
        q = cur_q - i
        y = cur_year
        while q < 1:
            q += 4
            y -= 1
        out.append((y, q))
    return list(reversed(out))


async def simulate_access_reviews(
    session: AsyncSession,
    *,
    tenant_id: str,
    quarters_back: int = 4,
    users_per_campaign: int = 30,
    seed: int = 42,
    skip_if_existing: bool = True,
) -> dict[str, int]:
    """
    Generate access review campaigns + decisions for a tenant.

    Args:
        tenant_id:           Tenant scope.
        quarters_back:       How many quarters of history to simulate.
        users_per_campaign:  Number of (user, entitlement) decisions per campaign.
        seed:                RNG seed.
        skip_if_existing:    No-op if any campaigns exist.
    """
    rng = make_rng(seed)

    if skip_if_existing:
        existing = (await session.execute(
            select(func.count()).select_from(AccessReviewCampaign).where(
                AccessReviewCampaign.tenant_id == tenant_id
            )
        )).scalar() or 0
        if existing > 0:
            return {
                "campaigns": 0,
                "decisions": 0,
                "skipped": existing,
                "tenant_id": tenant_id,
            }

    employees = generate_employees(rng, tenant_id, count=max(50, users_per_campaign * 2))

    quarters = _quarters_back(now_utc(), quarters_back)
    campaign_count = 0
    decision_count = 0

    # Reviewer pool — managers/directors
    reviewers = [
        e for e in employees if e["department"] in ("Engineering", "Operations", "Security", "Executive", "IT")
    ][:8]
    if not reviewers:
        reviewers = employees[:5]

    for q_idx, (year, q) in enumerate(quarters):
        is_current = q_idx == len(quarters) - 1
        for system_name, entitlements in SCOPED_SYSTEMS:
            q_start = _quarter_start(year, q)
            # Campaign starts 1 week into the quarter
            started_at = datetime.combine(
                q_start + timedelta(days=7), datetime.min.time()
            )
            due_date = q_start + timedelta(days=60)
            reviewer = rng.choice(reviewers)

            if is_current:
                status = "in_progress"
                completed_at = None
            else:
                status = "completed"
                completed_at = started_at + timedelta(days=rng.randint(15, 50))

            campaign = AccessReviewCampaign(
                id=stable_uuid(tenant_id, "campaign", str(year), str(q), system_name),
                tenant_id=tenant_id,
                name=f"{system_name} Access Review — {year} Q{q}",
                system_name=system_name,
                period_label=f"{year}-Q{q}",
                started_at=started_at,
                due_at=due_date,
                completed_at=completed_at,
                status=status,
                reviewer_user_id=reviewer["user_id"],
            )
            session.add(campaign)
            await session.flush()
            campaign_count += 1

            # Sample users
            sampled_users = rng.sample(employees, min(users_per_campaign, len(employees)))
            for u_idx, emp in enumerate(sampled_users):
                entitlement = rng.choice(entitlements)

                if status == "in_progress":
                    # ~30% already decided, rest pending
                    if rng.random() < 0.3:
                        decision = "keep" if rng.random() < 0.95 else "revoke"
                        decided_at = started_at + timedelta(days=rng.randint(1, 30))
                        decided_by = reviewer["user_id"]
                        justification = (
                            rng.choice(REVOKE_REASONS) if decision == "revoke"
                            else "Reviewer attests entitlement is required for current role."
                        )
                    else:
                        decision = "pending"
                        decided_at = None
                        decided_by = None
                        justification = None
                else:
                    decision = "keep" if rng.random() < 0.95 else "revoke"
                    decided_at = started_at + timedelta(days=rng.randint(1, 50))
                    decided_by = reviewer["user_id"]
                    justification = (
                        rng.choice(REVOKE_REASONS) if decision == "revoke"
                        else "Reviewer attests entitlement is required for current role."
                    )

                drow = AccessReviewDecision(
                    id=stable_uuid(
                        tenant_id, "decision",
                        str(year), str(q), system_name,
                        emp["user_id"], entitlement,
                    ),
                    campaign_id=campaign.id,
                    target_user_id=emp["user_id"],
                    target_user_email=emp["email"],
                    entitlement=entitlement,
                    decision=decision,
                    decided_at=decided_at,
                    decided_by_user_id=decided_by,
                    justification=justification,
                )
                session.add(drow)
                decision_count += 1

    await session.flush()
    return {
        "campaigns": campaign_count,
        "decisions": decision_count,
        "skipped": 0,
        "tenant_id": tenant_id,
    }
