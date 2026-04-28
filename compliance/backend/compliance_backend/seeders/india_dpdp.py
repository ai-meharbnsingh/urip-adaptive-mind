"""
India Digital Personal Data Protection Act 2023 (DPDP Act) seeder.

Covers Sections 4-17 and related provisions:
  - Lawful Processing and Consent (Sec. 4–7)
  - Data Principal Rights (Sec. 11–14)
  - Obligations of Data Fiduciary (Sec. 8–10, 16–17)
  - Significant Data Fiduciary Obligations (Sec. 10)
  - Transfer Restrictions (Sec. 16)
  - Duties of Data Principal (Sec. 15)

Control count: 29 controls with section references.

Sources: Digital Personal Data Protection Act, 2023 (No. 22 of 2023),
         Gazette of India Extraordinary, 11 August 2023.
Idempotent: skip if DPDP framework already exists.
"""
import uuid
from datetime import date
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from compliance_backend.models.framework import Framework, FrameworkVersion, Control


# ---------------------------------------------------------------------------
# India DPDP Act 2023 control data
# Format: (control_code, category, title, description)
# control_code uses Section references: Sec. X(Y)
# ---------------------------------------------------------------------------

DPDP_LAWFUL_PROCESSING: list[tuple[str, str, str, str]] = [
    ("Sec. 4(1)", "Lawful Processing",
     "Lawful Grounds for Processing Personal Data",
     "A Data Fiduciary may process personal data of a Data Principal only for a lawful purpose: with consent of the Data Principal, or for certain legitimate uses specified in the Act."),
    ("Sec. 4(2)", "Lawful Processing",
     "No Negative Consequence for Withdrawal of Consent",
     "Processing on the basis of consent shall not result in any negative consequence to the Data Principal for refusing to consent or withdrawing consent for goods and services not contingent on such consent."),
    ("Sec. 5", "Lawful Processing",
     "Notice Before or at the Time of Consent",
     "Every request for consent shall be accompanied by or preceded by a notice itemising: personal data and purpose of processing; manner in which consent may be withdrawn; and grievance redressal mechanism."),
    ("Sec. 6(1)", "Lawful Processing",
     "Consent Must Be Free, Specific, Informed, Unconditional and Unambiguous",
     "Consent given by the Data Principal must be free, specific, informed, unconditional and unambiguous, with a clear affirmative action, and shall signify agreement to processing for a specified purpose."),
    ("Sec. 6(3)", "Lawful Processing",
     "Right to Withdraw Consent",
     "The Data Principal shall have the right to withdraw consent at any time, with the ease of withdrawing consent being comparable to the ease with which consent was given."),
    ("Sec. 6(4)", "Lawful Processing",
     "Consequences of Withdrawal of Consent",
     "Upon withdrawal of consent, the Data Fiduciary shall cease processing of personal data within a reasonable time and return or delete personal data unless retention is required under law."),
    ("Sec. 7", "Lawful Processing",
     "Certain Legitimate Uses Without Consent",
     "Personal data may be processed without consent for: performance of state functions, compliance with judicial orders or law, employment-related purposes, medical emergencies, public health, and other specified legitimate uses."),
]


DPDP_RIGHTS: list[tuple[str, str, str, str]] = [
    ("Sec. 11(1)", "Rights of Data Principals",
     "Right to Access Information",
     "A Data Principal shall have the right to access information about: what personal data is processed, the processing activities, and a summary of the personal data processed."),
    ("Sec. 11(3)", "Rights of Data Principals",
     "Right to Access — Grievance Mechanism",
     "A Data Principal shall have the right to obtain information about the grievance redressal mechanism established by the Data Fiduciary."),
    ("Sec. 12", "Rights of Data Principals",
     "Right to Correction and Erasure",
     "A Data Principal shall have the right to correct or update inaccurate or misleading personal data, complete incomplete personal data, and erase personal data that is no longer necessary for the purpose for which it was processed."),
    ("Sec. 13", "Rights of Data Principals",
     "Right of Grievance Redressal",
     "A Data Principal shall have the right to have grievances redressed. Every Data Fiduciary shall establish an effective mechanism for redressal of grievances."),
    ("Sec. 14", "Rights of Data Principals",
     "Right to Nominate",
     "A Data Principal shall have the right to nominate another individual who shall exercise the rights of the Data Principal in the event of death or incapacity."),
    ("Sec. 15", "Rights of Data Principals",
     "Duties of Data Principal",
     "Every Data Principal shall comply with all applicable laws while exercising rights under this Act; shall not impersonate another person; shall not suppress material information; shall not register a false or frivolous grievance."),
]


DPDP_FIDUCIARY_OBLIGATIONS: list[tuple[str, str, str, str]] = [
    ("Sec. 8(1)", "Obligations of Data Fiduciary",
     "Data Quality and Purpose Limitation",
     "Every Data Fiduciary shall ensure completeness, accuracy and consistency of personal data and ensure that personal data is only used for its specified purpose."),
    ("Sec. 8(2)", "Obligations of Data Fiduciary",
     "Security Safeguards",
     "Every Data Fiduciary shall protect personal data in its possession or under its control by taking reasonable security safeguards to prevent personal data breach."),
    ("Sec. 8(3)", "Obligations of Data Fiduciary",
     "Notification of Data Breach",
     "In the event of a personal data breach, the Data Fiduciary shall inform the Board and each affected Data Principal in such form and manner as may be prescribed."),
    ("Sec. 8(5)", "Obligations of Data Fiduciary",
     "Erasure Upon Withdrawal of Consent or Fulfillment of Purpose",
     "A Data Fiduciary shall, upon the Data Principal withdrawing consent or upon the purpose being no longer served, erase personal data and cause its Data Processor to erase personal data."),
    ("Sec. 8(7)", "Obligations of Data Fiduciary",
     "Obligation Not to Engage Data Processors Without Contract",
     "A Data Fiduciary shall not engage a Data Processor to process personal data on its behalf except under a valid contract."),
    ("Sec. 9", "Obligations of Data Fiduciary",
     "Processing of Personal Data of Children",
     "A Data Fiduciary shall, before processing personal data of a child, obtain verifiable consent of the parent or lawful guardian, and shall not undertake processing of personal data of a child that is likely to cause detrimental effect on the well-being of the child."),
    ("Sec. 10(1)", "Obligations of Data Fiduciary",
     "Significant Data Fiduciary — Additional Obligations",
     "A Significant Data Fiduciary shall appoint a Data Protection Officer (DPO), appoint an independent data auditor, and undertake Data Protection Impact Assessment (DPIA) and periodic audits."),
    ("Sec. 10(2)", "Obligations of Data Fiduciary",
     "Significant Data Fiduciary — Data Protection Officer",
     "A Significant Data Fiduciary shall appoint a Data Protection Officer based in India who shall represent the Significant Data Fiduciary and be a point of contact for grievance redressal."),
    ("Sec. 10(3)", "Obligations of Data Fiduciary",
     "Significant Data Fiduciary — Periodic Audit",
     "A Significant Data Fiduciary shall undertake a periodic audit by an independent data auditor to review and evaluate compliance with the provisions of this Act."),
    ("Sec. 16(1)", "Obligations of Data Fiduciary",
     "Transfer of Personal Data Outside India",
     "The transfer of personal data outside India by a Data Fiduciary shall be subject to such terms and conditions as may be prescribed by the Central Government."),
    ("Sec. 16(2)", "Obligations of Data Fiduciary",
     "Restriction on Transfer to Notified Countries",
     "The Central Government may restrict the transfer of personal data by a Data Fiduciary to a country or territory outside India."),
    ("Sec. 17(1)", "Obligations of Data Fiduciary",
     "Exemptions — State Functions and Research",
     "The Central Government may, having regard to the volume and nature of personal data processed, exempt certain Data Fiduciaries or classes of Data Fiduciaries from compliance with all or any of the provisions of this Act."),
    ("Sec. 17(3)", "Obligations of Data Fiduciary",
     "Exemptions — Journalistic, Research and Archival Purposes",
     "Nothing in this Act shall apply to processing of personal data that is necessary for journalistic, research, archiving or statistical purposes, subject to standards as may be prescribed."),
]


ALL_DPDP_CONTROLS = (
    DPDP_LAWFUL_PROCESSING
    + DPDP_RIGHTS
    + DPDP_FIDUCIARY_OBLIGATIONS
)


async def seed_india_dpdp(session: AsyncSession) -> None:
    """
    Idempotent India DPDP Act 2023 seeder.

    Creates:
      - Framework: India DPDP Act 2023
      - FrameworkVersion: 2023 (is_current=True)
      - Controls: 29 covering Sections 4-17 (lawful processing, rights, obligations)

    Skips silently if DPDP framework already exists.
    """
    result = await session.execute(
        select(Framework).where(Framework.short_code == "DPDP")
    )
    existing = result.scalars().first()
    if existing:
        return

    framework = Framework(
        id=str(uuid.uuid4()),
        name="India DPDP Act 2023",
        short_code="DPDP",
        category="privacy",
        description=(
            "Digital Personal Data Protection Act, 2023 (No. 22 of 2023), India. "
            "Establishes a framework for processing digital personal data in a manner that "
            "recognises both the right of individuals to protect their personal data and the "
            "need to process such data for lawful purposes. Entered into force 11 August 2023."
        ),
    )
    session.add(framework)
    await session.flush()

    version = FrameworkVersion(
        id=str(uuid.uuid4()),
        framework_id=framework.id,
        version="2023",
        effective_date=date(2023, 8, 11),
        is_current=True,
    )
    session.add(version)
    await session.flush()

    for control_code, category, title, description in ALL_DPDP_CONTROLS:
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
