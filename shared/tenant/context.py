"""
shared.tenant.context — TenantContext contextvar

Provides per-request tenant isolation via Python contextvars.
Both the URIP backend and the Compliance service can import this.

The URIP backend's middleware/tenant.py re-exports from here so there is
a single canonical implementation. Services import from shared.tenant.context
directly; the URIP auth middleware calls TenantContext.set() on each request.

Usage:
    from shared.tenant.context import TenantContext

    # In auth middleware (set once per request):
    TenantContext.set(uuid.UUID(tenant_id_str))

    # In a handler or service (read):
    tenant_id = TenantContext.get()   # raises RuntimeError if not set
    tenant_id = TenantContext.get_or_none()  # returns None if not set
"""

import uuid
from contextvars import ContextVar

_tenant_id_var: ContextVar[uuid.UUID | None] = ContextVar("tenant_id", default=None)


class TenantContext:
    """
    Thread-safe, async-safe tenant identity carrier.

    Bound per request by the auth middleware; read by service layers.
    """

    @classmethod
    def set(cls, tenant_id: uuid.UUID) -> None:
        """Bind tenant_id to the current execution context (request/task)."""
        _tenant_id_var.set(tenant_id)

    @classmethod
    def get(cls) -> uuid.UUID:
        """
        Return the current tenant's UUID.

        Raises:
            RuntimeError: if no tenant context has been set (programming error —
                          the auth middleware must run before any DB query).
        """
        value = _tenant_id_var.get()
        if value is None:
            raise RuntimeError(
                "TenantContext.get() called before set() — "
                "ensure the auth middleware has run."
            )
        return value

    @classmethod
    def get_or_none(cls) -> uuid.UUID | None:
        """Return tenant_id or None if not set (e.g. super-admin without tenant scope)."""
        return _tenant_id_var.get()

    @classmethod
    def reset(cls) -> None:
        """Clear the tenant context (useful in tests)."""
        _tenant_id_var.set(None)
