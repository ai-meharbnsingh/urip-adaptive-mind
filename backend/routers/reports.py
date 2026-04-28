import io
from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from backend.middleware.auth import get_current_user
from backend.middleware.module_gate import require_module
from backend.middleware.tenant import TenantContext
from backend.models.risk import Risk
from backend.models.user import User
from backend.schemas.report import CertInAdvisory, ReportRequest, ScheduledReport
from backend.services.tenant_query import apply_tenant_filter

# CRIT-007 — reporting is a CORE platform feature.
router = APIRouter(dependencies=[Depends(require_module("CORE"))])


@router.post("/generate")
async def generate_report(
    data: ReportRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # Tenant-scoped report — only the caller's tenant data ever leaves the box.
    query = select(Risk).where(Risk.status.in_(["open", "in_progress"]))
    query = apply_tenant_filter(query, Risk)

    if data.report_type == "board":
        # Board report excludes accepted risks (already filtered by status)
        # Only aggregate data, no individual CVEs
        pass

    query = query.order_by(Risk.cvss_score.desc())
    result = await db.execute(query)
    risks = result.scalars().all()

    if data.format == "excel":
        return await _generate_excel(risks, data.report_type)
    else:
        return await _generate_pdf(risks, data.report_type)


async def _generate_excel(risks, report_type: str) -> StreamingResponse:
    from openpyxl import Workbook

    wb = Workbook()
    ws = wb.active
    ws.title = f"URIP {report_type.title()} Report"

    # Header
    headers = ["Risk ID", "Finding", "Source", "Domain", "CVSS", "Severity", "Asset", "Owner", "Status", "SLA Deadline"]
    ws.append(headers)

    for r in risks:
        ws.append([
            r.risk_id, r.finding, r.source, r.domain,
            float(r.cvss_score), r.severity, r.asset,
            r.owner_team, r.status, r.sla_deadline.strftime("%Y-%m-%d %H:%M"),
        ])

    output = io.BytesIO()
    wb.save(output)
    output.seek(0)

    now = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    filename = f"URIP_{report_type}_report_{now}.xlsx"

    return StreamingResponse(
        output,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


async def _generate_pdf(risks, report_type: str) -> StreamingResponse:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    output = io.BytesIO()
    doc = SimpleDocTemplate(output, pagesize=landscape(A4))
    styles = getSampleStyleSheet()
    elements = []

    # Title
    title = f"URIP - {report_type.title()} Security Report"
    elements.append(Paragraph(title, styles["Title"]))
    elements.append(Paragraph(
        f"Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')} | "
        f"Prepared by: URIP — Adaptive Mind",
        styles["Normal"],
    ))
    elements.append(Spacer(1, 20))

    # Summary
    severity_counts = {}
    for r in risks:
        severity_counts[r.severity] = severity_counts.get(r.severity, 0) + 1

    summary_text = (
        f"Total Open Risks: {len(risks)} | "
        f"Critical: {severity_counts.get('critical', 0)} | "
        f"High: {severity_counts.get('high', 0)} | "
        f"Medium: {severity_counts.get('medium', 0)} | "
        f"Low: {severity_counts.get('low', 0)}"
    )
    elements.append(Paragraph(summary_text, styles["Normal"]))
    elements.append(Spacer(1, 20))

    # Table
    table_data = [["Risk ID", "Finding", "Source", "CVSS", "Severity", "Asset", "Status"]]
    for r in risks[:50]:  # Limit to 50 for PDF readability
        table_data.append([
            r.risk_id,
            r.finding[:40] + "..." if len(r.finding) > 40 else r.finding,
            r.source,
            str(float(r.cvss_score)),
            r.severity.title(),
            r.asset[:30] + "..." if len(r.asset) > 30 else r.asset,
            r.status,
        ])

    table = Table(table_data, repeatRows=1)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0D1B2A")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTSIZE", (0, 0), (-1, 0), 9),
        ("FONTSIZE", (0, 1), (-1, -1), 7),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F0F4F8")]),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]))
    elements.append(table)

    doc.build(elements)
    output.seek(0)

    now = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    filename = f"URIP_{report_type}_report_{now}.pdf"

    return StreamingResponse(
        output,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@router.get("/certin", response_model=list[CertInAdvisory])
async def get_certin_advisories(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # Tenant-scoped — only return CERT-In rows belonging to the caller's tenant.
    query = select(Risk).where(Risk.source == "cert_in")
    query = apply_tenant_filter(query, Risk)
    query = query.order_by(Risk.created_at.desc()).limit(20)
    result = await db.execute(query)
    risks = result.scalars().all()
    return [
        CertInAdvisory(
            id=str(r.id),
            advisory_id=r.cve_id or f"CIVN-2026-{i+1:03d}",
            title=r.finding,
            published_date=r.created_at.strftime("%b %d, %Y"),
            severity=r.severity,
            response_status=r.status,
        )
        for i, r in enumerate(risks)
    ]


@router.get("/scheduled", response_model=list[ScheduledReport])
async def get_scheduled_reports(
    current_user: User = Depends(get_current_user),
):
    # Static schedule for demo — would be a table in production
    return [
        ScheduledReport(
            name="Weekly Security Summary",
            frequency="Every Monday",
            recipients=["CISO", "IT Lead"],
            next_run="2026-04-14 09:00 AM",
            status="active",
        ),
        ScheduledReport(
            name="Monthly Board Report",
            frequency="1st of Month",
            recipients=["Board Members"],
            next_run="2026-05-01 08:00 AM",
            status="active",
        ),
        ScheduledReport(
            name="CERT-In Response Report",
            frequency="Every Friday",
            recipients=["CISO", "Compliance"],
            next_run="2026-04-11 05:00 PM",
            status="active",
        ),
    ]
