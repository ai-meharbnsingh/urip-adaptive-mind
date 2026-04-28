"""
SOC 2 Management Report.

Sections (per AICPA Trust Services Criteria 2017 / TSC 2022 Revision):
  1. Cover page (org, period, framework version)
  2. Executive summary (overall compliance %)
  3. Trust Services Criteria coverage table
        (CC1, CC2, CC3, CC4, CC5, CC6, CC7, CC8, CC9, A1, PI1, C1,
         P1, P2, P3, P4, P5, P6, P7, P8)
  4. Control gap analysis
  5. Remediation roadmap
  6. Auditor sign-off page

Context shape:
    {
        "org_name": str,
        "period_start": date, "period_end": date,
        "framework_version": str,
        "report_date": date, "auditor_name": str,
        "overall_compliance_pct": float,
        "tsc_coverage": [
            {"category": "CC1", "title": "...", "status": "Pass|Partial|Fail",
             "controls_count": int, "controls_passed": int}, ...
        ],
        "control_gaps": [
            {"control_code": str, "description": str, "severity": "low|medium|high|critical"}, ...
        ],
        "remediation_roadmap": [
            {"item": str, "owner": str, "due": str|date}, ...
        ],
    }
"""
from __future__ import annotations

from typing import Any, Dict, List

from reportlab.lib.units import cm
from reportlab.platypus import Paragraph, Spacer

from compliance_backend.services.reports.base import (
    SHARED_STYLES,
    ReportTemplateBase,
    _esc,
    _fmt_date,
)


# Default TSC categories (used when no rows are supplied so the report still
# shows the framework structure).
DEFAULT_TSC_CATEGORIES: List[Dict[str, str]] = [
    {"category": "CC1", "title": "Control Environment"},
    {"category": "CC2", "title": "Communication & Information"},
    {"category": "CC3", "title": "Risk Assessment"},
    {"category": "CC4", "title": "Monitoring Activities"},
    {"category": "CC5", "title": "Control Activities"},
    {"category": "CC6", "title": "Logical & Physical Access Controls"},
    {"category": "CC7", "title": "System Operations"},
    {"category": "CC8", "title": "Change Management"},
    {"category": "CC9", "title": "Risk Mitigation"},
    {"category": "A1", "title": "Availability"},
    {"category": "PI1", "title": "Processing Integrity"},
    {"category": "C1", "title": "Confidentiality"},
    {"category": "P1", "title": "Privacy — Notice"},
    {"category": "P2", "title": "Privacy — Choice & Consent"},
    {"category": "P3", "title": "Privacy — Collection"},
    {"category": "P4", "title": "Privacy — Use, Retention & Disposal"},
    {"category": "P5", "title": "Privacy — Access"},
    {"category": "P6", "title": "Privacy — Disclosure to 3rd Parties"},
    {"category": "P7", "title": "Privacy — Quality"},
    {"category": "P8", "title": "Privacy — Monitoring & Enforcement"},
]


class Soc2ManagementReport(ReportTemplateBase):
    FRAMEWORK_SHORT_CODE = "SOC2"
    REPORT_TITLE = "SOC 2 Management Report"
    REPORT_SUBTITLE = "Type II — Trust Services Criteria Coverage"

    # ─────────────────────────────────────────────────────────────────────
    # HTML
    # ─────────────────────────────────────────────────────────────────────

    def render_html(self, ctx: Dict[str, Any]) -> str:
        tsc_rows = ctx.get("tsc_coverage") or DEFAULT_TSC_CATEGORIES
        gaps = ctx.get("control_gaps") or []
        roadmap = ctx.get("remediation_roadmap") or []
        overall_pct = ctx.get("overall_compliance_pct", 0.0)
        auditor = ctx.get("auditor_name", "")

        # Executive summary
        body = ['<h2>1. Executive Summary</h2>']
        body.append(
            f'<p>Overall compliance for the reporting period: '
            f'<strong>{_esc(f"{overall_pct:.1f}%")}</strong>.</p>'
        )

        # Trust Services Criteria coverage table
        body.append('<h2>2. Trust Services Criteria (TSC) Coverage</h2>')
        body.append(
            "<p>The following table summarises coverage for each Trust "
            "Services Category (CC1–CC9, A1, PI1, C1, P1–P8).</p>"
        )
        body.append(
            "<table><thead><tr>"
            "<th>Category</th><th>Title</th><th>Controls</th>"
            "<th>Passed</th><th>Status</th></tr></thead><tbody>"
        )
        for r in tsc_rows:
            status = r.get("status", "Pass")
            cls = {
                "Pass": "pass",
                "Partial": "partial",
                "Fail": "fail",
            }.get(status, "")
            body.append(
                "<tr>"
                f"<td>{_esc(r.get('category', ''))}</td>"
                f"<td>{_esc(r.get('title', ''))}</td>"
                f"<td>{_esc(r.get('controls_count', ''))}</td>"
                f"<td>{_esc(r.get('controls_passed', ''))}</td>"
                f"<td class='{cls}'>{_esc(status)}</td>"
                "</tr>"
            )
        body.append("</tbody></table>")

        # Control gap analysis
        body.append('<h2>3. Control Gap Analysis</h2>')
        if gaps:
            body.append(
                "<table><thead><tr>"
                "<th>Control</th><th>Gap</th><th>Severity</th>"
                "</tr></thead><tbody>"
            )
            for g in gaps:
                body.append(
                    "<tr>"
                    f"<td>{_esc(g.get('control_code'))}</td>"
                    f"<td>{_esc(g.get('description'))}</td>"
                    f"<td>{_esc(g.get('severity'))}</td>"
                    "</tr>"
                )
            body.append("</tbody></table>")
        else:
            body.append("<p><em>No open control gaps identified.</em></p>")

        # Remediation roadmap
        body.append('<h2>4. Remediation Roadmap</h2>')
        if roadmap:
            body.append(
                "<table><thead><tr>"
                "<th>Item</th><th>Owner</th><th>Due</th>"
                "</tr></thead><tbody>"
            )
            for it in roadmap:
                body.append(
                    "<tr>"
                    f"<td>{_esc(it.get('item'))}</td>"
                    f"<td>{_esc(it.get('owner'))}</td>"
                    f"<td>{_esc(_fmt_date(it.get('due')))}</td>"
                    "</tr>"
                )
            body.append("</tbody></table>")
        else:
            body.append("<p><em>No remediation items pending.</em></p>")

        # Auditor sign-off page
        body.append('<h2>5. Auditor Sign-off</h2>')
        body.append(
            "<div class='signoff'>"
            f"<p>Auditor: <strong>{_esc(auditor)}</strong></p>"
            "<p>Signature: ____________________________</p>"
            "<p>Date: ____________________________</p>"
            "</div>"
        )

        return self._html_shell(ctx, "\n".join(body))

    # ─────────────────────────────────────────────────────────────────────
    # PDF
    # ─────────────────────────────────────────────────────────────────────

    def build_pdf_story(self, ctx: Dict[str, Any]) -> List[Any]:
        tsc_rows = ctx.get("tsc_coverage") or DEFAULT_TSC_CATEGORIES
        gaps = ctx.get("control_gaps") or []
        roadmap = ctx.get("remediation_roadmap") or []
        overall_pct = ctx.get("overall_compliance_pct", 0.0)
        auditor = ctx.get("auditor_name", "")

        story: List[Any] = []
        story.append(Paragraph("1. Executive Summary", SHARED_STYLES["H1"]))
        story.append(
            Paragraph(
                f"Overall compliance for the reporting period: "
                f"<b>{overall_pct:.1f}%</b>.",
                SHARED_STYLES["Body"],
            )
        )

        story.append(
            Paragraph(
                "2. Trust Services Criteria (TSC) Coverage",
                SHARED_STYLES["H1"],
            )
        )
        headers = ["Category", "Title", "Controls", "Passed", "Status"]
        rows = [
            [
                str(r.get("category", "")),
                str(r.get("title", "")),
                str(r.get("controls_count", "")),
                str(r.get("controls_passed", "")),
                str(r.get("status", "Pass")),
            ]
            for r in tsc_rows
        ]
        story.append(
            self._pdf_table(headers, rows, col_widths=[2 * cm, 6 * cm, 2 * cm, 2 * cm, 3 * cm])
        )

        story.append(Spacer(1, 0.4 * cm))
        story.append(Paragraph("3. Control Gap Analysis", SHARED_STYLES["H1"]))
        if gaps:
            story.append(
                self._pdf_table(
                    ["Control", "Gap", "Severity"],
                    [
                        [
                            str(g.get("control_code", "")),
                            str(g.get("description", "")),
                            str(g.get("severity", "")),
                        ]
                        for g in gaps
                    ],
                    col_widths=[3 * cm, 9 * cm, 3 * cm],
                )
            )
        else:
            story.append(Paragraph("No open control gaps.", SHARED_STYLES["Body"]))

        story.append(Spacer(1, 0.4 * cm))
        story.append(Paragraph("4. Remediation Roadmap", SHARED_STYLES["H1"]))
        if roadmap:
            story.append(
                self._pdf_table(
                    ["Item", "Owner", "Due"],
                    [
                        [
                            str(it.get("item", "")),
                            str(it.get("owner", "")),
                            _fmt_date(it.get("due")),
                        ]
                        for it in roadmap
                    ],
                    col_widths=[9 * cm, 3 * cm, 3 * cm],
                )
            )
        else:
            story.append(Paragraph("No remediation items pending.", SHARED_STYLES["Body"]))

        story.append(Spacer(1, 1 * cm))
        story.append(Paragraph("5. Auditor Sign-off", SHARED_STYLES["H1"]))
        story.append(
            Paragraph(
                f"Auditor: <b>{_esc(auditor)}</b>",
                SHARED_STYLES["Body"],
            )
        )
        story.append(Paragraph("Signature: ____________________________", SHARED_STYLES["Body"]))
        story.append(Paragraph("Date: ____________________________", SHARED_STYLES["Body"]))

        return story
