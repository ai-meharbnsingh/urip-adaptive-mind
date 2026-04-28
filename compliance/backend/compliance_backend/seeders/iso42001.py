"""
ISO/IEC 42001:2023 — Artificial Intelligence Management System (AIMS) seeder.

ISO 42001 is the world's first management-system standard for AI, published
December 2023. It is the AI counterpart to ISO 27001 (security) and 27701
(privacy) — providing requirements + Annex A controls for organisations that
develop, provide or use AI systems.

Annex A of the standard contains 38 controls organised across 9 control
objectives (A.2 – A.10). This seeder covers all 38 Annex A controls.

Sources (verified, public):
  - ISO/IEC 42001:2023 official abstract: https://www.iso.org/standard/81230.html
  - Annex A control list (public summaries):
      https://www.a-lign.com/articles/iso-42001-annex-a-controls
      https://www.kpmg.com/us/en/articles/2024/iso-42001-ai-management-system.html
      https://www.itgovernance.eu/blog/en/iso-iec-42001-ai-management-system

Idempotent: skip if framework already exists.
"""
import uuid
from datetime import date
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from compliance_backend.models.framework import Framework, FrameworkVersion, Control


FRAMEWORK_SHORT_CODE = "ISO42001"
FRAMEWORK_NAME = "ISO/IEC 42001:2023 — AI Management System"
FRAMEWORK_VERSION = "2023"
REFERENCE_URL = "https://www.iso.org/standard/81230.html"


# ---------------------------------------------------------------------------
# ISO 42001 Annex A — 38 controls across 9 objectives (A.2 – A.10)
# Format: (control_code, category, title, description)
# ---------------------------------------------------------------------------

ISO42001_A2_POLICIES: list[tuple[str, str, str, str]] = [
    # A.2 — Policies related to AI
    ("A.2.2", "AI Policies",
     "AI Policy",
     "The organization shall document a policy for the development or use of AI systems, signed off by top management and reviewed at planned intervals."),
    ("A.2.3", "AI Policies",
     "Alignment with other organizational policies",
     "The AI policy shall align with other organizational policies (e.g., information security, privacy, ethics) so that AI activities do not violate broader commitments."),
    ("A.2.4", "AI Policies",
     "Review of the AI policy",
     "The AI policy shall be reviewed at planned intervals or in response to significant changes (regulatory, technological, or organizational) to ensure continued suitability."),
]

ISO42001_A3_ORG: list[tuple[str, str, str, str]] = [
    # A.3 — Internal organization
    ("A.3.2", "Internal Organization",
     "AI roles and responsibilities",
     "Roles and responsibilities for AI shall be defined and allocated according to the needs of the organization."),
    ("A.3.3", "Internal Organization",
     "Reporting of concerns",
     "The organization shall define and put in place a process to report concerns about the role of AI systems and any impact they may have throughout their lifecycle."),
]

ISO42001_A4_RESOURCES: list[tuple[str, str, str, str]] = [
    # A.4 — Resources for AI systems
    ("A.4.2", "Resources",
     "Resource documentation",
     "The organization shall identify and document the resources required for AI system development and operation, including AI components, data, computing/networking resources, human resources, and tooling."),
    ("A.4.3", "Resources",
     "Data resources",
     "The organization shall document information about the data resources used by the AI system (provenance, preparation, retention, sensitivity, controllers/processors)."),
    ("A.4.4", "Resources",
     "Tooling resources",
     "The organization shall document information about the tooling resources used by the AI system (development frameworks, MLOps platforms, third-party libraries, model registries)."),
    ("A.4.5", "Resources",
     "System and computing resources",
     "The organization shall document information about the system and computing resources used by the AI system (hardware, cloud services, accelerators, scaling capacity)."),
    ("A.4.6", "Resources",
     "Human resources",
     "The organization shall document information about the human resources and competencies required (data scientists, ML engineers, domain experts, governance staff)."),
]

ISO42001_A5_IMPACT: list[tuple[str, str, str, str]] = [
    # A.5 — Assessing impacts of AI systems
    ("A.5.2", "AI System Impact Assessment",
     "AI system impact assessment process",
     "The organization shall establish a process to assess the potential consequences of AI systems on individuals, groups, and society throughout the AI system lifecycle."),
    ("A.5.3", "AI System Impact Assessment",
     "Documentation of AI system impact assessments",
     "The organization shall document the results of AI system impact assessments and retain this documentation for the lifetime of the AI system."),
    ("A.5.4", "AI System Impact Assessment",
     "Assessing AI system impact on individuals or groups of individuals",
     "The organization shall assess and document potential impacts of AI systems to individuals or groups of individuals throughout their lifecycle."),
    ("A.5.5", "AI System Impact Assessment",
     "Assessing societal impacts of AI systems",
     "The organization shall assess and document societal impacts of its AI systems throughout their lifecycle, including unintended uses and downstream effects."),
]

ISO42001_A6_LIFECYCLE: list[tuple[str, str, str, str]] = [
    # A.6 — AI system life cycle
    ("A.6.1.2", "AI Lifecycle",
     "Objectives for responsible development of AI system",
     "The organization shall identify and document objectives to guide responsible development of AI systems."),
    ("A.6.1.3", "AI Lifecycle",
     "Processes for responsible AI system design and development",
     "The organization shall define and document specific processes for the responsible design and development of AI systems."),
    ("A.6.2.2", "AI Lifecycle",
     "AI system requirements and specification",
     "The organization shall specify and document requirements for new AI systems or substantial modifications to existing AI systems."),
    ("A.6.2.3", "AI Lifecycle",
     "Documentation of AI system design and development",
     "The organization shall document the design and development of the AI system, including architecture, algorithms, hyperparameters, training methodology, and evaluation criteria."),
    ("A.6.2.4", "AI Lifecycle",
     "AI system verification and validation",
     "The organization shall define and document verification and validation measures for the AI system, including acceptance criteria and test data."),
    ("A.6.2.5", "AI Lifecycle",
     "AI system deployment",
     "The organization shall document a deployment plan for the AI system that addresses prerequisites, environment, monitoring readiness, rollback procedures and stakeholder communications."),
    ("A.6.2.6", "AI Lifecycle",
     "AI system operation and monitoring",
     "The organization shall define and document the operational requirements of the AI system, including performance and quality monitoring, drift detection, and incident escalation."),
    ("A.6.2.7", "AI Lifecycle",
     "AI system technical documentation",
     "The organization shall maintain technical documentation about the AI system to enable required parties to assess its performance, behaviour, and limitations."),
    ("A.6.2.8", "AI Lifecycle",
     "AI system event logs",
     "The organization shall determine which events should be logged by the AI system and the level of detail required (decisions, training events, model updates, anomalies)."),
]

ISO42001_A7_DATA: list[tuple[str, str, str, str]] = [
    # A.7 — Data for AI systems
    ("A.7.2", "Data for AI",
     "Data for development and enhancement of AI systems",
     "The organization shall define, document and implement data management processes for AI system development and enhancement."),
    ("A.7.3", "Data for AI",
     "Acquisition of data",
     "The organization shall determine and document data acquisition criteria, including provenance, lawful basis, lineage and rights to use."),
    ("A.7.4", "Data for AI",
     "Quality of data for AI systems",
     "The organization shall establish data quality requirements (accuracy, completeness, representativeness, timeliness) appropriate to the intended use of the AI system."),
    ("A.7.5", "Data for AI",
     "Data provenance",
     "The organization shall define and document a process for recording the provenance of data used in the AI system across its lifecycle."),
    ("A.7.6", "Data for AI",
     "Data preparation",
     "The organization shall define and document data preparation criteria and methods (cleaning, normalisation, labelling, augmentation, anonymisation) used by the AI system."),
]

ISO42001_A8_INFO: list[tuple[str, str, str, str]] = [
    # A.8 — Information for interested parties of AI systems
    ("A.8.2", "Information for Interested Parties",
     "System documentation and information for users",
     "The organization shall make information about the AI system available to users (capabilities, limitations, intended use, conditions of operation)."),
    ("A.8.3", "Information for Interested Parties",
     "External reporting",
     "The organization shall provide a means for interested parties (regulators, affected individuals) to report adverse impacts arising from the AI system."),
    ("A.8.4", "Information for Interested Parties",
     "Communication of incidents",
     "The organization shall determine, document and respond to information needs of interested parties about AI system incidents (including affected end users and regulators)."),
    ("A.8.5", "Information for Interested Parties",
     "Information for interested parties about the AI system",
     "The organization shall determine and document its approach to providing information about the AI system to interested parties (transparency notices, model cards, datasheets)."),
]

ISO42001_A9_USE: list[tuple[str, str, str, str]] = [
    # A.9 — Use of AI systems
    ("A.9.2", "Use of AI Systems",
     "Processes for responsible use of AI systems",
     "The organization shall define and document processes for the responsible use of AI systems by employees, contractors and external users."),
    ("A.9.3", "Use of AI Systems",
     "Objectives for responsible use of AI system",
     "The organization shall identify objectives for the responsible use of the AI system, aligned with policies and ethical commitments."),
    ("A.9.4", "Use of AI Systems",
     "Intended use of the AI system",
     "The organization shall ensure that the AI system is used in accordance with its intended purpose and limits of use, and that out-of-scope use is restricted."),
]

ISO42001_A10_THIRD: list[tuple[str, str, str, str]] = [
    # A.10 — Third-party and customer relationships
    ("A.10.2", "Third-Party Relationships",
     "Allocation of responsibilities",
     "The organization shall ensure responsibilities and accountabilities within its AI system lifecycle are allocated between the organization, partners, suppliers, customers and third parties."),
    ("A.10.3", "Third-Party Relationships",
     "Suppliers",
     "The organization shall establish a process to ensure that the use of services, products, components or materials from suppliers aligns with the organization's responsible AI approach."),
    ("A.10.4", "Third-Party Relationships",
     "Customers",
     "The organization shall ensure responsible expectations of customers regarding the AI system are documented and considered."),
]

# Additional clauses from ISO 42001 main body and risk-treatment specifics
# (the standard enumerates these alongside Annex A)
ISO42001_RISK_AND_OPERATION: list[tuple[str, str, str, str]] = [
    ("Cl.6.1.2", "AI Risk Management",
     "AI risk assessment",
     "The organization shall define and apply an AI risk assessment process that produces consistent, valid and comparable results, identifying risks associated with the development, provision or use of AI systems."),
    ("Cl.6.1.3", "AI Risk Management",
     "AI risk treatment",
     "The organization shall define and apply an AI risk treatment process to select appropriate risk treatment options and determine necessary controls (including from Annex A)."),
    ("Cl.6.1.4", "AI Risk Management",
     "AI system impact assessment integration",
     "AI risk treatment shall integrate the results of the AI system impact assessment process so that risk decisions reflect impacts on individuals, groups, and society."),
    ("Cl.8.3", "AI Operational Controls",
     "AI system impact assessment performance",
     "The organization shall perform AI system impact assessments at planned intervals and when significant changes occur, retaining documented information of the results."),
    ("Cl.9.1", "Performance Evaluation",
     "Monitoring, measurement, analysis and evaluation",
     "The organization shall determine what needs to be monitored and measured for the AI management system, and shall analyse and evaluate the results to assess performance and effectiveness."),
    ("Cl.10.1", "Improvement",
     "Continual improvement",
     "The organization shall continually improve the suitability, adequacy and effectiveness of the AI management system, including in response to nonconformities and audit results."),
]


ALL_ISO42001_CONTROLS = (
    ISO42001_A2_POLICIES
    + ISO42001_A3_ORG
    + ISO42001_A4_RESOURCES
    + ISO42001_A5_IMPACT
    + ISO42001_A6_LIFECYCLE
    + ISO42001_A7_DATA
    + ISO42001_A8_INFO
    + ISO42001_A9_USE
    + ISO42001_A10_THIRD
    + ISO42001_RISK_AND_OPERATION
)


async def seed_iso42001(session: AsyncSession) -> None:
    """Idempotent ISO/IEC 42001:2023 seeder."""
    result = await session.execute(
        select(Framework).where(Framework.short_code == FRAMEWORK_SHORT_CODE)
    )
    if result.scalars().first():
        return

    framework = Framework(
        id=str(uuid.uuid4()),
        name=FRAMEWORK_NAME,
        short_code=FRAMEWORK_SHORT_CODE,
        category="ai_governance",
        description=(
            "ISO/IEC 42001:2023 — Artificial Intelligence Management System (AIMS). "
            "First international management-system standard for AI, providing 38 Annex A "
            "controls across 9 objectives covering AI policies, organization, resources, "
            "impact assessment, lifecycle, data, information for interested parties, use, "
            "and third-party relationships."
        ),
    )
    session.add(framework)
    await session.flush()

    version = FrameworkVersion(
        id=str(uuid.uuid4()),
        framework_id=framework.id,
        version=FRAMEWORK_VERSION,
        effective_date=date(2023, 12, 18),
        is_current=True,
    )
    session.add(version)
    await session.flush()

    for control_code, category, title, description in ALL_ISO42001_CONTROLS:
        session.add(Control(
            id=str(uuid.uuid4()),
            framework_version_id=version.id,
            control_code=control_code,
            category=category,
            title=title,
            description=description,
            rule_function=None,
        ))

    await session.flush()
