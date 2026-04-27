"""
SOC 2 Trust Services Criteria seeder.

Covers TSC 2017 (original) with 2022 updates incorporated.
All 5 Trust Services Categories:
  - Security (CC1–CC9)              — Common Criteria
  - Availability (A1)
  - Processing Integrity (PI1)
  - Confidentiality (C1)
  - Privacy (P1–P8)

Control count: 60 controls across both versions (30 per version minimum).
Sources: AICPA Trust Services Criteria 2017 + 2022 updates (public document).

Idempotent: skip if SOC2 framework already exists.
"""
import uuid
from datetime import date
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from compliance_backend.models.framework import Framework, FrameworkVersion, Control


# ---------------------------------------------------------------------------
# SOC 2 Trust Services Criteria — structured data
# Format: (control_code, category, title, description)
# ---------------------------------------------------------------------------

SOC2_COMMON_CRITERIA: list[tuple[str, str, str, str]] = [
    # ── CC1 — Control Environment ──────────────────────────────────────────
    ("CC1.1", "Security",
     "COSO Principle 1 — Commitment to Integrity and Ethical Values",
     "The entity demonstrates a commitment to integrity and ethical values."),
    ("CC1.2", "Security",
     "COSO Principle 2 — Board Independence and Oversight",
     "The board of directors demonstrates independence from management and exercises oversight of the development and performance of internal control."),
    ("CC1.3", "Security",
     "COSO Principle 3 — Organizational Structure",
     "Management establishes, with board oversight, structures, reporting lines, and appropriate authorities and responsibilities."),
    ("CC1.4", "Security",
     "COSO Principle 4 — Commitment to Competence",
     "The entity demonstrates a commitment to attract, develop, and retain competent individuals."),
    ("CC1.5", "Security",
     "COSO Principle 5 — Accountability",
     "The entity holds individuals accountable for their internal control responsibilities."),

    # ── CC2 — Communication and Information ───────────────────────────────
    ("CC2.1", "Security",
     "COSO Principle 13 — Relevant Quality Information",
     "The entity obtains or generates and uses relevant, quality information to support the functioning of internal control."),
    ("CC2.2", "Security",
     "COSO Principle 14 — Internal Communication",
     "The entity internally communicates information, including objectives and responsibilities for internal control."),
    ("CC2.3", "Security",
     "COSO Principle 15 — External Communication",
     "The entity communicates with external parties regarding matters affecting the functioning of internal control."),

    # ── CC3 — Risk Assessment ─────────────────────────────────────────────
    ("CC3.1", "Security",
     "COSO Principle 6 — Specification of Objectives",
     "The entity specifies objectives with sufficient clarity to enable the identification and assessment of risks."),
    ("CC3.2", "Security",
     "COSO Principle 7 — Risk Identification and Analysis",
     "The entity identifies risks to the achievement of its objectives across the entity and analyzes risks as a basis for determining how they should be managed."),
    ("CC3.3", "Security",
     "COSO Principle 8 — Fraud Risk Assessment",
     "The entity considers the potential for fraud in assessing risks to the achievement of objectives."),
    ("CC3.4", "Security",
     "COSO Principle 9 — Change Identification and Assessment",
     "The entity identifies and assesses changes that could significantly impact the system of internal control."),

    # ── CC4 — Monitoring Activities ───────────────────────────────────────
    ("CC4.1", "Security",
     "COSO Principle 16 — Ongoing and Separate Evaluations",
     "The entity selects, develops, and performs ongoing and/or separate evaluations to ascertain whether components of internal control are present and functioning."),
    ("CC4.2", "Security",
     "COSO Principle 17 — Evaluation and Communication of Deficiencies",
     "The entity evaluates and communicates internal control deficiencies in a timely manner."),

    # ── CC5 — Control Activities ──────────────────────────────────────────
    ("CC5.1", "Security",
     "COSO Principle 10 — Selection and Development of Control Activities",
     "The entity selects and develops control activities that contribute to the mitigation of risks."),
    ("CC5.2", "Security",
     "COSO Principle 11 — Technology General Controls",
     "The entity also selects and develops general control activities over technology."),
    ("CC5.3", "Security",
     "COSO Principle 12 — Policy and Procedure Deployment",
     "The entity deploys control activities through policies that establish what is expected."),

    # ── CC6 — Logical and Physical Access ─────────────────────────────────
    ("CC6.1", "Security",
     "Logical Access Security Measures",
     "The entity implements logical access security software, infrastructure, and architectures over protected information assets."),
    ("CC6.2", "Security",
     "Access Provisioning and Modification",
     "Prior to issuing system credentials and granting system access, the entity registers and authorizes new internal and external users."),
    ("CC6.3", "Security",
     "Removal of Access to Protected Information Assets",
     "The entity authorizes, modifies, or removes access to data, software, functions, and other protected information assets based on roles, responsibilities, or the system design."),
    ("CC6.4", "Security",
     "Physical Access Restrictions",
     "The entity restricts physical access to facilities and protected information assets."),
    ("CC6.5", "Security",
     "Logical Access to Protected Assets",
     "The entity discontinues logical and physical protections over physical assets only after the ability to read or recover data and software from those assets has been diminished."),
    ("CC6.6", "Security",
     "Logical Access Through Untrusted Networks",
     "The entity implements controls to prevent or detect and act upon the introduction of unauthorized or malicious software."),
    ("CC6.7", "Security",
     "Transmission, Movement, and Removal of Information",
     "The entity restricts the transmission, movement, and removal of information to authorized internal and external users and processes."),
    ("CC6.8", "Security",
     "Prevention and Detection of Unauthorized Software",
     "The entity implements controls to prevent or detect and act upon the introduction of unauthorized or malicious software."),

    # ── CC7 — System Operations ───────────────────────────────────────────
    ("CC7.1", "Security",
     "Detection of Configuration Vulnerabilities",
     "To meet its objectives, the entity uses detection and monitoring procedures to identify changes to configurations."),
    ("CC7.2", "Security",
     "Monitoring to Detect Anomalies and Security Incidents",
     "The entity monitors system components and the operation of those components for anomalies."),
    ("CC7.3", "Security",
     "Event Evaluation and Incident Identification",
     "The entity evaluates security events to determine whether they could or have resulted in a failure of controls."),
    ("CC7.4", "Security",
     "Incident Response",
     "The entity responds to identified security incidents by executing a defined incident-response program."),
    ("CC7.5", "Security",
     "Recovery from Security Incidents",
     "The entity identifies, develops, and implements activities to recover from identified security incidents."),

    # ── CC8 — Change Management ───────────────────────────────────────────
    ("CC8.1", "Security",
     "Change Management Process",
     "The entity authorizes, designs, develops or acquires, configures, documents, tests, approves, and implements changes to infrastructure, data, software, and procedures."),

    # ── CC9 — Risk Mitigation ─────────────────────────────────────────────
    ("CC9.1", "Security",
     "Risk Mitigation Activities",
     "The entity identifies, selects, and develops risk mitigation activities for risks arising from potential business disruptions."),
    ("CC9.2", "Security",
     "Vendor and Business Partner Management",
     "The entity assesses and manages risks associated with vendors and business partners."),
]


SOC2_AVAILABILITY: list[tuple[str, str, str, str]] = [
    ("A1.1", "Availability",
     "Capacity Management",
     "The entity maintains, monitors, and evaluates current processing capacity and use of system components."),
    ("A1.2", "Availability",
     "Recovery Infrastructure",
     "The entity authorizes, designs, develops or acquires, implements, operates, approves, maintains, and monitors environmental protections, software, data back-up processes, and recovery infrastructure."),
    ("A1.3", "Availability",
     "Recovery Plan Testing",
     "The entity tests recovery plan procedures supporting system availability to meet its objectives."),
]


SOC2_PROCESSING_INTEGRITY: list[tuple[str, str, str, str]] = [
    ("PI1.1", "Processing Integrity",
     "Inputs Processing",
     "The entity obtains or generates, uses, and communicates relevant, quality information regarding the objectives related to processing."),
    ("PI1.2", "Processing Integrity",
     "System Processing",
     "The entity implements policies and procedures over system inputs, including controls over completeness and accuracy."),
    ("PI1.3", "Processing Integrity",
     "Output Processing",
     "The entity implements policies and procedures over system outputs."),
    ("PI1.4", "Processing Integrity",
     "Error Handling",
     "The entity implements policies and procedures to make available or deliver output completely, accurately, and timely in accordance with specifications."),
    ("PI1.5", "Processing Integrity",
     "Stored Information",
     "The entity implements policies and procedures to store inputs, items in processing, and outputs completely, accurately, and timely."),
]


SOC2_CONFIDENTIALITY: list[tuple[str, str, str, str]] = [
    ("C1.1", "Confidentiality",
     "Confidential Information Identification",
     "The entity identifies and maintains confidential information to meet the entity's objectives related to confidentiality."),
    ("C1.2", "Confidentiality",
     "Confidential Information Disposal",
     "The entity disposes of confidential information to meet the entity's objectives related to confidentiality."),
]


SOC2_PRIVACY: list[tuple[str, str, str, str]] = [
    ("P1.1", "Privacy",
     "Privacy Notice",
     "The entity provides notice about its privacy practices to data subjects."),
    ("P2.1", "Privacy",
     "Choice and Consent",
     "The entity communicates choices available regarding the collection, use, retention, disclosure, and disposal of personal information."),
    ("P3.1", "Privacy",
     "Collection of Personal Information",
     "Personal information is collected consistent with the entity's objectives related to privacy."),
    ("P3.2", "Privacy",
     "Explicit Consent for Sensitive Data",
     "For information requiring explicit consent, the entity communicates the need for such consent and obtains the consent prior to the collection."),
    ("P4.1", "Privacy",
     "Use of Personal Information",
     "The entity limits the use of personal information to the purposes identified in the privacy notice."),
    ("P4.2", "Privacy",
     "Retention of Personal Information",
     "The entity retains personal information consistent with the entity's objectives related to privacy."),
    ("P4.3", "Privacy",
     "Disposal of Personal Information",
     "The entity disposes of personal information consistent with the entity's objectives related to privacy."),
    ("P5.1", "Privacy",
     "Access to Personal Information",
     "The entity grants identified and authenticated data subjects the ability to access their stored personal information."),
    ("P5.2", "Privacy",
     "Correction of Personal Information",
     "The entity corrects identified errors in personal information when requested by data subjects."),
    ("P6.1", "Privacy",
     "Disclosure of Personal Information",
     "The entity discloses personal information to third parties with the explicit consent of data subjects."),
    ("P6.2", "Privacy",
     "Disclosure to Third Parties",
     "The entity creates and retains a complete, accurate, and timely record of authorized disclosures of personal information."),
    ("P6.3", "Privacy",
     "Disclosure to Government Entities",
     "The entity creates and retains a complete, accurate, and timely record of detected or reported unauthorized disclosures of personal information."),
    ("P6.4", "Privacy",
     "Notification of Disclosure",
     "The entity notifies data subjects and others of any government agency or regulatory body requests for personal information."),
    ("P6.5", "Privacy",
     "Disclosure for Legal Obligations",
     "The entity discloses personal information when required by law or regulation."),
    ("P6.6", "Privacy",
     "Informing Third Parties",
     "The entity informs data subjects when personal information is disclosed against their preference."),
    ("P6.7", "Privacy",
     "Sharing of Personal Information with Third Parties",
     "The entity limits the disclosure of personal information to parties who have agreed to protect the information."),
    ("P7.1", "Privacy",
     "Quality of Personal Information",
     "The entity collects and maintains accurate, up-to-date, complete, and relevant personal information for the purposes identified in the privacy notice."),
    ("P8.1", "Privacy",
     "Monitoring and Enforcement",
     "The entity monitors compliance with its privacy policies and procedures and has procedures to address privacy-related complaints and disputes."),
]


# All controls combined
ALL_SOC2_CONTROLS = (
    SOC2_COMMON_CRITERIA
    + SOC2_AVAILABILITY
    + SOC2_PROCESSING_INTEGRITY
    + SOC2_CONFIDENTIALITY
    + SOC2_PRIVACY
)


async def seed_soc2(session: AsyncSession) -> None:
    """
    Idempotent SOC 2 framework seeder.

    Creates:
      - Framework: SOC 2
      - FrameworkVersion: 2017 (is_current=True)
      - Controls: 60+ covering all 5 Trust Services Categories

    Skips silently if SOC2 framework already exists.
    """
    # Idempotency check
    result = await session.execute(
        select(Framework).where(Framework.short_code == "SOC2")
    )
    existing = result.scalars().first()
    if existing:
        return  # Already seeded — skip

    # Create framework
    framework = Framework(
        id=str(uuid.uuid4()),
        name="SOC 2",
        short_code="SOC2",
        category="security",
        description=(
            "AICPA System and Organization Controls 2 — Trust Services Criteria. "
            "Evaluates controls relevant to security, availability, processing integrity, "
            "confidentiality, and privacy."
        ),
    )
    session.add(framework)
    await session.flush()  # Get framework.id

    # Create version
    version = FrameworkVersion(
        id=str(uuid.uuid4()),
        framework_id=framework.id,
        version="2017",
        effective_date=date(2017, 4, 1),
        is_current=True,
    )
    session.add(version)
    await session.flush()  # Get version.id

    # Create controls
    for control_code, category, title, description in ALL_SOC2_CONTROLS:
        control = Control(
            id=str(uuid.uuid4()),
            framework_version_id=version.id,
            control_code=control_code,
            category=category,
            title=title,
            description=description,
            rule_function=None,  # Automated rule plugins are Phase 2B.3 scope
        )
        session.add(control)

    await session.flush()
