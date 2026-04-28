"""
DORA — Digital Operational Resilience Act (Regulation (EU) 2022/2554) seeder.

DORA establishes a uniform regulatory framework for the digital operational
resilience of financial entities in the EU. It became applicable on
17 January 2025.

The framework has 5 pillars covered in this seeder:
  1. ICT Risk Management            (Articles 5-15)
  2. ICT-related Incident Management (Articles 17-23)
  3. Digital Operational Resilience Testing (Articles 24-27)
  4. Third-Party Risk (ICT) Management (Articles 28-44)
  5. Information Sharing             (Article 45)

Total controls in this seeder: 56.

Sources (verified, public):
  - Official Journal text (Regulation (EU) 2022/2554):
      https://eur-lex.europa.eu/eli/reg/2022/2554/oj
  - ESAs Joint Committee Q&A:
      https://www.eba.europa.eu/regulation-and-policy/internal-governance/digital-operational-resilience-act-dora
  - EIOPA DORA hub: https://www.eiopa.europa.eu/digital-operational-resilience-act-dora_en

Idempotent: skip if framework already exists.
"""
import uuid
from datetime import date
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from compliance_backend.models.framework import Framework, FrameworkVersion, Control


FRAMEWORK_SHORT_CODE = "DORA"
FRAMEWORK_NAME = "DORA — Digital Operational Resilience Act (EU 2022/2554)"
FRAMEWORK_VERSION = "2022/2554"
REFERENCE_URL = "https://eur-lex.europa.eu/eli/reg/2022/2554/oj"


# ---------------------------------------------------------------------------
# Pillar 1 — ICT Risk Management (Articles 5-15)
# ---------------------------------------------------------------------------
DORA_ICT_RISK: list[tuple[str, str, str, str]] = [
    ("Art. 5(1)", "ICT Risk Management",
     "Governance and organisation",
     "The management body of the financial entity shall define, approve, oversee and be responsible for the implementation of all arrangements related to the ICT risk management framework."),
    ("Art. 5(2)", "ICT Risk Management",
     "Management body responsibilities for ICT risk",
     "The management body shall set policies aimed at ensuring high standards of availability, authenticity, integrity and confidentiality of data; and approve digital operational resilience strategy."),
    ("Art. 6(1)", "ICT Risk Management",
     "ICT risk management framework",
     "Financial entities shall have a sound, comprehensive and well-documented ICT risk management framework as part of their overall risk management system."),
    ("Art. 6(8)", "ICT Risk Management",
     "Internal audit of ICT framework",
     "The ICT risk management framework shall be audited by ICT auditors with sufficient knowledge, skills and expertise in ICT risk on a regular basis."),
    ("Art. 7", "ICT Risk Management",
     "ICT systems, protocols and tools",
     "Financial entities shall use ICT systems, protocols and tools that are appropriate to the magnitude of the operations supporting their activities and that ensure resilience, capacity and security."),
    ("Art. 8(1)", "ICT Risk Management",
     "Identification — ICT-supported business functions",
     "Financial entities shall identify, classify and adequately document all ICT-supported business functions, roles and responsibilities, ICT assets supporting them, and their interdependencies."),
    ("Art. 8(4)", "ICT Risk Management",
     "Identification of ICT risk sources and threats",
     "Financial entities shall identify all sources of ICT risk, including legacy systems, on a continuous basis, and assess cyber threats and ICT vulnerabilities relevant to their operations."),
    ("Art. 9(1)", "ICT Risk Management",
     "Protection and prevention",
     "Financial entities shall continuously monitor and control the security and functioning of ICT systems and tools and minimise the impact of ICT risk on those systems through deployment of appropriate ICT security tools, policies and procedures."),
    ("Art. 9(2)", "ICT Risk Management",
     "ICT security policies — confidentiality, integrity, availability",
     "Financial entities shall design, procure and implement ICT security policies, procedures and protocols to ensure resilience, continuity and availability of ICT systems and to maintain high standards of confidentiality, integrity and availability."),
    ("Art. 9(4)", "ICT Risk Management",
     "Identity and access management",
     "Financial entities shall implement policies and procedures for strong authentication, access management based on the least-privilege and need-to-know principles, and segregation of duties."),
    ("Art. 10(1)", "ICT Risk Management",
     "Detection",
     "Financial entities shall have in place mechanisms to promptly detect anomalous activities, including ICT network performance issues and ICT-related incidents, and to identify potential material single points of failure."),
    ("Art. 11(1)", "ICT Risk Management",
     "Response and recovery — ICT business continuity policy",
     "Financial entities shall put in place a comprehensive ICT business continuity policy as an integral part of operational business continuity, with continuity plans for critical or important functions."),
    ("Art. 11(6)", "ICT Risk Management",
     "ICT response and recovery plans",
     "Financial entities shall implement ICT response and recovery plans subject to independent internal audit reviews, covering data backup procedures and recovery procedures with defined recovery time and point objectives (RTO / RPO)."),
    ("Art. 12(1)", "ICT Risk Management",
     "Backup policies and procedures, restoration and recovery procedures",
     "Financial entities shall develop and document backup policies and procedures, restoration procedures and methods, including geographic distribution of backups."),
    ("Art. 13(1)", "ICT Risk Management",
     "Learning and evolving",
     "Financial entities shall have in place capabilities and staff to gather information on vulnerabilities and cyber threats, ICT-related incidents and analyse their potential impact on the digital operational resilience."),
    ("Art. 14", "ICT Risk Management",
     "Communication",
     "Financial entities shall have a communication plan for personnel, external stakeholders and media regarding ICT-related incidents and significant cyber threats."),
    ("Art. 15", "ICT Risk Management",
     "Further harmonisation of ICT risk management tools",
     "Financial entities shall comply with the regulatory technical standards (RTS) further specifying ICT risk management tools, methods, processes and policies."),
]


# ---------------------------------------------------------------------------
# Pillar 2 — ICT-related Incident Management (Articles 17-23)
# ---------------------------------------------------------------------------
DORA_INCIDENTS: list[tuple[str, str, str, str]] = [
    ("Art. 17(1)", "ICT Incident Management",
     "ICT-related incident management process",
     "Financial entities shall define, establish and implement an ICT-related incident management process to detect, manage and notify ICT-related incidents."),
    ("Art. 17(3)", "ICT Incident Management",
     "Roles and responsibilities for incident handling",
     "The financial entity shall record, track and prioritise ICT-related incidents, define the roles and responsibilities, establish escalation paths, and provide for incident-handling logs."),
    ("Art. 18", "ICT Incident Management",
     "Classification of ICT-related incidents and cyber threats",
     "Financial entities shall classify ICT-related incidents and determine their impact on the basis of criteria specified in regulatory technical standards (number of clients affected, duration, geographical spread, data losses, criticality of services, economic impact)."),
    ("Art. 19(1)", "ICT Incident Management",
     "Reporting of major ICT-related incidents",
     "Financial entities shall report major ICT-related incidents to the relevant competent authority using a harmonised template, with initial, intermediate and final reports."),
    ("Art. 19(4)", "ICT Incident Management",
     "Voluntary notification of significant cyber threats",
     "Financial entities may notify, on a voluntary basis, significant cyber threats to the relevant competent authority where they consider the threat to be of relevance to the financial system."),
    ("Art. 20", "ICT Incident Management",
     "Harmonisation of reporting content and templates",
     "Financial entities shall use the standardised templates and reporting time-windows defined in the regulatory technical standards adopted under DORA for incident reports."),
    ("Art. 21", "ICT Incident Management",
     "Centralisation of reporting",
     "The European Supervisory Authorities (ESAs) shall, through the Joint Committee, set up a single EU hub for major ICT-related incident reporting from financial entities."),
    ("Art. 22", "ICT Incident Management",
     "Supervisory feedback",
     "Without prejudice to applicable supervisory powers, competent authorities receiving incident reports shall, where possible and useful, provide acknowledgement and high-level guidance to the financial entity following submission of the final report."),
    ("Art. 23", "ICT Incident Management",
     "Operational or security payment-related incidents",
     "Operational or security payment-related incidents in the meaning of Directive (EU) 2015/2366 shall be reported in accordance with DORA and the related RTS."),
]


# ---------------------------------------------------------------------------
# Pillar 3 — Digital Operational Resilience Testing (Articles 24-27)
# ---------------------------------------------------------------------------
DORA_TESTING: list[tuple[str, str, str, str]] = [
    ("Art. 24(1)", "Resilience Testing",
     "Digital operational resilience testing programme",
     "Financial entities shall establish, maintain and review a sound and comprehensive digital operational resilience testing programme as an integral part of their ICT risk management framework."),
    ("Art. 24(3)", "Resilience Testing",
     "Independent testers",
     "The digital operational resilience testing programme shall be carried out by independent parties (internal or external) with sufficient knowledge, skills and expertise."),
    ("Art. 25", "Resilience Testing",
     "Testing of ICT tools and systems",
     "Financial entities shall test ICT tools and systems used to support critical or important functions at least yearly, including vulnerability assessments and scans, open-source analyses, network security assessments, gap analyses, physical security reviews, source code reviews, scenario-based tests, compatibility testing, performance testing, and end-to-end testing."),
    ("Art. 26(1)", "Resilience Testing",
     "Threat-led penetration testing (TLPT)",
     "Financial entities, other than microenterprises, that are identified by the competent authority as significant shall carry out threat-led penetration testing at least every 3 years."),
    ("Art. 26(8)", "Resilience Testing",
     "TLPT — third-party providers in scope",
     "Where ICT third-party service providers are included in the scope of TLPT, the financial entity shall take the necessary measures to ensure their participation."),
    ("Art. 27", "Resilience Testing",
     "Requirements for testers carrying out TLPT",
     "TLPT testers shall be of the highest suitability and reputability, technically and organisationally capable, and certified by an accreditation body in a Member State (or comply with formal codes of conduct) and provide adequate professional indemnity insurance."),
]


# ---------------------------------------------------------------------------
# Pillar 4 — Third-Party (ICT) Risk Management (Articles 28-44)
# ---------------------------------------------------------------------------
DORA_THIRD_PARTY: list[tuple[str, str, str, str]] = [
    ("Art. 28(1)", "Third-Party Risk",
     "General principles for ICT third-party risk",
     "Financial entities shall manage ICT third-party risk as an integral component of their ICT risk management framework, in accordance with the principle of proportionality."),
    ("Art. 28(2)", "Third-Party Risk",
     "Strategy on ICT third-party risk",
     "The management body shall regularly review the risks identified in respect of contractual arrangements on the use of ICT services supporting critical or important functions, and adopt and review a strategy on ICT third-party risk."),
    ("Art. 28(3)", "Third-Party Risk",
     "Register of information on contractual arrangements",
     "Financial entities shall maintain and keep up to date a register of information in relation to all contractual arrangements on the use of ICT services provided by ICT third-party service providers, distinguishing those supporting critical or important functions."),
    ("Art. 28(4)", "Third-Party Risk",
     "Reporting of register to competent authorities",
     "Financial entities shall, on a regular basis and at the request of the competent authority, make available to the competent authority the register of information."),
    ("Art. 28(5)", "Third-Party Risk",
     "Reporting of new ICT contracts",
     "Financial entities shall report at least yearly to the competent authority on the number of new arrangements on ICT services, the categories of ICT third-party service providers, the type and content of contractual arrangements and the ICT services and functions provided."),
    ("Art. 29", "Third-Party Risk",
     "Preliminary assessment of ICT concentration risk",
     "Financial entities shall identify and assess concentration risk arising from contracting with a single ICT third-party service provider or a small group of providers, including risk of further sub-contracting."),
    ("Art. 30(1)", "Third-Party Risk",
     "Key contractual provisions — general",
     "The rights and obligations of the financial entity and the ICT third-party service provider shall be clearly allocated and set out in writing, with the full contract available in a single written document."),
    ("Art. 30(2)", "Third-Party Risk",
     "Mandatory contractual provisions — all ICT services",
     "The contractual arrangements on the use of ICT services shall include at least: clear description of services; locations of data and ICT services; data protection provisions; access, recovery and return of data; service-level descriptions; obligation to provide assistance; and notice periods."),
    ("Art. 30(3)", "Third-Party Risk",
     "Mandatory contractual provisions — critical or important functions",
     "Contracts for ICT services supporting critical or important functions shall additionally include: full service-level descriptions with quantitative/qualitative performance targets; notification obligations on incidents; cooperation in resolution of incidents; participation in the financial entity's ICT security awareness programmes and digital operational resilience training; right of audit; exit strategies."),
    ("Art. 31", "Third-Party Risk",
     "Designation of critical ICT third-party service providers",
     "The European Supervisory Authorities (ESAs), through the Joint Committee, shall designate the ICT third-party service providers that are critical for financial entities."),
    ("Art. 32", "Third-Party Risk",
     "Structure of the Oversight Framework",
     "The ESAs shall jointly establish an Oversight Forum to discuss matters concerning the development of the Oversight Framework for critical ICT third-party service providers."),
    ("Art. 33", "Third-Party Risk",
     "Tasks of the Lead Overseer",
     "Each critical ICT third-party service provider (CTPP) shall be allocated a Lead Overseer that shall conduct oversight to ensure CTPPs adequately monitor and manage ICT risks they may pose to financial entities."),
    ("Art. 34", "Third-Party Risk",
     "Operational coordination between Lead Overseers",
     "Lead Overseers shall coordinate with relevant competent authorities of financial entities and other Lead Overseers in the execution of their oversight tasks."),
    ("Art. 35", "Third-Party Risk",
     "Powers of the Lead Overseer",
     "The Lead Overseer has the power to request information, conduct general investigations, conduct on-site inspections, request reports, and issue recommendations to the CTPP."),
    ("Art. 36", "Third-Party Risk",
     "Exercise of powers outside the Union",
     "Where oversight tasks need to be performed outside the EU, the Lead Overseer shall conclude cooperation arrangements with the relevant authorities of the third country."),
    ("Art. 38", "Third-Party Risk",
     "Recommendations of the Lead Overseer",
     "The Lead Overseer may issue recommendations to the CTPP, including recommendations to mitigate concentration risk, sub-contracting risk, ICT security risk, or operational risks identified during the oversight."),
    ("Art. 40", "Third-Party Risk",
     "Joint Oversight Network",
     "Lead Overseers shall ensure consistency of oversight outcomes through a Joint Oversight Network involving the ESAs and competent authorities."),
    ("Art. 41", "Third-Party Risk",
     "Confidentiality and professional secrecy",
     "All persons working or having worked for the Lead Overseer, ESAs, competent authorities, and external experts shall be subject to the obligation of professional secrecy regarding information acquired in the course of duties."),
    ("Art. 42", "Third-Party Risk",
     "Cooperation with third-country authorities",
     "The ESAs and Lead Overseers shall cooperate with third-country authorities for the purposes of supervising critical ICT third-party service providers operating across borders."),
    ("Art. 43", "Third-Party Risk",
     "Oversight fees",
     "The Lead Overseer shall charge fees to critical ICT third-party service providers in accordance with delegated acts adopted by the Commission, fully covering the necessary expenditure for oversight tasks."),
    ("Art. 44", "Third-Party Risk",
     "International cooperation",
     "The ESAs may conclude administrative arrangements with regulatory and supervisory authorities of third countries to foster international cooperation on the digital operational resilience of the financial sector."),
]


# ---------------------------------------------------------------------------
# Pillar 5 — Information Sharing (Article 45)
# ---------------------------------------------------------------------------
DORA_INFO_SHARING: list[tuple[str, str, str, str]] = [
    ("Art. 45", "Information Sharing",
     "Information-sharing arrangements on cyber threat information",
     "Financial entities may exchange amongst themselves cyber-threat information and intelligence, including indicators of compromise, tactics, techniques and procedures, cybersecurity alerts and configuration tools, within trusted communities, while complying with data protection law."),
    ("Art. 45(2)", "Information Sharing",
     "Notification of participation in information-sharing arrangements",
     "Financial entities shall notify competent authorities of their participation in information-sharing arrangements upon validation of their membership, or, as applicable, upon cessation of their membership."),
]


ALL_DORA_CONTROLS = (
    DORA_ICT_RISK
    + DORA_INCIDENTS
    + DORA_TESTING
    + DORA_THIRD_PARTY
    + DORA_INFO_SHARING
)


async def seed_dora(session: AsyncSession) -> None:
    """Idempotent DORA seeder."""
    result = await session.execute(
        select(Framework).where(Framework.short_code == FRAMEWORK_SHORT_CODE)
    )
    if result.scalars().first():
        return

    framework = Framework(
        id=str(uuid.uuid4()),
        name=FRAMEWORK_NAME,
        short_code=FRAMEWORK_SHORT_CODE,
        category="financial_resilience",
        description=(
            "Regulation (EU) 2022/2554 — Digital Operational Resilience Act (DORA). "
            "Mandatory for EU financial entities since 17 January 2025. Establishes a "
            "uniform framework across 5 pillars: ICT risk management, ICT incident "
            "management, resilience testing (incl. TLPT), third-party (ICT) risk, and "
            "information sharing."
        ),
    )
    session.add(framework)
    await session.flush()

    version = FrameworkVersion(
        id=str(uuid.uuid4()),
        framework_id=framework.id,
        version=FRAMEWORK_VERSION,
        effective_date=date(2025, 1, 17),
        is_current=True,
    )
    session.add(version)
    await session.flush()

    for control_code, category, title, description in ALL_DORA_CONTROLS:
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
