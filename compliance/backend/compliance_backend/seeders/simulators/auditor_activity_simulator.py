"""
auditor_activity_simulator — synthesize external auditor sessions.

Behavior:
  - Creates `n_auditors` AuditorAccess invitations for a (tenant, framework, period).
  - Each invitation has an SHA-256 hashed token, expiry, audit-period bounds.
  - ~70% of invitations are accepted; accepted auditors generate realistic
    activity_log sequences:
        list_controls → view_control (×3-8) → list_evidence → download_evidence (×2-5)
        → view_policy (×1-3) → request_evidence → export_bundle
  - Some auditors only browse (no download); some go all the way to export.
  - Activity timestamps are sequenced realistically over a 1-3 day audit visit.

Idempotency: skip if any AuditorAccess for the tenant exist.
"""
from __future__ import annotations

import hashlib
import random
import secrets
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from compliance_backend.models.auditor import (
    AuditorAccess,
    AuditorActivityLog,
)
from compliance_backend.models.framework import Control
from compliance_backend.models.evidence import Evidence
from compliance_backend.models.policy import Policy
from compliance_backend.seeders.simulators._common import (
    make_rng,
    stable_uuid,
    now_utc,
)


AUDIT_FIRMS = [
    ("BDO India LLP", "audit"),
    ("Grant Thornton Bharat LLP", "advisory"),
    ("PKF Sridhar & Santhanam LLP", "audit"),
    ("Walker Chandiok & Co LLP", "audit"),
    ("RSM Astute Consulting Pvt Ltd", "advisory"),
    ("Aneja Associates Chartered Accountants", "ca"),
    ("Lodha & Co Chartered Accountants", "ca"),
    ("Nangia Andersen LLP", "advisory"),
]

AUDITOR_FIRST_NAMES = [
    "Anil", "Priya", "Rohan", "Meera", "Vikas", "Anjali", "Shyam", "Ritu",
    "Kunal", "Suchitra", "Manoj", "Lavanya",
]
AUDITOR_LAST_NAMES = [
    "Krishnan", "Iyer", "Mehta", "Sharma", "Banerjee", "Nair", "Pillai", "Bhat",
]


def _auditor_email(first: str, last: str, firm_domain: str) -> str:
    return f"{first.lower()}.{last.lower()}@{firm_domain}"


def _firm_domain(firm_name: str, firm_type: str) -> str:
    slug = "".join(c for c in firm_name.split()[0].lower() if c.isalnum())[:12]
    if firm_type == "ca":
        return f"{slug}-ca.in"
    if firm_type == "advisory":
        return f"{slug}advisory.in"
    return f"{slug}audit.com"


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _build_activity_sequence(
    auditor_email: str,
    access_id: str,
    tenant_id: str,
    accepted_at: datetime,
    rng: random.Random,
    control_ids: list[str],
    evidence_ids: list[str],
    policy_ids: list[str],
    is_thorough: bool,
) -> list[dict]:
    """
    Build a realistic auditor session sequence.

    Returns list of dicts with action/target_type/target_id/accessed_at/ip.
    """
    seq = []
    cur = accepted_at
    ip_address = f"203.0.113.{rng.randint(1, 254)}"  # TEST-NET-3 range

    def _step(action: str, target_type: Optional[str] = None, target_id: Optional[str] = None):
        nonlocal cur
        cur = cur + timedelta(minutes=rng.randint(2, 30))
        seq.append({
            "action": action,
            "target_type": target_type,
            "target_id": target_id,
            "accessed_at": cur,
            "ip": ip_address,
        })

    # Day 1 — overview
    _step("list_controls")
    n_controls = rng.randint(3, 8) if is_thorough else rng.randint(1, 3)
    for cid in rng.sample(control_ids, min(n_controls, len(control_ids))):
        _step("view_control", "control", cid)

    _step("list_evidence")
    if evidence_ids:
        n_evidence = rng.randint(2, 6) if is_thorough else 1
        for eid in rng.sample(evidence_ids, min(n_evidence, len(evidence_ids))):
            _step("download_evidence", "evidence", eid)

    if policy_ids:
        for pid in rng.sample(policy_ids, min(2, len(policy_ids))):
            _step("view_policy", "policy", pid)

    if is_thorough:
        _step("request_evidence", "control", rng.choice(control_ids) if control_ids else None)
        _step("export_bundle")

    return seq


async def simulate_auditor_activity(
    session: AsyncSession,
    *,
    tenant_id: str,
    framework_id: str,
    n_auditors: int = 3,
    seed: int = 42,
    skip_if_existing: bool = True,
) -> dict[str, int]:
    """
    Generate auditor invitations + activity logs for a tenant.

    Args:
        tenant_id:        Tenant scope.
        framework_id:     Framework the auditors are reviewing.
        n_auditors:       Number of auditor invitations to issue.
        seed:             RNG seed.
        skip_if_existing: No-op if any AuditorAccess for tenant exists.
    """
    rng = make_rng(seed)

    if skip_if_existing:
        existing = (await session.execute(
            select(func.count()).select_from(AuditorAccess).where(
                AuditorAccess.tenant_id == tenant_id
            )
        )).scalar() or 0
        if existing > 0:
            return {
                "invitations": 0,
                "activity_logs": 0,
                "skipped": existing,
                "tenant_id": tenant_id,
            }

    # Pull control / evidence / policy IDs (may be empty for fresh tenants)
    control_ids = [
        c[0] for c in (await session.execute(select(Control.id).limit(50))).all()
    ]
    evidence_ids = [
        e[0] for e in (await session.execute(
            select(Evidence.id).where(Evidence.tenant_id == tenant_id).limit(50)
        )).all()
    ]
    policy_ids = [
        p[0] for p in (await session.execute(
            select(Policy.id).where(Policy.tenant_id == tenant_id).limit(20)
        )).all()
    ]

    invitations = 0
    activity_logs = 0
    inviter_user_id = stable_uuid(tenant_id, "inviter", "tenant_admin")

    for i in range(n_auditors):
        firm_name, firm_type = rng.choice(AUDIT_FIRMS)
        first = rng.choice(AUDITOR_FIRST_NAMES)
        last = rng.choice(AUDITOR_LAST_NAMES)
        domain = _firm_domain(firm_name, firm_type)
        email = _auditor_email(first, last, domain)

        period_start = now_utc() - timedelta(days=rng.randint(30, 60))
        period_end = period_start + timedelta(days=90)

        # Token: stable per (tenant, email) so re-runs hash to the same value
        secret_value = stable_uuid(tenant_id, "auditor_token", email)
        token_hash = _hash_token(secret_value)

        # 70% acceptance
        is_accepted = rng.random() < 0.7
        accepted_at = (
            period_start + timedelta(days=rng.randint(1, 14))
            if is_accepted else None
        )

        access_id = stable_uuid(tenant_id, "auditor_access", email, framework_id)
        access = AuditorAccess(
            id=access_id,
            tenant_id=tenant_id,
            auditor_email=email,
            framework_id=framework_id,
            audit_period_start=period_start,
            audit_period_end=period_end,
            invited_by_user_id=inviter_user_id,
            invitation_token_hash=token_hash,
            accepted_at=accepted_at,
            expires_at=period_end + timedelta(days=14),
            is_revoked=False,
        )
        session.add(access)
        invitations += 1

        if is_accepted:
            is_thorough = rng.random() < 0.7
            sequence = _build_activity_sequence(
                email,
                access_id,
                tenant_id,
                accepted_at,
                rng,
                control_ids,
                evidence_ids,
                policy_ids,
                is_thorough,
            )
            for step_idx, step in enumerate(sequence):
                log = AuditorActivityLog(
                    id=stable_uuid(tenant_id, "audit_log", email, str(step_idx)),
                    tenant_id=tenant_id,
                    auditor_access_id=access_id,
                    auditor_email=email,
                    action=step["action"],
                    target_type=step["target_type"],
                    target_id=step["target_id"],
                    accessed_at=step["accessed_at"],
                    ip_address=step["ip"],
                )
                session.add(log)
                activity_logs += 1

    await session.flush()
    return {
        "invitations": invitations,
        "activity_logs": activity_logs,
        "skipped": 0,
        "tenant_id": tenant_id,
    }
