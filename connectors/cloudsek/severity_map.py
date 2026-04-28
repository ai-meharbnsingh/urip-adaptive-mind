"""
Explicit CloudSEK alert_type → URIP severity mapping.

Each mapping includes a comment explaining the security rationale.
This is the single source of truth for severity normalization.
"""

from __future__ import annotations

# CloudSEK alert_type (string) → URIP severity (critical | high | medium | low)
CLOUDSEK_ALERT_TYPE_TO_URIP_SEVERITY: dict[str, str] = {
    # ── XVigil (dark web / external threat intelligence) ──────────────────────
    # Leaked credentials are an immediate breach vector — password rotation,
    # session invalidation, and MFA re-enrollment must happen now.
    "leaked_credentials": "critical",
    # Active brand abuse / phishing sites are live attacks harvesting
    # employee or customer credentials. Takedown is urgent.
    "brand_abuse": "high",
    # Active phishing site specifically targeting the organization.
    # Same urgency as brand abuse — users are actively being deceived.
    "phishing_site": "high",
    # Fake mobile apps impersonating the brand can steal credentials
    # and install malware on user devices.
    "fake_app": "high",
    # Dark web mention without credential exposure is intel worth
    # tracking but does not require immediate incident response.
    "dark_web_mention": "medium",
    # ── BeVigil (mobile + web attack surface) ─────────────────────────────────
    # Hardcoded API keys or secrets in shipped mobile app binaries
    # are trivial to extract and abuse — immediate key rotation required.
    "hardcoded_secret": "critical",
    # Exposed S3 buckets can leak customer data, source code, or
    # backups. Unauthorized access is likely.
    "exposed_s3_bucket": "high",
    # Unauthenticated API or admin endpoints bypass identity controls
    # and may expose sensitive operations.
    "unauth_endpoint": "high",
    # Publicly exposed API without authentication is a direct data-loss
    # or manipulation vector.
    "exposed_api": "high",
    # ── SVigil (supply chain risk) ────────────────────────────────────────────
    # A critical CVE in a supply-chain vendor means the vendor's
    # vulnerability may cascade into the customer environment.
    "vendor_critical_cve": "high",
    # Expired SOC2 / ISO certification is a compliance and governance
    # gap. It does not imply active exploitation but weakens assurance.
    "vendor_cert_expired": "medium",
}
