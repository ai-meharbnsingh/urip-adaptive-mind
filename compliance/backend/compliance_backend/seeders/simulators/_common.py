"""
seeders/simulators/_common.py — shared fixtures for all simulators.

Realistic identity / asset / employee / vendor pools used to populate
synthetic compliance data. Industry context: IT services consultancy
(matches connectors/extended_simulator.py).
"""
from __future__ import annotations

import hashlib
import random
import string
import uuid
from datetime import datetime, timezone
from typing import Optional


# ─────────────────────────────────────────────────────────────────────────────
# Deterministic RNG — simulators MUST take a Random instance, not the global one
# ─────────────────────────────────────────────────────────────────────────────


def make_rng(seed: int = 42) -> random.Random:
    """Return a deterministic Random instance.

    Default seed 42 means re-running the simulator twice with default args
    produces byte-identical output (subject to UUID generation, which is
    also seeded via uuid_for() below).
    """
    return random.Random(seed)


def uuid_for(rng: random.Random, *parts: str) -> str:
    """
    Deterministic UUID derived from rng + arbitrary key parts.

    Using sha256(seed + parts) ensures the same simulator run always produces
    the same UUIDs for the same logical key — making idempotency simple
    (re-runs hit the same primary keys).
    """
    seed_int = rng.randint(0, 2**32 - 1)
    h = hashlib.sha256(f"{seed_int}::{'|'.join(parts)}".encode()).hexdigest()
    return str(uuid.UUID(h[:32]))


def stable_uuid(*parts: str) -> str:
    """
    Stable UUID derived from sha256(parts) — does NOT depend on rng.

    Used when we need the same key across simulator runs regardless of
    seed (e.g. tenant-scoped employee #5 should have the same user_id every
    run so policy acks can be tied to the same person).
    """
    h = hashlib.sha256("|".join(parts).encode()).hexdigest()
    return str(uuid.UUID(h[:32]))


# ─────────────────────────────────────────────────────────────────────────────
# Employee pool (realistic IT-services consultancy headcount)
# ─────────────────────────────────────────────────────────────────────────────

EMPLOYEE_FIRST_NAMES = [
    "Aarav", "Priya", "Rohan", "Ananya", "Vikram", "Meera", "Karan", "Divya",
    "Rajesh", "Sneha", "Arjun", "Pooja", "Nikhil", "Riya", "Sandeep", "Kavya",
    "Manish", "Shreya", "Aditya", "Nisha", "Suresh", "Kavita", "Ramesh", "Anjali",
    "Vivek", "Neha", "Anil", "Priyanka", "Deepak", "Sunita", "Rahul", "Pallavi",
    "Amit", "Swati", "Ravi", "Lakshmi", "Gaurav", "Madhuri", "Naveen", "Geetha",
    "Pradeep", "Sangeeta", "Mukesh", "Vandana", "Sachin", "Rashmi", "Tarun", "Bhavna",
    "Sanjay", "Asha",
]

EMPLOYEE_LAST_NAMES = [
    "Sharma", "Verma", "Iyer", "Reddy", "Nair", "Patel", "Singh", "Kumar",
    "Gupta", "Mehta", "Joshi", "Agarwal", "Rao", "Krishnan", "Bose", "Choudhary",
    "Banerjee", "Pillai", "Shetty", "Desai", "Khan", "Pandey", "Mishra", "Saxena",
    "Bhat", "Menon", "Naidu", "Shah", "Trivedi", "Kapoor",
]

EMPLOYEE_DEPARTMENTS = [
    ("Engineering", 0.30),
    ("Sales", 0.15),
    ("Customer Success", 0.12),
    ("Operations", 0.10),
    ("Finance", 0.06),
    ("HR", 0.05),
    ("Marketing", 0.07),
    ("Security", 0.04),
    ("IT", 0.06),
    ("Legal", 0.03),
    ("Executive", 0.02),
]

EMPLOYEE_DOMAIN = "adverb.in"


def generate_employees(
    rng: random.Random, tenant_slug: str, count: int = 50
) -> list[dict]:
    """
    Generate realistic employee records.

    Returns: list of {user_id, email, full_name, department, hire_date}
    Same tenant_slug + same RNG seed → same employees every run (idempotent).
    """
    out: list[dict] = []
    used_emails: set[str] = set()
    departments_weighted = []
    for d, w in EMPLOYEE_DEPARTMENTS:
        departments_weighted.extend([d] * int(w * 100))

    for i in range(count):
        first = EMPLOYEE_FIRST_NAMES[i % len(EMPLOYEE_FIRST_NAMES)]
        last = EMPLOYEE_LAST_NAMES[(i // len(EMPLOYEE_FIRST_NAMES) + i) % len(EMPLOYEE_LAST_NAMES)]
        # Stable email regardless of rng so policy_ack runs (potentially
        # different seed) still target the same person
        email = f"{first.lower()}.{last.lower()}{i:03d}@{EMPLOYEE_DOMAIN}"
        if email in used_emails:
            email = f"{first.lower()}.{last.lower()}{i:03d}.{rng.randint(1, 99)}@{EMPLOYEE_DOMAIN}"
        used_emails.add(email)

        user_id = stable_uuid(tenant_slug, "employee", str(i))
        dept = departments_weighted[i % len(departments_weighted)]
        out.append(
            {
                "user_id": user_id,
                "email": email,
                "full_name": f"{first} {last}",
                "department": dept,
                "hire_date_days_ago": rng.randint(30, 1500),
            }
        )
    return out


# ─────────────────────────────────────────────────────────────────────────────
# Vendor pool — realistic SaaS / services vendors a consultancy depends on
# ─────────────────────────────────────────────────────────────────────────────

VENDOR_CATALOG: list[dict] = [
    # (name, criticality, contact_email, profile)
    {"name": "Amazon Web Services", "criticality": "critical", "contact": "compliance@aws.amazon.com", "profile": "good"},
    {"name": "Microsoft Corporation", "criticality": "critical", "contact": "compliance@microsoft.com", "profile": "good"},
    {"name": "Atlassian", "criticality": "high", "contact": "trust@atlassian.com", "profile": "good"},
    {"name": "Salesforce.com Inc.", "criticality": "critical", "contact": "trust@salesforce.com", "profile": "good"},
    {"name": "Okta Inc.", "criticality": "critical", "contact": "trust@okta.com", "profile": "good"},
    {"name": "GitHub Inc.", "criticality": "high", "contact": "support@github.com", "profile": "good"},
    {"name": "Slack Technologies", "criticality": "high", "contact": "trust@slack.com", "profile": "good"},
    {"name": "Datadog Inc.", "criticality": "medium", "contact": "trust@datadoghq.com", "profile": "good"},
    {"name": "Twilio Inc.", "criticality": "medium", "contact": "trust@twilio.com", "profile": "good"},
    {"name": "Cloudflare Inc.", "criticality": "high", "contact": "trust@cloudflare.com", "profile": "good"},
    {"name": "Workday Inc.", "criticality": "high", "contact": "trust@workday.com", "profile": "good"},
    {"name": "Zoom Communications", "criticality": "medium", "contact": "trust@zoom.us", "profile": "good"},
    # concerning vendors — partial gaps
    {"name": "Zenith Helpdesk Pvt Ltd", "criticality": "medium", "contact": "support@zenithhelp.in", "profile": "concerning"},
    {"name": "QuickBooks Local Reseller", "criticality": "low", "contact": "ops@quickbooks-local.in", "profile": "concerning"},
    {"name": "PixelWave Design Studio", "criticality": "low", "contact": "hello@pixelwave.in", "profile": "concerning"},
    {"name": "Bharat Office Supplies", "criticality": "low", "contact": "sales@bharatoffice.in", "profile": "concerning"},
    {"name": "Sentinel Security Vendor", "criticality": "high", "contact": "info@sentinel-vendor.in", "profile": "concerning"},
    # delinquent vendors — non-responders
    {"name": "OldCorp Legacy Systems", "criticality": "low", "contact": "noreply@oldcorp.in", "profile": "delinquent"},
    {"name": "Phantom Cloud Services", "criticality": "medium", "contact": "billing@phantom-cloud.in", "profile": "delinquent"},
    {"name": "DefunctVendor Solutions", "criticality": "low", "contact": "info@defunct-vendor.in", "profile": "delinquent"},
]


# ─────────────────────────────────────────────────────────────────────────────
# Asset pool — realistic IT consultancy inventory
# ─────────────────────────────────────────────────────────────────────────────

LAPTOP_MODELS = [
    "Dell Latitude 5430", "Dell Latitude 7440", "Lenovo ThinkPad X1 Carbon Gen 11",
    "Lenovo ThinkPad T14s Gen 4", "MacBook Pro 14\" M3", "MacBook Air 13\" M2",
    "HP EliteBook 840 G10", "HP ProBook 450 G10",
]

SERVER_MODELS = [
    "Dell PowerEdge R750", "Dell PowerEdge R650", "HPE ProLiant DL380 Gen11",
    "HPE ProLiant DL360 Gen11", "Cisco UCS C240 M6",
]

NETWORK_DEVICE_MODELS = [
    "Cisco Catalyst 9300", "Cisco ASR 1001-X", "Palo Alto PA-3220",
    "Fortinet FortiGate 100F", "Juniper SRX340", "Aruba 6300M",
]

MOBILE_MODELS = [
    "Apple iPhone 15", "Apple iPhone 14", "Apple iPhone 13",
    "Samsung Galaxy S24", "Samsung Galaxy S23", "OnePlus 12",
]

CLOUD_WORKLOAD_PATTERNS = [
    "aws-eks-prod-portal", "aws-eks-prod-api", "aws-rds-postgres-crm",
    "aws-rds-postgres-billing", "aws-lambda-webhook-router",
    "aws-s3-deliverables-prod", "aws-s3-backups", "aws-s3-logs-prod",
    "azure-aks-internal-tools", "azure-blob-contracts",
    "azure-sql-hr-portal", "gcp-bq-analytics-warehouse",
]

SAAS_APPS = [
    "Microsoft 365 (Tenant adverb.in)", "Salesforce CRM Production",
    "Atlassian JIRA Cloud", "Atlassian Confluence Cloud",
    "Slack Workspace adverb-corp", "Zoom Workplace Pro",
    "Workday HR", "Okta Workforce Identity",
    "GitHub Enterprise Cloud", "Datadog APM",
]

OFFICE_LOCATIONS = [
    "Bengaluru HQ", "Pune Office", "Hyderabad Office",
    "Mumbai Office", "Delhi-NCR Office",
    "Remote (India)", "Remote (US East)", "Remote (UK)",
]


# ─────────────────────────────────────────────────────────────────────────────
# Incident scenario library — realistic, industry-appropriate
# ─────────────────────────────────────────────────────────────────────────────

INCIDENT_SCENARIOS: list[dict] = [
    {
        "category": "phishing",
        "severity": "high",
        "title": "Spear-phishing email targeting Finance team — payroll diversion attempt",
        "description": (
            "Three Finance department users received a tailored phishing email impersonating "
            "the CFO requesting urgent payroll account changes. Two users reported via the "
            "PhishAlarm button; one user clicked the link but did not enter credentials "
            "(Defender SmartScreen blocked the credential-harvesting page)."
        ),
        "affected_assets": ["O365 Mailbox: cfo@adverb.in", "ADV-FIN-WS-03", "ADV-FIN-LT-02"],
        "rca": (
            "Threat actor used display-name spoofing on a lookalike domain (adverb-corp.in) "
            "registered 4 days prior. SPF/DKIM/DMARC was relaxed (p=none) on adverb.in, "
            "allowing the spoofed mail past inbound filters."
        ),
        "lessons": (
            "Tighten DMARC to p=reject. Monitor newly-registered lookalike domains via "
            "DomainTools weekly digest. Add Finance team to high-risk distribution list "
            "with stricter ATP policy."
        ),
    },
    {
        "category": "ransomware",
        "severity": "critical",
        "title": "Lockbit 3.0 detection + encryption attempt on developer workstation",
        "description": (
            "SentinelOne behavioural engine detected ransomware encryption pattern on "
            "ADV-DEV-WS-04 at 02:14 IST. Process tree showed PowerShell → rundll32 → "
            "encrypted DLL load. Endpoint isolated within 47 seconds; encryption blocked "
            "before crossing the SMB share to the build server."
        ),
        "affected_assets": ["ADV-DEV-WS-04", "Build Server: ADV-CI-BUILD-01"],
        "rca": (
            "Initial access via developer downloading a malicious npm package "
            "(typosquat of a legitimate testing library). Package post-install script "
            "fetched the Lockbit loader from Cobalt Strike beacon C2."
        ),
        "lessons": (
            "Block direct npm registry — route through internal Verdaccio proxy with "
            "allowlisted packages. Add npm provenance verification to CI pipeline. "
            "Audit developer local-admin entitlements quarterly."
        ),
    },
    {
        "category": "data_loss",
        "severity": "high",
        "title": "Sensitive client deliverable uploaded to personal Dropbox account",
        "description": (
            "Netskope CASB blocked an attempted upload of a 47-page client deliverable "
            "(marked Confidential) to a personal Dropbox account from ADV-LAPTOP-07. "
            "User claims they intended to work from home and forgot the corporate VPN. "
            "Investigation confirmed no exfiltration occurred — block was effective."
        ),
        "affected_assets": ["ADV-LAPTOP-07", "Document: ClientX_StrategyDeck_v3.pdf"],
        "rca": (
            "User had legitimate business need (work-from-home) but did not follow "
            "approved process (corporate VPN + sanctioned cloud storage). No malicious "
            "intent identified."
        ),
        "lessons": (
            "Improve VPN onboarding UX — auto-launch on corporate device wake. "
            "Refresh quarterly DLP policy training with real-world scenarios. "
            "Issue policy reminder to all consultants."
        ),
    },
    {
        "category": "credential_compromise",
        "severity": "critical",
        "title": "Service account svc-billing-sync compromised via leaked GitHub token",
        "description": (
            "Cloudflare WAF flagged anomalous API calls to billing.adverb.in originating "
            "from an unusual ASN (Romania-hosted VPS). Traced to a GitHub personal access "
            "token committed to a public fork by a former contractor 11 months prior. "
            "Token had been used to deploy a developer test app that called billing APIs."
        ),
        "affected_assets": ["Service Account: svc-billing-sync", "billing.adverb.in API"],
        "rca": (
            "PAT was issued to a contractor for one-off integration work in 2024. "
            "Offboarding process did not revoke GitHub PATs (only revoked SSO access). "
            "PAT had no expiry and broad org-read scope."
        ),
        "lessons": (
            "Mandate 90-day expiry on all GitHub PATs. Add GitHub PAT revocation to "
            "offboarding checklist. Run GitGuardian secrets scan weekly across all "
            "public forks of internal repos. Rotate svc-billing-sync credentials."
        ),
    },
    {
        "category": "insider_threat",
        "severity": "medium",
        "title": "Departing consultant attempted bulk download from CRM",
        "description": (
            "Salesforce Event Monitoring flagged a CRM user downloading 2,847 customer "
            "records over 90 minutes — 8x the user's 90-day baseline. User had submitted "
            "resignation 3 days earlier with last day in 2 weeks. CRM admin disabled "
            "data export entitlement; conversation held with user."
        ),
        "affected_assets": ["Salesforce CRM Production", "User: ramesh.sharma015@adverb.in"],
        "rca": (
            "Standard sales-rep role permits bulk export — appropriate during normal "
            "tenure but elevated risk during notice period. No detective control existed "
            "for departing-employee activity spike."
        ),
        "lessons": (
            "Implement notice-period access reduction — automatic Salesforce profile "
            "downgrade triggered by Workday termination notice. Add SOC alert rule "
            "for >5x baseline activity by employees within 30 days of last day."
        ),
    },
    {
        "category": "misconfiguration",
        "severity": "high",
        "title": "S3 bucket adverb-marketing-assets briefly public-read",
        "description": (
            "AWS Config rule s3-bucket-public-read-prohibited triggered at 14:32 on a "
            "bucket holding 12,000 marketing PDFs (sales decks, brochures — non-confidential). "
            "Caused by Marketing intern enabling 'public' on a single object via console, "
            "which auto-promoted the bucket policy."
        ),
        "affected_assets": ["S3 Bucket: adverb-marketing-assets"],
        "rca": (
            "AWS console UX nudged user toward bucket-level public-read when she only "
            "intended object-level public-read for one file. IAM permitted the action "
            "(Marketing role had s3:PutBucketPolicy on this bucket)."
        ),
        "lessons": (
            "Apply S3 Block Public Access at account level for all non-public buckets. "
            "Restrict s3:PutBucketPolicy to platform-engineering role only. "
            "Add Marketing-specific runbook for sharing public assets via CloudFront."
        ),
    },
    {
        "category": "ddos",
        "severity": "medium",
        "title": "L7 DDoS against client portal — Cloudflare absorbed",
        "description": (
            "Cloudflare WAF logged 4.2M requests/minute against portal.adverb.in for "
            "23 minutes — typical L7 HTTP flood pattern with rotating UAs. Cloudflare "
            "rate-limit rule + bot-management absorbed the attack with no impact on "
            "legitimate users (P95 latency unchanged)."
        ),
        "affected_assets": ["portal.adverb.in", "Cloudflare Edge"],
        "rca": (
            "Suspected commodity booter service. No demand received, no targeted timing "
            "(off-peak Saturday)."
        ),
        "lessons": (
            "Verify rate-limit thresholds quarterly. Confirm Cloudflare 'Under Attack' "
            "mode runbook is documented. Add automated Sev-2 page to on-call when "
            ">1M req/min sustained > 5 min."
        ),
    },
    {
        "category": "third_party",
        "severity": "high",
        "title": "Vendor breach notification — Zenith Helpdesk database leak",
        "description": (
            "Zenith Helpdesk Pvt Ltd notified Adverb on 2026-04-08 of a database "
            "compromise affecting their support ticketing platform. Adverb had 47 "
            "open tickets containing internal contact information. No customer PII; "
            "no infrastructure credentials shared with vendor."
        ),
        "affected_assets": ["Vendor: Zenith Helpdesk", "Support tickets (47)"],
        "rca": (
            "Vendor disclosed root cause as exposed Elasticsearch instance in their "
            "staging environment. Vendor response was within their contractual 72-hour "
            "notification window."
        ),
        "lessons": (
            "Reassess Zenith Helpdesk vendor risk score. Require updated SOC 2 report "
            "before 2026 contract renewal. Adverb-side: do not put internal credentials "
            "in any external vendor tickets (already policy)."
        ),
    },
    {
        "category": "malware",
        "severity": "low",
        "title": "USB autorun malware blocked on Finance laptop",
        "description": (
            "SentinelOne blocked execution of Trojan:Win32/Wacatac.B!ml on ADV-FIN-LT-02 "
            "when a USB drive was inserted. User received the USB at an industry "
            "conference. No execution; quarantined on insertion."
        ),
        "affected_assets": ["ADV-FIN-LT-02", "USB device: SanDisk Cruzer 32GB"],
        "rca": (
            "Conference giveaway USB pre-loaded with malware (commodity, not targeted). "
            "EDR worked as designed; no further action required for incident itself."
        ),
        "lessons": (
            "Refresh annual security training segment on conference-giveaway USBs. "
            "Reinforce: report received USBs to IT for inspection, do not insert."
        ),
    },
    {
        "category": "physical",
        "severity": "medium",
        "title": "Tailgating incident — Bengaluru HQ Floor 3",
        "description": (
            "Reception logged an unbadged individual following an employee through the "
            "Floor 3 turnstile at 09:42. Security guard intercepted within 90 seconds. "
            "Individual was a delivery courier without valid escort — escorted to "
            "reception and badged in correctly."
        ),
        "affected_assets": ["Bengaluru HQ Floor 3"],
        "rca": (
            "Employee held door open out of politeness (cultural norm). No malicious "
            "intent from courier — process failure at reception (courier should have "
            "been escorted from lobby)."
        ),
        "lessons": (
            "All-hands reminder on no-tailgate policy. Reception SOP refresh — courier "
            "deliveries always escorted by reception staff. Consider mantrap on Floor 3 "
            "(executive floor)."
        ),
    },
]


# ─────────────────────────────────────────────────────────────────────────────
# Misc helpers
# ─────────────────────────────────────────────────────────────────────────────


def now_utc() -> datetime:
    """Return naive UTC datetime (matches model column types — most are DateTime sans tz)."""
    return datetime.utcnow()


def utc(year: int, month: int, day: int, hour: int = 0, minute: int = 0) -> datetime:
    """Construct a naive UTC datetime (column-compatible)."""
    return datetime(year, month, day, hour, minute)
