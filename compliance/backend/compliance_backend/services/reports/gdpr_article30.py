"""
GDPR Article 30 Record of Processing Activities (RoPA).

Per Art. 30, the controller must maintain a record listing per-purpose:
  - Purpose of processing
  - Categories of data subjects + data
  - Categories of recipients
  - Legal basis (Art. 6 / Art. 9 lawful basis)
  - International transfers (3rd countries) + safeguards
  - Retention period

Context shape:
    {
        "org_name": str,
        "period_start": date, "period_end": date,
        "processing_records": [
            {"purpose": str, "data_subjects": str, "data_categories": str,
             "legal_basis": str, "retention": str,
             "third_country_transfers": str}, ...
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


class GdprArticle30Report(ReportTemplateBase):
    FRAMEWORK_SHORT_CODE = "GDPR"
    REPORT_TITLE = "GDPR Article 30 Record of Processing Activities"
    REPORT_SUBTITLE = "EU GDPR — Article 30 Record"

    def render_html(self, ctx: Dict[str, Any]) -> str:
        records = ctx.get("processing_records") or []

        body: List[str] = []
        body.append('<h2>Record of Processing Activities</h2>')
        body.append(
            "<p>This record is maintained pursuant to Article 30 of the "
            "General Data Protection Regulation (Regulation (EU) 2016/679). "
            "It identifies, per processing purpose, the categories of data "
            "subjects and personal data, the legal basis (Art. 6 / Art. 9), "
            "the recipients, the retention period, and any transfers to "
            "third countries.</p>"
        )

        if not records:
            body.append("<p><em>No processing records supplied.</em></p>")
        for i, r in enumerate(records, start=1):
            body.append(
                f"<h3>{i}. {_esc(r.get('purpose'))}</h3>"
                "<table><tbody>"
                f"<tr><th>Categories of data subjects</th>"
                f"<td>{_esc(r.get('data_subjects'))}</td></tr>"
                f"<tr><th>Categories of personal data</th>"
                f"<td>{_esc(r.get('data_categories'))}</td></tr>"
                f"<tr><th>Legal basis</th>"
                f"<td>{_esc(r.get('legal_basis'))}</td></tr>"
                f"<tr><th>Retention</th>"
                f"<td>{_esc(r.get('retention'))}</td></tr>"
                f"<tr><th>Third-country transfers</th>"
                f"<td>{_esc(r.get('third_country_transfers'))}</td></tr>"
                "</tbody></table>"
            )

        return self._html_shell(ctx, "\n".join(body))

    def build_pdf_story(self, ctx: Dict[str, Any]) -> List[Any]:
        records = ctx.get("processing_records") or []

        story: List[Any] = []
        story.append(Paragraph("Record of Processing Activities", SHARED_STYLES["H1"]))
        story.append(
            Paragraph(
                "Maintained pursuant to Article 30 of the GDPR (Regulation "
                "(EU) 2016/679).",
                SHARED_STYLES["Body"],
            )
        )

        if not records:
            story.append(Paragraph("No processing records supplied.", SHARED_STYLES["Body"]))
            return story

        for i, r in enumerate(records, start=1):
            story.append(
                Paragraph(f"{i}. {_esc(r.get('purpose'))}", SHARED_STYLES["H2"])
            )
            story.append(
                self._pdf_table(
                    ["Field", "Value"],
                    [
                        ["Categories of data subjects", str(r.get("data_subjects", ""))],
                        ["Categories of personal data", str(r.get("data_categories", ""))],
                        ["Legal basis", str(r.get("legal_basis", ""))],
                        ["Retention", str(r.get("retention", ""))],
                        [
                            "Third-country transfers",
                            str(r.get("third_country_transfers", "")),
                        ],
                    ],
                    col_widths=[5 * cm, 11 * cm],
                )
            )
            story.append(Spacer(1, 0.3 * cm))

        return story
