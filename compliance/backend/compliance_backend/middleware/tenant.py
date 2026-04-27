"""
Tenant context middleware for the Compliance Service.

Extracts tenant_id from JWT claims (set by require_auth) and binds it to a
contextvars.ContextVar so any downstream service function can access it without
threading the request object everywhere.

Pattern mirrors URIP's tenant middleware in backend/middleware/tenant.py
(Track A is building that). Compliance keeps its own copy to remain standalone-deployable.

Usage in a route:
    from compliance_backend.middleware.tenant import get_tenant_id, require_tenant

    @router.get("/my-resource")
    async def handler(
        tenant_id: str = Depends(require_tenant),
    ):
        # tenant_id guaranteed present and verified
        ...

Or anywhere in the call stack:
    from compliance_backend.middleware.tenant import current_tenant_id
    tid = current_tenant_id.get()  # may be None if called outside request context
"""
from contextvars import ContextVar
from typing import Optional

from fastapi import Depends, HTTPException, status

from compliance_backend.middleware.auth import require_auth


# Module-level ContextVar — set per request in require_tenant dependency
current_tenant_id: ContextVar[Optional[str]] = ContextVar(
    "compliance_current_tenant_id", default=None
)


async def require_tenant(
    claims: dict = Depends(require_auth),
) -> str:
    """
    FastAPI dependency — extracts tenant_id from verified JWT claims.

    Call chain:  bearer_scheme → require_auth → require_tenant

    Returns:
        tenant_id string (guaranteed non-empty)

    Raises:
        401 if tenant_id is missing from claims (malformed token)
    """
    tenant_id: Optional[str] = claims.get("tenant_id")
    if not tenant_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="token missing tenant_id claim",
        )
    current_tenant_id.set(tenant_id)
    return tenant_id


def get_tenant_id() -> Optional[str]:
    """
    Utility helper — returns tenant_id from current context.
    Returns None if called outside an authenticated request context.
    """
    return current_tenant_id.get()
