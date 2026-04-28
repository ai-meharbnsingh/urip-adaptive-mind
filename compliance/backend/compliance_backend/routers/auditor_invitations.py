"""
Auditor invitations API — P2B.10

Endpoints (admin):
  POST   /auditor-invitations         — create invitation, returns redemption URL
  DELETE /auditor-invitations/{id}    — revoke (immediate; no grace period)
  GET    /auditor-invitations         — list invitations for the authenticated tenant

Endpoint (public, no auth — anyone holding the token can redeem):
  POST   /auditor-invitations/accept  — exchange invitation token for auditor JWT

The accept endpoint is intentionally unauthenticated — the token IS the credential.
That mirrors GitHub/Slack/Notion invitation patterns. Defense-in-depth: token
is opaque (not guessable), single-use semantics aren't enforced (multiple accepts
just refresh the JWT — useful when auditor switches devices), revocation is
instant via DELETE.
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from compliance_backend.database import get_async_session
from compliance_backend.middleware.auth import require_auth
from compliance_backend.middleware.tenant import require_tenant
from compliance_backend.models.auditor import AuditorAccess
from compliance_backend.services.audit_writer import write_audit
from compliance_backend.services.auditor_service import AuditorService

router = APIRouter(prefix="/auditor-invitations", tags=["auditor-invitations"])


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class InvitationCreate(BaseModel):
    auditor_email: EmailStr
    framework_id: str
    audit_period_start: datetime
    audit_period_end: datetime
    expires_at: datetime


class InvitationOut(BaseModel):
    id: str
    auditor_email: str
    framework_id: str
    audit_period_start: str
    audit_period_end: str
    expires_at: str
    is_revoked: bool
    accepted_at: Optional[str]
    created_at: str
    # invitation_url ONLY present in the create response — not in list/read.
    invitation_url: Optional[str] = None


class AcceptRequest(BaseModel):
    token: str = Field(..., min_length=10)


class AcceptResponse(BaseModel):
    auditor_jwt: str
    expires_at: str


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _require_admin(claims: dict) -> None:
    # CRIT-008 — delegate to centralised gate that knows URIP-side roles
    # (ciso / is_super_admin / is_compliance_admin) plus legacy "admin".
    from compliance_backend.middleware.auth import require_compliance_admin

    require_compliance_admin(
        claims,
        detail="Only tenant admins may manage auditor invitations.",
    )


def _to_out(rec: AuditorAccess, *, invitation_url: Optional[str] = None) -> InvitationOut:
    return InvitationOut(
        id=rec.id,
        auditor_email=rec.auditor_email,
        framework_id=rec.framework_id,
        audit_period_start=rec.audit_period_start.isoformat(),
        audit_period_end=rec.audit_period_end.isoformat(),
        expires_at=rec.expires_at.isoformat(),
        is_revoked=rec.is_revoked,
        accepted_at=rec.accepted_at.isoformat() if rec.accepted_at else None,
        created_at=rec.created_at.isoformat(),
        invitation_url=invitation_url,
    )


def _build_invitation_url(request: Request, raw_token: str) -> str:
    """Build the auditor-portal redemption URL.

    In production this would point at the frontend (e.g. https://app.example.com/auditor/accept).
    For the API stub we surface the API path — callers can rewrite for their UI.
    """
    base = str(request.base_url).rstrip("/")
    return f"{base}/auditor-invitations/accept?token={raw_token}"


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("", response_model=InvitationOut, status_code=status.HTTP_201_CREATED)
async def create_invitation(
    body: InvitationCreate,
    request: Request,
    claims: dict = Depends(require_auth),
    tenant_id: str = Depends(require_tenant),
    session: AsyncSession = Depends(get_async_session),
) -> InvitationOut:
    """
    Create an auditor invitation. Admin-only.

    Returns the persisted invitation + the one-time redemption URL containing
    the raw token. The token is NOT recoverable after this response — admin
    must re-send the link or create a fresh invitation.
    """
    _require_admin(claims)

    svc = AuditorService(db=session)
    try:
        result = await svc.create_invitation(
            tenant_id=tenant_id,
            auditor_email=str(body.auditor_email),
            framework_id=body.framework_id,
            audit_period_start=body.audit_period_start,
            audit_period_end=body.audit_period_end,
            expires_at=body.expires_at,
            invited_by_user_id=claims.get("sub", "unknown"),
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        )

    await write_audit(
        session,
        tenant_id=tenant_id,
        user_id=claims.get("sub", "unknown"),
        action="auditor_invitation_created",
        resource_type="auditor_invitation",
        resource_id=result.access.id,
        details={
            "auditor_email": str(body.auditor_email),
            "framework_id": body.framework_id,
            "expires_at": body.expires_at.isoformat(),
        },
    )
    await session.commit()
    invitation_url = _build_invitation_url(request, result.raw_token)
    return _to_out(result.access, invitation_url=invitation_url)


@router.post("/accept", response_model=AcceptResponse)
async def accept_invitation(
    body: AcceptRequest,
    session: AsyncSession = Depends(get_async_session),
) -> AcceptResponse:
    """
    Public — exchange invitation token for an auditor JWT.

    Returns 401 if the token is invalid, revoked, or expired (we deliberately
    do not distinguish causes to avoid leaking info to brute-force probes).
    """
    svc = AuditorService(db=session)
    result = await svc.accept_invitation(body.token)
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invitation token is invalid, revoked, or expired.",
        )
    # M5 / Codex MED-007 — single-use enforcement: a previously-redeemed
    # token is rejected with 409 (Conflict) so the operator immediately
    # knows the link has been consumed and can issue a fresh invitation.
    if result == AuditorService.ALREADY_ACCEPTED:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Invitation token has already been redeemed.",
        )
    access, jwt_token = result
    await session.commit()
    return AcceptResponse(
        auditor_jwt=jwt_token,
        expires_at=access.expires_at.isoformat(),
    )


@router.delete(
    "/{invitation_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_model=None,  # CritFix-D: required because `from __future__ import annotations` defers `-> None`, breaking FastAPI's body-allowed assertion on Python 3.14
)
async def revoke_invitation(
    invitation_id: str,
    claims: dict = Depends(require_auth),
    tenant_id: str = Depends(require_tenant),
    session: AsyncSession = Depends(get_async_session),
) -> None:
    """Revoke an invitation. Admin-only. Returns 404 if not found in tenant."""
    _require_admin(claims)
    svc = AuditorService(db=session)
    ok = await svc.revoke_invitation(invitation_id, tenant_id)
    if not ok:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Invitation '{invitation_id}' not found.",
        )
    await write_audit(
        session,
        tenant_id=tenant_id,
        user_id=claims.get("sub", "unknown"),
        action="auditor_invitation_revoked",
        resource_type="auditor_invitation",
        resource_id=invitation_id,
        details={},
    )
    await session.commit()


@router.get("", response_model=List[InvitationOut])
async def list_invitations(
    claims: dict = Depends(require_auth),
    tenant_id: str = Depends(require_tenant),
    session: AsyncSession = Depends(get_async_session),
) -> List[InvitationOut]:
    """List all invitations issued by this tenant (admin only)."""
    _require_admin(claims)
    rows = (await session.execute(
        select(AuditorAccess)
        .where(AuditorAccess.tenant_id == tenant_id)
        .order_by(AuditorAccess.created_at.desc())
    )).scalars().all()
    return [_to_out(r) for r in rows]
