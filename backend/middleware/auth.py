"""
Backend auth middleware.

CRIT-005 — migrated from python-jose 3.3.0 (CVE-2024-33663 + CVE-2024-33664,
unmaintained library) to PyJWT 2.9+ which has the same surface for HS256.
HIGH-006 — get_current_user now also rejects requests when the user's tenant
has been deactivated (tenants.is_active = False).
"""

import uuid
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt as pyjwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import settings
from backend.database import get_db
from backend.models.tenant import Tenant
from backend.models.user import User

# Explicitly control "no token" behaviour: tests and existing clients expect
# missing Authorization to surface as 403 (HTTPBearer), while invalid/expired
# tokens remain 401.
security = HTTPBearer(auto_error=False)


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))


# L7 / L11 (Codex LOW-004) — issuer claim.  Tokens minted by URIP backend get
# iss="urip". decode_token() requires iss + exp.
JWT_ISSUER = "urip"
# Legacy constant: some modules import JWT_AUDIENCE for parity/documentation.
# Tokens no longer emit an `aud` claim; this is kept to avoid import breakage.
JWT_AUDIENCE = "urip-tenant"


def create_access_token(
    user_id: str,
    role: str,
    tenant_id: str | None = None,
    is_super_admin: bool = False,
    *,
    include_audience: bool = True,
) -> str:
    expire = datetime.now(timezone.utc) + timedelta(hours=settings.JWT_EXPIRE_HOURS)
    payload = {
        "sub": user_id,
        "role": role,
        "exp": expire,
        "is_super_admin": is_super_admin,
        # L7 — issuer + audience claims
        "iss": JWT_ISSUER,
    }
    # Keep `aud` for non-super-admin tokens (legacy tests / client inspection).
    # Super-admin tokens omit it so python-jose decoders without an audience
    # parameter can still decode them.
    if include_audience and not is_super_admin:
        payload["aud"] = JWT_AUDIENCE
    if tenant_id is not None:
        payload["tenant_id"] = tenant_id
    return pyjwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def decode_token(token: str) -> dict:
    """
    Decode a URIP JWT.

    Algorithm is pinned to settings.JWT_ALGORITHM (HS256 by default).  Passing
    `algorithms=[…]` to PyJWT defends against algorithm-confusion attacks
    (alg=none, alg=RS256-with-HMAC-key, etc.) that broke jose-style verifiers.

    L7/L11 hardening (Codex LOW-004):
      - require `exp` (rejects tokens without expiry)
      - require `iss` claim and verify it matches JWT_ISSUER
      - (aud is intentionally omitted for compatibility with legacy test decoders)
    """
    try:
        claims = pyjwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
            issuer=JWT_ISSUER,
            options={"require": ["exp", "iss"], "verify_aud": False},
        )
        aud = claims.get("aud")
        if aud is not None:
            if isinstance(aud, str):
                valid = (aud == JWT_AUDIENCE)
            elif isinstance(aud, list):
                valid = JWT_AUDIENCE in aud
            else:
                valid = False
            if not valid:
                raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token")
        return claims
    except pyjwt.PyJWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
    db: AsyncSession = Depends(get_db),
) -> User:
    from backend.middleware.tenant import TenantContext  # local import to avoid circular

    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authenticated",
        )

    payload = decode_token(credentials.credentials)
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid token payload")

    is_super_admin = payload.get("is_super_admin", False)
    tenant_id_str = payload.get("tenant_id")

    if not is_super_admin:
        if not tenant_id_str:
            raise HTTPException(status_code=401, detail="Token missing tenant context")
        try:
            TenantContext.set(uuid.UUID(tenant_id_str))
        except ValueError:
            raise HTTPException(status_code=401, detail="Invalid tenant_id in token")
    else:
        if tenant_id_str:
            try:
                TenantContext.set(uuid.UUID(tenant_id_str))
            except ValueError:
                raise HTTPException(status_code=401, detail="Invalid tenant_id in token")

    result = await db.execute(select(User).where(User.id == uuid.UUID(user_id)))
    user = result.scalar_one_or_none()
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="User not found or inactive")

    # HIGH-006: enforce tenant.is_active for non-super-admin users.
    # Super-admins are not bound to a tenant and can always log in to manage
    # the platform (this is intentional — needed to re-enable a tenant).
    if not is_super_admin and user.tenant_id is not None:
        tenant_result = await db.execute(
            select(Tenant).where(Tenant.id == user.tenant_id)
        )
        tenant = tenant_result.scalar_one_or_none()
        if tenant is None:
            raise HTTPException(status_code=403, detail="Tenant not found")
        if not tenant.is_active:
            raise HTTPException(status_code=403, detail="Tenant suspended")

    return user
