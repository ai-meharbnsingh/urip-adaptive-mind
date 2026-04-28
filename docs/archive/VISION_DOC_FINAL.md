# URIP-Adverb Master Vision Document

**Status:** Final synthesis (4-way: Claude + Codex + Kimi + Gemini)
**Date:** 2026-04-27
**Audience:** Internal alignment + client review meeting
**Companion docs:** `ADVERB_BLUEPRINT.md` (scope), `ADVERB_IMPLEMENTATION_PLAN.md` (phases), `DELIVERY_ARCHITECTURE.md` (deployment options), `compliance/README.md` (Compliance sub-project)

---

## 0. Executive Summary

- **What we're building.** URIP-Adverb is a multi-tenant, module-pickable risk and compliance platform. Two dashboards on one data layer: URIP for live risk intelligence, Compliance for continuous audit-readiness — backed by 12 native connectors, a 4-feed enrichment layer (EPSS, CISA KEV, MITRE ATT&CK, AlienVault OTX), and a 7-framework compliance engine (SOC 2, ISO 27001, GDPR, HIPAA, PCI DSS, India DPDP Act 2023, NIST CSF 2.0).
- **Who it's for.** Adverb (Addverb Technologies) — Reliance-owned warehouse robotics, ~1,000 employees, sells to PepsiCo, J&J, and Reliance group companies that run formal vendor security questionnaires. Eleven security tools in their stack today, plus CloudSEK.
- **Two dashboards, one platform.** URIP (the CISO's "where am I most exposed today?") and Compliance (the Compliance Officer's "are we audit-ready if the auditor lands next week?"). Distinct buyers, shared data layer.
- **Hybrid-SaaS delivery.** Cloud portal in our infrastructure for UI and intelligence; a Docker agent inside Adverb's network for connectors and raw storage. Sensitive identifiers (IPs, hostnames, usernames, evidence files) never leave Adverb's network. Same architectural pattern CrowdStrike Falcon, Tenable Nessus Agent, and Splunk Forwarder use to clear procurement at regulated buyers.
- **The unique moat.** Risk → Control linkage. When a CVE breaks SOC 2 control CC7.1, the platform shows the exact CVEs, exact assets, exact owners. Sprinto cannot do this — its data model has compliance controls but no CVE-level threat enrichment. CloudSEK is the inverse — threat data with no compliance scaffolding. URIP has both inside one tenant scope.
- **What Adverb does in three clicks.** (1) Tick the tools they own in a visual catalog. (2) Enter API credentials per tool with an instant "Test Connection" check. (3) Watch the URIP and Compliance dashboards populate from the first 15-minute poll cycle onward.

---

## 1. The Client Experience — End-to-End Story

Tuesday morning. Adverb's CISO opens her laptop two days after signing the SoW and navigates to `https://adverb.urip.io`. The login carries Adverb's logo and brand colors. SSO via Microsoft Entra clears her into Adverb's tenant space.

**Step 1 — Welcome and tenant confirmation.** An onboarding wizard greets her by name, confirms the tenant is "Addverb Technologies — Production," and walks through three quick choices: industry vertical (Manufacturing / Logistics), primary geography (Noida, India), and the compliance frameworks she cares about (SOC 2 Type 2, ISO 27001:2022, India DPDP Act 2023). These seed the asset taxonomy and framework engine in the background.

**Step 2 — The Tool Catalog.** A visual grid renders 12 tool tiles — Tenable, SentinelOne, Zscaler ZIA/ZTA/CASB, Netskope, MS Entra ID, SharePoint/OneDrive/Teams, ManageEngine SDP/Endpoint Central/MDM, Burp Suite Enterprise, GTB Endpoint Protector, CloudSEK. Each tile shows vendor logo, one-line description ("Vulnerability scanner — pulls CVE inventory, CVSS, exploit availability"), setup difficulty (Low/Medium/High), freshness target ("15-minute pull"), status pill ("Not connected"). Below, a greyed-out roadmap row: AWS, Azure, GCP, Slack, Jira, GitHub, Okta — "Coming in Phase 2C." She ticks the 11 tools Adverb owns plus CloudSEK. Burp Suite shows a warning icon: "Requires Burp Enterprise license — confirm before continuing."

**Step 3 — Per-tool credential wizard.** For each tool, a guided form. Tenable: Access Key + Secret Key. SentinelOne: Singularity API token + Site ID. Zscaler: API key + partner key + cloud name. MS Entra: OAuth admin-consent flow — her IT admin grants `SecurityEvents.Read.All`, `IdentityRiskEvent.Read.All`, `AuditLog.Read.All`. Each form has inline help, a link to the vendor's API docs, exact scopes required, and a prominent **"Test Connection"** button.

**Step 4 — Real-time validation.** Within 2-4 seconds of clicking, the screen returns either green ("Connected. Found 2,847 assets. Last scan: 6 hours ago.") or a red error with the exact remediation step ("HTTP 403 from Tenable — verify your API key has Scanner Role"). Credentials never touch browser localStorage — they go straight to the on-prem agent's Fernet-encrypted vault.

**Step 5 — First poll, within minutes.** The wizard hands her off with a banner: *"Connectors are running their first sync. Initial population takes 5-15 minutes."* By 9:42 AM the URIP dashboard has 412 risks, EPSS has annotated each with an exploit probability (0.00-1.00), 7 risks are flagged as KEV (CISA), 3 of those KEV CVEs are attributed to APT41 via MITRE ATT&CK, and the asset criticality service has assigned T1/T2/T3/T4 tiers.

**Step 6 — Within an hour: the Compliance dashboard.** The framework engine has already evaluated ~50 controls. SOC 2 sits at 73% (failing: CC6.6 Logical Access, CC7.1 System Monitoring, CC7.2 Anomalies). ISO 27001:2022 sits at 81%. India DPDP sits at 64%. Each failing control has a "View root-cause risks" button; clicking SOC 2 CC7.1 shows the 14 actively-exploitable CVEs in her Tenable feed causing the failure. **No other product does this** — Sprinto can tell her the control failed; only URIP tells her *which CVE is breaking it, on which asset, owned by whom*.

**Step 7 — Within 24 hours.** The compliance scoring engine writes its first nightly snapshot to `compliance_score_history`. Evidence automation has captured ~50 evidence files (Tenable scan exports, SentinelOne agent rosters, MS Entra conditional-access policy snapshots). Auto-generated SDP tickets sit in the IT team's queue.

**Step 8 — Within a week.** Seven daily snapshots in, the trend chart shows whether the score is improving. Policy-acknowledgment workflows have reached 100% of employees. The action-items list has a stable shape. The CISO and Compliance Officer hold a Monday review meeting against a single source of truth — no spreadsheets.

---

## 2. Architecture — Hybrid-SaaS

URIP-Adverb ships as Hybrid-SaaS by default — Option 3 in `DELIVERY_ARCHITECTURE.md`. Cloud portal at the top, lightweight Docker agent inside Adverb's network, secure tunnel between them. Same pattern CrowdStrike, Tenable, and Splunk pioneered.

```
┌──────────────────────────────────────────────────────────────────┐
│                  SEMANTIC GRAVITY CLOUD (us)                      │
│                                                                   │
│  ┌──────────────────┐    ┌─────────────────────────────────────┐ │
│  │  Frontend Portal │    │  Cloud Backend                       │ │
│  │  - Dashboard UI  │◄──►│  - URIP intelligence engine          │ │
│  │  - Login + RBAC  │    │  - EPSS / KEV / MITRE / OTX feeds    │ │
│  │  - Auditor portal│    │  - Compliance scoring engine         │ │
│  │  - Reports       │    │  - Tenant + license + module mgmt    │ │
│  └──────────────────┘    │  - Aggregate metadata only           │ │
│                          └─────────────┬───────────────────────┘ │
│                                        │ HTTPS (signed payloads) │
└────────────────────────────────────────┼─────────────────────────┘
                                         │
                                         ▼
┌──────────────────────────────────────────────────────────────────┐
│                  ADVERB CUSTOMER NETWORK                          │
│                                                                   │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │  URIP Agent (Docker container)                              │ │
│  │  ┌────────────────┐   ┌──────────────────────────────────┐ │ │
│  │  │ API Connectors │──►│ Normalizer + Local DB Manager    │ │ │
│  │  │ (Tenable, S1,  │   │ (raw → URIP schema → local PG)   │ │ │
│  │  │  Entra, etc.)  │   └────────────┬─────────────────────┘ │ │
│  │  └────────────────┘                │                        │ │
│  │  ┌─────────────────────────────────▼─────────────────────┐ │ │
│  │  │ Encrypted Reporter (sends ONLY scores + counts)       │ │ │
│  │  │  e.g. "8.2 risk score, 15 criticals, SOC 2 = 73%"    │ │ │
│  │  │  NEVER sends: IPs, hostnames, usernames, raw evidence │ │ │
│  │  └───────────────────────────────────────────────────────┘ │ │
│  │  ┌───────────────────────────────────────────────────────┐ │ │
│  │  │ Drill-Down Tunnel (on-demand reverse tunnel)          │ │ │
│  │  │ User clicks "View Details" → cloud signs request →    │ │ │
│  │  │ agent returns raw data into the user's browser session│ │ │
│  │  │ — never persisted in our cloud                        │ │ │
│  │  └───────────────────────────────────────────────────────┘ │ │
│  └────────────────────────────────────────────────────────────┘ │
│                              │                                    │
│                              ▼                                    │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │ Local Postgres (Adverb-owned)                               │ │
│  │ Full risk records w/ IPs, hostnames, usernames              │ │
│  │ Compliance evidence files, audit logs, vendor docs          │ │
│  │ STAYS ON ADVERB'S NETWORK FOREVER                           │ │
│  └────────────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────────┘
```

**What stays in the cloud:** frontend UI, master intelligence engine (EPSS/KEV/MITRE/OTX feeds), compliance framework data (public reference data anyway), scoring engine, tenant + license + module management, aggregate metadata only, the auditor portal.

**What ships as the Docker agent:** API connectors, normalizer, local DB manager, Fernet-encrypted credential vault (decrypt only in-memory at runtime), encrypted reporter, drill-down responder.

**What stays on Adverb's network forever:** every IP address, hostname, username, file path, evidence file, audit log entry, vendor document. Full-detail Postgres records.

**Trust boundary, in plain English.** The only thing crossing from Adverb's network to our cloud is a tiny JSON envelope of summary metrics — risk scores, control pass/fail counts, compliance percentages, connector heartbeats. If our cloud is breached tomorrow, the attacker sees that some tenant called "Adverb" has a risk score of 8.2 and 73% SOC 2 compliance. They learn nothing about Adverb's actual infrastructure.

**Drill-down tunnel.** When a user clicks "View raw event," the cloud signs a short-lived JWT and pushes it to the agent over a persistent reverse WebSocket tunnel. The agent fetches from local Postgres and streams the payload back to the user's browser session. Nothing persists in our cloud. mTLS, comprehensive audit logging on every cloud-initiated drill-down, and an "off switch" Adverb's IT can flip at any time round out the security model.

This architecture is the procurement-clearing answer. When PepsiCo or J&J asks *"where does your security tooling vendor store our sensitive data?"*, Adverb's answer is **"nowhere — it stays on our network."** Sprinto cannot give that answer; their entire model is cloud-side.

---

## 3. Two Dashboards — Distinct But Linked

Two dashboards, two buyers, two rhythms. Same underlying data layer, same auth, same audit log.

### 3a. URIP Risk Intelligence Dashboard

Default landing page. Built to answer the CISO's first question: *"Where am I most exposed today, and are we fixing it fast enough?"*

**Top KPI strip** (5 click-through tiles, sample numbers from the demo tenant):
- **Total Open Risks**: 412 (▲ 23 since yesterday)
- **Critical Severity**: 18 (▲ 4)
- **Mean Time to Remediate** (rolling 30 days): 11.3 days (target: 14)
- **Exploit-Active Risks** (KEV + EPSS > 0.7): 7
- **Connectors Healthy**: 11 of 12 (Burp last sync failed 2h ago)

**Risk register.** Sortable, filterable table. Columns: Severity, Title, Source, Asset, EPSS Score, KEV Status, APT Attribution, Owner, SLA Status, Age. Filter chips: Source, Severity, Status, Asset Tier. Click any row → detail panel slides in with the full enrichment trail and a "Drill into source" button that hits the secure tunnel.

**Threat intel panel** (right column). Active APT groups targeting the Manufacturing / Logistics sector with MITRE ATT&CK technique IDs and the CVEs each group has historically exploited. Today: APT41 (T1190 Exploit Public-Facing Application), Lazarus (T1566 Phishing), FIN12 (T1486 Data Encrypted for Impact).

**Connector health board.** Every connector with last successful poll, error count in the last 24 hours, and a status pill (LIVE / DEGRADED / DOWN). Polling defaults: 15-minute cycles for high-volume sources (Tenable, SentinelOne, Zscaler), 60-minute for medium-volume (Netskope, Entra, ManageEngine), 4-hour for low-volume (Burp, GTB, CloudSEK). All intervals configurable per-tenant in `backend/routers/settings.py`. Drift detection (schema changes, null fields, permission regressions) escalates as a degraded state, not a green light.

**Drill-down tunnel UX.** "View Raw Source Data" → cloud signs short-lived JWT → agent fetches from local Postgres → browser renders directly. Nothing persists in the cloud database.

### 3b. Compliance Dashboard (Sprinto-equivalent)

Second top-nav tab. Built to answer the Compliance Officer's first question: *"If the audit was next week, would we pass?"* Lives as a separate FastAPI service on port 8001 (`compliance/backend/compliance_backend/`) with its own database. Can also run standalone (`docker-compose -f compliance/docker-compose.standalone.yml up`) for prospects who want only audit-readiness without the URIP risk layer.

**Per-framework KPI widgets** (sample values from `adverb-demo` seed):
- SOC 2 (Trust Services 2022): **87%** — 142 / 163 controls
- ISO 27001:2022: **92%** — 86 / 93
- India DPDP Act 2023: **78%** — 39 / 50
- GDPR: **91%** — 41 / 45
- HIPAA: **84%** (applicable only if Adverb supports US healthcare logistics)
- PCI DSS v4.0: **88%** (applies to one payment-handling subsystem)
- NIST CSF 2.0: **79%** (voluntary guidance)

Each tile shows trend arrow vs 7 days ago. Click-through opens framework drill-down: control list grouped by category, color-coded pass/fail/inconclusive, with "View root-cause risks" on every failing control hitting the URIP × Compliance bridge.

**Failing controls list.** Single ranked list across all frameworks, sorted by `remedy_priority_score = (frameworks_affected × failure_severity × root_cause_risk_count)`. The compliance team works top-down.

**Evidence collection status.** Three columns: Total controls (with auto-evidence configured) / Evidence captured this period / Evidence missing or stale. Auto-collection wired via `compliance/backend/compliance_backend/services/evidence_service.py` — every connector poll captures evidence-tagged extracts (configs, headless-browser screenshots, ticket exports) and indexes them against the relevant control. Files stored on the agent's local network in S3-compatible storage; only metadata syncs to the cloud.

**Policy acknowledgment status.** Every policy with current version, total employees, acknowledged count, percent acknowledged, expiring-soon flags. Bulk-remind unsigned employees in one click.

**Vendor risk overview.** Top vendors by risk via `compliance/backend/compliance_backend/routers/vendors.py`, with overdue questionnaires, expiring DPAs/BAAs, and a "Send reminder" action. Adverb's typical inventory: 40-80 vendors.

**Auditor portal entry.** Prominent "Invite an auditor" button at top right, plus a list of currently-active sessions (auditor name, framework scope, audit period, last activity, expiry). Read-only, time-bounded, framework-scoped. Routed through `compliance/backend/compliance_backend/routers/auditor.py` and the dedicated frontend at `compliance/frontend/auditor_portal.html`.

**Action items before next audit.** Prioritised punch-list synthesised from failing controls, missing evidence, unacknowledged policies, expiring vendor docs, unfinished access reviews. By design, the list is *always the same shape* whether Adverb is 4 weeks or 4 months out — the platform handles the routine items automatically so the visible list stays short.

---

## 4. The Connector Library

Each connector lives in `connectors/` and follows a uniform plugin architecture: `authenticate()`, `fetch_findings(since)`, `normalize(raw)`, `health_check()`. New connectors plug in without touching core code.

**What's already shipped:**

| Connector | Status | Where it lives |
|---|---|---|
| Tenable Vulnerability Manager | ✅ LIVE | `connectors/tenable/` |
| SentinelOne Singularity | ✅ LIVE | `connectors/sentinelone/` |
| Adverb tenant simulator (synthetic data for demo mode) | 🟡 SIMULATED | `connectors/adverb_simulator.py`, `connectors/simulator_connector.py` |

**Phase 2A planned (10 net-new connectors, per `ADVERB_IMPLEMENTATION_PLAN.md` Section 4):**

| # | Connector | What URIP pulls | Polling | API surface |
|---|---|---|---|---|
| 1 | Zscaler ZIA / ZTA / CASB | Blocked URLs, shadow SaaS, malicious downloads | 15 min | Three sub-endpoints; partner key + API key |
| 2 | Netskope | Cloud app risk, DLP violations, sanctioned-vs-unsanctioned usage | 60 min | REST API, OAuth2 |
| 3 | Microsoft Entra ID | Risky sign-ins, MFA bypass, conditional access violations, privileged role assignments | 60 min | MS Graph API, OAuth2 + admin consent |
| 4 | SharePoint / OneDrive / Teams | Anonymous link sharing, external sharing audit, sensitive label violations | 60 min | MS Graph API (shared auth with #3) |
| 5 | ManageEngine SDP | Bidirectional ticket creation + status sync | 60 min | REST API, OAuth2 |
| 6 | ManageEngine Endpoint Central | Patch status, missing critical patches | 60 min | REST API, OAuth2 |
| 7 | ManageEngine MDM | Jailbroken devices, non-compliant mobile, lost/stolen events | 4 hours | REST API, OAuth2 |
| 8 | Burp Suite Enterprise | Web app scan findings (XSS, SQLi, CSRF, etc.) | 4 hours | Burp Enterprise API (NOT Pro) |
| 9 | GTB Endpoint Protector | DLP policy violations, USB block events, exfil attempts | 60 min | REST API, key auth |
| 10 | CloudSEK (Option A) | Dark web alerts, brand abuse, leaked credentials, supply chain risk | 4 hours | XVigil + BeVigil + SVigil REST APIs |

**Phase 2C horizontal additions (roadmap, beyond Adverb):** AWS Security Hub, Azure Defender, GCP Security Command Center, Slack audit logs, Jira security issues, GitHub Advanced Security, Okta. Surface in the Tool Catalog as "Coming in Phase 2C."

**Per-connector card layout.** Vendor logo, one-line description, setup difficulty, data freshness target, status pill (Connected / Configured / Not Set / Error), "Owned" toggle.

**Add-new-connector flow.** Implement the four-method contract → provide source-severity → URIP-severity mapping → provide test harness with canned payloads + permission validation → register in the catalog with required scopes and UI fields.

**Per-tenant credential vault.** Every credential is Fernet-encrypted at rest (per-tenant key derived from a master key). Credentials never appear in logs, never serialise into telemetry, never replicate to read-replica DBs. Rotation is one click. In Hybrid-SaaS mode the vault lives on the agent — the cloud portal never sees raw API keys.

**Per-connector health monitoring.** Every connector emits structured JSON logs (`connector_name`, `tenant_id`, `event=poll_complete`, `duration_ms`, `records_ingested`, `errors`). 7-day rolling aggregate feeds the connector health board. If a connector misses 3 consecutive poll cycles, an alert fires and the tile turns red. Health checks validate *coverage* (expected record volumes), not just connectivity — silent connector failure is the enemy of the no-manual-effort promise.

---

## 5. Multi-Tenancy + License Modules

URIP ships as **9 capability modules + a mandatory Core**. Each tenant subscribes to exactly the modules they need; disabled modules are dark in the UI (frontend route guards) and inactive in the backend (decorator checks in `backend/middleware/auth.py`).

| Module | What it includes | Adverb subscribed? |
|---|---|---|
| **Core** (mandatory) | Risk register, scoring engine (EPSS+KEV+MITRE+OTX), dashboard, workflow, audit log, reports | ✅ Yes |
| **VM** | Tenable / Qualys / Rapid7 / CrowdStrike Spotlight | ✅ Yes (Tenable) |
| **EDR** | SentinelOne / CrowdStrike Falcon / Defender for Endpoint + ManageEngine EC + MDM | ✅ Yes (S1, EC, MDM) |
| **Network** | Zscaler / Netskope / Palo Alto / Fortigate + CloudSEK external threat | ✅ Yes (Zscaler, Netskope, CloudSEK) |
| **Identity** | MS Entra / Okta / Google Workspace | ✅ Yes (Entra) |
| **Collaboration** | SharePoint / OneDrive / Teams / Slack / Confluence | ✅ Yes (SP/OD/Teams) |
| **ITSM** | ServiceNow / Jira / ManageEngine SDP | ✅ Yes (SDP) |
| **DAST** | Burp Suite / OWASP ZAP / Acunetix | ✅ Yes (Burp Enterprise) |
| **DLP** | GTB / Forcepoint / Symantec DLP | ✅ Yes (GTB) |
| **Compliance & Audit-Readiness** | 7-framework engine, control monitoring, evidence automation, policy mgmt, access reviews, vendor risk, incident lifecycle, asset inventory, auditor portal, compliance scoring | ✅ Yes (the strategic upsell) |

**Adverb subscribes to Core + every module.** A different tenant might subscribe to Core + Compliance only (a startup just needing audit-readiness). A factory might want Core + VM + Network + ITSM. Modular pricing closes deals at every tier without forcing all-or-nothing.

**Module gating.** Enforced in three places: UI (hide unavailable modules), API (authorise based on tenant subscription), data plane (connectors only run when their module is enabled). Multi-tenancy is not just `tenant_id` on every table — it is enforced as a product principle: no cross-tenant inference, no cross-tenant leaks, no shared secrets.

**White-label theming per tenant.** Logo, color palette (primary / secondary / accent), app name, favicon, login-page background. Stored per-tenant in the `tenant_branding` table; rendered via CSS variable injection. Adverb's dashboard says "Adverb," not "URIP." Their auditor's email invitation says "Adverb invites you to their compliance audit portal."

**Compliance Module as strategic upsell.** Most modules are operational line items — they replace existing tools. The Compliance Module is different: it is a **board-level budget conversation**. Sprinto charges ₹8-25 lakh/year for compliance automation alone. Selling URIP without Compliance positions us as "another vulnerability dashboard" (low-budget). Selling URIP with Compliance positions us as "compliance + risk + audit platform" (board-level budget). Same code, dramatically different sales motion.

**Role separation:**
- **Super-admin (Semantic Gravity)** — provisions tenants, ships platform updates. Never sees tenant raw data (Hybrid-SaaS enforces this — raw data is on-prem).
- **Tenant admin (Adverb's CISO + Compliance Officer)** — configures their tenant: connectors, modules, roles, branding, framework selection.
- **Tenant user** — scoped roles within Adverb (e.g., "DLP Analyst" sees only the DLP module; "Risk Owner" sees their assigned risks only). Module-level RBAC in `backend/middleware/auth.py`.
- **Auditor** — read-only, time-bounded, framework-scoped. See Section 3b.

---

## 6. The "No Manual Effort" Promise

Once connectors are configured (one-time, ~2 hours during onboarding), the platform runs itself.

**What happens automatically every day, without anyone touching it:**

- Connectors poll on their schedule (15 / 60 / 240 min) and pull deltas; raw findings normalise into the URIP schema and write to local Postgres
- Every CVE is enriched with EPSS exploit probability (FIRST.org, free), KEV status (CISA, free), MITRE ATT&CK APT attribution (free + periodic refresh), OTX IOC context (AlienVault, free with API key) — all four feeds LIVE today in `backend/services/exploitability_service.py` and `backend/services/threat_intel_service.py`
- Composite scoring: `score = base_severity × asset_criticality_multiplier × exploit_probability × threat_attribution_weight`. Asset multiplier applies per-tenant taxonomy ("Robotics Production Line PLC" = T1; "Canteen Wi-Fi" = T4) via `backend/services/asset_criticality_service.py`
- Compliance controls auto-evaluate daily; pass/fail/inconclusive tracked per run via `compliance/backend/compliance_backend/services/control_engine.py`
- Evidence auto-captures at every control run (screenshots, config exports, ticket exports, log snippets) — tagged to control + framework + audit period, stored in S3-compatible storage on the agent's network
- Policy reminders auto-send to non-acknowledged employees; vendor reviews auto-schedule by criticality (T1 annually, T2 18mo, T3 24mo) with reminders at 30/14/7 days
- Compliance scores auto-recalculate after every run via `compliance/backend/compliance_backend/services/scoring_engine.py`; daily snapshot writes to `compliance_score_history` for trend charts
- Reports auto-generate on the tenant's schedule; auditor self-serves via the portal; remediation auto-tracks via bidirectional ManageEngine SDP sync

**What humans still own:** risk acceptance decisions (HoD sign-off), policy approval and version updates (legal review), incident response execution (the SOC still owns the response), auditor questions beyond the evidence in the portal, strategic decisions about which frameworks/vendors/controls to scope. The platform handles the routine; humans handle judgment.

---

## 7. Identity Risk Logic — Carry-Forward From Royal Enfield

Per `DELIVERY_ARCHITECTURE.md` Section 5, the Royal Enfield engagement built the Identity Module against CyberArk PAM. Adverb runs MS Entra ID. **Same engine, different connector.**

```
RE source (CyberArk PAM)  ─┐
                           │
                           ▼
                ┌──────────────────────────┐
                │   URIP Identity Module    │
                │   (Universal Logic)       │
                │   - Severity Mapping      │
                │   - Asset Tier Multiplier │
                │   - Auto-Assignment       │
                │   - SLA Timer             │
                │   - Remediation Workflow  │
                └──────────────┬───────────┘
                               │
Adverb source (MS Entra ID) ───┘
```

We swap the input adapter (CyberArk → MS Graph API); the entire downstream workflow (severity mapping → asset multiplier → auto-assignment → SLA timer → remediation) is identical.

**What Adverb gets from the carry-forward:** brute force / credential stuffing detection (Entra `signInActivity` 50 failed login attempts → HIGH risk), impossible travel (`atypicalTravel` event correlated with asset criticality), MFA fatigue / bypass (`mfaFatigue` signal → SDP ticket within SLA), suspicious privileged role assignments. Asset criticality multiplier is the secret sauce — a risky login on "Financial SharePoint" scores Critical 9.0+; same login on "Canteen Menu" stays Low.

Already built and reusable: URIP Identity Module risk handling (multi-tenant version), asset criticality service (per-tenant configurable), severity mapping, SLA service, remediation tracking. Net-new connector work for Adverb: MS Entra connector (Phase 2A item 2.4), Entra-specific `riskEventType` enum mapping, auto-ticket-to-ManageEngine flow. Connector-level addition, not architectural change.

---

## 8. What We've Built vs What's Coming

Three labels used consistently. ✅ LIVE = code runs against the real upstream API today. 🟡 PARTIAL / SIMULATED = code exists with synthetic data or partial extension. 🔴 TO BUILD = code does not exist.

### URIP Core (`backend/`) — ✅ LIVE

All routers live: `auth.py` (JWT, RBAC), `risks.py` (CRUD risk register), `dashboard.py`, `acceptance.py` (HoD approval), `remediation.py` (owner + SLA), `reports.py`, `threat_intel.py`, `audit_log.py`, `settings.py`. All services live: `exploitability_service.py` (EPSS + KEV + composite scoring), `threat_intel_service.py` (MITRE CVE→APT, OTX IOC pulls), `asset_criticality_service.py` (per-tenant T1-T4), `sla_service.py`. Multi-tenancy, module subscription registry, and white-label theming are LIVE. **9 frontend admin pages** live: dashboard, risk-register, acceptance-workflow, remediation-tracker, audit-log, admin-modules, admin-tenants, admin-tenant-detail, admin-scoring.

### Connectors (`connectors/`)

| Connector | Status |
|---|---|
| Tenable, SentinelOne | ✅ LIVE (`connectors/tenable/`, `connectors/sentinelone/`) |
| Adverb tenant simulator | 🟡 SIMULATED |
| Zscaler, Netskope, MS Entra, SharePoint/OneDrive/Teams, ManageEngine SDP/EC/MDM, Burp Enterprise, GTB, CloudSEK | 🔴 TO BUILD (Phase 2A — 10 net-new) |

### Compliance Module (`compliance/backend/compliance_backend/`) — mostly ✅ LIVE

LIVE: FastAPI service scaffold on port 8001 with separate DB; `routers/frameworks.py` + 7 framework seeders (SOC 2, ISO 27001:2022, GDPR, HIPAA, PCI DSS v4.0, India DPDP Act 2023, NIST CSF 2.0); cross-framework control mapping (`seeders/cross_mappings.py`); `routers/controls.py` + `services/control_engine.py` + control rules; `services/evidence_service.py` + storage; `routers/policies.py` + `services/policy_manager.py`; `routers/vendors.py` + `services/vendor_risk.py`; `routers/auditor.py` + `auditor_invitations.py` + `admin_auditor_activity.py` + `services/auditor_service.py`; `routers/admin_evidence_requests.py`; `routers/compliance_score.py` + `services/scoring_engine.py`; auditor portal frontend (`compliance/frontend/auditor_portal.html`); demo simulators (control runs, evidence, policy acks, vendors, incidents, assets, access reviews, auditor activity, compliance scores).

🟡 PARTIAL: Risk → Control linkage (bridge live in compliance side; full event-bus integration pending Phase 3).

🔴 TO BUILD: LMS integration (KnowBe4 / Hoxhunt), BGV integration (AuthBridge / OnGrid), framework-specific report templates (SOC 2 board pack, ISO 27001 SoA, etc.).

### Test coverage and demo data (snapshot)

- **685 backend tests passing** across both services (URIP + Compliance)
- **424 framework controls** seeded across the 7 frameworks
- **12 connectors registered** (2 LIVE + 1 SIMULATED + 9 stub-registered; 10 net-new live builds in Phase 2A)
- **9 frontend admin pages** built and live
- **Demo `adverb-demo` seed:** 30 incidents, 5,104 control check runs across 90 days, 848 evidence files on disk, 18 vendors, 120 assets, 20 access review campaigns / 500 decisions, 4 auditor invitations + ~35 activity logs, 630 compliance score snapshots (90 days × 7 frameworks), 13 Fernet-encrypted URIP connector credentials, ~1,200 audit log entries

### Hybrid-SaaS deployment plumbing

✅ LIVE: connector framework, tenant Fernet credential vault, cloud-side tenant + license + module management, EPSS/KEV/MITRE/OTX cloud-side feeds.

🔴 TO BUILD (Phase 4, tasks H1-H10 per `DELIVERY_ARCHITECTURE.md`): Docker agent image (H1), encrypted reporter for agent → cloud signed payloads (H2), cloud ingest endpoint for metadata (H3), agent registration / license activation (H4), drill-down reverse-WebSocket tunnel (H5), aggregate metadata schema (H6), agent heartbeat (H7), agent / cloud version compatibility (H8), agent upgrade path (H9), install runbook for Adverb IT (H10).

---

## 9. Sales Pitch — Why Adverb Should Buy

**Data sovereignty (the procurement-clearing pitch).** Your sensitive vulnerability data — every IP address, hostname, username, evidence file — never leaves your network. It lives in a Postgres instance on your infrastructure, controlled by your IT team. Our cloud only ever sees a number: "8.2 risk score, 73% SOC 2 compliance, 11 of 12 connectors healthy." If our cloud is breached tomorrow, the attacker learns absolutely nothing about your internal infrastructure. When PepsiCo or J&J procurement asks *"where does your security tooling vendor store your sensitive data?"*, your answer is **"nowhere — it stays on our network."** Sprinto cannot give that answer; their entire model is cloud-side.

**Unified pane (the consolidation pitch).** One product replaces three: Sprinto for compliance automation, CloudSEK for external threat intelligence, and the manual aggregation spreadsheet your team currently maintains. One UX, one auth, one audit log, one tenant config. Your CISO sees risk; your Compliance Officer sees audit-readiness; your auditor sees evidence — all rendering from the same data layer. And the **Risk → Control linkage** ties them together in a way no other product can: when a CVE breaks SOC 2 control CC7.1, you see it instantly with the exact CVE, the exact asset, and the exact remediation owner. Sprinto's control failures are binary (pass / fail). Yours come pre-prioritised with full threat context.

**Cost (the math pitch).** Today's ballpark for the same outcome: Sprinto ₹20-40 lakh/year + CloudSEK ₹15-40 lakh/year + manual audit-prep consultant time ₹8-15 lakh/year + tool swivel-chair FTE overhead ₹15-25 lakh/year ≈ **₹58-120 lakh/year** — and you still don't have a unified risk view. URIP-Adverb bundles the compliance module, external threat (via CloudSEK API integration — Option A), and the risk-control linkage that neither vendor can offer, at a single competitive subscription with on-demand customisation included rather than billed as a separate consulting engagement.

---

## 10. Honest Risks + Open Questions

Real risks, not boilerplate. Each with a concrete mitigation.

- **Adverb refuses the Docker agent.** Some IT teams ban vendor containers. *Mitigation:* fall back to Pure SaaS (Option 1 in `DELIVERY_ARCHITECTURE.md`). Same code, different deployment.
- **Tool API changes.** Tenable, SentinelOne, MS Graph, ManageEngine all evolve. *Mitigation:* connector framework isolates blast radius — when an API goes from v1 to v2, only that connector updates. Connector versions pinned per tenant; controlled-wave rollouts.
- **Microsoft Graph throttling under load.** SharePoint/OneDrive/Teams audit logs at a 1,000-employee company can blow through Graph limits. *Mitigation:* exponential backoff with jitter, batch via `$batch`, respect `Retry-After`, shard by sub-site/user-cohort.
- **Burp Pro vs Enterprise license mismatch.** Burp Pro has a deliberately limited API; Burp Enterprise exposes the full programmatic surface we need. *Mitigation:* confirm Burp Enterprise **before SoW signing**. If only Pro, descope or upgrade — clear, written, before contracts.
- **OAuth and admin consent friction (especially MS Entra).** *Mitigation:* least-privilege scopes, tenant-guided consent flows, explicit "why we need this" documentation, IP allowlisting.
- **Compliance frameworks change.** SOC 2 moved 2017 → 2022 Trust Services Criteria; ISO 27001 had a 2022 revision; India DPDP rules still being notified. *Mitigation:* `framework_versions` table with `effective_date`, evaluate against either version during transition, framework updates committed as part of the subscription.
- **Auditor pushback on a new portal.** Many know Drata or Vanta. *Mitigation:* disproportionate investment in auditor UX, 30-minute walkthrough call for every first-time auditor, export-to-Drata-compatible-bundle escape hatch.
- **Drill-down tunnel security.** The reverse-tunnel is the most sensitive piece of Hybrid-SaaS. *Mitigation:* short-lived signed JWTs, mTLS, comprehensive audit log of every cloud-initiated drill-down, "off switch" Adverb's IT can flip, annual third-party pen test.
- **Connector "green but blind."** A connector "connected" but silently missing data due to scope changes. *Mitigation:* health checks validate coverage (expected volumes), not just connectivity; alerting on volume drops.
- **Adverb credentials delayed → Phase 2 blocked.** *Mitigation:* SoW scope clock starts when credentials arrive, not at signing. Adverb-flavored simulator data keeps the dashboard usable meanwhile.
- **Quality of URIP output depends on quality of input.** If Tenable scans miss assets, URIP reflects that gap. URIP is a unifier, not a scanner. Stated honestly in the SoW.
- **"We built Sprinto in 6 months" credibility gap.** We don't have full parity on day one. We have the architectural foundation, framework seeders, control engine, evidence automation, auditor portal, policy management — enough to be audit-ready for SOC 2 / ISO 27001 / India DPDP. Sprinto has more depth in some areas (200+ pre-built integrations vs our 12 + Phase 2C roadmap). We win on Risk-Control linkage, data sovereignty, and pricing — not on raw integration count.

### Open questions to confirm with client

- Confirm "Adverb" = Addverb Technologies (per market research — Reliance-owned warehouse robotics)
- Confirm the 11-tool stack matches operational reality, not aspirational future state
- Confirm Hybrid-SaaS comfort with running a Docker container in their network
- Confirm target frameworks (SOC 2 only? plus ISO 27001? plus India DPDP? plus GDPR?)
- Confirm Burp Suite Enterprise license (not Burp Pro)
- Confirm MS Entra is the identity provider (likely yes given Microsoft 365 stack)
- Confirm ManageEngine SDP is operational and writeable via API (for the bidirectional ticket loop)

---

## 11. Decisions Pending For Client Review

| # | Decision | Default position |
|---|---|---|
| 1 | Delivery model | Hybrid-SaaS (Option 3); Pure SaaS as fallback |
| 2 | CloudSEK Option A (integrate) vs B (build native) | Option A in this engagement; Option B as a follow-on conversation |
| 3 | Module subscription | Core + 9 modules (Adverb's expected default) |
| 4 | Frameworks targeted | SOC 2 + ISO 27001 + India DPDP — confirm; GDPR/HIPAA/PCI/NIST optional |
| 5 | Burp license | Burp Enterprise required (confirm before SoW) |
| 6 | Identity provider | MS Entra ID (confirm) |
| 7 | Ticket destination for auto-remediation | ManageEngine SDP (confirm operational + writeable) |
| 8 | Timeline | Discussed separately (per project rule) |
| 9 | Pricing | Discussed separately |

---

## 12. What Makes This Document Final

A 4-way synthesis written independently by Claude (Opus), Codex (OpenAI), Kimi (Moonshot), and Gemini (Google). Claude contributed concrete numbers and file references; Codex contributed the operational framing of the Test-Connection workflow and add-new-connector flow; Kimi contributed the hour-by-hour first-day narrative; Gemini contributed the compact buyer-facing pitch arc.

Cross-checked against the repo state — `ADVERB_BLUEPRINT.md`, `ADVERB_IMPLEMENTATION_PLAN.md`, `DELIVERY_ARCHITECTURE.md`, `compliance/README.md`, and the actual code in `backend/`, `connectors/`, `compliance/backend/compliance_backend/`, and `frontend/`. Where the four sources disagreed, accuracy against the repo won: the connector count is 12 (11 Adverb tools + CloudSEK); the frameworks are 7 (not 6); the Compliance Module routers, services, and seeders are LIVE today, not "to build."

Honest LIVE / PARTIAL / TO BUILD labelling preserved in Section 8. Of Adverb's 11 connectors, 2 are LIVE (Tenable, SentinelOne) plus 1 simulator; 10 are Phase 2A net-new. The Compliance Module's framework engine, control monitoring, evidence service, policy manager, vendor risk, auditor portal, and scoring engine are LIVE today; framework-specific report templates and LMS/BGV integrations are TO BUILD. Hybrid-SaaS deployment plumbing (Docker agent, encrypted reporter, drill-down tunnel) is TO BUILD as Phase 4.

The reader should leave with four things: (1) a clear product picture — what URIP-Adverb is and what it does in three clicks; (2) a clear architecture choice — Hybrid-SaaS as default, Pure SaaS as fallback, both supported by the same codebase; (3) a clear sell-narrative — data sovereignty + unified pane + cost consolidation, with Risk-Control linkage as the unique moat; (4) a clear risk surface — the twelve risks named and mitigated in Section 10.

---

**End of master vision document.**
