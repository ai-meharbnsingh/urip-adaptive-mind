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
from jose import JWTError, jwt, ExpiredSignatureError

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
        jose.JWTError  — signature invalid or token malformed
        jose.ExpiredSignatureError — token is expired
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
    except JWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid token: {exc}",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return claims
