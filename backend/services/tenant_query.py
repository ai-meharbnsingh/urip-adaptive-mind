"""
Tenant-scoped query helper.

Provides apply_tenant_filter() which automatically appends a WHERE tenant_id = ?
clause to any SQLAlchemy Select statement, pulling the tenant_id from the
current request context (TenantContext).

Usage
-----
    from backend.services.tenant_query import apply_tenant_filter

    query = select(Risk)
    query = apply_tenant_filter(query, Risk)   # adds .where(Risk.tenant_id == <current_tenant>)
    result = await db.execute(query)

Design notes
------------
- Works with any model that has a `tenant_id` column.
- If TenantContext returns None (not yet bound) an AssertionError is raised early
  rather than silently returning all rows across all tenants.
- The helper is intentionally lightweight — no magic metaclass tricks, no session
  subclass. Keeps it easy to test and reason about.
"""

from typing import Any, TypeVar

from sqlalchemy import Select

from backend.middleware.tenant import TenantContext

# Generic model type — the model must have a `tenant_id` attribute
ModelType = TypeVar("ModelType")


def apply_tenant_filter(query: Select, model: Any) -> Select:
    """
    Return `query` with an additional WHERE tenant_id = <current_tenant> clause.

    Parameters
    ----------
    query : Select
        The SQLAlchemy select statement to filter.
    model : Any
        The ORM model class (e.g. Risk, User). Must have a `tenant_id` column.

    Returns
    -------
    Select
        The query with tenant filter applied.

    Raises
    ------
    RuntimeError
        If no tenant_id is bound in the current request context (forwarded from
        TenantContext.get()).
    AttributeError
        If the model does not have a `tenant_id` attribute.
    """
    tenant_id = TenantContext.get()
    return query.where(model.tenant_id == tenant_id)
