"""
ISO/IEC 27701:2019 — Privacy Information Management System (PIMS) seeder.

ISO 27701 extends ISO 27001 / 27002 with privacy-specific requirements and
controls. It is the international "GDPR-compatible" privacy management
standard, suitable also as the basis for India DPDP, LGPD and CCPA programmes.

Structure of the standard:
  - Clause 5: PIMS-specific requirements related to ISO 27001
  - Clause 6: PIMS-specific guidance related to ISO 27002
  - Clause 7: Additional ISO 27002 guidance for PII controllers
  - Clause 8: Additional ISO 27002 guidance for PII processors
  - Annex A: PIMS-specific reference control objectives & controls (PII Controllers)
              — 31 controls across 4 control objectives (A.7.2 – A.7.5)
  - Annex B: PIMS-specific reference control objectives & controls (PII Processors)
              — 18 controls across 4 control objectives (B.8.2 – B.8.5)

This seeder records 51 controls (31 controller + 18 processor + 2 PIMS-specific
clauses 5 & 6 management-system items).

Sources (verified, public):
  - ISO/IEC 27701:2019 — https://www.iso.org/standard/71670.html
  - Public summaries:
      https://www.iso27001security.com/html/27701.html
      https://www.bsigroup.com/en-GB/iso-iec-27701-privacy-information-management/
      https://www.itgovernance.eu/en-ie/iso-iec-27701

Idempotent: skip if framework already exists.
"""
import uuid
from datetime import date
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from compliance_backend.models.framework import Framework, FrameworkVersion, Control


FRAMEWORK_SHORT_CODE = "ISO27701"
FRAMEWORK_NAME = "ISO/IEC 27701:2019 — Privacy Information Management System"
FRAMEWORK_VERSION = "2019"
REFERENCE_URL = "https://www.iso.org/standard/71670.html"


# ---------------------------------------------------------------------------
# Clauses 5 & 6 — PIMS management system & ISO 27002 extension
# ---------------------------------------------------------------------------
ISO27701_PIMS: list[tuple[str, str, str, str]] = [
    ("Cl.5.2.1", "PIMS Management",
     "Understanding the organization and its context — privacy",
     "The organization shall determine external and internal issues relevant to the PIMS, including PII processing roles (controller, joint controller, processor)."),
    ("Cl.5.4.1.2", "PIMS Management",
     "Privacy risk assessment process",
     "The organization shall apply the information security risk assessment process to identify risks associated with the loss of confidentiality, integrity and availability of PII, plus risks to PII principals."),
    ("Cl.5.4.1.3", "PIMS Management",
     "Privacy risk treatment",
     "The organization shall apply the information security risk treatment process to determine controls necessary to implement the privacy-risk treatment options chosen, including from Annex A or B."),
    ("Cl.6.5.3", "PIMS Management",
     "Documented operating procedures — privacy",
     "Operating procedures shall include privacy-specific instructions (e.g., DSAR handling, breach notification, retention)."),
]


# ---------------------------------------------------------------------------
# Annex A — PII Controllers (31 controls across A.7.2 – A.7.5)
# ---------------------------------------------------------------------------
ISO27701_ANNEX_A: list[tuple[str, str, str, str]] = [
    # A.7.2 — Conditions for collection and processing
    ("A.7.2.1", "PII Controllers — Collection & Processing",
     "Identify and document purpose",
     "The organization shall identify and document the specific purposes for which the PII will be processed."),
    ("A.7.2.2", "PII Controllers — Collection & Processing",
     "Identify lawful basis",
     "The organization shall identify, document and comply with the relevant lawful basis for the processing of PII for the identified purposes."),
    ("A.7.2.3", "PII Controllers — Collection & Processing",
     "Determine when and how consent is to be obtained",
     "The organization shall determine and document a process by which it can demonstrate if, when and how consent for the processing of PII was obtained from PII principals."),
    ("A.7.2.4", "PII Controllers — Collection & Processing",
     "Obtain and record consent",
     "The organization shall obtain and record consent from PII principals according to the documented processes."),
    ("A.7.2.5", "PII Controllers — Collection & Processing",
     "Privacy impact assessment",
     "The organization shall assess the need for, and implement where appropriate, a privacy impact assessment whenever new processing of PII or changes to existing processing is planned."),
    ("A.7.2.6", "PII Controllers — Collection & Processing",
     "Contracts with PII processors",
     "The organization shall have a written contract with any PII processor that it uses, and shall ensure that their contracts with PII processors address the implementation of the appropriate controls in Annex B."),
    ("A.7.2.7", "PII Controllers — Collection & Processing",
     "Joint PII controller",
     "The organization shall determine respective roles and responsibilities for the processing of PII (including PII protection and security requirements) with any joint PII controller."),
    ("A.7.2.8", "PII Controllers — Collection & Processing",
     "Records related to processing PII",
     "The organization shall determine and securely maintain the necessary records (records of processing activities) in support of its obligations for the processing of PII."),
    # A.7.3 — Obligations to PII principals
    ("A.7.3.1", "PII Controllers — Obligations to Principals",
     "Determining and fulfilling obligations to PII principals",
     "The organization shall determine and document its legal, regulatory and business obligations to PII principals related to the processing of their PII and provide the means to meet these obligations."),
    ("A.7.3.2", "PII Controllers — Obligations to Principals",
     "Determining information for PII principals",
     "The organization shall determine and document the information to be provided to PII principals regarding the processing of their PII and the timing of such provision."),
    ("A.7.3.3", "PII Controllers — Obligations to Principals",
     "Providing information to PII principals",
     "The organization shall provide PII principals with clear and easily accessible information identifying the PII controller and describing the processing of their PII."),
    ("A.7.3.4", "PII Controllers — Obligations to Principals",
     "Providing mechanism to modify or withdraw consent",
     "The organization shall provide a mechanism for PII principals to modify or withdraw their consent."),
    ("A.7.3.5", "PII Controllers — Obligations to Principals",
     "Providing mechanism to object to PII processing",
     "The organization shall provide a mechanism for PII principals to object to the processing of their PII."),
    ("A.7.3.6", "PII Controllers — Obligations to Principals",
     "Access, correction and/or erasure",
     "The organization shall implement policies, procedures and/or mechanisms to meet their obligations to PII principals to access, correct and/or erase their PII."),
    ("A.7.3.7", "PII Controllers — Obligations to Principals",
     "PII controllers' obligations to inform third parties",
     "The organization shall inform third parties with whom PII has been shared of any modification, withdrawal or objections pertaining to the shared PII."),
    ("A.7.3.8", "PII Controllers — Obligations to Principals",
     "Providing copy of PII processed",
     "The organization shall be able to provide a copy of the PII that is processed when requested by the PII principal."),
    ("A.7.3.9", "PII Controllers — Obligations to Principals",
     "Handling requests",
     "The organization shall define and document policies and procedures for handling and responding to legitimate requests from PII principals."),
    ("A.7.3.10", "PII Controllers — Obligations to Principals",
     "Automated decision-making",
     "The organization shall identify and address obligations, including legal obligations, to the PII principals resulting from decisions made by the organization that are related to the PII principal based solely on automated processing of PII."),
    # A.7.4 — Privacy by design / default
    ("A.7.4.1", "PII Controllers — Privacy by Design",
     "Limit collection",
     "The organization shall limit the collection of PII to the minimum that is relevant, proportional and necessary for the identified purposes."),
    ("A.7.4.2", "PII Controllers — Privacy by Design",
     "Limit processing",
     "The organization shall limit the processing of PII to that which is adequate, relevant and necessary for the identified purposes."),
    ("A.7.4.3", "PII Controllers — Privacy by Design",
     "Accuracy and quality",
     "The organization shall ensure and document that PII is as accurate, complete and up-to-date as is necessary for the purposes for which it is processed, throughout the lifecycle of the PII."),
    ("A.7.4.4", "PII Controllers — Privacy by Design",
     "PII minimization objectives",
     "The organization shall define and document data minimisation objectives and what mechanisms (such as de-identification) are used to meet those objectives."),
    ("A.7.4.5", "PII Controllers — Privacy by Design",
     "PII de-identification and deletion at the end of processing",
     "The organization shall either delete PII or render it in a form which does not permit identification or re-identification of PII principals, as soon as the original PII is no longer necessary for the identified purposes."),
    ("A.7.4.6", "PII Controllers — Privacy by Design",
     "Temporary files",
     "The organization shall ensure that temporary files created as a result of the processing of PII are disposed of (e.g., erased or destroyed) following documented procedures within a specified, documented period of time."),
    ("A.7.4.7", "PII Controllers — Privacy by Design",
     "Retention",
     "The organization shall not retain PII for longer than is necessary for the purposes for which the PII is processed."),
    ("A.7.4.8", "PII Controllers — Privacy by Design",
     "Disposal",
     "The organization shall have documented policies, procedures and/or mechanisms for the disposal of PII."),
    ("A.7.4.9", "PII Controllers — Privacy by Design",
     "PII transmission controls",
     "The organization shall subject PII transmitted (e.g., sent to another organization) to appropriate controls designed to ensure that the data reaches its intended destination."),
    # A.7.5 — PII sharing, transfer and disclosure
    ("A.7.5.1", "PII Controllers — PII Sharing & Transfer",
     "Identify basis for PII transfer between jurisdictions",
     "The organization shall identify and document the relevant basis for transfers of PII between jurisdictions."),
    ("A.7.5.2", "PII Controllers — PII Sharing & Transfer",
     "Countries and international organizations to which PII can be transferred",
     "The organization shall specify and document the countries and international organisations to which PII can possibly be transferred."),
    ("A.7.5.3", "PII Controllers — PII Sharing & Transfer",
     "Records of PII transfer",
     "The organization shall record transfers of PII to or from third parties, ensuring co-operation with those parties to support future requests related to obligations to PII principals."),
    ("A.7.5.4", "PII Controllers — PII Sharing & Transfer",
     "Records of PII disclosure to third parties",
     "The organization shall record disclosures of PII to third parties, including what PII has been disclosed, to whom and at what time."),
]


# ---------------------------------------------------------------------------
# Annex B — PII Processors (18 controls across B.8.2 – B.8.5)
# ---------------------------------------------------------------------------
ISO27701_ANNEX_B: list[tuple[str, str, str, str]] = [
    # B.8.2 — Conditions for collection and processing
    ("B.8.2.1", "PII Processors — Collection & Processing",
     "Customer agreement",
     "The organization shall ensure, where relevant, that the contract to process PII addresses the organization's role in providing assistance with the customer's obligations (taking into account the nature of processing and the information available to the organization)."),
    ("B.8.2.2", "PII Processors — Collection & Processing",
     "Organization's purposes",
     "The organization shall ensure that PII processed on behalf of a customer are only processed for the purposes expressed in the documented instructions of the customer."),
    ("B.8.2.3", "PII Processors — Collection & Processing",
     "Marketing and advertising use",
     "The organization shall not use PII processed under a contract with a customer for the purposes of marketing and advertising without establishing that prior consent was obtained from the appropriate PII principal."),
    ("B.8.2.4", "PII Processors — Collection & Processing",
     "Infringing instruction",
     "The organization shall inform the customer if, in its opinion, a processing instruction infringes applicable legislation and/or regulation."),
    ("B.8.2.5", "PII Processors — Collection & Processing",
     "Customer obligations",
     "The organization shall provide the customer with the appropriate information such that the customer can demonstrate compliance with their obligations."),
    ("B.8.2.6", "PII Processors — Collection & Processing",
     "Records related to processing PII",
     "The organization shall determine and maintain the necessary records in support of demonstrating compliance with its obligations (as specified in the applicable contract) for the processing of PII carried out on behalf of a customer."),
    # B.8.3 — Obligations to PII principals
    ("B.8.3.1", "PII Processors — Obligations to Principals",
     "Obligations to PII principals",
     "The organization shall provide the customer with the means to comply with its obligations related to PII principals."),
    # B.8.4 — Privacy by design / default
    ("B.8.4.1", "PII Processors — Privacy by Design",
     "Temporary files",
     "The organization shall ensure that temporary files created as a result of the processing of PII are disposed of within a specified period of time."),
    ("B.8.4.2", "PII Processors — Privacy by Design",
     "Return, transfer or disposal of PII",
     "The organization shall provide the ability to return, transfer and/or dispose of PII in a secure manner. It shall also make its policy available to the customer."),
    ("B.8.4.3", "PII Processors — Privacy by Design",
     "PII transmission controls",
     "The organization shall subject PII transmitted over a data-transmission network to appropriate controls designed to ensure that the data reaches its intended destination."),
    # B.8.5 — PII sharing, transfer and disclosure
    ("B.8.5.1", "PII Processors — PII Sharing & Transfer",
     "Basis for PII transfer between jurisdictions",
     "The organization shall inform the customer in a timely manner of the basis for transfers of PII between jurisdictions and of any intended changes."),
    ("B.8.5.2", "PII Processors — PII Sharing & Transfer",
     "Countries and international organizations to which PII can be transferred",
     "The organization shall specify and document the countries and international organisations to which PII can possibly be transferred."),
    ("B.8.5.3", "PII Processors — PII Sharing & Transfer",
     "Records of PII disclosure to third parties",
     "The organization shall record disclosures of PII to third parties, including what PII has been disclosed, to whom and when."),
    ("B.8.5.4", "PII Processors — PII Sharing & Transfer",
     "Notification of PII disclosure requests",
     "The organization shall notify the customer of any legally binding requests for disclosure of PII."),
    ("B.8.5.5", "PII Processors — PII Sharing & Transfer",
     "Legally binding PII disclosures",
     "The organization shall reject any requests for PII disclosures that are not legally binding, consult with the corresponding customer before making any PII disclosures, and accept any contractually agreed requests for PII disclosures that are authorised by the customer."),
    ("B.8.5.6", "PII Processors — PII Sharing & Transfer",
     "Disclosure of sub-contractors used to process PII",
     "The organization shall disclose any use of sub-contractors to process PII to the customer before use."),
    ("B.8.5.7", "PII Processors — PII Sharing & Transfer",
     "Engagement of a sub-contractor to process PII",
     "The organization shall only engage a sub-contractor to process PII according to the customer contract."),
    ("B.8.5.8", "PII Processors — PII Sharing & Transfer",
     "Change of sub-contractor to process PII",
     "The organization shall, in the case of having general written authorization, inform the customer of any intended changes concerning the addition or replacement of sub-contractors to process PII, thereby giving the customer the opportunity to object to such changes."),
]


ALL_ISO27701_CONTROLS = ISO27701_PIMS + ISO27701_ANNEX_A + ISO27701_ANNEX_B


async def seed_iso27701(session: AsyncSession) -> None:
    """Idempotent ISO/IEC 27701 seeder."""
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
            "ISO/IEC 27701:2019 — Privacy Information Management System (PIMS). "
            "Extends ISO 27001 / 27002 with privacy-specific requirements and controls. "
            "Annex A (31 controls) covers PII controllers and Annex B (18 controls) covers "
            "PII processors. Often used as the GDPR / DPDP audit-grade companion."
        ),
    )
    session.add(framework)
    await session.flush()

    version = FrameworkVersion(
        id=str(uuid.uuid4()),
        framework_id=framework.id,
        version=FRAMEWORK_VERSION,
        effective_date=date(2019, 8, 6),
        is_current=True,
    )
    session.add(version)
    await session.flush()

    for control_code, category, title, description in ALL_ISO27701_CONTROLS:
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
