"""
VAPT vendor JWT verification middleware — P33a (URIP_Blueprint v3 §6.5).

Mirrors the auditor middleware (compliance_backend.middleware.auditor_auth) with
URIP-specific knobs:

  - VAPT vendor JWTs are signed with backend.config.JWT_SECRET_KEY (not the
    Compliance secret) — these are URIP-issued tokens.
  - JWT carries: vendor_id, tenant_id, type='vapt_vendor', exp,
                 iss='urip', aud='urip-vapt-vendor'
  - Two-layer security:
      1. JWT layer: signature, algorithm pin, iss / aud, exp
      2. DB layer:  VaptVendor row exists AND status='active' AND
                    vendor.tenant_id matches the JWT claim
  - Activity log entry is written by callers via log_vapt_vendor_action()
    for every action the vendor takes (so admin can see "vendor X uploaded
    finding Y on date Z").

The dependency raises 401 with a stable detail message — we deliberately do
NOT reveal the failure cause (expired vs revoked vs unknown) to avoid handing
brute-force attackers a useful oracle.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Optional

import jwt as pyjwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from backend.middleware.tenant import TenantContext
from backend.models.audit_log import AuditLog
from backend.services.vapt_vendor_service import (
    VAPT_JWT_TYPE,
    VaptVendorService,
)

bearer_scheme = HTTPBearer(auto_error=False)


@dataclass
class VaptVendorContext:
    """Value object passed to handlers; small + immutable."""
    vendor_id: uuid.UUID
    tenant_id: uuid.UUID
    contact_email: str


async def require_vapt_vendor(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> VaptVendorContext:
    """
    FastAPI dependency for /api/vapt-vendor/* routes.

    Order of checks:
      1. Bearer header present
      2. JWT decodes (signature, alg pin, iss, aud, exp)
      3. claims["type"] == "vapt_vendor"
      4. vendor row exists in DB and is active
      5. JWT tenant_id matches DB tenant_id (defence in depth)

    Side effect: binds tenant_id to TenantContext so any downstream
    tenant-scoped query helpers work transparently.
    """
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Authorization header",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Decode via the service (which knows our iss/aud/secret)
    svc = VaptVendorService(db=db)
    try:
        claims = svc.decode_vendor_jwt(credentials.credentials)
    except pyjwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="VAPT vendor token expired.",
        )
    except pyjwt.PyJWTError:
        # PyJWT umbrella — signature, alg-mismatch, malformed, missing claim
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid VAPT vendor token.",
        )

    if claims.get("type") != VAPT_JWT_TYPE:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token is not a VAPT vendor token.",
        )

    vendor_id_str = claims.get("vendor_id")
    tenant_id_str = claims.get("tenant_id")
    if not vendor_id_str or not tenant_id_str:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token missing vendor_id or tenant_id claim.",
        )

    try:
        vendor_id = uuid.UUID(vendor_id_str)
        tenant_id = uuid.UUID(tenant_id_str)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token contains malformed UUID claim.",
        )

    vendor = await svc.get_active_vendor_by_id(vendor_id)
    if vendor is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="VAPT vendor revoked or unknown.",
        )

    # Defence in depth: token tenant must match DB tenant
    if vendor.tenant_id != tenant_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token tenant mismatch.",
        )

    # Bind tenant context for downstream code (tenant-scoped queries etc.)
    TenantContext.set(tenant_id)

    return VaptVendorContext(
        vendor_id=vendor.id,
        tenant_id=vendor.tenant_id,
        contact_email=vendor.contact_email,
    )


# ---------------------------------------------------------------------------
#  Activity logging helper
# ---------------------------------------------------------------------------

async def log_vapt_vendor_action(
    db: AsyncSession,
    vendor: VaptVendorContext,
    *,
    action: str,
    target_type: Optional[str] = None,
    target_id: Optional[uuid.UUID] = None,
    request: Optional[Request] = None,
    extra_details: Optional[dict] = None,
) -> AuditLog:
    """
    Append an audit-log row for a VAPT vendor action.

    user_id is None (the vendor is NOT a User). Resource is recorded so the
    admin trail shows exactly what the vendor touched. Caller commits.
    """
    ip = None
    if request is not None and request.client is not None:
        ip = request.client.host

    details: dict = {
        "vendor_id": str(vendor.vendor_id),
        "vendor_email": vendor.contact_email,
    }
    if extra_details:
        details.update(extra_details)

    log = AuditLog(
        user_id=None,
        action=action,
        resource_type=target_type or "vapt_vendor_action",
        resource_id=target_id,
        details=details,
        ip_address=ip,
        tenant_id=vendor.tenant_id,
    )
    db.add(log)
    await db.flush()
    return log
