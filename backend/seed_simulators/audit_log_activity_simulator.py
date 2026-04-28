"""
backend/seed_simulators/audit_log_activity_simulator.py

Generate realistic AuditLog rows for a tenant — emulates day-to-day user
activity (logins, dashboard views, risk acceptances, comment additions,
remediation updates, settings tweaks).

Used to populate the audit-log dashboard with believable data so the demo
shows a real audit trail rather than an empty table.

Idempotency: skip if any AuditLog rows exist for the tenant.

Realism notes:
  - Action mix uses ACTIVITY_TEMPLATES weights (login dominant, settings rare).
  - Working-hours bias: most events between 09:00-19:00 IST.
  - Weekend slowdown: 30% of weekday volume on Sat/Sun.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional, Union

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.audit_log import AuditLog
from backend.models.user import User
from backend.middleware.auth import hash_password
from backend.seed_simulators._common import (
    ACTIVITY_TEMPLATES,
    make_rng,
    now_utc,
    stable_uuid,
    stable_uuid_obj,
)


SYNTHETIC_DEMO_USERS = [
    # (email, full_name, role, team)
    ("vikram.mehta@example.com", "Vikram Mehta", "ciso", "Security"),
    ("priya.sharma@example.com", "Priya Sharma", "it_team", "IT"),
    ("rohan.iyer@example.com", "Rohan Iyer", "it_team", "Network & Security"),
    ("ananya.reddy@example.com", "Ananya Reddy", "ciso", "Compliance"),
    ("karan.shah@example.com", "Karan Shah", "executive", "Executive"),
    ("meera.nair@example.com", "Meera Nair", "it_team", "Cloud Engineering"),
]


async def _ensure_demo_users(
    session: AsyncSession, tenant_id: uuid.UUID
) -> list[User]:
    """Create the synthetic demo users if missing; return their User rows."""
    result_users = []
    for email, full_name, role, team in SYNTHETIC_DEMO_USERS:
        existing = (await session.execute(
            select(User).where(User.email == email, User.tenant_id == tenant_id)
        )).scalars().first()
        if existing:
            result_users.append(existing)
            continue

        u = User(
            id=stable_uuid_obj(str(tenant_id), "user", email),
            email=email,
            hashed_password=hash_password("DemoPass!Never1Used"),
            full_name=full_name,
            role=role,
            team=team,
            is_active=True,
            tenant_id=tenant_id,
        )
        session.add(u)
        result_users.append(u)
    await session.flush()
    return result_users


def _weighted_pick_action(rng) -> tuple[str, str]:
    actions = [t[0] for t in ACTIVITY_TEMPLATES]
    types = [t[1] for t in ACTIVITY_TEMPLATES]
    weights = [t[2] for t in ACTIVITY_TEMPLATES]
    idx = rng.choices(range(len(actions)), weights=weights)[0]
    return actions[idx], types[idx]


def _ip_for_user(rng) -> str:
    """Plausible Indian/remote IP."""
    return f"203.0.{rng.randint(0, 255)}.{rng.randint(1, 254)}"


def _details_for_action(action: str, rng) -> dict:
    if action == "login":
        return {"method": rng.choice(["password+mfa", "sso", "saml"]), "device": rng.choice(["macOS Sonoma", "Windows 11", "iOS"])}
    if action == "view_risk":
        return {"risk_severity": rng.choice(["critical", "high", "medium", "low"])}
    if action == "comment_on_risk":
        return {"comment_excerpt": rng.choice([
            "Validated with vendor — false positive on staging.",
            "Patched in next maintenance window — ETA 2 weeks.",
            "Compensating control accepted by CISO.",
            "Re-assigned to AppSec team for remediation.",
        ])}
    if action == "accept_risk":
        return {
            "expiry_days": rng.choice([30, 90, 180]),
            "justification_excerpt": "Business-critical legacy system; remediation scheduled for Q2 refresh.",
        }
    if action == "create_remediation":
        return {"due_in_days": rng.choice([7, 14, 30, 60])}
    if action == "update_remediation_status":
        return {"new_status": rng.choice(["in_progress", "blocked", "resolved"])}
    if action == "export_report":
        return {"format": rng.choice(["pdf", "csv", "xlsx"]), "report_type": rng.choice(["risk_register", "compliance_score", "executive_summary"])}
    if action == "rotate_connector_credential":
        return {"connector": rng.choice(["zscaler", "tenable", "ms_entra", "sentinelone"])}
    return {}


async def simulate_audit_log_activity(
    session: AsyncSession,
    *,
    tenant_id: Union[str, uuid.UUID],
    days: int = 60,
    events_per_day: int = 25,
    seed: int = 42,
    skip_if_existing: bool = True,
) -> dict:
    """
    Generate audit log activity for a tenant.

    Args:
        tenant_id:        Tenant UUID.
        days:             How many days of history.
        events_per_day:   Average events per weekday (Sat/Sun reduced 70%).
        seed:             RNG seed.
        skip_if_existing: Skip if any AuditLog exists for tenant.
    """
    tenant_uuid = (
        uuid.UUID(tenant_id) if isinstance(tenant_id, str) else tenant_id
    )

    if skip_if_existing:
        existing = (await session.execute(
            select(func.count()).select_from(AuditLog).where(
                AuditLog.tenant_id == tenant_uuid
            )
        )).scalar() or 0
        if existing > 0:
            return {
                "created": 0,
                "skipped_existing": existing,
                "tenant_id": str(tenant_uuid),
            }

    rng = make_rng(seed)
    users = await _ensure_demo_users(session, tenant_uuid)

    now = now_utc()
    created = 0

    for d in range(days):
        day_date = now - timedelta(days=days - d - 1)
        is_weekend = day_date.weekday() >= 5
        n = max(1, int(events_per_day * (0.3 if is_weekend else 1.0)))

        for _ in range(n):
            user = rng.choice(users)
            action, resource_type = _weighted_pick_action(rng)
            # Working-hours bias: 09:00 - 19:00 IST = roughly 03:30 - 13:30 UTC
            hour = rng.choices(
                list(range(0, 24)),
                weights=[
                    1, 1, 1, 4, 6, 8, 10, 12, 12, 10, 8, 6,  # 0-11 UTC
                    5, 4, 3, 2, 2, 2, 1, 1, 1, 1, 1, 1,       # 12-23 UTC
                ],
            )[0]
            ts = day_date.replace(
                hour=hour, minute=rng.randint(0, 59), second=rng.randint(0, 59)
            )

            log = AuditLog(
                id=stable_uuid_obj(
                    str(tenant_uuid), "audit_log",
                    str(d), action, str(_), user.email,
                ),
                user_id=user.id,
                action=action,
                resource_type=resource_type,
                resource_id=stable_uuid_obj(
                    str(tenant_uuid), action, resource_type, str(d), str(_)
                ) if resource_type not in ("session", "tenant") else None,
                details=_details_for_action(action, rng),
                ip_address=_ip_for_user(rng),
                tenant_id=tenant_uuid,
                created_at=ts,
            )
            session.add(log)
            created += 1

    await session.flush()
    return {
        "created": created,
        "skipped_existing": 0,
        "users_seeded": len(users),
        "tenant_id": str(tenant_uuid),
    }
