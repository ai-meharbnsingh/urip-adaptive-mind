"""
Module gate decorator — restrict route access to tenants with an active module subscription.

Usage
-----
    from backend.middleware.module_gate import require_module, require_any_module

    @router.get("/vm/assets")
    async def vm_assets(
        _: User = Depends(require_module("VM")),
        db: AsyncSession = Depends(get_db),
    ):
        ...

    @router.get("/threat-intel/pulses")
    async def pulses(
        _: User = Depends(require_any_module(["VM", "EDR", "NETWORK"])),
        db: AsyncSession = Depends(get_db),
    ):
        ...

Behaviour
---------
- Returns 403 if the current tenant does NOT have ANY of the listed modules
  enabled (and within the subscription expires_at, see HIGH-007 below).
- Super-admins (is_super_admin=True in JWT) bypass the gate — they always pass.
- If tenant context is not set (unauthenticated path), the gate raises 401.
- Only rows with is_enabled=True AND (expires_at IS NULL OR expires_at > now())
  count as "active".  This was added in HIGH-007 — previously expires_at was
  ignored in the gate.
"""

from datetime import datetime, timezone
from typing import Callable, Iterable

from fastapi import Depends, HTTPException, status
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from backend.middleware.auth import get_current_user
from backend.middleware.tenant import TenantContext
from backend.models.subscription import TenantSubscription
from backend.models.user import User


def _active_subscription_filter(now: datetime):
    """SQLAlchemy boolean expr for: is_enabled AND (expires_at IS NULL OR > now)."""
    return (
        TenantSubscription.is_enabled.is_(True)
        & or_(
            TenantSubscription.expires_at.is_(None),
            TenantSubscription.expires_at > now,
        )
    )


def require_module(module_code: str) -> Callable:
    """
    FastAPI dependency factory — require a single module to be active.

    Returns a dependency that:
    1. Resolves the authenticated user (via get_current_user).
    2. Skips the gate for super_admin users.
    3. Looks up the tenant's subscription for `module_code`.
    4. Raises 403 if no active subscription found OR subscription expired.

    Parameters
    ----------
    module_code : str
        One of: CORE, VM, EDR, NETWORK, IDENTITY, COLLAB, ITSM, DAST, DLP, COMPLIANCE
    """

    async def _gate(
        current_user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db),
    ) -> User:
        # Super-admins bypass all module gates
        if current_user.is_super_admin:
            return current_user

        try:
            tenant_id = TenantContext.get()
        except RuntimeError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Tenant context not established",
            )

        now = datetime.now(timezone.utc)
        result = await db.execute(
            select(TenantSubscription).where(
                TenantSubscription.tenant_id == tenant_id,
                TenantSubscription.module_code == module_code,
                _active_subscription_filter(now),
            )
        )
        subscription = result.scalar_one_or_none()
        if subscription is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Module '{module_code}' is not enabled for this tenant. "
                       "Contact your administrator to enable this module.",
            )
        return current_user

    return _gate


def require_any_module(module_codes: Iterable[str]) -> Callable:
    """
    FastAPI dependency factory — require at least ONE of `module_codes` to be active.

    Used by endpoints whose data is exposed by any of several upstream modules
    (e.g. threat-intel feeds matter to VM, EDR and NETWORK customers).

    Parameters
    ----------
    module_codes : iterable of str
        e.g. ["VM", "EDR", "NETWORK"]

    Behaviour
    ---------
    - Super-admins bypass.
    - 403 if NONE of the listed modules are active (is_enabled + not expired).
    """
    codes = list(module_codes)
    if not codes:
        raise ValueError("require_any_module requires a non-empty list of module codes")

    async def _gate(
        current_user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db),
    ) -> User:
        if current_user.is_super_admin:
            return current_user

        try:
            tenant_id = TenantContext.get()
        except RuntimeError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Tenant context not established",
            )

        now = datetime.now(timezone.utc)
        result = await db.execute(
            select(TenantSubscription).where(
                TenantSubscription.tenant_id == tenant_id,
                TenantSubscription.module_code.in_(codes),
                _active_subscription_filter(now),
            ).limit(1)
        )
        subscription = result.scalar_one_or_none()
        if subscription is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=(
                    f"This endpoint requires at least one of the following modules: "
                    f"{', '.join(codes)}. None are enabled for this tenant."
                ),
            )
        return current_user

    return _gate
