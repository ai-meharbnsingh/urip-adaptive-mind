"""
Policy Manager service — business logic for the Policy Management module.

Handles:
  - Policy creation with initial version
  - Version publishing
  - User acknowledgment (e-sign)
  - Pending acknowledgment queries
  - Reminder generation
  - Expiry checks

HIGH-5 (audit fix — Codex HIGH-004 + Kimi MED-007): the acknowledgment
``signature`` field is no longer attacker-controlled. The server now computes
an HMAC-SHA256 over (policy_version_id, user_id, acknowledged_at) using a
server-side signing key (env: ``COMPLIANCE_POLICY_ACK_HMAC_KEY``). External
auditors can re-verify any acknowledgment with ``verify_acknowledgment``.
"""
import hashlib
import hmac
import logging
import os
from datetime import datetime, timedelta
from typing import List, Optional, Tuple

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_

from compliance_backend.models.policy import Policy, PolicyVersion, PolicyAcknowledgment

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# HIGH-5 — server-side HMAC signing for non-repudiation.
# ---------------------------------------------------------------------------

def _ack_signing_key() -> bytes:
    """
    The server-side HMAC key. Must be set in production (env
    ``COMPLIANCE_POLICY_ACK_HMAC_KEY``). For dev / tests, falls back to a
    well-known weak default that emits a warning the first time it's used.
    Reading at call-time (not at module import) lets tests monkeypatch it.
    """
    raw = os.environ.get("COMPLIANCE_POLICY_ACK_HMAC_KEY", "").strip()
    if not raw:
        logger.warning(
            "COMPLIANCE_POLICY_ACK_HMAC_KEY is unset — using insecure dev "
            "fallback. Set this env var in any non-dev environment."
        )
        raw = "compliance-policy-ack-dev-key-DO-NOT-USE-IN-PROD"
    return raw.encode("utf-8")


def _compute_ack_signature(
    policy_version_id: str,
    user_id: str,
    acknowledged_at: datetime,
) -> str:
    """
    Server-computed HMAC-SHA256 over (policy_version_id, user_id, ts_iso).

    The timestamp is included so a replayed ack on a freshly-published
    version produces a distinct signature each time. ISO-8601 with
    microsecond resolution defeats trivial second-granularity collisions.
    """
    ts = acknowledged_at
    if ts.tzinfo is None:
        # Treat naive datetimes as UTC — matches how the model stores them.
        ts_iso = ts.isoformat()
    else:
        ts_iso = ts.isoformat()
    canonical = f"{policy_version_id}.{user_id}.{ts_iso}".encode("utf-8")
    return hmac.new(_ack_signing_key(), canonical, hashlib.sha256).hexdigest()


def verify_acknowledgment(ack: PolicyAcknowledgment) -> bool:
    """
    Re-derive the server HMAC for an existing acknowledgment row and compare
    with what's stored. Returns True on match, False on tamper.

    Uses :func:`hmac.compare_digest` for constant-time comparison.
    """
    if not ack.signature:
        return False
    expected = _compute_ack_signature(
        policy_version_id=ack.policy_version_id,
        user_id=ack.user_id,
        acknowledged_at=ack.acknowledged_at,
    )
    return hmac.compare_digest(expected, ack.signature)


async def create_policy(
    session: AsyncSession,
    tenant_id: str,
    name: str,
    content: str,
    owner: str,
    expires_at: Optional[datetime] = None,
) -> Policy:
    """
    Create a new policy with an initial version (v1).

    The initial version is auto-published.
    """
    policy = Policy(
        tenant_id=tenant_id,
        name=name,
        owner_user_id=owner,
        expires_at=expires_at,
        is_active=True,
    )
    session.add(policy)
    await session.flush()

    version = PolicyVersion(
        policy_id=policy.id,
        version_number=1,
        content=content,
        published_at=datetime.utcnow(),
        published_by_user_id=owner,
    )
    session.add(version)
    await session.flush()

    policy.current_version_id = version.id
    await session.flush()
    await session.refresh(policy, attribute_names=["current_version", "versions"])
    return policy


async def publish_new_version(
    session: AsyncSession,
    policy_id: str,
    content: str,
    change_summary: str,
    publisher: str,
) -> PolicyVersion:
    """
    Publish a new version of an existing policy.

    Increments version_number and updates policy.current_version_id.
    """
    result = await session.execute(
        select(func.max(PolicyVersion.version_number)).where(
            PolicyVersion.policy_id == policy_id
        )
    )
    max_version = result.scalar() or 0

    version = PolicyVersion(
        policy_id=policy_id,
        version_number=max_version + 1,
        content=content,
        published_at=datetime.utcnow(),
        published_by_user_id=publisher,
        change_summary=change_summary,
    )
    session.add(version)
    await session.flush()

    policy = await session.get(Policy, policy_id)
    if not policy:
        raise ValueError(f"Policy {policy_id} not found")
    policy.current_version_id = version.id
    await session.flush()
    await session.refresh(version, attribute_names=["policy", "acknowledgments"])
    return version


async def acknowledge(
    session: AsyncSession,
    policy_version_id: str,
    user_id: str,
    signature: str,  # HIGH-5: kept for API compat — IGNORED for storage.
) -> PolicyAcknowledgment:
    """
    Record a user's acknowledgment of a specific policy version.

    Idempotent — returns existing acknowledgment if already present.

    HIGH-5: the persisted ``signature`` is ALWAYS the server-computed
    HMAC-SHA256 over (policy_version_id, user_id, acknowledged_at). The
    ``signature`` argument from the caller is discarded — it is preserved
    in the function signature only because the routers and tests still
    pass a value, and removing the parameter would be a breaking API
    change in the same patch as the security fix. Auditors verify the
    stored hash with :func:`verify_acknowledgment`.
    """
    version_result = await session.execute(
        select(PolicyVersion).where(PolicyVersion.id == policy_version_id)
    )
    version = version_result.scalar_one_or_none()
    if not version:
        raise ValueError(f"Policy version {policy_version_id} not found")

    policy = await session.get(Policy, version.policy_id)
    if not policy:
        raise ValueError("Policy not found")

    existing_result = await session.execute(
        select(PolicyAcknowledgment).where(
            and_(
                PolicyAcknowledgment.policy_version_id == policy_version_id,
                PolicyAcknowledgment.user_id == user_id,
            )
        )
    )
    existing = existing_result.scalar_one_or_none()
    if existing:
        # Idempotent — return the row that was first stored, signature and all.
        return existing

    # Set acknowledged_at explicitly so we can sign it (model default fires
    # at flush time — too late for the HMAC).
    now = datetime.utcnow()
    server_signature = _compute_ack_signature(
        policy_version_id=policy_version_id,
        user_id=user_id,
        acknowledged_at=now,
    )

    ack = PolicyAcknowledgment(
        policy_version_id=policy_version_id,
        user_id=user_id,
        tenant_id=policy.tenant_id,
        acknowledged_at=now,
        signature=server_signature,
    )
    session.add(ack)
    await session.flush()
    return ack


async def list_pending_acknowledgments(
    session: AsyncSession,
    tenant_id: str,
    user_id: str,
) -> List[Policy]:
    """
    Return active policies in the tenant whose current version
    has NOT been acknowledged by the given user.
    """
    from sqlalchemy.orm import aliased

    Ack = aliased(PolicyAcknowledgment)

    stmt = (
        select(Policy)
        .outerjoin(
            Ack,
            and_(
                Ack.policy_version_id == Policy.current_version_id,
                Ack.user_id == user_id,
            ),
        )
        .where(
            Policy.tenant_id == tenant_id,
            Policy.is_active.is_(True),
            Policy.current_version_id.is_not(None),
            Ack.id.is_(None),
        )
        .order_by(Policy.created_at.desc())
    )

    result = await session.execute(stmt)
    return list(result.scalars().all())


async def send_reminders(
    session: AsyncSession,
    tenant_id: str,
) -> List[Tuple[Policy, str]]:
    """
    Return (policy, user_id) pairs needing a reminder.

    A user needs a reminder if they have acknowledged a previous version
    of a policy but NOT the current version.
    """
    policies_result = await session.execute(
        select(Policy).where(
            Policy.tenant_id == tenant_id,
            Policy.is_active.is_(True),
            Policy.current_version_id.is_not(None),
        )
    )
    policies = policies_result.scalars().all()

    reminders: List[Tuple[Policy, str]] = []
    for policy in policies:
        current_version_id = policy.current_version_id
        if not current_version_id:
            continue

        users_result = await session.execute(
            select(PolicyAcknowledgment.user_id)
            .join(PolicyVersion, PolicyVersion.id == PolicyAcknowledgment.policy_version_id)
            .where(PolicyVersion.policy_id == policy.id)
            .distinct()
        )
        all_users = set(users_result.scalars().all())

        current_acked_result = await session.execute(
            select(PolicyAcknowledgment.user_id)
            .where(
                PolicyAcknowledgment.policy_version_id == current_version_id,
            )
            .distinct()
        )
        current_acked = set(current_acked_result.scalars().all())

        for user_id in all_users - current_acked:
            reminders.append((policy, user_id))

    return reminders


async def check_expiry(
    session: AsyncSession,
    tenant_id: str,
    days: int = 30,
) -> List[Policy]:
    """
    Return policies expiring within the next N days.

    Only includes policies with a non-null expires_at that is still
    in the future (or today).
    """
    now = datetime.utcnow()
    cutoff = now + timedelta(days=days)

    result = await session.execute(
        select(Policy).where(
            Policy.tenant_id == tenant_id,
            Policy.expires_at.is_not(None),
            Policy.expires_at >= now,
            Policy.expires_at <= cutoff,
        )
    )
    return list(result.scalars().all())
