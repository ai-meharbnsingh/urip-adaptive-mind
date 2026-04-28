"""
ISO 27001 Statement of Applicability (SoA).

Per ISO/IEC 27001:2022, the SoA must list every Annex A control with:
  - Applicability decision (Yes / No / Compensating)
  - Justification (especially for non-applicable)
  - Implementation status (Implemented / Partial / Planned / N/A)

Context shape:
    {
        "org_name": str,
        "period_start": date, "period_end": date,
        "framework_version": "ISO/IEC 27001:2022",
        "soa_controls": [
            {"control_code": "A.5.1", "title": "...",
             "applicability": "Yes|No|Compensating",
             "justification": str,
             "implementation_status": "Implemented|Partial|Planned|N/A"},
            ...
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
)


class Iso27001SoaReport(ReportTemplateBase):
    FRAMEWORK_SHORT_CODE = "ISO27001"
    REPORT_TITLE = "ISO 27001 Statement of Applicability"
    REPORT_SUBTITLE = "Annex A control applicability decisions"

    def render_html(self, ctx: Dict[str, Any]) -> str:
        rows = ctx.get("soa_controls") or []

        body: List[str] = ['<h2>Statement of Applicability — Annex A</h2>']
        body.append(
            "<p>For each Annex A control, this report records the "
            "applicability decision, justification, and current implementation "
            "status. Non-applicable controls require an explicit justification.</p>"
        )

        body.append(
            "<table><thead><tr>"
            "<th>Control</th><th>Title</th><th>Applicability</th>"
            "<th>Justification</th><th>Implementation</th>"
            "</tr></thead><tbody>"
        )
        if not rows:
            body.append('<tr><td colspan="5"><em>No controls supplied.</em></td></tr>')
        for r in rows:
            applicability = r.get("applicability", "")
            cls = {
                "Yes": "pass",
                "No": "fail",
                "Compensating": "partial",
            }.get(applicability, "")
            body.append(
                "<tr>"
                f"<td>{_esc(r.get('control_code'))}</td>"
                f"<td>{_esc(r.get('title'))}</td>"
                f"<td class='{cls}'>{_esc(applicability)}</td>"
                f"<td>{_esc(r.get('justification'))}</td>"
                f"<td>{_esc(r.get('implementation_status'))}</td>"
                "</tr>"
            )
        body.append("</tbody></table>")

        return self._html_shell(ctx, "\n".join(body))

    def build_pdf_story(self, ctx: Dict[str, Any]) -> List[Any]:
        rows = ctx.get("soa_controls") or []

        story: List[Any] = []
        story.append(
            Paragraph("Statement of Applicability — Annex A", SHARED_STYLES["H1"])
        )
        story.append(
            Paragraph(
                "For each Annex A control, this report records the "
                "applicability decision, justification, and current "
                "implementation status.",
                SHARED_STYLES["Body"],
            )
        )
        story.append(Spacer(1, 0.3 * cm))

        if not rows:
            story.append(Paragraph("No controls supplied.", SHARED_STYLES["Body"]))
            return story

        headers = ["Control", "Title", "Applicability", "Justification", "Status"]
        table_rows = [
            [
                str(r.get("control_code", "")),
                str(r.get("title", "")),
                str(r.get("applicability", "")),
                str(r.get("justification", "")),
                str(r.get("implementation_status", "")),
            ]
            for r in rows
        ]
        story.append(
            self._pdf_table(
                headers,
                table_rows,
                col_widths=[2.5 * cm, 4 * cm, 2.5 * cm, 5 * cm, 2.5 * cm],
            )
        )
        return story
