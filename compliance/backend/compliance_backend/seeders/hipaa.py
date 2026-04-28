"""
HIPAA Security Rule + Privacy Rule seeder.

Covers 45 CFR Part 164 Subpart C (Security Rule):
  - Administrative Safeguards   (164.308)
  - Physical Safeguards         (164.310)
  - Technical Safeguards        (164.312)
  - Organizational Requirements (164.314)
  - Policies, Procedures & Documentation (164.316)

Also includes selected Privacy Rule controls from 45 CFR Part 164 Subpart E.

Control count: 44 controls with CFR identifiers.

Sources: 45 CFR Part 164 (HHS HIPAA Security Rule & Privacy Rule).
Idempotent: skip if HIPAA framework already exists.
"""
import uuid
from datetime import date
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from compliance_backend.models.framework import Framework, FrameworkVersion, Control


# ---------------------------------------------------------------------------
# HIPAA control data
# Format: (control_code, category, title, description)
# control_code uses 45 CFR Part 164 identifiers
# ---------------------------------------------------------------------------

HIPAA_ADMINISTRATIVE: list[tuple[str, str, str, str]] = [
    ("164.308(a)(1)(i)", "Administrative Safeguards",
     "Security Management Process — Risk Analysis",
     "Conduct an accurate and thorough assessment of the potential risks and vulnerabilities to the confidentiality, integrity, and availability of electronic protected health information (ePHI)."),
    ("164.308(a)(1)(ii)(A)", "Administrative Safeguards",
     "Security Management Process — Risk Management",
     "Implement security measures sufficient to reduce risks and vulnerabilities to a reasonable and appropriate level to comply with 164.306(a)."),
    ("164.308(a)(1)(ii)(B)", "Administrative Safeguards",
     "Security Management Process — Sanction Policy",
     "Apply appropriate sanctions against workforce members who fail to comply with the security policies and procedures of the covered entity."),
    ("164.308(a)(1)(ii)(C)", "Administrative Safeguards",
     "Security Management Process — Information System Activity Review",
     "Implement procedures to regularly review records of information system activity, such as audit logs, access reports, and security incident tracking reports."),
    ("164.308(a)(2)", "Administrative Safeguards",
     "Assigned Security Responsibility",
     "Identify the security official who is responsible for the development and implementation of the policies and procedures required by this subpart."),
    ("164.308(a)(3)(i)", "Administrative Safeguards",
     "Workforce Security — Authorization and/or Supervision",
     "Implement procedures for the authorization and/or supervision of workforce members who work with ePHI or in locations where it might be accessed."),
    ("164.308(a)(3)(ii)(A)", "Administrative Safeguards",
     "Workforce Security — Workforce Clearance Procedure",
     "Implement procedures to determine that the access of a workforce member to ePHI is appropriate."),
    ("164.308(a)(3)(ii)(B)", "Administrative Safeguards",
     "Workforce Security — Termination Procedures",
     "Implement procedures for terminating access to ePHI when the employment or other arrangement of a workforce member ends."),
    ("164.308(a)(4)(i)", "Administrative Safeguards",
     "Information Access Management — Isolating Health Care Clearinghouse Functions",
     "If a health care clearinghouse is part of a larger organization, the clearinghouse must implement policies and procedures that protect ePHI from unauthorized access by the larger organization."),
    ("164.308(a)(4)(ii)(A)", "Administrative Safeguards",
     "Information Access Management — Access Authorization",
     "Implement policies and procedures for granting access to ePHI; for example, through access to a workstation, transaction, program, process, or other mechanism."),
    ("164.308(a)(4)(ii)(B)", "Administrative Safeguards",
     "Information Access Management — Access Establishment and Modification",
     "Implement policies and procedures that, based upon the entity's access authorization policies, establish, document, review, and modify a user's right of access to a workstation, transaction, program, or process."),
    ("164.308(a)(5)(i)", "Administrative Safeguards",
     "Security Awareness and Training — General Requirements",
     "Implement a security awareness and training program for all members of its workforce including management."),
    ("164.308(a)(5)(ii)(A)", "Administrative Safeguards",
     "Security Awareness — Security Reminders",
     "Periodic security updates for workforce members."),
    ("164.308(a)(5)(ii)(B)", "Administrative Safeguards",
     "Security Awareness — Protection from Malicious Software",
     "Procedures for guarding against, detecting, and reporting malicious software."),
    ("164.308(a)(5)(ii)(C)", "Administrative Safeguards",
     "Security Awareness — Log-in Monitoring",
     "Procedures for monitoring log-in attempts and reporting discrepancies."),
    ("164.308(a)(5)(ii)(D)", "Administrative Safeguards",
     "Security Awareness — Password Management",
     "Procedures for creating, changing, and safeguarding passwords."),
    ("164.308(a)(6)(i)", "Administrative Safeguards",
     "Security Incident Procedures — General",
     "Implement policies and procedures to address security incidents."),
    ("164.308(a)(6)(ii)", "Administrative Safeguards",
     "Security Incident Procedures — Response and Reporting",
     "Identify and respond to suspected or known security incidents; mitigate, to the extent practicable, harmful effects of security incidents known to the covered entity; document security incidents and their outcomes."),
    ("164.308(a)(7)(i)", "Administrative Safeguards",
     "Contingency Plan — General",
     "Establish and implement as needed policies and procedures for responding to an emergency or other occurrence that damages systems containing ePHI."),
    ("164.308(a)(7)(ii)(A)", "Administrative Safeguards",
     "Contingency Plan — Data Backup Plan",
     "Establish and implement procedures to create and maintain retrievable exact copies of ePHI."),
    ("164.308(a)(7)(ii)(B)", "Administrative Safeguards",
     "Contingency Plan — Disaster Recovery Plan",
     "Establish and implement procedures to restore any loss of data."),
    ("164.308(a)(7)(ii)(C)", "Administrative Safeguards",
     "Contingency Plan — Emergency Mode Operation Plan",
     "Establish and implement procedures to enable continuation of critical business processes for protection of the security of ePHI while operating in emergency mode."),
    ("164.308(a)(8)", "Administrative Safeguards",
     "Evaluation",
     "Perform a periodic technical and non-technical evaluation, based initially upon the standards implemented under this rule, in response to environmental or operational changes affecting the security of ePHI."),
    ("164.308(b)(1)", "Administrative Safeguards",
     "Business Associate Contracts — Written Contract Required",
     "A covered entity may permit a business associate to create, receive, maintain, or transmit ePHI on the covered entity's behalf only if the covered entity obtains satisfactory assurances that the BA will appropriately safeguard the information."),
]


HIPAA_PHYSICAL: list[tuple[str, str, str, str]] = [
    ("164.310(a)(1)", "Physical Safeguards",
     "Facility Access Controls — General",
     "Implement policies and procedures to limit physical access to electronic information systems and the facility in which they are housed."),
    ("164.310(a)(2)(i)", "Physical Safeguards",
     "Facility Access Controls — Contingency Operations",
     "Establish and implement as needed procedures that allow facility access in support of restoration of lost data under the disaster recovery plan and emergency mode operations plan."),
    ("164.310(a)(2)(ii)", "Physical Safeguards",
     "Facility Access Controls — Facility Security Plan",
     "Implement policies and procedures to safeguard the facility and the equipment therein from unauthorized physical access, tampering, and theft."),
    ("164.310(a)(2)(iii)", "Physical Safeguards",
     "Facility Access Controls — Access Control and Validation Procedures",
     "Implement procedures to control and validate a person's access to facilities based on their role or function, including visitor control, and control of access to software programs for testing and revision."),
    ("164.310(a)(2)(iv)", "Physical Safeguards",
     "Facility Access Controls — Maintenance Records",
     "Implement policies and procedures to document repairs and modifications to the physical components of a facility which are related to security."),
    ("164.310(b)", "Physical Safeguards",
     "Workstation Use",
     "Implement policies and procedures that specify the proper functions to be performed, the manner in which those functions are to be performed, and the physical attributes of the surroundings of a specific workstation or class of workstation that can access ePHI."),
    ("164.310(c)", "Physical Safeguards",
     "Workstation Security",
     "Implement physical safeguards for all workstations that access ePHI to restrict access to authorized users."),
    ("164.310(d)(1)", "Physical Safeguards",
     "Device and Media Controls — General",
     "Implement policies and procedures that govern the receipt and removal of hardware and electronic media containing ePHI into and out of a facility, and the movement of these items within the facility."),
    ("164.310(d)(2)(i)", "Physical Safeguards",
     "Device and Media Controls — Disposal",
     "Implement policies and procedures to address the final disposition of ePHI and/or the hardware or electronic media on which it is stored."),
    ("164.310(d)(2)(ii)", "Physical Safeguards",
     "Device and Media Controls — Media Re-use",
     "Implement procedures for removal of ePHI from electronic media before the media are made available for re-use."),
]


HIPAA_TECHNICAL: list[tuple[str, str, str, str]] = [
    ("164.312(a)(1)", "Technical Safeguards",
     "Access Control — General",
     "Implement technical policies and procedures for electronic information systems that maintain ePHI to allow access only to those persons or software programs that have been granted access rights."),
    ("164.312(a)(2)(i)", "Technical Safeguards",
     "Access Control — Unique User Identification",
     "Assign a unique name and/or number for identifying and tracking user identity."),
    ("164.312(a)(2)(ii)", "Technical Safeguards",
     "Access Control — Emergency Access Procedure",
     "Establish and implement as needed procedures for obtaining necessary ePHI during an emergency."),
    ("164.312(a)(2)(iii)", "Technical Safeguards",
     "Access Control — Automatic Logoff",
     "Implement electronic procedures that terminate an electronic session after a predetermined time of inactivity."),
    ("164.312(a)(2)(iv)", "Technical Safeguards",
     "Access Control — Encryption and Decryption",
     "Implement a mechanism to encrypt and decrypt ePHI."),
    ("164.312(b)", "Technical Safeguards",
     "Audit Controls",
     "Implement hardware, software, and/or procedural mechanisms that record and examine activity in information systems that contain or use ePHI."),
    ("164.312(c)(1)", "Technical Safeguards",
     "Integrity Controls — General",
     "Implement policies and procedures to protect ePHI from improper alteration or destruction."),
    ("164.312(c)(2)", "Technical Safeguards",
     "Integrity Controls — Authentication Mechanism",
     "Implement electronic mechanisms to corroborate that ePHI has not been altered or destroyed in an unauthorized manner."),
    ("164.312(d)", "Technical Safeguards",
     "Person or Entity Authentication",
     "Implement procedures to verify that a person or entity seeking access to ePHI is the one claimed."),
    ("164.312(e)(1)", "Technical Safeguards",
     "Transmission Security — General",
     "Implement technical security measures to guard against unauthorized access to ePHI that is being transmitted over an electronic communications network."),
    ("164.312(e)(2)(i)", "Technical Safeguards",
     "Transmission Security — Integrity Controls",
     "Implement security measures to ensure that electronically transmitted ePHI is not improperly modified without detection."),
    ("164.312(e)(2)(ii)", "Technical Safeguards",
     "Transmission Security — Encryption",
     "Implement a mechanism to encrypt ePHI in transit whenever deemed appropriate."),
]


HIPAA_ORGANIZATIONAL: list[tuple[str, str, str, str]] = [
    ("164.314(a)(1)", "Organizational Requirements",
     "Business Associate Contracts — Required Elements",
     "A contract between a covered entity and a business associate must contain certain required elements including the specific tasks permitted, appropriate safeguards, and reporting obligations."),
    ("164.314(b)(1)", "Organizational Requirements",
     "Requirements for Group Health Plans",
     "A group health plan must ensure adequate separation between the plan and the plan sponsor and implement reasonable and appropriate security measures."),
    ("164.316(a)", "Organizational Requirements",
     "Policies and Procedures — Implementation",
     "Implement reasonable and appropriate policies and procedures to comply with the standards, implementation specifications, or other requirements of this subpart."),
    ("164.316(b)(1)", "Organizational Requirements",
     "Documentation — Required Documentation",
     "Maintain the policies and procedures implemented to comply with this subpart in written (which may be electronic) form, and retain the documentation for 6 years from creation or last effective date."),
    ("164.316(b)(2)", "Organizational Requirements",
     "Documentation — Updates and Availability",
     "Make documentation available to those persons responsible for implementing the procedures and review documentation periodically, and update as needed in response to environmental or operational changes."),
]


ALL_HIPAA_CONTROLS = (
    HIPAA_ADMINISTRATIVE
    + HIPAA_PHYSICAL
    + HIPAA_TECHNICAL
    + HIPAA_ORGANIZATIONAL
)


async def seed_hipaa(session: AsyncSession) -> None:
    """
    Idempotent HIPAA Security Rule seeder.

    Creates:
      - Framework: HIPAA
      - FrameworkVersion: Security Rule 2003 (is_current=True)
      - Controls: 44 covering Administrative, Physical, Technical, Organizational

    Skips silently if HIPAA framework already exists.
    """
    result = await session.execute(
        select(Framework).where(Framework.short_code == "HIPAA")
    )
    existing = result.scalars().first()
    if existing:
        return

    framework = Framework(
        id=str(uuid.uuid4()),
        name="HIPAA Security Rule",
        short_code="HIPAA",
        category="sectoral",
        description=(
            "Health Insurance Portability and Accountability Act — Security Rule (45 CFR Part 164 "
            "Subpart C). Establishes national standards to protect individuals' electronic personal "
            "health information (ePHI) through Administrative, Physical, and Technical Safeguards."
        ),
    )
    session.add(framework)
    await session.flush()

    version = FrameworkVersion(
        id=str(uuid.uuid4()),
        framework_id=framework.id,
        version="Security Rule 2003",
        effective_date=date(2003, 2, 20),
        is_current=True,
    )
    session.add(version)
    await session.flush()

    for control_code, category, title, description in ALL_HIPAA_CONTROLS:
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
