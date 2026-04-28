"""
ztna_service — Project_33a §13 LIVE (MVP scaffold, 14th license module).
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.ztna import (
    DECISION_VALUES,
    POSTURE_REQUIREMENT_VALUES,
    ZTNAAccessDecision,
    ZTNAPolicy,
    ZTNAPostureViolation,
)

logger = logging.getLogger(__name__)


_VALID_SEVERITY = {"critical", "high", "medium", "low"}


# --------------------------------------------------------------------------- #
def _validate_posture_requirements(values: list[str] | None) -> None:
    if values is None:
        return
    bad = [v for v in values if v not in POSTURE_REQUIREMENT_VALUES]
    if bad:
        raise ValueError(
            f"Invalid posture requirements {bad!r}; allowed: {sorted(POSTURE_REQUIREMENT_VALUES)}"
        )


# --------------------------------------------------------------------------- #
async def create_policy(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    *,
    policy_name: str,
    target_app: str,
    identity_required: bool = True,
    mfa_required: bool = True,
    device_posture_required: Optional[list[str]] = None,
    source_provider: Optional[str] = None,
) -> ZTNAPolicy:
    if not policy_name or not policy_name.strip():
        raise ValueError("policy_name is required")
    if not target_app or not target_app.strip():
        raise ValueError("target_app is required")
    _validate_posture_requirements(device_posture_required)

    p = ZTNAPolicy(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        policy_name=policy_name.strip(),
        target_app=target_app.strip(),
        identity_required=identity_required,
        mfa_required=mfa_required,
        device_posture_required=device_posture_required,
        source_provider=source_provider,
        last_evaluated_at=datetime.now(timezone.utc),
    )
    db.add(p)
    await db.flush()
    return p


async def list_policies(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    *,
    target_app: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
) -> list[ZTNAPolicy]:
    stmt = select(ZTNAPolicy).where(ZTNAPolicy.tenant_id == tenant_id)
    if target_app:
        stmt = stmt.where(ZTNAPolicy.target_app == target_app)
    stmt = stmt.order_by(ZTNAPolicy.created_at.desc()).limit(limit).offset(offset)
    result = await db.execute(stmt)
    return list(result.scalars().all())


# --------------------------------------------------------------------------- #
async def record_access_decision(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    *,
    user_identity: str,
    target_app: str,
    decision: str,
    policy_id: Optional[uuid.UUID] = None,
    reason: Optional[str] = None,
    source_ip: Optional[str] = None,
) -> ZTNAAccessDecision:
    if decision not in DECISION_VALUES:
        raise ValueError(f"Invalid decision {decision!r}; allowed: {sorted(DECISION_VALUES)}")
    if not user_identity or not target_app:
        raise ValueError("user_identity and target_app are required")

    d = ZTNAAccessDecision(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        policy_id=policy_id,
        user_identity=user_identity.strip(),
        target_app=target_app.strip(),
        decision=decision,
        reason=reason,
        source_ip=source_ip,
    )
    db.add(d)
    await db.flush()
    return d


async def list_access_decisions(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    *,
    decision: Optional[str] = None,
    target_app: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
) -> list[ZTNAAccessDecision]:
    stmt = select(ZTNAAccessDecision).where(ZTNAAccessDecision.tenant_id == tenant_id)
    if decision:
        stmt = stmt.where(ZTNAAccessDecision.decision == decision)
    if target_app:
        stmt = stmt.where(ZTNAAccessDecision.target_app == target_app)
    stmt = stmt.order_by(ZTNAAccessDecision.decided_at.desc()).limit(limit).offset(offset)
    result = await db.execute(stmt)
    return list(result.scalars().all())


# --------------------------------------------------------------------------- #
async def record_posture_violation(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    *,
    user_identity: str,
    failed_requirement: str,
    severity: str = "medium",
    device_id: Optional[str] = None,
) -> ZTNAPostureViolation:
    if failed_requirement not in POSTURE_REQUIREMENT_VALUES:
        raise ValueError(
            f"Invalid failed_requirement {failed_requirement!r}; "
            f"allowed: {sorted(POSTURE_REQUIREMENT_VALUES)}"
        )
    if severity not in _VALID_SEVERITY:
        raise ValueError(f"Invalid severity {severity!r}")

    v = ZTNAPostureViolation(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        user_identity=user_identity.strip(),
        device_id=device_id,
        failed_requirement=failed_requirement,
        severity=severity,
    )
    db.add(v)
    await db.flush()
    return v


async def list_posture_violations(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    *,
    severity: Optional[str] = None,
    remediated: Optional[bool] = None,
    limit: int = 100,
    offset: int = 0,
) -> list[ZTNAPostureViolation]:
    stmt = select(ZTNAPostureViolation).where(ZTNAPostureViolation.tenant_id == tenant_id)
    if severity:
        stmt = stmt.where(ZTNAPostureViolation.severity == severity)
    if remediated is not None:
        stmt = stmt.where(ZTNAPostureViolation.remediated == remediated)
    stmt = stmt.order_by(ZTNAPostureViolation.detected_at.desc()).limit(limit).offset(offset)
    result = await db.execute(stmt)
    return list(result.scalars().all())
