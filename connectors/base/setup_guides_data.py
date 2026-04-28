"""
connectors/base/setup_guides_data.py — All 27 SETUP_GUIDE specs in one place.

P33-Z3 (revised): the Tool Catalog renders the full setup walk-through
INLINE on every connector tile.  Each concrete connector class assigns
``SETUP_GUIDE = SETUP_GUIDES["<name>"]`` to wire the spec onto the class.

Why one module?
---------------
- 27 connectors × ~120 lines each of inline spec would balloon the connector
  source files, hurting readability of the actual auth/fetch logic.
- Co-locating the data here lets one engineer review consistency across all
  guides at once (same tone, same step-count budget, same error coverage).
- Each connector still owns its class-level ``SETUP_GUIDE`` attribute — the
  attribute just references a dict entry instead of an inline literal.

Research provenance
-------------------
Each guide was written from the vendor's *current* (April 2026) public
documentation.  Where vendor docs were gated, paid, or ambiguous, the guide
falls back to widely-quoted community references and is flagged in the
``references`` block so customers can verify the most volatile steps
(e.g. menu paths) themselves.
"""

from __future__ import annotations

from connectors.base.setup_guide import (
    ErrorFix,
    PollingSpec,
    PrereqItem,
    QuickFacts,
    ScopeItem,
    SetupGuideSpec,
    SetupStep,
)


# ─────────────────────────────────────────────────────────────────────────────
# Reusable phrases — keep tone consistent across guides
# ─────────────────────────────────────────────────────────────────────────────


_CRED_VAULT_DELETE = (
    "Credentials are securely deleted from URIP's Fernet-encrypted vault."
)
_KEEP_HISTORY = (
    "Existing risks remain in URIP's risk register for historical reporting."
)


# ─────────────────────────────────────────────────────────────────────────────
# 1. Tenable Vulnerability Manager
# ─────────────────────────────────────────────────────────────────────────────


_TENABLE = SetupGuideSpec(
    quick_facts=QuickFacts(
        category="VM",
        module="VM",
        difficulty="easy",
        approx_setup_minutes=10,
        vendor_docs_url="https://developer.tenable.com/reference/navigate",
        polling_default_minutes=15,
        supports_webhooks=False,
        license_tier_required="Tenable Vulnerability Management (Tenable.io). Nessus Professional does NOT issue API keys.",
    ),
    what_pulled=[
        "CVE inventory per scanned asset (plugin output)",
        "CVSS v2 / v3 base scores",
        "EPSS exploit-prediction score (where Tenable enriches)",
        "VPR (Tenable Vulnerability Priority Rating)",
        "Asset inventory: hostname, FQDN, IPv4/IPv6, MAC, OS",
        "Plugin family + Tenable plugin ID (for cross-referencing)",
        "First-seen / last-seen / patch-available date",
    ],
    prerequisites=[
        PrereqItem(
            label="License tier",
            requirement=(
                "Tenable Vulnerability Management (cloud / Tenable.io). "
                "Nessus Professional does not ship API keys."
            ),
        ),
        PrereqItem(
            label="Admin role",
            requirement=(
                "Tenable.io user with Standard role or higher (read access to "
                "Assets + Workbenches). Read-only ‘Basic’ users cannot generate keys."
            ),
        ),
        PrereqItem(
            label="Network",
            requirement=(
                "Allow URIP egress to https://cloud.tenable.com (or your regional pod, "
                "e.g. eu-central.cloud.tenable.com) on TCP 443."
            ),
        ),
        PrereqItem(
            label="Browser",
            requirement="Modern browser to access the Tenable.io console for key generation.",
        ),
    ],
    steps=[
        SetupStep(
            n=1,
            title="Sign in to Tenable.io",
            body="Open https://cloud.tenable.com and log in as a Standard or Admin user.",
        ),
        SetupStep(
            n=2,
            title="Open My Account",
            body="Click your profile icon (top-right corner) → choose **My Account**.",
        ),
        SetupStep(
            n=3,
            title="Generate API keys",
            body=(
                "Open the **API Keys** tab → click **Generate** → confirm. "
                "Both Access Key and Secret Key appear in the dialog."
            ),
            warning=(
                "The Secret Key is shown ONCE. Copy it to your password vault NOW — "
                "Tenable cannot retrieve it later."
            ),
        ),
        SetupStep(
            n=4,
            title="Paste into URIP",
            body=(
                "URIP → Tool Catalog → click the Tenable tile → paste both keys. "
                "Leave **API Endpoint** at https://cloud.tenable.com unless you are on a regional pod."
            ),
        ),
        SetupStep(
            n=5,
            title="Test Connection",
            body=(
                "Click **Test Connection**. URIP calls GET /workbenches/assets and "
                "expects HTTP 200. On success, save the configuration."
            ),
        ),
    ],
    required_scopes=[
        ScopeItem(
            name="Standard role (or higher)",
            description="Read access to Assets, Vulnerabilities, Workbenches, Scans.",
            required=True,
        ),
        ScopeItem(
            name="Scan Manager role",
            description="Recommended if URIP should also surface scan-history details.",
            required=False,
        ),
    ],
    sample_data={
        "id": "tenable-finding-c2b9-1893",
        "source": "tenable",
        "domain": "endpoint",
        "finding": "CVE-2024-21413 — Microsoft Outlook Remote Code Execution",
        "asset": "WIN-LAPTOP-00347 (10.20.34.58)",
        "owner_team": "endpoint-ops",
        "cvss_score": 9.8,
        "severity": "critical",
        "cve_id": "CVE-2024-21413",
        "epss_score": 0.96,
        "in_kev_catalog": True,
        "exploit_status": "weaponized",
        "asset_tier": 2,
    },
    not_collected=[
        "Plain-text credentials embedded in scan policies",
        "Full .nessus scan-result XML exports",
        "Asset owner PII outside hostname / IP",
        "Scan schedule definitions or scanner availability",
    ],
    common_errors=[
        ErrorFix(
            error="401 Unauthorized on Test Connection",
            cause=(
                "API keys revoked, tenant password reset (auto-rotates keys), or "
                "Nessus Pro keys mistakenly used (unsupported)."
            ),
            fix=(
                "Tenable.io → My Account → API Keys → Generate a fresh pair. "
                "Update both values in URIP and retry."
            ),
        ),
        ErrorFix(
            error="403 Forbidden",
            cause="API user role downgraded to Basic / Disabled.",
            fix=(
                "Tenable.io → Settings → Access Control → Users → confirm the user is "
                "Enabled and has Standard role or higher."
            ),
        ),
        ErrorFix(
            error="429 Too Many Requests",
            cause="Tenable rate-limits at ~1500 req/hour per workspace; multiple integrations sharing keys collide.",
            fix=(
                "Lower **Max requests / hour** in the URIP wizard to 1000 (URIP's safe default leaves "
                "500 req headroom), or generate a dedicated API user for URIP."
            ),
        ),
        ErrorFix(
            error="SSL handshake failed",
            cause="Corporate egress proxy intercepting HTTPS to cloud.tenable.com.",
            fix=(
                "Allow-list cloud.tenable.com in your egress proxy with SSL passthrough. "
                "Tenable does not support TLS interception."
            ),
        ),
    ],
    polling=PollingSpec(
        default_minutes=15,
        first_sync_estimate_minutes=15,
        webhook_supported=False,
        manual_refresh="Tool Catalog → Tenable tile → Run Now (admin only).",
    ),
    disconnect_steps=[
        "Tool Catalog → Tenable tile → Disable.",
        _CRED_VAULT_DELETE,
        _KEEP_HISTORY,
        "Optionally rotate the API keys in Tenable.io to invalidate the values URIP held.",
    ],
    references=[
        "Tenable Developer Portal: https://developer.tenable.com/reference/navigate",
        "API key generation: https://docs.tenable.com/vulnerability-management/Content/Settings/my-account/GenerateAPIKey.htm",
        "Rate limits: https://developer.tenable.com/docs/rate-limiting",
    ],
)


# ─────────────────────────────────────────────────────────────────────────────
# 2. SentinelOne Singularity
# ─────────────────────────────────────────────────────────────────────────────


_SENTINELONE = SetupGuideSpec(
    quick_facts=QuickFacts(
        category="EDR",
        module="EDR",
        difficulty="easy",
        approx_setup_minutes=10,
        vendor_docs_url="https://usea1-partners.sentinelone.net/api-doc/overview",
        polling_default_minutes=15,
        supports_webhooks=False,
        license_tier_required="Singularity Core or higher (any tier with API access).",
    ),
    what_pulled=[
        "Threat detections (malware, exploit, lateral-movement)",
        "Endpoint agent health (online / offline / disabled)",
        "IoC matches against tenant threat-intel feeds",
        "Endpoint inventory: hostname, OS, agent version, last-seen",
        "Application inventory + outdated-app risk signals",
    ],
    prerequisites=[
        PrereqItem(
            label="License tier",
            requirement="SentinelOne Singularity Core / Control / Complete — all support REST API.",
        ),
        PrereqItem(
            label="Admin role",
            requirement="Console Admin or Site Admin — required to create a Service User.",
        ),
        PrereqItem(
            label="Network",
            requirement=(
                "Allow URIP egress to your console host "
                "(e.g. https://usea1-xxxx.sentinelone.net) on TCP 443."
            ),
        ),
    ],
    steps=[
        SetupStep(
            n=1,
            title="Identify your console URL",
            body=(
                "Log in to your SentinelOne console — copy the host portion of the URL "
                "(e.g. https://usea1-partners.sentinelone.net). This is your Console URL."
            ),
        ),
        SetupStep(
            n=2,
            title="Create a Service User",
            body=(
                "Settings → Users → **Service Users** → **Actions** → **Create New Service User**. "
                "Name it `urip-readonly`, set scope to your account / site, role = **Viewer**."
            ),
        ),
        SetupStep(
            n=3,
            title="Generate the API token",
            body=(
                "On the new Service User page click **Generate Token**. The token (JWT-style "
                "string starting with `eyJ…`) is shown ONCE."
            ),
            warning="The token cannot be retrieved later. Save it to your password vault now.",
        ),
        SetupStep(
            n=4,
            title="Paste into URIP",
            body=(
                "URIP → Tool Catalog → SentinelOne tile → paste **Console URL** and **API Token** → "
                "click **Test Connection** to verify."
            ),
        ),
    ],
    required_scopes=[
        ScopeItem(
            name="Viewer role",
            description="Read-only access to threats, endpoints, applications, activities.",
            required=True,
        ),
    ],
    sample_data={
        "id": "s1-threat-77a4-3120",
        "source": "sentinelone",
        "domain": "endpoint",
        "finding": "Mimikatz credential-dumping attempt blocked",
        "asset": "MAC-MARKETING-19 (192.168.10.42)",
        "owner_team": "endpoint-ops",
        "cvss_score": 8.5,
        "severity": "high",
        "exploit_status": "active",
        "asset_tier": 3,
    },
    not_collected=[
        "Process command-line arguments containing user credentials",
        "Full memory dumps captured during incident response",
        "User-typed clipboard content",
        "End-user names — only hostname and IP are stored",
    ],
    common_errors=[
        ErrorFix(
            error="401 Unauthorized — invalid or expired token",
            cause="Service User disabled or token rotated by another admin.",
            fix=(
                "Console → Settings → Service Users → confirm user is Active, then "
                "regenerate the token and update URIP."
            ),
        ),
        ErrorFix(
            error="403 Insufficient Privileges",
            cause="Service User role lower than Viewer (e.g. Custom-None).",
            fix=(
                "Edit the Service User → set role to Viewer at the right scope (Account or Site)."
            ),
        ),
        ErrorFix(
            error="429 / API rate limit exceeded",
            cause="SentinelOne enforces ~200 req/min per token by default.",
            fix=(
                "Set **Max requests / min** in the wizard to 150 to leave headroom; "
                "or contact SentinelOne support to lift the limit."
            ),
        ),
        ErrorFix(
            error="Connection refused / DNS failure",
            cause="Wrong Console URL — used the API host instead of the tenant subdomain.",
            fix=(
                "Use your tenant's console host (e.g. usea1-xxxx.sentinelone.net) — "
                "NOT api.sentinelone.net."
            ),
        ),
    ],
    polling=PollingSpec(
        default_minutes=15,
        first_sync_estimate_minutes=10,
        webhook_supported=False,
        manual_refresh="Tool Catalog → SentinelOne tile → Run Now.",
    ),
    disconnect_steps=[
        "Tool Catalog → SentinelOne tile → Disable.",
        _CRED_VAULT_DELETE,
        _KEEP_HISTORY,
        "Optionally disable the `urip-readonly` Service User in the SentinelOne console.",
    ],
    references=[
        "S1 API overview: https://usea1-partners.sentinelone.net/api-doc/overview",
        "Service User docs: https://www.sentinelone.com/blog/feature-spotlight-service-users-and-api-tokens/",
    ],
)


# ─────────────────────────────────────────────────────────────────────────────
# 3. Zscaler ZIA / ZTA / CASB
# ─────────────────────────────────────────────────────────────────────────────


_ZSCALER = SetupGuideSpec(
    quick_facts=QuickFacts(
        category="NETWORK",
        module="NETWORK",
        difficulty="medium",
        approx_setup_minutes=20,
        vendor_docs_url="https://help.zscaler.com/zia/api",
        polling_default_minutes=15,
        supports_webhooks=False,
        license_tier_required="ZIA / ZIA-CASB with API access enabled (any production tier).",
    ),
    what_pulled=[
        "Blocked URLs (web filter / URL category)",
        "Sandbox + advanced threat detections",
        "Shadow-SaaS application discovery",
        "Malicious download attempts",
        "DLP incidents (when CASB licensed)",
    ],
    prerequisites=[
        PrereqItem(
            label="License tier",
            requirement="ZIA Business or higher — Free/Bundle tiers do not expose the REST API.",
        ),
        PrereqItem(
            label="Admin role",
            requirement="Super Admin (or custom role with API + Reports read).",
        ),
        PrereqItem(
            label="Network",
            requirement=(
                "Allow URIP egress to your Zscaler cloud host "
                "(e.g. https://zsapi.zscalerthree.net) on TCP 443."
            ),
        ),
    ],
    steps=[
        SetupStep(
            n=1,
            title="Identify your cloud",
            body=(
                "Log in to your ZIA admin portal. The URL host (e.g. admin.zscalerthree.net) "
                "tells you the cloud — pick the matching value in the URIP wizard "
                "(zscaler, zscalertwo, zscalerthree, zscloud, …)."
            ),
        ),
        SetupStep(
            n=2,
            title="Generate the API key",
            body=(
                "Administration → **API Key Management** → click **Generate Key**. "
                "Copy the value — this is the `api_key` for the URIP wizard."
            ),
            warning="The API key replaces any existing one — coordinate with other integrations.",
        ),
        SetupStep(
            n=3,
            title="Use a dedicated API admin",
            body=(
                "Administration → Administrator Management → create a dedicated admin "
                "(`urip-api`) with role = **API & SSO Admin** (or a Read-Only Admin role). "
                "Set a strong password — URIP needs username + password for the OBFUSCATION login flow."
            ),
        ),
        SetupStep(
            n=4,
            title="Paste into URIP",
            body=(
                "URIP → Tool Catalog → Zscaler tile → fill **Cloud**, **Username**, **Password**, "
                "**API Key** → Test Connection."
            ),
        ),
    ],
    required_scopes=[
        ScopeItem(
            name="API Read access (Reports + URL Categories)",
            description="Required to pull blocked-URL events and sandbox detections.",
            required=True,
        ),
        ScopeItem(
            name="DLP Incidents read",
            description="Required only when the Zscaler CASB / DLP module is licensed.",
            required=False,
        ),
    ],
    sample_data={
        "id": "zia-event-92c1-4f30",
        "source": "zscaler",
        "domain": "network",
        "finding": "User attempted to download known-malicious file (sandbox verdict: malicious)",
        "asset": "user@example.com / 10.0.7.42",
        "owner_team": "security-ops",
        "cvss_score": 7.5,
        "severity": "high",
        "exploit_status": "active",
    },
    not_collected=[
        "Full URL query strings (PII risk) — only domain + path category",
        "Plain-text content of POST bodies",
        "User credentials seen on intercepted forms",
    ],
    common_errors=[
        ErrorFix(
            error="OBFUSCATED_API_KEY exception / 401 on /authenticatedSession",
            cause="API key expired or rotated. Zscaler API keys are time-bound by an obfuscation algorithm.",
            fix=(
                "Re-generate the API key in Administration → API Key Management; "
                "URIP automatically obfuscates the key on every call."
            ),
        ),
        ErrorFix(
            error="403 Forbidden — User does not have API access",
            cause="Admin role lacks the API + SSO permission set.",
            fix=(
                "Administration → Administrator Management → edit the admin → assign "
                "**API & SSO Admin** or a custom role with `API Access` enabled."
            ),
        ),
        ErrorFix(
            error="429 SESSION_LIMIT_EXCEEDED",
            cause="Concurrent sessions per admin user are limited (default 5).",
            fix=(
                "Lower polling frequency in URIP, or increase the session limit at "
                "Administration → Advanced Settings → Sessions."
            ),
        ),
        ErrorFix(
            error="Wrong cloud — connection works but no data",
            cause="Selected `zscaler` cloud while the tenant lives on `zscalerthree`.",
            fix="Confirm cloud from your admin portal URL host and update the wizard dropdown.",
        ),
    ],
    polling=PollingSpec(
        default_minutes=15,
        first_sync_estimate_minutes=15,
        webhook_supported=False,
        manual_refresh="Tool Catalog → Zscaler tile → Run Now.",
    ),
    disconnect_steps=[
        "Tool Catalog → Zscaler tile → Disable.",
        _CRED_VAULT_DELETE,
        _KEEP_HISTORY,
        "Optionally rotate the API key + delete the `urip-api` admin in Zscaler.",
    ],
    references=[
        "Zscaler ZIA API: https://help.zscaler.com/zia/api",
        "Zscaler authentication flow: https://help.zscaler.com/zia/api-authentication",
    ],
)


# ─────────────────────────────────────────────────────────────────────────────
# 4. Netskope CASB + DLP
# ─────────────────────────────────────────────────────────────────────────────


_NETSKOPE = SetupGuideSpec(
    quick_facts=QuickFacts(
        category="DLP",
        module="DLP",
        difficulty="medium",
        approx_setup_minutes=20,
        vendor_docs_url="https://docs.netskope.com/en/rest-api-v2-overview-312207.html",
        polling_default_minutes=15,
        supports_webhooks=False,
        license_tier_required="Netskope SASE platform with REST API v2 enabled (any production tier).",
    ),
    what_pulled=[
        "DLP incidents (file/email/web exfiltration)",
        "Cloud threats (malware, anomalous activity)",
        "User & app risk anomalies",
        "Shadow-IT (unsanctioned cloud app usage)",
        "CASB policy violations across IaaS/SaaS",
    ],
    prerequisites=[
        PrereqItem(
            label="License tier",
            requirement="Any Netskope SASE production tier — REST API v2 is included.",
        ),
        PrereqItem(
            label="Admin role",
            requirement="Tenant Admin (required to create a REST API token).",
        ),
        PrereqItem(
            label="Network",
            requirement=(
                "Allow URIP egress to your tenant URL "
                "(e.g. https://tenant.goskope.com) on TCP 443."
            ),
        ),
    ],
    steps=[
        SetupStep(
            n=1,
            title="Open the REST API v2 page",
            body=(
                "Log in to your Netskope tenant → Settings → Tools → **REST API v2**."
            ),
        ),
        SetupStep(
            n=2,
            title="Generate token",
            body=(
                "Click **New Token** → name it `urip-readonly` → set Scope to **Read-only** "
                "for /events/, /alerts/, /dlp/incidents → click **Generate**."
            ),
            warning=(
                "The token is shown ONCE. Copy the bearer string to your password vault now."
            ),
        ),
        SetupStep(
            n=3,
            title="Capture client ID + secret",
            body=(
                "Some Netskope tenants surface a separate Client ID + Secret pair on the same page. "
                "Copy whichever pair the page shows — URIP supports both."
            ),
        ),
        SetupStep(
            n=4,
            title="Paste into URIP",
            body=(
                "URIP → Tool Catalog → Netskope tile → paste **Tenant URL**, **Client ID**, **Client Secret** → "
                "click **Test Connection**."
            ),
        ),
    ],
    required_scopes=[
        ScopeItem(
            name="events:read",
            description="Read network/web/email events.",
            required=True,
        ),
        ScopeItem(
            name="alerts:read",
            description="Read DLP and threat alerts.",
            required=True,
        ),
        ScopeItem(
            name="incidents:read",
            description="Read DLP incident details (CASB tier).",
            required=False,
        ),
    ],
    sample_data={
        "id": "netskope-incident-441a-7c3d",
        "source": "netskope",
        "domain": "application",
        "finding": "DLP — Sensitive PII uploaded to personal Google Drive",
        "asset": "user@example.com / Chrome / 10.30.5.18",
        "owner_team": "data-protection",
        "cvss_score": 7.0,
        "severity": "high",
    },
    not_collected=[
        "Full file contents that triggered the DLP rule (only the rule name + match summary)",
        "User browsing history outside flagged events",
        "Plain-text passwords seen in HTTP forms",
    ],
    common_errors=[
        ErrorFix(
            error="401 Invalid Bearer Token",
            cause="Token rotated, expired (max 1 year), or scope changed.",
            fix=(
                "Settings → Tools → REST API v2 → confirm the token is still listed and "
                "**Active**. Regenerate if needed."
            ),
        ),
        ErrorFix(
            error="403 Forbidden — endpoint not in token scope",
            cause="Token created with narrower scope than URIP needs.",
            fix=(
                "Re-create the token with read access to events, alerts, and (optional) "
                "dlp/incidents."
            ),
        ),
        ErrorFix(
            error="429 Too Many Requests",
            cause="Netskope enforces ~50 req/sec per tenant; bursty integrations collide.",
            fix=(
                "Stagger pollers across tenants or contact Netskope to raise the cap."
            ),
        ),
        ErrorFix(
            error="DNS — tenant.goskope.com not found",
            cause="Wrong tenant URL — older tenants live at *.eu.goskope.com or similar.",
            fix=(
                "Confirm the tenant URL by signing in to the admin portal and copying the host."
            ),
        ),
    ],
    polling=PollingSpec(
        default_minutes=15,
        first_sync_estimate_minutes=10,
        webhook_supported=False,
        manual_refresh="Tool Catalog → Netskope tile → Run Now.",
    ),
    disconnect_steps=[
        "Tool Catalog → Netskope tile → Disable.",
        _CRED_VAULT_DELETE,
        _KEEP_HISTORY,
        "Settings → Tools → REST API v2 → revoke the `urip-readonly` token.",
    ],
    references=[
        "Netskope REST API v2: https://docs.netskope.com/en/rest-api-v2-overview-312207.html",
    ],
)


# ─────────────────────────────────────────────────────────────────────────────
# 5. Microsoft Entra ID (Identity Protection)
# ─────────────────────────────────────────────────────────────────────────────


_MS_ENTRA = SetupGuideSpec(
    quick_facts=QuickFacts(
        category="IDENTITY",
        module="IDENTITY",
        difficulty="medium",
        approx_setup_minutes=25,
        vendor_docs_url="https://learn.microsoft.com/en-us/graph/api/resources/identityprotectionroot",
        polling_default_minutes=15,
        supports_webhooks=False,
        license_tier_required="Microsoft Entra ID P2 (required for Identity Protection risk events).",
    ),
    what_pulled=[
        "Risky users (riskLevelAggregated, risk events)",
        "Sign-in risk detections (impossible travel, anonymous IP, leaked creds)",
        "Conditional Access policy drift",
        "Audit log entries (admin role grants, app consent, policy changes)",
    ],
    prerequisites=[
        PrereqItem(
            label="License tier",
            requirement="Microsoft Entra ID P2 — Identity Protection APIs require P2.",
        ),
        PrereqItem(
            label="Admin role",
            requirement="Global Admin or Application Administrator (to grant admin consent).",
        ),
        PrereqItem(
            label="Network",
            requirement="Allow URIP egress to https://login.microsoftonline.com and https://graph.microsoft.com on TCP 443.",
        ),
    ],
    steps=[
        SetupStep(
            n=1,
            title="Register an application",
            body=(
                "Azure Portal → Microsoft Entra ID → **App registrations** → **+ New registration**. "
                "Name: `URIP Risk Reader`. Supported types: Single tenant. Redirect URI: leave blank. "
                "Save the **Application (client) ID** + **Directory (tenant) ID** shown on Overview."
            ),
        ),
        SetupStep(
            n=2,
            title="Create a client secret",
            body=(
                "App registration → **Certificates & secrets** → **+ New client secret** → "
                "lifetime = 24 months → Add. **Copy the Value (not the ID) immediately.**"
            ),
            warning="The secret Value is shown ONCE. After you leave the page only the redacted form is visible.",
        ),
        SetupStep(
            n=3,
            title="Add Microsoft Graph API permissions",
            body=(
                "App registration → **API permissions** → **+ Add a permission** → Microsoft Graph → "
                "**Application permissions** → tick: `IdentityRiskEvent.Read.All`, `IdentityRiskyUser.Read.All`, "
                "`AuditLog.Read.All`, `Policy.Read.All`, `Directory.Read.All`."
            ),
        ),
        SetupStep(
            n=4,
            title="Grant admin consent",
            body=(
                "Same page → click **Grant admin consent for <tenant>**. Status column should turn "
                "green for every permission. This step requires Global Admin or Application Admin."
            ),
        ),
        SetupStep(
            n=5,
            title="Paste into URIP",
            body=(
                "URIP → Tool Catalog → Microsoft Entra ID tile → paste Tenant ID, Client ID, Client Secret → "
                "click **Test Connection**. URIP performs a token-exchange against /oauth2/v2.0/token."
            ),
        ),
    ],
    required_scopes=[
        ScopeItem(
            name="IdentityRiskEvent.Read.All",
            description="Read sign-in risk detections.",
            required=True,
        ),
        ScopeItem(
            name="IdentityRiskyUser.Read.All",
            description="Read risky-user aggregates.",
            required=True,
        ),
        ScopeItem(
            name="AuditLog.Read.All",
            description="Read directory audit + sign-in logs.",
            required=True,
        ),
        ScopeItem(
            name="Policy.Read.All",
            description="Read Conditional Access policies.",
            required=True,
        ),
        ScopeItem(
            name="Directory.Read.All",
            description="Resolve user / group context for findings.",
            required=True,
        ),
    ],
    sample_data={
        "id": "entra-risk-3f8c-2a91",
        "source": "ms_entra",
        "domain": "identity",
        "finding": "User sign-in from anonymous IP (Tor exit node)",
        "asset": "alice.smith@example.com",
        "owner_team": "identity-team",
        "cvss_score": 8.0,
        "severity": "high",
        "in_kev_catalog": False,
    },
    not_collected=[
        "Plain-text user passwords (Entra never exposes them)",
        "Personal device serial numbers from Intune (separate connector)",
        "Mailbox content (Exchange Online — separate connector)",
    ],
    common_errors=[
        ErrorFix(
            error="AADSTS70011 / 700016 — invalid_client",
            cause="Client secret value mistyped or expired (Entra secrets default 24-month lifetime).",
            fix=(
                "App registration → Certificates & secrets → check expiry. Create a new secret, "
                "copy its **Value** (not Secret ID), and update URIP."
            ),
        ),
        ErrorFix(
            error="AADSTS65001 — admin consent required",
            cause="Step 4 (Grant admin consent) was skipped or partially completed.",
            fix=(
                "App registration → API permissions → click Grant admin consent for <tenant> as a "
                "Global Admin. Wait ~30 seconds for the change to propagate."
            ),
        ),
        ErrorFix(
            error="403 Forbidden on /identityProtection/riskDetections",
            cause="Tenant lacks Entra ID P2 license — Identity Protection APIs return 403 on lower tiers.",
            fix=(
                "Verify license under Entra → Licenses. P2 (or Microsoft 365 E5) is required."
            ),
        ),
        ErrorFix(
            error="429 Too Many Requests from Microsoft Graph",
            cause="Graph throttles burst calls; URIP's poll collides with another integration.",
            fix=(
                "URIP applies exponential back-off automatically. Lower **Max requests / hour** in "
                "the wizard if 429s persist (default 1000)."
            ),
        ),
    ],
    polling=PollingSpec(
        default_minutes=15,
        first_sync_estimate_minutes=10,
        webhook_supported=False,
        manual_refresh="Tool Catalog → Microsoft Entra ID tile → Run Now.",
    ),
    disconnect_steps=[
        "Tool Catalog → Microsoft Entra ID tile → Disable.",
        _CRED_VAULT_DELETE,
        _KEEP_HISTORY,
        "Optionally delete the `URIP Risk Reader` app registration in Azure Portal.",
    ],
    references=[
        "Identity Protection API: https://learn.microsoft.com/en-us/graph/api/resources/identityprotectionroot",
        "App registration walkthrough: https://learn.microsoft.com/en-us/azure/active-directory/develop/quickstart-register-app",
    ],
)


# ─────────────────────────────────────────────────────────────────────────────
# 6. ManageEngine ServiceDesk Plus (ITSM)
# ─────────────────────────────────────────────────────────────────────────────


_ME_SDP = SetupGuideSpec(
    quick_facts=QuickFacts(
        category="ITSM",
        module="ITSM",
        difficulty="medium",
        approx_setup_minutes=25,
        vendor_docs_url="https://www.manageengine.com/products/service-desk/sdpod-v3-api/",
        polling_default_minutes=10,
        supports_webhooks=True,
        license_tier_required="ServiceDesk Plus Cloud (any paid tier) OR On-Prem Professional+.",
    ),
    what_pulled=[
        "Tickets created from URIP risks (bidirectional)",
        "Ticket status updates pushed back to URIP risks",
        "Assignee + group assignments (for ownership routing)",
        "Resolution notes (closed-loop tracking)",
    ],
    prerequisites=[
        PrereqItem(
            label="License tier",
            requirement=(
                "SDP Cloud (any paid tier) — On-Prem Standard does NOT expose the V3 API; "
                "Professional or Enterprise required."
            ),
        ),
        PrereqItem(
            label="Admin role",
            requirement="SDP Admin (Cloud) or technician with API access (On-Prem).",
        ),
        PrereqItem(
            label="Network",
            requirement=(
                "Allow URIP egress to your SDP instance "
                "(e.g. https://sdpondemand.manageengine.com) on TCP 443."
            ),
        ),
    ],
    steps=[
        SetupStep(
            n=1,
            title="Choose auth method",
            body=(
                "URIP supports both static **Auth Token** (simpler, recommended for on-prem) and "
                "**OAuth refresh-token** (recommended for SDP Cloud). Pick one in the wizard."
            ),
        ),
        SetupStep(
            n=2,
            title="Static token path (on-prem)",
            body=(
                "SDP → **Admin → Technicians** → select the API user → **API Key Generation** → "
                "Generate Authtoken. Copy the value — paste as **Auth Token** in URIP."
            ),
        ),
        SetupStep(
            n=3,
            title="OAuth path (SDP Cloud)",
            body=(
                "Visit https://api-console.zoho.com → **Add Client** → Server-Based Application. "
                "Save Client ID + Client Secret. Then generate a refresh token (one-time consent) "
                "via the Zoho OAuth playground using scope `SDPOnDemand.requests.ALL`."
            ),
        ),
        SetupStep(
            n=4,
            title="Paste into URIP",
            body=(
                "URIP → Tool Catalog → ManageEngine ServiceDesk Plus tile → set **Base URL** "
                "(e.g. https://sdpondemand.manageengine.com), select Auth Method, paste credentials, "
                "click **Test Connection**."
            ),
        ),
    ],
    required_scopes=[
        ScopeItem(
            name="SDPOnDemand.requests.ALL",
            description="Read + create tickets (Cloud OAuth scope).",
            required=True,
        ),
        ScopeItem(
            name="Technician with API access",
            description="On-prem path — technician role with API enabled.",
            required=True,
        ),
    ],
    sample_data={
        "ticket_id": "SDP-INC-1928",
        "status": "In Progress",
        "linked_risk_id": "RISK-A2C9F3B1",
        "assignee": "secops@example.com",
        "priority": "High",
    },
    not_collected=[
        "Internal helpdesk discussions outside URIP-linked tickets",
        "Customer survey responses",
        "End-user PII fields beyond requester email",
    ],
    common_errors=[
        ErrorFix(
            error="401 INVALID_TOKEN on first poll",
            cause="OAuth refresh token expired (Zoho refresh tokens expire after 60 days of inactivity).",
            fix=(
                "Re-run the consent flow at api-console.zoho.com to mint a new refresh token, "
                "update the URIP wizard."
            ),
        ),
        ErrorFix(
            error="403 URL_RULE_NOT_CONFIGURED",
            cause="On-prem SDP — request URL rule not registered for the technician.",
            fix=(
                "Admin → API → URL Rules → ensure /api/v3/requests is allowed for the technician."
            ),
        ),
        ErrorFix(
            error="404 on /api/v3/requests",
            cause="Wrong base URL (used SDP On-Prem path on a Cloud tenant or vice-versa).",
            fix=(
                "Cloud: https://sdpondemand.manageengine.com — On-Prem: https://<host>:8080."
            ),
        ),
        ErrorFix(
            error="Webhook signature mismatch",
            cause="HMAC secret in SDP webhook config differs from URIP's stored secret.",
            fix=(
                "Edit the SDP webhook → re-paste the secret from URIP's connector page."
            ),
        ),
    ],
    polling=PollingSpec(
        default_minutes=10,
        first_sync_estimate_minutes=5,
        webhook_supported=True,
        manual_refresh="Tool Catalog → ManageEngine ServiceDesk Plus tile → Run Now.",
    ),
    disconnect_steps=[
        "Tool Catalog → ManageEngine ServiceDesk Plus tile → Disable.",
        _CRED_VAULT_DELETE,
        "URIP-created tickets remain in SDP — disconnect does not delete them.",
        _KEEP_HISTORY,
    ],
    references=[
        "SDP Cloud V3 API: https://www.manageengine.com/products/service-desk/sdpod-v3-api/",
        "Zoho OAuth setup: https://www.zoho.com/accounts/protocol/oauth/web-apps/authorization.html",
    ],
)


# ─────────────────────────────────────────────────────────────────────────────
# 7. CloudSEK XVigil / BeVigil / SVigil
# ─────────────────────────────────────────────────────────────────────────────


_CLOUDSEK = SetupGuideSpec(
    quick_facts=QuickFacts(
        category="EXTERNAL_THREAT",
        module="EXTERNAL_THREAT",
        difficulty="easy",
        approx_setup_minutes=10,
        vendor_docs_url="https://docs.cloudsek.com/",
        polling_default_minutes=30,
        supports_webhooks=False,
        license_tier_required="CloudSEK XVigil / BeVigil / SVigil — at least one product subscription.",
    ),
    what_pulled=[
        "Brand impersonation (look-alike domains, fake apps)",
        "Exposed credentials on dark-web / paste sites",
        "Mobile app risks (BeVigil)",
        "Supply-chain / open-source risks (SVigil)",
        "Threat-intel indicators tagged to your org",
    ],
    prerequisites=[
        PrereqItem(
            label="License tier",
            requirement="At least one of CloudSEK XVigil, BeVigil, or SVigil.",
        ),
        PrereqItem(
            label="Admin role",
            requirement="Tenant Admin (required to mint API keys).",
        ),
        PrereqItem(
            label="Network",
            requirement="Allow URIP egress to https://api.cloudsek.com (or your regional pod) on TCP 443.",
        ),
    ],
    steps=[
        SetupStep(
            n=1,
            title="Open API access",
            body=(
                "CloudSEK admin portal → **Settings → API Access** → **Generate API Key**."
            ),
        ),
        SetupStep(
            n=2,
            title="Capture the key + org ID",
            body=(
                "Copy both the **API Key** and your **Organization ID** (shown on the same page "
                "or under Settings → Account)."
            ),
            warning="The API key is shown ONCE. Save it securely.",
        ),
        SetupStep(
            n=3,
            title="(Optional) regional override",
            body=(
                "If your tenant is in CloudSEK's EU/IN pod, the API base URL differs from the "
                "default. Set **API Base URL** in the URIP wizard (e.g. https://api-eu.cloudsek.com)."
            ),
        ),
        SetupStep(
            n=4,
            title="Paste into URIP",
            body=(
                "URIP → Tool Catalog → CloudSEK tile → paste **API Key**, **Organization ID**, optional "
                "**API Base URL**, comma-separated **Enabled Products** (e.g. xvigil,bevigil) → Test Connection."
            ),
        ),
    ],
    required_scopes=[
        ScopeItem(
            name="threats:read",
            description="Read brand-impersonation + dark-web findings (XVigil).",
            required=True,
        ),
        ScopeItem(
            name="mobile:read",
            description="Required only when BeVigil is licensed.",
            required=False,
        ),
        ScopeItem(
            name="supplychain:read",
            description="Required only when SVigil is licensed.",
            required=False,
        ),
    ],
    sample_data={
        "id": "cloudsek-xvigil-9d33-4471",
        "source": "cloudsek",
        "domain": "external_threat",
        "finding": "Look-alike domain registered: examp1e-bank.com",
        "asset": "example-bank.com (brand)",
        "owner_team": "brand-protection",
        "cvss_score": 6.5,
        "severity": "medium",
    },
    not_collected=[
        "Internal employee data (CloudSEK is purely external surface)",
        "Customer PII from leaked dumps (only counts + sample hashes)",
        "Plain-text leaked passwords (only their hashed/redacted form)",
    ],
    common_errors=[
        ErrorFix(
            error="401 Invalid API key",
            cause="API key revoked from the CloudSEK admin or pasted with surrounding whitespace.",
            fix=(
                "Settings → API Access → confirm key is **Active**. Trim trailing/leading spaces "
                "when pasting into URIP."
            ),
        ),
        ErrorFix(
            error="404 Organization not found",
            cause="Organization ID typed wrong (case-sensitive) or belongs to a different pod.",
            fix=(
                "Copy the org ID directly from Settings → Account; verify the API base URL matches your pod."
            ),
        ),
        ErrorFix(
            error="403 Product not subscribed",
            cause="`enabled_products` includes a CloudSEK product not licensed for your tenant.",
            fix=(
                "Remove the unlicensed product (e.g. drop `bevigil` if you only have XVigil). "
                "Contact CloudSEK to add product licenses."
            ),
        ),
        ErrorFix(
            error="429 Rate limit exceeded",
            cause="CloudSEK enforces ~10 req/sec per tenant.",
            fix=(
                "URIP polls hourly by default; if other integrations also hit CloudSEK, stagger "
                "their schedules."
            ),
        ),
    ],
    polling=PollingSpec(
        default_minutes=30,
        first_sync_estimate_minutes=15,
        webhook_supported=False,
        manual_refresh="Tool Catalog → CloudSEK tile → Run Now.",
    ),
    disconnect_steps=[
        "Tool Catalog → CloudSEK tile → Disable.",
        _CRED_VAULT_DELETE,
        _KEEP_HISTORY,
        "Optionally revoke the API key in CloudSEK Settings → API Access.",
    ],
    references=[
        "CloudSEK docs: https://docs.cloudsek.com/",
    ],
)


# ─────────────────────────────────────────────────────────────────────────────
# 8. AWS CSPM (Config + SecurityHub + GuardDuty + AccessAnalyzer)
# ─────────────────────────────────────────────────────────────────────────────


_AWS_CSPM = SetupGuideSpec(
    quick_facts=QuickFacts(
        category="CSPM",
        module="CSPM",
        difficulty="medium",
        approx_setup_minutes=25,
        vendor_docs_url="https://docs.aws.amazon.com/securityhub/latest/APIReference/Welcome.html",
        polling_default_minutes=30,
        supports_webhooks=False,
        license_tier_required="AWS account with SecurityHub + GuardDuty enabled (paid AWS services).",
    ),
    what_pulled=[
        "AWS Config rule compliance (drift, mis-config)",
        "Security Hub findings (CIS, AWS FSBP, PCI-DSS)",
        "GuardDuty threat findings (malicious IPs, IAM anomalies)",
        "IAM Access Analyzer findings (over-permissive policies)",
    ],
    prerequisites=[
        PrereqItem(
            label="License tier",
            requirement="AWS account with SecurityHub + GuardDuty + Config enabled (each is paid).",
        ),
        PrereqItem(
            label="Admin role",
            requirement=(
                "AWS IAM principal able to create users + attach policies "
                "(IAMFullAccess) — only needed for the initial setup."
            ),
        ),
        PrereqItem(
            label="Network",
            requirement="Allow URIP egress to AWS regional endpoints (TCP 443).",
        ),
    ],
    steps=[
        SetupStep(
            n=1,
            title="Create a dedicated IAM user",
            body=(
                "AWS Console → IAM → Users → **Create user** → name `urip-readonly` → "
                "**Programmatic access**. Click Next."
            ),
        ),
        SetupStep(
            n=2,
            title="Attach a least-privilege policy",
            body=(
                "Attach the AWS-managed policies: **SecurityAudit** (recommended baseline), "
                "**AWSConfigUserAccess**, **AmazonGuardDutyReadOnlyAccess**, **IAMAccessAnalyzerReadOnlyAccess**. "
                "Or use a custom policy with `securityhub:GetFindings`, `config:DescribeComplianceByConfigRule`, "
                "`guardduty:ListFindings`, `access-analyzer:ListFindings`."
            ),
        ),
        SetupStep(
            n=3,
            title="Generate access keys",
            body=(
                "User → **Security credentials** tab → **Create access key** → use case = "
                "**Application running outside AWS** → confirm warnings → **Create**."
            ),
            warning=(
                "The Secret access key is shown ONCE. Save Access key ID + Secret to your vault."
            ),
        ),
        SetupStep(
            n=4,
            title="Paste into URIP",
            body=(
                "URIP → Tool Catalog → AWS CSPM tile → paste **Access key** + **Secret key**, "
                "set **Region** (e.g. us-east-1) → **Test Connection**. URIP performs `STS:GetCallerIdentity`."
            ),
        ),
    ],
    required_scopes=[
        ScopeItem(
            name="SecurityAudit (managed)",
            description="Broad read-only across most AWS security services.",
            required=True,
        ),
        ScopeItem(
            name="AWSConfigUserAccess",
            description="Read AWS Config rule compliance.",
            required=True,
        ),
        ScopeItem(
            name="AmazonGuardDutyReadOnlyAccess",
            description="Read GuardDuty threat findings.",
            required=False,
        ),
        ScopeItem(
            name="IAMAccessAnalyzerReadOnlyAccess",
            description="Read Access Analyzer findings.",
            required=False,
        ),
    ],
    sample_data={
        "id": "aws-config-s3-public-read",
        "source": "aws_cspm",
        "domain": "cloud",
        "finding": "S3 bucket allows public READ access (rule: s3-bucket-public-read-prohibited)",
        "asset": "arn:aws:s3:::company-marketing-public",
        "owner_team": "cloud-security",
        "cvss_score": 8.0,
        "severity": "high",
    },
    not_collected=[
        "Object contents inside S3 buckets (only resource ARNs + metadata)",
        "CloudTrail event payloads outside enabled findings",
        "Customer secrets in Secrets Manager (no decryption)",
    ],
    common_errors=[
        ErrorFix(
            error="InvalidClientTokenId / SignatureDoesNotMatch",
            cause="Access key revoked, deleted, or pasted with whitespace.",
            fix=(
                "AWS IAM → User → Security credentials → confirm key is Active. "
                "Re-paste into URIP, trimmed of whitespace."
            ),
        ),
        ErrorFix(
            error="AccessDeniedException on securityhub:GetFindings",
            cause="IAM user lacks Security Hub read permission.",
            fix=(
                "Attach AWSSecurityHubReadOnlyAccess (or SecurityAudit). Wait ~30s for IAM to propagate."
            ),
        ),
        ErrorFix(
            error="UnrecognizedClientException — service not active in region",
            cause="GuardDuty / SecurityHub not enabled in the configured region.",
            fix=(
                "Either enable the service in that region or change the **Region** in the wizard."
            ),
        ),
        ErrorFix(
            error="ThrottlingException",
            cause="API rate limit hit — usually when other tools also poll the same account.",
            fix="URIP retries with exponential back-off; increase poll interval to 60 min if persistent.",
        ),
    ],
    polling=PollingSpec(
        default_minutes=30,
        first_sync_estimate_minutes=15,
        webhook_supported=False,
        manual_refresh="Tool Catalog → AWS CSPM tile → Run Now.",
    ),
    disconnect_steps=[
        "Tool Catalog → AWS CSPM tile → Disable.",
        _CRED_VAULT_DELETE,
        _KEEP_HISTORY,
        "AWS IAM → delete the `urip-readonly` user (or just deactivate its access keys).",
    ],
    references=[
        "Security Hub API: https://docs.aws.amazon.com/securityhub/latest/APIReference/Welcome.html",
        "GuardDuty API: https://docs.aws.amazon.com/guardduty/latest/APIReference/Welcome.html",
    ],
)


# ─────────────────────────────────────────────────────────────────────────────
# 9. Azure CSPM (Defender for Cloud)
# ─────────────────────────────────────────────────────────────────────────────


_AZURE_CSPM = SetupGuideSpec(
    quick_facts=QuickFacts(
        category="CSPM",
        module="CSPM",
        difficulty="medium",
        approx_setup_minutes=30,
        vendor_docs_url="https://learn.microsoft.com/en-us/rest/api/defenderforcloud/",
        polling_default_minutes=30,
        supports_webhooks=False,
        license_tier_required="Microsoft Defender for Cloud (paid plans) for full recommendations + alerts.",
    ),
    what_pulled=[
        "Azure Policy compliance state (per resource)",
        "Defender for Cloud security recommendations",
        "Defender for Cloud alerts (active threats)",
        "Resource inventory + tier classification",
    ],
    prerequisites=[
        PrereqItem(
            label="License tier",
            requirement=(
                "Defender for Cloud — Free tier returns posture only; paid plans add "
                "alerts + recommendations."
            ),
        ),
        PrereqItem(
            label="Admin role",
            requirement="Owner of the subscription (to assign roles to a service principal).",
        ),
        PrereqItem(
            label="Network",
            requirement="Allow URIP egress to https://login.microsoftonline.com + https://management.azure.com on TCP 443.",
        ),
    ],
    steps=[
        SetupStep(
            n=1,
            title="Register an application",
            body=(
                "Azure Portal → Microsoft Entra ID → App registrations → **+ New registration**. "
                "Name: `URIP CSPM Reader`. Save Tenant ID + Client (Application) ID."
            ),
        ),
        SetupStep(
            n=2,
            title="Create a client secret",
            body=(
                "App → **Certificates & secrets** → **+ New client secret** → 24 months → Add. "
                "Copy the **Value** immediately."
            ),
            warning="Secret Value is shown ONCE.",
        ),
        SetupStep(
            n=3,
            title="Grant Reader + Security Reader on the subscription",
            body=(
                "Subscription → **Access control (IAM)** → **+ Add role assignment** → role = **Reader**, "
                "assign to the service principal. Repeat with role = **Security Reader**."
            ),
        ),
        SetupStep(
            n=4,
            title="Paste into URIP",
            body=(
                "URIP → Tool Catalog → Azure CSPM tile → paste Tenant ID, Client ID, Client Secret → "
                "click **Test Connection**."
            ),
        ),
    ],
    required_scopes=[
        ScopeItem(
            name="Reader (RBAC)",
            description="Subscription-level read access to all resources.",
            required=True,
        ),
        ScopeItem(
            name="Security Reader (RBAC)",
            description="Read Defender for Cloud alerts + recommendations.",
            required=True,
        ),
    ],
    sample_data={
        "id": "azure-defender-rec-1234",
        "source": "azure_cspm",
        "domain": "cloud",
        "finding": "Storage account allows public network access (recommendation: disable public network access)",
        "asset": "/subscriptions/abc.../storageAccounts/marketingdata",
        "owner_team": "cloud-security",
        "cvss_score": 7.0,
        "severity": "high",
    },
    not_collected=[
        "Storage blob contents (URIP only reads resource metadata)",
        "Key Vault secret values",
        "Identity Protection events (use the Microsoft Entra ID connector for that)",
    ],
    common_errors=[
        ErrorFix(
            error="AADSTS70011 — invalid_client",
            cause="Client secret expired / mistyped.",
            fix=(
                "App registration → Certificates & secrets → confirm secret is unexpired. "
                "Create a new one if needed."
            ),
        ),
        ErrorFix(
            error="403 Forbidden on /providers/Microsoft.Security/alerts",
            cause="Service principal missing Security Reader role.",
            fix=(
                "Subscription → Access control (IAM) → add **Security Reader** to the service principal."
            ),
        ),
        ErrorFix(
            error="404 SubscriptionNotFound",
            cause="The service principal does not have any role at all on the target subscription.",
            fix=(
                "Add **Reader** at the subscription level (or higher in the hierarchy) before retrying."
            ),
        ),
        ErrorFix(
            error="429 — Resource Manager throttle",
            cause="Burst rate limit; usually after first sync on tenants with thousands of resources.",
            fix=(
                "URIP back-offs automatically. Increase polling interval if 429s persist."
            ),
        ),
    ],
    polling=PollingSpec(
        default_minutes=30,
        first_sync_estimate_minutes=20,
        webhook_supported=False,
        manual_refresh="Tool Catalog → Azure CSPM tile → Run Now.",
    ),
    disconnect_steps=[
        "Tool Catalog → Azure CSPM tile → Disable.",
        _CRED_VAULT_DELETE,
        _KEEP_HISTORY,
        "Optionally remove role assignments + delete the `URIP CSPM Reader` app registration.",
    ],
    references=[
        "Defender for Cloud REST API: https://learn.microsoft.com/en-us/rest/api/defenderforcloud/",
    ],
)


# ─────────────────────────────────────────────────────────────────────────────
# 10. GCP CSPM (Security Command Center + Recommender + Asset Inventory)
# ─────────────────────────────────────────────────────────────────────────────


_GCP_CSPM = SetupGuideSpec(
    quick_facts=QuickFacts(
        category="CSPM",
        module="CSPM",
        difficulty="medium",
        approx_setup_minutes=25,
        vendor_docs_url="https://cloud.google.com/security-command-center/docs/reference/rest",
        polling_default_minutes=30,
        supports_webhooks=False,
        license_tier_required="Security Command Center Standard (Premium recommended for full findings).",
    ),
    what_pulled=[
        "SCC findings (vuln, mis-config, threat)",
        "Cloud Asset Inventory (resource tier mapping)",
        "Recommender suggestions (IAM, security)",
        "Org policy compliance",
    ],
    prerequisites=[
        PrereqItem(
            label="License tier",
            requirement="SCC Standard (free) returns posture; SCC Premium recommended for active findings.",
        ),
        PrereqItem(
            label="Admin role",
            requirement="Project IAM Admin OR Org IAM Admin (to create a service account).",
        ),
        PrereqItem(
            label="Network",
            requirement="Allow URIP egress to https://oauth2.googleapis.com + https://*.googleapis.com on TCP 443.",
        ),
    ],
    steps=[
        SetupStep(
            n=1,
            title="Create a service account",
            body=(
                "GCP Console → IAM & Admin → **Service Accounts** → **+ Create service account** → "
                "name `urip-readonly` → Create."
            ),
        ),
        SetupStep(
            n=2,
            title="Grant least-privilege roles",
            body=(
                "Grant: **Security Center Findings Viewer**, **Cloud Asset Viewer**, "
                "**Recommender Viewer** at the org level (or project level for single-project setups)."
            ),
        ),
        SetupStep(
            n=3,
            title="Generate a key file",
            body=(
                "Service account → **Keys** tab → **Add key** → **Create new key** → JSON → Create. "
                "A JSON file downloads — this is your service account key."
            ),
            warning=(
                "Treat the JSON like a password. Anyone with this file can read your security findings."
            ),
        ),
        SetupStep(
            n=4,
            title="Paste into URIP",
            body=(
                "URIP → Tool Catalog → GCP CSPM tile → paste the JSON file content into "
                "**Service Account JSON** → optionally set **Org ID** for org-level SCC. Test Connection."
            ),
        ),
    ],
    required_scopes=[
        ScopeItem(
            name="roles/securitycenter.findingsViewer",
            description="Read SCC findings.",
            required=True,
        ),
        ScopeItem(
            name="roles/cloudasset.viewer",
            description="Read Cloud Asset Inventory.",
            required=True,
        ),
        ScopeItem(
            name="roles/recommender.viewer",
            description="Read Recommender suggestions.",
            required=False,
        ),
    ],
    sample_data={
        "id": "scc-finding-iam-9d12-3344",
        "source": "gcp_cspm",
        "domain": "cloud",
        "finding": "Service account has roles/owner — over-permissive (PRIORITY P1)",
        "asset": "//iam.googleapis.com/projects/prod/serviceAccounts/build-bot@prod.iam",
        "owner_team": "cloud-security",
        "cvss_score": 9.0,
        "severity": "critical",
    },
    not_collected=[
        "Cloud Storage object contents",
        "Secret Manager secret values",
        "BigQuery table contents (only metadata)",
    ],
    common_errors=[
        ErrorFix(
            error="invalid_grant — Account not authorized",
            cause="Service account JSON used belongs to a deleted/disabled account.",
            fix=(
                "Re-create the key file, confirm the service account is Enabled in IAM, paste fresh JSON."
            ),
        ),
        ErrorFix(
            error="PERMISSION_DENIED — securitycenter.findings.list",
            cause="Service account missing Security Center Findings Viewer.",
            fix=(
                "IAM → grant **Security Center Findings Viewer** at the right scope (org or project)."
            ),
        ),
        ErrorFix(
            error="404 — SCC source not found",
            cause="Org-level SCC findings requested but only project-level scope granted.",
            fix=(
                "Either grant the role at org scope, or set **Project ID** instead of **Org ID**."
            ),
        ),
        ErrorFix(
            error="429 RESOURCE_EXHAUSTED",
            cause="Per-minute quota hit (often during initial sync of large orgs).",
            fix="URIP retries with exponential back-off; increase polling interval if 429s persist.",
        ),
    ],
    polling=PollingSpec(
        default_minutes=30,
        first_sync_estimate_minutes=15,
        webhook_supported=False,
        manual_refresh="Tool Catalog → GCP CSPM tile → Run Now.",
    ),
    disconnect_steps=[
        "Tool Catalog → GCP CSPM tile → Disable.",
        _CRED_VAULT_DELETE,
        _KEEP_HISTORY,
        "GCP IAM → delete the `urip-readonly` service account or rotate its key.",
    ],
    references=[
        "Security Command Center: https://cloud.google.com/security-command-center/docs/reference/rest",
        "Service account keys: https://cloud.google.com/iam/docs/keys-create-delete",
    ],
)


# ─────────────────────────────────────────────────────────────────────────────
# 11. CERT-In Advisories (public)
# ─────────────────────────────────────────────────────────────────────────────


_CERT_IN = SetupGuideSpec(
    quick_facts=QuickFacts(
        category="ADVISORY",
        module="CORE",
        difficulty="easy",
        approx_setup_minutes=2,
        vendor_docs_url="https://www.cert-in.org.in/",
        polling_default_minutes=60,
        supports_webhooks=False,
        license_tier_required="None — public advisories.",
    ),
    what_pulled=[
        "CERT-In advisories (Indian Computer Emergency Response Team)",
        "CVE mappings cited in each advisory",
        "Severity classification (Critical / High / Medium / Low)",
        "Affected products + recommended actions",
    ],
    prerequisites=[
        PrereqItem(
            label="License tier",
            requirement="None — CERT-In publishes advisories publicly.",
        ),
        PrereqItem(
            label="Admin role",
            requirement=(
                "Any URIP CISO-role user can enable this connector — no upstream credentials are stored."
            ),
        ),
        PrereqItem(
            label="Network",
            requirement="Allow URIP egress to https://www.cert-in.org.in on TCP 443.",
        ),
    ],
    steps=[
        SetupStep(
            n=1,
            title="Open the connector in URIP",
            body="URIP → Tool Catalog → CERT-In Advisories tile.",
        ),
        SetupStep(
            n=2,
            title="(Optional) custom base URL",
            body=(
                "Most customers leave **Base URL** at the default https://www.cert-in.org.in. "
                "Override only if you proxy CERT-In through your own mirror."
            ),
        ),
        SetupStep(
            n=3,
            title="(Optional) tune severity threshold",
            body=(
                "Set **Min severity** to 'high' if you only want CERT-In advisories rated high or "
                "above to surface as URIP risks. Default is 'low' (everything ingested)."
            ),
        ),
        SetupStep(
            n=4,
            title="Test Connection",
            body=(
                "Click **Test Connection**. URIP fetches the RSS feed, falls back to HTML scrape "
                "if RSS is empty. Save."
            ),
        ),
    ],
    required_scopes=[
        ScopeItem(
            name="Public access",
            description="No credentials required — CERT-In is a public advisory source.",
            required=True,
        ),
    ],
    sample_data={
        "id": "cert-in-CIAD-2026-0042",
        "source": "cert_in",
        "domain": "advisory",
        "finding": "Multiple Vulnerabilities in Cisco IOS XE — CIAD-2026-0042",
        "asset": "Cisco IOS XE — affected versions 17.x.x",
        "owner_team": "advisory-watch",
        "cvss_score": 8.0,
        "severity": "high",
        "cve_id": "CVE-2026-12345",
    },
    not_collected=[
        "No customer data ingested — public source only",
    ],
    common_errors=[
        ErrorFix(
            error="Connectivity check failed: site unreachable",
            cause="Egress blocked, proxy intercepting cert-in.org.in, or DNS issue.",
            fix=(
                "Allow-list https://www.cert-in.org.in in your egress proxy. "
                "Confirm DNS resolution from the URIP backend host."
            ),
        ),
        ErrorFix(
            error="RSS empty — falling back to HTML scrape",
            cause="CERT-In occasionally rotates feed URLs.",
            fix=(
                "URIP automatically falls back to HTML. If both fail, set `force_scrape=true` "
                "in the wizard to skip RSS."
            ),
        ),
        ErrorFix(
            error="HTML structure parse error",
            cause="CERT-In has changed its advisory page layout.",
            fix=(
                "URIP's parser tolerates minor changes; raise a support ticket if the issue persists "
                "for >24 h so we can update the parser."
            ),
        ),
    ],
    polling=PollingSpec(
        default_minutes=60,
        first_sync_estimate_minutes=2,
        webhook_supported=False,
        manual_refresh="Tool Catalog → CERT-In Advisories tile → Run Now.",
    ),
    disconnect_steps=[
        "Tool Catalog → CERT-In Advisories tile → Disable.",
        "No credentials are stored — disable simply stops the polling job.",
        _KEEP_HISTORY,
    ],
    references=[
        "CERT-In: https://www.cert-in.org.in/",
    ],
)


# ─────────────────────────────────────────────────────────────────────────────
# 12. Generic SIEM (Splunk / Elastic / QRadar)
# ─────────────────────────────────────────────────────────────────────────────


_SIEM = SetupGuideSpec(
    quick_facts=QuickFacts(
        category="SOC",
        module="CORE",
        difficulty="medium",
        approx_setup_minutes=30,
        vendor_docs_url="https://docs.splunk.com/Documentation/Splunk/latest/RESTREF/RESTprolog",
        polling_default_minutes=10,
        supports_webhooks=False,
        license_tier_required=(
            "Splunk Enterprise / Cloud (any tier with REST API), "
            "Elastic 7+ (any tier with API keys), QRadar 7.4+ (paid)."
        ),
    ),
    what_pulled=[
        "Saved-search results (Splunk)",
        "Query DSL hits (Elastic)",
        "Ariel-query results (QRadar)",
        "Severity, asset, source-IP, raw event metadata",
    ],
    prerequisites=[
        PrereqItem(
            label="SIEM type",
            requirement="One of Splunk Enterprise / Cloud, Elastic 7+, IBM QRadar 7.4+.",
        ),
        PrereqItem(
            label="Admin role",
            requirement="Splunk: token-issuing admin; Elastic: superuser; QRadar: System Admin.",
        ),
        PrereqItem(
            label="Network",
            requirement="Allow URIP egress to your SIEM host on its REST port (e.g. 8089 for Splunk).",
        ),
    ],
    steps=[
        SetupStep(
            n=1,
            title="Pick your SIEM type",
            body=(
                "URIP → Tool Catalog → Generic SIEM tile → choose **siem_type**: "
                "splunk | elastic | qradar."
            ),
        ),
        SetupStep(
            n=2,
            title="Splunk path",
            body=(
                "Splunk Web → Settings → Tokens → New Token → owner = `urip` → audience = `urip` → "
                "expires = 1 year → Save. Copy the token. Paste **Base URL** "
                "(e.g. https://splunk.example:8089) and **Token** in URIP."
            ),
        ),
        SetupStep(
            n=3,
            title="Elastic path",
            body=(
                "Kibana → Stack Management → Security → API keys → Create API key → grant "
                "read on relevant indices. Copy the **Encoded** value. Paste Base URL and **API Key** "
                "(encoded form) in URIP."
            ),
        ),
        SetupStep(
            n=4,
            title="QRadar path",
            body=(
                "QRadar Console → Admin → User Management → **Authorized Services** → Add "
                "→ role = `Admin` (read-only OK) → Generate. Copy the **Authentication Token**. "
                "Paste Base URL and **Sec Token** in URIP."
            ),
        ),
        SetupStep(
            n=5,
            title="Test Connection",
            body="Click **Test Connection** — URIP runs a tiny query against your SIEM and verifies a 200.",
        ),
    ],
    required_scopes=[
        ScopeItem(
            name="search:read (Splunk)",
            description="Run saved searches in the configured app context.",
            required=True,
        ),
        ScopeItem(
            name="read on indices (Elastic)",
            description="Read access to indices the saved query targets.",
            required=True,
        ),
        ScopeItem(
            name="Authorized service (QRadar)",
            description="Read-only authorized service token.",
            required=True,
        ),
    ],
    sample_data={
        "id": "siem-event-elastic-44a-99",
        "source": "siem",
        "domain": "soc",
        "finding": "Brute-force authentication failures on prod-vpn (Elastic alert)",
        "asset": "prod-vpn (10.0.0.5)",
        "owner_team": "soc",
        "cvss_score": 6.5,
        "severity": "medium",
    },
    not_collected=[
        "Full raw log payloads (only the matched hit and key fields)",
        "PII in user-identity fields outside the configured search filter",
    ],
    common_errors=[
        ErrorFix(
            error="401 — token expired (Splunk)",
            cause="Splunk tokens default to 30-day lifetime.",
            fix="Generate a longer-lived token (Settings → Tokens → New Token → expires = never).",
        ),
        ErrorFix(
            error="403 — security_exception (Elastic)",
            cause="API key lacks read on the configured index pattern.",
            fix="Recreate the API key with explicit `indices: [<pattern>]` privileges.",
        ),
        ErrorFix(
            error="404 — Authorized service not found (QRadar)",
            cause="Authorized service token revoked or its role disabled.",
            fix="Admin → User Management → Authorized Services → re-enable or re-create.",
        ),
        ErrorFix(
            error="SSL certificate verify failed",
            cause="Self-signed cert on on-prem SIEM (common with Splunk/QRadar).",
            fix="Install a CA-trusted cert on the SIEM, or contact URIP support to allow-list the cert hash.",
        ),
    ],
    polling=PollingSpec(
        default_minutes=10,
        first_sync_estimate_minutes=5,
        webhook_supported=False,
        manual_refresh="Tool Catalog → Generic SIEM tile → Run Now.",
    ),
    disconnect_steps=[
        "Tool Catalog → Generic SIEM tile → Disable.",
        _CRED_VAULT_DELETE,
        _KEEP_HISTORY,
        "Optionally revoke the Splunk token / Elastic API key / QRadar service in your SIEM.",
    ],
    references=[
        "Splunk REST: https://docs.splunk.com/Documentation/Splunk/latest/RESTREF/RESTprolog",
        "Elastic API keys: https://www.elastic.co/guide/en/elasticsearch/reference/current/security-api-create-api-key.html",
        "QRadar authorized services: https://www.ibm.com/docs/en/qsip/7.5?topic=overview-authorized-services",
    ],
)


# ─────────────────────────────────────────────────────────────────────────────
# 13. Email Security (Google Workspace + M365 Defender)
# ─────────────────────────────────────────────────────────────────────────────


_EMAIL_SECURITY = SetupGuideSpec(
    quick_facts=QuickFacts(
        category="EMAIL",
        module="CORE",
        difficulty="medium",
        approx_setup_minutes=25,
        vendor_docs_url="https://learn.microsoft.com/en-us/graph/api/resources/security-api-overview",
        polling_default_minutes=15,
        supports_webhooks=False,
        license_tier_required=(
            "Google Workspace Business Plus+ (Alert Center API) OR "
            "Microsoft 365 E3/E5 with Defender for Office 365."
        ),
    ),
    what_pulled=[
        "Phishing alerts",
        "Business email compromise (BEC) detections",
        "Malware in attachments",
        "DMARC / SPF / DKIM hygiene failures",
        "Suspicious sign-in / impossible-travel events",
    ],
    prerequisites=[
        PrereqItem(
            label="License tier",
            requirement=(
                "Google Workspace Business Plus or Enterprise (Alert Center) — OR — "
                "Microsoft 365 E3/E5 with Defender for Office 365."
            ),
        ),
        PrereqItem(
            label="Admin role",
            requirement="Google Super Admin — OR — Entra Global Admin (for app consent).",
        ),
        PrereqItem(
            label="Network",
            requirement=(
                "Allow URIP egress to https://alertcenter.googleapis.com (Google) or "
                "https://graph.microsoft.com (M365) on TCP 443."
            ),
        ),
    ],
    steps=[
        SetupStep(
            n=1,
            title="Pick a provider",
            body="URIP → Tool Catalog → Email Security tile → choose **Provider**: google_workspace | m365_defender.",
        ),
        SetupStep(
            n=2,
            title="Google Workspace path",
            body=(
                "Google Cloud Console → IAM & Admin → Service Accounts → Create. Enable **Domain-wide delegation**. "
                "Grant scopes `https://www.googleapis.com/auth/apps.alerts` (Admin SDK + Alert Center). "
                "In Workspace Admin → Security → API controls → add the service account client ID with the same scope."
            ),
        ),
        SetupStep(
            n=3,
            title="M365 Defender path",
            body=(
                "Azure Portal → Entra ID → App registrations → Create app `URIP Email Security`. "
                "Add Microsoft Graph application permission `SecurityAlert.Read.All`. Grant admin consent. "
                "Create a client secret."
            ),
        ),
        SetupStep(
            n=4,
            title="Paste into URIP",
            body=(
                "URIP → Tool Catalog → Email Security tile → fill provider-specific fields → Test Connection."
            ),
        ),
    ],
    required_scopes=[
        ScopeItem(
            name="apps.alerts (Google)",
            description="Read Alert Center alerts (phishing, BEC, etc.).",
            required=True,
        ),
        ScopeItem(
            name="SecurityAlert.Read.All (M365)",
            description="Read Defender for O365 security alerts via Graph.",
            required=True,
        ),
    ],
    sample_data={
        "id": "email-alert-bec-7711",
        "source": "email_security",
        "domain": "email",
        "finding": "Business Email Compromise — CEO impersonation attempt blocked",
        "asset": "cfo@example.com",
        "owner_team": "security-ops",
        "cvss_score": 9.0,
        "severity": "critical",
    },
    not_collected=[
        "Full email body content (only the alert metadata)",
        "Mailbox contents outside flagged messages",
        "Attachment file contents — only hashes / filenames",
    ],
    common_errors=[
        ErrorFix(
            error="403 — domain-wide delegation not approved (Google)",
            cause="Service account scopes added in Cloud but not approved in Workspace Admin.",
            fix=(
                "Workspace Admin → Security → API controls → Domain-wide delegation → Add new → "
                "paste the service account client ID + scope."
            ),
        ),
        ErrorFix(
            error="AADSTS65001 — admin consent required",
            cause="`SecurityAlert.Read.All` not granted at tenant level (M365).",
            fix=(
                "App registration → API permissions → Grant admin consent for <tenant>."
            ),
        ),
        ErrorFix(
            error="429 — Graph throttling",
            cause="Burst polling colliding with another integration.",
            fix="URIP back-offs automatically; lower polling interval if persistent.",
        ),
        ErrorFix(
            error="No alerts returned despite known incidents",
            cause="Alert filter scoped too narrow (provider-specific time window).",
            fix=(
                "Check the provider's admin console — alerts older than the API window are not returned. "
                "URIP polls a 24-hour rolling window by default."
            ),
        ),
    ],
    polling=PollingSpec(
        default_minutes=15,
        first_sync_estimate_minutes=10,
        webhook_supported=False,
        manual_refresh="Tool Catalog → Email Security tile → Run Now.",
    ),
    disconnect_steps=[
        "Tool Catalog → Email Security tile → Disable.",
        _CRED_VAULT_DELETE,
        _KEEP_HISTORY,
        "Optionally revoke the Google service-account key or delete the M365 app registration.",
    ],
    references=[
        "Google Alert Center API: https://developers.google.com/admin-sdk/alertcenter/reference/rest",
        "Microsoft Graph Security alerts: https://learn.microsoft.com/en-us/graph/api/resources/security-api-overview",
    ],
)


# ─────────────────────────────────────────────────────────────────────────────
# 14. Bug Bounty (HackerOne + Bugcrowd)
# ─────────────────────────────────────────────────────────────────────────────


_BUG_BOUNTY = SetupGuideSpec(
    quick_facts=QuickFacts(
        category="BUG_BOUNTY",
        module="CORE",
        difficulty="easy",
        approx_setup_minutes=10,
        vendor_docs_url="https://api.hackerone.com/customer-resources/",
        polling_default_minutes=15,
        supports_webhooks=True,
        license_tier_required="HackerOne Bounty / Bugcrowd Crowdcontrol — both expose REST APIs to paying customers.",
    ),
    what_pulled=[
        "Researcher reports / submissions",
        "Triage state, severity (critical / high / medium / low or P1–P4)",
        "Bounty awarded amount (audit purposes)",
        "Affected asset + reproduction steps summary",
    ],
    prerequisites=[
        PrereqItem(
            label="License tier",
            requirement="HackerOne Bounty (any plan) — OR — Bugcrowd paying customer with API enabled.",
        ),
        PrereqItem(
            label="Admin role",
            requirement="Program Manager / Owner (HackerOne) or Program Admin (Bugcrowd).",
        ),
        PrereqItem(
            label="Network",
            requirement="Allow URIP egress to https://api.hackerone.com (or https://api.bugcrowd.com) on TCP 443.",
        ),
    ],
    steps=[
        SetupStep(
            n=1,
            title="HackerOne path",
            body=(
                "Profile → Settings → API tokens → Create API token → name `urip-readonly` → "
                "scope = read-only. Capture token + your API user identifier."
            ),
        ),
        SetupStep(
            n=2,
            title="Bugcrowd path",
            body=(
                "Profile menu → API Credentials → Create new credential → role = read-only. "
                "Capture username + token."
            ),
        ),
        SetupStep(
            n=3,
            title="Paste into URIP",
            body=(
                "URIP → Tool Catalog → Bug Bounty tile → choose **platform** (hackerone / bugcrowd) → "
                "paste API token (+ program handle for HackerOne) → Test Connection."
            ),
        ),
        SetupStep(
            n=4,
            title="(Optional) enable webhook ingestion",
            body=(
                "Both platforms can push triage state changes. URIP exposes a per-tenant webhook URL — "
                "paste it into the platform's webhook settings to get near-real-time updates."
            ),
        ),
    ],
    required_scopes=[
        ScopeItem(
            name="reports:read (HackerOne)",
            description="Read program reports.",
            required=True,
        ),
        ScopeItem(
            name="submissions:read (Bugcrowd)",
            description="Read submissions and their severity.",
            required=True,
        ),
    ],
    sample_data={
        "id": "h1-report-2384712",
        "source": "bug_bounty",
        "domain": "application",
        "finding": "Stored XSS in /search endpoint — researcher: alex_h",
        "asset": "https://app.example.com/search",
        "owner_team": "appsec",
        "cvss_score": 7.0,
        "severity": "high",
    },
    not_collected=[
        "Researcher PII beyond their public username",
        "Internal triage discussions on private programs (only state changes)",
    ],
    common_errors=[
        ErrorFix(
            error="401 — invalid token (HackerOne)",
            cause="Token revoked or scope changed.",
            fix="Profile → Settings → API tokens → re-create with read-only scope.",
        ),
        ErrorFix(
            error="403 — program access denied",
            cause="Token belongs to a user not on the configured program.",
            fix="Add the URIP user to the program with at least Member role.",
        ),
        ErrorFix(
            error="Webhook signature verification failed",
            cause="HMAC secret mismatch between URIP and the platform's webhook config.",
            fix="Re-paste the secret from the URIP connector page into the platform's webhook UI.",
        ),
        ErrorFix(
            error="Rate limit exceeded",
            cause="HackerOne caps at ~600 req/min; Bugcrowd has similar burst limits.",
            fix="URIP automatically back-offs; reduce polling cadence if persistent.",
        ),
    ],
    polling=PollingSpec(
        default_minutes=15,
        first_sync_estimate_minutes=10,
        webhook_supported=True,
        manual_refresh="Tool Catalog → Bug Bounty tile → Run Now.",
    ),
    disconnect_steps=[
        "Tool Catalog → Bug Bounty tile → Disable.",
        _CRED_VAULT_DELETE,
        _KEEP_HISTORY,
        "Revoke the API token in HackerOne / Bugcrowd if no longer in use.",
    ],
    references=[
        "HackerOne API: https://api.hackerone.com/customer-resources/",
        "Bugcrowd API: https://docs.bugcrowd.com/api/",
    ],
)


# ─────────────────────────────────────────────────────────────────────────────
# 15. CrowdStrike Falcon (Spotlight + EASM + CNAPP)
# ─────────────────────────────────────────────────────────────────────────────


_CROWDSTRIKE = SetupGuideSpec(
    quick_facts=QuickFacts(
        category="EDR",
        module="EDR",
        difficulty="medium",
        approx_setup_minutes=20,
        vendor_docs_url="https://falcon.us-2.crowdstrike.com/documentation/page/cb1eaaa1/falcon-platform-api-reference",
        polling_default_minutes=15,
        supports_webhooks=False,
        license_tier_required=(
            "CrowdStrike Falcon Insight (EDR), Spotlight (VM), Surface (EASM), or "
            "Cloud Security (CNAPP) — at least one product."
        ),
    ),
    what_pulled=[
        "Spotlight VM findings (ExPRT-prioritised)",
        "Surface (EASM) externally exposed assets",
        "Cloud Security (CNAPP) misconfigurations + threats",
        "Host inventory: hostname, agent ID, OS, last-seen",
    ],
    prerequisites=[
        PrereqItem(
            label="License tier",
            requirement=(
                "At least one of: Falcon Insight, Spotlight, Surface, Cloud Security."
            ),
        ),
        PrereqItem(
            label="Admin role",
            requirement="Falcon Administrator (required to create API clients).",
        ),
        PrereqItem(
            label="Network",
            requirement=(
                "Allow URIP egress to your Falcon API region: api.crowdstrike.com (US-1), "
                "api.us-2.crowdstrike.com (US-2), api.eu-1.crowdstrike.com (EU-1), "
                "api.us.gov.crowdstrike.com (US-GOV-1)."
            ),
        ),
    ],
    steps=[
        SetupStep(
            n=1,
            title="Identify your Falcon cloud",
            body=(
                "Note the host portion of your Falcon console URL (us-2, eu-1, etc.). You will pick "
                "this in the URIP wizard's **Falcon Cloud** dropdown."
            ),
        ),
        SetupStep(
            n=2,
            title="Create an API client",
            body=(
                "Falcon Console → Support → **API Clients and Keys** → **Add new API client**. "
                "Name: `URIP Risk Reader`. Scope (read-only): `Hosts:read`, `Spotlight Vulnerabilities:read`, "
                "`Falcon Surface (EASM):read`, `Cloud Security:read`."
            ),
        ),
        SetupStep(
            n=3,
            title="Capture client ID + secret",
            body=(
                "After **Add**, the dialog shows **Client ID** and **Secret**. Save the secret now — "
                "Falcon does NOT show it again."
            ),
            warning="Copy the Secret immediately — it cannot be retrieved later.",
        ),
        SetupStep(
            n=4,
            title="Paste into URIP",
            body=(
                "URIP → Tool Catalog → CrowdStrike Falcon tile → paste Client ID + Secret, pick "
                "**Falcon Cloud** dropdown matching your tenant, optionally narrow **Enabled Products** → "
                "Test Connection."
            ),
        ),
    ],
    required_scopes=[
        ScopeItem(
            name="Hosts:read",
            description="Resolve agent IDs to hostnames + OS.",
            required=True,
        ),
        ScopeItem(
            name="Spotlight Vulnerabilities:read",
            description="Spotlight VM findings.",
            required=False,
        ),
        ScopeItem(
            name="Falcon Surface:read",
            description="External attack surface findings.",
            required=False,
        ),
        ScopeItem(
            name="Cloud Security:read",
            description="CNAPP findings.",
            required=False,
        ),
    ],
    sample_data={
        "id": "cs-spotlight-vuln-44a-9911",
        "source": "crowdstrike",
        "domain": "endpoint",
        "finding": "CVE-2024-3400 — Palo Alto PAN-OS Command Injection (ExPRT: critical)",
        "asset": "fw-prod-01.example.com",
        "owner_team": "endpoint-ops",
        "cvss_score": 10.0,
        "severity": "critical",
        "epss_score": 0.97,
        "in_kev_catalog": True,
        "exploit_status": "weaponized",
    },
    not_collected=[
        "Process command lines containing credentials",
        "User keystrokes / clipboard data",
        "Memory dumps from incident response captures",
    ],
    common_errors=[
        ErrorFix(
            error="401 invalid_client",
            cause="Client secret mistyped, deleted, or wrong cloud selected.",
            fix=(
                "Falcon Console → API Clients → confirm client is Active. Match Falcon Cloud "
                "dropdown to your console URL host."
            ),
        ),
        ErrorFix(
            error="403 access_denied — scope missing",
            cause="API client lacks the read scope for the target product.",
            fix=(
                "Edit the API client → tick the missing scope (e.g. Spotlight Vulnerabilities:read)."
            ),
        ),
        ErrorFix(
            error="Wrong Falcon Cloud — 404 on /oauth2/token",
            cause="Selected `us-1` while your tenant is on `us-2`.",
            fix="Pick the correct Falcon Cloud in the URIP dropdown to match your console URL host.",
        ),
        ErrorFix(
            error="429 — rate limit",
            cause="Falcon enforces ~6000 req/min per tenant; large tenants hit it during first sync.",
            fix="URIP back-offs; lower polling cadence to 30 min if persistent.",
        ),
    ],
    polling=PollingSpec(
        default_minutes=15,
        first_sync_estimate_minutes=15,
        webhook_supported=False,
        manual_refresh="Tool Catalog → CrowdStrike Falcon tile → Run Now.",
    ),
    disconnect_steps=[
        "Tool Catalog → CrowdStrike Falcon tile → Disable.",
        _CRED_VAULT_DELETE,
        _KEEP_HISTORY,
        "Falcon Console → API Clients → revoke the `URIP Risk Reader` client.",
    ],
    references=[
        "Falcon API reference: https://falcon.us-2.crowdstrike.com/documentation/page/cb1eaaa1/falcon-platform-api-reference",
        "API client setup: https://www.crowdstrike.com/blog/tech-center/get-access-falcon-apis/",
    ],
)


# ─────────────────────────────────────────────────────────────────────────────
# 16. EASM (Censys / Shodan / Detectify)
# ─────────────────────────────────────────────────────────────────────────────


_EASM = SetupGuideSpec(
    quick_facts=QuickFacts(
        category="EASM",
        module="VM",
        difficulty="easy",
        approx_setup_minutes=10,
        vendor_docs_url="https://search.censys.io/api",
        polling_default_minutes=60,
        supports_webhooks=False,
        license_tier_required=(
            "Censys (paid plan with API access) OR Shodan (Membership / paid plan) OR "
            "Detectify (any subscription with API)."
        ),
    ),
    what_pulled=[
        "Externally exposed services (open ports, banners)",
        "TLS certificate hygiene (expired, self-signed)",
        "Subdomain inventory + new-asset discovery",
        "Detectify-found web vulns (when Detectify is provider)",
    ],
    prerequisites=[
        PrereqItem(
            label="License tier",
            requirement=(
                "At least one of: Censys paid plan, Shodan Membership, or Detectify subscription."
            ),
        ),
        PrereqItem(
            label="Admin role",
            requirement="Tenant Admin / Workspace Admin on the chosen provider.",
        ),
        PrereqItem(
            label="Network",
            requirement="Allow URIP egress to api.censys.io / api.shodan.io / api.detectify.com on TCP 443.",
        ),
    ],
    steps=[
        SetupStep(
            n=1,
            title="Pick a provider",
            body="URIP → Tool Catalog → EASM tile → choose **EASM Provider**: censys | shodan | detectify.",
        ),
        SetupStep(
            n=2,
            title="Censys",
            body=(
                "https://search.censys.io/account/api → copy **API ID** and **Secret**. URIP combines "
                "them as `api_token` (basic auth)."
            ),
        ),
        SetupStep(
            n=3,
            title="Shodan",
            body="https://account.shodan.io → copy **API Key**. Paste as **API Key (Shodan)** in URIP.",
        ),
        SetupStep(
            n=4,
            title="Detectify",
            body=(
                "Detectify → Team settings → **API keys** tab (admin permission required) → "
                "**Generate API key**. Paste as **API Token (Censys / Detectify)** in URIP."
            ),
        ),
        SetupStep(
            n=5,
            title="Configure monitored assets",
            body=(
                "Censys + Detectify need a comma-separated list of **Monitored domains** "
                "(e.g. example.com, example.org). Shodan needs **Monitored IPs**. Test Connection."
            ),
        ),
    ],
    required_scopes=[
        ScopeItem(
            name="search:read (Censys)",
            description="Run hosts / certificates queries.",
            required=True,
        ),
        ScopeItem(
            name="api:full (Shodan)",
            description="Standard Shodan paid API key.",
            required=True,
        ),
        ScopeItem(
            name="findings:read (Detectify)",
            description="Read scan findings.",
            required=True,
        ),
    ],
    sample_data={
        "id": "easm-censys-svc-22dd",
        "source": "easm",
        "domain": "external_threat",
        "finding": "RDP exposed (port 3389) with weak NLA on 198.51.100.34",
        "asset": "198.51.100.34",
        "owner_team": "external-surface",
        "cvss_score": 8.5,
        "severity": "high",
    },
    not_collected=[
        "Internal IPs / private-range data — only external surface",
        "Customer data behind authenticated endpoints",
    ],
    common_errors=[
        ErrorFix(
            error="401 — Censys auth failed",
            cause="Pasted only API ID, not the full ID:Secret pair.",
            fix=(
                "URIP combines them automatically when both fields are filled — verify both are present in the wizard."
            ),
        ),
        ErrorFix(
            error="402 Payment Required (Shodan)",
            cause="Free Shodan accounts cannot use the API.",
            fix="Upgrade to a Shodan paid Membership.",
        ),
        ErrorFix(
            error="403 Forbidden (Detectify)",
            cause="API key user lacks team admin permission.",
            fix=(
                "Detectify Team settings → ensure the API key is generated by a team admin."
            ),
        ),
        ErrorFix(
            error="429 — rate limit",
            cause=(
                "Censys: 0.4 q/sec by default. Shodan: 1 q/sec on standard plans. "
                "Detectify: tier-dependent."
            ),
            fix="URIP back-offs automatically; lower poll cadence to hourly if persistent.",
        ),
    ],
    polling=PollingSpec(
        default_minutes=60,
        first_sync_estimate_minutes=10,
        webhook_supported=False,
        manual_refresh="Tool Catalog → EASM tile → Run Now.",
    ),
    disconnect_steps=[
        "Tool Catalog → EASM tile → Disable.",
        _CRED_VAULT_DELETE,
        _KEEP_HISTORY,
        "Optionally rotate the API key in your EASM provider's account.",
    ],
    references=[
        "Censys API: https://search.censys.io/api",
        "Shodan API: https://developer.shodan.io/api",
        "Detectify API: https://developer.detectify.com/",
    ],
)


# ─────────────────────────────────────────────────────────────────────────────
# 17. Armis OT
# ─────────────────────────────────────────────────────────────────────────────


_ARMIS_OT = SetupGuideSpec(
    quick_facts=QuickFacts(
        category="OT",
        module="OT",
        difficulty="medium",
        approx_setup_minutes=15,
        vendor_docs_url="https://docs.armis.com/",
        polling_default_minutes=30,
        supports_webhooks=False,
        license_tier_required="Armis Centrix (paid) — OT/IoMT visibility module enabled.",
    ),
    what_pulled=[
        "OT / IoT asset inventory (PLCs, RTUs, IP cameras, medical devices)",
        "Vulnerabilities tied to each asset",
        "Risk events (anomalous traffic, unauthorized access)",
        "Device classification (vendor, model, function)",
    ],
    prerequisites=[
        PrereqItem(
            label="License tier",
            requirement="Armis Centrix subscription with OT module enabled.",
        ),
        PrereqItem(
            label="Admin role",
            requirement="Armis Tenant Admin (required to mint API tokens).",
        ),
        PrereqItem(
            label="Network",
            requirement="Allow URIP egress to your Armis cloud (e.g. https://your-tenant.armis.com) on TCP 443.",
        ),
    ],
    steps=[
        SetupStep(
            n=1,
            title="Identify your Armis API URL",
            body=(
                "Log in to your Armis console — the URL host (e.g. acme.armis.com) is your Armis tenant. "
                "API base = https://acme.armis.com/api/v1 (URIP appends the path)."
            ),
        ),
        SetupStep(
            n=2,
            title="Create an API token",
            body=(
                "Settings → **API Management** → **Generate Token** → name `urip-readonly` → "
                "permissions = read on devices, vulnerabilities, alerts."
            ),
            warning="Token is shown ONCE — copy now.",
        ),
        SetupStep(
            n=3,
            title="Paste into URIP",
            body=(
                "URIP → Tool Catalog → Armis OT tile → paste **Armis API Base URL** + **API Token**."
            ),
        ),
        SetupStep(
            n=4,
            title="Test Connection and save",
            body=(
                "Click **Test Connection**. URIP calls GET /api/v1/devices?limit=1 and expects HTTP 200. "
                "First sync takes ~20 min for tenants with thousands of OT devices."
            ),
        ),
    ],
    required_scopes=[
        ScopeItem(
            name="devices:read",
            description="Read OT/IoT asset inventory.",
            required=True,
        ),
        ScopeItem(
            name="vulnerabilities:read",
            description="Read vulnerabilities mapped to assets.",
            required=True,
        ),
        ScopeItem(
            name="alerts:read",
            description="Read risk events.",
            required=True,
        ),
    ],
    sample_data={
        "id": "armis-vuln-plc-92113",
        "source": "armis_ot",
        "domain": "ot",
        "finding": "Siemens S7-1500 PLC running firmware with CVE-2024-25101",
        "asset": "PLC-LINE-A-12 / 10.50.7.18",
        "owner_team": "ot-security",
        "cvss_score": 9.1,
        "severity": "critical",
        "cve_id": "CVE-2024-25101",
    },
    not_collected=[
        "Process variable values from PLCs (no DPI of OT protocols' payload)",
        "Patient data from medical devices",
        "Operator login activity",
    ],
    common_errors=[
        ErrorFix(
            error="401 — invalid Armis API token",
            cause="Token revoked or copy-paste truncated.",
            fix="Settings → API Management → confirm token Active, regenerate if needed.",
        ),
        ErrorFix(
            error="403 Forbidden",
            cause="Token role lacks read on devices/vulnerabilities.",
            fix="Edit the token → enable `devices:read`, `vulnerabilities:read`, `alerts:read`.",
        ),
        ErrorFix(
            error="DNS / connection refused",
            cause="Wrong tenant URL or your tenant is on a regional pod (eu1.armis.com).",
            fix="Confirm tenant URL in your Armis console; update the wizard's Base URL.",
        ),
    ],
    polling=PollingSpec(
        default_minutes=30,
        first_sync_estimate_minutes=20,
        webhook_supported=False,
        manual_refresh="Tool Catalog → Armis OT tile → Run Now.",
    ),
    disconnect_steps=[
        "Tool Catalog → Armis OT tile → Disable.",
        _CRED_VAULT_DELETE,
        _KEEP_HISTORY,
        "Optionally revoke the API token in Armis Settings → API Management.",
    ],
    references=[
        "Armis docs: https://docs.armis.com/",
    ],
)


# ─────────────────────────────────────────────────────────────────────────────
# 18. Forescout / Cisco ISE — NAC
# ─────────────────────────────────────────────────────────────────────────────


_FORESCOUT_NAC = SetupGuideSpec(
    quick_facts=QuickFacts(
        category="NAC",
        module="NETWORK",
        difficulty="hard",
        approx_setup_minutes=45,
        vendor_docs_url="https://docs.forescout.com/bundle/web-api-1-5-4-h/page/c-about-eyeextend-connect-module-web-api.html",
        polling_default_minutes=15,
        supports_webhooks=False,
        license_tier_required=(
            "Forescout eyeSight (paid) with Web API plugin — OR — "
            "Cisco ISE 2.7+ with ERS API enabled."
        ),
    ),
    what_pulled=[
        "Rogue / unknown device alerts",
        "NAC policy violations (host failed posture)",
        "Device classification (vendor, OS, function)",
        "Last-seen + connected switch/port",
    ],
    prerequisites=[
        PrereqItem(
            label="NAC vendor",
            requirement="Forescout eyeSight OR Cisco Identity Services Engine (ISE) — pick one in the wizard.",
        ),
        PrereqItem(
            label="Admin role",
            requirement=(
                "Forescout — Console Admin (Web API plugin enabled). "
                "Cisco ISE — Super Admin (to enable ERS + create the ERS-Admin user)."
            ),
        ),
        PrereqItem(
            label="Network",
            requirement="Allow URIP egress to the NAC management port (443 Forescout / 9060 Cisco ISE).",
        ),
    ],
    steps=[
        SetupStep(
            n=1,
            title="Forescout — install Web API plugin",
            body=(
                "Forescout Console → Settings → **Modules** → search 'Web API' → install + start. "
                "Click **Configure** → set port (443) → save."
            ),
        ),
        SetupStep(
            n=2,
            title="Forescout — create OAuth client",
            body=(
                "Web API plugin → **User Settings** tab → create user. Save **Client ID** and "
                "**Client Secret** for OAuth."
            ),
        ),
        SetupStep(
            n=3,
            title="Cisco ISE — enable ERS",
            body=(
                "ISE Console → Administration → System → Settings → **API Settings** → toggle **ERS (Read/Write)**. "
                "Then Administration → Identity Management → Admins → create admin in group **ERS-Admin** "
                "(or **ERS-Operator** for read-only)."
            ),
        ),
        SetupStep(
            n=4,
            title="Paste into URIP",
            body=(
                "URIP → Tool Catalog → Network Access Control tile → choose **NAC Vendor** → paste "
                "Base URL + (Forescout: Client ID + Client Secret) OR (Cisco ISE: Username + Password) → "
                "Test Connection."
            ),
        ),
    ],
    required_scopes=[
        ScopeItem(
            name="Web API user (Forescout)",
            description="Read endpoints + alerts.",
            required=True,
        ),
        ScopeItem(
            name="ERS-Admin / ERS-Operator (Cisco ISE)",
            description="Read endpoints + sessions via ERS API.",
            required=True,
        ),
    ],
    sample_data={
        "id": "nac-forescout-rogue-7733",
        "source": "forescout_nac",
        "domain": "network",
        "finding": "Rogue device detected: unknown MAC connected to switch core-sw1 port Gi1/0/24",
        "asset": "MAC=aa:bb:cc:dd:ee:ff (switch core-sw1 / Gi1/0/24)",
        "owner_team": "network-security",
        "cvss_score": 6.5,
        "severity": "medium",
    },
    not_collected=[
        "User credentials seen during 802.1X auth",
        "Captive portal POST bodies",
    ],
    common_errors=[
        ErrorFix(
            error="Forescout: 401 invalid_client",
            cause="OAuth client ID/secret mistyped or Web API plugin not started.",
            fix=(
                "Forescout Console → Modules → confirm Web API plugin status = Started. "
                "Edit the user, capture client_id/secret again."
            ),
        ),
        ErrorFix(
            error="Cisco ISE: 401 on /ers/config",
            cause="ERS not enabled or admin user not in ERS-Admin/Operator group.",
            fix=(
                "Administration → System → Settings → API Settings → enable ERS. "
                "Add the user to the ERS-Admin group."
            ),
        ),
        ErrorFix(
            error="Connection refused on port 9060 (ISE)",
            cause="Cisco ISE serves ERS on a separate port — firewall blocks it.",
            fix="Open 9060/tcp from URIP to ISE PAN node.",
        ),
        ErrorFix(
            error="SSL self-signed",
            cause="On-prem NAC with default cert.",
            fix="Install a CA cert on the NAC, or contact URIP support to allow-list its hash.",
        ),
    ],
    polling=PollingSpec(
        default_minutes=15,
        first_sync_estimate_minutes=20,
        webhook_supported=False,
        manual_refresh="Tool Catalog → Network Access Control tile → Run Now.",
    ),
    disconnect_steps=[
        "Tool Catalog → Network Access Control tile → Disable.",
        _CRED_VAULT_DELETE,
        _KEEP_HISTORY,
        "Optionally remove the OAuth client (Forescout) or ERS-Admin user (Cisco ISE).",
    ],
    references=[
        "Forescout Web API: https://docs.forescout.com/bundle/web-api-1-5-4-h/page/c-about-eyeextend-connect-module-web-api.html",
        "Cisco ISE ERS API: https://developer.cisco.com/docs/identity-services-engine/latest/setting-up/",
    ],
)


# ─────────────────────────────────────────────────────────────────────────────
# 19. CyberArk Privileged Access (PAM)
# ─────────────────────────────────────────────────────────────────────────────


_CYBERARK_PAM = SetupGuideSpec(
    quick_facts=QuickFacts(
        category="PAM",
        module="IDENTITY",
        difficulty="hard",
        approx_setup_minutes=45,
        vendor_docs_url="https://docs.cyberark.com/pam-self-hosted/latest/en/content/webservices/implementing%20privileged%20account%20security%20web%20services%20.htm",
        polling_default_minutes=15,
        supports_webhooks=False,
        license_tier_required="CyberArk PAM Self-Hosted or Privilege Cloud (paid).",
    ),
    what_pulled=[
        "Vault access logs (who accessed what + when)",
        "Privileged session anomalies",
        "Shared credential usage events",
        "Failed authentication patterns",
    ],
    prerequisites=[
        PrereqItem(
            label="License tier",
            requirement="CyberArk PAM Self-Hosted or Privilege Cloud — both expose PVWA REST API.",
        ),
        PrereqItem(
            label="Admin role",
            requirement="Vault Admin able to provision an API user + run APIKeyManager utility.",
        ),
        PrereqItem(
            label="Network",
            requirement="Allow URIP egress to the PVWA URL on TCP 443.",
        ),
        PrereqItem(
            label="Tools",
            requirement=(
                "APIKeyManager utility (CyberArk Marketplace) to mint the public/private key pair."
            ),
        ),
    ],
    steps=[
        SetupStep(
            n=1,
            title="Create the API user in the Vault",
            body=(
                "PrivateArk → Tools → User Management → New User → name `urip-api`. "
                "Permissions: read access to audit feeds + safes you want monitored. NO Vault admin rights."
            ),
        ),
        SetupStep(
            n=2,
            title="Generate API key pair",
            body=(
                "Download **APIKeyManager** from CyberArk Marketplace. Run with the `urip-api` username "
                "to generate a public/private key pair. The Vault stores the public part automatically; "
                "you keep the private key file."
            ),
            warning="Treat the private key file like a password.",
        ),
        SetupStep(
            n=3,
            title="Test API access",
            body=(
                "Use the documented PVWA `Logon` API call with `?logontype=APIKey` and the private "
                "key — confirm you receive a session token."
            ),
        ),
        SetupStep(
            n=4,
            title="Paste into URIP",
            body=(
                "URIP → Tool Catalog → CyberArk Privileged Access tile → paste **PVWA Base URL** "
                "(e.g. https://pvwa.example) + **API Key** (private key contents) → Test Connection."
            ),
        ),
    ],
    required_scopes=[
        ScopeItem(
            name="Audit Users / Auditor role",
            description="Read access to vault audit feed.",
            required=True,
        ),
        ScopeItem(
            name="Safe Members read",
            description="Visibility into safes whose access you want to monitor.",
            required=False,
        ),
    ],
    sample_data={
        "id": "cyberark-audit-vault-9911-3344",
        "source": "cyberark_pam",
        "domain": "identity",
        "finding": "Account `domain\\\\admin` retrieved from Safe `Domain-Admins` outside change window",
        "asset": "Safe: Domain-Admins / User: ops-engineer-12",
        "owner_team": "identity-team",
        "cvss_score": 7.5,
        "severity": "high",
    },
    not_collected=[
        "Plain-text passwords stored inside the vault (never returned by API)",
        "Session video recordings (large binaries)",
        "User personal data outside Vault audit fields",
    ],
    common_errors=[
        ErrorFix(
            error="401 ITATS001E — Authentication failed",
            cause="Wrong logon type (APIKey vs LDAP) or private-key file corrupt.",
            fix=(
                "Confirm `?logontype=APIKey` in API call. Re-mint the key pair via APIKeyManager."
            ),
        ),
        ErrorFix(
            error="403 PASWS027E — User has no permissions on this Safe",
            cause="API user not added to the safes you want to monitor.",
            fix="PrivateArk → Safe → Members → add `urip-api` with Audit Users.",
        ),
        ErrorFix(
            error="500 — Concurrent sessions exhausted",
            cause="CyberArk caps concurrent sessions per user (default 10).",
            fix="Reduce poll interval or increase the limit in Vault user properties.",
        ),
        ErrorFix(
            error="SSL self-signed certificate",
            cause="On-prem PVWA with default cert.",
            fix="Install a CA-signed cert on PVWA, or contact URIP support to allow-list the cert hash.",
        ),
    ],
    polling=PollingSpec(
        default_minutes=15,
        first_sync_estimate_minutes=15,
        webhook_supported=False,
        manual_refresh="Tool Catalog → CyberArk Privileged Access tile → Run Now.",
    ),
    disconnect_steps=[
        "Tool Catalog → CyberArk Privileged Access tile → Disable.",
        _CRED_VAULT_DELETE,
        _KEEP_HISTORY,
        "Optionally disable the `urip-api` user in PrivateArk.",
    ],
    references=[
        "PVWA REST API: https://docs.cyberark.com/pam-self-hosted/latest/en/content/webservices/implementing%20privileged%20account%20security%20web%20services%20.htm",
        "APIKey authentication: https://docs.cyberark.com/pam-self-hosted/latest/en/content/sdk/rest%20web%20services%20api%20-%20cyberark%20authentication.htm",
        "APIKeyManager utility: https://docs.cyberark.com/pam-self-hosted/latest/en/content/pasimp/apikeymanager.htm",
    ],
)


# ─────────────────────────────────────────────────────────────────────────────
# 20. Fortinet Fortiguard Firewall
# ─────────────────────────────────────────────────────────────────────────────


_FORTIGUARD_FW = SetupGuideSpec(
    quick_facts=QuickFacts(
        category="FIREWALL",
        module="NETWORK",
        difficulty="medium",
        approx_setup_minutes=20,
        vendor_docs_url="https://docs.fortinet.com/document/fortigate/latest/administration-guide/",
        polling_default_minutes=15,
        supports_webhooks=False,
        license_tier_required="FortiGate (any model with IPS / FortiGuard subscription).",
    ),
    what_pulled=[
        "Blocked threats (IPS, antivirus, web filter)",
        "Connection / drop logs (CEF format)",
        "Source / destination IP, geo, application",
        "Severity, threat name, signature ID",
    ],
    prerequisites=[
        PrereqItem(
            label="License tier",
            requirement="FortiGate with FortiGuard IPS subscription (active).",
        ),
        PrereqItem(
            label="Admin role",
            requirement=(
                "FortiGate super_admin (to mint API tokens for API mode) — OR — "
                "syslog/CEF collector that forwards events to URIP for syslog mode."
            ),
        ),
        PrereqItem(
            label="Network",
            requirement=(
                "API mode: TCP 443 from URIP to FortiGate management. "
                "Syslog mode: UDP/TCP 514 from your collector to URIP's ingest endpoint."
            ),
        ),
    ],
    steps=[
        SetupStep(
            n=1,
            title="Choose ingest mode",
            body=(
                "URIP → Tool Catalog → Fortinet Fortiguard tile → **Ingest Mode**: "
                "**syslog** (when an existing SIEM/collector forwards CEF) or **api** (FortiGate REST polling)."
            ),
        ),
        SetupStep(
            n=2,
            title="API mode — create API admin",
            body=(
                "FortiGate GUI → System → Administrators → **+ Create New** → name `urip-api` → "
                "type **REST API Admin** → trusted hosts = URIP's egress subnet → role read-only. Save."
            ),
        ),
        SetupStep(
            n=3,
            title="API mode — generate token",
            body=(
                "On save, FortiGate displays a one-time **API Token**. Copy it now — it cannot be retrieved later."
            ),
            warning="Token is shown ONCE. Save to your password vault.",
        ),
        SetupStep(
            n=4,
            title="Syslog mode — point your collector",
            body=(
                "Configure your existing CEF collector / FortiAnalyzer to forward `type=traffic` and "
                "`type=utm` events to URIP's ingest URL (shown in the wizard on save)."
            ),
        ),
        SetupStep(
            n=5,
            title="Paste into URIP",
            body=(
                "Paste **FortiGate Base URL** + **API Token** (API mode) → Test Connection. "
                "For syslog mode, no credentials are needed beyond ingest URL."
            ),
        ),
    ],
    required_scopes=[
        ScopeItem(
            name="REST API Admin (read-only)",
            description="Read traffic logs + UTM events via /api/v2/log.",
            required=True,
        ),
    ],
    sample_data={
        "id": "fg-utm-ips-block-77a-321",
        "source": "fortiguard_fw",
        "domain": "network",
        "finding": "IPS blocked exploit attempt: Apache Log4j JNDI injection (sig 51883)",
        "asset": "external 198.51.100.7 → internal app-server-01",
        "owner_team": "network-security",
        "cvss_score": 9.0,
        "severity": "critical",
        "exploit_status": "weaponized",
    },
    not_collected=[
        "Full packet captures",
        "User session content (only metadata)",
    ],
    common_errors=[
        ErrorFix(
            error="API mode: 401 invalid_token",
            cause="API admin's trusted-hosts list excludes the URIP egress IP.",
            fix=(
                "FortiGate → System → Administrators → edit `urip-api` → add URIP's egress subnet "
                "to trusted hosts."
            ),
        ),
        ErrorFix(
            error="Syslog mode: events arrive but no findings created",
            cause="CEF format mismatch — collector sending Fortinet-native syslog instead of CEF.",
            fix=(
                "FortiAnalyzer / collector → set output format to CEF (RFC 5424 with CEF body) and "
                "point to URIP's ingest URL."
            ),
        ),
        ErrorFix(
            error="503 — FortiGuard subscription expired",
            cause="No active IPS / FortiGuard subscription, so no signatures.",
            fix="Renew the FortiGuard subscription on the FortiGate.",
        ),
        ErrorFix(
            error="429 — too many API calls",
            cause="FortiGate REST API enforces ~120 req/min.",
            fix="Lower poll interval to 30 min if persistent, or switch to syslog mode.",
        ),
    ],
    polling=PollingSpec(
        default_minutes=15,
        first_sync_estimate_minutes=10,
        webhook_supported=False,
        manual_refresh="Tool Catalog → Fortinet Fortiguard tile → Run Now (API mode only).",
    ),
    disconnect_steps=[
        "Tool Catalog → Fortinet Fortiguard tile → Disable.",
        _CRED_VAULT_DELETE,
        _KEEP_HISTORY,
        "Optionally delete the `urip-api` REST API Admin in FortiGate.",
    ],
    references=[
        "FortiGate REST API: https://docs.fortinet.com/document/fortigate/latest/administration-guide/",
        "CEF event format: https://docs.fortinet.com/document/fortianalyzer/latest/administration-guide/",
    ],
)


# ─────────────────────────────────────────────────────────────────────────────
# 21. Microsoft 365 Collaboration (SharePoint / OneDrive / Teams)
# ─────────────────────────────────────────────────────────────────────────────


_M365_COLLAB = SetupGuideSpec(
    quick_facts=QuickFacts(
        category="COLLABORATION",
        module="COLLABORATION",
        difficulty="medium",
        approx_setup_minutes=25,
        vendor_docs_url="https://learn.microsoft.com/en-us/graph/api/overview",
        polling_default_minutes=30,
        supports_webhooks=False,
        license_tier_required="Microsoft 365 Business or Enterprise (E3/E5) — Graph API access required.",
    ),
    what_pulled=[
        "SharePoint anonymous link sharing events",
        "OneDrive external sharing (link grants to outside users)",
        "Teams data exposure events (guests in private channels, file leaks)",
        "Audit log entries for sensitive actions",
    ],
    prerequisites=[
        PrereqItem(
            label="License tier",
            requirement="Microsoft 365 Business or Enterprise (E3/E5).",
        ),
        PrereqItem(
            label="Admin role",
            requirement="Global Admin or Privileged Role Admin (to grant admin consent).",
        ),
        PrereqItem(
            label="Network",
            requirement="Allow URIP egress to https://login.microsoftonline.com + https://graph.microsoft.com on TCP 443.",
        ),
    ],
    steps=[
        SetupStep(
            n=1,
            title="Register an app",
            body=(
                "Azure Portal → Microsoft Entra ID → App registrations → **+ New registration** → "
                "name `URIP Collab Reader`. Save Tenant ID + Application (client) ID."
            ),
        ),
        SetupStep(
            n=2,
            title="Add Graph permissions (application)",
            body=(
                "App → API permissions → Add → Microsoft Graph → **Application permissions** → tick: "
                "`Sites.Read.All`, `Files.Read.All`, `Team.ReadBasic.All`, `Channel.ReadBasic.All`, "
                "`AuditLog.Read.All`."
            ),
        ),
        SetupStep(
            n=3,
            title="Grant admin consent",
            body=(
                "Same page → **Grant admin consent for <tenant>**. Status column should turn green for every permission."
            ),
        ),
        SetupStep(
            n=4,
            title="Create client secret",
            body=(
                "App → Certificates & secrets → New client secret → 24 months → Add. Copy the **Value**."
            ),
            warning="Secret Value shown ONCE.",
        ),
        SetupStep(
            n=5,
            title="Paste into URIP",
            body=(
                "URIP → Tool Catalog → Microsoft 365 Collaboration tile → paste Tenant ID, Client ID, Client Secret → "
                "Test Connection."
            ),
        ),
    ],
    required_scopes=[
        ScopeItem(name="Sites.Read.All", description="Read SharePoint site properties + sharing.", required=True),
        ScopeItem(name="Files.Read.All", description="Read OneDrive files for sharing context.", required=True),
        ScopeItem(name="Team.ReadBasic.All", description="Read Teams memberships + guest users.", required=True),
        ScopeItem(name="Channel.ReadBasic.All", description="Read channel metadata.", required=True),
        ScopeItem(name="AuditLog.Read.All", description="Read tenant-wide audit events.", required=True),
    ],
    sample_data={
        "id": "m365-share-anon-44ab",
        "source": "m365_collab",
        "domain": "collaboration",
        "finding": "Anonymous sharing link created on SharePoint document containing 'salary' in filename",
        "asset": "https://contoso.sharepoint.com/sites/HR/Docs/2026_Salaries.xlsx",
        "owner_team": "data-protection",
        "cvss_score": 7.5,
        "severity": "high",
    },
    not_collected=[
        "Document content (only metadata + sharing state)",
        "Chat / call recordings",
        "User personal device info",
    ],
    common_errors=[
        ErrorFix(
            error="AADSTS65001 admin consent required",
            cause="Step 3 not completed.",
            fix="App registration → API permissions → Grant admin consent for <tenant>.",
        ),
        ErrorFix(
            error="403 — Sites.Selected required for narrow site access",
            cause="Tenant uses Sites.Selected model — application not granted on each site.",
            fix=(
                "Run `New-PnPAzureADAppSitePermission` for each site you want URIP to read, OR "
                "grant the broader `Sites.Read.All`."
            ),
        ),
        ErrorFix(
            error="429 — Graph throttling",
            cause="Burst rate limit. Tenants with many sites hit it on first sync.",
            fix="URIP back-offs automatically; lower polling cadence if persistent.",
        ),
        ErrorFix(
            error="Audit log empty",
            cause="Audit log search not enabled in Microsoft Purview.",
            fix=(
                "Microsoft Purview → Audit → **Start recording user and admin activity**. "
                "(One-time tenant-wide setting.)"
            ),
        ),
    ],
    polling=PollingSpec(
        default_minutes=30,
        first_sync_estimate_minutes=15,
        webhook_supported=False,
        manual_refresh="Tool Catalog → Microsoft 365 Collaboration tile → Run Now.",
    ),
    disconnect_steps=[
        "Tool Catalog → Microsoft 365 Collaboration tile → Disable.",
        _CRED_VAULT_DELETE,
        _KEEP_HISTORY,
        "Optionally delete the `URIP Collab Reader` app registration.",
    ],
    references=[
        "Microsoft Graph: https://learn.microsoft.com/en-us/graph/api/overview",
        "Audit log API: https://learn.microsoft.com/en-us/graph/api/security-auditlogquery-get",
    ],
)


# ─────────────────────────────────────────────────────────────────────────────
# 22. ManageEngine Endpoint Central (EDR / Patch)
# ─────────────────────────────────────────────────────────────────────────────


_ME_EC = SetupGuideSpec(
    quick_facts=QuickFacts(
        category="EDR",
        module="EDR",
        difficulty="easy",
        approx_setup_minutes=15,
        vendor_docs_url="https://www.manageengine.com/products/desktop-central/api/",
        polling_default_minutes=15,
        supports_webhooks=False,
        license_tier_required="ManageEngine Endpoint Central (Professional or Enterprise).",
    ),
    what_pulled=[
        "Patch status per endpoint",
        "Missing critical / important patches (CVE-tagged)",
        "Per-endpoint compliance score",
        "Failed deployments / rollback events",
    ],
    prerequisites=[
        PrereqItem(
            label="License tier",
            requirement="Endpoint Central Professional or Enterprise (Free does not expose API).",
        ),
        PrereqItem(
            label="Admin role",
            requirement="Endpoint Central Admin able to mint API tokens.",
        ),
        PrereqItem(
            label="Network",
            requirement="Allow URIP egress to your Endpoint Central server (TCP 443 / 8020).",
        ),
    ],
    steps=[
        SetupStep(
            n=1,
            title="Generate API token",
            body=(
                "Endpoint Central → Admin → **API Token** → **Generate Token**. Copy the value."
            ),
            warning="Token is shown ONCE.",
        ),
        SetupStep(
            n=2,
            title="Capture base URL",
            body=(
                "Note the host portion of your Endpoint Central console URL "
                "(e.g. https://endpointcentral.example.com)."
            ),
        ),
        SetupStep(
            n=3,
            title="Paste into URIP",
            body=(
                "URIP → Tool Catalog → ManageEngine Endpoint Central tile → paste Base URL + API Token."
            ),
        ),
        SetupStep(
            n=4,
            title="Test Connection and save",
            body=(
                "Click **Test Connection**. URIP calls GET /patch/api/missingPatches with limit=1 "
                "and expects HTTP 200. On success, save the configuration."
            ),
        ),
    ],
    required_scopes=[
        ScopeItem(
            name="Read on Patch + Inventory APIs",
            description="Required for patch status + endpoint compliance pulls.",
            required=True,
        ),
    ],
    sample_data={
        "id": "ec-missing-patch-ms24-001",
        "source": "manageengine_ec",
        "domain": "endpoint",
        "finding": "Missing critical patch KB5034441 (CVE-2024-20666) on 23 endpoints",
        "asset": "Workstation pool: ENG-* (23 hosts)",
        "owner_team": "endpoint-ops",
        "cvss_score": 7.8,
        "severity": "high",
        "cve_id": "CVE-2024-20666",
    },
    not_collected=[
        "Document / file contents on endpoints",
        "User keystrokes",
    ],
    common_errors=[
        ErrorFix(
            error="401 INVALID_TOKEN",
            cause="API token rotated by another admin or copied with whitespace.",
            fix="Admin → API Token → regenerate; trim whitespace when pasting.",
        ),
        ErrorFix(
            error="403 — Admin not allowed for this scope",
            cause="API admin user role is Technician, not Admin.",
            fix="Promote the user, or generate the token from an Admin account.",
        ),
        ErrorFix(
            error="SSL handshake failed",
            cause="Self-signed certificate on on-prem Endpoint Central.",
            fix="Install a CA cert, or contact URIP support to allow-list the cert hash.",
        ),
    ],
    polling=PollingSpec(
        default_minutes=15,
        first_sync_estimate_minutes=10,
        webhook_supported=False,
        manual_refresh="Tool Catalog → ManageEngine Endpoint Central tile → Run Now.",
    ),
    disconnect_steps=[
        "Tool Catalog → ManageEngine Endpoint Central tile → Disable.",
        _CRED_VAULT_DELETE,
        _KEEP_HISTORY,
        "Admin → API Token → revoke the token.",
    ],
    references=[
        "Endpoint Central API: https://www.manageengine.com/products/desktop-central/api/",
    ],
)


# ─────────────────────────────────────────────────────────────────────────────
# 23. ManageEngine MDM
# ─────────────────────────────────────────────────────────────────────────────


_ME_MDM = SetupGuideSpec(
    quick_facts=QuickFacts(
        category="EDR",
        module="EDR",
        difficulty="easy",
        approx_setup_minutes=15,
        vendor_docs_url="https://www.manageengine.com/mobile-device-management/help/api/",
        polling_default_minutes=15,
        supports_webhooks=False,
        license_tier_required="ManageEngine MDM (paid tier, Cloud or On-Prem).",
    ),
    what_pulled=[
        "Jailbroken / rooted device alerts",
        "Non-compliant mobile asset inventory",
        "Lost / stolen / wiped events",
        "OS / patch level per device",
    ],
    prerequisites=[
        PrereqItem(
            label="License tier",
            requirement="ManageEngine MDM (paid). Free tier limits APIs.",
        ),
        PrereqItem(
            label="Admin role",
            requirement="MDM Tenant Admin (to mint API token).",
        ),
        PrereqItem(
            label="Network",
            requirement="Allow URIP egress to your MDM server (TCP 443).",
        ),
    ],
    steps=[
        SetupStep(
            n=1,
            title="Generate API token",
            body=(
                "MDM Console → Admin → **API Token** → Generate. Copy the value (shown once)."
            ),
            warning="Token is shown ONCE — save now.",
        ),
        SetupStep(
            n=2,
            title="Capture base URL",
            body=(
                "Note your MDM URL host (e.g. https://mdm.example.com)."
            ),
        ),
        SetupStep(
            n=3,
            title="Paste into URIP",
            body=(
                "URIP → Tool Catalog → ManageEngine MDM tile → paste Base URL + API Token."
            ),
        ),
        SetupStep(
            n=4,
            title="Test Connection and save",
            body=(
                "Click **Test Connection**. URIP calls GET /api/v1/devices?limit=1 and expects HTTP 200. "
                "Save the configuration on success."
            ),
        ),
    ],
    required_scopes=[
        ScopeItem(
            name="Devices read",
            description="Required to list managed devices + compliance state.",
            required=True,
        ),
    ],
    sample_data={
        "id": "mdm-noncompliance-jailbroken-7711",
        "source": "manageengine_mdm",
        "domain": "endpoint",
        "finding": "Jailbroken iPhone detected: device-id 482ff (user: alice@example.com)",
        "asset": "iPhone 14 Pro (482ff…) / alice@example.com",
        "owner_team": "endpoint-ops",
        "cvss_score": 7.5,
        "severity": "high",
    },
    not_collected=[
        "Personal app data on managed devices",
        "Photos / contacts / messages",
    ],
    common_errors=[
        ErrorFix(
            error="401 INVALID_TOKEN",
            cause="Token revoked or wrong scope.",
            fix="Admin → API Token → regenerate.",
        ),
        ErrorFix(
            error="403 Forbidden",
            cause="Token bound to a tenant the user no longer admins.",
            fix="Generate the token from a current Tenant Admin account.",
        ),
        ErrorFix(
            error="429 — too many requests",
            cause="MDM API rate limit (~60 req/min).",
            fix="Lower polling cadence to 30 min if persistent.",
        ),
    ],
    polling=PollingSpec(
        default_minutes=15,
        first_sync_estimate_minutes=10,
        webhook_supported=False,
        manual_refresh="Tool Catalog → ManageEngine MDM tile → Run Now.",
    ),
    disconnect_steps=[
        "Tool Catalog → ManageEngine MDM tile → Disable.",
        _CRED_VAULT_DELETE,
        _KEEP_HISTORY,
        "Admin → API Token → revoke.",
    ],
    references=[
        "MDM API docs: https://www.manageengine.com/mobile-device-management/help/api/",
    ],
)


# ─────────────────────────────────────────────────────────────────────────────
# 24. Burp Suite Enterprise (DAST)
# ─────────────────────────────────────────────────────────────────────────────


_BURP_ENT = SetupGuideSpec(
    quick_facts=QuickFacts(
        category="DAST",
        module="DAST",
        difficulty="easy",
        approx_setup_minutes=15,
        vendor_docs_url="https://portswigger.net/burp/documentation/enterprise/api-documentation",
        polling_default_minutes=30,
        supports_webhooks=False,
        license_tier_required="Burp Suite Enterprise Edition (paid).",
    ),
    what_pulled=[
        "DAST scan findings (XSS, SQLi, IDOR, etc.)",
        "Severity (critical / high / medium / low)",
        "Affected URL + reproduction request",
        "Scan + site metadata",
    ],
    prerequisites=[
        PrereqItem(
            label="License tier",
            requirement="Burp Suite Enterprise Edition.",
        ),
        PrereqItem(
            label="Admin role",
            requirement="Burp Suite Enterprise Administrator (to add API user).",
        ),
        PrereqItem(
            label="Network",
            requirement="Allow URIP egress to your Burp Enterprise server URL on TCP 443.",
        ),
    ],
    steps=[
        SetupStep(
            n=1,
            title="Add an API user",
            body=(
                "Burp Suite Enterprise → log in as Administrator → **Team** → **Add a new user** → "
                "name = `URIP API`, login type = **API Key** → save."
            ),
        ),
        SetupStep(
            n=2,
            title="Capture API key + URL",
            body=(
                "On save, a dialog shows the **API Key** + **API URL** — copy both. They cannot be retrieved later."
            ),
            warning="Both values are shown ONCE.",
        ),
        SetupStep(
            n=3,
            title="Paste into URIP",
            body=(
                "URIP → Tool Catalog → Burp Suite Enterprise tile → paste Base URL + API Key."
            ),
        ),
        SetupStep(
            n=4,
            title="Test Connection and save",
            body=(
                "Click **Test Connection**. URIP calls GraphQL `query { sites { id, name } }` "
                "via the Enterprise REST endpoint and expects HTTP 200. On success, save."
            ),
        ),
    ],
    required_scopes=[
        ScopeItem(
            name="API user (read)",
            description="Read scans + issues for all sites.",
            required=True,
        ),
    ],
    sample_data={
        "id": "burp-issue-xss-3344",
        "source": "burp_enterprise",
        "domain": "application",
        "finding": "Reflected XSS in /search?q= parameter — high confidence",
        "asset": "https://app.example.com/search",
        "owner_team": "appsec",
        "cvss_score": 7.5,
        "severity": "high",
    },
    not_collected=[
        "Production application response bodies (only finding evidence excerpts)",
        "User session tokens captured during scan",
    ],
    common_errors=[
        ErrorFix(
            error="401 — invalid API key",
            cause="API user disabled or key replaced.",
            fix="Burp Enterprise → Team → user → Reset API Key → re-paste in URIP.",
        ),
        ErrorFix(
            error="403 — user has no site access",
            cause="API user not assigned to any sites.",
            fix="Burp Enterprise → Sites → grant the API user read on relevant sites.",
        ),
        ErrorFix(
            error="429 — rate limit exceeded",
            cause="Burp Enterprise REST API caps to 1000 req/hour by default.",
            fix="Set **Max requests / hour** in URIP wizard to 800 to leave headroom.",
        ),
    ],
    polling=PollingSpec(
        default_minutes=30,
        first_sync_estimate_minutes=10,
        webhook_supported=False,
        manual_refresh="Tool Catalog → Burp Suite Enterprise tile → Run Now.",
    ),
    disconnect_steps=[
        "Tool Catalog → Burp Suite Enterprise tile → Disable.",
        _CRED_VAULT_DELETE,
        _KEEP_HISTORY,
        "Burp Enterprise → Team → delete or disable the URIP API user.",
    ],
    references=[
        "Burp Enterprise API: https://portswigger.net/burp/documentation/enterprise/api-documentation",
        "Creating API users: https://portswigger.net/burp/documentation/enterprise/api-documentation/create-api-user",
    ],
)


# ─────────────────────────────────────────────────────────────────────────────
# 25. GTB Endpoint Protector (DLP)
# ─────────────────────────────────────────────────────────────────────────────


_GTB = SetupGuideSpec(
    quick_facts=QuickFacts(
        category="DLP",
        module="DLP",
        difficulty="medium",
        approx_setup_minutes=20,
        vendor_docs_url="https://www.gtbtechnologies.com/support/api-documentation",
        polling_default_minutes=15,
        supports_webhooks=False,
        license_tier_required="GTB Inspector / Endpoint Protector — paid suite.",
    ),
    what_pulled=[
        "DLP policy violations",
        "USB block events",
        "Data exfiltration attempts (HTTP/SMTP/FTP)",
        "Per-policy + per-channel statistics",
    ],
    prerequisites=[
        PrereqItem(
            label="License tier",
            requirement="GTB Endpoint Protector / Inspector — paid.",
        ),
        PrereqItem(
            label="Admin role",
            requirement="GTB Console Super Admin (required to mint API key).",
        ),
        PrereqItem(
            label="Network",
            requirement="Allow URIP egress to your GTB management server on TCP 443.",
        ),
    ],
    steps=[
        SetupStep(
            n=1,
            title="Open API integration",
            body=(
                "GTB Console → Admin → **API Integration** → **Generate API Key**. Copy the value."
            ),
            warning="API key shown ONCE — save now.",
        ),
        SetupStep(
            n=2,
            title="Capture base URL",
            body=(
                "Note your GTB management server URL (e.g. https://gtb.example.com)."
            ),
        ),
        SetupStep(
            n=3,
            title="Paste into URIP",
            body=(
                "URIP → Tool Catalog → GTB Endpoint Protector tile → paste Base URL + API Key."
            ),
        ),
        SetupStep(
            n=4,
            title="Test Connection and save",
            body=(
                "Click **Test Connection**. URIP calls GET /api/v1/incidents?limit=1 and expects HTTP 200. "
                "Save the configuration on success."
            ),
        ),
    ],
    required_scopes=[
        ScopeItem(
            name="Read on Incidents + Policies",
            description="Required for DLP event ingestion.",
            required=True,
        ),
    ],
    sample_data={
        "id": "gtb-incident-usb-blocked-1182",
        "source": "gtb",
        "domain": "endpoint",
        "finding": "USB write blocked: 'customer_list_2026.csv' to unauthorised USB",
        "asset": "Workstation FIN-LAPTOP-007 / user: bob@example.com",
        "owner_team": "data-protection",
        "cvss_score": 7.0,
        "severity": "high",
    },
    not_collected=[
        "File contents that triggered the DLP rule (only policy + filename)",
        "Personal browsing history",
    ],
    common_errors=[
        ErrorFix(
            error="401 — API key invalid",
            cause="Key revoked or copied with whitespace.",
            fix="GTB Admin → API Integration → confirm Active, regenerate if needed.",
        ),
        ErrorFix(
            error="403 — endpoint not enabled",
            cause="API integration toggle off at the suite level.",
            fix="Admin → API Integration → ensure REST API is **Enabled**.",
        ),
        ErrorFix(
            error="SSL certificate error",
            cause="On-prem GTB with self-signed cert.",
            fix="Install a CA cert on the GTB management server.",
        ),
        ErrorFix(
            error="429 — Max requests / hour exceeded",
            cause="Default 500 req/hr cap on GTB API.",
            fix="Set **Max requests / hour** in URIP to 400.",
        ),
    ],
    polling=PollingSpec(
        default_minutes=15,
        first_sync_estimate_minutes=10,
        webhook_supported=False,
        manual_refresh="Tool Catalog → GTB Endpoint Protector tile → Run Now.",
    ),
    disconnect_steps=[
        "Tool Catalog → GTB Endpoint Protector tile → Disable.",
        _CRED_VAULT_DELETE,
        _KEEP_HISTORY,
        "Admin → API Integration → revoke the API key.",
    ],
    references=[
        "GTB API: https://www.gtbtechnologies.com/support/api-documentation",
        "Endpoint Protector user manual: https://www.endpointprotector.com/support/pdf/manual/Endpoint_Protector_5_User_Manual_EN.pdf",
    ],
)


# ─────────────────────────────────────────────────────────────────────────────
# 26 + 27. Simulator + Extended Simulator
# ─────────────────────────────────────────────────────────────────────────────


_SIMULATOR = SetupGuideSpec(
    quick_facts=QuickFacts(
        category="SIMULATOR",
        module="CORE",
        difficulty="easy",
        approx_setup_minutes=1,
        vendor_docs_url=None,
        polling_default_minutes=15,
        supports_webhooks=False,
        license_tier_required="None — built into URIP for demos / dev.",
    ),
    what_pulled=[
        "Synthetic findings drawn from a real-CVE corpus",
        "Realistic distribution of severities",
        "Source labels matching production connectors (e.g. crowdstrike, easm) so dashboards look real",
    ],
    prerequisites=[
        PrereqItem(
            label="License tier",
            requirement="No license required — built-in.",
        ),
        PrereqItem(
            label="Admin role",
            requirement="ciso role (URIP) — same as any production connector.",
        ),
        PrereqItem(
            label="Network",
            requirement="None — runs entirely in-process; no upstream calls are made.",
        ),
    ],
    steps=[
        SetupStep(
            n=1,
            title="Open the Simulator tile",
            body="URIP → Tool Catalog → click the **Simulator** tile to open the drawer.",
        ),
        SetupStep(
            n=2,
            title="(Optional) set Tenant Label",
            body=(
                "Leave blank for `default`, or enter your tenant slug to namespace synthetic findings. "
                "There is no upstream auth — Tenant Label is just metadata."
            ),
        ),
        SetupStep(
            n=3,
            title="Test Connection and Save",
            body=(
                "Click **Test Connection** (always returns success — runs locally) → Save."
            ),
        ),
        SetupStep(
            n=4,
            title="Run Now",
            body=(
                "Click **Run Now** — synthetic findings appear in the risk register within seconds."
            ),
        ),
        SetupStep(
            n=5,
            title="Disable when done",
            body=(
                "For production tenants, disable the Simulator after demos so synthetic and real risks "
                "are never mixed."
            ),
        ),
    ],
    required_scopes=[
        ScopeItem(
            name="ciso role",
            description="Standard URIP RBAC — same as production connectors.",
            required=True,
        ),
    ],
    sample_data={
        "id": "sim-finding-CVE-2024-12345",
        "source": "simulator",
        "domain": "endpoint",
        "finding": "CVE-2024-12345 — Synthetic critical RCE",
        "asset": "sim-host-007.example.local",
        "owner_team": "demo",
        "cvss_score": 9.5,
        "severity": "critical",
    },
    not_collected=[
        "No external data is touched — every finding is synthetic.",
    ],
    common_errors=[
        ErrorFix(
            error="No findings appear",
            cause="Simulator's tenant filter excludes the current tenant.",
            fix="Set the **Tenant Label** field to the current tenant's slug (or leave blank for default).",
        ),
        ErrorFix(
            error="Findings overlap with real data",
            cause="Simulator and a real connector running simultaneously.",
            fix="Disable the Simulator before going live — or filter dashboards by source != 'simulator'.",
        ),
        ErrorFix(
            error="Run Now returns 0 records",
            cause="Simulator already produced its capped batch this hour.",
            fix="Wait for the next 15-min poll cycle, or contact URIP support to lift the cap.",
        ),
    ],
    polling=PollingSpec(
        default_minutes=15,
        first_sync_estimate_minutes=1,
        webhook_supported=False,
        manual_refresh="Tool Catalog → Simulator tile → Run Now.",
    ),
    disconnect_steps=[
        "Tool Catalog → Simulator tile → Disable.",
        "Synthetic risks remain in the risk register; you can filter them out via source = 'simulator'.",
    ],
    references=[],
)


_EXTENDED_SIMULATOR = SetupGuideSpec(
    quick_facts=QuickFacts(
        category="SIMULATOR",
        module="CORE",
        difficulty="easy",
        approx_setup_minutes=1,
        vendor_docs_url=None,
        polling_default_minutes=15,
        supports_webhooks=False,
        license_tier_required="None — built into URIP for richer demo scenarios.",
    ),
    what_pulled=[
        "Synthetic findings across a wider product matrix (cloud, identity, OT, EASM)",
        "Cross-domain correlation scenarios (e.g. compromised identity → cloud asset)",
        "Larger volume + higher cardinality than the basic Simulator",
    ],
    prerequisites=[
        PrereqItem(
            label="License tier",
            requirement="No license required — built-in.",
        ),
        PrereqItem(
            label="Admin role",
            requirement="ciso role (URIP).",
        ),
        PrereqItem(
            label="Network",
            requirement="None — Extended Simulator runs in-process and never calls upstream services.",
        ),
    ],
    steps=[
        SetupStep(
            n=1,
            title="Open the Extended Simulator tile",
            body="URIP → Tool Catalog → click the **Extended Simulator** tile.",
        ),
        SetupStep(
            n=2,
            title="(Optional) set Tenant Label",
            body=(
                "Leave blank for `acme-default`, or enter your tenant slug. No upstream auth is performed."
            ),
        ),
        SetupStep(
            n=3,
            title="Test Connection and Save",
            body="Click **Test Connection** (local check) → **Save**.",
        ),
        SetupStep(
            n=4,
            title="Run Now",
            body=(
                "Click **Run Now** to seed a richer cross-domain dataset (cloud, identity, OT, EASM)."
            ),
        ),
        SetupStep(
            n=5,
            title="Disable when done",
            body="Same as basic Simulator — disable before go-live so synthetic data does not leak into production reports.",
        ),
    ],
    required_scopes=[
        ScopeItem(
            name="ciso role",
            description="Standard URIP RBAC.",
            required=True,
        ),
    ],
    sample_data={
        "id": "ext-sim-correlated-2002",
        "source": "extended_simulator",
        "domain": "identity",
        "finding": "Synthetic — Risky sign-in correlated with cloud key exposure",
        "asset": "alice@example.com / s3://corp-prod-keys",
        "owner_team": "demo",
        "cvss_score": 9.0,
        "severity": "critical",
    },
    not_collected=[
        "No external data is touched — every finding is synthetic.",
    ],
    common_errors=[
        ErrorFix(
            error="No correlated findings",
            cause="Simulator initialised without cross-domain seed data.",
            fix="Click Run Now twice — first run seeds, second run produces correlations.",
        ),
        ErrorFix(
            error="Findings overlap with real data",
            cause="Extended Simulator running alongside production connectors.",
            fix="Disable for production tenants, or filter dashboards by source != 'extended_simulator'.",
        ),
        ErrorFix(
            error="Run Now returns 0 records",
            cause="Extended Simulator caps to 50 findings per hour.",
            fix="Wait for the next poll, or contact URIP support to lift the cap.",
        ),
    ],
    polling=PollingSpec(
        default_minutes=15,
        first_sync_estimate_minutes=1,
        webhook_supported=False,
        manual_refresh="Tool Catalog → Extended Simulator tile → Run Now.",
    ),
    disconnect_steps=[
        "Tool Catalog → Extended Simulator tile → Disable.",
        "Synthetic risks remain in the risk register.",
    ],
    references=[],
)


# ─────────────────────────────────────────────────────────────────────────────
# LMS — KnowBe4 (Security Awareness Training)
# ─────────────────────────────────────────────────────────────────────────────


_KNOWBE4 = SetupGuideSpec(
    quick_facts=QuickFacts(
        category="LMS",
        module="CORE",
        difficulty="easy",
        approx_setup_minutes=10,
        vendor_docs_url="https://developer.knowbe4.com/reference/getting-started",
        polling_default_minutes=60,
        supports_webhooks=False,
        license_tier_required=(
            "KnowBe4 Diamond / Platinum tier or above (Reporting API access)."
        ),
    ),
    what_pulled=[
        "User training enrollments (module name, due date, status)",
        "Training completion timestamps",
        "Phishing simulation results (clicked / reported / no-action)",
        "Per-campaign delivery + outcome",
    ],
    prerequisites=[
        PrereqItem(
            label="License tier",
            requirement=(
                "KnowBe4 Diamond/Platinum subscription (Reporting API access). "
                "Silver/Gold do not expose the Reporting API."
            ),
        ),
        PrereqItem(
            label="Admin role",
            requirement="KnowBe4 Account Admin to mint the API key.",
        ),
        PrereqItem(
            label="Network",
            requirement=(
                "Allow URIP egress to https://us.api.knowbe4.com (or your "
                "regional pod, e.g. https://eu.api.knowbe4.com) on TCP 443."
            ),
        ),
    ],
    steps=[
        SetupStep(
            n=1,
            title="Open API access",
            body=(
                "Sign in to KnowBe4 → Account Settings → API Access. "
                "Click **Generate New Token**."
            ),
        ),
        SetupStep(
            n=2,
            title="Save the token",
            body=(
                "Copy the token immediately — KnowBe4 does not show it again. "
                "Save in your password manager before leaving the page."
            ),
            warning="The token is shown ONCE. If lost, you must regenerate.",
        ),
        SetupStep(
            n=3,
            title="Confirm the regional API base URL",
            body=(
                "Default is https://us.api.knowbe4.com. EU tenants must use "
                "https://eu.api.knowbe4.com. Check the URL bar of your "
                "KnowBe4 console — the subdomain matches your pod."
            ),
        ),
        SetupStep(
            n=4,
            title="Enter credentials in URIP",
            body=(
                "URIP → Tool Catalog → KnowBe4 tile → Configure. Paste the "
                "API token. Leave API Base at the default unless you are "
                "an EU customer."
            ),
        ),
        SetupStep(
            n=5,
            title="Test Connection",
            body=(
                "Click **Test Connection** — URIP calls GET /v1/account. "
                "On success, save."
            ),
        ),
    ],
    required_scopes=[
        ScopeItem(
            name="Reporting API — read",
            description=(
                "Read-only access to training enrollments + phishing test "
                "results. KnowBe4 tokens are scoped per-account; no granular "
                "scopes inside that."
            ),
            required=True,
        ),
    ],
    sample_data={
        "id": "kb4-tr-12345",
        "source": "knowbe4",
        "_kind": "training_incomplete",
        "user": {"email": "alice@acme.com", "first_name": "Alice"},
        "module_name": "Annual Security Awareness 2026",
        "status": "in_progress",
        "due_date": "2026-04-30T00:00:00Z",
    },
    not_collected=[
        "URIP does not collect the actual quiz answers or training video watch logs.",
        "Phishing email contents are NOT pulled — only outcome metadata (clicked / reported).",
    ],
    common_errors=[
        ErrorFix(
            error="401 Unauthorized when calling /v1/account",
            cause="Token revoked, copied with extra whitespace, or wrong pod URL.",
            fix=(
                "Regenerate the token, paste WITHOUT trailing whitespace, "
                "and confirm the API base matches your pod (us / eu)."
            ),
        ),
        ErrorFix(
            error="403 Forbidden — Reporting API not enabled",
            cause="Subscription tier is below Diamond.",
            fix=(
                "Contact your KnowBe4 customer success manager to upgrade or "
                "enable the Reporting API add-on."
            ),
        ),
        ErrorFix(
            error="429 Too Many Requests",
            cause="KnowBe4 enforces ~4 req/s per account.",
            fix=(
                "URIP throttles automatically. If errors persist, increase "
                "the polling interval from 60 to 120 minutes."
            ),
        ),
    ],
    polling=PollingSpec(
        default_minutes=60,
        first_sync_estimate_minutes=10,
        webhook_supported=False,
        manual_refresh="Tool Catalog → KnowBe4 tile → Run Now.",
    ),
    disconnect_steps=[
        "Tool Catalog → KnowBe4 tile → Disconnect.",
        f"{_CRED_VAULT_DELETE}",
        "Optionally revoke the API token in the KnowBe4 console.",
        f"{_KEEP_HISTORY}",
    ],
    references=[
        "https://developer.knowbe4.com/reference/getting-started",
        "https://support.knowbe4.com/hc/en-us/articles/360030393294",
    ],
)


# ─────────────────────────────────────────────────────────────────────────────
# LMS — Hoxhunt (Behaviour-change phishing training)
# ─────────────────────────────────────────────────────────────────────────────


_HOXHUNT = SetupGuideSpec(
    quick_facts=QuickFacts(
        category="LMS",
        module="CORE",
        difficulty="easy",
        approx_setup_minutes=10,
        vendor_docs_url="https://help.hoxhunt.com/en/articles/api-overview",
        polling_default_minutes=60,
        supports_webhooks=True,
        license_tier_required="Hoxhunt Standard tier or above (API access).",
    ),
    what_pulled=[
        "Per-user training engagement status (active / inactive / paused)",
        "Behaviour-change score (0.0–1.0)",
        "Phishing simulation responses (clicked / reported / ignored)",
        "Campaign metadata (name, delivered_at)",
    ],
    prerequisites=[
        PrereqItem(
            label="License tier",
            requirement=(
                "Hoxhunt Standard or Enterprise (API access). Trial accounts "
                "do not expose the API."
            ),
        ),
        PrereqItem(
            label="Admin role",
            requirement="Hoxhunt Org Admin to mint the API token.",
        ),
        PrereqItem(
            label="Network",
            requirement="Allow URIP egress to https://api.hoxhunt.com on TCP 443.",
        ),
    ],
    steps=[
        SetupStep(
            n=1,
            title="Open API integrations",
            body=(
                "Hoxhunt console → Settings → Integrations → API Tokens → "
                "**Create token**."
            ),
        ),
        SetupStep(
            n=2,
            title="Name the token + select scopes",
            body=(
                "Name it 'URIP'. Select scopes: read:users, read:simulations. "
                "Click Create."
            ),
        ),
        SetupStep(
            n=3,
            title="Copy the token",
            body=(
                "Copy and store the token — Hoxhunt only shows it once."
            ),
            warning="The token is shown ONCE. If lost, you must regenerate.",
        ),
        SetupStep(
            n=4,
            title="Configure in URIP",
            body=(
                "URIP → Tool Catalog → Hoxhunt tile → Configure. Paste the "
                "token. Click Test Connection. Save."
            ),
        ),
    ],
    required_scopes=[
        ScopeItem(
            name="read:users",
            description="Read user roster + training status + behaviour score.",
            required=True,
        ),
        ScopeItem(
            name="read:simulations",
            description="Read simulation campaign results.",
            required=True,
        ),
    ],
    sample_data={
        "id": "hox-u-987",
        "source": "hoxhunt",
        "_kind": "training_inactive",
        "email": "carol@acme.com",
        "training_status": "inactive",
        "behaviour_score": 0.2,
        "last_engaged_at": "2026-01-15T00:00:00Z",
    },
    not_collected=[
        "URIP does not collect training video watch progress.",
        "Phishing email contents are NOT pulled — only outcome metadata.",
    ],
    common_errors=[
        ErrorFix(
            error="403 Forbidden",
            cause="Token scopes are missing read:users or read:simulations.",
            fix=(
                "Regenerate the token with both scopes selected."
            ),
        ),
        ErrorFix(
            error="404 Not Found on /v1/organization",
            cause="API base URL typo or region-specific endpoint.",
            fix=(
                "Default is https://api.hoxhunt.com. Confirm with Hoxhunt "
                "support if you are on a regional pod."
            ),
        ),
        ErrorFix(
            error="No data appearing after sync",
            cause="No simulations have been delivered yet.",
            fix=(
                "Run at least one phishing campaign in Hoxhunt; URIP will "
                "ingest results on the next poll."
            ),
        ),
    ],
    polling=PollingSpec(
        default_minutes=60,
        first_sync_estimate_minutes=8,
        webhook_supported=True,
        manual_refresh="Tool Catalog → Hoxhunt tile → Run Now.",
    ),
    disconnect_steps=[
        "Tool Catalog → Hoxhunt tile → Disconnect.",
        f"{_CRED_VAULT_DELETE}",
        "Optionally revoke the token in Hoxhunt console.",
        f"{_KEEP_HISTORY}",
    ],
    references=[
        "https://help.hoxhunt.com/en/articles/api-overview",
    ],
)


# ─────────────────────────────────────────────────────────────────────────────
# BGV — AuthBridge
# ─────────────────────────────────────────────────────────────────────────────


_AUTHBRIDGE = SetupGuideSpec(
    quick_facts=QuickFacts(
        category="BGV",
        module="CORE",
        difficulty="medium",
        approx_setup_minutes=15,
        vendor_docs_url="https://www.authbridge.com/products/api/",
        polling_default_minutes=120,
        supports_webhooks=True,
        license_tier_required=(
            "AuthBridge Enterprise contract with API access enabled."
        ),
    ),
    what_pulled=[
        "Per-employee BGV verification record",
        "Status (initiated / in_progress / completed / failed)",
        "Checks completed + checks pending (criminal, education, address, …)",
        "Initiation + completion timestamps",
    ],
    prerequisites=[
        PrereqItem(
            label="License tier",
            requirement=(
                "AuthBridge Enterprise contract — API endpoints are not part "
                "of self-serve plans."
            ),
        ),
        PrereqItem(
            label="Admin role",
            requirement=(
                "AuthBridge tenant Account Owner. Get the API token from your "
                "AuthBridge account manager."
            ),
        ),
        PrereqItem(
            label="Network",
            requirement="Allow URIP egress to https://api.authbridge.com on TCP 443.",
        ),
    ],
    steps=[
        SetupStep(
            n=1,
            title="Request API access",
            body=(
                "Email your AuthBridge account manager and request API token "
                "issuance for 'URIP' integration. AuthBridge does not yet "
                "expose self-serve token generation."
            ),
        ),
        SetupStep(
            n=2,
            title="Confirm allow-list",
            body=(
                "AuthBridge requires URIP egress IPs to be allow-listed. "
                "Provide your URIP backend egress IP(s) to the AB account "
                "manager."
            ),
        ),
        SetupStep(
            n=3,
            title="Receive token + base URL",
            body=(
                "AuthBridge will email the bearer token + the regional API "
                "base (default https://api.authbridge.com). Treat the token "
                "as a secret."
            ),
            warning="Tokens are long-lived. Rotate on a 90-day cadence.",
        ),
        SetupStep(
            n=4,
            title="Configure in URIP",
            body=(
                "URIP → Tool Catalog → AuthBridge tile → Configure. Paste "
                "the token + API base. Save."
            ),
        ),
        SetupStep(
            n=5,
            title="Test Connection",
            body=(
                "Click Test Connection. URIP calls GET /v1/account."
            ),
        ),
    ],
    required_scopes=[
        ScopeItem(
            name="Verifications — read",
            description="Read-only access to BGV verification records.",
            required=True,
        ),
    ],
    sample_data={
        "id": "ab-12345",
        "source": "authbridge",
        "employee_email": "emily@acme.com",
        "employee_name": "Emily",
        "status": "in_progress",
        "checks_done": ["education"],
        "checks_pending": ["criminal", "address"],
        "initiated_at": "2026-03-01T00:00:00Z",
    },
    not_collected=[
        "URIP does not collect the underlying verification documents (PAN, Aadhaar, certificates).",
        "Only the BGV status + check checklist are ingested.",
    ],
    common_errors=[
        ErrorFix(
            error="401 Unauthorized",
            cause="Token expired or rotated by AB.",
            fix=(
                "Email your AuthBridge account manager to rotate. AB does "
                "not yet support self-serve regen."
            ),
        ),
        ErrorFix(
            error="403 Forbidden — IP not allow-listed",
            cause="URIP egress IP changed (e.g. infra rebuild).",
            fix=(
                "Submit the new egress IPs to AB account management for "
                "allow-listing."
            ),
        ),
        ErrorFix(
            error="No verifications returned",
            cause="No BGV requests initiated in your tenant yet.",
            fix=(
                "Initiate at least one BGV in the AuthBridge console; URIP "
                "will ingest on the next poll."
            ),
        ),
    ],
    polling=PollingSpec(
        default_minutes=120,
        first_sync_estimate_minutes=12,
        webhook_supported=True,
        manual_refresh="Tool Catalog → AuthBridge tile → Run Now.",
    ),
    disconnect_steps=[
        "Tool Catalog → AuthBridge tile → Disconnect.",
        f"{_CRED_VAULT_DELETE}",
        "Email AB account manager to revoke the token.",
        f"{_KEEP_HISTORY}",
    ],
    references=[
        "https://www.authbridge.com/products/api/",
    ],
)


# ─────────────────────────────────────────────────────────────────────────────
# BGV — OnGrid (alternative)
# ─────────────────────────────────────────────────────────────────────────────


_ONGRID = SetupGuideSpec(
    quick_facts=QuickFacts(
        category="BGV",
        module="CORE",
        difficulty="easy",
        approx_setup_minutes=10,
        vendor_docs_url="https://docs.ongrid.in/",
        polling_default_minutes=120,
        supports_webhooks=True,
        license_tier_required="OnGrid Business plan or above (API tier).",
    ),
    what_pulled=[
        "Per-candidate verification record",
        "Status (pending / verified / rejected)",
        "Checks completed + remaining (Aadhaar, PAN, address, …)",
        "Rejection reason where applicable",
    ],
    prerequisites=[
        PrereqItem(
            label="License tier",
            requirement="OnGrid Business plan with API tier.",
        ),
        PrereqItem(
            label="Admin role",
            requirement="OnGrid tenant Owner / Admin to generate API key.",
        ),
        PrereqItem(
            label="Network",
            requirement="Allow URIP egress to https://api.ongrid.in on TCP 443.",
        ),
    ],
    steps=[
        SetupStep(
            n=1,
            title="Generate API key",
            body=(
                "OnGrid console → Settings → API → Generate new key. "
                "Name it 'URIP'."
            ),
        ),
        SetupStep(
            n=2,
            title="Copy the key",
            body=(
                "Copy and store the API key — OnGrid only shows it on "
                "creation."
            ),
            warning="The key is shown ONCE. If lost, regenerate.",
        ),
        SetupStep(
            n=3,
            title="Configure in URIP",
            body=(
                "URIP → Tool Catalog → OnGrid tile → Configure. Paste the "
                "key. Save."
            ),
        ),
        SetupStep(
            n=4,
            title="Test Connection",
            body=(
                "Click Test Connection — URIP calls GET /v1/me."
            ),
        ),
    ],
    required_scopes=[
        ScopeItem(
            name="checks:read",
            description="Read-only access to verification records.",
            required=True,
        ),
    ],
    sample_data={
        "id": "og-789",
        "source": "ongrid",
        "candidate_email": "henry@acme.com",
        "candidate_name": "Henry",
        "verification_status": "pending",
        "checks_completed": ["aadhaar"],
        "checks_remaining": ["pan", "address"],
    },
    not_collected=[
        "URIP does not pull the underlying KYC documents.",
        "Only verification status + check progress are ingested.",
    ],
    common_errors=[
        ErrorFix(
            error="401 Unauthorized",
            cause="Key revoked or copied incorrectly.",
            fix="Regenerate the key in OnGrid console and re-paste in URIP.",
        ),
        ErrorFix(
            error="403 Forbidden",
            cause="OnGrid plan does not include API tier.",
            fix="Contact OnGrid sales to upgrade to Business + API tier.",
        ),
        ErrorFix(
            error="No checks returned",
            cause="No verifications initiated yet.",
            fix=(
                "Initiate at least one verification in OnGrid; URIP will "
                "ingest on the next poll."
            ),
        ),
    ],
    polling=PollingSpec(
        default_minutes=120,
        first_sync_estimate_minutes=10,
        webhook_supported=True,
        manual_refresh="Tool Catalog → OnGrid tile → Run Now.",
    ),
    disconnect_steps=[
        "Tool Catalog → OnGrid tile → Disconnect.",
        f"{_CRED_VAULT_DELETE}",
        "Optionally revoke the API key in OnGrid console.",
        f"{_KEEP_HISTORY}",
    ],
    references=[
        "https://docs.ongrid.in/",
    ],
)


# ─────────────────────────────────────────────────────────────────────────────
# Public registry — single dict keyed by connector NAME
# ─────────────────────────────────────────────────────────────────────────────


SETUP_GUIDES: dict[str, SetupGuideSpec] = {
    "tenable": _TENABLE,
    "sentinelone": _SENTINELONE,
    "zscaler": _ZSCALER,
    "netskope": _NETSKOPE,
    "ms_entra": _MS_ENTRA,
    "manageengine_sdp": _ME_SDP,
    "cloudsek": _CLOUDSEK,
    "aws_cspm": _AWS_CSPM,
    "azure_cspm": _AZURE_CSPM,
    "gcp_cspm": _GCP_CSPM,
    "cert_in": _CERT_IN,
    "siem": _SIEM,
    "email_security": _EMAIL_SECURITY,
    "bug_bounty": _BUG_BOUNTY,
    "crowdstrike": _CROWDSTRIKE,
    "easm": _EASM,
    "armis_ot": _ARMIS_OT,
    "forescout_nac": _FORESCOUT_NAC,
    "cyberark_pam": _CYBERARK_PAM,
    "fortiguard_fw": _FORTIGUARD_FW,
    "m365_collab": _M365_COLLAB,
    "manageengine_ec": _ME_EC,
    "manageengine_mdm": _ME_MDM,
    "burp_enterprise": _BURP_ENT,
    "gtb": _GTB,
    "simulator": _SIMULATOR,
    "extended_simulator": _EXTENDED_SIMULATOR,
    # P33 — LMS + BGV connectors
    "knowbe4": _KNOWBE4,
    "hoxhunt": _HOXHUNT,
    "authbridge": _AUTHBRIDGE,
    "ongrid": _ONGRID,
}


def get_setup_guide(connector_name: str) -> SetupGuideSpec | None:
    """Return the SETUP_GUIDE for ``connector_name`` or ``None`` if not found."""
    return SETUP_GUIDES.get(connector_name)
