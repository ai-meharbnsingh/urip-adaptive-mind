"""
Policy Management API — Phase 2B.5

Endpoints:
  POST /policies                — create policy (admin)
  GET  /policies                — list tenant policies
  GET  /policies/pending        — current user's pending acknowledgments
  GET  /policies/expiring       — policies expiring soon (admin)
  GET  /policies/{id}           — policy detail with current version
  GET  /policies/{id}/versions  — version history
  POST /policies/{id}/versions  — publish new version (admin)
  POST /policies/{id}/acknowledge — acknowledge current version
"""
from datetime import datetime
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from compliance_backend.database import get_async_session
from compliance_backend.middleware.auth import (
    require_auth,
    require_compliance_admin,
)
from compliance_backend.middleware.tenant import require_tenant
from compliance_backend.models.policy import Policy, PolicyVersion
from compliance_backend.services import policy_manager
from compliance_backend.services.audit_writer import write_audit

router = APIRouter(prefix="/policies", tags=["policies"])


# ---------------------------------------------------------------------------
# Dependencies
# ---------------------------------------------------------------------------
#
# Audit-fix CLAUDE-CRIT-A / KIMI-HIGH-004 — the local `require_admin` here used
# to compare `claims.get("role") != "admin"`. In INTEGRATED mode URIP issues
# the JWT and uses roles {board, executive, it_team, ciso} — never "admin"
# — so the previous gate denied ALL legitimate URIP users, and the policy
# admin pane was unreachable. The other admin routers in this service
# (auditor_invitations, admin_evidence_requests, admin_auditor_activity,
# compliance_score) already route through `require_compliance_admin`. The
# policies router was missed by the CRIT-008 sweep; this fix routes it
# through the same centralised helper so the gate stays consistent
# everywhere.

async def _require_admin(
    claims: dict = Depends(require_auth),
) -> dict:
    """Centralised compliance-admin gate (mirrors the other admin routers)."""
    require_compliance_admin(claims)
    return claims


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class PolicyVersionOut(BaseModel):
    id: str
    policy_id: str
    version_number: int
    content: str
    published_at: Optional[str]
    published_by_user_id: Optional[str]
    change_summary: Optional[str]

    model_config = {"from_attributes": True}


class PolicyOut(BaseModel):
    id: str
    tenant_id: str
    name: str
    owner_user_id: str
    current_version_id: Optional[str]
    expires_at: Optional[str]
    is_active: bool
    created_at: str

    model_config = {"from_attributes": True}


class PolicyDetail(PolicyOut):
    current_version: Optional[PolicyVersionOut]


class PolicyCreate(BaseModel):
    name: str
    content: str
    expires_at: Optional[str] = None


class PolicyVersionCreate(BaseModel):
    content: str
    change_summary: str


class AcknowledgeRequest(BaseModel):
    signature: str


class AcknowledgeOut(BaseModel):
    id: str
    policy_version_id: str
    user_id: str
    tenant_id: str
    acknowledged_at: str
    signature: str

    model_config = {"from_attributes": True}


class ReminderOut(BaseModel):
    policy_id: str
    policy_name: str
    user_id: str


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("", response_model=PolicyDetail, status_code=status.HTTP_201_CREATED)
async def create_policy(
    data: PolicyCreate,
    tenant_id: str = Depends(require_tenant),
    claims: dict = Depends(_require_admin),
    session: AsyncSession = Depends(get_async_session),
):
    owner = claims.get("sub", "unknown")
    expires_at = None
    if data.expires_at:
        expires_at = datetime.fromisoformat(data.expires_at)

    policy = await policy_manager.create_policy(
        session=session,
        tenant_id=tenant_id,
        name=data.name,
        content=data.content,
        owner=owner,
        expires_at=expires_at,
    )
    await write_audit(
        session,
        tenant_id=tenant_id,
        user_id=owner,
        action="policy_created",
        resource_type="policy",
        resource_id=policy.id,
        details={"name": data.name},
    )
    await session.commit()
    return _policy_detail(policy)


@router.get("", response_model=List[PolicyOut])
async def list_policies(
    tenant_id: str = Depends(require_tenant),
    _claims: dict = Depends(require_auth),
    session: AsyncSession = Depends(get_async_session),
):
    result = await session.execute(
        select(Policy)
        .where(Policy.tenant_id == tenant_id)
        .order_by(Policy.created_at.desc())
    )
    policies = result.scalars().all()
    return [_policy_out(p) for p in policies]


@router.get("/pending", response_model=List[PolicyOut])
async def list_pending(
    tenant_id: str = Depends(require_tenant),
    claims: dict = Depends(require_auth),
    session: AsyncSession = Depends(get_async_session),
):
    user_id = claims.get("sub", "unknown")
    pending = await policy_manager.list_pending_acknowledgments(
        session, tenant_id, user_id
    )
    return [_policy_out(p) for p in pending]


@router.get("/expiring", response_model=List[PolicyOut])
async def list_expiring(
    tenant_id: str = Depends(require_tenant),
    _claims: dict = Depends(_require_admin),
    session: AsyncSession = Depends(get_async_session),
):
    expiring = await policy_manager.check_expiry(session, tenant_id)
    return [_policy_out(p) for p in expiring]


@router.get("/{policy_id}", response_model=PolicyDetail)
async def get_policy(
    policy_id: str,
    tenant_id: str = Depends(require_tenant),
    _claims: dict = Depends(require_auth),
    session: AsyncSession = Depends(get_async_session),
):
    result = await session.execute(
        select(Policy)
        .options(selectinload(Policy.current_version))
        .where(Policy.id == policy_id)
    )
    policy = result.scalar_one_or_none()
    if not policy or policy.tenant_id != tenant_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Policy not found",
        )
    return _policy_detail(policy)


@router.get("/{policy_id}/versions", response_model=List[PolicyVersionOut])
async def list_versions(
    policy_id: str,
    tenant_id: str = Depends(require_tenant),
    _claims: dict = Depends(require_auth),
    session: AsyncSession = Depends(get_async_session),
):
    policy = await session.get(Policy, policy_id)
    if not policy or policy.tenant_id != tenant_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Policy not found",
        )
    result = await session.execute(
        select(PolicyVersion)
        .where(PolicyVersion.policy_id == policy_id)
        .order_by(PolicyVersion.version_number.desc())
    )
    versions = result.scalars().all()
    return [_version_out(v) for v in versions]


@router.post("/{policy_id}/versions", response_model=PolicyVersionOut)
async def publish_version(
    policy_id: str,
    data: PolicyVersionCreate,
    tenant_id: str = Depends(require_tenant),
    claims: dict = Depends(_require_admin),
    session: AsyncSession = Depends(get_async_session),
):
    policy = await session.get(Policy, policy_id)
    if not policy or policy.tenant_id != tenant_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Policy not found",
        )
    version = await policy_manager.publish_new_version(
        session=session,
        policy_id=policy_id,
        content=data.content,
        change_summary=data.change_summary,
        publisher=claims.get("sub", "unknown"),
    )
    await write_audit(
        session,
        tenant_id=tenant_id,
        user_id=claims.get("sub", "unknown"),
        action="policy_version_published",
        resource_type="policy_version",
        resource_id=version.id,
        details={
            "policy_id": policy_id,
            "version_number": version.version_number,
            "change_summary": data.change_summary,
        },
    )
    await session.commit()
    return _version_out(version)


@router.post("/{policy_id}/acknowledge", response_model=AcknowledgeOut)
async def acknowledge_policy(
    policy_id: str,
    data: AcknowledgeRequest,
    tenant_id: str = Depends(require_tenant),
    claims: dict = Depends(require_auth),
    session: AsyncSession = Depends(get_async_session),
):
    policy = await session.get(Policy, policy_id)
    if not policy or policy.tenant_id != tenant_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Policy not found",
        )
    if not policy.current_version_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Policy has no published version",
        )
    ack = await policy_manager.acknowledge(
        session=session,
        policy_version_id=policy.current_version_id,
        user_id=claims.get("sub", "unknown"),
        signature=data.signature,
    )
    await write_audit(
        session,
        tenant_id=tenant_id,
        user_id=claims.get("sub", "unknown"),
        action="policy_acknowledged",
        resource_type="policy_acknowledgment",
        resource_id=ack.id,
        details={
            "policy_id": policy_id,
            "policy_version_id": policy.current_version_id,
        },
    )
    await session.commit()
    return _ack_out(ack)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _policy_out(p: Policy) -> PolicyOut:
    return PolicyOut(
        id=p.id,
        tenant_id=p.tenant_id,
        name=p.name,
        owner_user_id=p.owner_user_id,
        current_version_id=p.current_version_id,
        expires_at=p.expires_at.isoformat() if p.expires_at else None,
        is_active=p.is_active,
        created_at=p.created_at.isoformat() if p.created_at else None,
    )


def _version_out(v: PolicyVersion) -> PolicyVersionOut:
    return PolicyVersionOut(
        id=v.id,
        policy_id=v.policy_id,
        version_number=v.version_number,
        content=v.content,
        published_at=v.published_at.isoformat() if v.published_at else None,
        published_by_user_id=v.published_by_user_id,
        change_summary=v.change_summary,
    )


def _policy_detail(p: Policy) -> PolicyDetail:
    base = _policy_out(p)
    detail_data = base.model_dump()
    detail_data["current_version"] = (
        _version_out(p.current_version) if p.current_version else None
    )
    return PolicyDetail(**detail_data)


def _ack_out(a) -> AcknowledgeOut:
    return AcknowledgeOut(
        id=a.id,
        policy_version_id=a.policy_version_id,
        user_id=a.user_id,
        tenant_id=a.tenant_id,
        acknowledged_at=a.acknowledged_at.isoformat() if a.acknowledged_at else None,
        signature=a.signature,
    )
