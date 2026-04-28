"""
PCI DSS v4.0 seeder.

Covers all 12 main requirements with sub-requirements:
  Req 1  — Install and Maintain Network Security Controls
  Req 2  — Apply Secure Configurations to All System Components
  Req 3  — Protect Stored Account Data
  Req 4  — Protect Cardholder Data with Strong Cryptography During Transmission
  Req 5  — Protect All Systems and Networks from Malicious Software
  Req 6  — Develop and Maintain Secure Systems and Software
  Req 7  — Restrict Access to System Components and Cardholder Data by Business Need to Know
  Req 8  — Identify Users and Authenticate Access to System Components
  Req 9  — Restrict Physical Access to Cardholder Data
  Req 10 — Log and Monitor All Access to System Components and Cardholder Data
  Req 11 — Test Security of Systems and Networks Regularly
  Req 12 — Support Information Security with Organizational Policies and Programs

Control count: 72 controls with PCI DSS v4.0 numbering.

Sources: PCI DSS v4.0 (March 2022), PCI Security Standards Council public document.
Idempotent: skip if PCIDSS framework already exists.
"""
import uuid
from datetime import date
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from compliance_backend.models.framework import Framework, FrameworkVersion, Control


# ---------------------------------------------------------------------------
# PCI DSS v4.0 control data
# Format: (control_code, category, title, description)
# control_code uses PCI DSS v4.0 numbering (X.Y.Z)
# ---------------------------------------------------------------------------

PCI_REQ_1: list[tuple[str, str, str, str]] = [
    ("1.1.1", "Req 1 — Network Security Controls",
     "Processes and mechanisms for installing and maintaining NSCs are defined and understood",
     "All security policies and operational procedures for NSCs are documented, kept up to date, in use, and known to all affected parties."),
    ("1.1.2", "Req 1 — Network Security Controls",
     "Roles and responsibilities for NSC management are defined",
     "Roles and responsibilities for performing activities in Requirement 1 are documented, assigned, and understood."),
    ("1.2.1", "Req 1 — Network Security Controls",
     "Configuration standards for NSC rulesets are defined, implemented, and maintained",
     "Configuration standards for NSC rulesets address known security vulnerabilities and are consistent with industry-accepted system hardening standards."),
    ("1.2.2", "Req 1 — Network Security Controls",
     "All changes to network connections and NSC configurations are approved and managed",
     "All changes to network connections and to NSC configurations are approved and managed in accordance with the change management process."),
    ("1.3.1", "Req 1 — Network Security Controls",
     "Inbound traffic to the CDE is restricted",
     "Inbound traffic to the cardholder data environment (CDE) is restricted to only that which is necessary."),
    ("1.3.2", "Req 1 — Network Security Controls",
     "Outbound traffic from the CDE is restricted",
     "Outbound traffic from the CDE is restricted to only that which is necessary."),
    ("1.4.1", "Req 1 — Network Security Controls",
     "NSCs are installed between trusted and untrusted networks",
     "NSCs are implemented between trusted and untrusted networks."),
    ("1.5.1", "Req 1 — Network Security Controls",
     "Security controls on devices connecting from untrusted networks",
     "Security controls are implemented on any computing devices, including company-owned and employee-owned devices, that connect to both untrusted networks and the CDE."),
]

PCI_REQ_2: list[tuple[str, str, str, str]] = [
    ("2.1.1", "Req 2 — Secure Configurations",
     "Processes and mechanisms for secure configurations are defined and understood",
     "All security policies and operational procedures for Requirement 2 are documented, kept up to date, in use, and known to all affected parties."),
    ("2.2.1", "Req 2 — Secure Configurations",
     "Configuration standards are developed and implemented for all system components",
     "Configuration standards are developed, implemented, and maintained to address all system components. Configuration standards address all known security vulnerabilities and are consistent with industry-accepted system hardening standards."),
    ("2.2.2", "Req 2 — Secure Configurations",
     "Vendor default accounts are managed",
     "Vendor default accounts are managed: either removed, disabled, or changed with a new password."),
    ("2.2.3", "Req 2 — Secure Configurations",
     "Primary functions requiring different security levels are managed",
     "Primary functions requiring different security levels are managed using one of the approaches: separate virtual network functions, or virtual server instance per function."),
    ("2.2.7", "Req 2 — Secure Configurations",
     "All non-console administrative access is encrypted",
     "All non-console administrative access is encrypted using strong cryptography."),
    ("2.3.1", "Req 2 — Secure Configurations",
     "Wireless environments are included in configuration reviews",
     "For wireless environments connected to the CDE or transmitting account data, all wireless vendor defaults are changed at installation or are confirmed to be secure."),
]

PCI_REQ_3: list[tuple[str, str, str, str]] = [
    ("3.1.1", "Req 3 — Protect Stored Account Data",
     "Processes and mechanisms for protecting stored data are defined and understood",
     "All security policies and operational procedures for Requirement 3 are documented, kept up to date, in use, and known to all affected parties."),
    ("3.2.1", "Req 3 — Protect Stored Account Data",
     "Account data storage is kept to a minimum",
     "Account data storage is kept to a minimum through implementation of data retention and disposal policies, procedures, and processes."),
    ("3.3.1", "Req 3 — Protect Stored Account Data",
     "SAD (sensitive authentication data) is not retained after authorization",
     "Sensitive authentication data is not retained after authorization, even if encrypted."),
    ("3.4.1", "Req 3 — Protect Stored Account Data",
     "PAN is masked when displayed",
     "PAN is masked when displayed (the BIN and last four digits are the maximum number of digits to be displayed), such that only personnel with a legitimate business need can see more than the BIN/last four digits of the PAN."),
    ("3.5.1", "Req 3 — Protect Stored Account Data",
     "PAN is secured with strong cryptography",
     "PAN is secured with strong cryptography wherever it is stored."),
    ("3.6.1", "Req 3 — Protect Stored Account Data",
     "Cryptographic key management procedures and processes are defined and implemented",
     "Procedures and processes for protecting cryptographic keys used to protect stored account data against disclosure and misuse are defined and implemented."),
    ("3.7.1", "Req 3 — Protect Stored Account Data",
     "Key management policies and procedures include key generation",
     "Key management policies and procedures specify the generation of strong cryptographic keys."),
]

PCI_REQ_4: list[tuple[str, str, str, str]] = [
    ("4.1.1", "Req 4 — Data Transmission Security",
     "Processes and mechanisms for transmission security are defined and understood",
     "All security policies and operational procedures for Requirement 4 are documented, kept up to date, in use, and known to all affected parties."),
    ("4.2.1", "Req 4 — Data Transmission Security",
     "Strong cryptography is used to safeguard PAN during transmission",
     "Strong cryptography is used to safeguard PAN during transmission over open, public networks."),
    ("4.2.2", "Req 4 — Data Transmission Security",
     "PAN is secured with strong cryptography when sent via end-user messaging",
     "PAN is secured with strong cryptography whenever it is sent via end-user messaging technologies."),
    ("4.2.1.1", "Req 4 — Data Transmission Security",
     "An inventory of trusted keys and certificates is maintained",
     "An inventory of the entity's trusted keys and certificates used to protect PAN during transmission is maintained."),
]

PCI_REQ_5: list[tuple[str, str, str, str]] = [
    ("5.1.1", "Req 5 — Malicious Software Protection",
     "Processes and mechanisms for malware protection are defined and understood",
     "All security policies and operational procedures for Requirement 5 are documented, kept up to date, in use, and known to all affected parties."),
    ("5.2.1", "Req 5 — Malicious Software Protection",
     "Anti-malware solution is deployed on all system components",
     "An anti-malware solution is deployed on all system components, except for those system components identified as not at risk."),
    ("5.2.2", "Req 5 — Malicious Software Protection",
     "Anti-malware solution detects, removes, and protects against all types of malware",
     "The deployed anti-malware solution detects all known types of malware and protects against all known types of malware."),
    ("5.3.1", "Req 5 — Malicious Software Protection",
     "Anti-malware solution is kept current via automatic updates",
     "The anti-malware solution is kept current via automatic updates."),
    ("5.4.1", "Req 5 — Malicious Software Protection",
     "Processes and automated mechanisms are in place to detect and protect against phishing attacks",
     "Processes and automated mechanisms are in place to detect and protect personnel against phishing attacks."),
]

PCI_REQ_6: list[tuple[str, str, str, str]] = [
    ("6.1.1", "Req 6 — Secure Systems and Software",
     "Processes and mechanisms for developing and maintaining secure systems are defined and understood",
     "All security policies and operational procedures for Requirement 6 are documented, kept up to date, in use, and known to all affected parties."),
    ("6.2.1", "Req 6 — Secure Systems and Software",
     "Bespoke and custom software is developed securely",
     "Bespoke and custom software is developed securely, as follows: based on industry standards and best practices, in-scope systems protected from known vulnerabilities."),
    ("6.2.4", "Req 6 — Secure Systems and Software",
     "Software engineering techniques prevent or mitigate common software attacks",
     "Software engineering techniques or other methods are defined and in use to prevent or mitigate common software attacks and related vulnerabilities."),
    ("6.3.1", "Req 6 — Secure Systems and Software",
     "Security vulnerabilities are identified and managed",
     "Security vulnerabilities are identified and managed using a defined ranking system that rates vulnerabilities according to risk."),
    ("6.3.3", "Req 6 — Secure Systems and Software",
     "All system components are protected from known vulnerabilities by patching",
     "All system components are protected from known vulnerabilities by installing applicable security patches/updates. Critical patches are installed within one month of release."),
    ("6.4.1", "Req 6 — Secure Systems and Software",
     "Public-facing web applications are protected against attacks",
     "For public-facing web applications, new threats and vulnerabilities are addressed on an ongoing basis, and these applications are protected against known attacks."),
    ("6.5.1", "Req 6 — Secure Systems and Software",
     "Changes to bespoke software are managed securely",
     "Changes to all system components are managed via a change management process."),
]

PCI_REQ_7: list[tuple[str, str, str, str]] = [
    ("7.1.1", "Req 7 — Restrict Access",
     "Processes and mechanisms for restricting access are defined and understood",
     "All security policies and operational procedures for Requirement 7 are documented, kept up to date, in use, and known to all affected parties."),
    ("7.2.1", "Req 7 — Restrict Access",
     "An access control model is defined and includes granting access based on need to know",
     "An access control model is defined and includes granting of access as follows: appropriate access based on business and access needs; access to system components and data resources that is based on users' job classification and functions."),
    ("7.2.2", "Req 7 — Restrict Access",
     "Access is assigned to users, including privileged users, based on job classification and function",
     "Access is assigned to users, including privileged users, based on job classification and function."),
    ("7.2.5", "Req 7 — Restrict Access",
     "All application and system accounts are managed as follows",
     "All application and system accounts are assigned and managed per an inventory, use the principle of least privilege, and are reviewed periodically."),
    ("7.3.1", "Req 7 — Restrict Access",
     "All user access to query repositories of cardholder data is restricted",
     "Access to cardholder data is restricted by application of access control and authentication."),
]

PCI_REQ_8: list[tuple[str, str, str, str]] = [
    ("8.1.1", "Req 8 — Identify Users and Authenticate Access",
     "Processes and mechanisms for user authentication are defined and understood",
     "All security policies and operational procedures for Requirement 8 are documented, kept up to date, in use, and known to all affected parties."),
    ("8.2.1", "Req 8 — Identify Users and Authenticate Access",
     "All users are assigned a unique ID before allowing access",
     "All users are assigned a unique ID before allowing them to access system components or cardholder data."),
    ("8.3.1", "Req 8 — Identify Users and Authenticate Access",
     "All user IDs and authentication factors are managed throughout their lifecycle",
     "All user IDs and associated authentication factors are managed with appropriate controls for lifecycle events including addition, modification, suspension, and deletion."),
    ("8.3.6", "Req 8 — Identify Users and Authenticate Access",
     "Passwords/passphrases meet complexity requirements",
     "If passwords/passphrases are used as authentication factors, they meet minimum length and complexity requirements."),
    ("8.4.1", "Req 8 — Identify Users and Authenticate Access",
     "MFA is implemented for all non-consumer users into the CDE",
     "Multi-factor authentication is implemented for all non-consumer users accessing the CDE."),
    ("8.6.1", "Req 8 — Identify Users and Authenticate Access",
     "System/application accounts and related authentication factors are managed",
     "System and application accounts and related authentication factors are managed in accordance with policy."),
]

PCI_REQ_9: list[tuple[str, str, str, str]] = [
    ("9.1.1", "Req 9 — Physical Access",
     "Processes and mechanisms for restricting physical access are defined and understood",
     "All security policies and operational procedures for Requirement 9 are documented, kept up to date, in use, and known to all affected parties."),
    ("9.2.1", "Req 9 — Physical Access",
     "Appropriate physical access controls are in place for facilities",
     "Appropriate physical security controls are in place to restrict and monitor entry into the CDE facilities."),
    ("9.3.1", "Req 9 — Physical Access",
     "Physical access for personnel is authorized and managed",
     "Physical access for personnel to the CDE is authorized and managed."),
    ("9.4.1", "Req 9 — Physical Access",
     "Physical access to sensitive areas within the CDE for visitors is authorized and managed",
     "Physical access for visitors to the CDE is authorized and managed with a badge or token."),
    ("9.5.1", "Req 9 — Physical Access",
     "Point-of-interaction devices are protected from tampering and substitution",
     "POI devices that capture payment card data via direct physical interaction with the payment card form factor are protected from tampering and unauthorized substitution."),
]

PCI_REQ_10: list[tuple[str, str, str, str]] = [
    ("10.1.1", "Req 10 — Log and Monitor",
     "Processes and mechanisms for audit logging are defined and documented",
     "All security policies and operational procedures for Requirement 10 are documented, kept up to date, in use, and known to all affected parties."),
    ("10.2.1", "Req 10 — Log and Monitor",
     "Audit logs are enabled and active for all system components",
     "Audit logs are enabled and active for all system components and cardholder data."),
    ("10.3.1", "Req 10 — Log and Monitor",
     "Read access to audit logs is limited to those with job-related needs",
     "Read access to audit logs is limited to those with a job-related need."),
    ("10.4.1", "Req 10 — Log and Monitor",
     "Log reviews are conducted for all system components",
     "The following audit logs are reviewed at least once daily: all security events, logs of all system components in the CDE, logs of all critical system components, logs of all servers and system components that perform security functions."),
    ("10.6.1", "Req 10 — Log and Monitor",
     "System clocks and time are synchronized using time-synchronization technology",
     "System clocks and time are synchronized using time synchronization technology (NTP or similar) to ensure consistent time across systems."),
    ("10.7.1", "Req 10 — Log and Monitor",
     "Failures of critical security controls are detected, reported, and responded to",
     "Failures of critical security controls are detected, alerted, and addressed promptly."),
]

PCI_REQ_11: list[tuple[str, str, str, str]] = [
    ("11.1.1", "Req 11 — Regular Security Testing",
     "Processes and mechanisms for security testing are defined and documented",
     "All security policies and operational procedures for Requirement 11 are documented, kept up to date, in use, and known to all affected parties."),
    ("11.2.1", "Req 11 — Regular Security Testing",
     "Authorized and unauthorized wireless access points are managed",
     "Authorized and unauthorized wireless access points are managed using a process that includes testing for the presence of wireless access points."),
    ("11.3.1", "Req 11 — Regular Security Testing",
     "Internal vulnerability scans are performed at least once every three months",
     "Internal vulnerability scans are performed via authenticated scanning at least once every three months on all system components."),
    ("11.3.2", "Req 11 — Regular Security Testing",
     "External vulnerability scans are performed by a PCI SSC Approved Scanning Vendor (ASV)",
     "External vulnerability scans are performed by an ASV at least once every three months."),
    ("11.4.1", "Req 11 — Regular Security Testing",
     "A penetration testing methodology is defined, documented, and implemented",
     "A penetration testing methodology is defined, documented, and implemented by the entity."),
    ("11.5.1", "Req 11 — Regular Security Testing",
     "Intrusion-detection and/or intrusion-prevention techniques detect and prevent intrusions",
     "Intrusion-detection and/or intrusion-prevention techniques are used to detect and/or prevent intrusions into the network."),
]

PCI_REQ_12: list[tuple[str, str, str, str]] = [
    ("12.1.1", "Req 12 — Organizational Security Policies",
     "An overall information security policy is established, published, maintained, and disseminated",
     "An overall information security policy is established, published, maintained, and disseminated to all relevant personnel."),
    ("12.2.1", "Req 12 — Organizational Security Policies",
     "Acceptable use policies for end-user technologies are defined and implemented",
     "Acceptable use policies for end-user technologies are defined and implemented."),
    ("12.3.1", "Req 12 — Organizational Security Policies",
     "Each PCI DSS requirement that provides flexibility for how frequently it is performed is completed per a targeted risk analysis",
     "Each PCI DSS requirement that provides flexibility for how frequently it is performed is completed per a documented, targeted risk analysis."),
    ("12.4.1", "Req 12 — Organizational Security Policies",
     "Responsibility for PCI DSS compliance is defined and managed",
     "Executive management has established responsibility for the protection of cardholder data and a PCI DSS compliance program."),
    ("12.5.1", "Req 12 — Organizational Security Policies",
     "An inventory of system components in scope for PCI DSS is maintained",
     "An inventory of system components that are in scope for PCI DSS, including a description of function/use, is maintained and kept current."),
    ("12.6.1", "Req 12 — Organizational Security Policies",
     "A formal security awareness program is implemented",
     "A formal security awareness program is implemented to make all personnel aware of the entity's information security policy and procedures, and their role in protecting the cardholder data."),
    ("12.8.1", "Req 12 — Organizational Security Policies",
     "A list of all third-party service providers (TPSPs) with which account data is shared is maintained",
     "A list of all third-party service providers with which account data is shared or that could affect the security of account data is maintained."),
    ("12.10.1", "Req 12 — Organizational Security Policies",
     "An incident response plan exists and is ready to be activated in the event of a suspected or confirmed security incident",
     "An incident response plan that is to be activated in the event of a confirmed or suspected security incident is documented."),
]


ALL_PCI_CONTROLS = (
    PCI_REQ_1
    + PCI_REQ_2
    + PCI_REQ_3
    + PCI_REQ_4
    + PCI_REQ_5
    + PCI_REQ_6
    + PCI_REQ_7
    + PCI_REQ_8
    + PCI_REQ_9
    + PCI_REQ_10
    + PCI_REQ_11
    + PCI_REQ_12
)


async def seed_pci_dss(session: AsyncSession) -> None:
    """
    Idempotent PCI DSS v4.0 framework seeder.

    Creates:
      - Framework: PCI DSS v4.0
      - FrameworkVersion: v4.0 (is_current=True)
      - Controls: 72 covering all 12 main requirements

    Skips silently if PCIDSS framework already exists.
    """
    result = await session.execute(
        select(Framework).where(Framework.short_code == "PCIDSS")
    )
    existing = result.scalars().first()
    if existing:
        return

    framework = Framework(
        id=str(uuid.uuid4()),
        name="PCI DSS v4.0",
        short_code="PCIDSS",
        category="sectoral",
        description=(
            "Payment Card Industry Data Security Standard v4.0 (March 2022). "
            "Developed by the PCI Security Standards Council to encourage and enhance payment "
            "card account data security. Covers 12 principal requirements for protecting "
            "cardholder data (CHD) and sensitive authentication data (SAD)."
        ),
    )
    session.add(framework)
    await session.flush()

    version = FrameworkVersion(
        id=str(uuid.uuid4()),
        framework_id=framework.id,
        version="v4.0",
        effective_date=date(2022, 3, 31),
        is_current=True,
    )
    session.add(version)
    await session.flush()

    for control_code, category, title, description in ALL_PCI_CONTROLS:
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
