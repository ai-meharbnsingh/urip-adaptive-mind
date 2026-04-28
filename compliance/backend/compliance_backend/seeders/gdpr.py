"""
GDPR (General Data Protection Regulation) seeder.

Covers Articles 5-39 as the control surface:
  - Data Protection Principles (Art. 5–11)
  - Rights of Data Subjects (Art. 12–22)
  - Controller & Processor Obligations (Art. 24–43)

Control count: 37 controls.

Sources: GDPR text (OJ L 119, 4.5.2016), EUR-Lex — verified article references.
Idempotent: skip if GDPR framework already exists.
"""
import uuid
from datetime import date
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from compliance_backend.models.framework import Framework, FrameworkVersion, Control


# ---------------------------------------------------------------------------
# GDPR control data
# Format: (control_code, category, title, description)
# control_code uses real GDPR article references: Art. X(Y)(Z)
# ---------------------------------------------------------------------------

GDPR_PRINCIPLES: list[tuple[str, str, str, str]] = [
    # Chapter II — Principles
    ("Art. 5(1)(a)", "Data Protection Principles",
     "Lawfulness, Fairness and Transparency",
     "Personal data shall be processed lawfully, fairly and in a transparent manner in relation to the data subject."),
    ("Art. 5(1)(b)", "Data Protection Principles",
     "Purpose Limitation",
     "Personal data shall be collected for specified, explicit and legitimate purposes and not further processed in a manner incompatible with those purposes."),
    ("Art. 5(1)(c)", "Data Protection Principles",
     "Data Minimisation",
     "Personal data shall be adequate, relevant and limited to what is necessary in relation to the purposes for which they are processed."),
    ("Art. 5(1)(d)", "Data Protection Principles",
     "Accuracy",
     "Personal data shall be accurate and, where necessary, kept up to date; every reasonable step must be taken to rectify or erase inaccurate data."),
    ("Art. 5(1)(e)", "Data Protection Principles",
     "Storage Limitation",
     "Personal data shall be kept in a form which permits identification of data subjects for no longer than is necessary for the purposes of processing."),
    ("Art. 5(1)(f)", "Data Protection Principles",
     "Integrity and Confidentiality",
     "Personal data shall be processed using appropriate technical or organisational measures to ensure appropriate security, including protection against unlawful processing or accidental loss."),
    ("Art. 5(2)", "Data Protection Principles",
     "Accountability",
     "The controller shall be responsible for, and be able to demonstrate compliance with, the data protection principles."),
    ("Art. 6(1)", "Data Protection Principles",
     "Lawfulness of Processing — Legal Basis",
     "Processing shall be lawful only if and to the extent that at least one of the six legal bases applies: consent, contract, legal obligation, vital interests, public task, or legitimate interests."),
    ("Art. 7", "Data Protection Principles",
     "Conditions for Consent",
     "Where processing is based on consent, the controller shall be able to demonstrate that the data subject has consented. Consent shall be freely given, specific, informed, and unambiguous."),
    ("Art. 9(1)", "Data Protection Principles",
     "Processing of Special Categories of Personal Data — Prohibition",
     "Processing of special categories (racial/ethnic origin, political opinions, religious beliefs, health, biometric data, etc.) is prohibited except under specific conditions."),
    ("Art. 9(2)", "Data Protection Principles",
     "Special Categories — Permitted Grounds",
     "Processing of special category data is permitted where explicit consent is given, or where processing is necessary for specified legitimate purposes."),
    ("Art. 11", "Data Protection Principles",
     "Processing Not Requiring Identification",
     "Where the purpose of processing does not require identification of a data subject, the controller shall not be obliged to maintain additional information to comply with this Regulation."),
]


GDPR_RIGHTS: list[tuple[str, str, str, str]] = [
    # Chapter III — Rights of Data Subjects
    ("Art. 12", "Rights of Data Subjects",
     "Transparent Information and Communication",
     "The controller shall take appropriate measures to provide information to the data subject in a concise, transparent, intelligible, and easily accessible form."),
    ("Art. 13", "Rights of Data Subjects",
     "Information to be Provided — Data Collected Directly",
     "Where personal data relating to a data subject are collected from the data subject, the controller shall provide specific information at the time of collection."),
    ("Art. 14", "Rights of Data Subjects",
     "Information to be Provided — Data Not Collected Directly",
     "Where personal data are not obtained from the data subject, the controller shall provide information about the source and nature of processing within a reasonable period."),
    ("Art. 15", "Rights of Data Subjects",
     "Right of Access by the Data Subject",
     "The data subject shall have the right to obtain from the controller confirmation as to whether personal data concerning them is being processed, and access to that data."),
    ("Art. 16", "Rights of Data Subjects",
     "Right to Rectification",
     "The data subject shall have the right to obtain from the controller without undue delay the rectification of inaccurate personal data."),
    ("Art. 17", "Rights of Data Subjects",
     "Right to Erasure ('Right to be Forgotten')",
     "The data subject shall have the right to obtain from the controller the erasure of personal data concerning them without undue delay under specified circumstances."),
    ("Art. 18", "Rights of Data Subjects",
     "Right to Restriction of Processing",
     "The data subject shall have the right to obtain from the controller restriction of processing where one of the specified conditions applies."),
    ("Art. 19", "Rights of Data Subjects",
     "Notification Obligation — Rectification, Erasure, Restriction",
     "The controller shall communicate any rectification, erasure, or restriction of processing to each recipient to whom the personal data has been disclosed."),
    ("Art. 20", "Rights of Data Subjects",
     "Right to Data Portability",
     "The data subject shall have the right to receive personal data concerning them in a structured, commonly used and machine-readable format and have the right to transmit those data to another controller."),
    ("Art. 21", "Rights of Data Subjects",
     "Right to Object",
     "The data subject shall have the right to object, on grounds relating to their particular situation, to processing of personal data based on legitimate interests or public task."),
    ("Art. 22", "Rights of Data Subjects",
     "Automated Individual Decision-Making Including Profiling",
     "The data subject shall have the right not to be subject to a decision based solely on automated processing, including profiling, which produces legal or similarly significant effects."),
]


GDPR_CONTROLLER_OBLIGATIONS: list[tuple[str, str, str, str]] = [
    # Chapter IV — Controller & Processor
    ("Art. 24", "Controller Obligations",
     "Responsibility of the Controller",
     "Taking into account the nature, scope, context and purposes of processing, the controller shall implement appropriate technical and organisational measures to ensure processing in accordance with this Regulation."),
    ("Art. 25", "Controller Obligations",
     "Data Protection by Design and by Default",
     "The controller shall implement appropriate technical and organisational measures designed to implement data protection principles effectively (privacy by design). By default, only data necessary for each specific purpose shall be processed (privacy by default)."),
    ("Art. 26", "Controller Obligations",
     "Joint Controllers",
     "Where two or more controllers jointly determine the purposes and means of processing, they shall be joint controllers and shall in a transparent manner determine their respective responsibilities."),
    ("Art. 28", "Controller Obligations",
     "Processor — Data Processing Agreement",
     "Where processing is carried out on behalf of a controller, processing by a processor shall be governed by a binding contract setting out the subject-matter, duration, nature and purpose of processing."),
    ("Art. 30", "Controller Obligations",
     "Records of Processing Activities",
     "Each controller and processor shall maintain a record of processing activities under its responsibility (ROPA), containing information on the categories of data, purposes, recipients, and retention periods."),
    ("Art. 32", "Controller Obligations",
     "Security of Processing",
     "Taking into account the state of the art, costs, and nature of risks, the controller and processor shall implement appropriate technical and organisational measures to ensure a level of security appropriate to the risk, including encryption, pseudonymisation, resilience, and restoration capability."),
    ("Art. 33", "Controller Obligations",
     "Notification of Personal Data Breach to Supervisory Authority",
     "In the case of a personal data breach, the controller shall notify the supervisory authority without undue delay and, where feasible, within 72 hours of becoming aware of the breach."),
    ("Art. 34", "Controller Obligations",
     "Communication of Personal Data Breach to the Data Subject",
     "When the personal data breach is likely to result in a high risk to the rights and freedoms of natural persons, the controller shall communicate the breach to the data subject without undue delay."),
    ("Art. 35", "Controller Obligations",
     "Data Protection Impact Assessment (DPIA)",
     "Where processing is likely to result in a high risk to the rights and freedoms of natural persons, the controller shall carry out a DPIA of the envisaged processing operations prior to processing."),
    ("Art. 37", "Controller Obligations",
     "Designation of the Data Protection Officer",
     "The controller and the processor shall designate a data protection officer where required (public authorities, large-scale processing of special categories, or large-scale systematic monitoring)."),
    ("Art. 38", "Controller Obligations",
     "Position of the Data Protection Officer",
     "The controller and the processor shall ensure that the DPO is involved, properly and in a timely manner, in all issues relating to the protection of personal data."),
    ("Art. 39", "Controller Obligations",
     "Tasks of the Data Protection Officer",
     "The DPO shall inform and advise, monitor compliance, provide advice on DPIA, cooperate with, and act as contact point for, the supervisory authority."),
    ("Art. 44", "Controller Obligations",
     "General Principle for Transfers to Third Countries",
     "Any transfer of personal data to a third country or international organisation shall take place only if the conditions of Chapter V are complied with."),
    ("Art. 46", "Controller Obligations",
     "Transfers Subject to Appropriate Safeguards",
     "A controller or processor may transfer personal data to a third country only if appropriate safeguards (standard contractual clauses, binding corporate rules, approved codes of conduct, etc.) have been provided."),
]

ALL_GDPR_CONTROLS = GDPR_PRINCIPLES + GDPR_RIGHTS + GDPR_CONTROLLER_OBLIGATIONS


async def seed_gdpr(session: AsyncSession) -> None:
    """
    Idempotent GDPR framework seeder.

    Creates:
      - Framework: GDPR
      - FrameworkVersion: 2016/679 (is_current=True)
      - Controls: 37 covering data protection principles, rights, controller obligations

    Skips silently if GDPR framework already exists.
    """
    result = await session.execute(
        select(Framework).where(Framework.short_code == "GDPR")
    )
    existing = result.scalars().first()
    if existing:
        return

    framework = Framework(
        id=str(uuid.uuid4()),
        name="GDPR — General Data Protection Regulation",
        short_code="GDPR",
        category="privacy",
        description=(
            "EU Regulation 2016/679 on the protection of natural persons with regard to the "
            "processing of personal data and on the free movement of such data. Entered into "
            "force 25 May 2018. Covers data protection principles, rights of data subjects, "
            "and obligations of controllers and processors."
        ),
    )
    session.add(framework)
    await session.flush()

    version = FrameworkVersion(
        id=str(uuid.uuid4()),
        framework_id=framework.id,
        version="2016/679",
        effective_date=date(2018, 5, 25),
        is_current=True,
    )
    session.add(version)
    await session.flush()

    for control_code, category, title, description in ALL_GDPR_CONTROLS:
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
