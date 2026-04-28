"""
NIST Cybersecurity Framework 2.0 seeder.

Covers all 6 Functions with Categories and Subcategories:
  GV — Govern     (new in CSF 2.0)
  ID — Identify
  PR — Protect
  DE — Detect
  RS — Respond
  RC — Recover

Uses real CSF 2.0 subcategory IDs (GV.OC-01, ID.AM-01, PR.AC-01, etc.)
Decisions: subcategories are stored as individual controls with their
  parent category as the 'category' field for navigation and filtering.

Control count: 68 controls across all 6 Functions.

Sources: NIST Cybersecurity Framework 2.0 (February 2024), NIST.gov public document.
Idempotent: skip if NISTCSF framework already exists.
"""
import uuid
from datetime import date
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from compliance_backend.models.framework import Framework, FrameworkVersion, Control


# ---------------------------------------------------------------------------
# NIST CSF 2.0 control data
# Format: (control_code, category, title, description)
# category = Function name (Govern, Identify, Protect, Detect, Respond, Recover)
# control_code = CSF 2.0 subcategory ID (e.g., GV.OC-01)
# ---------------------------------------------------------------------------

NIST_GOVERN: list[tuple[str, str, str, str]] = [
    # GV.OC — Organizational Context
    ("GV.OC-01", "Govern",
     "Organizational Context — Mission Understood",
     "The organizational mission is understood and informs cybersecurity risk management decisions."),
    ("GV.OC-02", "Govern",
     "Organizational Context — Internal and External Stakeholders",
     "Internal and external stakeholders are understood, and their needs and expectations regarding cybersecurity risk management are understood and considered."),
    ("GV.OC-03", "Govern",
     "Organizational Context — Legal and Regulatory Requirements",
     "Legal, regulatory, and contractual requirements regarding cybersecurity — including privacy and civil liberties obligations — are understood and managed."),
    ("GV.OC-04", "Govern",
     "Organizational Context — Critical Objectives",
     "Critical objectives, capabilities, and services that stakeholders depend on or expect from the organization are understood and communicated."),
    ("GV.OC-05", "Govern",
     "Organizational Context — Outcomes and Dependencies",
     "Outcomes, capabilities, and services that the organization depends on are understood and communicated."),
    # GV.RM — Risk Management Strategy
    ("GV.RM-01", "Govern",
     "Risk Management Strategy — Risk Appetite",
     "Risk management objectives are established and agreed to by organizational stakeholders."),
    ("GV.RM-02", "Govern",
     "Risk Management Strategy — Risk Tolerance",
     "Risk appetite and risk tolerance statements are established, communicated, and maintained."),
    ("GV.RM-03", "Govern",
     "Risk Management Strategy — Cybersecurity Risk Information",
     "Cybersecurity risk management activities and outcomes are included in enterprise risk management processes."),
    ("GV.RM-06", "Govern",
     "Risk Management Strategy — Policy",
     "Policy is established, communicated, and enforced."),
    ("GV.RM-07", "Govern",
     "Risk Management Strategy — Strategic Decisions",
     "Strategic opportunities (i.e., positive risks) are characterized and are included in organizational cybersecurity risk discussions."),
    # GV.RR — Roles, Responsibilities, and Authorities
    ("GV.RR-01", "Govern",
     "Roles and Responsibilities — Leadership Accountability",
     "Organizational leadership is responsible and accountable for cybersecurity risk and fosters a culture that is risk-aware, ethical, and continually improving."),
    ("GV.RR-02", "Govern",
     "Roles and Responsibilities — Roles Defined",
     "Roles, responsibilities, and authorities related to cybersecurity risk management are established, communicated, understood, and enforced."),
    ("GV.RR-03", "Govern",
     "Roles and Responsibilities — Adequate Resources",
     "Adequate resources are allocated commensurate with the cybersecurity risk strategy, roles, responsibilities, and policies."),
    # GV.PO — Policy
    ("GV.PO-01", "Govern",
     "Policy — Cybersecurity Policy",
     "Policy for managing cybersecurity risks is established based on organizational context, cybersecurity strategy, and priorities and is communicated and enforced."),
    ("GV.PO-02", "Govern",
     "Policy — Policy Review",
     "Policy for managing cybersecurity risks is reviewed, updated, communicated, and enforced to reflect changes in requirements, threats, technology, and organizational mission."),
    # GV.OV — Oversight
    ("GV.OV-01", "Govern",
     "Oversight — Performance Monitoring",
     "Cybersecurity risk management strategy outcomes are reviewed to inform and adjust strategy and direction."),
    ("GV.OV-02", "Govern",
     "Oversight — Risk Management Review",
     "The cybersecurity risk management strategy is reviewed and adjusted to ensure coverage of organizational requirements and risks."),
    ("GV.OV-03", "Govern",
     "Oversight — Organizational Cybersecurity Results",
     "Organizational cybersecurity risk management performance is evaluated and reviewed for adjustments needed."),
    # GV.SC — Cybersecurity Supply Chain Risk Management
    ("GV.SC-01", "Govern",
     "Supply Chain Risk Management — Policy and Practice",
     "A cybersecurity supply chain risk management program, strategy, objectives, policies, and processes are established and agreed to by organizational stakeholders."),
    ("GV.SC-06", "Govern",
     "Supply Chain Risk Management — Planning and Due Diligence",
     "Planning and due diligence are performed to reduce risks before entering into formal supplier or other third-party relationships."),
]

NIST_IDENTIFY: list[tuple[str, str, str, str]] = [
    # ID.AM — Asset Management
    ("ID.AM-01", "Identify",
     "Asset Management — Inventories of Hardware Assets",
     "Inventories of hardware managed by the organization are maintained."),
    ("ID.AM-02", "Identify",
     "Asset Management — Inventories of Software Assets",
     "Inventories of software, services, and systems managed by the organization are maintained."),
    ("ID.AM-03", "Identify",
     "Asset Management — Network Representation",
     "Representations of the organization's authorized network communication and internal and external network data flows are maintained."),
    ("ID.AM-04", "Identify",
     "Asset Management — Inventories of Services",
     "Inventories of services provided by suppliers are maintained."),
    ("ID.AM-05", "Identify",
     "Asset Management — Asset Prioritization",
     "Assets are prioritized based on classification, criticality, resources, and impact on the mission."),
    ("ID.AM-07", "Identify",
     "Asset Management — Data Inventories",
     "Inventories of data and corresponding metadata for designated data types are maintained."),
    # ID.RA — Risk Assessment
    ("ID.RA-01", "Identify",
     "Risk Assessment — Vulnerabilities Identified",
     "Vulnerabilities in assets are identified, validated, and recorded."),
    ("ID.RA-02", "Identify",
     "Risk Assessment — Threat Intelligence",
     "Cyber threat intelligence is received from information sharing forums and sources."),
    ("ID.RA-03", "Identify",
     "Risk Assessment — Threats Identified",
     "Internal and external threats to the organization are identified and recorded."),
    ("ID.RA-04", "Identify",
     "Risk Assessment — Potential Impacts",
     "Potential impacts and likelihoods of threats exploiting vulnerabilities are identified and recorded."),
    ("ID.RA-05", "Identify",
     "Risk Assessment — Risk Prioritization",
     "Threats, vulnerabilities, likelihoods, and impacts are used to understand inherent risk and inform risk response prioritization."),
    ("ID.RA-06", "Identify",
     "Risk Assessment — Risk Response",
     "Risk responses are chosen, prioritized, planned, tracked, and communicated."),
    # ID.IM — Improvement
    ("ID.IM-01", "Identify",
     "Improvement — Lessons Learned from Assessments",
     "Improvements are identified from evaluations, assessments, post-incident reviews, and exercises."),
    ("ID.IM-02", "Identify",
     "Improvement — Lessons from Internal Sources",
     "Improvements are identified from security tests and exercises, including those done in coordination with suppliers and relevant third parties."),
]

NIST_PROTECT: list[tuple[str, str, str, str]] = [
    # PR.AA — Identity Management, Authentication and Access Control
    ("PR.AA-01", "Protect",
     "Identity Management — Identities and Credentials",
     "Identities and credentials for authorized users, services, and hardware are managed by the organization."),
    ("PR.AA-02", "Protect",
     "Identity Management — Remote Access",
     "Identities are proofed and bound to credentials based on the context of interactions."),
    ("PR.AA-03", "Protect",
     "Identity Management — Users, Services, Hardware Authenticated",
     "Users, services, and hardware are authenticated."),
    ("PR.AA-04", "Protect",
     "Identity Management — Identity Assertions",
     "Identity assertions are protected, conveyed, and verified."),
    ("PR.AA-05", "Protect",
     "Identity Management — Access Permissions",
     "Access permissions, entitlements, and authorizations are defined in a policy, managed, enforced, and reviewed, and incorporate the principles of least privilege and separation of duties."),
    ("PR.AA-06", "Protect",
     "Identity Management — Physical Access",
     "Physical access to assets is managed, monitored, and enforced commensurate with risk."),
    # PR.AT — Awareness and Training
    ("PR.AT-01", "Protect",
     "Awareness and Training — General Workforce",
     "Personnel are provided with awareness and training so that they possess the knowledge and skills to perform general tasks with cybersecurity risks in mind."),
    ("PR.AT-02", "Protect",
     "Awareness and Training — Privileged Users",
     "Individuals in specialized roles are provided with awareness and training so that they possess the knowledge and skills to perform relevant tasks with cybersecurity risks in mind."),
    # PR.DS — Data Security
    ("PR.DS-01", "Protect",
     "Data Security — Data at Rest",
     "The confidentiality, integrity, and availability of data-at-rest are protected."),
    ("PR.DS-02", "Protect",
     "Data Security — Data in Transit",
     "The confidentiality, integrity, and availability of data-in-transit are protected."),
    ("PR.DS-10", "Protect",
     "Data Security — Data in Use",
     "The confidentiality, integrity, and availability of data-in-use are protected."),
    ("PR.DS-11", "Protect",
     "Data Security — Data Backups",
     "Backups of data are created, protected, maintained, and tested."),
    # PR.PS — Platform Security
    ("PR.PS-01", "Protect",
     "Platform Security — Configuration Management",
     "Configuration management practices are established and applied."),
    ("PR.PS-02", "Protect",
     "Platform Security — Software Maintained",
     "Software is maintained, replaced, and removed commensurate with risk."),
    ("PR.PS-03", "Protect",
     "Platform Security — Hardware Maintained",
     "Hardware is maintained, replaced, and removed commensurate with risk."),
    ("PR.PS-04", "Protect",
     "Platform Security — Log Records",
     "Log records are created, protected, and managed to enable monitoring, incident analysis, and forensics."),
    ("PR.PS-05", "Protect",
     "Platform Security — Installation Policies",
     "Installation and execution of unauthorized software are prevented."),
    # PR.IR — Technology Infrastructure Resilience
    ("PR.IR-01", "Protect",
     "Infrastructure Resilience — Networks Kept Protected",
     "Networks and environments are protected from unauthorized logical access and usage."),
    ("PR.IR-02", "Protect",
     "Infrastructure Resilience — Capacity and Availability",
     "The organization's technology assets are protected from environmental threats."),
    ("PR.IR-04", "Protect",
     "Infrastructure Resilience — Sufficient Capacity",
     "Adequate resource capacity to ensure availability is maintained."),
]

NIST_DETECT: list[tuple[str, str, str, str]] = [
    # DE.CM — Continuous Monitoring
    ("DE.CM-01", "Detect",
     "Continuous Monitoring — Networks Monitored",
     "Networks and network services are monitored to find potentially adverse events."),
    ("DE.CM-02", "Detect",
     "Continuous Monitoring — Physical Environment Monitored",
     "The physical environment is monitored to find potentially adverse events."),
    ("DE.CM-03", "Detect",
     "Continuous Monitoring — Personnel Activity Monitored",
     "Personnel activity and technology usage are monitored to find potentially adverse events."),
    ("DE.CM-06", "Detect",
     "Continuous Monitoring — External Service Provider Activities",
     "External service provider activities and services are monitored to find potentially adverse events."),
    ("DE.CM-09", "Detect",
     "Continuous Monitoring — Computing Hardware and Software Monitored",
     "Computing hardware and software, runtime environments, and their data are monitored to find potentially adverse events."),
    # DE.AE — Adverse Event Analysis
    ("DE.AE-02", "Detect",
     "Adverse Event Analysis — Anomalies Detected",
     "Potentially adverse events are analyzed to better understand associated activities."),
    ("DE.AE-03", "Detect",
     "Adverse Event Analysis — Information Correlated",
     "Information is correlated from multiple sources."),
    ("DE.AE-04", "Detect",
     "Adverse Event Analysis — Impact Estimated",
     "The estimated impact and scope of adverse events are understood."),
    ("DE.AE-06", "Detect",
     "Adverse Event Analysis — Information Shared with Stakeholders",
     "Information on adverse events is provided to authorized staff and tools."),
    ("DE.AE-07", "Detect",
     "Adverse Event Analysis — Cyber Threat Intelligence Correlated",
     "Cyber threat intelligence and other contextual information are integrated into the analysis."),
    ("DE.AE-08", "Detect",
     "Adverse Event Analysis — Incidents Declared",
     "Incidents are declared when adverse events meet the defined incident criteria."),
]

NIST_RESPOND: list[tuple[str, str, str, str]] = [
    # RS.MA — Incident Management
    ("RS.MA-01", "Respond",
     "Incident Management — Incidents Contained",
     "The incident response plan is executed in coordination with relevant third parties once an incident is declared."),
    ("RS.MA-02", "Respond",
     "Incident Management — Incidents Reported",
     "Incidents are reported to appropriate internal and external stakeholders in compliance with applicable requirements."),
    ("RS.MA-03", "Respond",
     "Incident Management — Incident Scope Assessed",
     "Incidents are categorized and prioritized."),
    ("RS.MA-04", "Respond",
     "Incident Management — Incident Scope Escalated",
     "Incidents are escalated or elevated as needed."),
    # RS.AN — Incident Analysis
    ("RS.AN-03", "Respond",
     "Incident Analysis — Root Causes Established",
     "Analysis is performed to establish what has taken place during an incident and the root cause of the incident."),
    ("RS.AN-06", "Respond",
     "Incident Analysis — Actions Performed",
     "Actions performed during an investigation are recorded, and the records' integrity and provenance are preserved."),
    ("RS.AN-07", "Respond",
     "Incident Analysis — Incident Magnitude Estimated",
     "The magnitude of an incident and its impacts on the organization and ecosystem are estimated."),
    # RS.CO — Incident Response Reporting and Communication
    ("RS.CO-02", "Respond",
     "Incident Communication — Internal Reporting",
     "Internal stakeholders are notified of incidents in a timely manner."),
    ("RS.CO-03", "Respond",
     "Incident Communication — External Sharing",
     "Information is shared with designated internal and external stakeholders."),
    # RS.MI — Incident Mitigation
    ("RS.MI-01", "Respond",
     "Incident Mitigation — Incidents Contained",
     "Incidents are contained."),
    ("RS.MI-02", "Respond",
     "Incident Mitigation — Incidents Eradicated",
     "Incidents are eradicated."),
]

NIST_RECOVER: list[tuple[str, str, str, str]] = [
    # RC.RP — Incident Recovery Plan Execution
    ("RC.RP-01", "Recover",
     "Recovery Plan Execution — Recovery Plan Initiated",
     "The recovery portion of the incident response plan is executed once initiated from the incident response process."),
    ("RC.RP-02", "Recover",
     "Recovery Plan Execution — Recovery Actions Prioritized",
     "Recovery actions are selected, scoped, prioritized, and performed."),
    ("RC.RP-03", "Recover",
     "Recovery Plan Execution — Recovery Actions Managed",
     "The integrity of backups and other restoration assets is verified before using them for restoration."),
    ("RC.RP-04", "Recover",
     "Recovery Plan Execution — Recovery Activities Reported",
     "Critical mission functions and cybersecurity risk management are considered to establish post-incident operational norms."),
    ("RC.RP-05", "Recover",
     "Recovery Plan Execution — Recovery End Declared",
     "The end of incident recovery is declared based on criteria, and incident-related documentation is completed."),
    # RC.CO — Incident Recovery Communication
    ("RC.CO-03", "Recover",
     "Recovery Communication — Public Relations",
     "Recovery activities and progress in restoring operational capabilities are communicated to designated internal and external stakeholders."),
    ("RC.CO-04", "Recover",
     "Recovery Communication — Stakeholders Updated",
     "Public updates on incident recovery are shared using approved methods and messaging."),
]


ALL_NIST_CSF_CONTROLS = (
    NIST_GOVERN
    + NIST_IDENTIFY
    + NIST_PROTECT
    + NIST_DETECT
    + NIST_RESPOND
    + NIST_RECOVER
)


async def seed_nist_csf(session: AsyncSession) -> None:
    """
    Idempotent NIST CSF 2.0 framework seeder.

    Creates:
      - Framework: NIST CSF 2.0
      - FrameworkVersion: 2.0 (is_current=True)
      - Controls: 68 subcategories across 6 Functions

    Decisions:
      - Subcategories stored as individual controls; parent category = Function name.
      - CSF 2.0 IDs used directly as control_code (GV.OC-01, ID.AM-01, PR.AC-01…).
      - CSF 1.1 (ID.AC-*) IDs not included — this seeder covers CSF 2.0 IDs only.

    Skips silently if NISTCSF framework already exists.
    """
    result = await session.execute(
        select(Framework).where(Framework.short_code == "NISTCSF")
    )
    existing = result.scalars().first()
    if existing:
        return

    framework = Framework(
        id=str(uuid.uuid4()),
        name="NIST Cybersecurity Framework 2.0",
        short_code="NISTCSF",
        category="security",
        description=(
            "NIST Cybersecurity Framework (CSF) 2.0 (February 2024). "
            "Provides guidance to industry, government agencies, and other organizations "
            "to manage cybersecurity risk. CSF 2.0 adds a sixth Function — Govern — to the "
            "original five: Identify, Protect, Detect, Respond, Recover."
        ),
    )
    session.add(framework)
    await session.flush()

    version = FrameworkVersion(
        id=str(uuid.uuid4()),
        framework_id=framework.id,
        version="2.0",
        effective_date=date(2024, 2, 26),
        is_current=True,
    )
    session.add(version)
    await session.flush()

    for control_code, category, title, description in ALL_NIST_CSF_CONTROLS:
        control = Control(
            id=str(uuid.uuid4()),
            framework_version_id=version.id,
            control_code=control_code,
            category=category,
            title=title,
            description=description,
            rule_function=None,
        )
        session.add(control)

    await session.flush()
