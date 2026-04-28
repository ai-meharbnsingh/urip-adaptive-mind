"""
PCI DSS Attestation of Compliance (AoC) Inputs.

PCI DSS v4.0 has 12 high-level requirements grouped into 6 control objectives.
This report captures the *inputs* a QSA needs to produce the actual AoC:

  - Per-requirement compliance status (1..12)
  - Compensating controls list (with worksheet refs)
  - Network diagram references (CDE / scope diagrams)

Context shape:
    {
        "org_name": str,
        "framework_version": "PCI DSS v4.0",
        "requirements": [
            {"req_no": 1..12, "title": str, "status": "Compliant|Not Applicable|Not in Place",
             "compensating_controls": [str, ...]}, ...
        ],
        "network_diagram_refs": [str, ...],
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


# Default labels for each of the 12 PCI DSS v4 requirements.
DEFAULT_REQUIREMENTS: List[Dict[str, Any]] = [
    {"req_no": 1, "title": "Install and maintain network security controls"},
    {"req_no": 2, "title": "Apply secure configurations to all system components"},
    {"req_no": 3, "title": "Protect stored account data"},
    {"req_no": 4, "title": "Protect cardholder data with strong cryptography during transmission"},
    {"req_no": 5, "title": "Protect all systems and networks from malicious software"},
    {"req_no": 6, "title": "Develop and maintain secure systems and software"},
    {"req_no": 7, "title": "Restrict access to system components and cardholder data by need to know"},
    {"req_no": 8, "title": "Identify users and authenticate access to system components"},
    {"req_no": 9, "title": "Restrict physical access to cardholder data"},
    {"req_no": 10, "title": "Log and monitor all access to system components and cardholder data"},
    {"req_no": 11, "title": "Test security of systems and networks regularly"},
    {"req_no": 12, "title": "Support information security with organisational policies and programs"},
]


class PciDssAocReport(ReportTemplateBase):
    FRAMEWORK_SHORT_CODE = "PCI_DSS"
    REPORT_TITLE = "PCI DSS Attestation of Compliance — Inputs"
    REPORT_SUBTITLE = "Inputs for QSA-prepared AoC (PCI DSS v4.0)"

    def render_html(self, ctx: Dict[str, Any]) -> str:
        # If no requirements provided, render the default 12 with status "Not in Place".
        reqs = ctx.get("requirements") or [
            {**r, "status": "Not in Place", "compensating_controls": []}
            for r in DEFAULT_REQUIREMENTS
        ]
        diagrams = ctx.get("network_diagram_refs") or []

        body: List[str] = []
        body.append('<h2>1. Twelve PCI DSS Requirements — Status</h2>')
        body.append(
            "<table><thead><tr>"
            "<th>#</th><th>Title</th><th>Status</th><th>Compensating Controls</th>"
            "</tr></thead><tbody>"
        )
        # Always show the requirement number with the canonical label "Requirement N"
        # so QSAs can scan quickly.
        default_titles = {r["req_no"]: r["title"] for r in DEFAULT_REQUIREMENTS}
        for r in reqs:
            num = r.get("req_no")
            title_supplied = r.get("title")
            label = f"Requirement {num}"
            if title_supplied:
                label = f"{label} — {title_supplied}"
            elif num in default_titles:
                label = f"{label} — {default_titles[num]}"

            status = r.get("status", "")
            cls = {
                "Compliant": "pass",
                "Not Applicable": "partial",
                "Not in Place": "fail",
            }.get(status, "")
            comp = r.get("compensating_controls") or []
            comp_html = (
                "<ul>" + "".join(f"<li>{_esc(c)}</li>" for c in comp) + "</ul>"
                if comp
                else ""
            )
            body.append(
                "<tr>"
                f"<td>{_esc(num)}</td>"
                f"<td>{_esc(label)}</td>"
                f"<td class='{cls}'>{_esc(status)}</td>"
                f"<td>{comp_html}</td>"
                "</tr>"
            )
        body.append("</tbody></table>")

        body.append('<h2>2. Network Diagram References (CDE Scope)</h2>')
        if diagrams:
            body.append("<ul>")
            for d in diagrams:
                body.append(f"<li>{_esc(d)}</li>")
            body.append("</ul>")
        else:
            body.append("<p><em>No network diagrams referenced.</em></p>")

        return self._html_shell(ctx, "\n".join(body))

    def build_pdf_story(self, ctx: Dict[str, Any]) -> List[Any]:
        reqs = ctx.get("requirements") or [
            {**r, "status": "Not in Place", "compensating_controls": []}
            for r in DEFAULT_REQUIREMENTS
        ]
        diagrams = ctx.get("network_diagram_refs") or []

        default_titles = {r["req_no"]: r["title"] for r in DEFAULT_REQUIREMENTS}

        story: List[Any] = []
        story.append(
            Paragraph("1. Twelve PCI DSS Requirements — Status", SHARED_STYLES["H1"])
        )
        rows: List[List[str]] = []
        for r in reqs:
            num = r.get("req_no")
            title_supplied = r.get("title")
            label = f"Requirement {num}"
            if title_supplied:
                label = f"{label} — {title_supplied}"
            elif num in default_titles:
                label = f"{label} — {default_titles[num]}"
            comp = r.get("compensating_controls") or []
            rows.append(
                [
                    str(num),
                    label,
                    str(r.get("status", "")),
                    "; ".join(str(c) for c in comp) if comp else "",
                ]
            )
        story.append(
            self._pdf_table(
                ["#", "Title", "Status", "Compensating Controls"],
                rows,
                col_widths=[1.2 * cm, 8.3 * cm, 2.5 * cm, 4 * cm],
            )
        )

        story.append(Spacer(1, 0.4 * cm))
        story.append(
            Paragraph("2. Network Diagram References (CDE Scope)", SHARED_STYLES["H1"])
        )
        if diagrams:
            for d in diagrams:
                story.append(Paragraph(f"• {_esc(d)}", SHARED_STYLES["Body"]))
        else:
            story.append(Paragraph("No network diagrams referenced.", SHARED_STYLES["Body"]))

        return story
