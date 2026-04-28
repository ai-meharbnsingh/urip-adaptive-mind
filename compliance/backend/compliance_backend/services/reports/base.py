"""
ReportTemplateBase — abstract base class for framework-specific reports.

Each subclass produces both HTML (browser preview) and PDF (downloadable) for a
specific compliance framework (SOC 2, ISO 27001, HIPAA, GDPR, PCI DSS, India DPDP).

Design notes
------------
- Templates are pure-function-style: render_html(ctx) and render_pdf(ctx) take a
  context dict and return a string (HTML) or bytes (PDF).
- HTML is built using simple string templating (no Jinja dependency to keep the
  service lean — the structure is highly framework-specific anyway).
- PDF uses reportlab Platypus (Flowable + SimpleDocTemplate). Each subclass
  builds a list of flowables in build_pdf_story(ctx).
- The base class supplies a shared cover-page builder + corporate styling so
  every framework looks consistent.
"""
from __future__ import annotations

import abc
import html as html_lib
import io
from datetime import date, datetime
from typing import Any, Dict, List, Optional

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm, mm
from reportlab.platypus import (
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
    PageBreak,
)


# ─────────────────────────────────────────────────────────────────────────────
# Shared style sheet
# ─────────────────────────────────────────────────────────────────────────────


def _build_styles() -> Dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()
    styles: Dict[str, ParagraphStyle] = {
        "Title": ParagraphStyle(
            "ReportTitle",
            parent=base["Title"],
            fontSize=24,
            leading=28,
            alignment=TA_CENTER,
            spaceAfter=12,
            textColor=colors.HexColor("#0f3057"),
        ),
        "Subtitle": ParagraphStyle(
            "ReportSubtitle",
            parent=base["Normal"],
            fontSize=14,
            leading=18,
            alignment=TA_CENTER,
            spaceAfter=18,
            textColor=colors.HexColor("#37474f"),
        ),
        "H1": ParagraphStyle(
            "H1",
            parent=base["Heading1"],
            fontSize=16,
            leading=20,
            spaceBefore=18,
            spaceAfter=8,
            textColor=colors.HexColor("#0f3057"),
        ),
        "H2": ParagraphStyle(
            "H2",
            parent=base["Heading2"],
            fontSize=13,
            leading=16,
            spaceBefore=12,
            spaceAfter=6,
            textColor=colors.HexColor("#1565c0"),
        ),
        "Body": ParagraphStyle(
            "Body",
            parent=base["Normal"],
            fontSize=10,
            leading=13,
            alignment=TA_LEFT,
            spaceAfter=6,
        ),
        "Small": ParagraphStyle(
            "Small",
            parent=base["Normal"],
            fontSize=8,
            leading=10,
            alignment=TA_LEFT,
        ),
        "Cover": ParagraphStyle(
            "Cover",
            parent=base["Normal"],
            fontSize=12,
            leading=16,
            alignment=TA_CENTER,
            spaceAfter=8,
        ),
    }
    return styles


SHARED_STYLES = _build_styles()


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────


def _fmt_date(d: Any) -> str:
    if d is None:
        return ""
    if isinstance(d, (date, datetime)):
        return d.isoformat()
    return str(d)


def _esc(value: Any) -> str:
    """HTML-escape any scalar."""
    if value is None:
        return ""
    return html_lib.escape(str(value))


# ─────────────────────────────────────────────────────────────────────────────
# Abstract base
# ─────────────────────────────────────────────────────────────────────────────


class ReportTemplateBase(abc.ABC):
    """
    Abstract base for framework-specific reports.

    Subclasses set:
      - FRAMEWORK_SHORT_CODE  : e.g. "SOC2", "ISO27001"
      - REPORT_TITLE          : full report name shown on cover page
      - REPORT_SUBTITLE       : optional secondary line on cover page

    Subclasses MUST implement:
      - render_html(ctx)      : returns str (HTML document)
      - build_pdf_story(ctx)  : returns list of reportlab Flowables (the body
                                AFTER the cover page)
    """

    FRAMEWORK_SHORT_CODE: str = ""
    REPORT_TITLE: str = ""
    REPORT_SUBTITLE: str = ""

    # ─────────────────────────────────────────────────────────────────────
    # PDF entry point — shared cover + subclass-specific story
    # ─────────────────────────────────────────────────────────────────────

    def render_pdf(self, ctx: Dict[str, Any]) -> bytes:
        """Render the full PDF (cover page + body) and return bytes."""
        buf = io.BytesIO()
        doc = SimpleDocTemplate(
            buf,
            pagesize=A4,
            leftMargin=2 * cm,
            rightMargin=2 * cm,
            topMargin=2 * cm,
            bottomMargin=2 * cm,
            title=self.REPORT_TITLE or self.FRAMEWORK_SHORT_CODE,
            author="URIP Compliance Service",
        )
        story: List[Any] = []
        story.extend(self._build_cover(ctx))
        story.append(PageBreak())
        story.extend(self.build_pdf_story(ctx))
        doc.build(story)
        return buf.getvalue()

    def _build_cover(self, ctx: Dict[str, Any]) -> List[Any]:
        org = ctx.get("org_name", "")
        fw_ver = ctx.get("framework_version", "")
        period_start = _fmt_date(ctx.get("period_start"))
        period_end = _fmt_date(ctx.get("period_end"))
        report_date = _fmt_date(ctx.get("report_date") or date.today())

        story: List[Any] = []
        story.append(Spacer(1, 4 * cm))
        story.append(Paragraph(self.REPORT_TITLE, SHARED_STYLES["Title"]))
        if self.REPORT_SUBTITLE:
            story.append(Paragraph(self.REPORT_SUBTITLE, SHARED_STYLES["Subtitle"]))
        story.append(Spacer(1, 1 * cm))
        story.append(Paragraph(f"<b>Organisation:</b> {_esc(org)}", SHARED_STYLES["Cover"]))
        if fw_ver:
            story.append(
                Paragraph(
                    f"<b>Framework version:</b> {_esc(fw_ver)}",
                    SHARED_STYLES["Cover"],
                )
            )
        if period_start or period_end:
            story.append(
                Paragraph(
                    f"<b>Reporting period:</b> {_esc(period_start)} — {_esc(period_end)}",
                    SHARED_STYLES["Cover"],
                )
            )
        story.append(
            Paragraph(
                f"<b>Report generated:</b> {_esc(report_date)}",
                SHARED_STYLES["Cover"],
            )
        )
        story.append(Spacer(1, 4 * cm))
        story.append(
            Paragraph(
                "<i>Generated by URIP Compliance Service</i>",
                SHARED_STYLES["Small"],
            )
        )
        return story

    # ─────────────────────────────────────────────────────────────────────
    # HTML helpers (shared structure for every report)
    # ─────────────────────────────────────────────────────────────────────

    def _html_shell(self, ctx: Dict[str, Any], inner_html: str) -> str:
        """Wrap subclass body in a complete HTML document with cover-page header."""
        title = self.REPORT_TITLE or self.FRAMEWORK_SHORT_CODE
        org = _esc(ctx.get("org_name", ""))
        period = (
            f"{_esc(_fmt_date(ctx.get('period_start')))} — "
            f"{_esc(_fmt_date(ctx.get('period_end')))}"
        )
        report_date = _esc(_fmt_date(ctx.get("report_date") or date.today()))
        subtitle = self.REPORT_SUBTITLE or ""
        framework_version = _esc(ctx.get("framework_version", ""))

        # Inline CSS so the report can be opened in a browser without extra files.
        css = """
        body { font-family: 'Helvetica', Arial, sans-serif; color:#222; margin:2.5cm 2cm; }
        .cover { text-align:center; padding:6cm 0 4cm; border-bottom:2px solid #0f3057; }
        .cover h1 { color:#0f3057; font-size:32pt; margin:0; }
        .cover .sub { color:#37474f; font-size:14pt; margin:0.3cm 0 0; }
        .meta { margin-top:1.5cm; font-size:11pt; line-height:1.6; }
        h2 { color:#0f3057; border-bottom:1px solid #cfd8dc; padding-bottom:4px;
             margin-top:24px; }
        h3 { color:#1565c0; margin-bottom:6px; }
        table { width:100%; border-collapse:collapse; margin:8px 0 16px; font-size:10pt; }
        th { background:#0f3057; color:#fff; text-align:left; padding:6px 8px; }
        td { border:1px solid #cfd8dc; padding:6px 8px; vertical-align:top; }
        tr:nth-child(even) td { background:#f5f7fa; }
        .pass { color:#2e7d32; font-weight:bold; }
        .fail { color:#c62828; font-weight:bold; }
        .partial { color:#ef6c00; font-weight:bold; }
        .signoff { margin-top:48px; padding-top:24px; border-top:1px solid #cfd8dc; }
        .small { font-size:9pt; color:#666; }
        """

        return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <title>{_esc(title)} — {org}</title>
    <style>{css}</style>
</head>
<body>
    <section class="cover">
        <h1>{_esc(title)}</h1>
        <p class="sub">{_esc(subtitle)}</p>
        <div class="meta">
            <div><strong>Organisation:</strong> {org}</div>
            <div><strong>Framework version:</strong> {framework_version}</div>
            <div><strong>Reporting period:</strong> {period}</div>
            <div><strong>Report generated:</strong> {report_date}</div>
        </div>
    </section>
    <section class="body">
        {inner_html}
    </section>
    <footer class="small signoff">
        <p>Generated by URIP Compliance Service.</p>
    </footer>
</body>
</html>"""

    # ─────────────────────────────────────────────────────────────────────
    # PDF table helper (shared)
    # ─────────────────────────────────────────────────────────────────────

    def _pdf_table(
        self,
        headers: List[str],
        rows: List[List[Any]],
        col_widths: Optional[List[float]] = None,
    ) -> Table:
        """Build a styled reportlab Table with the project's house style."""
        # Wrap long cell content in Paragraph so it word-wraps.
        wrapped_rows: List[List[Any]] = []
        for r in rows:
            wrapped_rows.append(
                [Paragraph(_esc(c), SHARED_STYLES["Small"]) if isinstance(c, str) else c for c in r]
            )

        data: List[List[Any]] = [headers] + wrapped_rows
        table = Table(data, colWidths=col_widths, repeatRows=1)
        table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0f3057")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("FONTSIZE", (0, 0), (-1, 0), 9),
                    ("BOTTOMPADDING", (0, 0), (-1, 0), 6),
                    ("ALIGN", (0, 0), (-1, 0), "LEFT"),
                    ("FONTSIZE", (0, 1), (-1, -1), 8),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#cfd8dc")),
                    (
                        "ROWBACKGROUNDS",
                        (0, 1),
                        (-1, -1),
                        [colors.white, colors.HexColor("#f5f7fa")],
                    ),
                ]
            )
        )
        return table

    # ─────────────────────────────────────────────────────────────────────
    # Abstract methods
    # ─────────────────────────────────────────────────────────────────────

    @abc.abstractmethod
    def render_html(self, ctx: Dict[str, Any]) -> str:
        """Render the full HTML document and return a string."""
        ...

    @abc.abstractmethod
    def build_pdf_story(self, ctx: Dict[str, Any]) -> List[Any]:
        """
        Return the list of reportlab Flowables that make up the PDF body
        (after the shared cover page).
        """
        ...
