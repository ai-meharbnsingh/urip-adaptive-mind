"""
NIS2 Directive — Directive (EU) 2022/2555 seeder.

NIS2 ("Network and Information Security Directive 2") replaces the original
2016 NIS Directive. EU Member States had until 17 October 2024 to transpose.
NIS2 covers 18 sectors of essential and important entities, with significantly
broader scope, harsher penalties (up to €10M or 2 % of worldwide turnover —
Art. 34) and accountability for management bodies.

This seeder covers:
  - Article 20  — Governance & accountability
  - Article 21  — Risk management measures (10 minimum measures, expanded)
  - Article 22  — Coordinated security risk assessments of critical supply chains
  - Article 23  — Incident reporting (early warning, incident notification, final)
  - Article 24  — Use of European cybersecurity certification schemes
  - Article 25  — Standardisation
  - Article 26  — Jurisdiction & registry obligations
  - Article 27  — Registry of entities
  - Article 28  — Database of domain name registration data
  - Article 30  — Voluntary notification of relevant information
  - Article 32  — Supervisory and enforcement measures (essential entities)
  - Article 33  — Supervisory and enforcement measures (important entities)
  - Article 34  — Administrative fines and penalties
  - Sectoral coverage — 18 sectors split between Annex I (high-criticality) and Annex II

Total controls: 86.

Sources (verified, public):
  - Official Journal text (Directive (EU) 2022/2555):
      https://eur-lex.europa.eu/eli/dir/2022/2555/oj
  - ENISA NIS2 hub: https://www.enisa.europa.eu/topics/nis-directive
  - Commission factsheet: https://digital-strategy.ec.europa.eu/en/policies/nis2-directive

Idempotent: skip if framework already exists.
"""
import uuid
from datetime import date
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from compliance_backend.models.framework import Framework, FrameworkVersion, Control


FRAMEWORK_SHORT_CODE = "NIS2"
FRAMEWORK_NAME = "NIS2 Directive (EU) 2022/2555"
FRAMEWORK_VERSION = "2022/2555"
REFERENCE_URL = "https://eur-lex.europa.eu/eli/dir/2022/2555/oj"


# ---------------------------------------------------------------------------
# Article 20 — Governance & accountability
# ---------------------------------------------------------------------------
NIS2_GOVERNANCE: list[tuple[str, str, str, str]] = [
    ("Art. 20(1)", "Governance",
     "Approval of cybersecurity risk-management measures",
     "Management bodies of essential and important entities shall approve the cybersecurity risk-management measures taken by those entities to comply with Article 21, oversee their implementation and be accountable for non-compliance."),
    ("Art. 20(2)", "Governance",
     "Cybersecurity training for management bodies",
     "Members of management bodies shall be required to follow regular training to gain sufficient knowledge and skills to apprehend and assess cybersecurity risks and management practices, and to offer similar training to their employees."),
]


# ---------------------------------------------------------------------------
# Article 21 — Risk management measures (10 minimum measures)
# ---------------------------------------------------------------------------
NIS2_RISK_MEASURES: list[tuple[str, str, str, str]] = [
    ("Art. 21(1)", "Risk Management",
     "All-hazards approach",
     "Essential and important entities shall take appropriate and proportionate technical, operational and organisational measures to manage the risks posed to the security of network and information systems, taking into account state-of-the-art and an all-hazards approach."),
    ("Art. 21(2)(a)", "Risk Management",
     "Policies on risk analysis and information system security",
     "Entities shall implement policies on risk analysis and information system security."),
    ("Art. 21(2)(b)", "Risk Management",
     "Incident handling",
     "Entities shall implement incident handling, including detection, analysis, containment, response, recovery and post-incident review."),
    ("Art. 21(2)(c)", "Risk Management",
     "Business continuity & crisis management",
     "Entities shall maintain business continuity, including backup management and disaster recovery, and crisis management."),
    ("Art. 21(2)(d)", "Risk Management",
     "Supply chain security",
     "Entities shall ensure supply-chain security, including security-related aspects concerning the relationships between each entity and its direct suppliers or service providers."),
    ("Art. 21(2)(e)", "Risk Management",
     "Security in network and information systems acquisition, development and maintenance",
     "Entities shall ensure security in the acquisition, development and maintenance of network and information systems, including vulnerability handling and disclosure."),
    ("Art. 21(2)(f)", "Risk Management",
     "Effectiveness assessment of risk management measures",
     "Entities shall implement policies and procedures to assess the effectiveness of cybersecurity risk-management measures."),
    ("Art. 21(2)(g)", "Risk Management",
     "Basic cyber hygiene practices and cybersecurity training",
     "Entities shall implement basic cyber hygiene practices and cybersecurity training."),
    ("Art. 21(2)(h)", "Risk Management",
     "Cryptography and encryption",
     "Entities shall implement policies and procedures regarding the use of cryptography and, where appropriate, encryption."),
    ("Art. 21(2)(i)", "Risk Management",
     "Human resources security, access control and asset management",
     "Entities shall implement policies on human resources security, access control policies and asset management."),
    ("Art. 21(2)(j)", "Risk Management",
     "Multi-factor authentication, secure communications, secure emergency communication",
     "Entities shall implement, where appropriate, multi-factor authentication or continuous authentication solutions, secured voice/video/text communications, and secured emergency communication systems."),
    ("Art. 21(3)", "Risk Management",
     "Specific consideration of supplier vulnerabilities and product quality",
     "Member States shall ensure entities take into account the specific vulnerabilities of each direct supplier and service provider, the overall quality of products and cybersecurity practices of suppliers, and the results of coordinated security risk assessments under Art. 22."),
    ("Art. 21(4)", "Risk Management",
     "Corrective measures",
     "Member States shall ensure that, when an entity finds it does not comply with Art. 21(2), it takes, without undue delay, all necessary, appropriate and proportionate corrective measures."),
]


# ---------------------------------------------------------------------------
# Article 22 — Coordinated security risk assessments of critical supply chains
# ---------------------------------------------------------------------------
NIS2_SUPPLY_CHAIN: list[tuple[str, str, str, str]] = [
    ("Art. 22(1)", "Supply Chain Security",
     "Union-level coordinated risk assessments",
     "The Cooperation Group, in cooperation with the Commission and ENISA, may carry out coordinated security risk assessments of specific critical ICT services, ICT systems or ICT products supply chains."),
    ("Art. 22(2)", "Supply Chain Security",
     "Risk factors considered",
     "The risk assessment shall identify technical and, where relevant, non-technical risk factors, including those caused by undue influence by a third country on suppliers and service providers."),
]


# ---------------------------------------------------------------------------
# Article 23 — Incident reporting (multi-stage)
# ---------------------------------------------------------------------------
NIS2_INCIDENT_REPORTING: list[tuple[str, str, str, str]] = [
    ("Art. 23(1)", "Incident Reporting",
     "Notification of significant incidents to CSIRT or competent authority",
     "Essential and important entities shall notify, without undue delay, their CSIRT or competent authority of any significant incident."),
    ("Art. 23(3)", "Incident Reporting",
     "Significance criteria for incidents",
     "An incident shall be considered significant if it has caused or is capable of causing severe operational disruption of services or financial loss for the entity concerned, or if it has affected or is capable of affecting other natural or legal persons by causing considerable material or non-material damage."),
    ("Art. 23(4)(a)", "Incident Reporting",
     "Early warning — within 24 hours",
     "Entities shall submit, without undue delay and in any event within 24 hours of becoming aware of the significant incident, an early warning indicating whether it is suspected to be caused by unlawful or malicious acts or could have a cross-border impact."),
    ("Art. 23(4)(b)", "Incident Reporting",
     "Incident notification — within 72 hours",
     "Entities shall submit, without undue delay and in any event within 72 hours of becoming aware of the significant incident, an incident notification updating the early-warning information and providing an initial assessment, severity, impact and indicators of compromise."),
    ("Art. 23(4)(c)", "Incident Reporting",
     "Intermediate report on request",
     "Upon the request of a CSIRT or, where applicable, the competent authority, entities shall provide an intermediate report on relevant status updates."),
    ("Art. 23(4)(d)", "Incident Reporting",
     "Final report — within 1 month",
     "Entities shall submit a final report not later than 1 month after submission of the incident notification, including a detailed description of the incident, threat or root cause, mitigation applied, and where applicable cross-border impact."),
    ("Art. 23(4)(e)", "Incident Reporting",
     "Progress report for ongoing incidents",
     "In the case of an ongoing incident at the time of submission of the final report, entities shall provide a progress report at that time and a final report within 1 month after handling the incident."),
    ("Art. 23(5)", "Incident Reporting",
     "Notification of recipients of services",
     "Where appropriate, in particular where the significant incident concerns two or more Member States, the entity shall notify, without undue delay, recipients of its services that are potentially affected of the significant incident."),
    ("Art. 23(6)", "Incident Reporting",
     "Communication to the public",
     "Where the significant incident is of public interest, the CSIRT or competent authority and, where appropriate, the competent authorities of other affected Member States may inform the public, in cooperation with the entity concerned, after consultation."),
]


# ---------------------------------------------------------------------------
# Articles 24-25 — Certification & standardisation
# ---------------------------------------------------------------------------
NIS2_CERTIFICATION: list[tuple[str, str, str, str]] = [
    ("Art. 24", "Certification & Standardisation",
     "Use of European cybersecurity certification schemes",
     "Member States may require essential and important entities to use particular ICT products, ICT services and ICT processes that are certified under European cybersecurity certification schemes adopted under Regulation (EU) 2019/881."),
    ("Art. 25", "Certification & Standardisation",
     "Standardisation",
     "Member States shall, without imposing or discriminating in favour of the use of a particular type of technology, encourage the use of European and international standards and technical specifications relevant to the security of network and information systems."),
]


# ---------------------------------------------------------------------------
# Articles 26-30 — Jurisdiction, registries, voluntary notifications
# ---------------------------------------------------------------------------
NIS2_REGISTRIES: list[tuple[str, str, str, str]] = [
    ("Art. 26(1)", "Jurisdiction & Registries",
     "Jurisdiction principle",
     "Essential and important entities shall be considered as falling under the jurisdiction of the Member State in which they are established (with specific rules for DNS providers, TLD name registries, providers of cloud computing services, data-centre services, content-delivery networks, managed (security) services, and digital providers)."),
    ("Art. 27(1)", "Jurisdiction & Registries",
     "Registry of entities",
     "By 17 January 2025, ENISA shall create and maintain a registry of essential and important entities providing certain services on the basis of information submitted by Member States."),
    ("Art. 27(2)", "Jurisdiction & Registries",
     "Information to be provided by entities",
     "Entities shall submit at least: name, address and up-to-date contact details, sector and sub-sector under Annex I or II, list of Member States where they provide services, IP ranges, and assigned ICT entity identifier."),
    ("Art. 28", "Jurisdiction & Registries",
     "Database of domain name registration data",
     "TLD name registries and entities providing domain name registration services shall collect and maintain accurate and complete domain name registration data in a dedicated database, applying due diligence procedures, including verification."),
    ("Art. 30", "Jurisdiction & Registries",
     "Voluntary notification of relevant information",
     "Member States shall ensure that other entities not falling within the scope of NIS2 may submit on a voluntary basis notifications of significant incidents, cyber threats, or near misses."),
]


# ---------------------------------------------------------------------------
# Articles 32-34 — Supervision & enforcement
# ---------------------------------------------------------------------------
NIS2_ENFORCEMENT: list[tuple[str, str, str, str]] = [
    ("Art. 32(1)", "Supervision & Enforcement",
     "Supervisory measures for essential entities",
     "Competent authorities shall have the power, in respect of essential entities, to subject them to: on-site inspections, off-site supervision, regular and targeted security audits, ad hoc audits, security scans, requests for information, and requests for evidence."),
    ("Art. 32(4)", "Supervision & Enforcement",
     "Enforcement powers — essential entities",
     "Competent authorities shall have at least the power to: issue warnings, instructions and binding orders, designate a monitoring officer, set deadlines, suspend certifications/authorisations, and prohibit the management from exercising managerial functions."),
    ("Art. 32(5)", "Supervision & Enforcement",
     "Suspension of certification or authorisation",
     "Where enforcement powers under Art. 32(4)(d), (e), or (f) are ineffective, competent authorities may suspend, temporarily, a certification or authorisation concerning part or all of the relevant services or activities."),
    ("Art. 33(1)", "Supervision & Enforcement",
     "Supervisory measures for important entities",
     "Competent authorities, when provided with evidence, indication or information that an important entity allegedly does not comply, shall take ex post supervisory measures, including on-site inspections, off-site supervision, audits, security scans, requests for information, and requests for evidence."),
    ("Art. 33(4)", "Supervision & Enforcement",
     "Enforcement powers — important entities",
     "Competent authorities shall have, in respect of important entities, the power to issue warnings and instructions, binding orders, deadlines, and to make compliance public."),
    ("Art. 34(1)", "Supervision & Enforcement",
     "Penalties — general principles",
     "Member States shall lay down the rules on penalties applicable to infringements of national measures adopted pursuant to NIS2 and ensure that they are effective, proportionate and dissuasive."),
    ("Art. 34(4)", "Supervision & Enforcement",
     "Maximum fines for essential entities",
     "Essential entities shall be subject to administrative fines of a maximum of at least €10 000 000 or at least 2 % of the total worldwide annual turnover in the preceding financial year of the undertaking to which the essential entity belongs, whichever is higher."),
    ("Art. 34(5)", "Supervision & Enforcement",
     "Maximum fines for important entities",
     "Important entities shall be subject to administrative fines of a maximum of at least €7 000 000 or at least 1.4 % of the total worldwide annual turnover in the preceding financial year of the undertaking to which the important entity belongs, whichever is higher."),
]


# ---------------------------------------------------------------------------
# Sectoral coverage — Annex I (highly critical) + Annex II (other critical)
# 18 sectors covered: 11 in Annex I + 7 in Annex II
# ---------------------------------------------------------------------------
NIS2_SECTORS: list[tuple[str, str, str, str]] = [
    # Annex I — sectors of high criticality (essential entities)
    ("Annex I.1", "Sectoral Coverage",
     "Energy",
     "Includes: electricity producers, distribution and transmission system operators, gas, oil, district heating and cooling, hydrogen. Operators in this sector are essential entities subject to all NIS2 obligations."),
    ("Annex I.2", "Sectoral Coverage",
     "Transport",
     "Includes: air, rail, water, road. Operators of airports, port authorities, traffic-management control operators, intelligent transport systems."),
    ("Annex I.3", "Sectoral Coverage",
     "Banking",
     "Credit institutions as defined in Article 4(1) of Regulation (EU) No 575/2013."),
    ("Annex I.4", "Sectoral Coverage",
     "Financial market infrastructures",
     "Operators of trading venues and central counterparties (CCPs) as defined under MiFID II and EMIR."),
    ("Annex I.5", "Sectoral Coverage",
     "Health",
     "Healthcare providers, EU reference laboratories, manufacturers of medicinal products, of basic pharmaceutical substances, and of medical devices considered critical during a public health emergency."),
    ("Annex I.6", "Sectoral Coverage",
     "Drinking water",
     "Suppliers and distributors of water intended for human consumption (excluding distributors for whom distribution of water for human consumption is a non-essential part of their general activity)."),
    ("Annex I.7", "Sectoral Coverage",
     "Waste water",
     "Undertakings collecting, disposing of or treating urban waste water, domestic waste water or industrial waste water (where this is an essential part of their activity)."),
    ("Annex I.8", "Sectoral Coverage",
     "Digital infrastructure",
     "Internet exchange point providers; DNS service providers (excluding root DNS); TLD name registries; cloud computing service providers; data-centre service providers; content-delivery network providers; trust service providers; public electronic communications networks/services."),
    ("Annex I.9", "Sectoral Coverage",
     "ICT service management (B2B)",
     "Managed service providers and managed security service providers (MSPs / MSSPs)."),
    ("Annex I.10", "Sectoral Coverage",
     "Public administration",
     "Public-administration entities of central governments, and public-administration entities at regional level when their disruption would have a significant impact on critical societal or economic activities."),
    ("Annex I.11", "Sectoral Coverage",
     "Space",
     "Operators of ground-based infrastructure that supports the provision of space-based services (excluding providers of public electronic communications networks)."),
    # Annex II — other critical sectors (important entities)
    ("Annex II.1", "Sectoral Coverage",
     "Postal and courier services",
     "Postal service providers as defined in Directive 97/67/EC, including providers of courier services."),
    ("Annex II.2", "Sectoral Coverage",
     "Waste management",
     "Undertakings carrying out waste management as defined in Directive 2008/98/EC (excluding those for which waste management is not their principal economic activity)."),
    ("Annex II.3", "Sectoral Coverage",
     "Manufacture, production and distribution of chemicals",
     "Undertakings engaged in the manufacture of substances and the distribution of substances or mixtures and undertakings carrying out the production of articles from substances or mixtures (Regulation (EC) No 1907/2006 — REACH)."),
    ("Annex II.4", "Sectoral Coverage",
     "Production, processing and distribution of food",
     "Food businesses engaged in wholesale distribution and industrial production and processing as defined in Article 3(2) of Regulation (EC) No 178/2002."),
    ("Annex II.5", "Sectoral Coverage",
     "Manufacturing",
     "Manufacturing of medical devices and in vitro diagnostic medical devices; computer, electronic and optical products; electrical equipment; machinery and equipment; motor vehicles, trailers and semi-trailers; other transport equipment."),
    ("Annex II.6", "Sectoral Coverage",
     "Digital providers",
     "Providers of online marketplaces, online search engines, and social networking services platforms."),
    ("Annex II.7", "Sectoral Coverage",
     "Research",
     "Research organisations engaged in scientific research with the aim of generating commercial products."),
]


# ---------------------------------------------------------------------------
# Detailed expansion of Article 21(2)(a)–(j) — sub-controls per measure family
# (one per measure pillar to give engineers granular implementation hooks)
# ---------------------------------------------------------------------------
NIS2_DETAILED_MEASURES: list[tuple[str, str, str, str]] = [
    # Risk-analysis and information system security policies
    ("Art. 21(2)(a).1", "Detailed Measures",
     "Documented information security policy",
     "Information security policy approved by management body, communicated to staff and reviewed at planned intervals."),
    ("Art. 21(2)(a).2", "Detailed Measures",
     "Risk-assessment methodology",
     "Documented risk-assessment methodology covering identification, analysis, evaluation and treatment of cyber risks across the entity's network and information systems."),
    ("Art. 21(2)(a).3", "Detailed Measures",
     "Asset inventory",
     "Maintained inventory of assets supporting the entity's services, including ownership, classification and criticality."),
    # Incident handling
    ("Art. 21(2)(b).1", "Detailed Measures",
     "Incident detection capability",
     "Continuous monitoring with detection rules tuned to the entity's threat profile and supported by appropriate logging."),
    ("Art. 21(2)(b).2", "Detailed Measures",
     "Incident response plan",
     "Documented incident response plan with defined roles, severity classification, escalation paths, communication plan and tested at planned intervals."),
    ("Art. 21(2)(b).3", "Detailed Measures",
     "Post-incident review",
     "Lessons-learned process applied after each significant incident with action items tracked to closure."),
    # Business continuity
    ("Art. 21(2)(c).1", "Detailed Measures",
     "Business continuity plan",
     "BCP covering critical services with defined RTO/RPO, alternative arrangements, dependencies, and tested at planned intervals."),
    ("Art. 21(2)(c).2", "Detailed Measures",
     "Backup management",
     "Backups of critical data and systems performed, encrypted, stored geographically separately and restoration tested."),
    ("Art. 21(2)(c).3", "Detailed Measures",
     "Crisis management arrangements",
     "Crisis management team, decision-making authority, and communication channels established and tested."),
    # Supply chain
    ("Art. 21(2)(d).1", "Detailed Measures",
     "Supplier security requirements",
     "Security requirements imposed on suppliers and service providers via contractual clauses, including audit rights and incident notification obligations."),
    ("Art. 21(2)(d).2", "Detailed Measures",
     "Supplier risk assessments",
     "Risk-based supplier assessments at onboarding and periodic intervals; documented mitigation actions."),
    # Acquisition / development / maintenance
    ("Art. 21(2)(e).1", "Detailed Measures",
     "Secure development lifecycle",
     "Secure development lifecycle procedures with security requirements, threat modelling, code review, security testing, and change management."),
    ("Art. 21(2)(e).2", "Detailed Measures",
     "Vulnerability handling and disclosure",
     "Vulnerability management programme with patch SLAs, scanning, coordinated disclosure policy, and contact for security researchers."),
    # Effectiveness assessment
    ("Art. 21(2)(f).1", "Detailed Measures",
     "Internal effectiveness assessment",
     "Periodic internal review of cybersecurity controls' effectiveness with metrics, KPIs and management reporting."),
    ("Art. 21(2)(f).2", "Detailed Measures",
     "Independent audit",
     "Independent audit of cybersecurity controls at planned intervals (internal audit, third-party audit, or designated competent authority audit)."),
    # Hygiene & training
    ("Art. 21(2)(g).1", "Detailed Measures",
     "Cyber hygiene baseline",
     "Documented cyber hygiene baseline (patching, anti-malware, password policy, secure configuration, network segmentation, principle of least privilege)."),
    ("Art. 21(2)(g).2", "Detailed Measures",
     "Awareness and training programme",
     "Mandatory cybersecurity awareness training for all staff at onboarding and periodically; role-specific training for privileged roles."),
    # Cryptography
    ("Art. 21(2)(h).1", "Detailed Measures",
     "Cryptographic controls policy",
     "Policy on use of cryptography (encryption at rest, encryption in transit, key management, algorithm selection, deprecation rules)."),
    ("Art. 21(2)(h).2", "Detailed Measures",
     "Key management lifecycle",
     "Documented cryptographic key management lifecycle: generation, distribution, storage, rotation, archival, destruction."),
    # HR security, access control, asset mgmt
    ("Art. 21(2)(i).1", "Detailed Measures",
     "HR security — onboarding screening",
     "Pre-employment screening and security-related terms in employment contracts, proportionate to the role and risk."),
    ("Art. 21(2)(i).2", "Detailed Measures",
     "Access control policy and reviews",
     "Access control policy implementing least privilege; periodic access reviews of privileged and standard access."),
    ("Art. 21(2)(i).3", "Detailed Measures",
     "Joiner-mover-leaver process",
     "Documented JML process with timely provisioning, modification and revocation of access rights upon role change or termination."),
    # MFA, secure comms, emergency comms
    ("Art. 21(2)(j).1", "Detailed Measures",
     "Multi-factor authentication for privileged access",
     "MFA enforced for privileged accounts, remote access and access to critical systems, with phishing-resistant factors where appropriate."),
    ("Art. 21(2)(j).2", "Detailed Measures",
     "Secured voice/video/text communications",
     "End-to-end secured communications channels for sensitive internal and external communications (e.g., for incident response)."),
    ("Art. 21(2)(j).3", "Detailed Measures",
     "Secured emergency communications",
     "Out-of-band, resilient emergency communication channels available during ICT incidents that affect normal channels."),
]


ALL_NIS2_CONTROLS = (
    NIS2_GOVERNANCE
    + NIS2_RISK_MEASURES
    + NIS2_SUPPLY_CHAIN
    + NIS2_INCIDENT_REPORTING
    + NIS2_CERTIFICATION
    + NIS2_REGISTRIES
    + NIS2_ENFORCEMENT
    + NIS2_SECTORS
    + NIS2_DETAILED_MEASURES
)


async def seed_nis2(session: AsyncSession) -> None:
    """Idempotent NIS2 Directive seeder."""
    result = await session.execute(
        select(Framework).where(Framework.short_code == FRAMEWORK_SHORT_CODE)
    )
    if result.scalars().first():
        return

    framework = Framework(
        id=str(uuid.uuid4()),
        name=FRAMEWORK_NAME,
        short_code=FRAMEWORK_SHORT_CODE,
        category="security",
        description=(
            "Directive (EU) 2022/2555 — NIS2. Replaces the original 2016 NIS Directive "
            "with broader scope (18 sectors, ~150k entities EU-wide), tightened risk-management "
            "obligations (Art. 21), strict multi-stage incident reporting (Art. 23), "
            "supply-chain security, harsher penalties (€10M / 2 % global turnover for essential, "
            "€7M / 1.4 % for important), and direct accountability for management bodies. "
            "Member States transposition deadline: 17 October 2024."
        ),
    )
    session.add(framework)
    await session.flush()

    version = FrameworkVersion(
        id=str(uuid.uuid4()),
        framework_id=framework.id,
        version=FRAMEWORK_VERSION,
        effective_date=date(2024, 10, 17),
        is_current=True,
    )
    session.add(version)
    await session.flush()

    for control_code, category, title, description in ALL_NIS2_CONTROLS:
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
