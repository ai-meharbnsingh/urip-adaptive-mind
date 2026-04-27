import asyncio
import math
import secrets
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from backend.middleware.auth import get_current_user
from backend.middleware.rbac import role_required
from backend.middleware.tenant import TenantContext
from backend.models.audit_log import AuditLog
from backend.models.risk import Risk, RiskHistory
from backend.models.user import User
from backend.schemas.risk import AssignRequest, RiskCreate, RiskListResponse, RiskRead, RiskUpdate
from backend.services.exploitability_service import enrich_risk
from backend.services.sla_service import compute_sla_deadline
from backend.services.tenant_query import apply_tenant_filter
from backend.services.threat_intel_service import get_apt_for_cve
from backend.utils import parse_uuid

router = APIRouter()


def risk_to_read(r: Risk) -> RiskRead:
    apt_groups = get_apt_for_cve(r.cve_id) if r.cve_id else None
    return RiskRead(
        id=str(r.id),
        risk_id=r.risk_id,
        finding=r.finding,
        description=r.description,
        source=r.source,
        domain=r.domain,
        cvss_score=float(r.cvss_score),
        severity=r.severity,
        asset=r.asset,
        owner_team=r.owner_team,
        assigned_to=str(r.assigned_to) if r.assigned_to else None,
        status=r.status,
        sla_deadline=r.sla_deadline,
        jira_ticket=r.jira_ticket,
        cve_id=r.cve_id,
        epss_score=float(r.epss_score) if r.epss_score is not None else None,
        epss_percentile=float(r.epss_percentile) if r.epss_percentile is not None else None,
        in_kev_catalog=r.in_kev_catalog,
        exploit_status=r.exploit_status,
        asset_tier=r.asset_tier,
        composite_score=float(r.composite_score) if r.composite_score is not None else None,
        apt_groups=apt_groups if apt_groups else None,
        created_at=r.created_at,
        updated_at=r.updated_at,
    )


@router.get("", response_model=RiskListResponse)
async def list_risks(
    severity: str | None = Query(default=None),
    source: str | None = Query(default=None),
    domain: str | None = Query(default=None),
    status: str | None = Query(default=None),
    owner: str | None = Query(default=None),
    search: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=20, ge=1, le=100),
    sort_by: str = Query(default="composite_score"),
    order: str = Query(default="desc"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = select(Risk)
    count_query = select(func.count()).select_from(Risk)

    # Apply tenant isolation — only return risks belonging to the current tenant
    query = apply_tenant_filter(query, Risk)
    count_query = count_query.where(Risk.tenant_id == TenantContext.get())

    # Apply filters
    if severity:
        query = query.where(Risk.severity == severity.lower())
        count_query = count_query.where(Risk.severity == severity.lower())
    if source:
        query = query.where(Risk.source == source.lower())
        count_query = count_query.where(Risk.source == source.lower())
    if domain:
        query = query.where(Risk.domain == domain.lower())
        count_query = count_query.where(Risk.domain == domain.lower())
    if status:
        query = query.where(Risk.status == status.lower().replace("-", "_"))
        count_query = count_query.where(Risk.status == status.lower().replace("-", "_"))
    if owner:
        query = query.where(Risk.owner_team.ilike(f"%{owner}%"))
        count_query = count_query.where(Risk.owner_team.ilike(f"%{owner}%"))
    if search:
        search_filter = (
            Risk.finding.ilike(f"%{search}%")
            | Risk.risk_id.ilike(f"%{search}%")
            | Risk.asset.ilike(f"%{search}%")
        )
        query = query.where(search_filter)
        count_query = count_query.where(search_filter)

    # Sort
    sort_col = getattr(Risk, sort_by, Risk.cvss_score)
    if order == "desc":
        query = query.order_by(sort_col.desc())
    else:
        query = query.order_by(sort_col.asc())

    # Count
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0
    pages = math.ceil(total / per_page)

    # Paginate
    offset = (page - 1) * per_page
    query = query.offset(offset).limit(per_page)

    result = await db.execute(query)
    risks = result.scalars().all()

    return RiskListResponse(
        items=[risk_to_read(r) for r in risks],
        total=total,
        page=page,
        pages=pages,
    )


@router.get("/{risk_id}")
async def get_risk(
    risk_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # Scope by both risk_id string AND tenant_id — prevents cross-tenant ID fishing
    result = await db.execute(
        select(Risk).where(Risk.risk_id == risk_id, Risk.tenant_id == TenantContext.get())
    )
    risk = result.scalar_one_or_none()
    if not risk:
        raise HTTPException(status_code=404, detail="Risk not found")

    # Get history
    history_result = await db.execute(
        select(RiskHistory).where(RiskHistory.risk_id == risk.id).order_by(RiskHistory.created_at.desc())
    )
    history = history_result.scalars().all()

    return {
        "risk": risk_to_read(risk),
        "history": [
            {
                "field_changed": h.field_changed,
                "old_value": h.old_value,
                "new_value": h.new_value,
                "changed_by": str(h.changed_by),
                "created_at": h.created_at.isoformat(),
            }
            for h in history
        ],
    }


@router.post("", response_model=RiskRead)
async def create_risk(
    data: RiskCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(role_required("it_team")),
):
    # Generate unique risk_id using full year + random suffix.
    # Format: RISK-YYYY-XXXX (tenant-neutral; replaces the old RE- Royal Enfield prefix)
    now = datetime.now(timezone.utc)
    suffix = secrets.token_hex(2).upper()  # 4 hex chars
    risk_id = f"RISK-{now.strftime('%Y')}-{suffix}"

    sla_deadline = compute_sla_deadline(data.severity)

    risk = Risk(
        risk_id=risk_id,
        finding=data.finding,
        description=data.description,
        source=data.source.lower(),
        domain=data.domain.lower(),
        cvss_score=data.cvss_score,
        severity=data.severity.lower(),
        asset=data.asset,
        owner_team=data.owner_team,
        status="open",
        sla_deadline=sla_deadline,
        cve_id=data.cve_id,
        tenant_id=TenantContext.get(),  # stamp tenant on create
    )

    # Auto-classify asset tier
    from backend.services.asset_criticality_service import classify_asset
    risk.asset_tier = data.asset_tier if data.asset_tier else classify_asset(data.asset)

    # Apply exploitability fields if provided (e.g. from simulator)
    has_exploitability = data.composite_score is not None
    if has_exploitability:
        risk.epss_score = data.epss_score
        risk.in_kev_catalog = data.in_kev_catalog
        risk.exploit_status = data.exploit_status
        risk.composite_score = data.composite_score

    db.add(risk)

    # Audit log — stamped with the same tenant_id
    db.add(AuditLog(
        user_id=current_user.id,
        action="risk_created",
        resource_type="risk",
        resource_id=risk.id,
        details={"finding": data.finding, "severity": data.severity},
        tenant_id=TenantContext.get(),
    ))

    await db.commit()
    await db.refresh(risk)

    # If exploitability fields were not provided, fire async enrichment
    if not has_exploitability:
        asyncio.create_task(enrich_risk(risk.id, data.cve_id, data.cvss_score, data.severity.lower()))

    return risk_to_read(risk)


@router.patch("/{risk_id}", response_model=RiskRead)
async def update_risk(
    risk_id: str,
    data: RiskUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(role_required("it_team")),
):
    result = await db.execute(
        select(Risk).where(Risk.risk_id == risk_id, Risk.tenant_id == TenantContext.get())
    )
    risk = result.scalar_one_or_none()
    if not risk:
        raise HTTPException(status_code=404, detail="Risk not found")

    # Track changes
    for field in ["status", "owner_team", "jira_ticket"]:
        new_val = getattr(data, field, None)
        if new_val is not None:
            old_val = getattr(risk, field)
            if old_val != new_val:
                db.add(RiskHistory(
                    risk_id=risk.id,
                    field_changed=field,
                    old_value=str(old_val),
                    new_value=str(new_val),
                    changed_by=current_user.id,
                ))
                setattr(risk, field, new_val)

    if data.assigned_to is not None:
        old_assigned = str(risk.assigned_to) if risk.assigned_to else None
        risk.assigned_to = parse_uuid(data.assigned_to, "assigned_to") if data.assigned_to else None
        db.add(RiskHistory(
            risk_id=risk.id,
            field_changed="assigned_to",
            old_value=old_assigned,
            new_value=data.assigned_to,
            changed_by=current_user.id,
        ))

    db.add(AuditLog(
        user_id=current_user.id,
        action="risk_updated",
        resource_type="risk",
        resource_id=risk.id,
        details={"changes": data.model_dump(exclude_none=True)},
    ))

    await db.commit()
    await db.refresh(risk)
    return risk_to_read(risk)


@router.post("/{risk_id}/assign", response_model=RiskRead)
async def assign_risk(
    risk_id: str,
    data: AssignRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(role_required("it_team")),
):
    result = await db.execute(
        select(Risk).where(Risk.risk_id == risk_id, Risk.tenant_id == TenantContext.get())
    )
    risk = result.scalar_one_or_none()
    if not risk:
        raise HTTPException(status_code=404, detail="Risk not found")

    old_assigned = str(risk.assigned_to) if risk.assigned_to else None
    risk.assigned_to = parse_uuid(data.user_id, "user_id")

    db.add(RiskHistory(
        risk_id=risk.id,
        field_changed="assigned_to",
        old_value=old_assigned,
        new_value=data.user_id,
        changed_by=current_user.id,
    ))
    db.add(AuditLog(
        user_id=current_user.id,
        action="risk_assigned",
        resource_type="risk",
        resource_id=risk.id,
        details={"assigned_to": data.user_id},
    ))

    await db.commit()
    await db.refresh(risk)
    return risk_to_read(risk)
