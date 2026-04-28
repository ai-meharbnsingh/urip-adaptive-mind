"""
India DPDP — Data Protection Impact Assessment.

Per the Digital Personal Data Protection Act, 2023 (India), Significant Data
Fiduciaries must perform a DPIA before processing.

Sections:
  1. Processing description
  2. Necessity assessment
  3. Proportionality assessment
  4. Risks to data principals (likelihood × impact)
  5. Mitigation measures

Context shape:
    {
        "org_name": str,
        "processing_description": str,
        "necessity_assessment": str,
        "proportionality_assessment": str,
        "principal_risks": [
            {"risk": str, "likelihood": str, "impact": str}, ...
        ],
        "mitigations": [
            {"measure": str, "owner": str}, ...
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


class IndiaDpdpDpiaReport(ReportTemplateBase):
    FRAMEWORK_SHORT_CODE = "INDIA_DPDP"
    REPORT_TITLE = "Data Protection Impact Assessment (India DPDP Act, 2023)"
    REPORT_SUBTITLE = "DPIA per § 10(2)(c) — Significant Data Fiduciary obligations"

    def render_html(self, ctx: Dict[str, Any]) -> str:
        body: List[str] = []
        body.append('<h2>1. Processing Description</h2>')
        body.append(f"<p>{_esc(ctx.get('processing_description', ''))}</p>")

        body.append('<h2>2. Necessity Assessment</h2>')
        body.append(f"<p>{_esc(ctx.get('necessity_assessment', ''))}</p>")

        body.append('<h2>3. Proportionality Assessment</h2>')
        body.append(f"<p>{_esc(ctx.get('proportionality_assessment', ''))}</p>")

        body.append('<h2>4. Risks to Data Principals</h2>')
        risks = ctx.get("principal_risks") or []
        if risks:
            body.append(
                "<table><thead><tr>"
                "<th>Risk</th><th>Likelihood</th><th>Impact</th>"
                "</tr></thead><tbody>"
            )
            for r in risks:
                body.append(
                    "<tr>"
                    f"<td>{_esc(r.get('risk'))}</td>"
                    f"<td>{_esc(r.get('likelihood'))}</td>"
                    f"<td>{_esc(r.get('impact'))}</td>"
                    "</tr>"
                )
            body.append("</tbody></table>")
        else:
            body.append("<p><em>No risks recorded.</em></p>")

        body.append('<h2>5. Mitigation Measures</h2>')
        mits = ctx.get("mitigations") or []
        if mits:
            body.append(
                "<table><thead><tr>"
                "<th>Measure</th><th>Owner</th>"
                "</tr></thead><tbody>"
            )
            for m in mits:
                body.append(
                    "<tr>"
                    f"<td>{_esc(m.get('measure'))}</td>"
                    f"<td>{_esc(m.get('owner'))}</td>"
                    "</tr>"
                )
            body.append("</tbody></table>")
        else:
            body.append("<p><em>No mitigations recorded.</em></p>")

        return self._html_shell(ctx, "\n".join(body))

    def build_pdf_story(self, ctx: Dict[str, Any]) -> List[Any]:
        story: List[Any] = []

        story.append(Paragraph("1. Processing Description", SHARED_STYLES["H1"]))
        story.append(
            Paragraph(_esc(ctx.get("processing_description", "")), SHARED_STYLES["Body"])
        )

        story.append(Paragraph("2. Necessity Assessment", SHARED_STYLES["H1"]))
        story.append(
            Paragraph(_esc(ctx.get("necessity_assessment", "")), SHARED_STYLES["Body"])
        )

        story.append(Paragraph("3. Proportionality Assessment", SHARED_STYLES["H1"]))
        story.append(
            Paragraph(_esc(ctx.get("proportionality_assessment", "")), SHARED_STYLES["Body"])
        )

        story.append(Paragraph("4. Risks to Data Principals", SHARED_STYLES["H1"]))
        risks = ctx.get("principal_risks") or []
        if risks:
            story.append(
                self._pdf_table(
                    ["Risk", "Likelihood", "Impact"],
                    [
                        [
                            str(r.get("risk", "")),
                            str(r.get("likelihood", "")),
                            str(r.get("impact", "")),
                        ]
                        for r in risks
                    ],
                    col_widths=[10 * cm, 3 * cm, 3 * cm],
                )
            )
        else:
            story.append(Paragraph("No risks recorded.", SHARED_STYLES["Body"]))

        story.append(Spacer(1, 0.4 * cm))
        story.append(Paragraph("5. Mitigation Measures", SHARED_STYLES["H1"]))
        mits = ctx.get("mitigations") or []
        if mits:
            story.append(
                self._pdf_table(
                    ["Measure", "Owner"],
                    [
                        [
                            str(m.get("measure", "")),
                            str(m.get("owner", "")),
                        ]
                        for m in mits
                    ],
                    col_widths=[12 * cm, 4 * cm],
                )
            )
        else:
            story.append(Paragraph("No mitigations recorded.", SHARED_STYLES["Body"]))

        return story
