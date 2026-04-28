"""
ISO/IEC 27018:2019 — Code of practice for protection of Personally Identifiable
Information (PII) in public clouds acting as PII processors.

ISO 27018 is the international standard for PII protection in public-cloud
contexts. It provides:
  - Cloud-specific implementation guidance for ISO 27002 controls (clauses 5–18)
  - An Annex A with 25 additional control objectives for PII protection
    derived from the privacy principles of ISO 29100.

This seeder records 27 distinct controls (25 Annex A + 2 cloud-extended
implementation guidance items not present in 27017's overlap surface).

Sources (verified, public):
  - ISO/IEC 27018:2019 — https://www.iso.org/standard/76559.html
  - Public summaries:
      https://www.bsigroup.com/en-GB/iso-iec-27018-personal-data-in-the-cloud/
      https://learn.microsoft.com/en-us/compliance/regulatory/offering-iso-27018
      https://www.aicpa.org/resources/article/iso-27018-cloud-privacy

Idempotent: skip if framework already exists.
"""
import uuid
from datetime import date
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from compliance_backend.models.framework import Framework, FrameworkVersion, Control


FRAMEWORK_SHORT_CODE = "ISO27018"
FRAMEWORK_NAME = "ISO/IEC 27018:2019 — Cloud PII Protection"
FRAMEWORK_VERSION = "2019"
REFERENCE_URL = "https://www.iso.org/standard/76559.html"


# ---------------------------------------------------------------------------
# Annex A — 25 PII-specific controls aligned to ISO 29100 privacy principles
# Format: (control_code, category, title, description)
# ---------------------------------------------------------------------------
ISO27018_ANNEX_A: list[tuple[str, str, str, str]] = [
    # A.1 — Consent and choice
    ("A.1.1", "Consent and Choice",
     "Obligation to co-operate regarding PII principals' rights",
     "The public cloud PII processor shall provide the cloud service customer with the means to enable PII principals to exercise their rights of access, correction, erasure, restriction and portability."),
    # A.2 — Purpose legitimacy and specification
    ("A.2.1", "Purpose Legitimacy and Specification",
     "Public cloud PII processor's purpose",
     "PII to be processed under a contract shall not be processed for any purpose independent of the instructions of the cloud service customer."),
    ("A.2.2", "Purpose Legitimacy and Specification",
     "Public cloud PII processor's commercial use",
     "PII processed under a contract shall not be used by the public cloud PII processor for the purposes of marketing and advertising without express consent of PII principals or the customer."),
    # A.3 — Collection limitation
    ("A.3.1", "Collection Limitation",
     "Secure erasure of temporary files",
     "Temporary files and documents containing PII shall be erased or destroyed within a specified, documented period."),
    # A.4 — Data minimisation
    ("A.4.1", "Data Minimisation",
     "PII disclosure notification",
     "Contracts shall require the public cloud PII processor to notify the cloud service customer in case of any legally binding request for disclosure of PII (e.g., subpoenas)."),
    ("A.4.2", "Data Minimisation",
     "Recording of PII disclosures",
     "Disclosures of PII to third parties shall be recorded, including what PII has been disclosed, to whom and at what time."),
    # A.5 — Use, retention and disclosure limitation
    ("A.5.1", "Use, Retention and Disclosure Limitation",
     "Disclosure of sub-contracted PII processing",
     "The use of sub-contractors by the public cloud PII processor to process PII shall be disclosed to the relevant cloud service customer before their use."),
    ("A.5.2", "Use, Retention and Disclosure Limitation",
     "Engagement of a sub-contractor to process PII",
     "Contracts between the public cloud PII processor and any sub-contractors that process PII shall specify minimum technical and organisational measures meeting the information-security and PII-protection obligations of the public cloud PII processor."),
    # A.6 — Accuracy and quality
    ("A.6.1", "Accuracy and Quality",
     "Notification of a data breach involving PII",
     "The public cloud PII processor shall promptly notify the relevant cloud service customer of any unauthorised access to PII or unauthorised access to processing equipment or facilities resulting in loss, disclosure or alteration of PII."),
    ("A.6.2", "Accuracy and Quality",
     "Retention period for administrative security policies and guidelines",
     "Copies of security policies and operating procedures shall be retained for a period of N years after their replacement (where N is specified in the contract)."),
    ("A.6.3", "Accuracy and Quality",
     "PII return, transfer and disposal",
     "The public cloud PII processor shall have a policy on the return, transfer and/or disposal of PII (including required formats and timelines)."),
    # A.7 — Openness, transparency and notice
    ("A.7.1", "Openness, Transparency and Notice",
     "Geographic location of PII",
     "The public cloud PII processor shall specify and document the countries in which PII may possibly be stored."),
    ("A.7.2", "Openness, Transparency and Notice",
     "Intended destination of PII",
     "PII transmitted using a data-transmission network shall be subject to appropriate controls designed to ensure that data reaches its intended destination."),
    # A.8 — Individual participation and access
    ("A.8.1", "Individual Participation and Access",
     "Use of unique user IDs to access PII",
     "Unique user IDs shall be used to access PII to allow audit trails per user."),
    ("A.8.2", "Individual Participation and Access",
     "Records of authorised users",
     "An up-to-date record of users or profiles of users with authorised access to PII processing systems shall be maintained."),
    ("A.8.3", "Individual Participation and Access",
     "User ID management",
     "De-activated or expired user IDs shall not be granted to other individuals."),
    # A.9 — Accountability
    ("A.9.1", "Accountability",
     "Contract measures",
     "Contracts between the cloud service customer and the public cloud PII processor shall specify minimum technical and organisational measures to ensure obligations are met."),
    ("A.9.2", "Accountability",
     "Sub-contracted PII processing",
     "Sub-contracts between the public cloud PII processor and PII sub-processors shall include the same data-protection obligations as those between the cloud service customer and the public cloud PII processor."),
    # A.10 — Information security
    ("A.10.1", "Information Security",
     "Confidentiality or non-disclosure agreements",
     "Personnel of the public cloud PII processor with access to PII shall sign confidentiality / NDAs prior to gaining access."),
    ("A.10.2", "Information Security",
     "Restriction of the creation of hardcopy material",
     "Creation of hardcopy material displaying PII shall be restricted to that which is strictly necessary to fulfil identified processing purposes."),
    ("A.10.3", "Information Security",
     "Control and logging of data restoration",
     "Data restorations from backups (which involve PII) shall be controlled, logged and reviewed."),
    ("A.10.4", "Information Security",
     "Protecting data on storage media leaving the premises",
     "Removable physical media that may contain PII shall be encrypted or otherwise protected when transported off-premises."),
    ("A.10.5", "Information Security",
     "Use of unencrypted portable storage media and devices",
     "Use of unencrypted portable storage devices and media for PII storage or transport shall be prohibited unless an exceptional, documented exception applies."),
    ("A.10.6", "Information Security",
     "Encryption of PII transmitted over public data-transmission networks",
     "PII transmitted over public networks shall be encrypted prior to transmission."),
    # A.11 — Privacy compliance
    ("A.11.1", "Privacy Compliance",
     "PII transfer agreements",
     "Where PII is transferred between the public cloud PII processor and third countries or international organisations, the conditions of transfer shall be documented in transfer agreements that satisfy applicable law."),
]


# ---------------------------------------------------------------------------
# Cloud-extended implementation guidance items unique to PII context
# ---------------------------------------------------------------------------
ISO27018_GUIDANCE: list[tuple[str, str, str, str]] = [
    ("G.5.1", "Implementation Guidance",
     "Information security policy for cloud-based PII",
     "Cloud-based PII processing shall be addressed in the information security policy, including PII handling, PII principal rights, and applicable regulatory requirements."),
    ("G.6.1", "Implementation Guidance",
     "Designated contact for PII-related communications",
     "The public cloud PII processor shall appoint a contact (e.g., DPO) responsible for handling PII-related communications from cloud service customers and their PII principals."),
]


ALL_ISO27018_CONTROLS = ISO27018_ANNEX_A + ISO27018_GUIDANCE


async def seed_iso27018(session: AsyncSession) -> None:
    """Idempotent ISO/IEC 27018 seeder."""
    result = await session.execute(
        select(Framework).where(Framework.short_code == FRAMEWORK_SHORT_CODE)
    )
    if result.scalars().first():
        return

    framework = Framework(
        id=str(uuid.uuid4()),
        name=FRAMEWORK_NAME,
        short_code=FRAMEWORK_SHORT_CODE,
        category="privacy",
        description=(
            "ISO/IEC 27018:2019 — Code of practice for protection of PII in public clouds "
            "acting as PII processors. Annex A provides 25 PII-specific controls aligned "
            "to the ISO 29100 privacy framework, plus implementation guidance for ISO 27002 "
            "controls in cloud-PII contexts."
        ),
    )
    session.add(framework)
    await session.flush()

    version = FrameworkVersion(
        id=str(uuid.uuid4()),
        framework_id=framework.id,
        version=FRAMEWORK_VERSION,
        effective_date=date(2019, 1, 14),
        is_current=True,
    )
    session.add(version)
    await session.flush()

    for control_code, category, title, description in ALL_ISO27018_CONTROLS:
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
