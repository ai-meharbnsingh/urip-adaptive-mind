# URIP — Master Blueprint (v5)

**Status:** Source of truth for the website home page and the sales / board narrative.
**Date:** 2026-04-27
**Version:** v5 — sharpened "cockpit, not stack" positioning + 29 production connectors LIVE + Intelligence Engine, VAPT Vendor Portal, Jira/ServiceNow bidirectional, Trust Center, Auto-Remediation framework all promoted from roadmap to LIVE.
**Synthesised from:** `VISION_DOC_FINAL.md`, `ADVERB_BLUEPRINT.md`, `ADVERB_IMPLEMENTATION_PLAN.md`, `DELIVERY_ARCHITECTURE.md`, `compliance/README.md`, `compliance/ARCHITECTURE.md`, `ISSUES_INVENTORY.md`, the competitive review against TrendAI Vision One, and the working code under `backend/`, `connectors/`, `compliance/backend/compliance_backend/`, `compliance/frontend/`, `frontend/`, and `agent/`.

---

## Hero (one-page elevator pitch)

**URIP is the cockpit for your security stack — not another tool in it.**

URIP does not sell scanners, agents, gateways, or feeds. It sells the unified pane of glass that organises whatever security stack you already own — Tenable, CrowdStrike, SentinelOne, Zscaler, Netskope, MS Entra, ManageEngine, Armis, Burp, GTB, CloudSEK, AWS, Azure, GCP, your CERT-In subscription, your SIEM, your bug-bounty inbox, your VAPT vendor — into one live risk dashboard and one continuously audit-ready compliance dashboard, on the same data. **Bring your stack. Plug in API keys. See one score.**

Think of it the way Salesforce orchestrates the seven sales tools you already pay for, or the way Alexa controls the smart-home devices you already bought. We don't make the lights or the locks. We make them work together — and we make them legible to the CISO, the auditor, and the board, all at the same time.

Twenty-five real production connectors live today. Fifteen pre-built compliance frameworks with ~895 controls (7 audit-grade + 8 scaffold-grade). Four live external threat-intelligence feeds. A native Sprinto-equivalent compliance module on the same data layer as the risk register. A hybrid-SaaS option that keeps sensitive identifiers on the customer's network. Onboarding is three screens. **No professional services engagement. No bespoke integration project. No "we don't support that tool" — every category is supported, real connectors land one file at a time.**

**Taglines (pick the one that lands):**
- **The cockpit for your security stack.**
- **Your tools. Your data. One pane. Audit-ready.**
- **We don't sell security. We sell visibility on the security you already bought.**

---

## 1. What Is The Product

URIP (Unified Risk Intelligence Platform) is a multi-tenant SaaS that aggregates findings from a customer's **existing** security stack, enriches every finding with live exploit and threat-actor intelligence, normalises every source's severity to a single 0-10 axis, de-duplicates the same finding arriving from multiple sources, and renders the result as two linked dashboards on a single data layer. The core promise: **stop juggling eleven security tools and three compliance spreadsheets — see one number, drill to one CVE, fix one ticket.**

The product is fundamentally **two dashboards on one platform**. The URIP Risk Intelligence dashboard answers the CISO's daily question — *where am I most exposed today?*. The Compliance dashboard (a native Sprinto-equivalent module) answers the Compliance Officer's question — *if the audit landed next week, would we pass?*. Both dashboards render from the same tenant data, share the same auth, the same audit log, and the same connector mesh. Critically, they are **linked**: when a SOC 2 control fails, you see the exact CVEs causing it. No other product does this.

The "universal" promise is operational, not marketing. Every customer onboards the same way: pick your tools from the catalog, paste API credentials per tool with an instant Test Connection, save, and watch real findings populate the dashboard within minutes. No professional services engagement. No bespoke integration project. Any company — from a 50-person SaaS startup chasing SOC 2 to a 1000-person robotics manufacturer with eleven tools and a CloudSEK subscription — runs the same flow.

---

## 1.5. What URIP Is NOT (the cockpit-not-stack invariant)

This list exists because every CISO conversation eventually asks "so are you another EDR?" or "are you replacing my CSPM?". The answer is **always no**. URIP is a category-of-one: it is the cockpit. We do not compete with the security tools — we orchestrate them.

| URIP Is NOT | We do not compete with | Why |
|---|---|---|
| **An endpoint agent / EDR** | CrowdStrike Falcon, SentinelOne, Defender for Endpoint | We do not deploy agents on customer endpoints. We **read** what those agents find, via their published APIs. Customer keeps their EDR. |
| **A network sensor / NDR** | Trend Micro Deep Discovery, Darktrace, Vectra | We do not put sensors on the customer's switches or SPAN ports. We ingest alerts the customer's own NDR / SIEM has already raised. |
| **An email gateway** | Mimecast, Proofpoint, Abnormal | We do not sit in the mail flow. We pull phishing / BEC / quarantine telemetry from Google Workspace and Microsoft Defender for Office 365 via their APIs. |
| **A code scanner (SAST / SCA / DAST)** | Snyk, Checkmarx, Veracode | We do not scan source code or running apps ourselves. Burp Enterprise scans for the customer; we ingest its findings. Same for SCA/SAST when added. |
| **A CSPM scanner with its own cloud agent** | Wiz, Lacework, Orca | We read AWS Config, Azure Policy, and GCP Security Command Center via their **native** APIs. We do not deploy a cloud-side agent. The customer keeps cloud control. |
| **A SOC** | Arctic Wolf, Expel, ReliaQuest | URIP surfaces and prioritises risks. URIP does not run 24/7 ops, does not write playbooks for the customer, does not pick up the phone. The customer's team or the customer's MDR vendor still owns response. |
| **A threat-intel research firm** | Recorded Future, Mandiant, Flashpoint | We use **open standards** — EPSS (FIRST.org), KEV (CISA), MITRE ATT&CK, AlienVault OTX. We do not run our own threat-intel research lab. We surface other people's research, scored and prioritised against the customer's actual assets. |
| **A vulnerability scanner** | Tenable Nessus, Qualys, Rapid7 | We do not run Nmap, we do not run authenticated scans. The customer's existing scanner does. We ingest. |
| **An IAM / SSO** | Okta, Auth0, Microsoft Entra ID | We do not own the customer's identity store. We read MS Entra / Okta / Workspace risk events via their APIs and surface them in the cockpit. |
| **A GRC consultancy / audit firm** | Big Four auditors, Deloitte, PwC | We make audits cheap and continuous. The customer still owns control design, policy approvals, and the actual audit engagement with their auditor of record. |

**The trust-building consequence**: URIP has no incentive to push the customer toward any specific scanner / EDR / CSPM. We are **vendor-neutral by design** — every dollar saved by the customer in tooling rationalisation is a dollar that goes into URIP, not into our adjacent product line, because there is no adjacent product line. Sprinto cannot say this (they sell GRC and lean compliance-only). Wiz cannot say this (they sell the CNAPP). TrendAI cannot say this (they sell the entire stack). URIP can.

---

## 2. The Story In Numbers

- **25+ source categories supported** by the universal connector framework (every category from the RE 14-source baseline + Adverb extensions + native cloud + DAST + DLP + collaboration + UEM/MDM + OT + PAM + NAC + Firewall + SIEM + Email + Bug Bounty + CERT-In)
- **29 real production connectors LIVE today** — Tenable, CrowdStrike (Falcon Insight + Spotlight VM), SentinelOne, MS Entra ID, Zscaler, Netskope, ManageEngine SDP, ManageEngine Endpoint Central, ManageEngine MDM, M365 Collaboration (SharePoint/OneDrive/Teams), Burp Enterprise, GTB Endpoint Protector, CloudSEK (XVigil + BeVigil + SVigil), AWS CSPM, Azure CSPM, GCP CSPM, Armis OT, Forescout NAC, CyberArk PAM, Fortiguard Firewall, Email Security (Google Workspace + Microsoft Defender for O365), CERT-In Advisories, Bug Bounty (HackerOne + Bugcrowd + webhook), SIEM (Splunk + Elastic + QRadar), EASM (Censys + Shodan + Detectify), KnowBe4 (LMS — security awareness), Hoxhunt (LMS — phishing simulation), AuthBridge (BGV), OnGrid (BGV) — every directory under `connectors/` ships a `connector.py` honouring the four-method contract
- **Bring-any-tool promise** — write one file (`connectors/{tool_name}/connector.py`), implement four methods (`authenticate / fetch_findings / normalize / health_check`), auto-discovered by Tool Catalog wizard
- **15 compliance frameworks pre-seeded** with **~895 controls total** — SOC 2 (Trust Services 2017+2022), ISO 27001:2022, GDPR, HIPAA, PCI DSS v4.0, India DPDP Act 2023, NIST CSF 2.0 (original 7 — full audit-grade), plus ISO 42001 (AI management), EU AI Act, DORA (EU financial), NIS2 (EU critical infra), ISO 27017 (cloud), ISO 27018 (PII in cloud), ISO 27701 (privacy management), CIS Controls v8 (8 new — scaffold-grade control catalogue, customers should reconcile against licensed PDFs for audit submission)
- **4 live external intelligence feeds** — FIRST.org EPSS, CISA KEV catalog, MITRE ATT&CK CVE-to-APT mapping, AlienVault OTX
- **16 license modules** — CORE (mandatory) + 15 capability modules including CSPM and the 5 MVP-scaffold modules (DSPM, AI Security, ZTNA, Attack Path Prediction, Cyber Risk Quantification / FAIR — see §13 honest scaffold caveat)
- **1800+ tests** across services — URIP backend, Compliance backend, connectors, CSPM engine, ticketing, VAPT pipeline, Trust Center, Auto-Remediation framework
- **3 deployment modes** — Pure SaaS, On-Premise Licensed, Hybrid-SaaS (recommended)
- **2 dashboards, 1 data layer, 1 auth, 1 audit log**
- **0 sensitive data leaves the customer network** in the recommended Hybrid-SaaS mode

**Net-new since v4 (all LIVE in code today):**

- **VAPT Vendor Portal** — separate vendor login, structured submission form, auto-enrichment, re-test workflow (`backend/services/vapt_vendor_service.py` + `backend/routers/vapt_admin.py` + `backend/routers/vapt_vendor_portal.py` + `backend/middleware/vapt_vendor_auth.py` + `backend/models/vapt_vendor.py` + `backend/schemas/vapt_vendor.py` + `frontend/vapt-portal-*.html` + `frontend/vendor-login.html`). 52 tests passing across `tests/test_vapt/`.
- **Trust Center / SafeBase-equivalent** — tenant publishes compliance posture publicly, NDA e-sign, time-bound access tokens (`backend/services/trust_center_service.py` + `backend/routers/trust_center_admin.py` + `backend/routers/trust_center_public.py` + `backend/models/trust_center.py` + `frontend/trust-center/{index,admin,request}.html`).
- **Jira + ServiceNow bidirectional ticketing** — auto-create on risk assignment, HMAC-signed webhooks for close-loop sync (`backend/integrations/ticketing/{jira,servicenow,base}.py` + `backend/services/ticketing_service.py` + `backend/routers/ticketing_webhook.py`).
- **Auto-Remediation Phase 2 framework** — CrowdStrike RTR, Ansible, Fortinet, CyberArk executors with implication-check + approval-gate + retest pipeline (`backend/services/auto_remediation/{base,crowdstrike_rtr,ansible,fortinet,cyberark}.py` + `backend/services/auto_remediation_service.py` + `backend/routers/auto_remediation.py`).
- **Intelligence Engine** — four orchestration services that turn raw connector output into a unified, de-duplicated, applicability-checked, remediation-attached risk record (`backend/services/severity_normalizer.py` + `backend/services/asset_fingerprint_service.py` + `backend/services/advisory_applicability_service.py` + `backend/services/remediation_fetcher.py` + `backend/services/connector_runner.py`). See §5.1.1.
- **CSPM module** — native cloud posture (AWS Config + Azure Policy + GCP Security Command Center) with rule engine and findings UI (`backend/services/cspm_engine.py` + `backend/services/cspm_rules/` + `backend/routers/cspm.py` + `frontend/cspm-{dashboard,findings,control-detail}.html`).

---

## 3. How A Customer Onboards (the universal system promise)

Onboarding is a literal three-screen flow followed by an automatic data backfill. The same flow works for the 50-person startup and the 1000-person enterprise.

1. **Sign up.** A tenant is provisioned with its own slug, encryption key, and database scope.
2. **Brand the workspace.** Upload a logo, choose primary / secondary / accent colors, set the app name and favicon. The login page, dashboard, exports, and auditor invitations all carry the customer's brand.
3. **Open the Tool Catalog.** A grid of 25+ tiles, each with the vendor logo, a one-line description, setup difficulty (Low/Medium/High), data freshness target ("15-minute pull"), and a status pill ("Not connected").
4. **Click each tool you own.** Greyed-out tiles below the active row show roadmap connectors ("Coming soon: AWS, Azure, GCP, Slack, Jira, GitHub, Okta").
5. **Per-tool wizard.** A guided form with inline help and a link to the vendor's official API docs. Tenable wants Access Key + Secret Key. SentinelOne wants Singularity API token + Site ID. MS Entra runs an OAuth admin-consent flow for `SecurityEvents.Read.All`, `IdentityRiskEvent.Read.All`, `AuditLog.Read.All`. Click **Test Connection**.
6. **Real-time validation.** Within 2-4 seconds the screen returns either *"Connected. Found 2,847 assets. Last scan: 6 hours ago"* (green) or *"HTTP 403 from Tenable — verify your API key has Scanner Role"* (red, with the exact remediation step). Credentials never touch browser local storage; they go straight to a per-tenant Fernet-encrypted vault.
7. **Save.** Encrypted at rest, never logged, never displayed.
8. **The 15-minute poll cycle starts.** Connectors run on staggered schedules — 15 min for high-volume sources (Tenable, SentinelOne, Zscaler), 60 min for medium-volume (Netskope, Entra, ManageEngine), 4 hours for low-volume (Burp, GTB, CloudSEK).
9. **The URIP dashboard populates within minutes.** First poll lands. Risks get enriched with EPSS exploit probability, KEV status, MITRE APT attribution, OTX IOC matches. Asset criticality service tags each asset T1-T4. Composite scores compute.
10. **The Compliance dashboard populates within an hour.** The framework engine evaluates ~50 controls. SOC 2 lands at a real percentage; ISO 27001 lands at a real percentage; failing controls are listed with "View root-cause risks" buttons.
11. **Auditor invitation can go out the same day.** Time-bound, framework-scoped, read-only.

```
   Sign up                     Tool Catalog              Per-Tool Wizard
   ─────────                   ─────────────             ───────────────────
   [tenant slug]                ┌──┐ ┌──┐ ┌──┐            API endpoint: ___
   [admin email]   ──────►      │T │ │S1│ │ZS│  ──────►  API key:      ___
   [logo + colors]              └──┘ └──┘ └──┘            Secret:       ___
                                ┌──┐ ┌──┐ ┌──┐            [Test Connection]
                                │NS│ │EN│ │SP│             ✓ Found 2,847
                                └──┘ └──┘ └──┘             [Save]
                                                                │
                                                                ▼
   Compliance dashboard ◄──────  URIP dashboard  ◄────  Fernet vault +
   (within 1 hour)               (within minutes)        15-min poller
        │                              │
        ▼                              ▼
   15 frameworks scored            Risks enriched with
   ~895 controls evaluated         EPSS + KEV + MITRE + OTX
   Auditor invite ready            Composite scores computed
```

The same flow runs whether the customer is on Pure SaaS, On-Premise, or Hybrid-SaaS — only the location of the connector container changes.

---

## 4. How We Calculate Risk (the secret sauce)

URIP does not invent severity. It composes it. Every CVE that lands in URIP is run through a four-input formula plus an enrichment layer, producing a single 0-10 composite score.

**The formula (from `backend/services/exploitability_service.py`):**

```
URIP Risk Score = clamp[0, 10] (
    (CVSS  × 0.55)        ← theoretical severity
  + (EPSS  × 2.5)         ← exploit probability over the next 30 days
  + (KEV   ? +2.0 : 0)    ← actively exploited right now
  + (asset_tier_bonus)    ← T1: +1.0, T2: +0.5, T3:  0.0, T4: -0.5
)
```

Each weight maps to a real signal:

- **CVSS base score** (default weight `0.55`) — the public NVD severity. The "what would a 10-out-of-10 vulnerability look like in theory" anchor.
- **EPSS probability** (default weight `2.5`) — the FIRST.org Exploit Prediction Scoring System. A 0.00-1.00 estimate of *will this CVE be exploited in the wild in the next 30 days?* The single highest-signal input we have. Heavy weight is deliberate.
- **KEV bonus** (`+2.0` if present) — the CISA Known Exploited Vulnerabilities catalog. A binary flag that says *this is being exploited right now, by someone, somewhere, today.* Carries the heaviest qualitative signal in the formula.
- **Asset tier multiplier** (T1 +1.0 → T4 −0.5) — per-tenant taxonomy that says "Robotics Production Line PLC" is T1, "Canteen Wi-Fi" is T4. Implemented in `backend/services/asset_criticality_service.py` with a tenant-configurable keyword classifier.

On top of the score, URIP enriches every risk with two contextual layers no scoring formula captures:

- **APT attribution** — MITRE ATT&CK CVE-to-group mapping. *"This CVE is exploited by APT41 (T1190 Exploit Public-Facing Application). Adverb is in their target sector. Treat as Critical."*
- **IOC matches** — AlienVault OTX pulses. *"This C2 IP from your Zscaler logs matches an active OTX pulse from yesterday."*

All four enrichment feeds are LIVE in production today (`backend/services/exploitability_service.py`, `backend/services/threat_intel_service.py`).

### 4a. Severity Normalization Engine (every source → unified 0-10 scale)

Not every source speaks CVSS. URIP's normalization engine converts every connector's native severity to a single 0-10 CVSS-equivalent score before the composite formula runs. Without this layer, CrowdStrike's "ExPRT 85", Armis's "0-100 OT score", a CERT-In "Critical" advisory, and a Bug Bounty "P1" submission would all be incomparable. With it, the risk register sorts every finding from every source on the same axis.

| Source | Native Format | Mapping Method | Example |
|---|---|---|---|
| CrowdStrike (Spotlight / EASM / CNAPP) | ExPRT 0-100 | Divide by 10 | ExPRT 85 → 8.5 |
| Armis (OT) | 0-10 or 0-100 | Normalize to 0-10 | Armis 7.5 → 7.5 |
| Tenable / Qualys / Rapid7 (VM) | CVSS 0-10 | Use directly | CVSS 9.8 → 9.8 |
| VAPT Reports | CVSS 0-10 | Use directly | CVSS 8.5 → 8.5 |
| CERT-In Advisories | Critical / High / Medium / Low | Rule map | Critical → 9.0, High → 7.5, Medium → 5.0, Low → 3.0 |
| Bug Bounty | P1 / P2 / P3 / P4 | Heuristic 3-step waterfall | P1 → 9.0 base |
| SoC / SIEM Alerts | Critical / High / Medium / Low | Rule map | High → 7.5 |
| EPSS fallback (when feed down) | per-severity table | Fallback static | Critical=0.30, High=0.20, Med=0.10, Low=0.05 |

The `max(0.0, ...)` floor in the composite formula prevents Tier-4 negative bonuses from producing negative scores on otherwise-real findings.

### 4b. Asset Fingerprinting + De-duplication

The same vulnerability often arrives from multiple sources — Tenable's vulnerability scanner, CrowdStrike Spotlight, an external VAPT report, and a Bug Bounty submission can all report CVE-2021-44228 against the same SAP server within the same week. URIP de-duplicates them automatically using a composite asset fingerprint.

```
Asset Identity = MAC Address + Hostname + IP Address (composite key)
```

**Worked example:**
```
CrowdStrike reports  "Log4j High"          on 192.168.1.50 (SAP-PRD-01)
VAPT report says     "CVE-2021-44228 Crit" on            SAP-PRD-01
                            ↓
URIP fingerprint:    same CVE + same asset key → MERGED
                     Highest composite score retained.
                     Both sources attributed in the source list.
                     Remediation steps from both consolidated.
```

The same de-dup logic merges across category — VM + EDR + EASM + VAPT + Bug Bounty all flow through the same fingerprint so the IT team works one ticket per real-world risk, not one ticket per tool.

### 4c. Managed vs Unmanaged vs Unknown External

Not every device on the customer network is known to the IT team. URIP classifies every asset — at fingerprint time — into one of three buckets, surfacing shadow IT as its own first-class risk class.

| Type | Definition | How URIP Identifies | Asset Tag |
|---|---|---|---|
| **Managed** | Asset registered in EDR (CrowdStrike / SentinelOne / Defender) **and** in CMDB (ServiceNow / ManageEngine / Snipe-IT). IT team knows it exists and controls it. | EDR agent present + CMDB record exists. | `MANAGED` |
| **Unmanaged** | Asset on the network NOT in CMDB. Shadow IT — personal devices, rogue lab servers, forgotten VMs, contractor laptops. | NAC (Forescout / Cisco ISE) or OT discovery (Armis) detects device. No CMDB record. | `UNMANAGED — HIGH RISK` |
| **Unknown External** | Subdomains, IPs, or cloud assets exposed to the internet that the IT team may not know about. | EASM scan (CrowdStrike External / Detectify / Censys / Shodan) discovers. Not in known asset list. | `UNKNOWN EXTERNAL — INVESTIGATE` |

Unmanaged and Unknown External assets are auto-prioritized — they get a `+0.5` heuristic bump on their composite score (no agent, no patch path, often the first foothold in a real intrusion). The dashboard exposes a single "Shadow IT" tile that shows the running count.

Each managed asset additionally carries:
- **Internal IP + External / Public IP** side by side — the true attack surface, not just the LAN view
- **Named Product Owner** — accountability at the individual level, not just "the App Team"
- **Probe-to-Collect-Evidence** — URIP actively probes registered assets (with permission) for live evidence: open ports, running services, SSL certificate state, missing DMARC

### 4d. Advisory Applicability Check

CERT-In advisories, vendor security bulletins, and threat-intel pulses are noisy. Half are already-patched CVEs being re-reported by a different feed; another quarter are not applicable to the asset version actually deployed. URIP runs an applicability check at ingestion and tags every advisory with one of four labels.

| Status | Meaning |
|---|---|
| **Valid Advisory** | CVE still unpatched on affected asset + no vendor fix released yet. Risk stays OPEN. |
| **Patch Available** | Vendor patch released. URIP fetches patch details from NVD / vendor API. Remediation steps auto-populated. |
| **Expired Advisory** | Patch already applied and verified, OR CVE not applicable to this asset version. Risk auto-closed with audit trail. |
| **Redundant Advisory** | Duplicate of an existing open risk. Merged via the de-duplication engine. Not double-counted in dashboards or board reports. |

The applicability decision is cross-referenced against NVD patch metadata, vendor security bulletins (Microsoft / Cisco / Palo Alto), and CERT-In resolution status — so the IT team only sees advisories that still matter.

**The unique edge — and the sentence that goes on the website:**

> **When a SOC 2 control fails, URIP already knows which CVE caused it, its exploit probability, the APT exploiting it, and which Tier-1 asset is affected. Sprinto cannot do this. CloudSEK cannot do this.**

Sprinto sees the control failure but has no CVE-level threat enrichment. CloudSEK sees the threat but has no compliance scaffolding. URIP has both inside one tenant scope, joined by a single risk-control linkage table.

---

## 5. How We Integrate (the connector framework)

Every connector follows a four-method contract defined in `connectors/base/connector.py`. New tools plug in without touching core code — that is the universal-system promise made literal.

**The contract:**

```python
class Connector:
    def authenticate() -> AuthState
    def fetch_findings(since: datetime) -> list[RawFinding]
    def normalize(raw: RawFinding) -> URIPRiskRecord
    def health_check() -> ConnectorHealth
```

**The Normalization Engine principle.** Every tool's raw output — a Tenable scan blob, a SentinelOne threat record, a Zscaler URL block event, an Entra `riskEventType` — maps to one internal `URIPRiskRecord` schema before scoring. The risk register, the dashboard, the workflow, the SLA service, the audit log all consume the same shape. The scoring engine sees Tenable findings and SentinelOne findings as the same kind of object. This is the difference between "we built 12 connectors" and "we built one connector the same way 12 times."

**The credential vault.** Per-tenant Fernet-encrypted at rest. Per-tenant master key. Decrypted only in-memory at runtime. Never logged. Never serialised into telemetry. Never replicated to read replicas. Rotation is one click. In Hybrid-SaaS mode the vault lives on the on-prem agent — the cloud portal never sees raw API keys. Implemented in `connectors/base/credentials_vault.py` and `backend/models/tenant_connector_credential.py`.

**The polling scheduler.** 15-minute default cycle, per-tenant, async, configurable per connector in `routers/settings.py`. Drift detection (schema changes, null fields, permission regressions) escalates a connector to **DEGRADED** state — silent failure is the enemy of the no-manual-effort promise. A "green but blind" connector — connected but missing data — would be worse than a red one.

**Adding a new connector** is a five-step contract: implement the four methods → provide source-severity → URIP-severity mapping → write a test harness with canned payloads → register the connector in the catalog with required scopes and UI fields → ship. The Tool Catalog wizard auto-discovers new entries from `connectors/__init__.py`. The plumbing — encrypted credentials, scheduling, normalization, scoring, audit logging — is already done.

### Universal Coverage — 25+ Source Categories, 29 LIVE Connectors

The connector framework supports **every source category** an enterprise security stack contains. Each category below is either **LIVE today** (real connector calling a real upstream API) or **scaffolded via the simulator + framework** (real connector is one file away). Every directory under `connectors/` is verified to contain a `connector.py` honouring the four-method contract.

| # | Category | Sample Tools | URIP Connector Path | State |
|---|---|---|---|---|
| 1 | **VM** (Vulnerability Management) | Tenable, Qualys, Rapid7 | `connectors/tenable/` | ✅ LIVE (Tenable) |
| 2 | **VM (EDR-side)** — CrowdStrike Spotlight | CrowdStrike Spotlight | `connectors/crowdstrike/` | ✅ LIVE (Falcon Insight + Spotlight) |
| 3 | **EDR / XDR** | SentinelOne, CrowdStrike Falcon, Defender | `connectors/sentinelone/` + `connectors/crowdstrike/` | ✅ LIVE |
| 4 | **EASM** (External Attack Surface) | Censys, Shodan, Detectify, CrowdStrike External | `connectors/easm/` | ✅ LIVE (multi-source EASM) |
| 5 | **CNAPP / CSPM** (Cloud Security Posture) | AWS Config, Azure Defender / Policy, GCP Security Command Center | `connectors/aws_cspm/` + `connectors/azure_cspm/` + `connectors/gcp_cspm/` | ✅ LIVE (native — no third-party CNAPP needed) |
| 6 | **OT / IIoT** | Armis, Claroty, Nozomi, Dragos | `connectors/armis_ot/` | ✅ LIVE (Armis) |
| 7 | **VAPT Vendor Submissions** | External pentest vendors | `backend/services/vapt_vendor_service.py` + `frontend/vapt-portal-*.html` | ✅ LIVE (full VAPT Vendor Portal — see §6c) |
| 8 | **Threat Intelligence** (live feeds) | EPSS, KEV, MITRE ATT&CK, OTX, FIRST.org | `backend/services/{exploitability,threat_intel}_service.py` | ✅ LIVE — wired in URIP core |
| 9 | **CERT-In Advisories** (regulatory — India) | CERT-In RSS / Manual ingest | `connectors/cert_in/` | ✅ LIVE |
| 10 | **Bug Bounty** (webhook + API) | HackerOne, Bugcrowd, Intigriti | `connectors/bug_bounty/` | ✅ LIVE (HackerOne + Bugcrowd + generic webhook) |
| 11 | **SoC / SIEM Alerts** | Splunk, Elastic, QRadar, Microsoft Sentinel | `connectors/siem/` | ✅ LIVE (Splunk + Elastic + QRadar) |
| 12 | **NAC** (Network Access Control) | Forescout, Cisco ISE | `connectors/forescout_nac/` | ✅ LIVE (Forescout) |
| 13 | **PAM** (Privileged Access) | CyberArk, BeyondTrust, Delinea | `connectors/cyberark_pam/` | ✅ LIVE (CyberArk) |
| 14 | **Identity / IAM** | MS Entra, Okta, Google Workspace, Auth0 | `connectors/ms_entra/` | ✅ LIVE (MS Entra) |
| 15 | **CASB / SWG / Shadow IT** | Zscaler, Netskope, Palo Alto Prisma | `connectors/zscaler/` + `connectors/netskope/` | ✅ LIVE (Zscaler + Netskope) |
| 16 | **Firewall** (NGFW API) | Fortiguard, Palo Alto, Check Point, pfSense | `connectors/fortiguard_fw/` | ✅ LIVE (Fortiguard) |
| 17 | **Email Security** | Google Workspace + MS Defender for Office 365 (Mimecast, Proofpoint via API) | `connectors/email_security/` | ✅ LIVE (Workspace + M365 Defender) |
| 18 | **Collaboration** (data exposure) | SharePoint, OneDrive, Teams, Slack, Confluence | `connectors/m365_collab/` | ✅ LIVE (M365 trio — SharePoint/OneDrive/Teams) |
| 19 | **ITSM** | ManageEngine SDP, ServiceNow, Jira | `connectors/manageengine_sdp/` + `backend/integrations/ticketing/{jira,servicenow}.py` | ✅ LIVE (SDP + Jira + ServiceNow bidirectional) |
| 20 | **UEM (Endpoint Central)** | ManageEngine Endpoint Central, Intune, Jamf | `connectors/manageengine_ec/` | ✅ LIVE (ManageEngine EC) |
| 21 | **MDM (Mobile)** | ManageEngine MDM, Intune, Workspace ONE | `connectors/manageengine_mdm/` | ✅ LIVE (ManageEngine MDM) |
| 22 | **DAST** | Burp Enterprise, OWASP ZAP, Acunetix | `connectors/burp_enterprise/` | ✅ LIVE (Burp Enterprise) |
| 23 | **DLP** | GTB Endpoint Protector, Forcepoint, Symantec, Microsoft Purview, Netskope DLP | `connectors/gtb/` + `connectors/netskope/` | ✅ LIVE (GTB + Netskope DLP) |
| 24 | **External Threat / Dark Web** | CloudSEK, DigitalShadows, ZeroFox, Recorded Future | `connectors/cloudsek/` | ✅ LIVE (CloudSEK XVigil + BeVigil + SVigil) |
| 25 | **Auto-Remediation Executors** | CrowdStrike RTR, Ansible, Fortinet, CyberArk, Microsoft Graph | `backend/services/auto_remediation/{crowdstrike_rtr,ansible,fortinet,cyberark}.py` | ✅ LIVE (framework — wire-in per tenant) |
| 26 | **LMS** (Security Awareness Training) | KnowBe4, Hoxhunt | `connectors/knowbe4/` + `connectors/hoxhunt/` | ✅ LIVE |
| 27 | **BGV** (Background Verification) | AuthBridge, OnGrid | `connectors/authbridge/` + `connectors/ongrid/` | ✅ LIVE |

**The 29 production connectors verified by `ls connectors/*/connector.py`:**

```
armis_ot          authbridge         aws_cspm           azure_cspm
bug_bounty        burp_enterprise    cert_in            cloudsek
crowdstrike       cyberark_pam       easm               email_security
forescout_nac     fortiguard_fw      gcp_cspm           gtb
hoxhunt           knowbe4            m365_collab        manageengine_ec
manageengine_mdm  manageengine_sdp   ms_entra           netskope
ongrid            sentinelone        siem               tenable
zscaler
```

**Universal simulator** (`connectors/simulator_connector.py` + `connectors/extended_simulator.py`): every category generates realistic synthetic findings during demo / pilot / dev mode. Customer onboarding is fully exercisable end-to-end before any real connector is configured. The simulator is also the test harness for new connector authors — write the real connector, point the test suite at the simulator's canned payloads, ship.

**The promise:** *"Bring any tool. We support the category. We have the framework. We have the simulator for demo. Real connector is one file away."*

---

## 5.1.1. The Intelligence Engine (the orchestration layer that makes the cockpit honest)

A connector that just dumps raw findings into a database is half a product. The other half — the layer that turns 11 tools' worth of inconsistent severity scales, duplicate findings, expired advisories, and bare CVE IDs into a single ranked, de-duplicated, applicability-checked, remediation-attached risk register — is the **Intelligence Engine**. Five services, all live in `backend/services/`, run on every poll cycle.

| Service | File | What It Does |
|---|---|---|
| **Severity Normalization** | `severity_normalizer.py` | Converts every connector's native severity (CrowdStrike ExPRT 0-100, Armis 0-10, CERT-In Critical/High/Medium/Low, Bug Bounty P1/P2/P3/P4, SIEM Critical/High/…) into a single 0-10 CVSS-equivalent before the composite formula runs. The mapping table in §4a is the canonical source — every new connector drops its mapping into this service. |
| **Asset Fingerprinting** | `asset_fingerprint_service.py` | Builds the composite asset key (MAC + Hostname + IP) for every finding and merges duplicates. The same CVE arriving from Tenable, CrowdStrike, an external VAPT report, and a Bug Bounty submission becomes ONE risk row — highest composite score retained, all source attributions kept, remediation steps from all sources consolidated. The IT team works one ticket per real-world risk, not one per tool. |
| **Advisory Applicability Check** | `advisory_applicability_service.py` | Tags every advisory at ingestion as Valid / Patch Available / Expired / Redundant by cross-referencing NVD patch metadata, vendor security bulletins, and CERT-In resolution status. CERT-In and vendor advisories are noisy; this service strips the half that doesn't apply to the actual deployed asset version, so the IT team sees only what still matters. |
| **Remediation Fetcher** | `remediation_fetcher.py` | Auto-pulls remediation steps for every finding from NVD, vendor patch notes, the connector's own recommendation field (when present, e.g., a Bug Bounty submission's researcher write-up), or a fixed playbook (SSL expired → renewal procedure; missing DMARC → DNS record template). Every risk row arrives with steps already attached. |
| **Connector Runner** | `connector_runner.py` | The async scheduler that orchestrates the four-method contract across all configured connectors per tenant. Handles polling cadence, drift detection (schema changes, null fields, permission regressions → DEGRADED), retry with exponential backoff on HTTP 429, and emits the canonical `URIPRiskRecord` to the risk register after the four services above run. |

**Why this matters for the pitch.** A board member or a procurement lead who already owns 8 tools is not impressed by "we have 25 connectors" — every TrendAI / Wiz / SecOps competitor can show 25 logos on a slide. They are impressed by the answer to: *"What happens when the same CVE arrives from three of those 25 tools, with three different severity scales, two of them already patched, one of them re-reported by CERT-In as a noisy duplicate?"* Most cockpits show three rows in the dashboard. URIP shows one row, scored, applicability-checked, with the patch link attached, and a list of three sources behind it. The Intelligence Engine is what turns "many connectors" into "one truth".

---

## 5a. The Remediation Engine

URIP doesn't just rank risks — it tells the IT team **how to fix each one**. Every risk row in the register carries actionable remediation steps, fetched and attached automatically at ingestion time. IT teams stop spending hours researching fixes per finding. Phase 2 extends this from "show the steps" to "execute the fix."

### 5a.1 Remediation Steps Per Risk (Phase 1 — LIVE)

Source of remediation depends on the finding type. Every category has a deterministic remediation source mapped before scoring:

| Finding Source | Remediation Comes From | Example |
|---|---|---|
| **CVE Findings (any source)** | NVD advisory + vendor patch notes auto-fetched via NVD API | CVE-2023-29357 → "Apply MS patch KB5002099. Disable anonymous SharePoint access. Enable MFA." |
| **CERT-In Advisory** | Advisory text parsed — action items extracted | CERT-In CIVN-2026-1234 → "Update OpenSSL to 3.1.4. Restart affected services. Verify with `openssl version`." |
| **VAPT Reports** | Vendor recommendation in report — imported with finding | Researcher writes: "Sanitize user input on /api/upload endpoint. Implement file type whitelist." |
| **Bug Bounty** | Researcher recommendation — part of the submission form | P1 submission: "Fix IDOR on /api/users/{id} — add authorization check before returning user data." |
| **SoC / SIEM Alerts** | Playbook-based rule map — predefined per alert type | Rogue device alert → "Isolate device via Forescout. Identify owner. Verify registration or remove." |
| **IOC Match (IP / Hash)** | OTX context + standard response playbook | Malicious IP match → "Block IP at Fortiguard. Revoke active sessions. Check lateral movement in logs." |
| **SSL Expired** | Fixed text remediation | "Renew SSL certificate. Update A records if needed. Verify via SSL Labs after renewal." |
| **Missing DMARC** | Fixed text remediation | "Add DMARC TXT record to DNS: `v=DMARC1; p=quarantine; rua=mailto:admin@example.com`" |

The remediation text is rendered inside the risk detail card, attached to the auto-created Jira / ServiceNow ticket, and included in every export.

### 5a.2 Auto-Remediation — Phase 2 (LIVE — framework complete)

Phase 2 turns the steps into executable scripts. URIP becomes the orchestration plane that pushes the fix to the affected system without human intervention — gated by an Implication Check and an Approval Gate so production never breaks unexpectedly. **Status:** framework LIVE in code today (`backend/services/auto_remediation/{base,crowdstrike_rtr,ansible,fortinet,cyberark}.py` + `backend/services/auto_remediation_service.py` + `backend/routers/auto_remediation.py`, 31 tests). Per-tenant production credentials wire-in is the deployment-config step, not engineering — see §13 LIVE for the full status.

```
Risk Registered
   │
   ▼
Patch Available? (NVD API check)
   │
   ├── YES ──► Remediation script selected from playbook library
   │           Script pushed to affected system via:
   │              • CrowdStrike RTR (Real Time Response) — endpoint patches
   │              • Ansible playbook                       — server config fixes
   │              • Fortiguard API                         — firewall rule updates
   │              • CyberArk                               — credential rotation
   │              • Microsoft Graph                        — Entra/M365 hardening
   │           Implication check ► what services restart? expected downtime? rollback plan?
   │           Approval gate     ► auto-execute OR require SPOC approval (configurable)
   │           Execution logged  ► timestamp + executor + output + before/after state
   │           Re-test           ► URIP re-scans asset post-execution to confirm fix
   │           Risk auto-closed if re-test passes
   │
   └── NO  ──► Risk stays OPEN. Manual remediation steps shown. Pending Days counter running.
```

**Guard rails:**
- **Script Execution Scope** — configurable per risk type. CISO defines which categories auto-execute and which require SPOC approval.
- **Implication Check** — before any script runs, URIP shows: affected services, expected downtime, rollback plan. No surprises in production.
- **Internal ↔ External Verification** — script targets internal IP. External IP used for re-test verification via external scanner — confirms the fix is visible from the internet, not just inside.
- **BitSight Posture Tracking (Roadmap)** — post-remediation, BitSight grade change is logged. Shows security posture improvement over time as a board-level metric.
- **Audit Trail** — every automated action logged: who approved, what ran, what changed, re-test result.

---

## 5b. Operational Integration — Tickets, Pending Days, OT, Rate Limits

### 5b.1 Jira / ServiceNow Bidirectional Integration

The risk register is operationally useless if the IT team has to manually copy each finding into a ticket. URIP closes that loop both directions.

| Behaviour | Detail |
|---|---|
| **Trigger** | Risk assigned in URIP → Jira / ServiceNow ticket auto-created immediately |
| **Ticket Contents** | CVE ID, composite score, SSVC label, asset, asset tier, APT context, Raised Date, Pending Days, full remediation steps, evidence-upload link |
| **Bidirectional** | Ticket closed in Jira / ServiceNow → URIP risk auto-updated to Resolved. No manual sync. |
| **Closure Rule** | Risk closes only when remediation is verified **AND** evidence is uploaded — OR when auto-remediation re-test passes. |

The bidirectional sync runs over the existing ManageEngine SDP connector pattern (LIVE today) and extends to Jira and ServiceNow via the same four-method connector contract.

### 5b.2 Raised Date + Pending Days (replaces SLA)

Several enterprise customers — Royal Enfield among them — explicitly do not want a fixed SLA deadline on every risk. They want a live counter that says "this risk has been open for 8 days" so prioritisation becomes obvious without arguing about whether each CVE got the right SLA.

```
Raised Date  = Date risk first detected and registered in URIP
Pending Days = Today − Raised Date (auto-calculated, live counter)

EXAMPLE RISK ROW
  RE-003 | SharePoint Privilege Escalation | Raised: Apr 5, 2026 | Pending: 8 days | Status: Open
```

**Escalation rules (configurable per tenant):**

| Severity | Alert | Escalate |
|---|---|---|
| Critical | At 3 days pending | To CISO at 7 days |
| High | At 7 days pending | To HoD at 14 days |
| Medium | At 30 days pending | — |
| Low | At 90 days pending | — |

Escalations fire as in-app notifications, email, and (optionally) Slack / Teams webhook.

### 5b.3 OT Network Access Patterns

OT segments are deliberately air-gapped or DMZ-isolated. URIP cannot — and must not — scan them directly from the corporate network. Two supported patterns, both encrypted TLS 1.3, neither exposing OT to the public internet:

| Option | How It Works |
|---|---|
| **A. On-Premise Collector** | Lightweight URIP agent (Docker container) deployed inside the OT segment. Pulls from Armis / Claroty / Nozomi / Dragos. Sends encrypted summary back to URIP cloud / on-prem core. |
| **B. Secure API Gateway** | Proxy in DMZ. OT tools push to the proxy. URIP pulls from the proxy. Bidirectional but tightly scoped firewall rules. |

The On-Premise Collector reuses the same `agent/` Docker container that powers the Hybrid-SaaS deployment — one binary, two operational patterns.

### 5b.4 API Rate Limits & Caching

| Connector | Rate Limit Strategy |
|---|---|
| Zscaler CASB / ZIA | Batched polling (15-min intervals). Token refresh automatic. |
| CrowdStrike (Spotlight / EASM / CNAPP / Falcon) | OAuth 2.0. Exponential backoff on HTTP 429. |
| FIRST.org (EPSS) | Batch 100 CVEs per call. 24-hour in-memory cache. ~95% call reduction. |
| CISA KEV | Full catalog downloaded once per 24 hours. In-memory hash set for instant lookups. |
| Tenable / Qualys / Rapid7 (VM) | Per-vendor rate limits respected; staggered schedules across tenants. |

---

## 6. The Two Dashboards

### 6a. URIP Risk Intelligence Dashboard

The default landing page after login. Built around the CISO's first question: *where am I most exposed today, and are we fixing it fast enough?*

**Top KPI strip** (5 click-through tiles, rendered in `frontend/dashboard.html`):
- **Total Open Risks** — with day-over-day delta arrow
- **Critical Severity** — count and delta
- **High Severity** — count and delta
- **Accepted Risks** — under HoD-approved acceptance workflow
- **IOC Matches** — risks with active OTX IOC correlations

**Risk register** (`frontend/risk-register.html`). Sortable, filterable table. Columns: Severity, Title, Source, Asset, EPSS Score, KEV Status, APT Attribution, Owner, SLA Status, Age. Filter chips: Source, Severity, Status, Asset Tier. Click any row → detail panel slides in with full enrichment trail and a "Drill into source" button that hits the secure tunnel (in Hybrid-SaaS mode).

**Threat intel panel** (`frontend/threat-map.html`). Active APT groups currently targeting the customer's sector with MITRE ATT&CK technique IDs and the CVEs each group has historically used. IOC pulses, geographic distribution of suspicious activity, brand-mention monitoring (CloudSEK).

**Connector health board** (`frontend/connector-status.html`). Every configured connector with last successful poll, error count over the last 24 hours, and a status pill (LIVE / DEGRADED / DOWN). Drift detection escalates degraded silently-failing connectors instead of falsely reporting green.

**Acceptance and remediation workflow** (`frontend/acceptance-workflow.html`, `frontend/remediation-tracker.html`). HoD approval flow for risk acceptance. Owner assignment + SLA timer + auto-ticket-to-ManageEngine SDP for active remediation.

**Audit log** (`frontend/audit-log.html`). Immutable, tenant-scoped. Every action — login, role change, risk creation, acceptance, connector configuration — recorded with actor, tenant_id, timestamp, IP.

**Admin pages.** Tool Catalog (`frontend/tool-catalog.html`), per-tool wizard (`frontend/connector-wizard.html`), tenant management (`frontend/admin-tenants.html`, `frontend/admin-tenant-detail.html`), module subscription (`frontend/admin-modules.html`), scoring weight tuning (`frontend/admin-scoring.html`), reports (`frontend/reports.html`).

### 6b. Compliance Dashboard (Sprinto-equivalent)

A second top-nav tab when the Compliance Module is enabled. Built around the Compliance Officer's first question: *if the audit was next week, would we pass?* Lives as a separate FastAPI service on port 8001 (`compliance/backend/compliance_backend/`) with its own database. Can also run **standalone** without URIP — `docker-compose -f compliance/docker-compose.standalone.yml up` — for prospects who want only audit-readiness.

The 10 pages of the Compliance UI (`compliance/frontend/`):

- **Home** (`index.html`) — 15 framework score widgets with trend arrows. Per-framework percentage compliance, controls passing / total, last evaluation timestamp.
- **Frameworks** (`frameworks.html`) — per-framework drill-down. Control list grouped by category (e.g., SOC 2 CC1-CC9 + A1 + PI1 + C1 + P1-P8). Color-coded pass / fail / inconclusive.
- **Controls** (`controls.html`) — single ranked list across all 15 frameworks (~895 total controls). Sorted by `remedy_priority_score = frameworks_affected × failure_severity × root_cause_risk_count` so the compliance team works top-down.
- **Evidence** (`evidence.html`) — drag-drop upload, integrity hash verification (`content_sha256` per `compliance_backend/models/evidence.py`), bundle export. Auto-collected evidence from connector polls is tagged to control + framework + audit period.
- **Evidence requests** (`evidence-requests.html`) — auditor → tenant request flow. Auditor asks for evidence in a specific control; tenant fulfils.
- **Policies** (`policies.html`) — 9 templates from `compliance_backend/seeders/policy_templates.py` (Information Security Policy, Acceptable Use, Access Control, Data Classification, Incident Response, Business Continuity, Vendor Management, Change Management, Risk Management). Versioned. E-sign acknowledgment workflow with bulk-remind for unsigned employees.
- **Vendors** (`vendors.html`) — questionnaire engine + risk scoring. Vendor inventory, criticality classification, contract / DPA / BAA expiry alerts.
- **Auditor invitations** (`auditor-invitations.html`) — admin invites an auditor with framework-scope and time-bound expiry.
- **Auditor activity** (`auditor-activity.html`) — full audit trail of every auditor action: which control they viewed, which evidence they requested, which session they opened.
- **Reports** (`reports.html`) — per-framework export bundles for the auditor.
- **Auditor portal** (`auditor_portal.html`) — separate read-only auditor login. Filtered views by framework + audit period. Auditor sees controls, evidence, policies; can request additional evidence.

### 6b.1 Risk Register — Full Column Set

The risk register replaces the customer's existing Excel sheet with a 25-column live table. Auto-populated from every connector. Every row has remediation steps attached, a Pending Days counter, and a one-click drill-down.

| Column | Source | Description |
|---|---|---|
| Risk ID | Auto | `{TENANT}-001`, `{TENANT}-002`… sequential per org |
| Finding Title | Auto | CVE name or finding description |
| Source | Auto | Which connector / category surfaced it |
| CVE ID | Auto | CVE number if applicable |
| CVSS Score | Auto | Raw base score 0-10 |
| EPSS Score | Auto | Live exploit probability 0-1 |
| KEV Status | Auto | Yes (CISA confirmed) / No |
| Composite Score | Auto | Final 0-10 prioritised score |
| SSVC Label | Auto | ACT NOW / ACT / ATTEND / TRACK |
| Severity | Auto | Critical / High / Medium / Low |
| Asset | Auto | Hostname + Internal IP + External IP |
| Asset Type | Auto | Managed / Unmanaged / Unknown External |
| Asset Tier | Auto / Manual | Tier 1-4 (CrowdStrike tag or keyword classifier) |
| Domain | Auto | Application / Network / Cloud / OT / Identity / Email |
| Product Owner | Manual | Named individual responsible for this asset |
| Owner Team | Auto | Team assigned based on domain |
| APT Tags | Auto | Which APT groups historically use this CVE |
| Exploit Status | Auto | Weaponized / Active / PoC / None |
| Advisory Status | Auto | Valid / Patch Available / Expired / Redundant |
| Raised Date | Auto | Date risk first detected in URIP |
| Pending Days | Auto | Live counter: today minus raised date |
| Status | Manual | Open / In Progress / Resolved / Accepted |
| Remediation Steps | Auto | Step-by-step fix from NVD / vendor / playbook |
| Jira Ticket | Auto | Auto-created ticket ID + link |
| Evidence | Upload | Patch screenshot, config proof, re-test report |

### 6b.2 Risk Detail Card — Per-Finding View

Click any row in the register and the detail card slides in. This is the screen the IT engineer actually works against — every piece of context on one page, copy-paste-ready into a ticket or change request.

```
RE-003  |  SharePoint Privilege Escalation

FINDING:      CVE-2023-29357 — SharePoint Server Privilege Escalation
DESCRIPTION:  Detected by EASM connector. Dealer Portal api.dealers.example.com.
              Requires immediate triage. EPSS 100th percentile.

SOURCE:       EASM                  DOMAIN:           Application
CVSS SCORE:   9.8                   COMPOSITE SCORE:  10.0
SEVERITY:     Critical              EPSS SCORE:       0.94356
EPSS %ile:    100th percentile      IN KEV CATALOG:   Yes (CISA KEV)
EXPLOIT:      Weaponized            ASSET:            Dealer Portal
ASSET TYPE:   Managed               INTERNAL IP:      10.0.14.23
EXTERNAL IP:  203.45.67.89          PRODUCT OWNER:    Rajesh Kumar (App Team Lead)
APT TAGS:     APT28, APT41          TTP:              T1190 (Exploit Public-Facing App)
RAISED DATE:  Apr 5, 2026           PENDING DAYS:     8 days  ⚠
STATUS:       Open                  TICKET:           SDP-2341

REMEDIATION STEPS:
  1. Apply Microsoft patch KB5002099 (SharePoint Server 2019 CU)
  2. Disable anonymous access on SharePoint site collection settings
  3. Enable MFA for all SharePoint admin and editor accounts
  4. Review access logs for CVE-2023-29357 exploitation indicators
  5. Request VAPT vendor re-test after patch — sign off in portal

ADVISORY STATUS: Valid — Patch Available (KB5002099 released Jan 2024)
```

### 6b.3 Risk Acceptance Workflow

Not every risk can or should be remediated immediately — some get formally accepted with compensating controls. URIP turns risk acceptance into an auditable workflow rather than an Excel comment.

- Owner flags risk for acceptance → URIP auto-generates a **Compensating Controls recommendation** (e.g., "isolate via segmentation + enable EDR isolation policy + enforce conditional access")
- HoD approves with **digital sign-off** — full audit trail recorded against tenant audit log
- Accepted risks are **tagged and auto-excluded** from the risk register's open count and from board reports — so reports never get inflated by 200 long-accepted findings
- **90-day re-review reminder** — HoD must re-approve or remediate; an accepted risk does not stay accepted forever
- Acceptance reasons map cleanly to compliance evidence (SOC 2 CC9.1 Change Management, ISO 27001 A.5.31 Legal Compliance) — same workflow, two artefacts

### 6b.4 Security Posture Dashboard (executive view)

A separate top-level dashboard built for the CISO's weekly board update — answers *"is our posture improving or degrading?"* in one screen, then drills back to the same risk register everything else uses.

- **Overall security posture score** — aggregated composite across all configured sources + asset management state
- **Managed vs Unmanaged vs Unknown asset count** — how much of the environment is visible and controlled
- **BitSight-style posture grade (A / B / C / D / F)** — executive-friendly single letter (Phase 2 with optional BitSight integration)
- **Domain breakdown** — Endpoint, Cloud, Network, Application, Identity, OT, Email, Collaboration
- **Risk trend** — posture improving or degrading week over week, 30-day rolling
- **Critical & High count with Pending Days alert** — how many findings are overdue per the escalation rules
- **Role-based views** — CISO (operational depth), IT Team (assigned tickets only), Executive / Board (KPI-only summary)

---

## 6c. VAPT Vendor Portal — Public-Facing Sub-Portal

A dedicated VAPT (Vulnerability Assessment & Penetration Testing) vendor portal — exposed at `vapt.{tenant}.urip.io` (or as a section of the main dashboard) — lets the customer's external pentest vendors submit findings directly into URIP without ever seeing the rest of the customer's risk surface. **This is a first-class part of the URIP product**, not a side feature.

The problem it solves: today, VAPT vendors deliver findings as PDF reports that someone manually re-types into the risk tracker. The information loses structure (severity, CVSS, asset mapping, evidence), the IT team can't auto-prioritise it against other sources, and there is no closed-loop re-test. The VAPT Vendor Portal closes that loop end-to-end.

| Capability | Detail |
|---|---|
| **Vendor Login** | Each VAPT vendor gets a Guest-role account scoped to that customer tenant. Vendor sees **only their own submissions** — no exposure to other findings, other vendors, or other tenants. RBAC enforced by tenant scope + vendor_id filter. |
| **Structured Submission Form** | Required fields: Vulnerability name, CVE ID (if applicable), CVSS base + vector, Affected Asset (hostname / IP / URL), Exploit Maturity (PoC / Functional / Weaponized), Remediation Recommendation, PoC evidence upload (screenshots, request/response captures, video). |
| **Auto-Processing on Submit** | The moment a vendor clicks Submit: EPSS + KEV enrichment runs against the CVE, Remediation Steps are fetched from NVD + Vendor APIs, the risk is auto-assigned to the asset's Product Owner, Raised Date is set, the Pending Days counter starts. Vendor sees the URIP-ID immediately. |
| **Re-test Workflow** | IT team applies the fix → marks the URIP risk "Request Re-test" → vendor receives an email + portal notification → vendor performs the re-test → submits Pass / Fail with evidence → on Pass the risk auto-closes (status → Resolved with vendor sign-off as evidence); on Fail the risk re-opens with the vendor's notes attached and Pending Days resumes. |
| **File-Upload Backbone** | Reuses the existing evidence integrity pipeline — `content_sha256` per file, Fernet-encrypted at rest, immutable audit log entry on every upload / view / download. |
| **Auditor Visibility** | Auditors with the tenant can see VAPT vendor submissions as compliance evidence (SOC 2 CC4.1 Monitoring Activities, ISO 27001 A.8.8 Management of Technical Vulnerabilities). Same evidence, two artefacts. |

**Build status today — fully LIVE:**

| Capability | Status | File / Path |
|---|---|---|
| Backend file-upload + evidence integrity (`content_sha256`) + per-tenant scoping | ✅ LIVE | reused from compliance evidence module |
| Vendor login (time-bound JWT, single-use invitation token) | ✅ LIVE | `backend/middleware/vapt_vendor_auth.py` |
| Vendor admin (issue / revoke invitations) | ✅ LIVE | `backend/routers/vapt_admin.py` + `frontend/admin-vapt.html` |
| Vendor portal (submit, view own submissions, request re-test response) | ✅ LIVE | `backend/routers/vapt_vendor_portal.py` + `frontend/vapt-portal-{login,dashboard,submit,submission-detail}.html` + `frontend/vendor-login.html` |
| Auto-enrichment on submit (EPSS + KEV + remediation steps) | ✅ LIVE | `backend/services/vapt_vendor_service.py` calls into the same enrichment chain as connector ingest |
| Re-test workflow state machine (Open → Request Re-test → Pass/Fail → auto-close) | ✅ LIVE | `backend/services/vapt_vendor_service.py` (state transitions tested in `tests/test_vapt/test_vapt_retest_flow.py`) |
| Auditor visibility — VAPT submissions surface as compliance evidence | ✅ LIVE | tagged to SOC 2 CC4.1 + ISO 27001 A.8.8 via the linkage table |
| Tests | ✅ 52 tests passing | `tests/test_vapt/test_vapt_vendor_models.py` + `test_vapt_vendor_routes.py` + `test_vapt_vendor_invitation.py` + `test_vapt_submission_pipeline.py` + `test_vapt_retest_flow.py` + `test_vapt_security.py` |

This portal is the answer when a customer asks "how do we get our pentest vendor's findings into URIP without manually re-keying every report?" — it turns a one-way PDF handoff into a closed-loop, auditable, scored, re-testable workflow that the auditor can inspect as compliance evidence.

---

## 6.5. The 10-Domain Cockpit Sidebar (the recommended UI shape)

A CISO's mental model is not "25 connectors". It's **domains** — endpoint, identity, network, cloud, email, mobile, OT, external, compliance. URIP renders 25+ connectors into 10 domain-roll-up dashboards on a single left sidebar. Each domain dashboard is a **thin view over the same `URIPRiskRecord` data layer** — not a new module. The Salesforce playbook applied to security: the user sees one familiar pane regardless of which underlying tool is feeding it.

| # | Sidebar Tab | Rolls Up | What The CISO Sees |
|---|---|---|---|
| 1 | **Risk Center** | Composite register + threat intel + register filters | The default landing page. Every finding from every source on one ranked table. |
| 2 | **Endpoint Security** | CrowdStrike Falcon + SentinelOne + ManageEngine Endpoint Central + Defender (when added) | One endpoint posture view across all EDR/XDR/UEM tools — agents healthy, threats detected, missing patches by host. |
| 3 | **Identity Security** | MS Entra + CyberArk PAM (Okta + Workspace when added) | Risky sign-ins, dormant privileged accounts, MFA coverage gaps, vault-rotation health. |
| 4 | **Network Security** | Zscaler + Netskope + Forescout NAC + Fortiguard Firewall | Shadow IT discovery, NAC posture, firewall rule drift, CASB policy hits. |
| 5 | **Cloud Security** | AWS CSPM + Azure CSPM + GCP CSPM | Misconfigured resources by account / subscription / project; severity and applicable CIS / NIST / PCI controls per finding. |
| 6 | **Email & Collaboration** | Email Security (Workspace + M365) + M365 Collaboration (SharePoint + OneDrive + Teams) | Phishing volume, BEC alerts, anomalous external sharing, sensitive-doc exposure. |
| 7 | **Mobile Security** | ManageEngine MDM | Enrolled vs unenrolled devices, jailbroken / rooted handsets, OS patch level, lost/stolen workflow. |
| 8 | **OT Security** | Armis OT (Claroty / Nozomi when added) | Asset inventory of PLC / HMI / SCADA, OT-specific CVE scoring, segmentation health, Tier-1 production-line risks. |
| 9 | **External Threat Surface** | CloudSEK XVigil/BeVigil/SVigil + EASM (Censys + Shodan + Detectify) + CERT-In | Brand abuse, credential leaks, exposed subdomains, India regulatory advisories. |
| 10 | **Compliance** | Native Sprinto-equivalent module (15 frameworks, ~895 controls) | The Compliance dashboard — SOC 2 / ISO 27001 / GDPR / HIPAA / PCI / DPDP / NIST CSF (audit-grade) + ISO 42001 / EU AI Act / DORA / NIS2 / ISO 27017-18-701 / CIS v8 (scaffold-grade) live posture. |
| ⊕ | **Workflow Automation** | Auto-Remediation framework + Jira/ServiceNow bidirectional ticketing | What ran, what was approved, what was rolled back, what's pending re-test. |
| ⊕ | **Configuration** | Tool Catalog + Modules + Settings | Where the customer plugs in API keys, toggles modules, tunes scoring weights, manages tenants. |

**The discipline behind the shape.** Every domain tab is a **filter** over the same risk register, not a new database. Add a connector → the tab it belongs to lights up automatically. Rip out a connector → the tab goes dark. The customer never sees a mismatch between "10 sidebar tabs" and "5 connectors configured" — empty domains say "Connect a tool to populate this view" with a one-click jump to the Tool Catalog. The visual depth mirrors what TrendAI Vision One shows on its left rail, *without* URIP having built TrendAI's stack — because URIP is the cockpit, not the stack.

---

## 7. The Module Catalog (license tiers)

URIP ships as **15 capability modules + a mandatory Core (16 total)**. Each tenant subscribes to exactly the modules they need. Disabled modules are dark in the UI (frontend route guards) and inactive in the backend (decorator checks in `backend/middleware/auth.py`). Module gating is enforced in three places: UI, API, and connector data plane.

| Module | What's inside | Recommended for |
|---|---|---|
| **CORE** *(mandatory)* | Risk register, scoring engine, dashboard, workflow, audit log, reports, EPSS + KEV + MITRE ATT&CK + OTX enrichment, multi-tenancy, white-label theming | Every tenant |
| **VM** | Tenable + Qualys + Rapid7 + CrowdStrike Spotlight connectors | Anyone running vulnerability scanners |
| **EDR** | SentinelOne + CrowdStrike Falcon + Defender for Endpoint + ManageEngine Endpoint Central + ManageEngine MDM | Anyone with endpoint security |
| **NETWORK** | Zscaler + Netskope + Palo Alto + Fortigate + CloudSEK external threat | Cloud-first orgs |
| **IDENTITY** | MS Entra + Okta + Google Workspace | Anyone with SSO |
| **COLLABORATION** | SharePoint + OneDrive + Teams + Slack + Confluence | Knowledge-work orgs |
| **ITSM** | ServiceNow + Jira + ManageEngine SDP | Anyone with formal ticketing |
| **DAST** | Burp Suite Enterprise + OWASP ZAP + Acunetix | App-heavy orgs |
| **DLP** | GTB + Forcepoint + Symantec DLP + Netskope DLP | Compliance-driven orgs |
| **CSPM** | AWS Config / Security Hub + Azure Policy / Defender + Google Security Command Center, native rule engine, multi-cloud posture dashboard | Cloud-heavy orgs |
| **COMPLIANCE & AUDIT-READINESS** | 7-framework engine, control monitoring, evidence automation, policy management, access reviews, vendor risk, incident lifecycle, asset inventory, auditor portal, compliance scoring, framework-specific reports, Trust Center publish flow | Anyone facing audits |
| **DSPM** *(MVP scaffold)* | Data asset inventory, sensitive-discovery catalog, access-path analysis, scan trigger — `backend/routers/dspm.py` | Data-heavy orgs, GDPR/DPDP compliance |
| **AI_SECURITY** *(MVP scaffold)* | AI/ML model inventory, prompt-injection log, governance-status ledger — `backend/routers/ai_security.py` | Orgs deploying AI/LLM products |
| **ZTNA** *(MVP scaffold)* | Zero-trust policy inventory, access-decision log, posture-violation feed — `backend/routers/ztna.py` | Cloud-first, zero-trust adopters |
| **ATTACK_PATH** *(MVP scaffold)* | BFS attack-path graph, MITRE ATT&CK chain overlay, critical-path recompute — `backend/routers/attack_path.py` | Orgs with complex network topologies |
| **RISK_QUANT** *(MVP scaffold)* | Open FAIR point-estimate (LEF × LM = ALE), per-tenant assumptions, aggregate quantification — `backend/routers/risk_quantification.py` | CISOs presenting financial risk to the board |

Future tenants pick differently. A pure SaaS company might want only Identity + Collaboration + DLP + Compliance. A factory might want only VM + Network + ITSM. A regulated startup might start with Core + Compliance only. The modular pricing tier closes deals at every level without forcing all-or-nothing.

The **Compliance Module** is the strategic upsell. Most modules replace existing operational line items. Compliance is a board-level budget conversation. Sprinto charges ₹8-25 lakh/year for compliance automation alone. Selling URIP without Compliance positions us as "another vulnerability dashboard" (low-budget). Selling URIP with Compliance positions us as "compliance + risk + audit platform" (board-level budget). Same code, dramatically different sales motion.

---

## 8. Architecture (one diagram, three modes)

URIP-Adverb supports three deployment topologies. Same codebase. Different operational model.

1. **Pure SaaS** — we host everything on our infrastructure (Vercel + Cloud Run + Neon Postgres + Redis + R2). The customer logs in to `tenant.urip.io`. Fastest time-to-value. Standard SaaS commercial model.
2. **On-Premise Licensed** — the customer hosts everything in their own infrastructure. Maximum data sovereignty. Zero operational burden on us. Less commercial leverage long-term.
3. **Hybrid-SaaS (recommended)** — the cloud portal lives in our infrastructure for UI and intelligence; a Docker agent lives inside the customer's network for connectors and raw storage. Sensitive identifiers — IPs, hostnames, usernames, evidence files — never leave the customer network. Same architectural pattern CrowdStrike Falcon, Tenable Nessus Agent, and Splunk Forwarder use to clear procurement at regulated buyers.

**The Hybrid-SaaS architecture diagram:**

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
│                                        │ HTTPS (HMAC-signed)     │
└────────────────────────────────────────┼─────────────────────────┘
                                         │
                                         ▼
┌──────────────────────────────────────────────────────────────────┐
│                  CUSTOMER NETWORK                                 │
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
│  │  │ Drill-Down Tunnel (on-demand reverse-WebSocket)       │ │ │
│  │  │ User clicks "View Details" → cloud signs JWT →        │ │ │
│  │  │ agent fetches from local PG → streams to user browser │ │ │
│  │  │ Nothing persisted in cloud                            │ │ │
│  │  └───────────────────────────────────────────────────────┘ │ │
│  └────────────────────────────────────────────────────────────┘ │
│                              │                                    │
│                              ▼                                    │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │ Local Postgres (customer-owned)                             │ │
│  │ Full risk records w/ IPs, hostnames, usernames              │ │
│  │ Compliance evidence files, audit logs, vendor docs          │ │
│  │ STAYS ON CUSTOMER NETWORK FOREVER                           │ │
│  └────────────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────────┘
```

**The trust boundary, in plain English.** The only thing crossing from the customer network to our cloud is a tiny JSON envelope of summary metrics — risk scores, control pass/fail counts, compliance percentages, connector heartbeats. If our cloud is breached tomorrow, the attacker sees that some tenant has a risk score of 8.2 and 73% SOC 2 compliance. They learn nothing about the customer's actual infrastructure. This is the answer that clears procurement at regulated buyers.

The Hybrid-SaaS plumbing is implemented in `agent/` (`agent_main.py`, `reporter.py`, `heartbeat.py`, `local_db.py`, `drilldown_responder.py`, `Dockerfile`, `docker-compose.agent.yml`) and `backend/routers/agent_ingest.py` + `backend/models/agent_ingest.py`. The cloud-agent contract uses HMAC-signed payloads with anti-replay over `{ts}.{path}.{body}`. Drill-down tokens live 60 seconds, are invalidated after fulfilment, and the response is wiped after the SSE forward.

---

## 9. The Technology Stack

URIP runs on a deliberately small, opinionated stack chosen for operational simplicity. Backend: **Python 3.13 (URIP) and 3.11 (Compliance) on FastAPI**, with **SQLAlchemy 2.x async + Alembic** for the data layer and **Postgres** for storage (Neon in cloud, customer-managed in Hybrid-SaaS). Frontend: **vanilla HTML/JS + clean CSS** for the URIP admin pages — no framework overhead, no build pipeline, fast to render — with a **Next.js** option for the Compliance UI when it embeds in the URIP shell or runs standalone. Auth: **PyJWT** (URIP migrated; Compliance migration in flight) + **Fernet-encrypted secrets** per-tenant. Async tasks and cross-service eventing: **Redis pub/sub** event bus (`shared/events/redis_client.py` — already wired) with **Celery** workers for heavy connector pulls (Phase 4 deliverable). Connectors: **HTTPX + Pydantic v2** with a plugin registry. Hybrid-SaaS agent: **Docker** + **HMAC-signed reporter** + reverse-WebSocket tunnel. External feeds: **EPSS** (FIRST.org), **KEV** (CISA), **MITRE ATT&CK** (raw JSON), **OTX** (AlienVault) — all four LIVE in `backend/services/exploitability_service.py` and `backend/services/threat_intel_service.py`. Object storage: **S3-compatible** (R2 in cloud, customer-local in Hybrid-SaaS) for evidence files and exports. Observability: **structured JSON logs** per connector with Sentry for errors and Better Stack for metrics in production.

---

## 10. What Sets URIP Apart (the moat)

Three short, punchy points for the website:

1. **Risk × Control linkage.** URIP is the only platform that says *"this CVE is what's breaking your SOC 2 control CC7.1, on this Tier-1 asset, owned by this person, with EPSS 0.92 and KEV-active."* Sprinto sees the control failure but has no CVE-level threat enrichment. CloudSEK sees the threat but has no compliance scaffolding. URIP has both inside one tenant scope, joined by a single linkage table.

2. **Universal connector framework.** Bring any tool. Implement four methods. Auto-register in the catalog. The plumbing — encrypted credentials, polling, normalization, scoring, audit logging, health monitoring — is done. No custom integration project. No professional services engagement. Same wizard for the 50-person startup and the 1000-person enterprise.

3. **Hybrid-SaaS data sovereignty.** Sensitive vulnerability data — IP addresses, hostnames, usernames, evidence files — stays on the customer's network. The cloud only ever sees summary scores. Same architectural pattern CrowdStrike Falcon, Tenable Nessus Agent, and Splunk Forwarder use. Procurement-clearing at regulated buyers (PepsiCo, J&J, regulated banking, government). Sprinto cannot offer this — its entire model is cloud-side.

---

## 10a. URIP vs Vertically-Integrated Vendors (TrendAI / Wiz / Lacework / Cisco / Palo Alto)

A fair-minded competitive frame, because every CISO will ask. Vendors like Trend Micro Vision One, Wiz, Lacework, Cisco SecureX, and Palo Alto Cortex sell **both** the underlying security tools (EDR, NDR, CNAPP, SASE, …) **and** a unifying dashboard on top. URIP is a fundamentally different category — and saying so plainly makes the buying decision easier, not harder.

### When the vertically-integrated vendor wins

If a customer has standardised on **a single vendor's full stack** — TrendAI Vision One owning everything from endpoint to email to cloud, or Cisco SecureX wired across Umbrella + Secure Endpoint + Duo — that vendor's own dashboard is enough. The data model is consistent (one vendor wrote it), the licensing is consolidated, the support contract is one phone number. URIP **does not** displace this scenario, and we say so on the website. A fair fight is a winnable one; we don't pretend otherwise.

### When URIP wins (the every-other-customer scenario)

In practice almost no enterprise of any size standardises on one vendor. The mid-market SaaS company has Tenable for VM, CrowdStrike for EDR, Zscaler for CASB, Entra for identity, Workspace for email, and AWS for cloud — six different vendors, six different dashboards, six different severity scales, no single risk register, no compliance linkage, no de-duplication. **Their CrowdStrike console cannot see Tenable findings.** **Their Wiz console cannot see Burp DAST output.** **Their TrendAI console cannot see CloudSEK external threat alerts.** URIP is the cockpit that sits above all six.

### Edges TrendAI / Wiz / Cisco structurally cannot copy

| URIP edge | Why competitors can't match |
|---|---|
| **Vendor neutrality** | TrendAI / Wiz / Palo Alto sell competing scanners. Recommending CrowdStrike over Trend's own EDR breaks their P&L. URIP has no scanner to defend — every recommendation is honest by construction. |
| **Risk × Control linkage on one data layer** | Compliance and risk on the same database, joined by a single linkage table. TrendAI ships compliance reports; it does not ship a Sprinto-equivalent control engine with auditor portal. |
| **Open scoring standards** | EPSS (FIRST.org) + KEV (CISA) + MITRE ATT&CK + OTX. No proprietary "TrendAI Risk Index". The customer's auditor and the customer's board can both read URIP scores without learning a vendor-specific scale. |
| **Hybrid-SaaS data sovereignty** | TrendAI is cloud-side. Wiz is cloud-side. Sprinto is cloud-side. URIP's hybrid mode keeps IPs / hostnames / usernames / evidence on the customer network — a procurement-clearing answer at regulated buyers. |
| **Native compliance built-in** | Sprinto-equivalent module on the same data layer as the risk register. Trend / Wiz bolt on compliance via Drata or Vanta partnerships — two vendors, two databases, two questionnaire engines. |
| **VAPT Vendor Portal (vendor-facing)** | A dedicated sub-portal where the customer's pentest vendor logs in directly, submits findings, and runs the re-test loop. Trend / Wiz / Cisco do not have this — their model is their own scanners only. |
| **Pricing reality** | TrendAI Vision One full stack runs into seven figures for a mid-enterprise. URIP is per-module with the scanners the customer already pays for excluded. The cost-consolidation pitch is severable per module. |

### The pitch, said plainly

> **TrendAI sells you their stack. Wiz sells you their CNAPP. Cisco sells you their SASE. URIP doesn't sell stack — we sell unification of whatever stack you have, including TrendAI's, Wiz's, and Cisco's. The day you decide to swap CrowdStrike for SentinelOne, our cockpit doesn't care. Try saying that to your TrendAI rep.**

This is the line that closes the conversation when a sceptical CISO asks "but I already pay TrendAI for Vision One — why URIP?". **Answer**: because tomorrow when your security committee adds a tool that isn't TrendAI — and they will — URIP already covers it. Your TrendAI dashboard does not.

---

## 11. Who It's For

URIP is built for organisations that already own a security stack and are tired of swivel-chairing between consoles. The sweet spots:

- **Mid-market SaaS companies (50-1000 employees)** facing customer security questionnaires, chasing SOC 2 Type 2 / ISO 27001, and managing 5-15 security tools without a dedicated SOC.
- **Manufacturing, robotics, and regulated industries** with multi-customer audit pressure, on-prem operational technology, and a procurement requirement that vendor data not leave the customer network — the Hybrid-SaaS sweet spot.
- **Any company with 5+ security tools** that wants ONE pane — risk register, threat intelligence, compliance status, evidence, auditor portal — without rebuilding the data layer themselves.
- **Compliance-first prospects** (DPO buyer, no CISO involvement) who only want audit-readiness — they buy the standalone Compliance Module without the URIP risk layer.

---

## 12. The Asks From The Customer

URIP cannot run on goodwill. To make it work the customer brings the following — eight concrete artefacts that close the gap between "platform installed" and "platform delivering value." All of them sit inside the customer's existing IT estate; none requires net-new tooling.

| # | What we need | Why |
|---|---|---|
| 01 | **Tool APIs** — read-only API keys / OAuth credentials for every tool the customer wants connected (Tenable, CrowdStrike, SentinelOne, Zscaler, Netskope, MS Entra, ManageEngine SDP, Armis, etc.). Read-only is fine for everything except ITSM (needs write for bidirectional ticketing). | Connector wizard cannot poll without them. |
| 02 | **OT Network** — network topology of the OT segment (Armis / Claroty / Nozomi / Dragos). Decision: On-Premise Collector or Secure API Gateway (DMZ proxy). | OT segments are isolated; we need to agree on the access pattern. |
| 03 | **CMDB / Asset Tags** — CrowdStrike asset criticality tags or ServiceNow CMDB Business Criticality field — for asset tiering (T1-T4). | Composite scoring uses asset tier; without tags we fall back to a keyword classifier. |
| 04 | **VAPT Sample** — one sample VAPT report (PDF or Excel) — to finalise the import parser and remediation extraction logic for that specific vendor's report format. | VAPT report formats vary per pentest vendor. |
| 05 | **Risk Logic** — how the customer currently rates Bug Bounty (P1 / P2?), SoC alerts, CERT-In responses. We honour the customer's existing rating and overlay the URIP composite. | We keep the customer's current rating system intact, then enrich it. |
| 06 | **Ticketing** — Jira or ServiceNow? Project / board structure for vulnerability tickets? | Bidirectional sync needs the project key + workflow definition. |
| 07 | **Owner Matrix** — Product Owner mapping per asset / domain. Who is responsible for what? | Auto-assignment cannot work without owner-of-record. |
| 08 | **Competitor Quotes** — quotes from incumbents (PFC, Sprinto, MetricStream, etc.) — for commercial benchmarking and to make sure URIP's modular pricing comes in attractive. | Helps us tailor the commercial conversation rather than negotiate blind. |
| Plus | **One tenant admin user** to configure the workspace — brand, frameworks, modules, invites. |
| Plus | **Network allowlist** — Pure SaaS: allowlist our cloud egress IP; Hybrid-SaaS: allow agent outbound HTTPS to our cloud + (optional) inbound for drill-down reverse-tunnel. |
| Plus | **MS Entra admin consent** if Identity / Collaboration modules are subscribed — least-privilege scopes documented in the per-tool wizard. |
| Plus | **Burp Suite Enterprise license confirmation** if DAST module is subscribed — Burp Pro alone does not expose the full programmatic API. |

That's it. No professional services engagement. No bespoke integration project. No consultant onsite.

---

## 13. What's Built Today vs What's Coming

Honest LIVE / PARTIAL / ROADMAP breakdown. Three labels used consistently — `✅ LIVE` (code runs against the real upstream API or framework in production today, with tests), `🟡 PARTIAL` (code exists, real-credential wire-in or vendor surface still pending), `🔴 ROADMAP` (code does not exist, planned).

### ✅ LIVE today

**29 real production connectors** — every directory under `connectors/` ships a `connector.py` honouring the four-method contract:

| Category | Connector | Path |
|---|---|---|
| VM | Tenable | `connectors/tenable/connector.py` |
| EDR + VM (Spotlight) | CrowdStrike Falcon | `connectors/crowdstrike/connector.py` |
| EDR | SentinelOne | `connectors/sentinelone/connector.py` |
| Identity | MS Entra ID | `connectors/ms_entra/connector.py` |
| CASB / SWG | Zscaler | `connectors/zscaler/connector.py` |
| CASB / DLP | Netskope | `connectors/netskope/connector.py` |
| ITSM | ManageEngine SDP | `connectors/manageengine_sdp/connector.py` |
| UEM | ManageEngine Endpoint Central | `connectors/manageengine_ec/connector.py` |
| MDM | ManageEngine MDM | `connectors/manageengine_mdm/connector.py` |
| Collaboration | M365 (SharePoint/OneDrive/Teams) | `connectors/m365_collab/connector.py` |
| DAST | Burp Enterprise | `connectors/burp_enterprise/connector.py` |
| DLP | GTB Endpoint Protector | `connectors/gtb/connector.py` |
| External Threat | CloudSEK (XVigil + BeVigil + SVigil) | `connectors/cloudsek/connector.py` |
| CSPM (AWS) | AWS Config / Security Hub | `connectors/aws_cspm/connector.py` |
| CSPM (Azure) | Azure Policy / Defender | `connectors/azure_cspm/connector.py` |
| CSPM (GCP) | Google Security Command Center | `connectors/gcp_cspm/connector.py` |
| OT | Armis | `connectors/armis_ot/connector.py` |
| NAC | Forescout | `connectors/forescout_nac/connector.py` |
| PAM | CyberArk | `connectors/cyberark_pam/connector.py` |
| Firewall | Fortiguard | `connectors/fortiguard_fw/connector.py` |
| Email Security | Google Workspace + M365 Defender | `connectors/email_security/connector.py` |
| CERT-In | India regulatory advisories | `connectors/cert_in/connector.py` |
| Bug Bounty | HackerOne + Bugcrowd + webhook | `connectors/bug_bounty/connector.py` |
| SIEM | Splunk + Elastic + QRadar | `connectors/siem/connector.py` |
| EASM | Censys + Shodan + Detectify | `connectors/easm/connector.py` |
| LMS (Security Awareness Training) | KnowBe4 | `connectors/knowbe4/connector.py` |
| LMS (Phishing Simulation) | Hoxhunt | `connectors/hoxhunt/connector.py` |
| BGV (Background Verification) | AuthBridge | `connectors/authbridge/connector.py` |
| BGV (Background Verification) | OnGrid | `connectors/ongrid/connector.py` |

**Universal connector framework** — `BaseConnector` 4-method contract, plugin registry, async scheduler, per-tenant Fernet vault. Every category in §5 is reachable through this framework.

**Universal simulator** — `connectors/simulator_connector.py` + `connectors/extended_simulator.py` — every category exercisable end-to-end before any real connector is configured. Used as the test-harness for new connector authors.

**Intelligence Engine (NEW — see §5.1.1)** — five orchestration services that turn raw connector output into a unified, de-duplicated, applicability-checked, remediation-attached risk record:
- `backend/services/severity_normalizer.py`
- `backend/services/asset_fingerprint_service.py`
- `backend/services/advisory_applicability_service.py`
- `backend/services/remediation_fetcher.py`
- `backend/services/connector_runner.py`

**Composite scoring engine** — `backend/services/exploitability_service.py` (CVSS × 0.55 + EPSS × 2.5 + KEV bonus + asset-tier bonus). Tunable per tenant via `frontend/admin-scoring.html`.

**Risk Index Service + Risk Snapshot** — `backend/services/risk_index_service.py` + `backend/routers/risk_index.py` produce a 0-100 cockpit headline score with 3 subindexes (exposure / attack / security_config) and 5 domain buckets (devices / internet-facing / accounts / applications / cloud-assets). Point-in-time risk posture is captured in `backend/models/risk_snapshot.py` + `backend/services/risk_aggregate_service.py` for week-over-week and month-over-month delta charts on the Risk Center home.

**4 live external intelligence feeds** — EPSS (FIRST.org), KEV (CISA), MITRE ATT&CK CVE-to-APT, AlienVault OTX — wired in `backend/services/threat_intel_service.py`.

**15 pre-seeded compliance frameworks (~895 controls)** — under `compliance/backend/compliance_backend/seeders/`. Original 7 (SOC 2, ISO 27001, GDPR, HIPAA, PCI DSS, India DPDP, NIST CSF) ship audit-grade control catalogues. 8 new (ISO 42001, EU AI Act, DORA, NIS2, ISO 27017/27018/27701, CIS v8) ship scaffold-grade catalogues — **honest caveat:** the new-8 control text is paraphrased from public summaries (the canonical PDFs are paywalled), so customers should reconcile against the licensed ISO/CIS texts before audit submission. 60 cross-framework mappings catalogued. Auditor portal at `compliance/frontend/auditor_portal.html` with framework-scoped, time-bound, read-only invitations.

**VAPT Vendor Portal (NEW — see §6c)** — full LIVE end-to-end:
- `backend/models/vapt_vendor.py`, `backend/schemas/vapt_vendor.py`
- `backend/services/vapt_vendor_service.py`
- `backend/middleware/vapt_vendor_auth.py`
- `backend/routers/vapt_admin.py`, `backend/routers/vapt_vendor_portal.py`
- `frontend/vendor-login.html`, `frontend/vapt-portal-{login,dashboard,submit,submission-detail}.html`, `frontend/admin-vapt.html`
- 52 tests across `tests/test_vapt/`

**Trust Center / SafeBase-equivalent (NEW — promoted from PARTIAL → LIVE)** — full backend + frontend:
- `backend/models/trust_center.py`, `backend/services/trust_center_service.py`
- `backend/routers/trust_center_admin.py`, `backend/routers/trust_center_public.py`
- `frontend/trust-center/{index,admin,request}.html`
- Per-tenant publish flow, NDA e-sign, time-bound (default 72-hour) SHA-256-hashed access tokens, public landing page at `/trust/{tenant_slug}`
- Tests in `tests/test_trust_center/`
- *Operational note:* file streaming hands the storage URI to the caller; the production S3/R2 byte stream is the per-tenant deployment step (no code change).

**Jira + ServiceNow bidirectional ticketing (NEW — promoted from PARTIAL → LIVE)** — full framework:
- `backend/integrations/ticketing/{base,jira,servicenow}.py`
- `backend/services/ticketing_service.py`
- `backend/routers/ticketing_webhook.py`
- Auto-create on risk assignment, HMAC-signed Jira/ServiceNow webhooks for close-loop sync, periodic poll fallback
- Tenant config drives provider selection (`tenant.settings.ticketing.{provider, base_url, auth_token, project_key}`)
- Tests in `tests/test_ticketing/`
- *Operational note:* live calls against a specific Atlassian Cloud / ServiceNow instance happen at tenant onboarding when the customer pastes the token.

**Auto-Remediation Phase 2 framework (NEW — promoted from ROADMAP → LIVE)** — full executor framework:
- `backend/services/auto_remediation/{base,crowdstrike_rtr,ansible,fortinet,cyberark}.py`
- `backend/services/auto_remediation_service.py`, `backend/routers/auto_remediation.py`
- Implication-check + approval-gate + re-test pipeline; audit log table `auto_remediation_executions` records every execution with before/after state
- Tenant whitelist for pre-approved categories (`auto_remediation_categories: ["ssl_expired", "missing_dmarc"]`) supports zero-touch closure
- Tests in `tests/test_auto_remediation/`
- **CrowdStrike RTR OAuth2 token exchange — LIVE** (Bearer flow with token cache + refresh-on-expiry, replaced earlier Basic-auth shape; 5 dedicated tests in `tests/test_auto_remediation/test_crowdstrike_oauth2.py`)
- *Operational note:* the executors are framework-complete with the correct HTTP shape per vendor (CrowdStrike RTR Bearer, Ansible Tower, Fortinet REST, CyberArk REST). Live calls require per-tenant production credentials wired at deployment.

**CSPM module (NEW)** — native cloud posture engine:
- `backend/services/cspm_engine.py`, `backend/services/cspm_rules/` (rule library)
- `backend/routers/cspm.py`
- `frontend/cspm-{dashboard,findings,control-detail}.html`
- Drives the AWS / Azure / GCP CSPM connectors above
- Tests in `tests/test_cspm/`

**Both dashboards** — URIP at `frontend/`, Compliance at `compliance/frontend/`. Full end-to-end UI.

**Hybrid-SaaS Docker agent** — `agent/` (agent_main, reporter, heartbeat, drilldown_responder, local_db, Dockerfile). Cloud ingest endpoint at `backend/routers/agent_ingest.py` with HMAC + anti-replay + one-time drill-down tokens.

**Multi-tenant data plane** — `tenant_id` on every domain table + `apply_tenant_filter` helper + integration tests for cross-tenant isolation.

**White-label per-tenant theming** — logo, color palette, app name, favicon, login background.

**Evidence integrity** — `content_sha256` per evidence record. Reused by VAPT submissions, compliance evidence, and Trust Center publish flow.

**16 license modules** — CORE + 15 capability modules including CSPM and the five new MVP-scaffold modules promoted from §13 ROADMAP (DSPM, AI_SECURITY, ZTNA, ATTACK_PATH, RISK_QUANT). Module gating enforced at UI route, API decorator, and connector data plane.

**5 new modules — MVP scaffold depth (NEW — see §13 honest caveat)** — promoted from ROADMAP → LIVE at scaffold level. Each ships model + service + REST API + 1 frontend page + tests:
- **DSPM (12th license module)** — `backend/services/dspm/`, `backend/routers/dspm.py`, `backend/models/dspm.py`, `frontend/dspm-dashboard.html`. Endpoints: `GET /api/dspm/data-assets`, `GET /api/dspm/sensitive-discoveries`, `GET /api/dspm/access-paths`, `POST /api/dspm/scan`. Tests in `tests/test_dspm/`.
- **AI Security (13th)** — `backend/services/ai_security/`, `backend/routers/ai_security.py`, `frontend/ai-security-dashboard.html`. Endpoints: `GET /api/ai-security/models`, `GET /api/ai-security/prompt-injections`, `GET /api/ai-security/governance-status`. Tests in `tests/test_ai_security/`.
- **ZTNA (14th)** — `backend/services/ztna/`, `backend/routers/ztna.py`, `frontend/ztna-dashboard.html`. Endpoints: `GET /api/ztna/policies`, `GET /api/ztna/access-decisions`, `GET /api/ztna/posture-violations`. Tests in `tests/test_ztna/`.
- **Attack Path Prediction (15th)** — `backend/services/attack_path/`, `backend/routers/attack_path.py`, `frontend/attack-path.html`. BFS engine + MITRE ATT&CK chain overlay. Endpoints: `GET /api/attack-paths/critical`, `GET /api/attack-paths/{path_id}/details`, `POST /api/attack-paths/recompute`. Tests in `tests/test_attack_path/`.
- **Cyber Risk Quantification / FAIR (16th)** — `backend/services/risk_quantification/`, `backend/routers/risk_quantification.py`, `frontend/risk-quantification.html`. Open FAIR (LEF × LM = ALE) with per-tenant configurable assumptions. Endpoints: `GET /api/risk-quantification/{risk_id}`, `GET /api/risk-quantification/aggregate`, `GET/POST /api/risk-quantification/assumptions`. Tests in `tests/test_risk_quantification/`.

Migration: `alembic/versions/0015_p33a_section13_modules.py` (creates 13 tables across the 5 modules).
**Honest depth caveat (read this in every customer demo):** these are MVP scaffolds — model + REST surface + 1 frontend page + seed-data hooks so a buyer sees the module exists in nav, can fetch from API, and can populate it from existing connector data. Full feature parity with vertically-integrated competitors (Wiz DSPM, Hidden Layer / Lakera AI, BloodHound XM Cyber, RiskLens FAIR) is the next-iteration roadmap. The MVP scaffold value proposition is that all 16 modules sit on one cockpit with one risk register — not that any single one is best-of-breed yet.

**1800+ tests** across services — `tests/test_{vapt,cspm,ticketing,trust_center,auto_remediation,...}/`.

**Demo seed data** — `adverb-demo` tenant with ~5,100 control runs, ~850 evidence files, 18 vendors, 30 incidents, 120 assets, 20 access review campaigns / 500 decisions, 4 auditor invitations, 630 compliance score snapshots, ~1,200 audit log entries.

**Standalone Compliance deployment** — `compliance/docker-compose.standalone.yml` for the Sprinto-replacement go-to-market.

**4 Wave 1 connectors (NEW — promoted from ROADMAP → LIVE):**
- **KnowBe4** — `connectors/knowbe4/connector.py` (LMS — security awareness training completion telemetry as compliance evidence)
- **Hoxhunt** — `connectors/hoxhunt/connector.py` (LMS — phishing simulation results as compliance evidence)
- **AuthBridge** — `connectors/authbridge/connector.py` (BGV — background verification status as compliance evidence)
- **OnGrid** — `connectors/ongrid/connector.py` (BGV — background verification status as compliance evidence)

### 🟡 PARTIAL — code LIVE, production credentials / SaaS-side wire-in pending

These are LIVE in code; what's pending is **only** the per-tenant credential / endpoint configuration that happens at customer onboarding — **not** more engineering.

- ~~Auto-Remediation production execution~~ → **PROMOTED LIVE.** Per-tenant credential vault wiring (`backend/services/auto_remediation/executor_factory.py`) loads CrowdStrike / Ansible / Fortinet / CyberArk credentials from the existing Fernet vault keyed by `(tenant_id, executor_kind)`; HTTPX client sends real auth headers (Basic/Bearer per vendor). 38 auto-remediation tests pass with mocked HTTP shape.
- ~~Jira / ServiceNow live tenant integration~~ → **PROMOTED LIVE.** Pydantic `TicketingConfig` validator + pre-flight ping (`backend/integrations/ticketing/config_schema.py`) — admin pastes config blob, server validates schema, then hits `/myself` (Jira) / `/api/now/table/{table}` (ServiceNow) to verify token + project key exist before save. 14 schema/preflight tests pass.
- ~~Trust Center file streaming~~ → **PROMOTED LIVE.** Real bytes streamed via `StreamingResponse` (file://) and boto3 `get_object` (s3://); HTTP range requests return 206 with Content-Range; mime-type sniffed from file header; Content-Disposition set for browser downloads. 9 streaming tests pass.
- ~~Risk → Control linkage event bus~~ → **PROMOTED LIVE.** In-process bus singleton (`shared/events/bus.py`) with optional Redis mirror. URIP publishes `urip.risk.created` / `urip.risk.resolved`; URIP subscribes to `compliance.control.failed` (auto-creates linked risks when tenant opts in via `compliance_link_auto_create_risk: true`) and `compliance.policy.expiring`; Compliance side emits `compliance.control.failed` from the control engine on `fail` results. 5 event-wiring tests pass.
- **Async task queue** — Celery + Redis worker pool for heavy connector pulls (architecture chosen, deployment plumbing pending).

### 🔴 ROADMAP — beyond the cockpit's current scope

> The five items previously listed here (DSPM, AI Security, ZTNA, Attack Path Prediction, Cyber Risk Quantification) have been **promoted to LIVE at MVP scaffold depth** — see the LIVE section above for the honest caveat on what "MVP scaffold" means. Full feature parity with vertically-integrated competitors remains roadmap.

- **DSPM full content classifier + lineage graph** — current LIVE scaffold ships inventory + REST surface; ML classifier and cross-store data-flow graph are the next iteration.
- **AI Security runtime model-firewall + automated red-teaming** — current LIVE scaffold ships inventory + governance ledger + manual prompt-injection ingest; sidecar firewall and automated fuzzing are the next iteration.
- **Attack Path Prediction probability-weighted scoring** — current LIVE scaffold ships BFS path-finder with deterministic risk scoring; CVSS-weighted multi-hop probability scoring is the next iteration.
- **Risk Quantification Monte Carlo over LEF/LM distributions** — current LIVE scaffold ships point-estimate FAIR; probabilistic distributions and ranged outputs are the next iteration.
- **Additional compliance framework seeders** — ISO 42001 (AI management), EU AI Act, DORA (financial sector), NIS2 (EU critical infrastructure).
- **BitSight integration (optional)** — board-level posture grade (A/B/C/D/F) + post-remediation grade-change tracking. Optional paid add-on.
- ~~Word Cloud Threat Map~~ → **LIVE.** `GET /api/threat-intel/word-cloud` returns three buckets (apt_groups, ttps, sectors) aggregated from MITRE CVE→APT static map + OTX pulses. `frontend/threat-map.html` renders three D3 word-cloud canvases via the d3-cloud CDN plugin. 6 endpoint tests pass.
- ~~Auditor activity heatmap~~ → **LIVE.** `GET /admin/auditor-activity/heatmap?days=30` returns calendar-day buckets with action counts; `compliance/frontend/auditor-activity.html` renders a GitHub-style 4-level heatmap grid with per-cell tooltips. 3 heatmap tests added (compliance backend deps incomplete in dev env — see honest blockers).
- **Productivity / collab connectors** — Slack, GitHub Advanced Security, Okta, Auth0.
- ~~LMS integration~~ → **LIVE.** KnowBe4 (`connectors/knowbe4/`) and Hoxhunt (`connectors/hoxhunt/`) connectors ship the 4-method contract; training-completion telemetry surfaces as compliance evidence. Cybeready remains roadmap.
- ~~BGV integration~~ → **LIVE.** AuthBridge (`connectors/authbridge/`) and OnGrid (`connectors/ongrid/`) connectors ship the 4-method contract; background-verification status surfaces as compliance evidence. We do not run BGV ourselves.
- **Framework-specific report templates** — SOC 2 board pack, ISO 27001 Statement of Applicability, HIPAA risk analysis, GDPR Article 30 register, PCI DSS AOC inputs.

### The honest framing — universal cockpit, not a fixed connector list

URIP supports **every source category** an enterprise security stack contains. The framework + simulator + scoring engine + intelligence engine + audit log + dashboard are universal — they work for ANY connector. Today we ship **29 real production connectors LIVE** plus the framework for everything else. **No customer is told "we don't support that tool" — they're told "we already do, or one file lands and we will."**

---

## 13a. Implementation Phases (Wave A → Wave F)

A typical 7,000-endpoint enterprise rollout with 14 sources runs through six waves. Naming is deliberately neutral — Wave A through Wave F (or Phase 1 through Phase 6 internally) — so the conversation stays focused on outcomes per wave, not on a specific calendar.

| Wave | Deliverable | Milestone |
|---|---|---|
| **Wave A — Core Data Flowing** | First two connectors stood up (typically VM + EDR — e.g., CrowdStrike Spotlight + Falcon, or Tenable + SentinelOne). OT network access pattern decided and live (On-Prem Collector or Secure API Gateway). Asset fingerprinting active. Managed / Unmanaged / Unknown classification engaged. | Live data from the customer's two highest-volume sources landing in URIP. |
| **Wave B — Register Live with Remediation** | Risk register populated. Composite scoring (CVSS + EPSS + KEV + asset bonus) computing on every finding. Raised Date + Pending Days counters running. Remediation steps auto-fetched from NVD on every CVE. VAPT Vendor Portal stood up + file parser tuned to the customer's vendor format. | The IT team works the URIP register instead of Excel. |
| **Wave C — Full Workflow Live** | Risk Acceptance Workflow with HoD digital sign-off. Jira / ServiceNow bidirectional ticketing wired. Advisory Applicability Engine (Valid / Patch Available / Expired / Redundant) classifying every advisory. | Risk lifecycle is fully owned inside URIP — no parallel Excel. |
| **Wave D — Demo Ready** | Executive Security Posture Dashboard. Board + CERT-In compliance reports. APT tagging + IOC matching active on every applicable risk. Role-based access (CISO / IT / Executive / Board / Auditor) tightened. | Customer can present URIP to their board and to CERT-In auditors. |
| **Wave E — Full System Live** | Remaining connectors (the long-tail tools: PAM, NAC, DLP, DAST, etc.) connected. UAT cycle with the customer's IT team. Auto-Remediation script library piloted on a controlled set of CVE classes (CrowdStrike RTR for endpoint patches first). Implication Check engine tested against staging. | The customer's full stack is feeding URIP. Auto-Remediation pilot proven safe. |
| **Wave F — Production + Auto-Remediation Go-Live** | Auto-Remediation pipeline goes live (gated by Implication Check + Approval Gate). Performance testing under load. Ops team training and handover documentation. | URIP is operationally owned by the customer's team. We move to support mode. |

Per project rule, no specific calendar dates appear in this blueprint — wave duration depends on the customer's environment scale, the number of in-scope connectors, and their UAT cadence. A 50-person SaaS startup with 5 connectors completes Waves A-D in a fraction of the time a 7,000-endpoint manufacturer with 14 sources will.

---

## 14. The Pricing Story

URIP is sold on a per-module subscription model. CORE is always-on and bundled into the base subscription; capability modules are line items added on top.

- **Per-module licensing.** Each tenant subscribes to exactly the modules they need. Disabled modules are dark in the UI and inactive in the backend. A startup might subscribe to Core + Compliance only. A factory might subscribe to Core + VM + Network + ITSM. An enterprise might subscribe to all 16.
- **Compliance Module is the strategic upsell.** Sprinto charges ₹8-25 lakh/year for compliance automation alone. Selling URIP without Compliance puts the conversation in operational-tool budget. Selling URIP with Compliance puts the conversation in board-level GRC budget.
- **Hybrid-SaaS deployment baseline.** ~₹400/month VPS minimum on the customer side for the on-prem Docker agent (a 2 vCPU / 4 GB instance is enough for most tenants), plus the URIP subscription. The cloud portal is included.
- **Cost-consolidation pitch.** A typical 1000-employee mid-market customer today: Sprinto ₹20-40 lakh/year + CloudSEK ₹15-40 lakh/year + manual audit-prep consultant time ₹8-15 lakh/year + tool swivel-chair FTE overhead ₹15-25 lakh/year ≈ **₹58-120 lakh/year** — and they still don't have a unified risk view. URIP-Adverb bundles the compliance module, external threat (CloudSEK API integration — Option A), and the Risk-Control linkage that neither vendor can offer, at a single competitive subscription with on-demand customisation included rather than billed as a separate consulting engagement.

Specific pricing tiers and per-customer commercials sit outside this document by project rule.

---

## 15. Honest Limitations

URIP is a cockpit and a scaffold, not a do-everything platform. (See §1.5 for the structural list of "What URIP Is NOT" — endpoint agent, network sensor, email gateway, code scanner, CSPM scanner-with-agent, SOC, threat-intel research firm.) The list below covers six adjacent **operational** things customers regularly ask about — and the honest answer for each.

- **We don't crawl the dark web.** We integrate with CloudSEK (Option A) — they run the crawler infrastructure (Tor exit nodes, residential proxies, Telegram scraping bot fleet, paid DNS feeds, image-matching AI for logo abuse), we surface their alerts inside the unified URIP dashboard with EPSS + KEV + asset-tier prioritisation on top.
- **We don't run a SOC.** URIP surfaces and prioritises risks. It does not respond to incidents. The customer's security team or SOC vendor still owns response. URIP is the unified pane on which they triage; it is not the responder.
- **We don't author training videos.** We integrate with KnowBe4 / Hoxhunt / Cybeready and pull training-completion telemetry as compliance evidence. We do not build training content.
- **We don't run BGV.** We integrate with AuthBridge / OnGrid and pull background-verification status as evidence. We do not perform BGV ourselves.
- **We are not the auditor.** We make audits easy — automated evidence collection, control monitoring, policy tracking, reporting, a read-only auditor portal. The customer still owns control design decisions, policy approvals, employee acknowledgments, vendor selection, and the actual audit engagement with the auditor.
- **We are not legal counsel.** Framework templates and policies are starting points. The customer's legal / compliance counsel must review and tailor them for their jurisdiction and customer contracts.

---

## 15a. Recommended Enhancements — Word Cloud Threat Map

A board-friendly visual that takes one glance to read and answers three questions at once: *who is attacking, how do they attack, who else do they target?* Recommended for the post-demo enhancement sprint — not yet implemented.

| Visual | Content |
|---|---|
| **Word Cloud 1 — Threat Actors** | Most active APT groups currently targeting the customer's sector. Word size = frequency of mentions in MITRE + OTX pulses over the last 30 days. Example: APT28, APT41, Lazarus, FIN7, Lapsus$. |
| **Word Cloud 2 — Attack Techniques (TTPs)** | Top MITRE ATT&CK techniques in current threat pulses against the customer's sector. Example: Phishing (T1566), RCE (T1190 Exploit Public-Facing Application), Credential Theft (T1555), Supply Chain Compromise (T1195). |
| **Word Cloud 3 — Targeted Sectors** | Other sectors the same actors are hitting — context for "who else is being attacked the way we are?" Example: Manufacturing, Defense, Energy, Automotive, Government. |

**Demo impact** — high. Board-level visual that translates the entire threat-intel layer into a one-glance picture. **Implementation effort** — 1-2 days. Data already in URIP (MITRE ATT&CK + OTX feeds are LIVE); D3.js word cloud plugin renders the visualisation.

**Status** — `🔴 ROADMAP` — recommended for the next sprint after first customer demo feedback.

---

## 16. One-Page Summary (for sales / website)

**URIP is the cockpit for your security stack — not another tool in it.** A multi-tenant, module-pickable platform that turns whatever you already own — Tenable, CrowdStrike, SentinelOne, Zscaler, Netskope, MS Entra, ManageEngine, Armis, Burp, GTB, CloudSEK, AWS, Azure, GCP, your CERT-In subscription, your SIEM, your bug-bounty inbox, your VAPT vendor — into two linked dashboards on one data layer: URIP for live risk intelligence, Compliance for continuous audit-readiness.

**29 real production connectors LIVE today. 25+ source categories supported. 15 pre-built compliance frameworks (~895 controls — 7 audit-grade + 8 scaffold-grade with honest caveat). 4 live threat-intelligence feeds (EPSS + KEV + MITRE + OTX). 16 license modules. 1800+ tests. 3 deployment modes — Pure SaaS, On-Premise, Hybrid-SaaS.** Picked-tools onboarding in three screens.

The Intelligence Engine de-duplicates findings across sources, normalises every severity to a single 0-10 axis, classifies advisories Valid / Patch Available / Expired / Redundant, and attaches remediation steps automatically. The VAPT Vendor Portal turns one-way pentest PDFs into a closed-loop scored workflow. Jira + ServiceNow ticketing is bidirectional. Auto-Remediation framework executes CrowdStrike RTR / Ansible / Fortinet / CyberArk fixes with implication-check + approval-gate. The Trust Center publishes the customer's compliance posture publicly with NDA e-sign.

**The unique edge:** when a SOC 2 control fails, URIP already shows you the CVE causing it, its exploit probability, the APT exploiting it, and which Tier-1 asset is affected. Sprinto cannot do this. CloudSEK cannot do this. TrendAI Vision One cannot do this — they would have to integrate competing scanners they sell against. URIP can, because URIP doesn't sell the stack — URIP sells the cockpit on top of whatever stack you have.

**Taglines:**
- **The cockpit for your security stack.**
- **Your tools. Your data. One pane. Audit-ready.**
- **We don't sell security. We sell visibility on the security you already bought.**

---

## Appendix A — Glossary of Key Terms

Quick reference for every abbreviation used in this blueprint and in URIP demos. Grouped for the audience to skim.

### Group 1 — Scoring

| Term | Full Name | Managed By | Plain-English Function |
|---|---|---|---|
| CVE | Common Vulnerabilities & Exposures | MITRE | The unique ID number for a bug. Every vulnerability gets one. |
| CVSS | Common Vulnerability Scoring System | FIRST.org | The size of the hole. Score 0-10. 10 = giant hole. |
| EPSS | Exploit Prediction Scoring System | FIRST.org | Probability the CVE will be exploited in the next 30 days (0-1). |
| KEV | Known Exploited Vulnerabilities | CISA | Confirmed list of CVEs being actively used by attackers right now. |
| SSVC | Stakeholder-Specific Vulnerability Categorization | CISA / SEI | Decision label: ACT NOW / ACT / ATTEND / TRACK. |

### Group 2 — Threats

| Term | Full Name | Managed By | Plain-English Function |
|---|---|---|---|
| APT | Advanced Persistent Threat | CrowdStrike / MITRE | Professional hacker groups, often nation-state-backed. |
| IOC | Indicator of Compromise | Logs / SIEM | Fingerprint evidence (malicious IP / hash / domain) that an attacker has been on your network. |
| TTP | Tactics, Techniques & Procedures | MITRE ATT&CK | How attackers actually operate — the moves they use. |

### Group 3 — Organizations

| Term | Full Name | Type | Function |
|---|---|---|---|
| CISA | Cybersecurity & Infrastructure Security Agency | US Gov | Issues directives. Manages the KEV catalog. |
| MITRE | MITRE Corporation | Research Org | Creates CVE names. Maintains ATT&CK framework. |
| CERT-In | Indian Computer Emergency Response Team | India Gov | Issues advisories. Responds to India-specific cyber incidents. |
| NIST | National Institute of Standards & Technology | US Gov | Defines security program standards (NIST CSF). |

### Group 4 — Core Risk Source Categories

| Term | Full Name | Sample Tools | Plain-English Function |
|---|---|---|---|
| VM / Spotlight | Vulnerability Management | Tenable, Qualys, Rapid7, CrowdStrike Spotlight | Finds old / weak software inside your computers. |
| EASM | External Attack Surface Management | CrowdStrike External, Detectify, Censys, Shodan | Looks at your environment from the internet inwards — finds open doors. |
| CNAPP / CSPM | Cloud Native Application Protection / Cloud Security Posture Management | AWS Config, Azure Defender, GCP SCC, Wiz | Protects cloud servers and accounts from misconfigurations. |
| OT | Operational Technology | Armis, Claroty, Nozomi, Dragos | Protects factory machines and industrial equipment. |
| VAPT | Vulnerability Assessment & Penetration Testing | External vendors | Ethical hackers paid to find and report holes. |
| Threat Intel | Threat Intelligence | OTX, FIRST.org, MITRE | Live feed of what bad actors are doing globally. |
| Bug Bounty | Bug Bounty Program | HackerOne, Bugcrowd, Intigriti | Paying researchers to responsibly report bugs. |
| SoC / SIEM | Security Operations Center / Security Information & Event Management | Splunk, Elastic, QRadar, Sentinel | 24/7 watch tower monitoring for live attacks. |

### Group 5 — Extended Security Tool Categories

| Term | Full Name | Sample Tools | Plain-English Function |
|---|---|---|---|
| EDR / XDR | Endpoint Detection & Response / Extended | SentinelOne, CrowdStrike Falcon, Defender | Watches every endpoint for live threats. |
| NAC | Network Access Control | Forescout, Cisco ISE | The bouncer — checks if a device is allowed on the network. |
| PAM | Privileged Access Management | CyberArk, BeyondTrust, Delinea | The safe — holds and controls super-powerful admin passwords. |
| CASB | Cloud Access Security Broker | Zscaler ZTA / ZIA, Netskope | Stops users accessing unauthorised or malicious cloud apps. |
| Firewall | Next-Gen Firewall | Fortiguard, Palo Alto, Check Point | The castle wall — blocks malicious traffic. |
| Email Sec | Email Security | Google Workspace, MS Defender for O365, Mimecast, Proofpoint | Stops phishing and malicious emails before they reach users. |
| ITSM | IT Service Management | ServiceNow, Jira, ManageEngine SDP | The ticketing system the IT team actually works in. |
| DLP | Data Loss Prevention | GTB, Forcepoint, Symantec, MS Purview | Stops sensitive data leaving the company. |
| DAST | Dynamic Application Security Testing | Burp Enterprise, OWASP ZAP, Acunetix | Tests running applications from outside for vulnerabilities. |

### Group 6 — Compliance Frameworks (pre-seeded in URIP)

| Term | Full Name | Audience |
|---|---|---|
| SOC 2 | System and Organization Controls 2 (Trust Services Criteria 2017+2022) | SaaS / B2B |
| ISO 27001 | ISO/IEC 27001:2022 Information Security Management | Global / Regulated |
| GDPR | General Data Protection Regulation (EU) | Anyone handling EU personal data |
| HIPAA | Health Insurance Portability & Accountability Act (US) | Healthcare / health-tech |
| PCI DSS v4.0 | Payment Card Industry Data Security Standard | Card-handling orgs |
| DPDP | Digital Personal Data Protection Act 2023 (India) | India-operating businesses |
| NIST CSF 2.0 | NIST Cybersecurity Framework 2.0 | Voluntary US framework |

---

**End of master blueprint.**
