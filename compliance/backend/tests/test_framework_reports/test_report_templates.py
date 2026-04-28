"""
TDD tests for the framework-specific report templates (PART 1).

Each report template:
- Inherits from ReportTemplateBase
- Has a unique FRAMEWORK_SHORT_CODE
- Renders HTML (string)
- Renders PDF (bytes — reportlab generated)
- Accepts a `context` dict with org_name, period, framework_version, controls, etc.
- The rendered output contains framework-specific section headers
"""
from __future__ import annotations

from datetime import date

import pytest

from compliance_backend.services.reports import (
    ReportTemplateBase,
    Soc2ManagementReport,
    Iso27001SoaReport,
    HipaaRiskAnalysisReport,
    GdprArticle30Report,
    PciDssAocReport,
    IndiaDpdpDpiaReport,
    REPORT_REGISTRY,
    get_report_template,
)


# ─────────────────────────────────────────────────────────────────────────────
# Generic context fixture
# ─────────────────────────────────────────────────────────────────────────────


@pytest.fixture
def base_context() -> dict:
    return {
        "org_name": "Acme Corp",
        "period_start": date(2026, 1, 1),
        "period_end": date(2026, 4, 1),
        "framework_version": "2017 (TSC 2022 Revision)",
        "report_date": date(2026, 4, 27),
        "auditor_name": "Jane Smith, CPA",
        "overall_compliance_pct": 92.4,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Base contract
# ─────────────────────────────────────────────────────────────────────────────


def test_base_class_is_abstract():
    """ReportTemplateBase cannot be instantiated directly."""
    with pytest.raises(TypeError):
        ReportTemplateBase()  # type: ignore[abstract]


def test_registry_has_all_six_frameworks():
    """REPORT_REGISTRY exposes all 6 framework reports keyed by short_code."""
    expected_codes = {"SOC2", "ISO27001", "HIPAA", "GDPR", "PCI_DSS", "INDIA_DPDP"}
    assert set(REPORT_REGISTRY.keys()) == expected_codes


def test_get_report_template_returns_class():
    """get_report_template('SOC2') returns the Soc2ManagementReport class."""
    cls = get_report_template("SOC2")
    assert cls is Soc2ManagementReport


def test_get_report_template_unknown_returns_none():
    assert get_report_template("UNKNOWN_FRAMEWORK") is None


# ─────────────────────────────────────────────────────────────────────────────
# SOC 2 Management Report
# ─────────────────────────────────────────────────────────────────────────────


class TestSoc2ManagementReport:
    def test_short_code_matches(self):
        assert Soc2ManagementReport.FRAMEWORK_SHORT_CODE == "SOC2"

    def test_render_html_includes_org_and_tsc(self, base_context):
        ctx = {
            **base_context,
            "tsc_coverage": [
                {"category": "CC1", "title": "Control Environment", "status": "Pass", "controls_count": 5, "controls_passed": 5},
                {"category": "CC6", "title": "Logical & Physical Access", "status": "Partial", "controls_count": 8, "controls_passed": 6},
            ],
            "control_gaps": [
                {"control_code": "CC6.1", "description": "MFA missing on legacy app", "severity": "high"},
            ],
            "remediation_roadmap": [
                {"item": "Roll MFA to legacy app", "owner": "IT", "due": "2026-06-30"},
            ],
        }
        report = Soc2ManagementReport()
        html = report.render_html(ctx)
        assert isinstance(html, str)
        assert "Acme Corp" in html
        assert "SOC 2" in html
        # Trust Services Criteria coverage section
        assert "Trust Services" in html or "TSC" in html
        # CC1 should appear in the table
        assert "CC1" in html
        assert "CC6" in html
        # Control gap analysis
        assert "Control Gap" in html or "Gap Analysis" in html
        # Remediation roadmap
        assert "Remediation" in html
        # Auditor sign-off
        assert "Sign" in html or "sign" in html

    def test_render_pdf_returns_bytes(self, base_context):
        ctx = {
            **base_context,
            "tsc_coverage": [],
            "control_gaps": [],
            "remediation_roadmap": [],
        }
        pdf = Soc2ManagementReport().render_pdf(ctx)
        assert isinstance(pdf, bytes)
        # All PDFs start with %PDF
        assert pdf.startswith(b"%PDF")
        # Sanity: length > 1KB
        assert len(pdf) > 1024


# ─────────────────────────────────────────────────────────────────────────────
# ISO 27001 Statement of Applicability
# ─────────────────────────────────────────────────────────────────────────────


class TestIso27001SoaReport:
    def test_short_code(self):
        assert Iso27001SoaReport.FRAMEWORK_SHORT_CODE == "ISO27001"

    def test_render_html_includes_annex_a_table(self, base_context):
        ctx = {
            **base_context,
            "soa_controls": [
                {
                    "control_code": "A.5.1",
                    "title": "Policies for information security",
                    "applicability": "Yes",
                    "justification": "Required for all in-scope systems.",
                    "implementation_status": "Implemented",
                },
                {
                    "control_code": "A.6.3",
                    "title": "Information security awareness, education & training",
                    "applicability": "Yes",
                    "justification": "Mandatory training program.",
                    "implementation_status": "Partial",
                },
                {
                    "control_code": "A.8.32",
                    "title": "Change management",
                    "applicability": "No",
                    "justification": "Not applicable: outsourced cloud platform.",
                    "implementation_status": "N/A",
                },
            ],
        }
        html = Iso27001SoaReport().render_html(ctx)
        assert "ISO" in html and "27001" in html
        assert "Statement of Applicability" in html
        assert "A.5.1" in html
        assert "A.6.3" in html
        assert "A.8.32" in html
        # Justification text should appear for non-applicable
        assert "Not applicable" in html

    def test_render_pdf(self, base_context):
        ctx = {**base_context, "soa_controls": []}
        pdf = Iso27001SoaReport().render_pdf(ctx)
        assert pdf.startswith(b"%PDF")


# ─────────────────────────────────────────────────────────────────────────────
# HIPAA Risk Analysis
# ─────────────────────────────────────────────────────────────────────────────


class TestHipaaRiskAnalysisReport:
    def test_short_code(self):
        assert HipaaRiskAnalysisReport.FRAMEWORK_SHORT_CODE == "HIPAA"

    def test_render_html_includes_risk_matrix(self, base_context):
        ctx = {
            **base_context,
            "asset_inventory": [
                {"asset": "EHR Production DB", "system_type": "Database", "ePHI_volume": "high"},
                {"asset": "Patient Portal", "system_type": "Web App", "ePHI_volume": "medium"},
            ],
            "risk_matrix": [
                {
                    "threat": "Unauthorized access",
                    "vulnerability": "Weak password policy",
                    "likelihood": "High",
                    "impact": "High",
                    "risk_level": "Critical",
                    "asset": "EHR Production DB",
                },
            ],
            "mitigations": [
                {"safeguard_category": "Administrative", "measure": "Enforce MFA + password rotation"},
                {"safeguard_category": "Technical", "measure": "Encrypt ePHI at rest with AES-256"},
                {"safeguard_category": "Physical", "measure": "Badge-only datacenter access"},
            ],
        }
        html = HipaaRiskAnalysisReport().render_html(ctx)
        assert "HIPAA" in html
        assert "Risk Analysis" in html
        assert "EHR Production DB" in html
        assert "Administrative" in html
        assert "Technical" in html
        assert "Physical" in html

    def test_render_pdf(self, base_context):
        ctx = {
            **base_context,
            "asset_inventory": [],
            "risk_matrix": [],
            "mitigations": [],
        }
        pdf = HipaaRiskAnalysisReport().render_pdf(ctx)
        assert pdf.startswith(b"%PDF")


# ─────────────────────────────────────────────────────────────────────────────
# GDPR Article 30 Record of Processing
# ─────────────────────────────────────────────────────────────────────────────


class TestGdprArticle30Report:
    def test_short_code(self):
        assert GdprArticle30Report.FRAMEWORK_SHORT_CODE == "GDPR"

    def test_render_html_includes_processing_records(self, base_context):
        ctx = {
            **base_context,
            "processing_records": [
                {
                    "purpose": "Customer support ticketing",
                    "data_subjects": "Customers",
                    "data_categories": "Name, email, support transcripts",
                    "legal_basis": "Contract (Art. 6(1)(b))",
                    "retention": "5 years post-contract",
                    "third_country_transfers": "USA (SCC + DPF)",
                },
                {
                    "purpose": "Marketing emails",
                    "data_subjects": "Newsletter subscribers",
                    "data_categories": "Email, behavioural metrics",
                    "legal_basis": "Consent (Art. 6(1)(a))",
                    "retention": "Until consent withdrawn",
                    "third_country_transfers": "None",
                },
            ],
        }
        html = GdprArticle30Report().render_html(ctx)
        assert "GDPR" in html
        assert "Article 30" in html
        assert "Customer support ticketing" in html
        assert "Marketing emails" in html
        assert "Art. 6" in html or "Article 6" in html

    def test_render_pdf(self, base_context):
        ctx = {**base_context, "processing_records": []}
        pdf = GdprArticle30Report().render_pdf(ctx)
        assert pdf.startswith(b"%PDF")


# ─────────────────────────────────────────────────────────────────────────────
# PCI DSS AoC
# ─────────────────────────────────────────────────────────────────────────────


class TestPciDssAocReport:
    def test_short_code(self):
        assert PciDssAocReport.FRAMEWORK_SHORT_CODE == "PCI_DSS"

    def test_render_html_lists_twelve_requirements(self, base_context):
        # PCI DSS has exactly 12 requirements
        ctx = {
            **base_context,
            "requirements": [
                {"req_no": i, "title": f"Requirement {i}", "status": "Compliant", "compensating_controls": []}
                for i in range(1, 13)
            ],
            "network_diagram_refs": ["NetDiag-2026-Q2.pdf"],
        }
        html = PciDssAocReport().render_html(ctx)
        assert "PCI DSS" in html
        assert "Attestation of Compliance" in html
        # All 12 requirement labels
        for i in range(1, 13):
            assert f"Requirement {i}" in html
        assert "NetDiag-2026-Q2.pdf" in html

    def test_render_pdf(self, base_context):
        ctx = {
            **base_context,
            "requirements": [],
            "network_diagram_refs": [],
        }
        pdf = PciDssAocReport().render_pdf(ctx)
        assert pdf.startswith(b"%PDF")


# ─────────────────────────────────────────────────────────────────────────────
# India DPDP DPIA
# ─────────────────────────────────────────────────────────────────────────────


class TestIndiaDpdpDpiaReport:
    def test_short_code(self):
        assert IndiaDpdpDpiaReport.FRAMEWORK_SHORT_CODE == "INDIA_DPDP"

    def test_render_html_includes_proportionality(self, base_context):
        ctx = {
            **base_context,
            "processing_description": "Processing PAN + Aadhaar for KYC.",
            "necessity_assessment": "Required by RBI master direction on KYC.",
            "proportionality_assessment": "Limited to KYC fields; deleted after 5y.",
            "principal_risks": [
                {"risk": "Re-identification of pseudonymised data", "likelihood": "Low", "impact": "High"},
            ],
            "mitigations": [
                {"measure": "Tokenisation of PAN at ingest", "owner": "Data Eng"},
            ],
        }
        html = IndiaDpdpDpiaReport().render_html(ctx)
        assert "DPDP" in html
        assert "Data Protection Impact Assessment" in html
        assert "Necessity" in html
        assert "Proportionality" in html
        assert "Tokenisation" in html

    def test_render_pdf(self, base_context):
        ctx = {
            **base_context,
            "processing_description": "x",
            "necessity_assessment": "x",
            "proportionality_assessment": "x",
            "principal_risks": [],
            "mitigations": [],
        }
        pdf = IndiaDpdpDpiaReport().render_pdf(ctx)
        assert pdf.startswith(b"%PDF")
