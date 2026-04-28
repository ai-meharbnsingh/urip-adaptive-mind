"""
ISO/IEC 27017:2015 — Code of practice for information security controls based
on ISO/IEC 27002 for cloud services.

ISO 27017 extends ISO 27002 by:
  - Adding 7 cloud-specific controls (CLD.x.y.z numbering)
  - Providing cloud-specific implementation guidance for 30 existing 27002
    controls (split between cloud customer and cloud service provider
    responsibilities — Annex B of ISO 27017 contains the responsibility matrix).

This seeder records 37 distinct controls covering both the 7 CLD additions
and the 30 cloud-extended ISO 27002 controls. Each control is annotated with
the relevant clause number from the 2015 standard.

Sources (verified, public):
  - ISO/IEC 27017:2015 — https://www.iso.org/standard/43757.html
  - Public summary mappings:
      https://www.iso27001security.com/html/27017.html
      https://cloudsecurityalliance.org/articles/iso-iec-27017-cloud-controls-explained
      https://www.bsigroup.com/en-GB/iso-iec-27017-cloud-security/

Idempotent: skip if framework already exists.
"""
import uuid
from datetime import date
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from compliance_backend.models.framework import Framework, FrameworkVersion, Control


FRAMEWORK_SHORT_CODE = "ISO27017"
FRAMEWORK_NAME = "ISO/IEC 27017:2015 — Cloud Security"
FRAMEWORK_VERSION = "2015"
REFERENCE_URL = "https://www.iso.org/standard/43757.html"


# ---------------------------------------------------------------------------
# 7 cloud-specific controls (CLD.x.y.z)
# ---------------------------------------------------------------------------
ISO27017_CLD: list[tuple[str, str, str, str]] = [
    ("CLD.6.3.1", "Cloud-Specific Controls",
     "Shared roles and responsibilities within a cloud computing environment",
     "Responsibilities for the cloud service customer and the cloud service provider shall be allocated, documented and communicated, including for cases where the cloud service provider relies on subcontractors."),
    ("CLD.8.1.5", "Cloud-Specific Controls",
     "Removal of cloud service customer assets",
     "Assets of the cloud service customer that are at the cloud service provider's premises shall be removed, returned, or disposed of in a timely manner upon termination of the cloud service agreement."),
    ("CLD.9.5.1", "Cloud-Specific Controls",
     "Segregation in virtual computing environments",
     "A cloud service customer's virtual environment running on a cloud service shall be protected from other customers and unauthorised parties."),
    ("CLD.9.5.2", "Cloud-Specific Controls",
     "Virtual machine hardening",
     "Virtual machines in a cloud computing environment shall be hardened to meet business needs."),
    ("CLD.12.1.5", "Cloud-Specific Controls",
     "Administrator's operational security",
     "Procedures for administrative operations of a cloud service shall be defined, documented and monitored."),
    ("CLD.12.4.5", "Cloud-Specific Controls",
     "Monitoring of cloud services",
     "The cloud service customer shall have the capability to monitor specified aspects of the cloud service. The cloud service provider shall provide such capability."),
    ("CLD.13.1.4", "Cloud-Specific Controls",
     "Alignment of security management for virtual and physical networks",
     "Configurations of virtual networks shall be aligned with the information-security policy for physical networks upon configuration of virtual networks."),
]


# ---------------------------------------------------------------------------
# Cloud-extended ISO 27002 controls (with cloud-specific implementation
# guidance from ISO 27017). 30 controls.
# ---------------------------------------------------------------------------
ISO27017_EXTENDED: list[tuple[str, str, str, str]] = [
    ("5.1.1", "Information Security Policies (Cloud Context)",
     "Policies for information security — cloud extension",
     "Information security policies shall include cloud-service-specific topics: customer/provider responsibilities, cloud risks, customer data, supplier (sub-cloud) management."),
    ("5.1.2", "Information Security Policies (Cloud Context)",
     "Review of information security policies — cloud context",
     "Cloud-related security policies shall be reviewed when significant changes occur in the cloud service or its risk landscape."),
    ("6.1.1", "Organization of Information Security (Cloud)",
     "Information security roles and responsibilities — cloud",
     "Information security roles in cloud services shall be defined and split between cloud service customer and provider, including escalation paths and out-of-band contacts."),
    ("6.1.3", "Organization of Information Security (Cloud)",
     "Contact with authorities — cloud",
     "Cloud service customers and providers shall maintain contact with relevant authorities (data protection, sector regulators) for cloud-related matters."),
    ("7.2.1", "Human Resource Security (Cloud)",
     "Management responsibilities — cloud personnel",
     "Cloud service provider personnel handling customer data shall be subject to access agreements, screening and security training proportionate to risk."),
    ("7.2.2", "Human Resource Security (Cloud)",
     "Information security awareness, education and training — cloud",
     "Cloud service customers shall ensure their users are trained on cloud-specific risks (phishing, account takeover, data leakage)."),
    ("8.1.1", "Asset Management (Cloud)",
     "Inventory of assets — cloud assets",
     "An inventory of cloud-service-related assets (accounts, encryption keys, data, applications) shall be maintained by the cloud service customer."),
    ("8.2.2", "Asset Management (Cloud)",
     "Labelling of information — cloud labelling",
     "Cloud service customers shall ensure that data classification labels are preserved when data is processed by cloud services."),
    ("9.1.2", "Access Control (Cloud)",
     "Access to networks and network services — cloud",
     "Cloud service customer and provider shall agree on access controls for management, customer and inter-service network paths."),
    ("9.2.1", "Access Control (Cloud)",
     "User registration and de-registration — cloud accounts",
     "Cloud service customer shall manage cloud account registration and de-registration including federation, MFA, and emergency lockout."),
    ("9.2.3", "Access Control (Cloud)",
     "Management of privileged access rights — cloud admins",
     "Privileged access to cloud-management consoles shall be tightly controlled, including separation of duties between operations and security."),
    ("9.2.4", "Access Control (Cloud)",
     "Management of secret authentication information — cloud secrets",
     "Cloud service customer shall manage authentication secrets (API keys, OAuth tokens, service-account credentials) using a secret-management system with rotation."),
    ("9.4.1", "Access Control (Cloud)",
     "Information access restriction — cloud data isolation",
     "Cloud service customer's data shall be isolated logically from other customers' data, with access restricted on a need-to-know basis."),
    ("10.1.1", "Cryptography (Cloud)",
     "Policy on the use of cryptographic controls — cloud",
     "Cloud service customer shall define a policy on cryptography in the cloud (encryption at rest, encryption in transit, customer-managed keys, BYOK / HYOK)."),
    ("10.1.2", "Cryptography (Cloud)",
     "Key management — cloud KMS",
     "Cloud-based cryptographic keys shall be managed via a key management system (KMS) with documented key generation, distribution, storage, rotation and destruction."),
    ("11.2.7", "Physical Security (Cloud)",
     "Secure disposal or re-use of equipment — cloud media",
     "Cloud service provider shall securely dispose of or reuse storage media containing customer data per agreed procedures (cryptographic erasure or physical destruction)."),
    ("12.1.2", "Operations Security (Cloud)",
     "Change management — cloud",
     "Changes to cloud-service infrastructure shall be subject to change management; cloud service customer shall be notified of changes that materially affect customer's controls."),
    ("12.1.3", "Operations Security (Cloud)",
     "Capacity management — cloud",
     "Cloud service customer shall monitor cloud capacity (compute, storage, network) and the provider shall provide capacity-related telemetry."),
    ("12.3.1", "Operations Security (Cloud)",
     "Information backup — cloud backups",
     "Cloud service customer shall ensure that backups exist for cloud-resident data, including geo-redundant copies and tested restoration; the provider shall declare its backup capabilities."),
    ("12.4.1", "Operations Security (Cloud)",
     "Event logging — cloud logs",
     "Cloud service customer shall obtain and retain event logs from the cloud service for activities relevant to its security; the provider shall offer access to these logs."),
    ("12.4.3", "Operations Security (Cloud)",
     "Administrator and operator logs — cloud",
     "All administrative actions performed in the cloud (by customer or provider) shall be logged, integrity-protected and reviewed."),
    ("12.4.4", "Operations Security (Cloud)",
     "Clock synchronisation — cloud",
     "Time sources used by cloud services and customer systems shall be synchronised so that timestamps in event logs are comparable."),
    ("12.6.1", "Operations Security (Cloud)",
     "Management of technical vulnerabilities — cloud",
     "Cloud service customer shall manage vulnerabilities in the components it controls; the provider shall manage vulnerabilities in the components it controls and notify the customer of customer-impacting vulnerabilities."),
    ("13.1.3", "Communications Security (Cloud)",
     "Segregation in networks — cloud",
     "Cloud-network traffic between tenants and management shall be segregated; the customer shall use VLAN/VPC equivalents and network ACLs."),
    ("13.2.1", "Communications Security (Cloud)",
     "Information transfer policies and procedures — cloud",
     "Information transferred to or from a cloud service shall be protected (TLS 1.2+, mutual TLS where required, VPN/dedicated link options)."),
    ("14.1.2", "Acquisition, Development and Maintenance (Cloud)",
     "Securing application services on public networks — cloud apps",
     "Cloud-deployed application services accessible via public networks shall be protected against fraudulent activity and unauthorised disclosure / modification (TLS, WAF, anti-bot)."),
    ("15.1.1", "Supplier Relationships (Cloud)",
     "Information security policy for supplier relationships — cloud",
     "Cloud service customer shall have a policy for cloud supplier relationships covering selection, onboarding, monitoring, and exit."),
    ("16.1.1", "Incident Management (Cloud)",
     "Responsibilities and procedures — cloud incidents",
     "Incident response responsibilities and procedures shall be split between cloud service customer and provider, including incident notification timelines."),
    ("17.1.2", "Business Continuity (Cloud)",
     "Implementing information security continuity — cloud",
     "Cloud service customer shall ensure that the cloud service supports its business continuity plans (regional failover, disaster recovery, multi-AZ deployments)."),
    ("18.1.1", "Compliance (Cloud)",
     "Identification of applicable legislation and contractual requirements — cloud",
     "Cloud service customer and provider shall identify legal/contractual requirements applicable to the cloud service (data location, sectoral, export-controls), and document them in the agreement."),
]


ALL_ISO27017_CONTROLS = ISO27017_CLD + ISO27017_EXTENDED


async def seed_iso27017(session: AsyncSession) -> None:
    """Idempotent ISO/IEC 27017 seeder."""
    result = await session.execute(
        select(Framework).where(Framework.short_code == FRAMEWORK_SHORT_CODE)
    )
    if result.scalars().first():
        return

    framework = Framework(
        id=str(uuid.uuid4()),
        name=FRAMEWORK_NAME,
        short_code=FRAMEWORK_SHORT_CODE,
        category="cloud_security",
        description=(
            "ISO/IEC 27017:2015 — Code of practice for information security controls "
            "based on ISO/IEC 27002 for cloud services. Provides 7 cloud-specific (CLD.*) "
            "controls and cloud-specific implementation guidance for 30 ISO 27002 controls. "
            "Splits responsibilities between cloud service customer and provider."
        ),
    )
    session.add(framework)
    await session.flush()

    version = FrameworkVersion(
        id=str(uuid.uuid4()),
        framework_id=framework.id,
        version=FRAMEWORK_VERSION,
        effective_date=date(2015, 12, 15),
        is_current=True,
    )
    session.add(version)
    await session.flush()

    for control_code, category, title, description in ALL_ISO27017_CONTROLS:
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
