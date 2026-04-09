from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from backend.middleware.auth import get_current_user
from backend.models.risk import Risk
from backend.models.user import User
from backend.schemas.dashboard import AlertItem, ChartData, DashboardKPIs, TrendData, TrendDataset

router = APIRouter()


@router.get("/kpis", response_model=DashboardKPIs)
async def get_kpis(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    now = datetime.now(timezone.utc)

    # Total open (non-accepted, non-closed)
    total_q = await db.execute(
        select(func.count()).where(Risk.status.in_(["open", "in_progress"]))
    )
    total_open = total_q.scalar() or 0

    # By severity (open + in_progress only)
    severity_counts = {}
    for sev in ["critical", "high", "medium", "low"]:
        q = await db.execute(
            select(func.count()).where(Risk.severity == sev, Risk.status.in_(["open", "in_progress"]))
        )
        severity_counts[sev] = q.scalar() or 0

    # Accepted count
    accepted_q = await db.execute(select(func.count()).where(Risk.status == "accepted"))
    accepted = accepted_q.scalar() or 0

    # SLA breaching (deadline passed, still open/in_progress)
    breach_q = await db.execute(
        select(Risk).where(
            Risk.sla_deadline < now,
            Risk.status.in_(["open", "in_progress"]),
        ).order_by(Risk.cvss_score.desc()).limit(10)
    )
    breaching = breach_q.scalars().all()
    sla_list = [
        {
            "risk_id": r.risk_id,
            "finding": r.finding,
            "severity": r.severity,
            "sla_deadline": r.sla_deadline.isoformat(),
        }
        for r in breaching
    ]

    return DashboardKPIs(
        total_open=total_open,
        critical=severity_counts["critical"],
        high=severity_counts["high"],
        medium=severity_counts["medium"],
        low=severity_counts["low"],
        accepted=accepted,
        sla_breaching=sla_list,
    )


@router.get("/charts/by-domain", response_model=ChartData)
async def charts_by_domain(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Risk.domain, func.count())
        .where(Risk.status.in_(["open", "in_progress"]))
        .group_by(Risk.domain)
        .order_by(func.count().desc())
    )
    rows = result.all()
    return ChartData(
        labels=[r[0].capitalize() for r in rows],
        data=[r[1] for r in rows],
    )


@router.get("/charts/by-source", response_model=ChartData)
async def charts_by_source(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Risk.source, func.count())
        .where(Risk.status.in_(["open", "in_progress"]))
        .group_by(Risk.source)
        .order_by(func.count().desc())
    )
    rows = result.all()
    source_labels = {
        "crowdstrike": "CrowdStrike",
        "easm": "EASM",
        "cnapp": "CNAPP",
        "armis": "Armis",
        "vapt": "VAPT",
        "threat_intel": "Threat Intel",
        "cert_in": "CERT-In",
        "bug_bounty": "Bug Bounty",
        "soc": "SoC",
    }
    return ChartData(
        labels=[source_labels.get(r[0], r[0]) for r in rows],
        data=[r[1] for r in rows],
    )


@router.get("/charts/trend", response_model=TrendData)
async def charts_trend(
    months: int = Query(default=6, ge=1, le=12),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # Generate trend data from actual risk creation dates
    now = datetime.now(timezone.utc)
    labels = []
    critical_data = []
    high_data = []
    medium_data = []
    total_data = []

    month_names = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

    for i in range(months - 1, -1, -1):
        month = now.month - i
        year = now.year
        while month <= 0:
            month += 12
            year -= 1
        labels.append(month_names[month - 1])

        for sev, data_list in [("critical", critical_data), ("high", high_data), ("medium", medium_data)]:
            q = await db.execute(
                select(func.count()).where(
                    Risk.severity == sev,
                    Risk.status.in_(["open", "in_progress"]),
                    func.extract("month", Risk.created_at) == month,
                    func.extract("year", Risk.created_at) == year,
                )
            )
            data_list.append(q.scalar() or 0)

        q = await db.execute(
            select(func.count()).where(
                Risk.status.in_(["open", "in_progress"]),
                func.extract("month", Risk.created_at) == month,
                func.extract("year", Risk.created_at) == year,
            )
        )
        total_data.append(q.scalar() or 0)

    return TrendData(
        labels=labels,
        datasets=[
            TrendDataset(label="Critical", data=critical_data),
            TrendDataset(label="High", data=high_data),
            TrendDataset(label="Medium", data=medium_data),
            TrendDataset(label="Total", data=total_data),
        ],
    )


@router.get("/alerts")
async def get_alerts(
    limit: int = Query(default=5, ge=1, le=20),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Risk)
        .where(Risk.status.in_(["open", "in_progress"]), Risk.severity.in_(["critical", "high"]))
        .order_by(Risk.cvss_score.desc())
        .limit(limit)
    )
    risks = result.scalars().all()
    return [
        AlertItem(
            id=str(r.id),
            risk_id=r.risk_id,
            finding=r.finding,
            source=r.source,
            cvss_score=float(r.cvss_score),
            severity=r.severity,
            status=r.status,
            asset=r.asset,
        )
        for r in risks
    ]
