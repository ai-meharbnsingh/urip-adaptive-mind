"""
CIS Controls v8 (formerly Critical Security Controls) seeder.

CIS Controls v8 organises 153 Safeguards across 18 Control families, mapped to
3 Implementation Groups (IG1, IG2, IG3) by maturity:
  - IG1 — basic cyber hygiene (56 Safeguards)
  - IG2 — adds 74 Safeguards (cumulative IG1 + IG2 = 130)
  - IG3 — adds 23 Safeguards (cumulative all 153)

This seeder covers IG1 + IG2 — the 130 Safeguards every regulated /
mid-sized organisation should aim for. Each Safeguard is loaded as a control
with its CIS code (e.g., "1.1", "1.2", … "18.5").

Sources (verified, public):
  - CIS Controls v8 official site:
      https://www.cisecurity.org/controls/v8
  - CIS Controls v8.1 release notes (Aug 2024 minor update):
      https://www.cisecurity.org/insights/blog/cis-controls-v8-1-released
  - Free PDF download (registration): https://www.cisecurity.org/controls/cis-controls-list
  - CIS-CSAT mappings (NIST CSF, ISO 27001, etc.)

Idempotent: skip if framework already exists.
"""
import uuid
from datetime import date
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from compliance_backend.models.framework import Framework, FrameworkVersion, Control


FRAMEWORK_SHORT_CODE = "CISV8"
FRAMEWORK_NAME = "CIS Controls v8"
FRAMEWORK_VERSION = "8"
REFERENCE_URL = "https://www.cisecurity.org/controls/v8"


# ---------------------------------------------------------------------------
# Format: (control_code, category, title, description)
# IG1 + IG2 Safeguards across all 18 Controls. ~130 entries.
# ---------------------------------------------------------------------------

CIS_CONTROLS: list[tuple[str, str, str, str]] = [
    # Control 1 — Inventory and Control of Enterprise Assets
    ("1.1", "C1: Inventory & Control of Enterprise Assets",
     "Establish and maintain detailed enterprise asset inventory",
     "Establish and maintain an accurate, detailed and up-to-date inventory of all enterprise assets with the potential to store or process data, including end-user devices, network devices, IoT devices, and servers. (IG1)"),
    ("1.2", "C1: Inventory & Control of Enterprise Assets",
     "Address unauthorized assets",
     "Ensure that a process exists to address unauthorized assets on a weekly basis. (IG1)"),
    ("1.3", "C1: Inventory & Control of Enterprise Assets",
     "Utilize an active discovery tool",
     "Utilize an active discovery tool to identify assets connected to the enterprise's network. Configure the tool to execute daily, or more frequently. (IG2)"),
    ("1.4", "C1: Inventory & Control of Enterprise Assets",
     "Use DHCP logging to update enterprise asset inventory",
     "Use DHCP logging on all DHCP servers or IP-address-management tools to update the enterprise's asset inventory. Review and use logs to update the asset inventory weekly, or more frequently. (IG2)"),
    ("1.5", "C1: Inventory & Control of Enterprise Assets",
     "Use a passive asset discovery tool",
     "Use a passive discovery tool to identify assets connected to the enterprise's network. Review and use scans to update the enterprise asset inventory at least weekly. (IG2)"),

    # Control 2 — Inventory and Control of Software Assets
    ("2.1", "C2: Inventory & Control of Software Assets",
     "Establish and maintain a software inventory",
     "Establish and maintain a detailed inventory of all licensed software installed on enterprise assets. The inventory must document the title, publisher, initial install/use date, and business purpose. (IG1)"),
    ("2.2", "C2: Inventory & Control of Software Assets",
     "Ensure authorized software is currently supported",
     "Ensure that only currently supported software is designated as authorized in the software inventory. (IG1)"),
    ("2.3", "C2: Inventory & Control of Software Assets",
     "Address unauthorized software",
     "Ensure that unauthorized software is either removed from use on enterprise assets or receives a documented exception. Review monthly. (IG1)"),
    ("2.4", "C2: Inventory & Control of Software Assets",
     "Utilize automated software inventory tools",
     "Utilize software inventory tools, when possible, throughout the enterprise to automate the discovery and documentation of installed software. (IG2)"),
    ("2.5", "C2: Inventory & Control of Software Assets",
     "Allowlist authorized software",
     "Use technical controls, such as application allowlisting, to ensure that only authorized software can execute or be accessed. (IG2)"),
    ("2.6", "C2: Inventory & Control of Software Assets",
     "Allowlist authorized libraries",
     "Use technical controls to ensure that only authorized software libraries are allowed to load into a system process. (IG2)"),

    # Control 3 — Data Protection
    ("3.1", "C3: Data Protection",
     "Establish and maintain a data management process",
     "Establish and maintain a data management process. Address data sensitivity, owner, handling, retention limits and disposal requirements. (IG1)"),
    ("3.2", "C3: Data Protection",
     "Establish and maintain a data inventory",
     "Establish and maintain a data inventory of sensitive data, at minimum. Review and update at least annually. (IG1)"),
    ("3.3", "C3: Data Protection",
     "Configure data access control lists",
     "Configure data access control lists based on a user's need to know. (IG1)"),
    ("3.4", "C3: Data Protection",
     "Enforce data retention",
     "Retain data according to the enterprise's data management process. Data retention must include both minimum and maximum timelines. (IG1)"),
    ("3.5", "C3: Data Protection",
     "Securely dispose of data",
     "Securely dispose of data as outlined in the enterprise's data management process. (IG1)"),
    ("3.6", "C3: Data Protection",
     "Encrypt data on end-user devices",
     "Encrypt data on end-user devices containing sensitive data. (IG1)"),
    ("3.7", "C3: Data Protection",
     "Establish and maintain a data classification scheme",
     "Establish and maintain an overall data-classification scheme. Review and update annually, or when significant enterprise changes occur. (IG2)"),
    ("3.8", "C3: Data Protection",
     "Document data flows",
     "Document data flows. Reviews shall include service provider data flows. (IG2)"),
    ("3.9", "C3: Data Protection",
     "Encrypt data on removable media",
     "Encrypt data on removable media. (IG2)"),
    ("3.10", "C3: Data Protection",
     "Encrypt sensitive data in transit",
     "Encrypt sensitive data in transit. Example implementations include TLS 1.2+, IPSec, OpenSSH. (IG2)"),
    ("3.11", "C3: Data Protection",
     "Encrypt sensitive data at rest",
     "Encrypt sensitive data at rest on servers, applications and databases. (IG2)"),
    ("3.12", "C3: Data Protection",
     "Segment data processing and storage based on sensitivity",
     "Segment data processing and storage based on the sensitivity of the data. (IG2)"),

    # Control 4 — Secure Configuration of Enterprise Assets and Software
    ("4.1", "C4: Secure Configuration",
     "Establish and maintain a secure configuration process",
     "Establish and maintain a secure configuration process for enterprise assets (end-user devices, including portable and mobile, non-computing/IoT devices, and servers) and software (operating systems and applications). (IG1)"),
    ("4.2", "C4: Secure Configuration",
     "Establish and maintain a secure configuration process for network infrastructure",
     "Establish and maintain a secure configuration process for network devices. (IG1)"),
    ("4.3", "C4: Secure Configuration",
     "Configure automatic session locking",
     "Configure automatic session locking on enterprise assets after a defined period of inactivity. (IG1)"),
    ("4.4", "C4: Secure Configuration",
     "Implement and manage a firewall on servers",
     "Implement and manage a firewall on servers, where supported. Example implementations include a virtual firewall, OS firewall, or third-party firewall agent. (IG1)"),
    ("4.5", "C4: Secure Configuration",
     "Implement and manage a firewall on end-user devices",
     "Implement and manage a host-based firewall or port-filtering tool on end-user devices, with a default deny rule. (IG1)"),
    ("4.6", "C4: Secure Configuration",
     "Securely manage enterprise assets and software",
     "Securely manage enterprise assets and software. Example implementations include managing configuration through version-controlled-infrastructure-as-code, accessing administrative interfaces over secure network protocols. (IG1)"),
    ("4.7", "C4: Secure Configuration",
     "Manage default accounts on enterprise assets and software",
     "Manage default accounts on enterprise assets and software, such as root, administrator, and other pre-configured vendor accounts. (IG1)"),
    ("4.8", "C4: Secure Configuration",
     "Uninstall or disable unnecessary services",
     "Uninstall or disable unnecessary services on enterprise assets and software, such as an unused file-sharing service, web app module, or service function. (IG2)"),
    ("4.9", "C4: Secure Configuration",
     "Configure trusted DNS servers on enterprise assets",
     "Configure trusted DNS servers on enterprise assets. (IG2)"),
    ("4.10", "C4: Secure Configuration",
     "Enforce automatic device lockout on portable end-user devices",
     "Enforce automatic device lockout following a predetermined threshold of local failed authentication attempts on portable end-user devices, where supported. (IG2)"),
    ("4.11", "C4: Secure Configuration",
     "Enforce remote-wipe capability on portable end-user devices",
     "Remotely wipe enterprise data from enterprise-owned portable end-user devices when deemed appropriate, such as lost or stolen devices, or when an individual no longer supports the enterprise. (IG2)"),
    ("4.12", "C4: Secure Configuration",
     "Separate enterprise workspaces on mobile end-user devices",
     "Ensure separate enterprise workspaces are used on mobile end-user devices, where supported. (IG2)"),

    # Control 5 — Account Management
    ("5.1", "C5: Account Management",
     "Establish and maintain an inventory of accounts",
     "Establish and maintain an inventory of all accounts managed in the enterprise. Inventory must include user, administrator, and service accounts. Review and update at least quarterly. (IG1)"),
    ("5.2", "C5: Account Management",
     "Use unique passwords",
     "Use unique passwords for all enterprise assets. Best practice: minimum 8-character password for accounts using MFA, and minimum 14-character password for accounts not using MFA. (IG1)"),
    ("5.3", "C5: Account Management",
     "Disable dormant accounts",
     "Delete or disable any dormant accounts after a period of 45 days of inactivity, where supported. (IG1)"),
    ("5.4", "C5: Account Management",
     "Restrict administrator privileges to dedicated administrator accounts",
     "Restrict administrator privileges to dedicated administrator accounts on enterprise assets. (IG1)"),
    ("5.5", "C5: Account Management",
     "Establish and maintain an inventory of service accounts",
     "Establish and maintain an inventory of service accounts. Review and update quarterly. (IG2)"),
    ("5.6", "C5: Account Management",
     "Centralize account management",
     "Centralize account management through a directory or identity service. (IG2)"),

    # Control 6 — Access Control Management
    ("6.1", "C6: Access Control Management",
     "Establish an access granting process",
     "Establish and follow a process, preferably automated, for granting access to enterprise assets upon new hire, rights grant, or role change of a user. (IG1)"),
    ("6.2", "C6: Access Control Management",
     "Establish an access revoking process",
     "Establish and follow a process, preferably automated, for revoking access upon termination, rights revocation, or role change of a user. (IG1)"),
    ("6.3", "C6: Access Control Management",
     "Require MFA for externally-exposed applications",
     "Require all externally-exposed enterprise or third-party applications to enforce MFA. (IG1)"),
    ("6.4", "C6: Access Control Management",
     "Require MFA for remote network access",
     "Require MFA for remote network access. (IG1)"),
    ("6.5", "C6: Access Control Management",
     "Require MFA for administrative access",
     "Require MFA for all administrative access accounts, where supported, on all enterprise assets, whether managed on-site or through a third-party provider. (IG1)"),
    ("6.6", "C6: Access Control Management",
     "Establish and maintain an inventory of authentication and authorization systems",
     "Establish and maintain an inventory of the enterprise's authentication and authorization systems. Review and update annually. (IG2)"),
    ("6.7", "C6: Access Control Management",
     "Centralize access control",
     "Centralize access control for all enterprise assets through a directory service or SSO provider, where supported. (IG2)"),
    ("6.8", "C6: Access Control Management",
     "Define and maintain role-based access control",
     "Define and maintain role-based access control. Review access annually. (IG2)"),

    # Control 7 — Continuous Vulnerability Management
    ("7.1", "C7: Continuous Vulnerability Management",
     "Establish and maintain a vulnerability management process",
     "Establish and maintain a documented vulnerability-management process for enterprise assets. Review and update annually, or when significant enterprise changes occur. (IG1)"),
    ("7.2", "C7: Continuous Vulnerability Management",
     "Establish and maintain a remediation process",
     "Establish and maintain a risk-based remediation strategy documented in a remediation process, with monthly, or more frequent, reviews. (IG1)"),
    ("7.3", "C7: Continuous Vulnerability Management",
     "Perform automated operating-system patch management",
     "Perform operating-system updates on enterprise assets through automated patch management on a monthly, or more frequent, basis. (IG1)"),
    ("7.4", "C7: Continuous Vulnerability Management",
     "Perform automated application patch management",
     "Perform application updates on enterprise assets through automated patch management on a monthly, or more frequent, basis. (IG1)"),
    ("7.5", "C7: Continuous Vulnerability Management",
     "Perform automated vulnerability scans of internal enterprise assets",
     "Perform automated vulnerability scans of internal enterprise assets on a quarterly, or more frequent, basis. Conduct both authenticated and unauthenticated scans, using a SCAP-compliant vulnerability scanning tool. (IG2)"),
    ("7.6", "C7: Continuous Vulnerability Management",
     "Perform automated vulnerability scans of externally-exposed enterprise assets",
     "Perform automated vulnerability scans of externally-exposed enterprise assets using a SCAP-compliant vulnerability-scanning tool. Perform scans on a monthly, or more frequent, basis. (IG2)"),
    ("7.7", "C7: Continuous Vulnerability Management",
     "Remediate detected vulnerabilities",
     "Remediate detected vulnerabilities in software through processes and tooling on a monthly, or more frequent, basis, based on the remediation process. (IG2)"),

    # Control 8 — Audit Log Management
    ("8.1", "C8: Audit Log Management",
     "Establish and maintain an audit log management process",
     "Establish and maintain an audit-log management process that defines the enterprise's logging requirements. (IG1)"),
    ("8.2", "C8: Audit Log Management",
     "Collect audit logs",
     "Collect audit logs. Ensure that logging, per the enterprise's audit-log management process, has been enabled across enterprise assets. (IG1)"),
    ("8.3", "C8: Audit Log Management",
     "Ensure adequate audit log storage",
     "Ensure that logging destinations maintain adequate storage to comply with the enterprise's audit-log management process. (IG1)"),
    ("8.4", "C8: Audit Log Management",
     "Standardize time synchronization",
     "Standardize time synchronization. Configure at least two synchronized time sources across enterprise assets, where supported. (IG2)"),
    ("8.5", "C8: Audit Log Management",
     "Collect detailed audit logs",
     "Configure detailed audit logging for enterprise assets containing sensitive data. (IG2)"),
    ("8.6", "C8: Audit Log Management",
     "Collect DNS query audit logs",
     "Collect DNS query audit logs on enterprise assets, where appropriate and supported. (IG2)"),
    ("8.7", "C8: Audit Log Management",
     "Collect URL request audit logs",
     "Collect URL request audit logs on enterprise assets, where appropriate and supported. (IG2)"),
    ("8.8", "C8: Audit Log Management",
     "Collect command-line audit logs",
     "Collect command-line audit logs. Example implementations include collecting audit logs from PowerShell, BASH, and remote administrative terminals. (IG2)"),
    ("8.9", "C8: Audit Log Management",
     "Centralize audit logs",
     "Centralize, to the extent possible, audit log collection and retention across enterprise assets. (IG2)"),
    ("8.10", "C8: Audit Log Management",
     "Retain audit logs",
     "Retain audit logs across enterprise assets for a minimum of 90 days. (IG2)"),
    ("8.11", "C8: Audit Log Management",
     "Conduct audit log reviews",
     "Conduct reviews of audit logs to detect anomalies or abnormal events that could indicate a potential threat. Conduct reviews on a weekly, or more frequent, basis. (IG2)"),

    # Control 9 — Email and Web Browser Protections
    ("9.1", "C9: Email & Web Browser Protections",
     "Ensure use of only fully supported browsers and email clients",
     "Ensure only fully supported browsers and email clients are allowed to execute in the enterprise, only using the latest version. (IG1)"),
    ("9.2", "C9: Email & Web Browser Protections",
     "Use DNS filtering services",
     "Use DNS filtering services on all enterprise assets to block access to known malicious domains. (IG1)"),
    ("9.3", "C9: Email & Web Browser Protections",
     "Maintain and enforce network-based URL filters",
     "Enforce and update network-based URL filters to limit an enterprise asset from connecting to potentially malicious or unapproved websites. (IG2)"),
    ("9.4", "C9: Email & Web Browser Protections",
     "Restrict unnecessary or unauthorized browser and email-client extensions",
     "Restrict, either through uninstalling or disabling, any unauthorized or unnecessary browser or email client plugins, extensions, and add-on applications. (IG2)"),
    ("9.5", "C9: Email & Web Browser Protections",
     "Implement DMARC",
     "To lower the chance of spoofed or modified emails from valid domains, implement DMARC policy and verification, starting with implementing the SPF and DKIM standards. (IG2)"),
    ("9.6", "C9: Email & Web Browser Protections",
     "Block unnecessary file types",
     "Block unnecessary file types attempting to enter the enterprise's email gateway. (IG2)"),

    # Control 10 — Malware Defenses
    ("10.1", "C10: Malware Defenses",
     "Deploy and maintain anti-malware software",
     "Deploy and maintain anti-malware software on all enterprise assets. (IG1)"),
    ("10.2", "C10: Malware Defenses",
     "Configure automatic anti-malware signature updates",
     "Configure automatic updates for anti-malware signature files on all enterprise assets. (IG1)"),
    ("10.3", "C10: Malware Defenses",
     "Disable autorun and autoplay for removable media",
     "Disable autorun and autoplay auto-execute functionality for removable media. (IG1)"),
    ("10.4", "C10: Malware Defenses",
     "Configure automatic anti-malware scanning of removable media",
     "Configure anti-malware software to automatically scan removable media. (IG2)"),
    ("10.5", "C10: Malware Defenses",
     "Enable anti-exploitation features",
     "Enable anti-exploitation features on enterprise assets and software, where possible (e.g., Microsoft Data Execution Prevention (DEP), Windows Defender Exploit Guard, Apple System Integrity Protection (SIP), gatekeeper). (IG2)"),
    ("10.6", "C10: Malware Defenses",
     "Centrally manage anti-malware software",
     "Centrally manage anti-malware software. (IG2)"),
    ("10.7", "C10: Malware Defenses",
     "Use behavior-based anti-malware software",
     "Use behavior-based anti-malware software. (IG2)"),

    # Control 11 — Data Recovery
    ("11.1", "C11: Data Recovery",
     "Establish and maintain a data recovery process",
     "Establish and maintain a documented data recovery process. Review and update annually, or when significant enterprise changes occur. (IG1)"),
    ("11.2", "C11: Data Recovery",
     "Perform automated backups",
     "Perform automated backups of in-scope enterprise assets. Run backups on a weekly, or more frequent, basis. (IG1)"),
    ("11.3", "C11: Data Recovery",
     "Protect recovery data",
     "Protect recovery data with equivalent controls to the original data. Reference encryption or data separation, based on requirements. (IG1)"),
    ("11.4", "C11: Data Recovery",
     "Establish and maintain an isolated instance of recovery data",
     "Establish and maintain an isolated instance of recovery data. Example implementations include version controlled offsite backups or cloud backups. (IG1)"),
    ("11.5", "C11: Data Recovery",
     "Test data recovery",
     "Test backup recovery quarterly, or more frequently, for a sampling of in-scope enterprise assets. (IG2)"),

    # Control 12 — Network Infrastructure Management
    ("12.1", "C12: Network Infrastructure Management",
     "Ensure network infrastructure is up-to-date",
     "Ensure network infrastructure is kept up-to-date. (IG1)"),
    ("12.2", "C12: Network Infrastructure Management",
     "Establish and maintain a secure network architecture",
     "Establish and maintain a secure network architecture. A secure network architecture must address segmentation, least privilege, and availability, at a minimum. (IG2)"),
    ("12.3", "C12: Network Infrastructure Management",
     "Securely manage network infrastructure",
     "Securely manage network infrastructure. Example implementations include version-controlled infrastructure-as-code, and the use of secure network protocols, such as SSH and HTTPS. (IG2)"),
    ("12.4", "C12: Network Infrastructure Management",
     "Establish and maintain architecture diagrams",
     "Establish and maintain architecture diagram(s) and/or other network system documentation. Review and update documentation annually. (IG2)"),
    ("12.5", "C12: Network Infrastructure Management",
     "Centralize network authentication, authorization, and auditing",
     "Centralize network AAA. (IG2)"),
    ("12.6", "C12: Network Infrastructure Management",
     "Use of secure network management and communication protocols",
     "Use secure network management and communication protocols (e.g., 802.1X, Wi-Fi Protected Access 2 (WPA2) Enterprise or greater). (IG2)"),
    ("12.7", "C12: Network Infrastructure Management",
     "Ensure remote devices utilize a VPN and connect to enterprise AAA infrastructure",
     "Require users to authenticate to enterprise-managed VPN and authentication services prior to accessing enterprise resources on end-user devices. (IG2)"),

    # Control 13 — Network Monitoring and Defense
    ("13.1", "C13: Network Monitoring & Defense",
     "Centralize security event alerting",
     "Centralize security event alerting across enterprise assets for log correlation and analysis. (IG2)"),
    ("13.2", "C13: Network Monitoring & Defense",
     "Deploy a host-based intrusion detection solution",
     "Deploy a host-based intrusion detection solution on enterprise assets, where appropriate and/or supported. (IG2)"),
    ("13.3", "C13: Network Monitoring & Defense",
     "Deploy a network intrusion detection solution",
     "Deploy a network intrusion detection solution on enterprise assets, where appropriate. (IG2)"),
    ("13.4", "C13: Network Monitoring & Defense",
     "Perform traffic filtering between network segments",
     "Perform traffic filtering between network segments, where appropriate. (IG2)"),
    ("13.5", "C13: Network Monitoring & Defense",
     "Manage access control for remote assets",
     "Manage access control for assets remotely connecting to enterprise resources. Determine amount of access to enterprise resources based on up-to-date anti-malware software, configuration compliance, and operating system. (IG2)"),
    ("13.6", "C13: Network Monitoring & Defense",
     "Collect network traffic flow logs",
     "Collect network traffic flow logs and/or network traffic to review and alert upon from network devices. (IG2)"),

    # Control 14 — Security Awareness and Skills Training
    ("14.1", "C14: Security Awareness & Skills Training",
     "Establish and maintain a security awareness program",
     "Establish and maintain a security awareness program. The purpose of a security awareness program is to educate the enterprise's workforce on how to interact with enterprise assets and data in a secure manner. (IG1)"),
    ("14.2", "C14: Security Awareness & Skills Training",
     "Train workforce members to recognize social engineering attacks",
     "Train workforce members to recognize social engineering attacks. (IG1)"),
    ("14.3", "C14: Security Awareness & Skills Training",
     "Train workforce members on authentication best practices",
     "Train workforce members on authentication best practices. (IG1)"),
    ("14.4", "C14: Security Awareness & Skills Training",
     "Train workforce on data handling best practices",
     "Train workforce members on how to identify and properly store, transfer, archive, and destroy sensitive data. (IG1)"),
    ("14.5", "C14: Security Awareness & Skills Training",
     "Train workforce members on causes of unintentional data exposure",
     "Train workforce members to be aware of causes for unintentional data exposure. (IG1)"),
    ("14.6", "C14: Security Awareness & Skills Training",
     "Train workforce members on recognizing and reporting security incidents",
     "Train workforce members to be able to recognize and report a potential incident. (IG1)"),
    ("14.7", "C14: Security Awareness & Skills Training",
     "Train workforce on how to identify and report missing security updates",
     "Train workforce on how to identify and report if their enterprise assets are missing security updates. (IG1)"),
    ("14.8", "C14: Security Awareness & Skills Training",
     "Train workforce on dangers of connecting to and transmitting data over insecure networks",
     "Train workforce members on the dangers of connecting to, and transmitting enterprise data over, insecure networks. (IG1)"),
    ("14.9", "C14: Security Awareness & Skills Training",
     "Conduct role-specific security awareness and skills training",
     "Conduct role-specific security awareness and skills training. (IG2)"),

    # Control 15 — Service Provider Management
    ("15.1", "C15: Service Provider Management",
     "Establish and maintain an inventory of service providers",
     "Establish and maintain an inventory of service providers. The inventory must list all known service providers, classification(s), and a designated enterprise contact for each. (IG1)"),
    ("15.2", "C15: Service Provider Management",
     "Establish and maintain a service provider management policy",
     "Establish and maintain a service provider management policy. Ensure the policy addresses classification, inventory, assessment, monitoring, and decommissioning. Review and update the policy annually. (IG2)"),
    ("15.3", "C15: Service Provider Management",
     "Classify service providers",
     "Classify service providers based on what kind of data they handle, the data sensitivity, and the volume. Reassess service providers' classifications annually. (IG2)"),
    ("15.4", "C15: Service Provider Management",
     "Ensure service provider contracts include security requirements",
     "Ensure service provider contracts include security requirements. (IG2)"),

    # Control 16 — Application Software Security
    ("16.1", "C16: Application Software Security",
     "Establish and maintain a secure application development process",
     "Establish and maintain a secure application development process. (IG2)"),
    ("16.2", "C16: Application Software Security",
     "Establish and maintain a process to accept and address software vulnerabilities",
     "Establish and maintain a process to accept and address reports of software vulnerabilities, including providing a means for external entities to report. (IG2)"),
    ("16.3", "C16: Application Software Security",
     "Perform root cause analysis on security vulnerabilities",
     "Perform root cause analysis on security vulnerabilities. (IG2)"),
    ("16.4", "C16: Application Software Security",
     "Establish and manage an inventory of third-party software components",
     "Establish and manage an updated inventory of third-party components used in development, often referred to as a 'bill of materials' (SBOM). (IG2)"),
    ("16.5", "C16: Application Software Security",
     "Use up-to-date and trusted third-party software components",
     "Use up-to-date and trusted third-party software components. (IG2)"),
    ("16.6", "C16: Application Software Security",
     "Establish and maintain a severity rating system and process for application vulnerabilities",
     "Establish and maintain a severity rating system and process for application vulnerabilities that facilitates prioritising the order in which discovered vulnerabilities are fixed. (IG2)"),
    ("16.7", "C16: Application Software Security",
     "Use standard hardening configuration templates for application infrastructure",
     "Use standard, industry-recommended hardening configuration templates for application infrastructure components. (IG2)"),
    ("16.8", "C16: Application Software Security",
     "Separate production and non-production systems",
     "Maintain separate environments for production and non-production systems. (IG2)"),
    ("16.9", "C16: Application Software Security",
     "Train developers in application security concepts and secure coding",
     "Ensure that all software development personnel receive training in writing secure code for their specific development environment and responsibilities. (IG2)"),
    ("16.10", "C16: Application Software Security",
     "Apply secure design principles in application architectures",
     "Apply secure design principles in application architectures. Secure design principles include the concept of least privilege and enforcing mediation to validate every operation. (IG2)"),
    ("16.11", "C16: Application Software Security",
     "Leverage vetted modules or services for application security components",
     "Leverage vetted modules or services for application security components, such as identity management, encryption, and auditing and logging. (IG2)"),

    # Control 17 — Incident Response Management
    ("17.1", "C17: Incident Response Management",
     "Designate personnel to manage incident handling",
     "Designate one key person, and at least one backup, who will manage the enterprise's incident handling process. (IG1)"),
    ("17.2", "C17: Incident Response Management",
     "Establish and maintain contact information for reporting security incidents",
     "Establish and maintain contact information for parties that need to be informed of security incidents. (IG1)"),
    ("17.3", "C17: Incident Response Management",
     "Establish and maintain an enterprise process for reporting incidents",
     "Establish and maintain an enterprise process for the workforce to report security incidents. (IG1)"),
    ("17.4", "C17: Incident Response Management",
     "Establish and maintain an incident response process",
     "Establish and maintain an incident response process that addresses roles and responsibilities, compliance requirements, and a communication plan. (IG2)"),
    ("17.5", "C17: Incident Response Management",
     "Assign key roles and responsibilities",
     "Assign key roles and responsibilities for incident response, including staff from legal, IT, information security, facilities, public relations, human resources, incident responders, and analysts. (IG2)"),
    ("17.6", "C17: Incident Response Management",
     "Define mechanisms for communicating during incident response",
     "Determine which primary and secondary mechanisms will be used to communicate and report during a security incident. (IG2)"),
    ("17.7", "C17: Incident Response Management",
     "Conduct routine incident response exercises",
     "Plan and conduct routine incident response exercises and scenarios for key personnel involved in the incident response process. (IG2)"),
    ("17.8", "C17: Incident Response Management",
     "Conduct post-incident reviews",
     "Conduct post-incident reviews. Post-incident reviews help prevent incident recurrence through identifying lessons learned and follow-up action. (IG2)"),
    ("17.9", "C17: Incident Response Management",
     "Establish and maintain security incident thresholds",
     "Establish and maintain security incident thresholds, including, at a minimum, differentiating between an incident and an event. (IG2)"),

    # Control 18 — Penetration Testing
    ("18.1", "C18: Penetration Testing",
     "Establish and maintain a penetration testing program",
     "Establish and maintain a penetration testing program appropriate to the size, complexity, and maturity of the enterprise. (IG2)"),
    ("18.2", "C18: Penetration Testing",
     "Perform periodic external penetration tests",
     "Perform periodic external penetration tests based on program requirements, no less than annually. (IG2)"),
    ("18.3", "C18: Penetration Testing",
     "Remediate penetration test findings",
     "Remediate penetration-test findings based on the enterprise's policy for remediation scope and prioritization. (IG2)"),
    ("18.4", "C18: Penetration Testing",
     "Validate security measures",
     "Validate security measures after each penetration test. (IG2)"),
    ("18.5", "C18: Penetration Testing",
     "Perform periodic internal penetration tests",
     "Perform periodic internal penetration tests based on program requirements, no less than annually. (IG2)"),
]


ALL_CIS_V8_CONTROLS = CIS_CONTROLS


async def seed_cis_v8(session: AsyncSession) -> None:
    """Idempotent CIS Controls v8 seeder."""
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
            "CIS Controls v8 — 153 Safeguards across 18 control families with 3 "
            "Implementation Groups (IG1, IG2, IG3). This seeder loads the IG1 + IG2 "
            "Safeguards (~130) — the practical baseline for regulated and mid-sized "
            "organisations. Maintained by the Center for Internet Security (CIS), "
            "widely mapped against NIST CSF, ISO 27001, PCI DSS and SOC 2."
        ),
    )
    session.add(framework)
    await session.flush()

    version = FrameworkVersion(
        id=str(uuid.uuid4()),
        framework_id=framework.id,
        version=FRAMEWORK_VERSION,
        effective_date=date(2021, 5, 18),
        is_current=True,
    )
    session.add(version)
    await session.flush()

    for control_code, category, title, description in ALL_CIS_V8_CONTROLS:
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
