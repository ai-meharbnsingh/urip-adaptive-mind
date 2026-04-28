"""
HIPAA Risk Analysis (per 45 CFR § 164.308(a)(1)(ii)(A)).

Sections:
  1. Asset inventory — every system that creates, receives, maintains, or
     transmits ePHI.
  2. Threat × Vulnerability matrix — per-asset enumeration of likely threat
     actors and exploitable weaknesses.
  3. Risk likelihood × impact scoring (qualitative).
  4. Mitigation strategies grouped by safeguard category:
       Administrative (§ 164.308) | Physical (§ 164.310) | Technical (§ 164.312).

Context shape:
    {
        "org_name": str,
        "asset_inventory": [
            {"asset": str, "system_type": str, "ePHI_volume": "low|medium|high"}, ...
        ],
        "risk_matrix": [
            {"threat": str, "vulnerability": str,
             "likelihood": "Low|Medium|High",
             "impact": "Low|Medium|High",
             "risk_level": "Low|Medium|High|Critical",
             "asset": str}, ...
        ],
        "mitigations": [
            {"safeguard_category": "Administrative|Technical|Physical",
             "measure": str}, ...
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


class HipaaRiskAnalysisReport(ReportTemplateBase):
    FRAMEWORK_SHORT_CODE = "HIPAA"
    REPORT_TITLE = "HIPAA Security Risk Analysis"
    REPORT_SUBTITLE = "45 CFR § 164.308(a)(1)(ii)(A)"

    def render_html(self, ctx: Dict[str, Any]) -> str:
        assets = ctx.get("asset_inventory") or []
        matrix = ctx.get("risk_matrix") or []
        mits = ctx.get("mitigations") or []

        body: List[str] = []
        body.append('<h2>1. Asset Inventory (ePHI Systems)</h2>')
        if assets:
            body.append(
                "<table><thead><tr>"
                "<th>Asset</th><th>System Type</th><th>ePHI Volume</th>"
                "</tr></thead><tbody>"
            )
            for a in assets:
                body.append(
                    "<tr>"
                    f"<td>{_esc(a.get('asset'))}</td>"
                    f"<td>{_esc(a.get('system_type'))}</td>"
                    f"<td>{_esc(a.get('ePHI_volume'))}</td>"
                    "</tr>"
                )
            body.append("</tbody></table>")
        else:
            body.append("<p><em>No ePHI assets supplied.</em></p>")

        body.append('<h2>2. Threat × Vulnerability Matrix</h2>')
        if matrix:
            body.append(
                "<table><thead><tr>"
                "<th>Asset</th><th>Threat</th><th>Vulnerability</th>"
                "<th>Likelihood</th><th>Impact</th><th>Risk Level</th>"
                "</tr></thead><tbody>"
            )
            for r in matrix:
                level = r.get("risk_level", "")
                cls = {
                    "Low": "pass",
                    "Medium": "partial",
                    "High": "fail",
                    "Critical": "fail",
                }.get(level, "")
                body.append(
                    "<tr>"
                    f"<td>{_esc(r.get('asset'))}</td>"
                    f"<td>{_esc(r.get('threat'))}</td>"
                    f"<td>{_esc(r.get('vulnerability'))}</td>"
                    f"<td>{_esc(r.get('likelihood'))}</td>"
                    f"<td>{_esc(r.get('impact'))}</td>"
                    f"<td class='{cls}'>{_esc(level)}</td>"
                    "</tr>"
                )
            body.append("</tbody></table>")
        else:
            body.append("<p><em>No risks supplied.</em></p>")

        body.append('<h2>3. Mitigation Strategies by Safeguard Category</h2>')
        for cat in ("Administrative", "Technical", "Physical"):
            body.append(f"<h3>{cat} Safeguards</h3>")
            cat_items = [m for m in mits if m.get("safeguard_category") == cat]
            if cat_items:
                body.append("<ul>")
                for m in cat_items:
                    body.append(f"<li>{_esc(m.get('measure'))}</li>")
                body.append("</ul>")
            else:
                body.append(
                    f"<p><em>No mitigations recorded for {cat} safeguards.</em></p>"
                )

        return self._html_shell(ctx, "\n".join(body))

    def build_pdf_story(self, ctx: Dict[str, Any]) -> List[Any]:
        assets = ctx.get("asset_inventory") or []
        matrix = ctx.get("risk_matrix") or []
        mits = ctx.get("mitigations") or []

        story: List[Any] = []
        story.append(Paragraph("1. Asset Inventory (ePHI Systems)", SHARED_STYLES["H1"]))
        if assets:
            story.append(
                self._pdf_table(
                    ["Asset", "System Type", "ePHI Volume"],
                    [
                        [
                            str(a.get("asset", "")),
                            str(a.get("system_type", "")),
                            str(a.get("ePHI_volume", "")),
                        ]
                        for a in assets
                    ],
                    col_widths=[7 * cm, 5 * cm, 3 * cm],
                )
            )
        else:
            story.append(Paragraph("No ePHI assets supplied.", SHARED_STYLES["Body"]))

        story.append(Spacer(1, 0.4 * cm))
        story.append(Paragraph("2. Threat × Vulnerability Matrix", SHARED_STYLES["H1"]))
        if matrix:
            story.append(
                self._pdf_table(
                    ["Asset", "Threat", "Vulnerability", "Likelihood", "Impact", "Risk"],
                    [
                        [
                            str(r.get("asset", "")),
                            str(r.get("threat", "")),
                            str(r.get("vulnerability", "")),
                            str(r.get("likelihood", "")),
                            str(r.get("impact", "")),
                            str(r.get("risk_level", "")),
                        ]
                        for r in matrix
                    ],
                    col_widths=[3.5 * cm, 3 * cm, 3.5 * cm, 2 * cm, 2 * cm, 2 * cm],
                )
            )
        else:
            story.append(Paragraph("No risks supplied.", SHARED_STYLES["Body"]))

        story.append(Spacer(1, 0.4 * cm))
        story.append(
            Paragraph("3. Mitigation Strategies by Safeguard Category", SHARED_STYLES["H1"])
        )
        for cat in ("Administrative", "Technical", "Physical"):
            story.append(Paragraph(f"{cat} Safeguards", SHARED_STYLES["H2"]))
            cat_items = [m for m in mits if m.get("safeguard_category") == cat]
            if cat_items:
                for m in cat_items:
                    story.append(
                        Paragraph(f"• {_esc(m.get('measure'))}", SHARED_STYLES["Body"])
                    )
            else:
                story.append(
                    Paragraph(
                        f"No mitigations recorded for {cat} safeguards.",
                        SHARED_STYLES["Body"],
                    )
                )

        return story
