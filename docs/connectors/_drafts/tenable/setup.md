# Connector Setup: Tenable Vulnerability Manager

## Quick Facts
- **Category:** VM (Vulnerability Management)
- **Module:** VM
- **Status:** LIVE
- **Setup difficulty:** Easy (~10 min)
- **Vendor docs:** https://developer.tenable.com/reference/navigate
- **Updates:** Polled every 15 min · No real-time webhooks (Tenable.io API does not push)

## What This Pulls
- CVE inventory for every scanned asset
- CVSS v2/v3 base score
- EPSS score (exploit-prediction)
- VPR (Tenable Vulnerability Priority Rating)
- Exploit availability flag (in-the-wild, exploit DB)
- Patch publication date / vulnerability age
- Plugin family + Tenable plugin ID
- Asset hostname, FQDN, IPv4/IPv6, MAC, OS

## Prerequisites
- **License tier:** Tenable Vulnerability Management (cloud / Tenable.io). Tenable Nessus Professional **does not** ship API keys — you need Tenable.io.
- **Admin role:** Standard or Administrator user. Read-only roles cannot generate API keys.
- **Network allowlist:** Allow URIP backend egress to `cloud.tenable.com` (or your regional pod, e.g. `eu-central.cloud.tenable.com`). HTTPS/443.
- **Browser:** Modern browser to access the Tenable.io console.

## Step-by-Step Setup
1. Log in to Tenable Vulnerability Management as admin: https://cloud.tenable.com
2. Click your profile icon (top-right) and choose **My Account**.
3. Open the **API Keys** tab.
4. Click **Generate** and confirm the warning ("This will replace any existing keys").
5. Copy both values that appear:
   - **Access Key** (~64 alphanumeric characters)
   - **Secret Key** (~64 alphanumeric characters)
6. **WARNING:** the Secret Key is shown ONCE. Tenable cannot retrieve it later — save it now to your password manager.
7. In URIP: **Tool Catalog** → click the **Tenable Vulnerability Manager** tile.
8. Paste the Access Key and Secret Key into the wizard.
9. Leave **API Endpoint** as `https://cloud.tenable.com` unless you are on a regional pod.
10. Optional: set **Max requests / hour** if your tenant has tightened rate limits below the default 1000/hr.
11. Click **Test Connection**. URIP performs `GET /workbenches/assets` and verifies a 200 response.
12. Save. The first sync runs immediately and may take 5–30 min for tenants with >10K assets.

`[screenshot: tenable-api-keys-page.png]`
`[screenshot: tenable-generate-button.png]`

## Required API Scopes / Permissions
Tenable.io uses **role-based** API scopes, not OAuth. The user that owns the API keys must have at least:
- **Standard** role — read access to: Assets, Vulnerabilities, Workbenches, Scans (read).
- Recommended: **Scan Manager** role if URIP should also read scan-history details.

NOT required: Administrator, Scan Operator (write), or Tag-Manager. URIP never modifies Tenable data.

## What URIP Receives (Sample Data)
```json
{
  "id": "tenable-finding-c2b9-1893",
  "source": "tenable",
  "domain": "endpoint",
  "finding": "CVE-2024-21413 — Microsoft Outlook Information Disclosure",
  "asset": "WIN-LAPTOP-00347 (10.20.34.58)",
  "owner_team": "endpoint-ops",
  "cvss_score": 9.8,
  "severity": "critical",
  "cve_id": "CVE-2024-21413",
  "epss_score": 0.96,
  "in_kev_catalog": true,
  "exploit_status": "weaponized",
  "asset_tier": 2,
  "description": "Microsoft Outlook Elevation of Privilege Vulnerability — patch available 2024-02-13.",
  "raw_data": {
    "plugin_id": 192987,
    "plugin_family": "Windows : Microsoft Bulletins",
    "vpr_score": 9.4,
    "first_found": "2024-02-15T08:21:00Z"
  }
}
```

## What URIP Does NOT Receive
- Plain-text credentials stored inside Tenable scan policies
- Scan-policy XML / .nessus exports
- Asset owner names or other PII outside hostname/IP
- Scan schedule details or scanner availability data

## Common Errors & Fixes

### Error: 401 Unauthorized on Test Connection
**Cause:** API keys revoked, tenant password reset (which auto-rotates keys), or wrong tier (Nessus Pro keys do not work).
**Fix:** Tenable.io → My Account → API Keys → **Generate** new pair. Update both values in URIP.

### Error: 403 Forbidden
**Cause:** API user role downgraded to "Basic" / "Disabled" or workspace permissions revoked.
**Fix:** Tenable.io → Settings → Access Control → Users → confirm role is **Standard** or higher and `Enabled` toggle is on.

### Error: 429 Too Many Requests
**Cause:** Tenable rate-limits at 1000 req/hr per workspace. Multiple connectors sharing keys can collide.
**Fix:** Set **Max requests / hour** in the URIP wizard to 80 % of your tenant's limit, or generate a dedicated API user for URIP.

### Error: SSL certificate verify failed (only on self-hosted Tenable.sc)
**Cause:** Tenable Security Center (sc) on-prem with private CA.
**Fix:** Tenable.sc is *not* officially supported by this connector — use Tenable.io. If you must, contact URIP support to add your CA bundle.

## Polling & Refresh
- Default poll cycle: every **15 minutes** (incremental — only assets/vulns updated since last poll).
- First sync: full pull. Allow 5–30 min for >10K assets.
- Webhook ingestion: **No** (Tenable.io has no outbound webhooks).
- Manual refresh: Tool Catalog → Tenable tile → **Run Now** (admin only).

## Disconnecting
1. Tool Catalog → Tenable tile → **Disable**.
2. Credentials are erased from the Fernet-encrypted vault.
3. Existing risks remain in URIP for historical reporting.
4. Optional: Tenable.io → My Account → API Keys → **Generate** to invalidate the keys URIP held.

## Useful References
- Tenable Developer Portal: https://developer.tenable.com/reference/navigate
- Tenable.io API Keys: https://docs.tenable.com/vulnerability-management/Content/Settings/my-account/GenerateAPIKey.htm
- Tenable rate limits: https://developer.tenable.com/docs/rate-limiting
- URIP connector source: `connectors/tenable/`
