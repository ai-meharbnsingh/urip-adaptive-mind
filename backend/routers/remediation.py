import math
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from backend.middleware.auth import get_current_user
from backend.middleware.rbac import role_required
from backend.models.audit_log import AuditLog
from backend.models.remediation import RemediationTask
from backend.models.risk import Risk
from backend.models.user import User
from backend.schemas.remediation import RemediationCreate, RemediationRead, RemediationUpdate
from backend.utils import parse_uuid

router = APIRouter()


def task_to_read(t: RemediationTask) -> RemediationRead:
    return RemediationRead(
        id=str(t.id),
        risk_id=str(t.risk_id),
        title=t.title,
        description=t.description,
        assigned_to=str(t.assigned_to) if t.assigned_to else None,
        status=t.status,
        priority=t.priority,
        due_date=t.due_date,
        jira_key=t.jira_key,
        completed_at=t.completed_at,
        created_at=t.created_at,
    )


@router.get("")
async def list_remediation_tasks(
    status: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = select(RemediationTask)
    count_query = select(func.count()).select_from(RemediationTask)

    if status:
        query = query.where(RemediationTask.status == status)
        count_query = count_query.where(RemediationTask.status == status)

    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0
    pages = math.ceil(total / per_page)

    query = query.order_by(RemediationTask.created_at.desc())
    query = query.offset((page - 1) * per_page).limit(per_page)

    result = await db.execute(query)
    tasks = result.scalars().all()

    # Batch-fetch related risks to avoid N+1 queries
    risk_ids = [t.risk_id for t in tasks]
    risk_result = await db.execute(select(Risk).where(Risk.id.in_(risk_ids)))
    risks_map = {r.id: r for r in risk_result.scalars().all()}

    # Enrich with risk details
    enriched = []
    for t in tasks:
        risk = risks_map.get(t.risk_id)

        enriched.append({
            **task_to_read(t).model_dump(),
            "risk_detail": {
                "risk_id": risk.risk_id,
                "finding": risk.finding,
                "severity": risk.severity,
                "asset": risk.asset,
                "sla_deadline": risk.sla_deadline.isoformat(),
            } if risk else None,
        })

    return {"items": enriched, "total": total, "page": page, "pages": pages}


@router.post("", response_model=RemediationRead)
async def create_remediation_task(
    data: RemediationCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(role_required("it_team")),
):
    risk_result = await db.execute(select(Risk).where(Risk.risk_id == data.risk_id))
    risk = risk_result.scalar_one_or_none()
    if not risk:
        raise HTTPException(status_code=404, detail="Risk not found")

    task = RemediationTask(
        risk_id=risk.id,
        title=data.title,
        description=data.description,
        assigned_to=parse_uuid(data.assigned_to, "assigned_to") if data.assigned_to else None,
        priority=data.priority,
        due_date=data.due_date,
        jira_key=data.jira_key,
    )
    db.add(task)

    db.add(AuditLog(
        user_id=current_user.id,
        action="remediation_created",
        resource_type="remediation",
        resource_id=task.id,
        details={"risk_id": data.risk_id, "title": data.title},
    ))

    await db.commit()
    await db.refresh(task)
    return task_to_read(task)


@router.patch("/{task_id}", response_model=RemediationRead)
async def update_remediation_task(
    task_id: str,
    data: RemediationUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(role_required("it_team")),
):
    result = await db.execute(
        select(RemediationTask).where(RemediationTask.id == parse_uuid(task_id, "task_id"))
    )
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="Remediation task not found")

    if data.status is not None:
        task.status = data.status
        if data.status in ("completed", "verified"):
            task.completed_at = datetime.now(timezone.utc)
    if data.assigned_to is not None:
        task.assigned_to = parse_uuid(data.assigned_to, "assigned_to") if data.assigned_to else None
    if data.jira_key is not None:
        task.jira_key = data.jira_key
    if data.due_date is not None:
        task.due_date = data.due_date

    db.add(AuditLog(
        user_id=current_user.id,
        action="remediation_updated",
        resource_type="remediation",
        resource_id=task.id,
        details=data.model_dump(exclude_none=True),
    ))

    await db.commit()
    await db.refresh(task)
    return task_to_read(task)
