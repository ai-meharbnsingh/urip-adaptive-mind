import math
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from backend.middleware.module_gate import require_module
from backend.middleware.rbac import role_required
from backend.middleware.tenant import TenantContext
from backend.models.audit_log import AuditLog
from backend.models.user import User
from backend.services.tenant_query import apply_tenant_filter

# CRIT-007 — audit log is a CORE platform feature; gate accordingly.
router = APIRouter(dependencies=[Depends(require_module("CORE"))])


class AuditLogEntry(BaseModel):
    id: str
    user_id: str
    user_name: str
    user_role: str
    action: str
    resource_type: str
    resource_id: str | None
    details: dict[str, Any] | None
    ip_address: str | None
    created_at: datetime


class AuditLogListResponse(BaseModel):
    items: list[AuditLogEntry]
    total: int
    page: int
    pages: int


@router.get("", response_model=AuditLogListResponse)
async def list_audit_logs(
    resource_type: str | None = Query(default=None),
    user_id: str | None = Query(default=None),
    action: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(role_required("it_team")),
):
    query = select(AuditLog)
    count_query = select(func.count()).select_from(AuditLog)

    # Apply tenant isolation — only return audit logs belonging to the current tenant
    query = apply_tenant_filter(query, AuditLog)
    count_query = count_query.where(AuditLog.tenant_id == TenantContext.get())

    if resource_type:
        query = query.where(AuditLog.resource_type == resource_type)
        count_query = count_query.where(AuditLog.resource_type == resource_type)
    if action:
        query = query.where(AuditLog.action == action)
        count_query = count_query.where(AuditLog.action == action)

    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0
    pages = math.ceil(total / per_page)

    query = query.order_by(AuditLog.created_at.desc())
    query = query.offset((page - 1) * per_page).limit(per_page)

    result = await db.execute(query)
    logs = result.scalars().all()

    # L4 (CL-NEW-4) — audit_logs.user_id is nullable for system-level rows
    # such as `login_attempt` rows for unknown email addresses.  Filter out
    # NULLs before the IN(...) lookup.
    #
    # L12 (Codex LOW-003) — defensive tenant filter on the user join.  Even
    # if a corrupted audit row references a user_id from another tenant,
    # the enrichment never loads the foreign user row.
    non_null_user_ids = [log.user_id for log in logs if log.user_id is not None]
    users_map: dict = {}
    if non_null_user_ids:
        user_query = select(User).where(User.id.in_(set(non_null_user_ids)))
        caller_tenant_id = TenantContext.get_or_none()
        if caller_tenant_id is not None and hasattr(User, "tenant_id"):
            user_query = user_query.where(User.tenant_id == caller_tenant_id)
        user_result = await db.execute(user_query)
        users_map = {u.id: u for u in user_result.scalars().all()}

    # Enrich with user name.  Login-attempt rows with NULL user_id render
    # as "(failed login)" so the operator can still see the row.
    enriched: list[AuditLogEntry] = []
    for log in logs:
        if log.user_id is None:
            user_id_str = ""
            display_name = "(failed login)" if log.action == "login_attempt" else "(system)"
            display_role = "system"
        else:
            user = users_map.get(log.user_id)
            # Tenant-scoped audit log: drop rows whose user cannot be resolved
            # inside the caller's tenant (prevents cross-tenant identity leakage).
            if user is None:
                continue
            user_id_str = str(log.user_id)
            display_name = user.full_name
            display_role = user.role

        enriched.append(AuditLogEntry(
            id=str(log.id),
            user_id=user_id_str,
            user_name=display_name,
            user_role=display_role,
            action=log.action,
            resource_type=log.resource_type,
            resource_id=str(log.resource_id) if log.resource_id else None,
            details=log.details,
            ip_address=log.ip_address,
            created_at=log.created_at,
        ))

    return AuditLogListResponse(items=enriched, total=total, page=page, pages=pages)
