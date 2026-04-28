"""
URIP Seed Script — Generate 200 synthetic risks + users + test data

Usage: python -m backend.seed
       URIP_SEED_PASSWORD='strong!pass' python -m backend.seed
"""
import os
import random
import secrets
import string
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from backend.config import settings
from backend.database import Base
from backend.middleware.auth import hash_password


def _resolve_seed_password() -> tuple[str, bool]:
    """Return (password, was_generated). Prefer URIP_SEED_PASSWORD over a
    random one so a known-weak demo string is never committed to source."""
    env = os.environ.get("URIP_SEED_PASSWORD")
    if env:
        return env, False
    alphabet = string.ascii_letters + string.digits + "!@#$%^&*"
    return "".join(secrets.choice(alphabet) for _ in range(20)), True
from backend.models import (
    AcceptanceRequest,
    AuditLog,
    ConnectorConfig,
    RemediationTask,
    Risk,
    User,
)
from backend.services.sla_service import SLA_HOURS

# Use sync engine for seeding
sync_engine = create_engine(settings.DATABASE_URL_SYNC)

# ─── CONSTANTS ───────────────────────────────────────────────────────

SOURCES = [
    "crowdstrike", "easm", "cnapp", "armis", "vapt",
    "threat_intel", "cert_in", "bug_bounty", "soc",
]

SOURCE_DOMAIN_MAP = {
    "crowdstrike": ["endpoint"],
    "easm": ["network", "cloud", "application"],
    "cnapp": ["cloud"],
    "armis": ["ot"],
    "vapt": ["application", "network"],
    "threat_intel": ["endpoint", "network", "application"],
    "cert_in": ["application", "endpoint", "network"],
    "bug_bounty": ["application"],
    "soc": ["endpoint", "network", "identity"],
}

DOMAIN_TEAM_MAP = {
    "endpoint": "Infra Team",
    "cloud": "Cloud Team",
    "network": "Network Team",
    "application": "App Team",
    "identity": "IAM Team",
    "ot": "OT Team",
}

STATUSES = ["open", "in_progress", "accepted", "closed"]
STATUS_WEIGHTS = [0.55, 0.25, 0.12, 0.08]

# Sample assets per domain (synthetic demo data)
ASSETS = {
    "endpoint": [
        "Finance Workstation FIN-WS-01", "HR Laptop HR-LT-042", "CISO Workstation EXEC-01",
        "Engineering Desktop ENG-WS-107", "Dealer Support Laptop DL-LT-15",
        "Chennai Plant Floor PC PF-CH-03", "Manesar Plant Terminal MN-TM-12",
        "QA Lab Machine QA-WS-05", "Marketing MacBook MKT-MB-22",
        "Server Room KVM Console SRV-KVM-01",
    ],
    "cloud": [
        "AWS EKS Cluster - Dealer Portal", "S3 Bucket re-customer-data-prod",
        "Azure AD Tenant example.com", "GCP BigQuery Analytics Warehouse",
        "AWS Lambda - Order Processing", "CloudFront CDN - example.com",
        "S3 Bucket re-marketing-assets", "AWS RDS PostgreSQL - ERP",
        "Azure Blob - Warranty Docs", "AWS ECR Container Registry",
    ],
    "network": [
        "Core Switch Chennai Plant CS-CH-01", "Firewall FW-DMZ-01 Internet Edge",
        "VPN Gateway VPN-GW-PRIMARY", "Load Balancer LB-WEB-01",
        "DNS Server DNS-INT-01", "WiFi Controller WLC-MN-01",
        "MPLS Router RTR-MPLS-CH", "IDS Sensor IDS-DMZ-02",
        "Network TAP TAP-CORE-01", "Proxy Server PROXY-INT-01",
    ],
    "application": [
        "Dealer Portal API api.dealers.example.com",
        "SAP ERP Production SAP-PRD-01", "Customer Mobile App v4.2",
        "E-Commerce Platform shop.example.com",
        "Warranty Management System WMS-01",
        "Spare Parts Catalog API parts-api.re.internal",
        "HR Portal HRMS Workday Integration",
        "CRM Salesforce Instance RE-CRM-PROD",
        "Internal Wiki Confluence wiki.re.internal",
        "CI/CD Pipeline Jenkins jenkins.re.internal",
    ],
    "identity": [
        "Domain Admin Accounts DA-GROUP-01",
        "Service Account svc-sap-integration",
        "CyberArk PAM Vault VAULT-PROD-01",
        "Azure AD Privileged Roles",
        "LDAP Server LDAP-INT-01",
        "MFA Gateway Duo Security",
        "Service Account svc-dealer-sync",
        "Root AWS Account re-master-org",
        "API Gateway Service Keys",
        "SSO IdP Okta Production",
    ],
    "ot": [
        "Chennai Plant HMI Controller HMI-CH-01",
        "Paint Shop PLC PLC-PAINT-03",
        "Assembly Line SCADA SCADA-ASSY-01",
        "Welding Robot Controller WRC-07",
        "Manesar Plant RTU RTU-MN-05",
        "Quality Inspection Camera QIC-04",
        "Conveyor Belt Sensor CBS-12",
        "Compressor Control Unit CCU-02",
        "Engine Test Bench ETB-CTRL-01",
        "Warehouse AGV Controller AGV-WH-03",
    ],
}

# Finding templates per source
FINDINGS = {
    "crowdstrike": [
        "Malware Signature Detected - Emotet Variant",
        "Suspicious PowerShell Execution",
        "Credential Dumping Attempt (Mimikatz)",
        "Lateral Movement via PsExec",
        "Ransomware Indicator - LockBit 3.0",
        "Fileless Malware Detected",
        "Cobalt Strike Beacon Communication",
        "Phishing Campaign - Spear Phishing",
        "Unpatched Windows Server 2019",
        "Endpoint Detection Bypass Attempt",
    ],
    "easm": [
        "Exposed S3 Bucket - Public Read",
        "Open MongoDB Port 27017",
        "Expired SSL Certificate",
        "Subdomain Takeover Risk",
        "Exposed Admin Panel",
        "Open Elasticsearch Port 9200",
        "DMARC Policy Not Enforced",
        "Exposed .git Directory",
        "Open SMTP Relay Detected",
        "Certificate Transparency Log Anomaly",
    ],
    "cnapp": [
        "S3 Bucket Without Encryption",
        "EC2 Instance with Public IP in Prod VPC",
        "IAM Role with AdministratorAccess",
        "Security Group Allows 0.0.0.0/0 Inbound",
        "CloudTrail Logging Disabled",
        "RDS Instance Publicly Accessible",
        "EBS Volume Not Encrypted",
        "Lambda Function with Excessive Permissions",
        "Root Account Used for Daily Operations",
        "VPC Flow Logs Disabled",
    ],
    "armis": [
        "Unencrypted OT Protocol (Modbus TCP)",
        "Legacy PLC Firmware Vulnerability",
        "Unpatched HMI Software",
        "OT Device Communicating to Internet",
        "Default Credentials on SCADA System",
        "Unauthorized Device on OT Network",
        "PLC Logic Modification Detected",
        "Industrial Protocol Anomaly",
        "Unpatched RTU Firmware CVE-2026-4521",
        "OT Network Segmentation Bypass",
    ],
    "vapt": [
        "SQL Injection in Search Parameter",
        "Cross-Site Scripting (XSS) Stored",
        "Broken Authentication - Token Leakage",
        "IDOR in User Profile API",
        "Remote Code Execution (RCE) in File Upload",
        "Server-Side Request Forgery (SSRF)",
        "XML External Entity (XXE) Injection",
        "Insecure Deserialization",
        "Broken Access Control - Privilege Escalation",
        "Sensitive Data Exposure in API Response",
    ],
    "threat_intel": [
        "Active Exploit Campaign Targeting Apache Struts",
        "Zero-Day Exploit for Microsoft Exchange",
        "APT Group Targeting Manufacturing Sector",
        "Supply Chain Attack via npm Package",
        "Botnet C2 Communication Detected",
        "Known Malicious IP Communicating with Assets",
        "Dark Web Credential Dump Includes RE Domain",
        "Ransomware Group Targeting Indian Automotive",
        "Exploit Kit Targeting Java Applications",
        "New CVE Published for SAP NetWeaver",
    ],
    "cert_in": [
        "CIVN-2026-001: Multiple Vulnerabilities in Google Chrome",
        "CIVN-2026-002: Apache Struts RCE (CVE-2026-1234)",
        "CIVN-2026-003: Microsoft Patch Tuesday Critical",
        "CIVN-2026-004: OpenSSL Buffer Overflow",
        "CIVN-2026-005: VMware vCenter Vulnerabilities",
        "CIVN-2026-006: Linux Kernel Privilege Escalation",
        "CIVN-2026-007: Oracle Java Critical Update",
        "CIVN-2026-008: Fortinet FortiOS Vulnerability",
        "CIVN-2026-009: Cisco IOS XE Web UI Exploit",
        "CIVN-2026-010: WordPress Plugin Vulnerability",
    ],
    "bug_bounty": [
        "IDOR in Dealer Portal Order History",
        "Stored XSS in Product Review Section",
        "Account Takeover via Password Reset Flow",
        "API Key Exposed in JavaScript Bundle",
        "Rate Limiting Bypass on Login Endpoint",
        "Open Redirect in OAuth Callback",
        "Information Disclosure in Error Pages",
        "CSRF in Profile Settings Update",
        "Insecure Direct Object Reference in /api/orders",
        "JWT Token Not Expiring After Logout",
    ],
    "soc": [
        "Suspicious Lateral Movement Detected",
        "Brute Force Attack on VPN Gateway",
        "Data Exfiltration Alert - Large Upload",
        "Anomalous Login from Unknown Geography",
        "Privilege Escalation Attempt",
        "DNS Tunneling Detected",
        "Rogue DHCP Server on VLAN",
        "After-Hours Admin Access Detected",
        "Failed Login Spike - 500+ in 10 min",
        "Unauthorized USB Device Connected",
    ],
}

CVE_IDS = [
    "CVE-2026-1234", "CVE-2026-2345", "CVE-2026-3456", "CVE-2026-4567",
    "CVE-2026-5678", "CVE-2026-6789", "CVE-2026-7890", "CVE-2026-8901",
    "CVE-2026-9012", "CVE-2026-0123", "CVE-2025-44228", "CVE-2025-38112",
    "CVE-2026-21887", "CVE-2026-27104", "CVE-2026-31337",
]


def generate_cvss_for_severity(severity: str) -> float:
    ranges = {
        "critical": (9.0, 10.0),
        "high": (7.0, 8.9),
        "medium": (4.0, 6.9),
        "low": (0.1, 3.9),
    }
    low, high = ranges[severity]
    return round(random.uniform(low, high), 1)


def severity_from_distribution() -> str:
    r = random.random()
    if r < 0.15:
        return "critical"
    elif r < 0.40:
        return "high"
    elif r < 0.80:
        return "medium"
    else:
        return "low"


def seed_database():
    Base.metadata.create_all(sync_engine)

    with Session(sync_engine) as session:
        # Check if already seeded
        existing = session.execute(text("SELECT COUNT(*) FROM users")).scalar()
        if existing > 0:
            print("Database already seeded. Skipping.")
            return

        now = datetime.now(timezone.utc)
        seed_password, generated = _resolve_seed_password()
        password_hash = hash_password(seed_password)

        # ─── USERS ─────────────────────────────────────────────
        users = [
            User(
                id=uuid.uuid4(), email="ciso@example.com",
                hashed_password=password_hash, full_name="Rajesh Kumar",
                role="ciso", team="Security",
            ),
            User(
                id=uuid.uuid4(), email="it.lead@example.com",
                hashed_password=password_hash, full_name="Priya Sharma",
                role="it_team", team="Infra Team",
            ),
            User(
                id=uuid.uuid4(), email="vp.eng@example.com",
                hashed_password=password_hash, full_name="Arun Mehta",
                role="executive", team="Engineering",
            ),
            User(
                id=uuid.uuid4(), email="board@example.com",
                hashed_password=password_hash, full_name="Siddharth Lal",
                role="board", team=None,
            ),
        ]
        session.add_all(users)
        session.flush()
        print(f"Created {len(users)} users")

        user_map = {u.role: u for u in users}

        # ─── 200 RISKS ────────────────────────────────────────
        risks = []
        for i in range(1, 201):
            source = random.choice(SOURCES)
            domain = random.choice(SOURCE_DOMAIN_MAP[source])
            severity = severity_from_distribution()
            cvss = generate_cvss_for_severity(severity)
            status = random.choices(STATUSES, weights=STATUS_WEIGHTS, k=1)[0]
            asset = random.choice(ASSETS[domain])
            finding = random.choice(FINDINGS[source])
            owner_team = DOMAIN_TEAM_MAP[domain]

            # Spread creation dates over past 60 days
            days_ago = random.randint(0, 60)
            created_at = now - timedelta(days=days_ago, hours=random.randint(0, 23))
            sla_hours = SLA_HOURS[severity]
            sla_deadline = created_at + timedelta(hours=sla_hours)

            # ~15% should be SLA breached (deadline in the past, still open/in_progress)
            if random.random() < 0.15 and status in ("open", "in_progress"):
                sla_deadline = now - timedelta(hours=random.randint(1, 72))

            cve_id = random.choice(CVE_IDS) if random.random() < 0.3 else None
            jira_ticket = f"RE-SEC-{random.randint(1000, 9999)}" if status == "in_progress" and random.random() < 0.5 else None

            risk = Risk(
                id=uuid.uuid4(),
                risk_id=f"RISK-2026-{i:03d}",
                finding=finding,
                description=f"Detected by {source} scan. Asset: {asset}. Immediate investigation required.",
                source=source,
                domain=domain,
                cvss_score=cvss,
                severity=severity,
                asset=asset,
                owner_team=owner_team,
                assigned_to=random.choice(users).id if status == "in_progress" else None,
                status=status,
                sla_deadline=sla_deadline,
                jira_ticket=jira_ticket,
                cve_id=cve_id,
                created_at=created_at,
                updated_at=created_at,
            )
            risks.append(risk)

        session.add_all(risks)
        session.flush()
        print(f"Created {len(risks)} risks")

        # ─── ACCEPTANCE REQUESTS ──────────────────────────────
        accepted_risks = [r for r in risks if r.status == "accepted"][:10]
        pending_count = 0
        approved_count = 0
        for risk in accepted_risks:
            is_approved = approved_count < 3 and random.random() < 0.4
            ar = AcceptanceRequest(
                id=uuid.uuid4(),
                risk_id=risk.id,
                requested_by=user_map["it_team"].id,
                justification=f"Risk mitigated through compensating controls. {risk.finding} on {risk.asset} "
                              f"has acceptable residual risk for current business operations.",
                compensating_controls=["DLP policies active", "CASB monitoring", "Quarterly review scheduled"],
                residual_risk=f"Potential {risk.domain} exposure if controls degrade",
                recommendation=f"Accept with monitoring. Schedule re-review in 90 days. "
                               f"Ensure compensating controls remain active.",
                status="approved" if is_approved else "pending",
                reviewed_by=user_map["ciso"].id if is_approved else None,
                review_date=now - timedelta(days=random.randint(1, 10)) if is_approved else None,
                review_period_days=90,
                created_at=now - timedelta(days=random.randint(1, 15)),
            )
            session.add(ar)
            if is_approved:
                approved_count += 1
            else:
                pending_count += 1

        print(f"Created {pending_count + approved_count} acceptance requests ({pending_count} pending, {approved_count} approved)")

        # ─── REMEDIATION TASKS ────────────────────────────────
        high_crit_risks = [r for r in risks if r.severity in ("critical", "high") and r.status in ("open", "in_progress")][:30]
        rem_statuses = ["not_started", "in_progress", "blocked", "completed", "verified"]
        rem_weights = [0.3, 0.35, 0.1, 0.2, 0.05]

        for risk in high_crit_risks:
            rem_status = random.choices(rem_statuses, weights=rem_weights, k=1)[0]
            task = RemediationTask(
                id=uuid.uuid4(),
                risk_id=risk.id,
                title=f"Remediate: {risk.finding}",
                description=f"Fix {risk.finding} on {risk.asset}. Priority: {risk.severity}.",
                assigned_to=random.choice(users).id,
                status=rem_status,
                priority=risk.severity,
                due_date=(now + timedelta(days=random.randint(1, 30))).date(),
                jira_key=f"RE-SEC-{random.randint(1000, 9999)}" if random.random() < 0.6 else None,
                completed_at=now - timedelta(days=random.randint(1, 5)) if rem_status in ("completed", "verified") else None,
                created_at=now - timedelta(days=random.randint(1, 20)),
            )
            session.add(task)

        print(f"Created {len(high_crit_risks)} remediation tasks")

        # ─── CONNECTOR CONFIGS ────────────────────────────────
        connector_names = {
            "crowdstrike": ("CrowdStrike Falcon Spotlight", "https://api.crowdstrike.com"),
            "easm": ("CrowdStrike EASM", "https://api.crowdstrike.com/easm"),
            "cnapp": ("CrowdStrike CNAPP", "https://api.crowdstrike.com/cloud"),
            "armis": ("Armis OT Security", "https://api.armis.com"),
            "vapt": ("VAPT Report Uploads", None),
            "threat_intel": ("Threat Intelligence Feed", "https://api.threatintel.example.com"),
            "cert_in": ("CERT-In Advisory Feed", "https://www.cert-in.org.in/api"),
            "bug_bounty": ("Bug Bounty Platform", "https://api.bugcrowd.com"),
            "soc": ("SIEM / SoC Alerts", "https://siem.example.internal/api"),
        }

        for source_type, (name, url) in connector_names.items():
            conn = ConnectorConfig(
                id=uuid.uuid4(),
                name=name,
                source_type=source_type,
                base_url=url,
                is_active=True,
                last_sync=now - timedelta(minutes=random.randint(5, 120)),
                sync_interval_minutes=60,
            )
            session.add(conn)

        print(f"Created {len(connector_names)} connector configs")

        # ─── AUDIT LOGS ──────────────────────────────────────
        actions = [
            ("login", "user", "User logged in"),
            ("risk_created", "risk", "New risk ingested from connector"),
            ("risk_status_changed", "risk", "Risk status updated"),
            ("risk_assigned", "risk", "Risk assigned to team member"),
            ("acceptance_requested", "acceptance", "Risk acceptance requested"),
            ("acceptance_approved", "acceptance", "Risk acceptance approved by CISO"),
            ("report_generated", "report", "Security report generated"),
            ("connector_synced", "connector", "Source connector synced"),
        ]

        for _ in range(50):
            action, resource_type, description = random.choice(actions)
            user = random.choice(users)
            risk = random.choice(risks)
            log = AuditLog(
                id=uuid.uuid4(),
                user_id=user.id,
                action=action,
                resource_type=resource_type,
                resource_id=risk.id,
                details={"description": description, "ip": f"10.0.{random.randint(1,254)}.{random.randint(1,254)}"},
                ip_address=f"10.0.{random.randint(1,254)}.{random.randint(1,254)}",
                created_at=now - timedelta(days=random.randint(0, 30), hours=random.randint(0, 23)),
            )
            session.add(log)

        print("Created 50 audit log entries")

        session.commit()
        print("\nSeed complete. Database populated with URIP demo data.")
        if generated:
            print(f"  Login: ciso@example.com / {seed_password}")
            print("  (auto-generated — set URIP_SEED_PASSWORD env var to use a known value)")
        else:
            print("  Login: ciso@example.com / (password unchanged from URIP_SEED_PASSWORD)")


if __name__ == "__main__":
    seed_database()
