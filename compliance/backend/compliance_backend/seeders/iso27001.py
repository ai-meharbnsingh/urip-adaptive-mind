"""
ISO/IEC 27001:2022 Annex A seeder.

Covers the 2022 revision of ISO/IEC 27001 Annex A controls.
The 2022 revision reorganized the original 2013 controls into 4 themes:
  - Organizational controls (5.1 – 5.37)     — 37 controls
  - People controls (6.1 – 6.8)              — 8 controls
  - Physical controls (7.1 – 7.14)           — 14 controls
  - Technological controls (8.1 – 8.34)      — 34 controls
Total: 93 controls

This seeder covers at least 50 controls (per Phase 2B.2.4 scope).
We seed all Organizational + People + Physical + 20 key Technological controls.

Sources: ISO/IEC 27001:2022 Annex A (public summary / official mapping documents).

Idempotent: skip if ISO27001 framework already exists.
"""
import uuid
from datetime import date
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from compliance_backend.models.framework import Framework, FrameworkVersion, Control


# ---------------------------------------------------------------------------
# ISO 27001:2022 Annex A controls
# Format: (control_code, category, title, description)
# Categories: Organizational | People | Physical | Technological
# ---------------------------------------------------------------------------

ISO27001_ORGANIZATIONAL: list[tuple[str, str, str, str]] = [
    ("5.1", "Organizational",
     "Policies for information security",
     "Information security policy and topic-specific policies shall be defined, approved by management, published, communicated to, and acknowledged by relevant personnel."),
    ("5.2", "Organizational",
     "Information security roles and responsibilities",
     "Information security roles and responsibilities shall be defined and allocated according to the organization needs."),
    ("5.3", "Organizational",
     "Segregation of duties",
     "Conflicting duties and conflicting areas of responsibility shall be segregated."),
    ("5.4", "Organizational",
     "Management responsibilities",
     "Management shall require all personnel to apply information security in accordance with the established information security policy."),
    ("5.5", "Organizational",
     "Contact with authorities",
     "The organization shall establish and maintain contact with relevant authorities."),
    ("5.6", "Organizational",
     "Contact with special interest groups",
     "The organization shall establish and maintain contact with special interest groups or other specialist security forums."),
    ("5.7", "Organizational",
     "Threat intelligence",
     "Information relating to information security threats shall be collected and analysed to produce threat intelligence."),
    ("5.8", "Organizational",
     "Information security in project management",
     "Information security shall be integrated into project management."),
    ("5.9", "Organizational",
     "Inventory of information and other associated assets",
     "An inventory of information and other associated assets, including owners, shall be developed and maintained."),
    ("5.10", "Organizational",
     "Acceptable use of information and other associated assets",
     "Rules for the acceptable use and procedures for handling information and other associated assets shall be identified, documented and implemented."),
    ("5.11", "Organizational",
     "Return of assets",
     "Personnel and other interested parties shall return all the organization's assets in their possession upon change or termination of their employment, contract or agreement."),
    ("5.12", "Organizational",
     "Classification of information",
     "Information shall be classified according to the information security needs of the organization."),
    ("5.13", "Organizational",
     "Labelling of information",
     "An appropriate set of procedures for information labelling shall be developed and implemented."),
    ("5.14", "Organizational",
     "Information transfer",
     "Information transfer rules, procedures, or agreements shall be in place for all types of transfer facilities."),
    ("5.15", "Organizational",
     "Access control",
     "Rules to control physical and logical access to information and other associated assets shall be established and implemented."),
    ("5.16", "Organizational",
     "Identity management",
     "The full life cycle of identities shall be managed."),
    ("5.17", "Organizational",
     "Authentication information",
     "Allocation and management of authentication information shall be controlled by a management process."),
    ("5.18", "Organizational",
     "Access rights",
     "Access rights to information and other associated assets shall be provisioned, reviewed, modified and removed in accordance with the organization's topic-specific policy on access control."),
    ("5.19", "Organizational",
     "Information security in supplier relationships",
     "Processes and procedures shall be defined and implemented to manage the information security risks associated with the use of supplier's products or services."),
    ("5.20", "Organizational",
     "Addressing information security within supplier agreements",
     "Relevant information security requirements shall be established and agreed with each supplier."),
    ("5.21", "Organizational",
     "Managing information security in the ICT supply chain",
     "Processes and procedures shall be defined and implemented to manage the information security risks associated with the ICT products and services supply chain."),
    ("5.22", "Organizational",
     "Monitoring, review and change management of supplier services",
     "The organization shall regularly monitor, review, evaluate and manage change in supplier information security practices and service delivery."),
    ("5.23", "Organizational",
     "Information security for use of cloud services",
     "Processes for acquisition, use, management and exit from cloud services shall be established in accordance with the organization's information security requirements."),
    ("5.24", "Organizational",
     "Information security incident management planning and preparation",
     "The organization shall plan and prepare for managing information security incidents by defining, establishing and communicating information security incident management processes."),
    ("5.25", "Organizational",
     "Assessment and decision on information security events",
     "The organization shall assess information security events and decide if they are to be categorized as information security incidents."),
    ("5.26", "Organizational",
     "Response to information security incidents",
     "Information security incidents shall be responded to in accordance with the documented procedures."),
    ("5.27", "Organizational",
     "Learning from information security incidents",
     "Knowledge gained from information security incidents shall be used to strengthen and improve the information security controls."),
    ("5.28", "Organizational",
     "Collection of evidence",
     "The organization shall establish and implement procedures for the identification, collection, acquisition and preservation of evidence related to information security events."),
    ("5.29", "Organizational",
     "Information security during disruption",
     "The organization shall plan how to maintain information security at an appropriate level during disruption."),
    ("5.30", "Organizational",
     "ICT readiness for business continuity",
     "ICT readiness shall be planned, implemented, maintained and tested based on business continuity objectives and ICT continuity requirements."),
    ("5.31", "Organizational",
     "Legal, statutory, regulatory and contractual requirements",
     "Legal, statutory, regulatory and contractual requirements relevant to information security and the organization's approach to meet these requirements shall be identified, documented and kept up to date."),
    ("5.32", "Organizational",
     "Intellectual property rights",
     "The organization shall implement appropriate procedures to protect intellectual property rights."),
    ("5.33", "Organizational",
     "Protection of records",
     "Records shall be protected from loss, destruction, falsification, unauthorized access and unauthorized release."),
    ("5.34", "Organizational",
     "Privacy and protection of personal identifiable information (PII)",
     "The organization shall identify and meet the requirements regarding the preservation of privacy and protection of PII."),
    ("5.35", "Organizational",
     "Independent review of information security",
     "The organization's approach to managing information security and its implementation shall be reviewed independently at planned intervals."),
    ("5.36", "Organizational",
     "Compliance with policies, rules and standards for information security",
     "Compliance with the organization's information security policy, topic-specific policies, rules and standards shall be regularly reviewed."),
    ("5.37", "Organizational",
     "Documented operating procedures",
     "Operating procedures for information processing facilities shall be documented and made available to personnel who need them."),
]


ISO27001_PEOPLE: list[tuple[str, str, str, str]] = [
    ("6.1", "People",
     "Screening",
     "Background verification checks on all candidates for employment shall be carried out prior to joining the organization and on an ongoing basis."),
    ("6.2", "People",
     "Terms and conditions of employment",
     "The employment contractual agreements shall state the personnel's and the organization's responsibilities for information security."),
    ("6.3", "People",
     "Information security awareness, education and training",
     "Personnel of the organization and relevant interested parties shall receive appropriate information security awareness, education and training."),
    ("6.4", "People",
     "Disciplinary process",
     "A disciplinary process shall be formalized and communicated to take actions against personnel who have committed an information security policy violation."),
    ("6.5", "People",
     "Responsibilities after termination or change of employment",
     "Information security responsibilities and duties that remain valid after termination or change of employment shall be defined, enforced and communicated to relevant personnel."),
    ("6.6", "People",
     "Confidentiality or non-disclosure agreements",
     "Confidentiality or non-disclosure agreements reflecting the organization's needs for the protection of information shall be identified, documented, regularly reviewed and signed by personnel."),
    ("6.7", "People",
     "Remote working",
     "Security measures shall be implemented when personnel are working remotely to protect information accessed, processed or stored outside the organization's premises."),
    ("6.8", "People",
     "Information security event reporting",
     "The organization shall provide a mechanism for personnel to report observed or suspected information security events through appropriate channels in a timely manner."),
]


ISO27001_PHYSICAL: list[tuple[str, str, str, str]] = [
    ("7.1", "Physical",
     "Physical security perimeters",
     "Security perimeters shall be defined and used to protect areas that contain information and other associated assets."),
    ("7.2", "Physical",
     "Physical entry",
     "Secure areas shall be protected by appropriate entry controls and access points."),
    ("7.3", "Physical",
     "Securing offices, rooms and facilities",
     "Physical security for offices, rooms and facilities shall be designed and implemented."),
    ("7.4", "Physical",
     "Physical security monitoring",
     "Premises shall be continuously monitored for unauthorized physical access."),
    ("7.5", "Physical",
     "Protecting against physical and environmental threats",
     "Protection against physical and environmental threats such as natural disasters and other intentional or unintentional physical threats to infrastructure shall be designed and implemented."),
    ("7.6", "Physical",
     "Working in secure areas",
     "Security measures for working in secure areas shall be designed and implemented."),
    ("7.7", "Physical",
     "Clear desk and clear screen",
     "Clear desk rules for papers and removable storage media and clear screen rules for information processing facilities shall be defined and appropriately enforced."),
    ("7.8", "Physical",
     "Equipment siting and protection",
     "Equipment shall be sited securely and protected."),
    ("7.9", "Physical",
     "Security of assets off-premises",
     "Off-site assets shall be protected."),
    ("7.10", "Physical",
     "Storage media",
     "Storage media shall be managed through their life cycle of acquisition, use, transportation and disposal in accordance with the organization's classification scheme."),
    ("7.11", "Physical",
     "Supporting utilities",
     "Information processing facilities shall be protected from power failures and other disruptions caused by failures in supporting utilities."),
    ("7.12", "Physical",
     "Cabling security",
     "Cables carrying power, data or supporting information services shall be protected from interception, interference or damage."),
    ("7.13", "Physical",
     "Equipment maintenance",
     "Equipment shall be maintained correctly to ensure availability, integrity and confidentiality of information."),
    ("7.14", "Physical",
     "Secure disposal or re-use of equipment",
     "Items of equipment containing storage media shall be verified to ensure that any sensitive data and licensed software has been removed or securely overwritten prior to disposal or re-use."),
]


ISO27001_TECHNOLOGICAL: list[tuple[str, str, str, str]] = [
    ("8.1", "Technological",
     "User endpoint devices",
     "Information stored on, processed by or accessible via user endpoint devices shall be protected."),
    ("8.2", "Technological",
     "Privileged access rights",
     "The allocation and use of privileged access rights shall be restricted and managed."),
    ("8.3", "Technological",
     "Information access restriction",
     "Access to information and other associated assets shall be restricted in accordance with the established topic-specific policy on access control."),
    ("8.4", "Technological",
     "Access to source code",
     "Read and write access to source code, development tools and software libraries shall be appropriately managed."),
    ("8.5", "Technological",
     "Secure authentication",
     "Secure authentication technologies and procedures shall be implemented based on information access restrictions."),
    ("8.6", "Technological",
     "Capacity management",
     "The use of resources shall be monitored and adjusted in line with current and expected capacity requirements."),
    ("8.7", "Technological",
     "Protection against malware",
     "Protection against malware shall be implemented and supported by appropriate user awareness."),
    ("8.8", "Technological",
     "Management of technical vulnerabilities",
     "Information about technical vulnerabilities of information systems in use shall be obtained in a timely manner."),
    ("8.9", "Technological",
     "Configuration management",
     "Configurations, including security configurations, of hardware, software, services and networks shall be established, documented, implemented, monitored and reviewed."),
    ("8.10", "Technological",
     "Information deletion",
     "Information stored in information systems, devices or in any other storage media shall be deleted when no longer required."),
    ("8.11", "Technological",
     "Data masking",
     "Data masking shall be used in accordance with the organization's topic-specific policy on access control and other related topic-specific policies."),
    ("8.12", "Technological",
     "Data leakage prevention",
     "Data leakage prevention measures shall be applied to systems, networks and any other devices that process, store or transmit sensitive information."),
    ("8.13", "Technological",
     "Information backup",
     "Backup copies of information, software and systems shall be maintained and regularly tested."),
    ("8.14", "Technological",
     "Redundancy of information processing facilities",
     "Information processing facilities shall be implemented with redundancy sufficient to meet availability requirements."),
    ("8.15", "Technological",
     "Logging",
     "Logs that record activities, exceptions, faults and other relevant events shall be produced, stored, protected and analysed."),
    ("8.16", "Technological",
     "Monitoring activities",
     "Networks, systems and applications shall be monitored for anomalous behaviour and appropriate actions taken to evaluate potential information security incidents."),
    ("8.17", "Technological",
     "Clock synchronization",
     "The clocks of information processing systems used by the organization shall be synchronized to approved time sources."),
    ("8.18", "Technological",
     "Use of privileged utility programs",
     "The use of utility programs that might be capable of overriding system and application controls shall be restricted and tightly controlled."),
    ("8.19", "Technological",
     "Installation of software on operational systems",
     "Procedures and measures shall be implemented to securely manage software installation on operational systems."),
    ("8.20", "Technological",
     "Networks security",
     "Networks and network devices shall be secured, managed and controlled to protect information in systems and applications."),
    ("8.21", "Technological",
     "Security of network services",
     "Security mechanisms, service levels and service requirements of network services shall be identified, implemented and monitored."),
    ("8.22", "Technological",
     "Segregation of networks",
     "Groups of information services, users and information systems shall be segregated in the organization's networks."),
    ("8.23", "Technological",
     "Web filtering",
     "Access to external websites shall be managed to reduce exposure to malicious content."),
    ("8.24", "Technological",
     "Use of cryptography",
     "Rules for the effective use of cryptography, including cryptographic key management, shall be defined and implemented."),
    ("8.25", "Technological",
     "Secure development life cycle",
     "Rules for the secure development of software and systems shall be established and applied."),
    ("8.26", "Technological",
     "Application security requirements",
     "Information security requirements shall be identified, specified and approved when developing or acquiring applications."),
    ("8.27", "Technological",
     "Secure system architecture and engineering principles",
     "Principles for engineering secure systems shall be established, documented, maintained and applied to any information system development activities."),
    ("8.28", "Technological",
     "Secure coding",
     "Secure coding principles shall be applied to software development."),
    ("8.29", "Technological",
     "Security testing in development and acceptance",
     "Security testing processes shall be defined and implemented in the development life cycle."),
    ("8.30", "Technological",
     "Outsourced development",
     "The organization shall direct, monitor and review the activities related to outsourced system development."),
    ("8.31", "Technological",
     "Separation of development, test and production environments",
     "Development, testing and production environments shall be separated and secured."),
    ("8.32", "Technological",
     "Change management",
     "Changes to information processing facilities and information systems shall be subject to change management procedures."),
    ("8.33", "Technological",
     "Test information",
     "Test information shall be appropriately selected, protected and managed."),
    ("8.34", "Technological",
     "Protection of information systems during audit testing",
     "Audit tests and other assurance activities involving assessment of operational systems shall be planned and agreed between the tester and appropriate management."),
]


ALL_ISO27001_CONTROLS = (
    ISO27001_ORGANIZATIONAL
    + ISO27001_PEOPLE
    + ISO27001_PHYSICAL
    + ISO27001_TECHNOLOGICAL
)


async def seed_iso27001(session: AsyncSession) -> None:
    """
    Idempotent ISO/IEC 27001:2022 Annex A seeder.

    Creates:
      - Framework: ISO/IEC 27001:2022
      - FrameworkVersion: 2022 (is_current=True)
      - Controls: all 93 Annex A controls across 4 categories

    Skips silently if ISO27001 framework already exists.
    """
    # Idempotency check
    result = await session.execute(
        select(Framework).where(Framework.short_code == "ISO27001")
    )
    existing = result.scalars().first()
    if existing:
        return

    # Create framework
    framework = Framework(
        id=str(uuid.uuid4()),
        name="ISO/IEC 27001",
        short_code="ISO27001",
        category="security",
        description=(
            "ISO/IEC 27001:2022 — Information Security Management Systems Requirements. "
            "Annex A contains 93 controls organized into 4 themes: Organizational, People, "
            "Physical, and Technological."
        ),
    )
    session.add(framework)
    await session.flush()

    # Create version (2022 is current)
    version = FrameworkVersion(
        id=str(uuid.uuid4()),
        framework_id=framework.id,
        version="2022",
        effective_date=date(2022, 10, 25),
        is_current=True,
    )
    session.add(version)
    await session.flush()

    # Create controls
    for control_code, category, title, description in ALL_ISO27001_CONTROLS:
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
