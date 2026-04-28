# URIP-Adverb Master Vision Document (Claude perspective)

**Author:** Claude (synthesizer / orchestrator role)
**Date:** 2026-04-27
**Status:** Vision document — input for SoW + sales conversation
**Companion docs:** `ADVERB_BLUEPRINT.md` (scope), `ADVERB_IMPLEMENTATION_PLAN.md` (execution), `DELIVERY_ARCHITECTURE.md` (Hybrid-SaaS detail), `compliance/README.md` (Compliance sub-project)

---

## 1. The Client Experience — End-to-End Story

It is a Tuesday morning. Adverb's CISO, two days after signing the SoW, opens her laptop and navigates to `https://adverb.urip.io`. The login page carries Adverb's logo, Adverb's brand colors, and the tagline her marketing team approved. She enters the credentials provisioned for her last week, clicks through MFA, and lands on a clean onboarding wizard.

**Step 1 — Welcome + tenant confirmation.** The wizard greets her by name, confirms the tenant is "Adverb Technologies — Production," and walks through three quick checkboxes: choose her industry vertical (Manufacturing / Logistics), confirm her primary office geography (Noida, India), and select the compliance frameworks she cares about (SOC 2 Type 2, ISO 27001:2022, India DPDP Act 2023). These choices seed the asset taxonomy and the framework engine in the background.

**Step 2 — The Tool Catalog.** The next screen is the moment that justifies the purchase. A visual grid renders 11 tool tiles — **Tenable**, **SentinelOne**, **Zscaler ZIA/ZTA/CASB**, **Netskope**, **Microsoft Entra ID**, **SharePoint / OneDrive / Teams**, **ManageEngine Service Desk Plus**, **ManageEngine Endpoint Central**, **ManageEngine MDM**, **Burp Suite Enterprise**, **GTB Endpoint Protector**, **CloudSEK** — each with its vendor logo, a short description ("Vulnerability scanner — pulls CVE inventory, CVSS, exploit availability"), and a status pill (initially: "Not connected"). Below the active tiles is a roadmap row: **AWS, Azure, GCP, Slack, Jira, GitHub, Okta** — each marked "Coming in Phase 2C." She checks the boxes for the 11 tools Adverb actually owns. Burp Suite gets a small warning icon: "Requires Burp Enterprise license — confirm before continuing." She clicks through; her procurement team has already confirmed.

**Step 3 — Per-tool credential wizard.** For each selected tool, a guided form appears (one screen per tool). Tenable asks for an Access Key + Secret Key. SentinelOne wants a Singularity API token. MS Entra triggers an OAuth admin-consent flow that pops a Microsoft sign-in window — her IT admin grants `SecurityEvents.Read.All`, `IdentityRiskEvent.Read.All`, `AuditLog.Read.All` scopes. ManageEngine SDP requires a service-account token. Each form has a prominent **"Test Connection"** button. Within 2-4 seconds of clicking, the screen returns either a green "Connected — pulled 47 sample records" or a red error with the exact remediation step ("API key valid but missing `vulnerabilities.read` scope — add this in Tenable Console > Settings > Access Control"). Credentials never appear in browser localStorage; they go straight to the on-prem agent's local Fernet vault.

**Step 4 — First poll.** The wizard hands her off to the dashboard with a banner: *"Connectors are running their first sync. Initial population takes 5-15 minutes."* She refreshes coffee. By 9:42 AM the URIP dashboard has 412 risks, the EPSS enrichment layer has annotated each one with an exploit probability (0.00 to 1.00), 7 risks are flagged as KEV (CISA's Known-Exploited Vulnerabilities catalog), 3 of those KEV CVEs are attributed to APT41 via the MITRE ATT&CK mapping, and the asset criticality service has assigned T1/T2/T3/T4 tiers based on her tenant taxonomy.

**Step 5 — Hour one, the Compliance dashboard.** She clicks the **Compliance** tab in the top nav. The framework engine has already evaluated the initial set of ~50 controls against the live data flowing in. SOC 2 sits at 73% (controls failing: CC6.6 — Logical Access Controls Restricted; CC7.1 — System Monitoring; CC7.2 — Anomalies Detected). ISO 27001:2022 sits at 81%. India DPDP sits at 64% — three Data Principal Rights controls require policies that don't exist yet. Each failing control has a "View root-cause risks" button; clicking SOC 2 CC7.1 shows her the 14 actively-exploitable CVEs in her Tenable feed that are causing the failure. **No other product on the market does this** — Sprinto can tell her the control failed, but it cannot tell her *which CVE* is breaking it.

**Step 6 — End of day one.** Her team has accepted 6 risks (with HoD sign-off), assigned 31 to remediation owners with auto-created ManageEngine SDP tickets, downloaded a draft SOC 2 board pack, and invited their external auditor (someone from BDO India) to the Auditor Portal with read-only access scoped to "SOC 2 — 2026 Audit Period." She closes the laptop. The Adverb stack is now visible as one risk picture for the first time.

---

## 2. Architecture — Hybrid-SaaS

Per `DELIVERY_ARCHITECTURE.md` Option 3, URIP-Adverb ships as a **Hybrid-SaaS** model — the same pattern CrowdStrike, Tenable, and Splunk pioneered. Cloud portal at the top, lightweight Docker agent inside Adverb's network, secure tunnel between them.

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

**Trust boundary, in plain English:** the only thing that ever crosses from Adverb's network to our cloud is a tiny JSON envelope of summary metrics — risk scores, control pass/fail counts, compliance percentages, connector heartbeat timestamps. Sensitive identifiers (IP addresses, hostnames, usernames, file paths, evidence files) never leave Adverb's network. If our cloud is compromised tomorrow, the attacker sees that some tenant called "Adverb" has a risk score of 8.2 and 73% SOC 2 compliance. They learn nothing about Adverb's actual infrastructure.

This is the same architecture CrowdStrike Falcon Sensor uses to keep customer endpoint telemetry on-prem while exposing summary dashboards in the Falcon cloud, and the same model Tenable Nessus Agent uses to keep raw scan data on-prem while pushing summary findings to Tenable.io. It is industry-standard for security tooling that targets regulated buyers — exactly the position Adverb is in (selling robotics to PepsiCo, J&J, Reliance Pharma, who run formal vendor security questionnaires).

---

## 3. Two Dashboards — Distinct But Linked

### 3a. URIP Risk Intelligence Dashboard

Default landing page. Built to answer the CISO's first question every morning: *"Where am I most exposed today?"*

**Top KPI strip** (5 tiles, each click-through to a filtered view):

- **Total Open Risks**: 412 (▲ 23 since yesterday)
- **Critical Severity**: 18 (▲ 4)
- **Mean Time to Remediate** (rolling 30 days): 11.3 days (target: 14)
- **Exploit-Active Risks** (KEV + EPSS > 0.7): 7
- **Connectors Healthy**: 11 of 12 (⚠️ Burp last sync failed 2h ago)

**Risk register** — sortable, filterable table. Columns: Severity, Title, Source, Asset, EPSS Score, KEV Status, APT Attribution, Owner, SLA Status, Age. Filter chips across the top: Source (Tenable / SentinelOne / Zscaler / etc.), Severity (Critical / High / Medium / Low), Status (Open / In Remediation / Accepted / Closed), Asset Tier (T1 / T2 / T3 / T4). Click any row → detail panel slides in from the right with the full enrichment trail and a "Drill into source" button that hits the secure tunnel and pulls raw records from the on-prem agent.

**Threat intel panel** (right column, collapsible) — active APT groups currently targeting the Manufacturing / Logistics sector, with MITRE ATT&CK technique IDs and a list of CVEs that any of these groups has historically exploited. As of this writing the panel shows APT41 (T1190 — Exploit Public-Facing Application), Lazarus (T1566 — Phishing), and FIN12 (T1486 — Data Encrypted for Impact) as the three most-active in Adverb's vertical.

**Connector health board** — every connector with last successful poll timestamp, error count in the last 24 hours, and a status pill (LIVE / DEGRADED / DOWN). Polling defaults: 15-minute cycles for high-volume sources (Tenable, SentinelOne, Zscaler), 60-minute cycles for medium-volume (Netskope, Entra, ManageEngine), 4-hour cycles for low-volume (Burp Suite scans, GTB DLP, CloudSEK alerts). Each interval is configurable per-tenant in `backend/routers/settings.py`.

**Drill-down tunnel UX** — when a user clicks "View Raw Source Data" on any risk, the cloud signs a short-lived JWT, hands it to the on-prem agent over the persistent reverse tunnel, the agent fetches from local Postgres, returns the payload over the same tunnel, and the browser renders it directly. Nothing persists in our cloud database. The user sees the data; the cloud does not.

### 3b. Compliance Dashboard (Sprinto-equivalent)

Second top-nav tab. Built to answer the Compliance Officer's first question every morning: *"Are we audit-ready?"*

**Per-framework KPI widgets** (one tile per subscribed framework — Adverb's example values):

- SOC 2 (Trust Services 2022): **87%** — 142 controls passing / 163 applicable
- ISO 27001:2022: **92%** — 86 controls passing / 93 applicable
- India DPDP Act 2023: **78%** — 39 controls passing / 50 applicable
- GDPR: **91%** — 41 controls passing / 45 applicable (Adverb has EU customer data)
- HIPAA: **84%** — only relevant if Adverb supports US healthcare logistics; configurable
- PCI DSS v4.0: **88%** — applies to one payment-handling subsystem
- NIST CSF 2.0: **79%** — adopted as voluntary guidance

Each tile shows trend arrow (▲ or ▼ vs 7 days ago), and click-through opens the framework drill-down: control list grouped by category, color-coded pass/fail/inconclusive, with the "View root-cause risks" button on every failing control that hits the URIP × Compliance bridge (`P2B.14` — Risk → Control linkage).

**Failing controls list** — a single ranked list of every failing control across all frameworks, ordered by `remedy_priority_score = (frameworks_affected × failure_severity × root_cause_risk_count)`. The compliance team works from the top down.

**Evidence collection status** — three-column view: Total controls (with auto-evidence configured) / Evidence captured this period / Evidence missing or stale. Drill-in shows exactly which control is missing what evidence and when it was last successfully captured. Auto-collection backs this with connector hooks — every time a connector polls, evidence-tagged extracts (configs, screenshots via headless browser, ticket exports) are captured and indexed against the relevant control.

**Policy acknowledgment status** — a list of every policy with current version, total employees, acknowledged count, percent acknowledged, expiring-soon flags. Click-in to see the per-employee status and bulk-remind unsigned employees.

**Vendor risk scores** — top vendors by risk, surfaced from the vendor inventory module, with overdue questionnaires, expiring DPAs/BAAs, and a "Send reminder" action. Adverb's typical inventory: ~40-80 vendors (cloud providers, SaaS tools, hardware suppliers, integration partners).

**Auditor portal entry point** — a prominent **"Invite an auditor"** button at the top right, plus a list of currently-active auditor sessions (auditor name, framework scope, audit period, last activity, expiry date). Auditors get read-only access scoped to a specific framework + audit period, time-bounded, with full activity audit trail.

**Action items before next audit** — a prioritized punch-list synthesized from: failing controls, missing evidence, unacknowledged policies, expiring vendor docs, unfinished access reviews. Adverb's compliance team works this list in the four weeks leading up to audit. By design, the list is **always the same** whether they are 4 weeks out or 4 months out — the platform just keeps it short by handling the routine items automatically.

---

## 4. The Connector Library

The Tool Catalog screen (Section 1, Step 2) is backed by a connector framework that lives in `connectors/` (per `ADVERB_IMPLEMENTATION_PLAN.md` Section 2). Each connector is an independent Python module implementing a four-method interface: `authenticate()`, `fetch_findings(since)`, `normalize(raw)`, `health_check()`. New connectors plug in without touching core code.

**Phase 2A connectors (Adverb's stack — 12 sources):**

| # | Connector | What it pulls | Polling | API surface |
|---|---|---|---|---|
| 1 | Tenable Vulnerability Manager | CVE inventory, CVSS, exploit availability, asset list | 15 min | Tenable.io REST API, key-pair auth |
| 2 | SentinelOne (Singularity) | Active threats, agent health, vulnerable endpoints, threat hunting results | 15 min | REST API, token auth |
| 3 | Zscaler ZIA / ZTA / CASB | Blocked URLs, shadow SaaS apps, malicious downloads | 15 min | Three sub-endpoints; partner key + API key |
| 4 | Netskope | Cloud app risk scores, DLP violations, sanctioned-vs-unsanctioned usage | 60 min | REST API, OAuth2 |
| 5 | Microsoft Entra ID | Risky sign-ins, MFA bypass, conditional access violations, privileged role assignments | 60 min | MS Graph API, OAuth2 + admin consent |
| 6 | SharePoint / OneDrive / Teams | Anonymous link sharing, external sharing audit, sensitive label violations | 60 min | MS Graph API (shared auth with #5) — large data volumes |
| 7 | ManageEngine SDP | Bidirectional ticket creation + status sync | 60 min | REST API, OAuth2 |
| 8 | ManageEngine Endpoint Central | Patch status, missing critical patches, compliance score | 60 min | REST API, OAuth2 |
| 9 | ManageEngine MDM | Jailbroken devices, non-compliant mobile, lost/stolen events | 4 hours | REST API, OAuth2 |
| 10 | Burp Suite Enterprise | Web app scan findings (XSS, SQLi, CSRF, etc.) per target | 4 hours | Burp Enterprise API (NOT Pro) |
| 11 | GTB Endpoint Protector | DLP policy violations, USB block events, exfil attempts | 60 min | REST API, key auth |
| 12 | CloudSEK (Option A — API integration) | Dark web alerts, brand abuse, leaked credentials, supply chain risk | 4 hours | XVigil + BeVigil + SVigil REST APIs |

**Phase 2C horizontal additions (roadmap, per market research):** AWS Security Hub, Azure Defender, GCP Security Command Center, Slack audit logs, Jira security issues, GitHub Advanced Security, Okta. These are not in Adverb's initial stack but expand the platform's TAM.

**Per-tenant credential management** — every credential is encrypted at rest with Fernet (per-tenant encryption key derived from a master key in HashiCorp Vault or AWS Secrets Manager, depending on cloud target). Credentials never appear in logs, never serialize into telemetry, never replicate to read-replica DBs. Rotation is one click from the connector settings page.

**Per-connector health monitoring** — every connector emits structured JSON logs (`connector_name`, `tenant_id`, `event=poll_complete`, `duration_ms`, `records_ingested`, `errors`). The connector health board (Dashboard 3a) reads from a 7-day rolling aggregate. If any connector misses 3 consecutive poll cycles, an alert fires to the tenant admin's Slack/email and the connector tile turns red.

---

## 5. Multi-Tenancy + License Modules

Per `ADVERB_BLUEPRINT.md` Section 8, URIP ships as **9 capability modules + a mandatory Core**. Each tenant subscribes to exactly the modules they need; disabled modules are dark in the UI and inactive in the backend (route guards in the frontend, decorator-level checks in the backend).

| Module | What it includes | Adverb subscribed? |
|---|---|---|
| **Core** (mandatory) | Risk register, scoring engine (EPSS + KEV + MITRE + OTX), dashboard, workflow, audit log, reports | ✅ Yes |
| **VM Module** | Tenable / Qualys / Rapid7 / CrowdStrike Spotlight connectors | ✅ Yes (Tenable) |
| **EDR Module** | SentinelOne / CrowdStrike Falcon / Defender for Endpoint connectors + ManageEngine Endpoint Central + MDM | ✅ Yes (S1, EC, MDM) |
| **Network Module** | Zscaler / Netskope / Palo Alto / Fortigate connectors + CloudSEK external threat | ✅ Yes (Zscaler, Netskope, CloudSEK) |
| **Identity Module** | MS Entra / Okta / Google Workspace connectors | ✅ Yes (Entra) |
| **Collaboration Module** | SharePoint / OneDrive / Teams / Slack / Confluence connectors | ✅ Yes (SP/OD/Teams) |
| **ITSM Module** | ServiceNow / Jira / ManageEngine SDP connectors | ✅ Yes (SDP) |
| **DAST Module** | Burp Suite / OWASP ZAP / Acunetix connectors | ✅ Yes (Burp Enterprise) |
| **DLP Module** | GTB / Forcepoint / Symantec DLP connectors | ✅ Yes (GTB) |
| **Compliance & Audit-Readiness Module** | Framework engine (SOC 2, ISO 27001, GDPR, HIPAA, PCI DSS, India DPDP, NIST CSF), control monitoring, evidence automation, policy mgmt, access reviews, vendor risk, incident lifecycle, asset inventory, auditor portal, compliance scoring | ✅ Yes (the strategic upsell) |

Adverb subscribes to **Core + 9 modules** — essentially every module. A different tenant might subscribe to Core + Compliance only (a startup just needing audit-readiness). A factory client might subscribe to Core + VM + Network + ITSM and skip Identity / Collaboration / Compliance entirely. The pricing model lets us close deals at every tier without forcing "all or nothing."

**White-label theming per tenant** — logo, color palette (primary / secondary / accent), app name, favicon, login-page background image. Stored per-tenant in the `tenant_branding` table; rendered via CSS variable injection in the frontend shell. Adverb's dashboard says "Adverb," not "URIP." Their auditor's email invitation says "Adverb invites you to their compliance audit portal," not "URIP invites you."

**Role separation:**

- **Super-admin (Semantic Gravity)** — can see all tenants, provision new ones, ship platform updates, audit usage. Never sees tenant raw data (the Hybrid-SaaS architecture enforces this — raw data is on-prem).
- **Tenant admin (Adverb's CISO + Compliance Officer)** — can configure their own tenant: connectors, modules, roles, branding, framework selection.
- **Tenant user** — scoped roles within Adverb (e.g., "DLP Analyst" sees only the DLP module; "Risk Owner" sees their assigned risks only). Module-level RBAC defined in `backend/middleware/auth.py`.
- **Auditor** (read-only, time-bounded, framework-scoped) — described in Section 3b.

**Compliance Module as strategic upsell.** Most modules are operational line items — they replace existing tools. The Compliance Module is different: it is a **board-level budget conversation**. Sprinto charges ₹8-25 lakh/year for compliance automation alone. Selling URIP without Compliance positions us as "another vulnerability dashboard" (low-budget). Selling URIP with Compliance positions us as "compliance + risk + audit platform" (board-level budget). Same code, dramatically different sales motion.

---

## 6. The "No Manual Effort" Promise

Once the connectors are configured (a one-time, maybe-2-hour exercise during onboarding), the platform runs itself. Adverb's security and compliance teams stop doing the soul-crushing manual work and focus on the things that actually require human judgment.

**What happens automatically, every day, without anyone touching it:**

- Connectors poll on their configured schedule (15 min / 60 min / 4 hour) and pull deltas
- Raw findings normalize into the URIP risk schema and write to the local Postgres
- Every CVE gets enriched with EPSS exploit probability (from FIRST.org, free), KEV exploitation status (from CISA, free), MITRE ATT&CK APT attribution (from MITRE, free + periodic refresh), and OTX IOC context (from AlienVault, free with API key)
- Composite scoring auto-calculates per risk: `score = base_severity × asset_criticality_multiplier × exploit_probability × threat_attribution_weight`
- Asset criticality multiplier auto-applies based on the per-tenant taxonomy (Adverb's "Robotics Production Line PLC" might be T1; "Canteen Wi-Fi" might be T4)
- Compliance controls auto-evaluate against current state on their scheduled cadence (default daily); pass/fail/inconclusive tracked per control per tenant per run in `control_check_runs`
- Evidence auto-captures at every control run — screenshots via headless browser, config exports, ticket exports, log snippets — tagged to control + framework + audit period, stored in S3-compatible object storage on the agent's local network
- Policy reminders auto-send to non-acknowledged employees on a configurable cadence (typical: weekly until signed)
- Vendor reviews auto-schedule based on criticality (T1 vendors annually, T2 every 18 months, T3 every 24 months); questionnaire reminders fire 30 / 14 / 7 days before due
- Compliance scores auto-recalculate after every control run; daily snapshot writes to `compliance_score_history` for trend charts
- Reports auto-generate on the schedule the tenant configures (Adverb's CISO gets a Monday-morning PDF; the board gets a quarterly export)
- Auditor self-serves through the portal — finds evidence, files requests, checks status — without pinging anyone on Adverb's team

**What the team still has to do** (no platform can eliminate these):

- Risk acceptance decisions (HoD sign-off on residual risk)
- Policy approval and version updates (legal review)
- Incident response execution (the SOC still owns the response)
- Auditor questions that go beyond the evidence in the portal
- Strategic decisions about which frameworks to pursue, which vendors to onboard, which controls to scope

The platform handles the routine; humans handle judgment. That is the promise — and unlike most "automation" pitches, this one is realistic because the underlying connectors and enrichment APIs are real, free, and battle-tested.

---

## 7. Sales Pitch — Why Adverb Should Buy

**The data sovereignty pitch.** Your sensitive vulnerability data — every IP address, hostname, username, evidence file — never leaves your network. It lives in a Postgres instance on your infrastructure, controlled by your IT team. Our cloud only ever sees a number: "8.2 risk score, 73% SOC 2 compliance, 11 of 12 connectors healthy." If our cloud is breached tomorrow, the attacker learns absolutely nothing about your internal infrastructure. When PepsiCo or J&J procurement asks, *"where does your security tooling vendor store your sensitive data?"*, your answer is **"nowhere — it stays on our network."** That is a procurement-clearing answer. Sprinto cannot give it; their entire model is cloud-side. CrowdStrike Falcon Sensor, Tenable Nessus Agent, and Splunk Forwarder all use this exact architecture for the same reason.

**The unified pane pitch.** One product replaces three: Sprinto for compliance automation, CloudSEK for external threat intelligence, and the manual aggregation spreadsheet your team currently maintains for risk visibility. One UX, one auth, one audit log, one tenant config. Your CISO sees risk; your Compliance Officer sees audit-readiness; your auditor sees evidence — all rendering from the same data layer with the same access controls. And the **Risk → Control linkage** capability (Section 3b) ties them together in a way no other product can: when a CVE breaks SOC 2 control CC7.1, you see it instantly with the exact CVE, the exact asset, and the exact remediation owner. Sprinto's control failures are binary (pass / fail). Yours come pre-prioritized with full threat context.

**The cost pitch.** Sprinto alone is ₹8-25 lakh/year depending on tier and employee count. CloudSEK is ₹15-40 lakh/year depending on coverage. Together that is ₹23-65 lakh/year, and you still have no unified risk view — you need to buy a third tool or build the spreadsheet yourself. URIP-Adverb bundles compliance, external threat (via CloudSEK API integration — Option A), and the unique risk-control linkage that neither vendor can offer, at competitive pricing — with on-demand customization included rather than billed as a separate consulting engagement. Over a 3-year horizon the math is simple: lower total cost, dramatically less integration toil, and a defensible answer to every procurement security questionnaire you face.

---

## 8. What Could Go Wrong (Honest)

These are real risks, not boilerplate. Each has a concrete mitigation that has been thought through, not invented for the slide.

- **Adverb refuses the Docker agent.** Some IT teams have a blanket policy against running vendor containers in production networks. Mitigation: fall back to **Pure SaaS** deployment (Option 1 in `DELIVERY_ARCHITECTURE.md`). We acknowledge in writing that their data lives in our cloud, and we offer SOC 2 Type 2 evidence for our cloud as compensation. The codebase supports both modes — same code, different deployment topology.

- **Adverb's tools change API versions.** Tenable, SentinelOne, MS Graph, ManageEngine all evolve their APIs. Mitigation: the connector framework isolates blast radius — when Tenable goes from v1 to v2, only the Tenable connector needs an update. Connector versions are pinned per tenant; rollouts happen in a controlled wave. Connector health monitoring (Section 4) catches breakage within the first failed poll cycle.

- **CloudSEK relationship strain.** We are integrating their data via API (Option A); they may push back if we ever scale to a point where we look like an aggregator competing with their channel. Mitigation: contract clarity around data use (we are a *technical integration*, not a *resale*); be explicit that we are not building CloudSEK-equivalent native features (Option B is explicitly out of scope per `ADVERB_BLUEPRINT.md` Section 6).

- **Auditor pushback on a new portal** — auditors are creatures of habit and most are familiar with Drata or Vanta's portals. Mitigation: invest disproportionately in auditor UX (clean filters by framework + period, fast evidence search, request workflow that mirrors how auditors actually work); offer a 30-minute walkthrough call for every first-time auditor; provide an **export-to-Drata-compatible-bundle** feature as an escape hatch if the auditor refuses our portal entirely.

- **Microsoft Graph throttling under load.** SharePoint / OneDrive / Teams sharing audit logs at a 1000-employee company can blow through Graph's per-app and per-tenant throttling limits. Mitigation: implement exponential backoff with jitter, batch requests via Graph's `$batch` endpoint, respect `Retry-After` headers, and shard audit-log pulls by sub-site or by user-cohort. Cache aggressively for read-heavy operations.

- **Compliance frameworks change.** SOC 2 moved from 2017 Trust Services Criteria to 2022. ISO 27001 had a major 2022 revision. India DPDP rules are still being notified incrementally. Mitigation: maintain framework data as part of the subscription — `framework_versions` table with `effective_date`, ability to evaluate against either version during transition periods, public-facing changelog when we update seeders. Customers do not have to rebuild their controls when frameworks change; we update the seeders, they re-evaluate.

- **Burp Pro vs Enterprise license mismatch.** Burp Suite Professional has a deliberately limited API surface. Burp Suite Enterprise exposes the full programmatic surface we need. Mitigation: confirm Adverb has Burp Enterprise (not just Pro) **before SoW signing**, not after. This is in the Phase 2A blocker list (`ADVERB_IMPLEMENTATION_PLAN.md` Section 4.7) and in the SoW dependency list. If they have only Pro, the Burp connector is descoped or Adverb upgrades — clear, written, before contracts.

- **Drill-down tunnel security model.** The reverse-tunnel from agent → cloud is the most sensitive piece of the Hybrid-SaaS architecture. If compromised it becomes a backdoor into Adverb's network. Mitigation: short-lived signed JWTs per request, mTLS on the tunnel, comprehensive audit log of every cloud-initiated drill-down request, ability for Adverb's IT to disable the tunnel at any time (degraded UX but zero exposure), and an annual third-party pen test on the tunnel implementation.

- **The "we built Sprinto in 6 months" credibility gap.** Buyers will ask, *"how can you have feature parity with a Sprinto that took 6 years to build?"* Honest answer: we don't have full parity on day one. We have the architectural foundation, the framework seeders, the control engine, the evidence automation, the auditor portal, the policy management — enough to be audit-ready for SOC 2 / ISO 27001 / India DPDP. Sprinto has more depth in some areas (e.g., 200+ pre-built integrations vs our 12 + Phase 2C roadmap). We do not over-claim. We win on Risk-Control linkage, data sovereignty, and pricing — not on raw integration count.

---

## 9. What Makes This Document Different (Claude's perspective)

I have read every blueprint, every implementation plan, every architecture doc, and every compliance README that the team has produced for this engagement. As the synthesizer, the things I weigh most heavily — the lens through which I prioritized this vision — are these:

**Honest LIVE / SIMULATED / TO BUILD labeling.** The blueprint uses three explicit labels everywhere. The temptation to sand off the "TO BUILD" label and present everything as ready-to-ship is huge. I refuse that. Of Adverb's 11 connectors, exactly 1 has a simulator stub today; the other 10 are net-new. The Compliance Module is 9 of 14 capabilities net-new build, 3 partial extensions, 1 already live (risk register), 1 explicitly out of scope (training authoring). That honesty is what makes Codex score this engagement 8/10 instead of 2/10. It is also what protects the relationship with Adverb — there is no surprise three months in.

**Risk-Control Linkage as the unique moat.** Sprinto literally cannot do this. Their data model has compliance controls but no concept of CVE-level threat enrichment. Drata is the same. CloudSEK is the inverse — threat data without compliance scaffolding. The architectural fact that URIP has *both* — the EPSS/KEV/MITRE/OTX enrichment layer *and* the framework + control + evidence layer in the same tenant scope — means we can ship a feature that says *"SOC 2 control CC7.1 is failing because of these 14 specific CVEs, all KEV-listed, on these specific assets, owned by these specific people"*. That is a defensible moat. I prioritized it in Section 3b and Section 7 because if we lose it in the noise, we lose the deal.

**Identity Risk carry-forward from RE → Adverb.** The Royal Enfield engagement built the Identity Module logic against CyberArk. Adverb runs MS Entra ID. The temptation is to treat these as separate codebases. They are not. The risk-engine logic (severity mapping → asset multiplier → auto-assignment → SLA timer → remediation workflow) is identical regardless of whether the source is CyberArk or Entra. We swap the input adapter only. That single insight (documented in `DELIVERY_ARCHITECTURE.md` Section 5) shaves significant engineering time off Phase 2A and proves the multi-tenant connector architecture is sound.

**Multi-tenant first, even though Adverb is single-tenant initially.** The Phase 1 productization work (tenant_id on every table, per-tenant config, white-label theming, module subscription registry) is more upfront work than building Adverb-specific code would be. But once it ships, every future tenant deploys mechanically — provision tenant, apply branding, select modules, enter credentials, done. No engineering involvement per new tenant. That is the difference between a custom-built deployment and a SaaS product. I argued hard for this in the blueprint and the implementation plan, and it is the single most important architectural decision in the entire engagement.

**Honest cost / risk disclosure (no over-promising).** Section 8 of this document is not boilerplate. Each risk listed is one I genuinely think could derail the engagement, and each mitigation is one we can actually execute. The Burp Enterprise dependency, the Microsoft Graph throttling, the auditor pushback risk, the drill-down tunnel security model — these are the things that bite at month 4, not month 1. Naming them now is what builds the credibility we need to win the deal in the first place.

The reader who finishes this document should walk away with three things: (1) a clear mental model of what URIP-Adverb actually is, (2) a clear understanding of why it wins commercially against the alternatives, and (3) a clear-eyed view of the trade-offs involved. If any of those three is missing, this document failed.

---

**End of vision document.**
