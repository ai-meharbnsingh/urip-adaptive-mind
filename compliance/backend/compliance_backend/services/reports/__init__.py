"""
Framework-specific report templates.

Public API:
    ReportTemplateBase           — abstract base class
    Soc2ManagementReport         — SOC 2 Management Report
    Iso27001SoaReport            — ISO 27001 Statement of Applicability
    HipaaRiskAnalysisReport      — HIPAA Risk Analysis (45 CFR § 164.308)
    GdprArticle30Report          — GDPR Article 30 Record of Processing
    PciDssAocReport              — PCI DSS Attestation of Compliance Inputs
    IndiaDpdpDpiaReport          — India DPDP DPIA

    REPORT_REGISTRY              — dict[short_code -> ReportTemplate class]
    get_report_template(code)    — registry lookup helper
"""
from __future__ import annotations

from typing import Dict, Optional, Type

from compliance_backend.services.reports.base import ReportTemplateBase
from compliance_backend.services.reports.soc2_management import Soc2ManagementReport
from compliance_backend.services.reports.iso27001_soa import Iso27001SoaReport
from compliance_backend.services.reports.hipaa_risk_analysis import HipaaRiskAnalysisReport
from compliance_backend.services.reports.gdpr_article30 import GdprArticle30Report
from compliance_backend.services.reports.pci_dss_aoc import PciDssAocReport
from compliance_backend.services.reports.india_dpdp_dpia import IndiaDpdpDpiaReport


REPORT_REGISTRY: Dict[str, Type[ReportTemplateBase]] = {
    Soc2ManagementReport.FRAMEWORK_SHORT_CODE: Soc2ManagementReport,
    Iso27001SoaReport.FRAMEWORK_SHORT_CODE: Iso27001SoaReport,
    HipaaRiskAnalysisReport.FRAMEWORK_SHORT_CODE: HipaaRiskAnalysisReport,
    GdprArticle30Report.FRAMEWORK_SHORT_CODE: GdprArticle30Report,
    PciDssAocReport.FRAMEWORK_SHORT_CODE: PciDssAocReport,
    IndiaDpdpDpiaReport.FRAMEWORK_SHORT_CODE: IndiaDpdpDpiaReport,
}


def get_report_template(short_code: str) -> Optional[Type[ReportTemplateBase]]:
    """Return the report class for a framework short_code, or None if unknown."""
    return REPORT_REGISTRY.get(short_code.upper())


__all__ = [
    "ReportTemplateBase",
    "Soc2ManagementReport",
    "Iso27001SoaReport",
    "HipaaRiskAnalysisReport",
    "GdprArticle30Report",
    "PciDssAocReport",
    "IndiaDpdpDpiaReport",
    "REPORT_REGISTRY",
    "get_report_template",
]
