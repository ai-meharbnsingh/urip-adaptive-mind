"""
Tenant context propagation using Python contextvars.

The tenant_id is extracted from the JWT by get_current_user() in auth.py
and bound to a request-scoped contextvar.  Any code running within the same
async task can then call TenantContext.get() to retrieve the current tenant.

This approach works correctly with async FastAPI because each request runs in
its own asyncio task, so contextvar values are isolated per request.

Usage
-----
Write side (done in get_current_user):
    TenantContext.set(uuid.UUID(tenant_id_str))

Read side (used by routers / services / query helpers):
    tid = TenantContext.get()           # raises if not set
    tid = TenantContext.get_or_none()   # returns None if not set (legacy paths)
"""

import uuid
from contextvars import ContextVar

# The raw ContextVar — exposed for test introspection
_tenant_id_var: ContextVar[uuid.UUID | None] = ContextVar("tenant_id", default=None)


class TenantContext:
    """Thin helper wrapping the ContextVar with clear read/write semantics."""

    @staticmethod
    def set(tenant_id: uuid.UUID) -> None:
        """Bind tenant_id to the current async context (called once per request)."""
        _tenant_id_var.set(tenant_id)

    @staticmethod
    def get() -> uuid.UUID:
        """
        Return the tenant_id for the current request.

        Raises RuntimeError if called outside a properly authenticated request context.
        """
        value = _tenant_id_var.get(None)
        if value is None:
            raise RuntimeError(
                "TenantContext.get() called but no tenant has been bound. "
                "Ensure get_current_user() has run before calling tenant-scoped code."
            )
        return value

    @staticmethod
    def get_or_none() -> uuid.UUID | None:
        """Return the tenant_id, or None if not set (useful in health-check / public routes)."""
        return _tenant_id_var.get(None)
