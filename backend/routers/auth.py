"""
Auth router — login, /me.

HIGH-008: every login attempt (success and failure) is persisted as an
AuditLog row with action="login_attempt".  The submitted password is NEVER
written to any field — only the email, success flag, IP, user-agent and
failure_reason are recorded.

HIGH-4 (audit fix): the unknown-email branch now runs a dummy bcrypt.checkpw
against a constant fake hash so response time matches the known-user /
wrong-password branch, defeating account-enumeration via timing
(Gemini HIGH-G1, Kimi MED-004).
"""

from typing import Optional

import bcrypt
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from backend.middleware.auth import create_access_token, get_current_user, verify_password
from backend.models.audit_log import AuditLog
from backend.models.tenant import Tenant
from backend.models.user import User
from backend.schemas.auth import LoginRequest, TokenResponse, UserProfile

# HIGH-4 — constant bcrypt hash used to soak up the time of "login attempt for
# an email that doesn't exist". The hash is generated once at module import,
# so it leaks nothing — but bcrypt.checkpw on it takes the same ~50-200ms a
# real verify_password call would, defeating account enumeration via timing.
_DUMMY_PASSWORD_HASH = bcrypt.hashpw(
    b"this-is-a-dummy-password-for-timing-equalisation",
    bcrypt.gensalt(),
)

router = APIRouter()

async def _record_login_attempt(
    db: AsyncSession,
    *,
    actor_email: str,
    success: bool,
    ip_address: str,
    user_agent: str,
    user: Optional[User],
    tenant_id,
    failure_reason: Optional[str] = None,
) -> None:
    """
    Persist a single AuditLog row describing the login attempt.

    NEVER writes the password anywhere — `details` only carries metadata.
    """
    details = {
        "actor_email": actor_email,
        "success": success,
        "user_agent": user_agent,
        "failure_reason": failure_reason,
    }
    db.add(AuditLog(
        user_id=user.id if user is not None else None,
        action="login_attempt",
        resource_type="auth",
        resource_id=None,
        details=details,
        ip_address=ip_address,
        tenant_id=tenant_id,
    ))
    await db.commit()


@router.post("/login", response_model=TokenResponse)
async def login(request: LoginRequest, req: Request, db: AsyncSession = Depends(get_db)):
    client_ip = req.client.host if req.client else "unknown"
    user_agent = req.headers.get("user-agent", "")

    result = await db.execute(select(User).where(User.email == request.email))
    user = result.scalar_one_or_none()

    if user is None:
        # HIGH-4 — Unknown email: still run bcrypt.checkpw against a constant
        # dummy hash so response time matches the known-user-wrong-password
        # path. The result is discarded; the caller still gets a generic 401.
        try:
            bcrypt.checkpw(
                request.password.encode("utf-8"),
                _DUMMY_PASSWORD_HASH,
            )
        except Exception:  # pragma: no cover — never let a hash error leak timing
            pass

        # Log and fail.
        await _record_login_attempt(
            db,
            actor_email=request.email,
            success=False,
            ip_address=client_ip,
            user_agent=user_agent,
            user=None,
            tenant_id=None,
            failure_reason="user_not_found",
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    if not verify_password(request.password, user.hashed_password):
        await _record_login_attempt(
            db,
            actor_email=request.email,
            success=False,
            ip_address=client_ip,
            user_agent=user_agent,
            user=user,
            tenant_id=user.tenant_id,
            failure_reason="password_mismatch",
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    if not user.is_active:
        await _record_login_attempt(
            db,
            actor_email=request.email,
            success=False,
            ip_address=client_ip,
            user_agent=user_agent,
            user=user,
            tenant_id=user.tenant_id,
            failure_reason="account_disabled",
        )
        raise HTTPException(status_code=403, detail="Account is deactivated")

    # HIGH-006 — also block tenant-suspended users at login (in addition to
    # get_current_user enforcement on every subsequent request).
    if user.tenant_id is not None and not user.is_super_admin:
        tenant_q = await db.execute(select(Tenant).where(Tenant.id == user.tenant_id))
        tenant = tenant_q.scalar_one_or_none()
        if tenant is not None and not tenant.is_active:
            await _record_login_attempt(
                db,
                actor_email=request.email,
                success=False,
                ip_address=client_ip,
                user_agent=user_agent,
                user=user,
                tenant_id=user.tenant_id,
                failure_reason="tenant_suspended",
            )
            raise HTTPException(status_code=403, detail="Tenant suspended")

    # Embed tenant_id in JWT — str() works whether tenant_id is UUID or None (legacy users)
    tenant_id_str = str(user.tenant_id) if user.tenant_id else None
    token = create_access_token(
        str(user.id),
        user.role,
        tenant_id=tenant_id_str,
        is_super_admin=bool(user.is_super_admin),
        include_audience=False,
    )

    # Resolve tenant_slug for richer client UX (used by white-label routing)
    tenant_slug: str | None = None
    if user.tenant_id is not None:
        slug_result = await db.execute(select(Tenant.slug).where(Tenant.id == user.tenant_id))
        tenant_slug = slug_result.scalar_one_or_none()

    # Successful login → audit row
    await _record_login_attempt(
        db,
        actor_email=request.email,
        success=True,
        ip_address=client_ip,
        user_agent=user_agent,
        user=user,
        tenant_id=user.tenant_id,
        failure_reason=None,
    )

    return TokenResponse(
        access_token=token,
        user=UserProfile(
            id=str(user.id),
            email=user.email,
            full_name=user.full_name,
            role=user.role,
            team=user.team,
            is_super_admin=bool(user.is_super_admin),
            tenant_slug=tenant_slug,
        ),
    )


@router.get("/me", response_model=UserProfile)
async def get_me(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    tenant_slug: str | None = None
    if current_user.tenant_id is not None:
        slug_result = await db.execute(
            select(Tenant.slug).where(Tenant.id == current_user.tenant_id)
        )
        tenant_slug = slug_result.scalar_one_or_none()

    return UserProfile(
        id=str(current_user.id),
        email=current_user.email,
        full_name=current_user.full_name,
        role=current_user.role,
        team=current_user.team,
        is_super_admin=bool(current_user.is_super_admin),
        tenant_slug=tenant_slug,
    )
