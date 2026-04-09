"""
URIP Vulnerability Simulator
Generates realistic synthetic vulnerabilities from all 9 sources.
Runs every 15 minutes, pushes 5-15 new vulns per cycle via the live API.

Usage:
  # One-time bulk seed (3000 vulns)
  python -m backend.simulator --bulk

  # Continuous mode (5-15 vulns every 15 min)
  python -m backend.simulator --continuous

  # Single batch (5-15 vulns, then exit)
  python -m backend.simulator --batch
"""
import argparse
import json
import logging
import random
import re
import time
from datetime import datetime, timezone

import httpx

logger = logging.getLogger(__name__)

# ─── CONFIG (reads from env vars for GitHub Actions, falls back to defaults) ───
import os
API_BASE = os.environ.get("URIP_API_BASE", "https://urip-backend-production.up.railway.app")
LOGIN_EMAIL = os.environ.get("URIP_LOGIN_EMAIL", "ciso@royalenfield.com")
LOGIN_PASSWORD = os.environ.get("URIP_LOGIN_PASSWORD", "Urip@2026")
INTERVAL_SECONDS = 900  # 15 minutes

# ─── REAL CVE DATABASE (100+ entries) ────────────────────────
REAL_CVES = {
    "crowdstrike": [
        ("CVE-2024-3400", "Palo Alto PAN-OS Command Injection", 10.0, "critical", "endpoint"),
        ("CVE-2023-44228", "Log4j Remote Code Execution (Log4Shell)", 10.0, "critical", "endpoint"),
        ("CVE-2024-21887", "Ivanti Connect Secure Auth Bypass", 9.1, "critical", "endpoint"),
        ("CVE-2023-46805", "Ivanti Policy Secure SSRF", 8.2, "high", "endpoint"),
        ("CVE-2024-1709", "ConnectWise ScreenConnect Auth Bypass", 10.0, "critical", "endpoint"),
        ("CVE-2023-36884", "Microsoft Office HTML RCE", 8.3, "high", "endpoint"),
        ("CVE-2024-27198", "JetBrains TeamCity Auth Bypass", 9.8, "critical", "endpoint"),
        ("CVE-2023-38831", "WinRAR Code Execution via ZIP", 7.8, "high", "endpoint"),
        ("CVE-2024-0012", "Palo Alto PAN-OS Privilege Escalation", 9.8, "critical", "endpoint"),
        ("CVE-2023-22515", "Atlassian Confluence Privilege Escalation", 9.8, "critical", "endpoint"),
        ("CVE-2024-38063", "Windows TCP/IP RCE (IPv6)", 9.8, "critical", "endpoint"),
        ("CVE-2023-35078", "Ivanti EPMM Auth Bypass", 9.8, "critical", "endpoint"),
        ("CVE-2024-6387", "OpenSSH RegreSSHion RCE", 8.1, "high", "endpoint"),
        ("CVE-2023-20198", "Cisco IOS XE Web UI Privilege Escalation", 10.0, "critical", "endpoint"),
        ("CVE-2024-47575", "FortiManager Missing Auth RCE", 9.8, "critical", "endpoint"),
        ("CVE-2023-42793", "JetBrains TeamCity RCE", 9.8, "critical", "endpoint"),
        ("CVE-2024-23113", "FortiOS Format String RCE", 9.8, "critical", "endpoint"),
        ("CVE-2023-27997", "FortiOS Heap Buffer Overflow", 9.8, "critical", "endpoint"),
        ("CVE-2024-21762", "FortiOS Out-of-Bound Write", 9.6, "critical", "endpoint"),
        ("CVE-2023-4966", "Citrix Bleed Session Hijack", 9.4, "critical", "endpoint"),
    ],
    "easm": [
        ("CVE-2024-34102", "Adobe Commerce XML Injection", 9.8, "critical", "application"),
        ("CVE-2023-50164", "Apache Struts Path Traversal RCE", 9.8, "critical", "application"),
        ("CVE-2024-4577", "PHP CGI Argument Injection", 9.8, "critical", "application"),
        ("CVE-2023-29357", "SharePoint Privilege Escalation", 9.8, "critical", "application"),
        ("EASM-EXP-001", "Subdomain Takeover on dealer-staging.royalenfield.com", 7.5, "high", "network"),
        ("EASM-EXP-002", "Exposed .env File on Staging Server", 8.6, "high", "application"),
        ("EASM-EXP-003", "Open MongoDB 27017 on Public IP", 9.1, "critical", "network"),
        ("EASM-EXP-004", "Expired SSL Certificate on Parts Portal", 5.3, "medium", "network"),
        ("EASM-EXP-005", "DMARC Policy Not Enforced for royalenfield.com", 4.3, "medium", "network"),
        ("EASM-EXP-006", "Exposed Git Repository on Internal Wiki", 7.5, "high", "application"),
        ("EASM-EXP-007", "Open Elasticsearch 9200 on Analytics Server", 9.1, "critical", "network"),
        ("EASM-EXP-008", "WordPress xmlrpc.php Amplification", 5.3, "medium", "application"),
        ("EASM-EXP-009", "TLS 1.0 Enabled on Payment Gateway", 7.4, "high", "network"),
        ("EASM-EXP-010", "Open Redis 6379 Without Auth", 9.8, "critical", "network"),
    ],
    "cnapp": [
        ("CVE-2024-31497", "PuTTY ECDSA Key Recovery", 5.9, "medium", "cloud"),
        ("CNAPP-AWS-001", "S3 Bucket Without Encryption (re-warranty-docs)", 7.5, "high", "cloud"),
        ("CNAPP-AWS-002", "EC2 Instance with Public IP in Production VPC", 8.1, "high", "cloud"),
        ("CNAPP-AWS-003", "IAM Role with AdministratorAccess Attached", 9.0, "critical", "cloud"),
        ("CNAPP-AWS-004", "CloudTrail Logging Disabled in ap-south-1", 7.2, "high", "cloud"),
        ("CNAPP-AWS-005", "RDS PostgreSQL Publicly Accessible", 8.6, "high", "cloud"),
        ("CNAPP-AWS-006", "EBS Volume Not Encrypted (vol-0a1b2c3d)", 6.5, "medium", "cloud"),
        ("CNAPP-AWS-007", "Lambda with Wildcard Resource Permissions", 7.5, "high", "cloud"),
        ("CNAPP-AWS-008", "Root Account Used for Console Login", 9.8, "critical", "cloud"),
        ("CNAPP-AWS-009", "VPC Flow Logs Disabled in Prod VPC", 5.3, "medium", "cloud"),
        ("CNAPP-AWS-010", "Security Group Allows SSH from 0.0.0.0/0", 8.1, "high", "cloud"),
        ("CNAPP-GCP-001", "GCS Bucket with Public Read (analytics-export)", 7.5, "high", "cloud"),
        ("CNAPP-AZ-001", "Azure Storage Account Without Private Endpoint", 6.5, "medium", "cloud"),
    ],
    "armis": [
        ("CVE-2023-3595", "Rockwell Automation CIP RCE", 9.8, "critical", "ot"),
        ("CVE-2022-29303", "SolarView Compact Command Injection", 9.8, "critical", "ot"),
        ("CVE-2023-1133", "Delta Electronics InfraSuite RCE", 9.8, "critical", "ot"),
        ("ARMIS-OT-001", "Unencrypted Modbus TCP on Assembly Line PLC", 8.2, "high", "ot"),
        ("ARMIS-OT-002", "Default Credentials on Paint Shop HMI", 9.8, "critical", "ot"),
        ("ARMIS-OT-003", "Unpatched Firmware on Welding Robot Controller", 8.6, "high", "ot"),
        ("ARMIS-OT-004", "OT Device Communicating to External IP", 9.0, "critical", "ot"),
        ("ARMIS-OT-005", "Legacy PLC with No Authentication (Allen-Bradley)", 8.5, "high", "ot"),
        ("ARMIS-OT-006", "SCADA System Running Windows XP Embedded", 9.8, "critical", "ot"),
        ("ARMIS-OT-007", "Unauthorized Device on OT VLAN (MAC Spoofing)", 7.5, "high", "ot"),
        ("ARMIS-OT-008", "Conveyor Belt Sensor with Telnet Enabled", 6.5, "medium", "ot"),
        ("ARMIS-OT-009", "RTU Firmware Downgrade Detected", 7.2, "high", "ot"),
        ("ARMIS-OT-010", "Engine Test Bench Controller Buffer Overflow", 8.8, "high", "ot"),
    ],
    "vapt": [
        ("CVE-2024-53677", "Apache Struts File Upload RCE", 9.5, "critical", "application"),
        ("VAPT-RE-001", "SQL Injection in Dealer Portal Search API", 9.8, "critical", "application"),
        ("VAPT-RE-002", "Stored XSS in Product Review Section", 6.1, "medium", "application"),
        ("VAPT-RE-003", "IDOR in Order History API (/api/orders/{id})", 7.5, "high", "application"),
        ("VAPT-RE-004", "Broken Authentication on Password Reset Flow", 8.1, "high", "application"),
        ("VAPT-RE-005", "SSRF via Image Upload in CMS", 8.6, "high", "application"),
        ("VAPT-RE-006", "XXE in SOAP Endpoint (Legacy ERP Bridge)", 7.5, "high", "application"),
        ("VAPT-RE-007", "Insecure Deserialization in Java Backend", 9.8, "critical", "application"),
        ("VAPT-RE-008", "Hardcoded API Key in JavaScript Bundle", 7.5, "high", "application"),
        ("VAPT-RE-009", "Missing Rate Limiting on Login Endpoint", 5.3, "medium", "application"),
        ("VAPT-RE-010", "JWT Not Invalidated After Logout", 6.5, "medium", "application"),
        ("VAPT-RE-011", "Open Redirect in OAuth Callback URL", 6.1, "medium", "application"),
        ("VAPT-RE-012", "Directory Traversal in File Download API", 7.5, "high", "application"),
        ("VAPT-RE-013", "CSRF on Profile Settings Update", 4.3, "medium", "application"),
        ("VAPT-RE-014", "Sensitive Data in Error Response (Stack Trace)", 5.3, "medium", "application"),
    ],
    "threat_intel": [
        ("CVE-2024-50623", "Cleo File Transfer Unrestricted Upload RCE", 9.8, "critical", "application"),
        ("CVE-2023-34362", "MOVEit Transfer SQL Injection", 9.8, "critical", "application"),
        ("TI-APT-001", "APT28 Targeting Indian Manufacturing Sector", 8.0, "high", "endpoint"),
        ("TI-APT-002", "Lazarus Group Supply Chain Campaign via npm", 9.0, "critical", "application"),
        ("TI-RANSOM-001", "LockBit 3.0 Indicators Found on Network Edge", 9.5, "critical", "endpoint"),
        ("TI-RANSOM-002", "BlackCat/ALPHV Ransomware C2 Communication", 9.0, "critical", "network"),
        ("TI-LEAK-001", "Dark Web Credential Dump Contains RE Domain Emails", 8.0, "high", "identity"),
        ("TI-LEAK-002", "Employee Credentials on Paste Site (15 accounts)", 8.5, "high", "identity"),
        ("TI-EXPLOIT-001", "Active Exploitation of SAP NetWeaver CVE-2025-0282", 9.8, "critical", "application"),
        ("TI-BOTNET-001", "Mirai Variant Scanning RE IP Range", 6.5, "medium", "network"),
    ],
    "cert_in": [
        ("CIVN-2026-0142", "Multiple Vulnerabilities in Google Chrome Desktop", 8.8, "high", "endpoint"),
        ("CIVN-2026-0138", "Critical RCE in Apache Tomcat", 9.8, "critical", "application"),
        ("CIVN-2026-0135", "Microsoft Patch Tuesday April 2026 — 12 Critical", 9.0, "critical", "endpoint"),
        ("CIVN-2026-0131", "Oracle Java SE Critical Patch Update", 7.5, "high", "application"),
        ("CIVN-2026-0128", "VMware vCenter Server Authentication Bypass", 9.8, "critical", "cloud"),
        ("CIVN-2026-0124", "Cisco IOS XE Web UI Command Injection", 9.8, "critical", "network"),
        ("CIVN-2026-0119", "Linux Kernel Privilege Escalation (nf_tables)", 7.8, "high", "endpoint"),
        ("CIVN-2026-0115", "Fortinet FortiOS SSL VPN Pre-Auth RCE", 9.8, "critical", "network"),
        ("CIVN-2026-0110", "WordPress Plugin Vulnerability (WooCommerce)", 6.5, "medium", "application"),
        ("CIVN-2026-0105", "OpenSSL Certificate Verification Bypass", 7.4, "high", "network"),
    ],
    "bug_bounty": [
        ("BB-RE-001", "Account Takeover via SMS OTP Bypass on Mobile App", 9.1, "critical", "application"),
        ("BB-RE-002", "IDOR Exposes Other Dealers' Sales Data", 8.1, "high", "application"),
        ("BB-RE-003", "Stored XSS in Dealer Community Forum", 6.1, "medium", "application"),
        ("BB-RE-004", "GraphQL Introspection Enabled on Production", 5.3, "medium", "application"),
        ("BB-RE-005", "Race Condition in Coupon Redemption API", 6.5, "medium", "application"),
        ("BB-RE-006", "API Key Leaked in Client-Side JavaScript", 7.5, "high", "application"),
        ("BB-RE-007", "Privilege Escalation from Dealer to Admin Role", 8.8, "high", "application"),
        ("BB-RE-008", "Mass Assignment on User Profile Update", 6.5, "medium", "application"),
        ("BB-RE-009", "Session Fixation on Login Flow", 7.5, "high", "application"),
        ("BB-RE-010", "Blind SSRF via Webhook URL Configuration", 7.5, "high", "application"),
    ],
    "soc": [
        ("SOC-INC-001", "Brute Force Attack on VPN Gateway (500+ attempts/min)", 7.5, "high", "network"),
        ("SOC-INC-002", "Lateral Movement Detected via PsExec (Domain Admin)", 9.0, "critical", "endpoint"),
        ("SOC-INC-003", "Data Exfiltration Alert — 2GB Upload to Mega.nz", 9.0, "critical", "endpoint"),
        ("SOC-INC-004", "Anomalous Login from Nigeria (VPN Account)", 7.8, "high", "identity"),
        ("SOC-INC-005", "DNS Tunneling Detected (iodine signatures)", 8.0, "high", "network"),
        ("SOC-INC-006", "Rogue DHCP Server on Production VLAN", 7.2, "high", "network"),
        ("SOC-INC-007", "After-Hours Admin Console Access (3 AM IST)", 6.5, "medium", "identity"),
        ("SOC-INC-008", "Failed Login Spike — 800 Attempts in 5 Minutes", 7.0, "high", "identity"),
        ("SOC-INC-009", "Unauthorized USB Device on Finance Workstation", 6.5, "medium", "endpoint"),
        ("SOC-INC-010", "Privilege Escalation Attempt via PrintNightmare", 8.8, "high", "endpoint"),
        ("SOC-INC-011", "C2 Beacon Communication to Known Bad IP", 9.5, "critical", "network"),
        ("SOC-INC-012", "Cobalt Strike Watermark Detected in Memory", 9.8, "critical", "endpoint"),
    ],
}

# Royal Enfield assets per domain
ASSETS = {
    "endpoint": [
        "Finance Workstation FIN-WS-01", "CISO Laptop EXEC-LT-01", "HR Desktop HR-WS-042",
        "Engineering Workstation ENG-WS-107", "Dealer Support Laptop DL-LT-15",
        "Chennai Plant Floor PC PF-CH-03", "Manesar Plant Terminal MN-TM-12",
        "QA Lab Machine QA-WS-05", "Marketing MacBook MKT-MB-22",
        "Server Room Console SRV-KVM-01", "CEO Laptop EXEC-LT-02",
        "Design Studio Mac DS-MC-08", "Showroom Kiosk SK-DEL-03",
        "Warehouse Scanner WH-SC-14", "Security Ops Workstation SOC-WS-01",
    ],
    "cloud": [
        "AWS EKS Cluster — Dealer Portal", "S3 Bucket re-customer-data-prod",
        "Azure AD Tenant royalenfield.com", "GCP BigQuery Analytics",
        "AWS Lambda — Order Processing", "CloudFront CDN royalenfield.com",
        "AWS RDS PostgreSQL — ERP", "Azure Blob — Warranty Docs",
        "AWS ECR Container Registry", "GCP Cloud Storage — Marketing Assets",
        "AWS Secrets Manager — Prod", "Azure AKS — Internal Tools",
    ],
    "network": [
        "Core Switch Chennai CS-CH-01", "Firewall FW-DMZ-01 Internet Edge",
        "VPN Gateway VPN-GW-PRIMARY", "Load Balancer LB-WEB-01",
        "DNS Server DNS-INT-01", "WiFi Controller WLC-MN-01",
        "MPLS Router RTR-MPLS-CH", "IDS Sensor IDS-DMZ-02",
        "Proxy Server PROXY-INT-01", "WAF Cloudflare Edge",
        "SD-WAN Controller SDWAN-01", "Network TAP TAP-CORE-01",
    ],
    "application": [
        "Dealer Portal api.dealers.royalenfield.com", "SAP ERP Production SAP-PRD-01",
        "Royal Enfield Mobile App v4.2", "E-Commerce shop.royalenfield.com",
        "Warranty Management System WMS-01", "Spare Parts API parts-api.re.internal",
        "HR Portal Workday Integration", "CRM Salesforce RE-CRM-PROD",
        "Internal Wiki Confluence", "CI/CD Jenkins jenkins.re.internal",
        "Customer Support Portal support.royalenfield.com",
        "Dealer Onboarding Portal onboard.royalenfield.com",
    ],
    "identity": [
        "Domain Admin Group DA-GROUP-01", "Service Account svc-sap-integration",
        "CyberArk PAM Vault VAULT-PROD-01", "Azure AD Privileged Roles",
        "LDAP Server LDAP-INT-01", "Duo MFA Gateway",
        "Service Account svc-dealer-sync", "Root AWS Account re-master-org",
        "Okta SSO Production", "API Gateway Service Keys",
    ],
    "ot": [
        "Chennai Plant HMI Controller HMI-CH-01", "Paint Shop PLC PLC-PAINT-03",
        "Assembly Line SCADA SCADA-ASSY-01", "Welding Robot Controller WRC-07",
        "Manesar Plant RTU RTU-MN-05", "Quality Inspection Camera QIC-04",
        "Conveyor Belt Sensor CBS-12", "Compressor Control Unit CCU-02",
        "Engine Test Bench ETB-CTRL-01", "Warehouse AGV Controller AGV-WH-03",
        "CNC Machine Controller CNC-CH-04", "Paint Booth Ventilation PBV-01",
    ],
}

DOMAIN_TEAM = {
    "endpoint": "Infra Team", "cloud": "Cloud Team", "network": "Network Team",
    "application": "App Team", "identity": "IAM Team", "ot": "OT Team",
}

# ─── EXPLOITABILITY HELPERS (imported from canonical services) ──

_CVE_PATTERN = re.compile(r"^CVE-\d{4}-\d{4,}$")

from backend.services.asset_criticality_service import classify_asset as _classify_asset_tier_fn
from backend.services.exploitability_service import compute_composite, derive_exploit_status


def _compute_composite(cvss: float, epss: float | None, in_kev: bool, severity: str, asset_name: str = "") -> float:
    """Delegate to the canonical compute_composite in exploitability_service."""
    return compute_composite(cvss, epss, in_kev, severity, asset_name=asset_name)


def _classify_asset_tier(asset_name: str) -> int:
    return _classify_asset_tier_fn(asset_name)


def _derive_exploit_status(epss: float | None, in_kev: bool) -> str:
    return derive_exploit_status(epss, in_kev)


def fetch_epss_batch_sync(cve_ids: list[str], client: httpx.Client) -> dict[str, float]:
    """Synchronous EPSS batch fetch. Returns {cve_id: epss_score}."""
    from backend.services.scoring_config import EPSS_API_URL
    valid_cves = [c for c in cve_ids if _CVE_PATTERN.match(c)]
    if not valid_cves:
        return {}
    result = {}
    for i in range(0, len(valid_cves), 100):
        batch = valid_cves[i:i + 100]
        try:
            resp = client.get(EPSS_API_URL, params={"cve": ",".join(batch)})
            resp.raise_for_status()
            for entry in resp.json().get("data", []):
                cve = entry.get("cve")
                epss = entry.get("epss")
                if cve and epss is not None:
                    result[cve] = float(epss)
        except Exception:
            logger.warning("EPSS batch fetch failed for batch starting at %d", i)
    return result


def fetch_kev_catalog_sync(client: httpx.Client) -> set[str]:
    """Synchronous KEV catalog fetch."""
    from backend.services.scoring_config import KEV_CATALOG_URL
    try:
        resp = client.get(KEV_CATALOG_URL)
        resp.raise_for_status()
        return {v.get("cveID") for v in resp.json().get("vulnerabilities", []) if v.get("cveID")}
    except Exception:
        logger.warning("KEV catalog fetch failed")
        return set()


def get_token(client: httpx.Client) -> str:
    resp = client.post(f"{API_BASE}/api/auth/login", json={
        "email": LOGIN_EMAIL, "password": LOGIN_PASSWORD,
    })
    resp.raise_for_status()
    return resp.json()["access_token"]


def generate_vulnerability() -> dict:
    source = random.choice(list(REAL_CVES.keys()))
    cve_id, finding, cvss, severity, domain = random.choice(REAL_CVES[source])
    asset = random.choice(ASSETS[domain])
    owner = DOMAIN_TEAM[domain]

    return {
        "finding": finding,
        "description": f"[{cve_id}] {finding}. Detected by {source} connector. Asset: {asset}. Requires immediate triage.",
        "source": source,
        "domain": domain,
        "cvss_score": cvss,  # CVSS is a published standard score per CVE — no random variance
        "severity": severity,
        "asset": asset,
        "owner_team": owner,
        "cve_id": cve_id if not cve_id.startswith(("EASM-", "CNAPP-", "ARMIS-", "VAPT-", "TI-", "BB-", "SOC-")) else None,
    }


def push_vulnerabilities(count: int, token: str, client: httpx.Client) -> int:
    headers = {"Authorization": f"Bearer {token}"}

    # Pre-generate all vulns so we can batch-fetch EPSS
    vulns = [generate_vulnerability() for _ in range(count)]

    # Collect all real CVE IDs for EPSS batch fetch
    cve_ids = [v["cve_id"] for v in vulns if v.get("cve_id") and _CVE_PATTERN.match(v["cve_id"])]
    epss_data = fetch_epss_batch_sync(cve_ids, client) if cve_ids else {}

    # Fetch KEV catalog
    kev_set = fetch_kev_catalog_sync(client)

    # Enrich each vuln with exploitability fields
    for vuln in vulns:
        cve_id = vuln.get("cve_id")
        epss_score = None
        in_kev = False

        if cve_id and _CVE_PATTERN.match(cve_id):
            epss_score = epss_data.get(cve_id)
            in_kev = cve_id in kev_set

        vuln["epss_score"] = epss_score
        vuln["in_kev_catalog"] = in_kev
        vuln["exploit_status"] = _derive_exploit_status(epss_score, in_kev)
        vuln["asset_tier"] = _classify_asset_tier(vuln["asset"])
        vuln["composite_score"] = _compute_composite(
            vuln["cvss_score"], epss_score, in_kev, vuln["severity"], vuln["asset"]
        )

    success = 0
    for i, vuln in enumerate(vulns):
        resp = client.post(f"{API_BASE}/api/risks", json=vuln, headers=headers)
        if resp.status_code in (200, 201):
            risk_id = resp.json().get("risk_id", "?")
            exploit = vuln.get("exploit_status", "none")
            composite = vuln.get("composite_score", 0)
            print(f"  [{i+1}/{count}] {risk_id} | {vuln['severity'].upper():8s} | {vuln['source']:12s} | {exploit:11s} | C={composite:4.1f} | {vuln['finding'][:50]}")
            success += 1
        else:
            print(f"  [{i+1}/{count}] FAILED: {resp.status_code} — {resp.text[:100]}")
    return success


def run_bulk(count: int = 3000):
    print(f"\n{'='*70}")
    print(f"URIP VULNERABILITY SIMULATOR — BULK MODE ({count} vulns)")
    print(f"{'='*70}")
    print(f"Target: {API_BASE}")
    print(f"Time:   {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}\n")

    with httpx.Client(timeout=30) as client:
        token = get_token(client)
        print(f"Authenticated as {LOGIN_EMAIL}\n")

        batch_size = 50
        total_success = 0
        for batch in range(0, count, batch_size):
            batch_count = min(batch_size, count - batch)
            print(f"\n--- Batch {batch // batch_size + 1} ({batch+1}-{batch+batch_count}) ---")
            total_success += push_vulnerabilities(batch_count, token, client)

        print(f"\n{'='*70}")
        print(f"BULK COMPLETE: {total_success}/{count} vulnerabilities created")
        print(f"{'='*70}\n")


def run_batch():
    count = random.randint(5, 15)
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    print(f"\n[{now}] Generating {count} new vulnerabilities...")

    with httpx.Client(timeout=30) as client:
        token = get_token(client)
        success = push_vulnerabilities(count, token, client)
        print(f"[{now}] Done: {success}/{count} created\n")


def run_continuous():
    print(f"\n{'='*70}")
    print(f"URIP VULNERABILITY SIMULATOR — CONTINUOUS MODE")
    print(f"Interval: {INTERVAL_SECONDS}s ({INTERVAL_SECONDS // 60} minutes)")
    print(f"Target:   {API_BASE}")
    print(f"{'='*70}\n")

    cycle = 0
    while True:
        cycle += 1
        print(f"--- Cycle {cycle} ---")
        run_batch()
        print(f"Sleeping {INTERVAL_SECONDS}s until next cycle...\n")
        time.sleep(INTERVAL_SECONDS)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="URIP Vulnerability Simulator")
    parser.add_argument("--bulk", action="store_true", help="Generate 3000 vulns in one go")
    parser.add_argument("--bulk-count", type=int, default=3000, help="Number of vulns for bulk mode")
    parser.add_argument("--batch", action="store_true", help="Generate 5-15 vulns and exit")
    parser.add_argument("--continuous", action="store_true", help="Run every 15 min indefinitely")
    parser.add_argument("--api", type=str, default=API_BASE, help="API base URL override")
    args = parser.parse_args()

    if args.api:
        API_BASE = args.api

    if args.bulk:
        run_bulk(args.bulk_count)
    elif args.continuous:
        run_continuous()
    elif args.batch:
        run_batch()
    else:
        parser.print_help()
