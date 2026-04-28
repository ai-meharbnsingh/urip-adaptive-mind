"""
Auditor JWT verification middleware — P2B.10.

Separates auditor identity from regular user identity:
  - Auditor JWTs always have claim kind="auditor"
  - Always signed with COMPLIANCE_JWT_SECRET (Compliance is the issuer regardless
    of STANDALONE/INTEGRATED mode — URIP doesn't know about external auditors)
  - Every request re-checks AuditorAccess for revocation + expiry; the JWT exp
    alone is not sufficient (admin may revoke before token's natural expiry).

Security invariants enforced:
  1. Token signature valid + not expired (JWT layer)
  2. Token kind == "auditor" (rejects regular user tokens trying to call /auditor/*)
  3. AuditorAccess row exists, is_revoked=False, expires_at>now (DB layer)
  4. Every action logged to auditor_activity_log via log_auditor_action()
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
# CRIT-005 (Z2.1) — Migrated from python-jose to PyJWT 2.9+ (see
# middleware/auth.py for migration rationale: jose CVE-2024-33663/-33664,
# unmaintained). Decode pins algorithms=["HS256"] which PyJWT enforces
# strictly, blocking algorithm-confusion attacks (alg=none, alg-mismatch).
import jwt as pyjwt
from sqlalchemy.ext.asyncio import AsyncSession

from compliance_backend.config import settings
from compliance_backend.database import get_async_session
from compliance_backend.models.auditor import AuditorActivityLog
from compliance_backend.services.auditor_service import AuditorService

bearer_scheme = HTTPBearer(auto_error=False)


# ---------------------------------------------------------------------------
# AuditorContext — value object passed to handlers
# ---------------------------------------------------------------------------

@dataclass
class AuditorContext:
    access_id: str
    tenant_id: str
    framework_id: str
    auditor_email: str
    period_start: datetime
    period_end: datetime


# ---------------------------------------------------------------------------
# Dependency: require_auditor
# ---------------------------------------------------------------------------

async def require_auditor(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
    session: AsyncSession = Depends(get_async_session),
) -> AuditorContext:
    """
    FastAPI dependency for /auditor/* routes.

    Raises 401 on:
      - Missing / malformed bearer token
      - Token signature invalid / expired
      - Token claim kind != "auditor"
      - AuditorAccess row revoked / expired / missing
    """
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Authorization header",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        # Auditor tokens always signed with COMPLIANCE_JWT_SECRET.
        # PyJWT enforces algorithms=["HS256"] strictly — alg=none and
        # alg-mismatch tokens raise jwt.InvalidTokenError (algorithm-confusion
        # protection).
        # L7 / L11 — `exp` is required; if `aud` is set it must match
        # "compliance-auditor".  The `verify_aud=False` + manual check below
        # keeps backward-compat with old tokens that have no aud claim.
        claims = pyjwt.decode(
            credentials.credentials,
            settings.COMPLIANCE_JWT_SECRET,
            algorithms=["HS256"],
            options={"require": ["exp"], "verify_aud": False},
        )
        if "aud" in claims:
            token_aud = claims["aud"]
            aud_list = [token_aud] if isinstance(token_aud, str) else list(token_aud)
            if "compliance-auditor" not in aud_list:
                raise pyjwt.InvalidTokenError(
                    f"Invalid audience for auditor token: {token_aud!r}"
                )
    except pyjwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Auditor token expired.",
        )
    except pyjwt.InvalidTokenError as exc:
        # jwt.InvalidTokenError is PyJWT's umbrella exception, equivalent to
        # the broader jose.JWTError for our purposes (signature invalid,
        # malformed token, alg mismatch, alg=none rejected, etc.).
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid auditor token: {exc}",
        )

    if claims.get("kind") != "auditor":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token is not an auditor token.",
        )

    access_id = claims.get("access_id")
    if not access_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token missing access_id claim.",
        )

    svc = AuditorService(db=session)
    access = await svc.get_active_access(access_id)
    if access is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Auditor access revoked or expired.",
        )

    # Defensive: claims and DB row must agree on tenant + framework
    if (
        access.tenant_id != claims.get("tenant_id")
        or access.framework_id != claims.get("framework_id")
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token claims mismatch with access record.",
        )

    return AuditorContext(
        access_id=access.id,
        tenant_id=access.tenant_id,
        framework_id=access.framework_id,
        auditor_email=access.auditor_email,
        period_start=access.audit_period_start,
        period_end=access.audit_period_end,
    )


# ---------------------------------------------------------------------------
# Activity logging helper
# ---------------------------------------------------------------------------

async def log_auditor_action(
    session: AsyncSession,
    auditor: AuditorContext,
    *,
    action: str,
    target_type: Optional[str] = None,
    target_id: Optional[str] = None,
    request: Optional[Request] = None,
) -> AuditorActivityLog:
    """
    Append an auditor activity log row.

    Caller is responsible for commit (so write happens in the same transaction
    as the action being logged — atomicity guarantee).
    """
    ip = None
    if request is not None and request.client is not None:
        ip = request.client.host

    log = AuditorActivityLog(
        tenant_id=auditor.tenant_id,
        auditor_access_id=auditor.access_id,
        auditor_email=auditor.auditor_email,
        action=action,
        target_type=target_type,
        target_id=target_id,
        ip_address=ip,
    )
    session.add(log)
    await session.flush()
    return log
