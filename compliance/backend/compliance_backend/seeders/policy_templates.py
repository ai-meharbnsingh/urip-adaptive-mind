"""
Policy template library — Phase 2B.5

Provides 9 seeded policy templates that tenants can use as starting points
for their compliance documentation.
"""
from typing import List, Dict, Any, Optional


POLICY_TEMPLATES: List[Dict[str, Any]] = [
    {
        "name": "Information Security Policy",
        "content": """# Information Security Policy

## 1. Purpose and Scope
This Information Security Policy establishes the framework for protecting [Organization Name]'s information assets from unauthorized access, disclosure, modification, or destruction. It applies to all employees, contractors, vendors, and third parties who access organizational information systems, networks, or handle confidential data in any form.

## 2. Governance and Accountability
The Chief Information Security Officer (CISO) holds overall accountability for the information security program. The IT Security team is responsible for implementing technical controls, conducting risk assessments, and monitoring compliance. Department heads are responsible for enforcing security practices within their teams. Every individual with access to organizational resources shares responsibility for maintaining security.

## 3. Risk Management
The organization shall conduct annual risk assessments to identify threats, vulnerabilities, and potential impacts to information assets. Risk treatment plans must be documented, assigned owners, and tracked to completion. High-risk findings require executive-level review and sign-off.

## 4. Access Control
Access to information and systems shall be granted based on the principle of least privilege and need-to-know. User authentication requires strong, unique passwords with a minimum length of 12 characters and must be changed every 90 days. Multi-factor authentication (MFA) is mandatory for all remote access, privileged accounts, and systems containing sensitive data. Access rights are reviewed quarterly, and terminated employees' access is revoked within 24 hours.

## 5. Data Protection
Confidential and restricted data must be encrypted at rest using AES-256 and in transit using TLS 1.2 or higher. Removable media containing sensitive information must be encrypted and stored in locked containers. Data retention schedules must be followed, and destruction must render data irrecoverable.

## 6. Acceptable Use
Organization assets shall be used solely for authorized business purposes. Prohibited activities include: installing unauthorized software, bypassing security controls, sharing credentials, using personal email for business data, and engaging in activities that could damage the organization's reputation or expose it to liability.

## 7. Incident Response
All suspected or confirmed security incidents must be reported to the Security Operations Center (SOC) within 24 hours of discovery. The incident response team will classify incidents, contain threats, eradicate root causes, and document lessons learned. Post-incident reviews are mandatory for all significant incidents.

## 8. Training and Awareness
All personnel must complete annual security awareness training covering phishing, social engineering, password hygiene, and data handling. Role-specific training is required for developers, administrators, and personnel handling regulated data. Training completion is tracked, and non-compliance is escalated to management.

## 9. Third-Party Security
Vendors and service providers with access to organizational data must sign confidentiality agreements and undergo security assessments. Third-party access must be monitored, logged, and reviewed annually.

## 10. Policy Enforcement
Violations of this policy may result in disciplinary action, up to and including termination of employment or contractual relationships. Legal action may be pursued in cases involving theft, fraud, or willful negligence.

## 11. Review and Maintenance
This policy shall be reviewed annually or upon significant changes to the threat landscape, business operations, or regulatory requirements. Updates require CISO approval and must be communicated to all affected parties.
""",
    },
    {
        "name": "Acceptable Use Policy",
        "content": """# Acceptable Use Policy

## 1. Purpose
This Acceptable Use Policy (AUP) defines the acceptable and unacceptable use of [Organization Name]'s information technology resources, including computers, networks, internet access, email systems, cloud services, and mobile devices. The purpose is to protect the organization, its employees, and its stakeholders from harm caused by misuse or abuse of these resources.

## 2. Scope
This policy applies to all individuals granted access to organizational IT resources, including full-time and part-time employees, contractors, consultants, temporary staff, interns, and third-party users. It covers use on organizational premises, remote work environments, and personally owned devices accessing organizational data (BYOD).

## 3. Authorized Use
Users may access IT resources for:
- Performing job-related duties and responsibilities
- Professional development and training approved by management
- Limited personal use that does not interfere with work responsibilities, consume significant resources, or violate any other organizational policy

## 4. Prohibited Activities
The following activities are strictly prohibited:
- Accessing, downloading, or distributing illegal, offensive, or sexually explicit material
- Engaging in harassment, discrimination, or threats through any organizational communication channel
- Installing unauthorized software, including pirated applications, games, or peer-to-peer file sharing tools
- Circumventing security controls, firewalls, or network monitoring systems
- Sharing passwords, access tokens, or authentication credentials with any other person
- Using organizational resources for personal financial gain, political campaigning, or unauthorized commercial activities
- Sending unsolicited bulk email (spam) from organizational accounts
- Connecting unauthorized devices to the organizational network without IT approval
- Attempting to access data, systems, or accounts without explicit authorization

## 5. Email and Communication
Email is a business tool. Users must exercise caution when opening attachments or clicking links. Confidential information must not be sent to personal email accounts. All email remains the property of the organization and may be monitored for compliance and security purposes.

## 6. Internet and Social Media
Internet access is provided for business purposes. Users may not use organizational networks to access sites known for malware distribution, illegal content, or activities that could expose the organization to liability. When representing the organization on social media, users must adhere to brand guidelines and confidentiality requirements.

## 7. Software and Licensing
Only software approved by IT and properly licensed may be installed on organizational systems. Users must report suspected license violations immediately.

## 8. Monitoring and Privacy
The organization reserves the right to monitor IT resource usage, including network traffic, email, and file access, to ensure compliance and investigate security incidents. Users should have no expectation of privacy when using organizational resources.

## 9. Violations and Consequences
Violations of this policy may result in suspension of access privileges, disciplinary action up to and including termination, and legal proceedings where applicable.

## 10. Acknowledgment
All users must read, understand, and acknowledge this policy before receiving access to IT resources.
""",
    },
    {
        "name": "Business Continuity and Disaster Recovery Policy",
        "content": """# Business Continuity and Disaster Recovery Policy

## 1. Purpose
This policy establishes the framework for ensuring the continuity of critical business operations and the timely recovery of information systems in the event of a disruptive incident. It defines roles, responsibilities, strategies, and minimum recovery objectives for the organization.

## 2. Scope
This policy applies to all business units, information systems, facilities, and personnel involved in delivering critical services. It covers natural disasters, cyberattacks, equipment failures, supply chain disruptions, pandemics, and any other event that could significantly impact operations.

## 3. Business Impact Analysis (BIA)
The organization shall conduct a BIA at least annually to identify critical business processes, their dependencies, and the maximum tolerable downtime (MTD) for each. Recovery Time Objectives (RTO) and Recovery Point Objectives (RPO) shall be defined and documented for all critical systems.

## 4. Roles and Responsibilities
- **Executive Sponsor**: Provides resources and authority for the business continuity program
- **Business Continuity Manager**: Coordinates planning, testing, and maintenance activities
- **Department Heads**: Identify critical processes within their areas and designate alternate personnel
- **IT Department**: Maintains technical recovery capabilities, backup systems, and failover procedures
- **All Employees**: Understand their roles during an incident and participate in training and exercises

## 5. Continuity Strategies
The organization shall maintain strategies appropriate to the criticality of each business process, including:
- Hot standby systems for mission-critical applications (RTO < 4 hours)
- Warm recovery sites for important systems (RTO < 24 hours)
- Cold recovery capabilities for non-critical functions (RTO < 72 hours)
- Work-from-home arrangements and alternate workplace options
- Cross-training of personnel to ensure coverage during absences

## 6. Backup and Recovery
All critical data shall be backed up according to documented schedules. Backups must be encrypted, tested for integrity, and stored in geographically separated locations. At least one backup copy shall be kept offline (air-gapped) to protect against ransomware.

## 7. Incident Response and Activation
The Business Continuity Plan (BCP) is activated when an incident exceeds the normal operational capacity of a department or threatens the organization's ability to deliver critical services. Activation authority rests with the Executive Sponsor or designated alternate. Communication plans must ensure timely notification of stakeholders, employees, customers, and regulators.

## 8. Testing and Exercises
The BCP and Disaster Recovery Plan (DRP) shall be tested at least annually through tabletop exercises, functional drills, or full-scale simulations. Test results must be documented, gaps identified, and corrective actions tracked to completion.

## 9. Plan Maintenance
Business continuity and disaster recovery plans shall be reviewed and updated annually, or following significant organizational changes, technology updates, or post-incident reviews.

## 10. Training and Awareness
All employees shall receive orientation on business continuity procedures. Personnel with specific roles in the BCP/DRP shall receive specialized training and participate in exercises.
""",
    },
    {
        "name": "Incident Response Policy",
        "content": """# Incident Response Policy

## 1. Purpose
This policy establishes the organizational framework for detecting, reporting, assessing, responding to, and recovering from information security incidents. Its goal is to minimize business impact, preserve evidence, and prevent recurrence.

## 2. Scope
This policy applies to all security incidents affecting organizational information assets, including but not limited to: malware infections, unauthorized access, data breaches, denial-of-service attacks, insider threats, physical security breaches, and loss or theft of devices containing organizational data.

## 3. Incident Classification
Incidents are classified by severity:
- **Critical**: Massive data breach, widespread ransomware, active APT compromise. Response within 1 hour.
- **High**: Targeted attack on critical system, unauthorized access to sensitive data. Response within 4 hours.
- **Medium**: Phishing campaign with limited success, malware on single endpoint. Response within 24 hours.
- **Low**: Spam, port scans, minor policy violations. Response within 72 hours.

## 4. Roles and Responsibilities
- **Incident Response Manager**: Coordinates response activities and external communications
- **Security Analysts**: Perform technical analysis, containment, and eradication
- **IT Operations**: Implement technical changes, restore systems, and maintain availability
- **Legal/Compliance**: Assess regulatory notification obligations and manage legal risk
- **Human Resources**: Involved in incidents involving employees
- **All Employees**: Report suspected incidents immediately and cooperate with investigations

## 5. Response Lifecycle
The organization follows the NIST SP 800-61 incident response lifecycle:

### 5.1 Preparation
Maintain incident response tools, contact lists, playbooks, and trained personnel.

### 5.2 Detection and Analysis
Monitor security events, investigate alerts, and determine scope and impact.

### 5.3 Containment
Isolate affected systems to prevent further damage. Short-term containment is immediate; long-term containment involves applying patches and configuration changes.

### 5.4 Eradication
Remove malware, close vulnerabilities, and eliminate attacker access.

### 5.5 Recovery
Restore systems from clean backups, validate integrity, and return to normal operations under enhanced monitoring.

### 5.6 Post-Incident Activity
Document the incident, conduct a lessons-learned review, and update controls to prevent recurrence.

## 6. Reporting
All suspected incidents must be reported to the Security Operations Center via email, phone, or the incident reporting portal. Reports must include: time of discovery, systems involved, observed symptoms, and actions already taken.

## 7. Evidence Preservation
Evidence related to security incidents must be preserved in a forensically sound manner. Logs, disk images, and memory dumps must be stored securely with chain-of-custody documentation.

## 8. External Communications
Only designated spokespeople may communicate with media, regulators, law enforcement, or affected individuals. All external communications require legal review.

## 9. Review
This policy shall be reviewed annually and after every significant incident.
""",
    },
    {
        "name": "Access Control Policy",
        "content": """# Access Control Policy

## 1. Purpose
This policy defines the principles, requirements, and procedures for managing access to organizational information systems and data. It ensures that access is granted based on business need, properly authorized, regularly reviewed, and promptly revoked when no longer required.

## 2. Scope
This policy applies to all information systems, applications, databases, networks, cloud services, and physical facilities owned or managed by [Organization Name]. It covers all user types: employees, contractors, vendors, partners, and automated service accounts.

## 3. Access Control Principles
- **Least Privilege**: Users receive only the minimum access necessary to perform their job functions
- **Need-to-Know**: Access to sensitive data is restricted to those with a legitimate business requirement
- **Segregation of Duties**: Critical functions are divided among multiple individuals to prevent fraud or error
- **Default Deny**: Access is denied by default unless explicitly authorized

## 4. User Account Management
### 4.1 Provisioning
All access requests must be submitted through the designated access request workflow. Requests require manager approval and, for privileged access, additional approval from the data owner or CISO.

### 4.2 Authentication
Passwords must meet complexity requirements (minimum 12 characters, mixed case, numbers, and symbols). Multi-factor authentication is mandatory for remote access, privileged accounts, and systems containing confidential data. Biometric authentication may be used where technically feasible.

### 4.3 Privileged Access
Privileged accounts (administrators, root, service accounts with elevated rights) require enhanced monitoring, dedicated accounts separate from daily use accounts, and just-in-time access where possible. Privileged access is reviewed monthly.

### 4.4 Review and Recertification
User access rights are reviewed quarterly by managers and data owners. Dormant accounts (no login for 90 days) are suspended. Terminated employee access is revoked within 24 hours of separation.

## 5. Role-Based Access Control (RBAC)
Access rights are grouped into roles corresponding to job functions. Roles are defined by department heads in collaboration with IT and security. New roles or significant modifications require security team review.

## 6. Physical Access
Physical access to data centers, server rooms, and sensitive areas requires badge-based entry with audit logging. Visitors must be escorted at all times. Access badges are deactivated immediately upon termination or transfer.

## 7. Remote Access
Remote access is permitted only through approved VPN or Zero Trust Network Access (ZTNA) solutions. Split tunneling is prohibited. Remote sessions are subject to the same access controls and monitoring as on-premises access.

## 8. Monitoring and Logging
All authentication attempts, privilege escalations, and access to sensitive data are logged. Logs are retained for a minimum of 12 months and protected against tampering. Anomalies are investigated by the security team.

## 9. Exceptions
Exceptions to this policy require documented risk acceptance signed by the CISO or delegate. Exceptions are reviewed annually.

## 10. Review
This policy is reviewed annually and updated to reflect changes in technology, threats, and business requirements.
""",
    },
    {
        "name": "Change Management Policy",
        "content": """# Change Management Policy

## 1. Purpose
This policy establishes a standardized process for managing changes to information systems, infrastructure, applications, and security controls. It aims to minimize disruption, maintain security, and ensure that all changes are properly authorized, tested, and documented.

## 2. Scope
This policy applies to all changes affecting production and pre-production environments, including: software deployments, configuration changes, infrastructure modifications, security control updates, patch installations, and changes to integrations with third-party systems.

## 3. Change Categories
### 3.1 Standard Changes
Low-risk, pre-authorized changes that follow established procedures. Examples: routine patch deployments, adding a user to a standard group. Standard changes require minimal approval.

### 3.2 Normal Changes
Changes that require assessment, scheduling, and approval. Examples: application upgrades, network reconfigurations, firewall rule modifications. Normal changes require a Change Advisory Board (CAB) review.

### 3.3 Emergency Changes
Urgent changes required to restore service or address critical security vulnerabilities. Emergency changes may be implemented immediately with retrospective approval within 48 hours.

## 4. Change Lifecycle
### 4.1 Request
Submit a change request (CR) describing the change, business justification, affected systems, risk assessment, and rollback plan.

### 4.2 Assessment
Technical teams evaluate feasibility, dependencies, security impact, and resource requirements. A risk rating (low, medium, high, critical) is assigned.

### 4.3 Approval
Standard changes are approved by the service owner. Normal changes require CAB approval. Emergency changes require verbal or immediate written approval from the CIO or CISO, followed by retrospective CAB review.

### 4.4 Scheduling
Changes are scheduled during approved maintenance windows. Blackout periods (e.g., month-end close, audit windows) are observed.

### 4.5 Implementation
Changes are implemented according to the plan. Implementation teams must verify that rollback procedures are available and tested.

### 4.6 Verification
Post-implementation reviews confirm that the change achieved its intended outcome without adverse effects. Automated and manual testing are performed as appropriate.

### 4.7 Closure
The CR is closed with documentation of results, lessons learned, and updates to configuration management database (CMDB) entries.

## 5. Roles
- **Change Requester**: Initiates the change request
- **Change Owner**: Accountable for successful implementation
- **Change Advisory Board (CAB)**: Reviews and approves normal and high-risk changes
- **IT Operations**: Implements infrastructure and system changes
- **Security Team**: Reviews changes for security impact

## 6. Security Requirements
All changes must be assessed for security impact. Changes affecting authentication, authorization, encryption, logging, or network boundaries require mandatory security review. Separation of duties must be maintained between those who develop changes and those who approve and deploy them.

## 7. Documentation
All changes must be documented in the change management system, including: request details, approvals, implementation steps, test results, and closure notes.

## 8. Review
This policy is reviewed annually. Metrics such as change success rate, emergency change percentage, and mean time to implement are tracked and reported to leadership.
""",
    },
    {
        "name": "Vendor Management Policy",
        "content": """# Vendor Management Policy

## 1. Purpose
This policy establishes the requirements for selecting, onboarding, monitoring, and offboarding vendors and third-party service providers that access, process, store, or transmit organizational data. Its objective is to ensure that vendor relationships do not introduce unacceptable security, privacy, compliance, or operational risks.

## 2. Scope
This policy applies to all vendors, contractors, cloud service providers, SaaS vendors, outsourced development firms, data processors, and any other third parties with access to organizational systems or confidential information.

## 3. Vendor Classification
Vendors are classified by risk level:
- **Critical**: Access to sensitive data, direct impact on operations, or regulated functions
- **High**: Access to confidential data or significant operational dependencies
- **Medium**: Limited data access or operational impact
- **Low**: No data access, minimal operational impact

## 4. Due Diligence
Before onboarding, all critical and high-risk vendors must complete a security assessment questionnaire. Additional requirements include:
- Review of SOC 2 Type II, ISO 27001, or equivalent certifications
- Validation of encryption practices for data at rest and in transit
- Confirmation of incident response and breach notification capabilities
- Review of subcontractor and fourth-party dependencies
- Background checks for vendor personnel with privileged access

## 5. Contracts and Agreements
All vendor contracts must include:
- Confidentiality and data protection clauses
- Defined security and privacy obligations
- Right-to-audit provisions
- Breach notification requirements (24–72 hours depending on criticality)
- Data return and destruction procedures upon termination
- Compliance with applicable regulations (GDPR, HIPAA, etc.)
- Cyber insurance or liability coverage requirements

## 6. Ongoing Monitoring
Critical vendors are reviewed annually; high-risk vendors at least every 18 months. Monitoring activities include:
- Review of security audit reports and certifications
- Assessment of open vulnerabilities or security incidents
- Validation of contract compliance
- Re-evaluation of risk classification based on service changes

## 7. Access Control
Vendor access to organizational systems requires:
- Dedicated service accounts with least privilege
- Multi-factor authentication
- Time-bound access (expiration dates)
- Monitoring and logging of all activities
- Immediate revocation upon contract termination

## 8. Incident Management
Vendors must report security incidents affecting organizational data within 24 hours. The organization retains the right to conduct forensic investigations and require remediation.

## 9. Offboarding
Upon termination, vendors must return or securely destroy all organizational data. Access credentials are revoked immediately. A final security review confirms data handling compliance.

## 10. Review
This policy is reviewed annually and updated to reflect regulatory changes, threat landscape evolution, and lessons learned from vendor incidents.
""",
    },
    {
        "name": "Data Classification Policy",
        "content": """# Data Classification Policy

## 1. Purpose
This policy establishes a framework for classifying organizational data based on sensitivity, value, and regulatory requirements. It ensures that data is handled, stored, transmitted, and destroyed in a manner commensurate with its classification level.

## 2. Scope
This policy applies to all data created, received, stored, processed, or transmitted by [Organization Name], regardless of form (electronic, physical, verbal) or location (on-premises, cloud, mobile devices, third-party systems).

## 3. Classification Levels
### 3.1 Public
Data intended for public disclosure. No restrictions on distribution. Examples: marketing materials, press releases, published financial reports.

### 3.2 Internal
Data for internal use only. Unauthorized disclosure could cause minor inconvenience but no material harm. Examples: internal memos, organizational charts, non-sensitive policies.

### 3.3 Confidential
Data whose unauthorized disclosure could cause financial loss, reputational damage, or operational disruption. Examples: customer lists, contracts, product roadmaps, employee records.

### 3.4 Restricted
Data whose unauthorized disclosure could cause severe harm, legal liability, or regulatory penalties. Examples: payment card data, health records, authentication credentials, source code, trade secrets.

## 4. Data Handling Requirements
| Classification | Encryption at Rest | Encryption in Transit | Access Controls | Labeling | Retention |
|---|---|---|---|---|---|
| Public | Recommended | Required | Minimal | Optional | Per schedule |
| Internal | Recommended | Required | Role-based | Optional | Per schedule |
| Confidential | Required (AES-256) | Required (TLS 1.2+) | Need-to-know | Required | Per schedule |
| Restricted | Required (AES-256) | Required (TLS 1.2+) | Strict least privilege | Required | Strict per regulation |

## 5. Roles and Responsibilities
- **Data Owners**: Business unit leaders responsible for assigning and reviewing classifications
- **Data Stewards**: Personnel who manage data quality, access requests, and handling procedures
- **IT Security**: Implements technical controls aligned with classification levels
- **All Users**: Handle data according to its classification and report misclassified data

## 6. Labeling and Marking
Confidential and Restricted data must be labeled with its classification. Digital labels should be embedded in file metadata or headers. Physical documents must bear classification stamps on every page.

## 7. Data Movement and Sharing
Transfer of Confidential or Restricted data outside the organization requires:
- Encryption of the transmission medium
- Signed data sharing agreements
- Confirmation of recipient's ability to maintain equivalent controls
- Logging of transfer for audit purposes

## 8. Data Retention and Disposal
Data must be retained only as long as required by business needs and legal obligations. Disposal methods must render data irrecoverable: secure erase for electronic media, shredding for paper.

## 9. Exception Handling
Any exception to classification or handling requirements must be documented with a risk acceptance approved by the data owner and CISO.

## 10. Review
Classifications are reviewed annually or when the data's sensitivity changes. This policy is reviewed annually.
""",
    },
    {
        "name": "Privacy Policy",
        "content": """# Privacy Policy

## 1. Purpose
This Privacy Policy describes how [Organization Name] collects, uses, stores, shares, and protects personal data. It reflects our commitment to respecting individual privacy rights and complying with applicable data protection laws, including GDPR, CCPA, and other regional regulations.

## 2. Scope
This policy applies to all personal data processed by the organization, including data about employees, customers, prospects, website visitors, and any other individuals whose information we hold.

## 3. Data Collection Principles
We collect personal data only for specified, explicit, and legitimate purposes. Collection is limited to what is necessary for those purposes. We collect data lawfully and fairly, with transparency about how it will be used.

Types of personal data we may collect include:
- Contact information (name, email, phone, address)
- Employment and professional information
- Account credentials and authentication data
- Transaction and billing information
- Technical data (IP address, browser type, device identifiers)
- Cookies and usage analytics

## 4. Lawful Basis for Processing
We process personal data based on one or more lawful grounds:
- Consent of the data subject
- Performance of a contract
- Compliance with legal obligations
- Protection of vital interests
- Performance of a task carried out in the public interest
- Legitimate interests of the organization

## 5. Data Use
Personal data is used for:
- Providing products and services
- Managing accounts and transactions
- Communicating about updates, security alerts, and marketing (where consented)
- Complying with legal and regulatory obligations
- Improving products, services, and user experience
- Detecting and preventing fraud and security incidents

## 6. Data Sharing
We do not sell personal data. We share data only with:
- Service providers under contract and confidentiality obligations
- Legal or regulatory authorities when required by law
- Professional advisors (legal, audit, insurance)
- In connection with mergers, acquisitions, or asset sales

All third-party recipients must demonstrate adequate data protection capabilities.

## 7. Data Retention
Personal data is retained only as long as necessary for the purposes for which it was collected, or as required by law. Retention schedules are documented and reviewed periodically.

## 8. Data Subject Rights
Individuals have the right to:
- Access their personal data
- Request correction of inaccurate data
- Request deletion (right to be forgotten)
- Object to or restrict processing
- Data portability
- Withdraw consent at any time
- Lodge a complaint with a supervisory authority

Requests are processed within 30 days unless complexity requires extension.

## 9. Security Measures
We implement appropriate technical and organizational measures to protect personal data, including encryption, access controls, network security, staff training, and regular security assessments.

## 10. International Transfers
Personal data transferred outside the jurisdiction of collection is protected through adequacy decisions, Standard Contractual Clauses, or other legally recognized transfer mechanisms.

## 11. Breach Notification
In the event of a personal data breach, we will notify affected individuals and relevant supervisory authorities in accordance with legal timeframes (e.g., within 72 hours under GDPR).

## 12. Policy Updates
This policy is reviewed annually and updated to reflect changes in practices, technology, and legal requirements. Material changes are communicated to affected individuals.

## 13. Contact
For privacy-related inquiries or to exercise your rights, contact our Data Protection Officer at [privacy@organization.com].
""",
    },
]


def get_policy_templates() -> List[Dict[str, Any]]:
    """Return the full list of seeded policy templates."""
    return POLICY_TEMPLATES


def get_template_by_name(name: str) -> Optional[Dict[str, Any]]:
    """Return a single template by exact name match."""
    for template in POLICY_TEMPLATES:
        if template["name"] == name:
            return template
    return None
