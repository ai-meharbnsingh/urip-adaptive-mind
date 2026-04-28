"""
connectors/extended_simulator.py — extended synthetic data simulator.

P1.8: extended simulator mode.

Design decisions
----------------
- 12 source labels exactly matching the extended tool stack (per ):
  zscaler, netskope, sentinelone, ms_entra, sharepoint, manageengine_sdp,
  manageengine_ec, manageengine_mdm, tenable, burpsuite, gtb_dlp, cloudsek

- Acme's industry context is IT services / consultancy (not manufacturing like RE).
  Assets are enterprise IT assets (SaaS apps, cloud infra, employee endpoints,
  collaboration tools, help-desk tickets, mobile devices) rather than OT/assembly lines.

- Each source has a curated finding list matching what that tool would ACTUALLY surface
  at a company like Acme.  This is important for the demo — a CISO seeing "Conveyor
  Belt Sensor Buffer Overflow" would immediately know the data is fake.

- Source coverage guarantee: fetch_findings(count=N) cycles through all 12 sources in
  round-robin order when count >= 12, then fills remaining slots randomly.  This ensures
  the test assertion "all 12 sources appear in 120 findings" always passes deterministically.

- Out-of-scope vs simulator_connector.py code sharing:
  Both connectors share the same abstract interface (BaseConnector) and DTO types.
  The CVE/finding DATA is intentionally separate — Extended uses different source names
  and industry-appropriate findings.  The normalize() logic is nearly identical because
  the schema is the same; a _normalize_common() helper could be extracted to a base
  module if a third simulator variant is added.  Noted as an out-of-scope improvement.
"""

from __future__ import annotations

import random
import uuid
from datetime import datetime, timezone
from typing import Optional

from connectors.base.connector import (
    BaseConnector,
    ConnectorHealth,
    ConnectorSession,
    CredentialFieldSpec,
    RawFinding,
    URIPRiskRecord,
)
from connectors.base.registry import register_connector
from connectors.base.setup_guides_data import SETUP_GUIDES

# ─────────────────────────────────────────────────────────────────────────────
# Extended source labels — 12 tools from the blueprint
# ─────────────────────────────────────────────────────────────────────────────

EXTENDED_SOURCES = [
    "zscaler",
    "netskope",
    "sentinelone",
    "ms_entra",
    "sharepoint",
    "manageengine_sdp",
    "manageengine_ec",
    "manageengine_mdm",
    "tenable",
    "burpsuite",
    "gtb_dlp",
    "cloudsek",  # NOTE: production tenants use connectors/cloudsek/ (real API) instead of this simulator entry
]

# ─────────────────────────────────────────────────────────────────────────────
# extended CVEs/findings per source
# Each entry: (finding_id, title, cvss, severity, domain)
# ─────────────────────────────────────────────────────────────────────────────

EXTENDED_FINDINGS: dict[str, list[tuple[str, str, float, str, str]]] = {
    "zscaler": [
        ("ZS-001", "Malware Download Blocked from Employee Browser — Acme-FIN-01", 7.5, "high", "network"),
        ("ZS-002", "Shadow SaaS: Unauthorized File Sync to Personal Dropbox", 6.5, "medium", "network"),
        ("ZS-003", "CASB Alert: Sensitive Data Upload to ChatGPT (AI Tool)", 8.0, "high", "network"),
        ("ZS-004", "DNS Category Block: Crypto Mining Pool Contacted by ADV-LAPTOP-07", 7.2, "high", "network"),
        ("ZS-005", "Bandwidth Anomaly: 4GB Exfil via Mega.nz from ADV-WS-22", 9.0, "critical", "network"),
        ("ZS-006", "Phishing URL Clicked: Credential Harvesting Site", 8.5, "high", "network"),
        ("CVE-2024-20353", "Cisco ASA/FTD DoS — Zscaler Proxy Chain Affected", 8.6, "high", "network"),
        ("ZS-007", "TLS Inspection Bypass Attempt — Pinned Certificate App", 6.0, "medium", "network"),
        ("ZS-008", "Unauthorized Tor Exit Node Access via ZIA", 9.1, "critical", "network"),
        ("ZS-009", "High-Risk App: Unauthorized TeamViewer Usage Detected", 6.5, "medium", "network"),
    ],
    "netskope": [
        ("NS-001", "DLP Alert: PAN Data in Outbound Email Attachment (Gmail)", 9.1, "critical", "application"),
        ("NS-002", "CASB: External Share of Confidential Doc to Personal Account", 7.5, "high", "application"),
        ("NS-003", "Malware Uploaded to OneDrive and Synced to 3 Endpoints", 8.8, "high", "endpoint"),
        ("NS-004", "SaaS Risk Score High: Unsanctioned AI Tool with Data Retention", 7.0, "high", "application"),
        ("NS-005", "Netskope DLP: Source Code Repository Uploaded to Personal GitHub", 9.0, "critical", "application"),
        ("NS-006", "Cloud Firewall: C2 Beacon to Known Cobalt Strike IP via SaaS", 9.5, "critical", "network"),
        ("NS-007", "Account Compromise Risk: Admin SaaS Login from TOR Exit Node", 8.5, "high", "identity"),
        ("NS-008", "Anomalous Data Download: 2,000 Customer Records from CRM", 9.0, "critical", "application"),
        ("NS-009", "Unauthorized SaaS: WhatsApp Web Used on Corporate Device", 4.3, "medium", "application"),
        ("NS-010", "SSL Inspection Gap: Pinned-Certificate App Bypassing Netskope", 6.5, "medium", "network"),
    ],
    "sentinelone": [
        ("CVE-2024-3400", "Palo Alto PAN-OS Command Injection — Active Exploit on ADV-SRV-01", 10.0, "critical", "endpoint"),
        ("CVE-2024-27198", "JetBrains TeamCity Auth Bypass — SentinelOne Agent Alert", 9.8, "critical", "endpoint"),
        ("S1-001", "Ransomware Behavior Detected: File Encryption on ADV-FIN-WS-03", 9.8, "critical", "endpoint"),
        ("S1-002", "Lateral Movement: PsExec Used by Non-Admin on Domain Controller", 9.0, "critical", "endpoint"),
        ("CVE-2024-6387", "OpenSSH RegreSSHion RCE — Unpatched Agent on ADV-LINUX-04", 8.1, "high", "endpoint"),
        ("S1-003", "Suspicious PowerShell: LOLBIN Abuse on ADV-HR-WS-11", 7.5, "high", "endpoint"),
        ("S1-004", "Credential Dump Attempt: Mimikatz Signature on ADV-WS-07", 9.0, "critical", "endpoint"),
        ("CVE-2023-36884", "Microsoft Office HTML RCE — Zero-Day Phish Opened by Extended User", 8.3, "high", "endpoint"),
        ("S1-005", "USB Malware: AutoRun Threat on Finance Laptop ADV-FIN-LT-02", 7.0, "high", "endpoint"),
        ("S1-006", "Agent Health: 12 Endpoints Missing SentinelOne Agent (BYOD)", 6.0, "medium", "endpoint"),
        ("S1-007", "Process Injection: Suspicious DLL Loaded in svchost.exe", 8.5, "high", "endpoint"),
    ],
    "ms_entra": [
        ("ENTRA-001", "Risky Sign-In: Impossible Travel Detected — ADV-CEO Account", 9.0, "critical", "identity"),
        ("ENTRA-002", "Conditional Access Failure: MFA Bypass Attempt from Unknown Device", 8.5, "high", "identity"),
        ("ENTRA-003", "Legacy Auth Enabled for 3 Service Accounts — MFA Cannot Protect", 7.5, "high", "identity"),
        ("ENTRA-004", "Global Admin Role Assigned Outside PIM — No Approval Record", 9.5, "critical", "identity"),
        ("ENTRA-005", "Guest Account with SharePoint Admin Rights — External User", 8.0, "high", "identity"),
        ("ENTRA-006", "Password Spray Attack: 40 Failed Logins Across 20 Accounts in 5 min", 8.5, "high", "identity"),
        ("ENTRA-007", "Entra ID: Token Replay Attack Detected (Anomalous Session Lifetime)", 9.0, "critical", "identity"),
        ("ENTRA-008", "MFA Registration Hijack: Authenticator App Changed from Unknown IP", 8.8, "high", "identity"),
        ("ENTRA-009", "Service Principal with Owner Role on All Resource Groups", 9.0, "critical", "cloud"),
        ("ENTRA-010", "Stale Privileged Accounts: 5 Former Employees Still Active in Entra", 7.5, "high", "identity"),
        ("ENTRA-011", "Conditional Access Policy Gap: Unmanaged Device Accessing O365 Mail", 7.0, "high", "identity"),
    ],
    "sharepoint": [
        ("SP-001", "Anonymous Link Created for NDA-Protected Client Proposal Document", 8.0, "high", "application"),
        ("SP-002", "External Sharing: Financial Projections Shared to Non-Corporate Email", 8.5, "high", "application"),
        ("SP-003", "Sensitivity Label Violation: Confidential Doc Moved to Public Site", 7.5, "high", "application"),
        ("SP-004", "Teams: Sensitive HR Data Shared in General Channel (500 members)", 7.0, "high", "application"),
        ("SP-005", "SharePoint Audit: 3,000 Files Accessed by Single User in 1 Hour", 8.0, "high", "application"),
        ("SP-006", "OneDrive Sync: Source Code Synced to Personal Computer Outside Corporate", 9.0, "critical", "application"),
        ("SP-007", "Oversharing: Entire Project Site Shared with All Guests (50 externals)", 7.5, "high", "application"),
        ("SP-008", "Teams DLP: Credit Card Number Detected in Chat Message", 8.0, "high", "application"),
        ("SP-009", "SharePoint Permission Creep: 200+ Unique Permissions on Document Library", 5.3, "medium", "application"),
        ("SP-010", "Teams Meeting Recording with Sensitive Info Shared Externally", 6.5, "medium", "application"),
    ],
    "manageengine_sdp": [
        ("SDP-001", "Critical Ticket SLA Breach: P1 Incident Open 72+ Hours Without Update", 7.0, "high", "application"),
        ("SDP-002", "Change Request Bypassed CAB Approval — Emergency Change Not Authorized", 8.5, "high", "application"),
        ("SDP-003", "Service Account Password Reset Without IT Approval (Ticket Backdated)", 9.0, "critical", "identity"),
        ("SDP-004", "Firewall Rule Change Ticket: Production Firewall Opened to 0.0.0.0/0", 9.5, "critical", "network"),
        ("SDP-005", "Unresolved Vulnerability Tickets: 45 High-Severity Open > 30 Days", 7.5, "high", "application"),
        ("SDP-006", "ITSM Audit: Admin Ticket Created Without Requestor — SOD Violation", 8.0, "high", "application"),
        ("SDP-007", "Patch Deployment Ticket: 80 Endpoints Missed Monthly Patching Cycle", 7.0, "high", "endpoint"),
        ("SDP-008", "Vendor Access Request: Unreviewed External Access to Production ITSM", 7.5, "high", "identity"),
    ],
    "manageengine_ec": [
        ("EC-001", "Patch Gap: 45 Endpoints Missing Critical Windows Security Update (MS24-031)", 8.5, "high", "endpoint"),
        ("CVE-2024-38063", "Windows TCP/IP RCE (IPv6) — 12 Unpatched Extended Endpoints", 9.8, "critical", "endpoint"),
        ("EC-002", "Software Inventory: Unauthorized Remote Desktop Tool on 8 Devices", 7.0, "high", "endpoint"),
        ("EC-003", "EOL Software: Windows 7 Found on 3 Isolated Test Lab Machines", 9.5, "critical", "endpoint"),
        ("EC-004", "BitLocker Not Enabled: 5 Laptops Without Full Disk Encryption", 7.5, "high", "endpoint"),
        ("CVE-2024-21887", "Ivanti Connect Secure Auth Bypass — Unpatched on ADV-VPN-GW", 9.1, "critical", "endpoint"),
        ("EC-005", "Local Admin Proliferation: 23 Endpoints with Non-Standard Local Admins", 6.5, "medium", "endpoint"),
        ("EC-006", "Anti-Virus Signature Outdated: 10+ Endpoints > 7 Days Behind", 5.3, "medium", "endpoint"),
        ("EC-007", "Unapproved Application: Crypto Miner Detected on ADV-DEV-WS-04", 9.0, "critical", "endpoint"),
    ],
    "manageengine_mdm": [
        ("MDM-001", "Jailbroken Device: iPhone 15 (ADV-EMP-042) Accessing Corporate Email", 8.5, "high", "endpoint"),
        ("MDM-002", "Non-Compliant Device: Android Missing Device Encryption — MDM Policy", 7.5, "high", "endpoint"),
        ("MDM-003", "Unmanaged Device: BYOD with CRM App — No MDM Profile Installed", 7.0, "high", "endpoint"),
        ("MDM-004", "Outdated iOS: 8 iPhones on iOS 15 (2 Major Versions Behind)", 6.5, "medium", "endpoint"),
        ("MDM-005", "MDM Unenrollment: Employee Removed Corporate Profile (Potential Leak)", 8.0, "high", "endpoint"),
        ("MDM-006", "Rooted Android: Samsung Device with Root Access on Corporate Network", 8.5, "high", "endpoint"),
        ("MDM-007", "Mobile Malware: Joker Spyware Variant Detected on ADV-MOBILE-11", 9.0, "critical", "endpoint"),
        ("MDM-008", "Corporate App Outdated: 15 Devices Running Unpatched Outlook Mobile", 5.3, "medium", "endpoint"),
    ],
    "tenable": [
        ("CVE-2024-34102", "Adobe Commerce XML Injection — Extended Client Portal Affected", 9.8, "critical", "application"),
        ("CVE-2024-4577", "PHP CGI Argument Injection — Extended Internal Dev Server", 9.8, "critical", "application"),
        ("TEN-001", "Open SSH Port 22 Exposed to Internet on ADV-SRV-PROD-03", 7.5, "high", "network"),
        ("CVE-2023-44228", "Log4Shell — Extended Legacy Java App Unpatched", 10.0, "critical", "application"),
        ("TEN-002", "TLS 1.0/1.1 Enabled on Extended Client-Facing API Gateway", 7.4, "high", "network"),
        ("TEN-003", "Default Credentials on Internal Monitoring Stack (Grafana admin/admin)", 9.8, "critical", "application"),
        ("CVE-2024-0012", "Palo Alto PAN-OS Privilege Escalation — ADV-FW-EDGE-01", 9.8, "critical", "network"),
        ("TEN-004", "SQL Injection in Internal Timesheet Application (Auth Bypass)", 9.8, "critical", "application"),
        ("CVE-2023-50164", "Apache Struts Path Traversal — Legacy ERP Integration Endpoint", 9.8, "critical", "application"),
        ("TEN-005", "Exposed .env File on Staging Subdomain staging.acme-internal.com", 8.6, "high", "application"),
        ("TEN-006", "Subdomain Takeover: dev-api.example.com DNS Pointing to Unclaimed Cloud", 7.5, "high", "network"),
        ("TEN-007", "Publicly Accessible Redis 6379 on Extended Analytics Server", 9.8, "critical", "network"),
    ],
    "burpsuite": [
        ("BURP-001", "Stored XSS in Extended Client Portal Comment Field (Persistent)", 7.5, "high", "application"),
        ("BURP-002", "IDOR: Client A Can Access Client B Invoices via /api/invoices/{id}", 8.5, "high", "application"),
        ("BURP-003", "SSRF via Webhook URL in Integration Settings — Internal Service Scan", 8.6, "high", "application"),
        ("BURP-004", "JWT Algorithm Confusion — None Algorithm Accepted on Admin Endpoint", 9.5, "critical", "application"),
        ("BURP-005", "Mass Assignment: POST /api/users Accepts role=admin Parameter", 8.8, "high", "application"),
        ("BURP-006", "Broken Object Level Auth: Consultant Accesses Other Consultant Timesheets", 7.5, "high", "application"),
        ("BURP-007", "SQL Injection in Report Filter API (Blind, Time-Based Confirmed)", 9.8, "critical", "application"),
        ("BURP-008", "Missing Rate Limiting on Login — 1000+ Attempts No Lockout", 6.5, "medium", "application"),
        ("BURP-009", "Sensitive Data in Error: Stack Trace with DB Credentials in Response", 7.5, "high", "application"),
        ("BURP-010", "CSRF on Account Settings — Token Not Validated on Email Change", 6.1, "medium", "application"),
        ("BURP-011", "GraphQL Introspection Enabled in Production — Full Schema Exposed", 5.3, "medium", "application"),
        ("BURP-012", "XML External Entity (XXE) on SOAP Integration with Legacy Partner API", 8.0, "high", "application"),
    ],
    "gtb_dlp": [
        ("GTB-001", "USB Transfer: 500MB of Client Deliverables Copied to Personal USB", 9.0, "critical", "endpoint"),
        ("GTB-002", "DLP Block: Employee Attempted to Print 200 Pages of Client Contracts", 6.5, "medium", "endpoint"),
        ("GTB-003", "Email DLP: Proposal with Pricing Sent to Personal Gmail Account", 8.5, "high", "application"),
        ("GTB-004", "Screen Capture: Sensitive Financial Dashboard Captured via Snipping Tool", 7.0, "high", "endpoint"),
        ("GTB-005", "Clipboard Monitoring: 150-Row Customer List Pasted into Personal Notes App", 8.0, "high", "endpoint"),
        ("GTB-006", "USB Block Override: Manager Approved USB Exception — Audit Required", 6.0, "medium", "endpoint"),
        ("GTB-007", "DLP Keyword Match: 'Salary' + 'Confidential' in Outbound Email to Competitor Domain", 9.0, "critical", "application"),
        ("GTB-008", "Insider Risk: Departing Employee Mass Download Before Last Day", 9.5, "critical", "endpoint"),
    ],
    "cloudsek": [
        ("CSK-001", "Dark Web: Extended Employee Credentials in BreachForums Dump (23 Accounts)", 9.0, "critical", "identity"),
        ("CSK-002", "Brand Impersonation: Fake Extended LinkedIn Page Collecting Resumes", 7.5, "high", "identity"),
        ("CSK-003", "Leaked API Key: Extended AWS Access Key Found in Public GitHub Repository", 9.5, "critical", "cloud"),
        ("CSK-004", "Dark Web Forum: Extended Network VPN Credentials Listed for Sale", 9.8, "critical", "identity"),
        ("CSK-005", "Typosquat Domain: acme-security.in Registered by Unknown Entity", 6.5, "medium", "network"),
        ("CSK-006", "Code Leak: Internal Extended Project Repo Found on Paste Site", 8.5, "high", "application"),
        ("CSK-007", "Executive Spear Phish Kit: CEO Email Spoofing Template Sold on Dark Web", 8.0, "high", "identity"),
        ("CSK-008", "Exposed Config: Extended Confluence Space Indexed by Search Engine", 7.5, "high", "application"),
        ("CSK-009", "Threat Intel: APT Group Targeting Acme's Industry (IT Services Sector)", 8.5, "high", "endpoint"),
        ("CSK-010", "Dark Web: RDP Credentials for adv-jump-01.example.com Listed on Exploit[.]in", 9.8, "critical", "endpoint"),
    ],
}

# Extended asset inventory — enterprise IT company assets
EXTENDED_ASSETS: dict[str, list[str]] = {
    "endpoint": [
        "ADV-FIN-WS-01 (CFO Workstation)", "ADV-CEO-LAPTOP-01", "ADV-HR-WS-11",
        "ADV-DEV-WS-04 (Developer Machine)", "ADV-LAPTOP-07", "ADV-FIN-LT-02",
        "ADV-MOBILE-11 (Android)", "ADV-EMP-042 (iPhone 15)", "ADV-SOC-WS-01",
        "ADV-LINUX-04 (Ubuntu Dev Server)", "ADV-WS-07 (Domain Joined)", "ADV-WS-22",
    ],
    "cloud": [
        "AWS EKS Cluster — Extended Client Portal", "S3 Bucket acme-client-deliverables-prod",
        "Azure AD Tenant example.com", "Azure AKS — Internal Tools",
        "AWS Lambda — Billing API", "AWS RDS PostgreSQL — CRM Data",
        "Azure Blob — Contract Repository", "GCP BigQuery — Analytics",
        "AWS Secrets Manager — Prod Keys", "CloudFront CDN example.com",
    ],
    "network": [
        "ADV-FW-EDGE-01 (Palo Alto NGFW)", "ADV-VPN-GW (GlobalProtect)",
        "Core Switch ADV-SW-CORE-01", "Load Balancer ADV-LB-WEB-01",
        "DNS ADV-DNS-INT-01", "SD-WAN Controller ADV-SDWAN",
        "WAF Cloudflare Edge", "IDS Sensor ADV-IDS-01",
        "Proxy ADV-PROXY-INT", "WiFi Controller ADV-WLC-01",
    ],
    "application": [
        "Client Portal portal.example.com", "Internal Timesheet App timesheet.example.com",
        "CRM Salesforce ADV-CRM-PROD", "JIRA acme.atlassian.net",
        "Internal Wiki Confluence", "CI/CD GitLab gitlab.example.com",
        "ERP SAP ADV-SAP-PROD", "HR Portal Darwinbox",
        "Billing System billing.example.com", "Dev Staging staging.acme-internal.com",
    ],
    "identity": [
        "Azure AD Global Admin Group", "Service Account svc-crm-integration",
        "Privileged Access ADV-PAM-VAULT", "Entra ID Privileged Roles",
        "LDAP ADV-LDAP-INT", "Duo MFA Gateway",
        "Okta SSO Production", "Service Account svc-billing-sync",
        "Root AWS Account acme-master-org", "API Gateway Service Keys",
    ],
}

EXTENDED_DOMAIN_TEAM = {
    "endpoint": "IT Operations",
    "cloud": "Cloud Engineering",
    "network": "Network & Security",
    "application": "AppSec / DevSecOps",
    "identity": "Identity & Access",
}


@register_connector("extended_simulator")
class ExtendedSimulatorConnector(BaseConnector):
    """
    extended simulator connector.

    Returns synthetic findings labeled with Acme's 12-tool stack.
    Used when tenant simulator_mode = "acme".
    """

    NAME = "extended_simulator"

    # ── Z3: Tool Catalog metadata ───────────────────────────────────────────
    DISPLAY_NAME = "Extended Simulator (12-tool stack)"
    CATEGORY = "SIMULATOR"
    SHORT_DESCRIPTION = (
        "Synthetic findings spanning the Acme 12-tool stack — IT-services demo data."
    )
    STATUS = "simulated"
    VENDOR_DOCS_URL = None
    SUPPORTED_PRODUCTS = [
        "zscaler", "netskope", "sentinelone", "ms_entra", "sharepoint",
        "manageengine_sdp", "manageengine_ec", "manageengine_mdm",
        "tenable", "burpsuite", "gtb_dlp", "cloudsek",
    ]
    MODULE_CODE = "CORE"
    CREDENTIAL_FIELDS = [
        CredentialFieldSpec(
            name="tenant_id", label="Tenant Label", type="text", required=False,
            placeholder="acme-default",
            help_text="Optional label attached to extended-simulator runs.",
        ),
    ]

    # P33-Z3 (revised): inline onboarding content rendered in the Tool Catalog drawer.
    SETUP_GUIDE = SETUP_GUIDES["extended_simulator"]

    def authenticate(self, tenant_credentials: dict) -> ConnectorSession:
        return ConnectorSession(
            connector_name=self.NAME,
            tenant_id=tenant_credentials.get("tenant_id", "acme-default"),
            token="extended-simulator-no-auth",
            expires_at=datetime(9999, 12, 31, tzinfo=timezone.utc),
        )

    def fetch_findings(self, since: datetime, **kwargs) -> list[RawFinding]:
        """
        Generate extended findings.

        Parameters
        ----------
        count : int, optional
            Number of findings to generate.  Default: random 5–15.
            All 12 sources are guaranteed to appear if count >= 12 (round-robin).
        tenant_id : str, optional
            Tenant context; stored in each RawFinding.tenant_id.
        """
        count: int = kwargs.get("count", random.randint(5, 15))
        tenant_id: str = kwargs.get("tenant_id", "acme-default")

        findings: list[RawFinding] = []

        # Round-robin fill: guarantees all 12 sources when count >= 12
        source_cycle = list(EXTENDED_SOURCES)  # copy to avoid mutating module constant
        random.shuffle(source_cycle)

        for i in range(count):
            # Cycle through sources deterministically for coverage, then wrap
            source = source_cycle[i % len(source_cycle)]
            cve_id, title, cvss, severity, domain = random.choice(EXTENDED_FINDINGS[source])

            asset_pool = EXTENDED_ASSETS.get(domain, EXTENDED_ASSETS["endpoint"])
            asset = random.choice(asset_pool)
            owner = EXTENDED_DOMAIN_TEAM.get(domain, "IT Operations")

            raw_id = str(uuid.uuid4())
            findings.append(RawFinding(
                id=raw_id,
                source=source,
                raw_data={
                    "cve_id": cve_id,
                    "title": title,
                    "cvss": cvss,
                    "severity": severity,
                    "domain": domain,
                    "asset": asset,
                    "owner_team": owner,
                },
                fetched_at=datetime.now(timezone.utc),
                tenant_id=tenant_id,
            ))

        return findings

    def normalize(self, raw: RawFinding) -> URIPRiskRecord:
        d = raw.raw_data
        cve_id = d["cve_id"]
        # Custom/internal IDs → cve_id=None
        if not cve_id.startswith("CVE-"):
            cve_id = None

        return URIPRiskRecord(
            finding=d["title"],
            description=(
                f"[{d['cve_id']}] {d['title']}. "
                f"Source: {raw.source}. Asset: {d['asset']}."
            ),
            source=raw.source,
            domain=d["domain"],
            cvss_score=d["cvss"],
            severity=d["severity"],
            asset=d["asset"],
            owner_team=d["owner_team"],
            cve_id=cve_id,
        )

    def health_check(self) -> ConnectorHealth:
        return ConnectorHealth(
            connector_name=self.NAME,
            status="ok",
            last_run=datetime.now(timezone.utc),
            error_count=0,
        )
