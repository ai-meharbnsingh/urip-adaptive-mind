"""Per-resource scope checks. Layered ABOVE role_required (which stays
as the coarse hierarchy gate). A user must have BOTH:
  - their role >= the route's role_required floor, AND
  - the route's required scope present in their effective scopes.

Scope vocabulary (8 scopes):
  tenants:read    — list/read tenant records
  tenants:write   — create/patch/delete tenants
  modules:read    — list module subscriptions
  modules:write   — enable/disable/update module subscriptions
  scoring:write   — read or write scoring weights (sensitive — read is also gated)
  vapt:read       — list VAPT vendors and submissions
  vapt:write      — invite/revoke VAPT vendors, request retests
  settings:read   — read tenant settings (users, connectors, scoring config)
  settings:write  — write tenant settings (users, connectors, scoring weights)
"""

from fastapi import Depends, HTTPException, status

from backend.middleware.auth import get_current_user
from backend.models.user import User

# ---------------------------------------------------------------------------
# Effective scope map per role.
# ciso = superset; lower roles get less.
# ---------------------------------------------------------------------------
ROLE_SCOPES: dict[str, set[str]] = {
    "ciso": {
        "admin:*",
        "tenants:write",
        "tenants:read",
        "modules:write",
        "modules:read",
        "scoring:write",
        "vapt:write",
        "vapt:read",
        "settings:write",
        "settings:read",
    },
    "it_team": {
        "tenants:read",
        "modules:read",
        "scoring:write",
        "vapt:read",
        "settings:read",
    },
    "executive": {
        "tenants:read",
        "modules:read",
        "vapt:read",
        "settings:read",
    },
    "board": {
        "tenants:read",
    },
}


def _has(user_scopes: set[str], required: str) -> bool:
    """Return True if user_scopes satisfies the required scope."""
    if "admin:*" in user_scopes:
        return True
    return required in user_scopes


def require_scope(scope: str):
    """
    FastAPI dependency factory. Returns a dependency that enforces the named
    scope on the current user.

    Usage::

        @router.post("/foo")
        async def create_foo(
            _admin: User = Depends(role_required("ciso")),
            _scope: User = Depends(require_scope("tenants:write")),
        ):
            ...

    The scope check is ADDITIVE — it does not replace role_required.
    """
    async def _dep(current_user: User = Depends(get_current_user)) -> User:
        role = (getattr(current_user, "role", "") or "").lower()
        user_scopes = ROLE_SCOPES.get(role, set())
        if not _has(user_scopes, scope):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Missing required scope: {scope}",
            )
        return current_user

    return _dep
