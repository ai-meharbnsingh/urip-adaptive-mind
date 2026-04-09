import math

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from backend.middleware.rbac import role_required
from backend.models.audit_log import AuditLog
from backend.models.user import User

router = APIRouter()


@router.get("")
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

    # Batch-fetch related users to avoid N+1 queries
    user_ids = list(set(log.user_id for log in logs))
    user_result = await db.execute(select(User).where(User.id.in_(user_ids)))
    users_map = {u.id: u for u in user_result.scalars().all()}

    # Enrich with user name
    enriched = []
    for log in logs:
        user = users_map.get(log.user_id)

        enriched.append({
            "id": str(log.id),
            "user_id": str(log.user_id),
            "user_name": user.full_name if user else "Unknown",
            "user_role": user.role if user else "Unknown",
            "action": log.action,
            "resource_type": log.resource_type,
            "resource_id": str(log.resource_id) if log.resource_id else None,
            "details": log.details,
            "ip_address": log.ip_address,
            "created_at": log.created_at.isoformat(),
        })

    return {"items": enriched, "total": total, "page": page, "pages": pages}
