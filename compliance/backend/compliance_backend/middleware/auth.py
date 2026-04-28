"""
JWT verification middleware for the Compliance Service.

Two modes (set via COMPLIANCE_AUTH_MODE env var):

  STANDALONE   — Compliance verifies using COMPLIANCE_JWT_SECRET (its own tokens).
                 Used when Compliance is deployed alone (Sprinto-replacement mode).

  INTEGRATED   — Compliance verifies using URIP_JWT_SECRET (shared signing secret).
                 Used when both URIP + Compliance run together. URIP issues the token;
                 Compliance only needs to verify + extract claims.

Usage as a FastAPI dependency:
    from compliance_backend.middleware.auth import require_auth

    @router.get("/protected")
    async def handler(claims: dict = Depends(require_auth)):
        tenant_id = claims["tenant_id"]
        ...
"""
import os
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
# CRIT-005 (Z2.1) — Migrated from python-jose to PyJWT 2.9+ (jose CVE-2024-33663
# algorithm-confusion + CVE-2024-33664 DoS; jose is unmaintained).
#   PyJWT raises ``jwt.InvalidTokenError`` family (parent of all errors) and
#   ``jwt.ExpiredSignatureError`` for expiry. ``algorithms=["HS256"]`` is
#   passed on every decode call so ``alg=none`` and HS512 tokens are rejected.
import jwt
from jwt.exceptions import ExpiredSignatureError, InvalidTokenError

from compliance_backend.config import settings

bearer_scheme = HTTPBearer(auto_error=False)


def _active_secret() -> str:
    """Return the correct secret based on current auth mode."""
    mode = settings.COMPLIANCE_AUTH_MODE.upper()
    if mode == "INTEGRATED":
        return settings.URIP_JWT_SECRET
    # Default: STANDALONE
    return settings.COMPLIANCE_JWT_SECRET


def verify_token(token: str) -> dict:
    """
    Verify a JWT and return its claims dict.

    Raises:
        jwt.InvalidTokenError  — signature invalid, malformed, or alg mismatch
        jwt.ExpiredSignatureError — token is expired
    """
    secret = _active_secret()
    claims = jwt.decode(token, secret, algorithms=["HS256"])
    return claims


async def require_auth(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
) -> dict:
    """
    FastAPI dependency that enforces JWT authentication.

    Extracts the Bearer token, verifies it with the active secret, and returns
    the decoded claims dict. Raises 401 on any failure.
    """
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Authorization header",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        claims = verify_token(credentials.credentials)
    except ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except InvalidTokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid token: {exc}",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return claims


# ---------------------------------------------------------------------------
# CRIT-008 — compliance-admin gate (centralised)
# ---------------------------------------------------------------------------
#
# The original gate checked claims.get("role") in {"admin","owner","compliance_admin"}.
# In INTEGRATED mode URIP issues the JWT, and URIP's ROLE_HIERARCHY only contains
# {"board","executive","it_team","ciso"} — so the legacy gate ALWAYS denied URIP
# users access to compliance admin routes (entire admin path was unreachable).
#
# This helper accepts a user as a compliance admin if ANY of:
#   - claims["role"] == "ciso"            (highest tenant-level URIP role)
#   - claims["is_super_admin"] is True    (URIP super-admin bypass)
#   - claims["is_compliance_admin"] is True
#       (capability flag URIP backend should add to the JWT — see coordination
#        note in critfix C report; until backend ships, ciso/super-admin paths
#        are sufficient)
#   - claims["role"] == "admin"           (STANDALONE-mode compliance-issued
#       legacy tokens — kept for backward compat in non-integrated deployments)


COMPLIANCE_ADMIN_ROLES: frozenset = frozenset({"ciso", "admin"})


def is_compliance_admin(claims: dict) -> bool:
    """Return True iff the JWT claims authorise compliance-admin operations."""
    if not isinstance(claims, dict):
        return False
    if claims.get("is_super_admin") is True:
        return True
    if claims.get("is_compliance_admin") is True:
        return True
    role = claims.get("role")
    return role in COMPLIANCE_ADMIN_ROLES


def require_compliance_admin(claims: dict, *, detail: str = "Admin role required.") -> None:
    """Raise 403 if the caller is not a compliance admin."""
    if not is_compliance_admin(claims):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=detail,
        )
