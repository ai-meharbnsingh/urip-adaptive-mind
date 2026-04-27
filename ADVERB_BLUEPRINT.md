# URIP for Adverb — Engagement Blueprint

**Client:** Adverb
**Platform:** URIP (Unified Risk Intelligence Platform)
**Document version:** v1.0
**Date:** 2026-04-27
**Prepared by:** Semantic Gravity
**Status:** Draft — for internal alignment before client review

> **Note on timelines:** This document intentionally does not contain time, week, or effort estimates. Scope and approach are captured here; commercials and timelines will be discussed and committed separately.

---

## 0. Reading Guide (Honest Disclosure Up Front)

This document follows our standard rule: **say what is real, say what is simulated, say what is yet to be built.** No mixing.

Three labels appear throughout:

| Label | Meaning |
|---|---|
| ✅ **LIVE** | Code exists, runs against the real upstream API in production today |
| 🟡 **SIMULATED** | Code exists, but generates synthetic data (no real upstream API call). Architecture is in place — connector swap is the work. |
| 🔴 **TO BUILD** | Code does not exist. Must be designed and developed. |

If you see a feature listed without one of these three labels, it is either implicit infrastructure (database, auth, etc.) or a roll-up category.

---

## 1. Executive Summary

Adverb has provided a list of **8 security tools / platforms** that need to be unified into a single risk intelligence view:

1. Zscaler / Netskope (CASB, SWG)
2. SentinelOne (EDR/XDR)
3. Microsoft Entra ID + SharePoint + OneDrive + Teams (IAM + Collaboration)
4. ManageEngine Service Desk Plus + Endpoint Central + MDM (ITSM + UEM)
5. Tenable Vulnerability Manager (VM)
6. Burpsuite Professional (DAST)
7. GTB Endpoint Protector (DLP)
8. CloudSEK (CSPM + External Threat Monitoring) — *all features*

**The URIP engagement for Adverb has three distinct deliverables:**

- **Phase 1 — Tenant-Ready URIP (productization)**
  Refactor current URIP code so it is **multi-tenant and module-pickable**. Any future client (including Adverb) can subscribe to only the modules they need. Adverb's specific modules go live with simulated data + real exploit-intel layer so the dashboard is usable from day one.

- **Phase 2 — Adverb Live Connectors**
  Replace simulated data sources with real API integrations to Adverb's 8-tool stack. CloudSEK is handled separately because CloudSEK is a **product, not just a data source**.

- **Phase 2 (parallel) — Compliance & Audit-Readiness Layer (Sprinto-equivalent)**
  Add a compliance automation layer so any tenant (including Adverb) is **audit-ready before the audit lands**. Maps URIP risks to recognised framework controls (SOC 2, ISO 27001, GDPR, HIPAA, PCI DSS, etc.), automates evidence collection, manages policies and employee acknowledgments, runs access reviews, and provides a read-only auditor portal. See Section 7.

All three deliverables are scoped here. We can prepare and execute all of them. Sequencing and commercial terms will be agreed in the SoW.

---

## 2. Adverb's Tool Stack — Mapping Table

| # | Adverb Tool | Category | URIP-side Module | What URIP Will Do With This Data |
|---|---|---|---|---|
| 1a | Zscaler ZIA / ZTA / CASB | SWG + CASB | Shadow IT + Web Threats | Pull blocked URLs, shadow SaaS apps, malicious downloads → unified risk register |
| 1b | Netskope | CASB + DLP | Cloud App Risk | Cloud app risk score, DLP violations, sanctioned vs unsanctioned app usage |
| 2 | SentinelOne | EDR / XDR | Endpoint Threats | Active threats, quarantined items, agent health, vulnerable endpoints |
| 3a | Microsoft Entra ID | IAM | Identity Risk | Risky sign-ins, MFA bypass attempts, conditional access violations, privileged role assignments |
| 3b | SharePoint / OneDrive / Teams | Collaboration | Data Exposure | Anonymous link sharing, external sharing audit, sensitive label violations |
| 4a | ManageEngine SDP | ITSM | Remediation Tracking | Auto-create tickets for risks, track SLA, sync resolution status |
| 4b | ManageEngine Endpoint Central | UEM | Patch Compliance | Patch status per endpoint, missing critical patches, compliance score |
| 4c | ManageEngine MDM | MDM | Mobile Risk | Jailbroken devices, non-compliant mobile, lost/stolen device events |
| 5 | Tenable Vulnerability Manager | VM | Vulnerability Feed | Asset → CVE list with CVSS, exploit availability, remediation guidance |
| 6 | Burpsuite Professional | DAST | Web App Findings | Burp scan findings (XSS, SQLi, etc.) per application target |
| 7 | GTB Endpoint Protector | DLP | Data Loss Events | DLP policy violations, USB block events, exfil attempts |
| 8 | CloudSEK | CSPM + EASM + Dark Web | External Threat Layer | **See Section 6** — handled separately |

**Adverb total connectors needed in Phase 2:** 11 connectors (1a, 1b, 2, 3a, 3b, 4a, 4b, 4c, 5, 6, 7) + CloudSEK strategy.

---

## 3. Current URIP State — The Honest Audit

This section is critical. Before promising Adverb anything, we must agree internally on what URIP **actually does** today vs what the brochure says.

### 3.1 Backend Modules (`backend/`) — What Is Built

| Module | Status | Notes |
|---|---|---|
| `routers/auth.py` | ✅ LIVE | Email + password login, JWT, role-based access |
| `routers/risks.py` | ✅ LIVE | Full CRUD on risk register |
| `routers/dashboard.py` | ✅ LIVE | KPI cards, charts, source-wise breakdown |
| `routers/acceptance.py` | ✅ LIVE | HoD approval workflow for risk acceptance |
| `routers/remediation.py` | ✅ LIVE | Remediation tracking, owner assignment |
| `routers/reports.py` | ✅ LIVE | Exportable PDF / CSV reports |
| `routers/threat_intel.py` | ✅ LIVE | Threat intel surface — APT groups, IOCs |
| `routers/audit_log.py` | ✅ LIVE | Immutable audit trail of all actions |
| `routers/settings.py` | ✅ LIVE | Tenant-level scoring weights, SLA config |
| `services/exploitability_service.py` | ✅ LIVE | EPSS + KEV + composite scoring engine |
| `services/threat_intel_service.py` | ✅ LIVE | MITRE ATT&CK CVE→APT mapping, OTX IOC pulls |
| `services/scoring_config.py` | ✅ LIVE | Configurable formula weights |
| `services/sla_service.py` | ✅ LIVE | SLA derivation from severity tier |
| `services/asset_criticality_service.py` | ✅ LIVE | Keyword-based asset tier (T1–T4) classification |
| `services/crypto_service.py` | ✅ LIVE | Password hashing, token signing |
| `simulator.py` | 🟡 SIMULATED | **Generates synthetic vulnerability data labeled as 14 sources** |
| `seed.py` | ✅ LIVE | Bootstraps tenant with demo users + initial data |

**Bottom line:** URIP has a substantial, working backend. The risk register, scoring engine, dashboard, workflow, audit, and reporting layers are all real and live. The thing that is **simulated** is the data ingestion layer — the connectors that pull from CrowdStrike, Armis, Zscaler etc. all point at `simulator.py` which generates synthetic-but-realistic CVE data.

### 3.2 Live External APIs Already Wired

These connect to real internet APIs in production today:

| API | Purpose | Status | Cost |
|---|---|---|---|
| FIRST.org EPSS | Exploit probability per CVE | ✅ LIVE | Free |
| CISA KEV catalog | Known-exploited vulnerabilities | ✅ LIVE | Free |
| MITRE ATT&CK | CVE → APT group mapping | ✅ LIVE | Free (static + periodic refresh) |
| AlienVault OTX | IOC enrichment | ✅ LIVE | Free with API key |

**This is real, defensible value.** Even before any Adverb-specific connector exists, every CVE that lands in URIP gets enriched with EPSS exploit probability, KEV exploitation status, APT attribution, and IOC context. This is the layer that turns raw vulnerability data into prioritized risk.

### 3.3 What Adverb's Stack Maps To Today

| Adverb Tool | Currently in URIP? | How |
|---|---|---|
| Zscaler | 🟡 SIMULATED | `simulator.py` generates CASB-flavored synthetic data |
| Netskope | 🔴 TO BUILD | Not in simulator, no connector |
| SentinelOne | 🔴 TO BUILD | Not in simulator, no connector |
| MS Entra ID | 🔴 TO BUILD | Not in simulator, no connector |
| SharePoint / OneDrive / Teams | 🔴 TO BUILD | Not in simulator, no connector |
| ManageEngine (all 3) | 🔴 TO BUILD | Not in simulator, no connector |
| Tenable | 🔴 TO BUILD | Not in simulator, no connector |
| Burpsuite | 🔴 TO BUILD | Not in simulator, no connector |
| GTB Endpoint Protector | 🔴 TO BUILD | Not in simulator, no connector |
| CloudSEK | 🔴 TO BUILD | Strategy decision needed (see Section 6) |

**Translation:** 1 of Adverb's 11 connector slots has a simulator stub. The other 10 are net-new build. CloudSEK is a separate scope conversation.

---

## 4. Phase 1 — Productize URIP Into Modules

### 4.1 Why this phase exists

Today URIP is **single-tenant, hardcoded for Royal Enfield**. Login emails are `@royalenfield.com`. Asset criticality keywords are tuned for two-wheeler manufacturing. Branding, scoring defaults, and source labels all assume one customer.

For Adverb (and every future customer) to subscribe, we must refactor URIP into a **module-pickable, multi-tenant** platform. This is Phase 1 work and lands before any Adverb-specific connector is built.

### 4.2 Phase 1 Scope — Changes to Current Modules

| # | Change | Files Affected | Why |
|---|---|---|---|
| 1.1 | **Multi-tenant data isolation** — add `tenant_id` to every table, filter all queries by tenant | `models/*.py`, every router | One Adverb user must never see another tenant's data |
| 1.2 | **Tenant onboarding flow** — admin can create new tenant, set domain, configure modules | New `routers/tenants.py`, new admin UI | Sales needs self-serve provisioning |
| 1.3 | **Module subscription registry** — each tenant has a list of enabled modules; UI hides disabled modules | New `models/subscription.py`, frontend route guards | Adverb may not want all features; pricing tiers depend on this |
| 1.4 | **Tenant-configurable asset taxonomy** — replace hardcoded RE keywords with per-tenant config | `services/asset_criticality_service.py`, `config/tier_keywords.json` | Adverb assets are not motorcycles |
| 1.5 | **White-label branding** — logo, colors, app name configurable per tenant | Frontend theming layer | Adverb dashboard says "Adverb", not "Royal Enfield" |
| 1.6 | **Connector framework abstraction** — move from hardcoded simulator dispatch to plugin-style connector registry | New `connectors/` package, refactor `simulator.py` | Phase 2 connectors plug in cleanly without touching core |
| 1.7 | **Module-level RBAC** — roles can be scoped to specific modules (e.g., "DLP analyst" sees GTB module only) | `middleware/auth.py`, role definitions | Large clients want granular access |
| 1.8 | **Simulator → Adverb mode** — synthetic data generator with Adverb-flavored sources (Zscaler-as-Adverb, SentinelOne-as-Adverb, etc.) so the dashboard is populated for demo | `simulator.py` config | Adverb sees a populated dashboard from day one even before live connectors |
| 1.9 | **Per-tenant scoring weights** — already exists at code level; expose tenant-scoped UI | `routers/settings.py`, frontend | Adverb may weight EPSS differently than RE |
| 1.10 | **Subscription pricing module** — track which features are paid vs trial per tenant | New table + routes | Foundation for SaaS billing |
| 1.11 | **Compliance schema foundation** — add `frameworks`, `controls`, `control_evidence`, `policies`, `policy_acknowledgments`, `access_reviews`, `vendors`, `incidents` tables. Empty seed; populated by Phase 2 compliance work. | New `models/compliance.py`, new migration | Required so Compliance Module (Section 7) plugs into a stable data layer |

### 4.3 Phase 1 Deliverables to Adverb

At end of Phase 1, Adverb gets:

- ✅ **Their own URIP tenant** — `adverb.urip.io` (or similar)
- ✅ **Adverb-branded dashboard** — logo, colors, app name
- ✅ **All workflow modules** live and usable: risk register, acceptance workflow, remediation tracking, reports, audit log
- ✅ **EPSS + KEV + MITRE + OTX enrichment** — every risk that lands gets real-world exploit and threat context
- ✅ **Adverb-flavored simulator data** — dashboard is populated with realistic synthetic findings labeled as if from their actual tools, so they can see what the system will look like once live connectors are added
- ✅ **Module subscription UI** — Adverb admin picks which capability modules they want enabled
- ✅ **Configurable asset taxonomy** — Adverb's own asset categories and criticality tiers

What Adverb does **not** get in Phase 1:

- ❌ Real data flowing from their actual Zscaler / Sentinel / Tenable / etc. tenants. That is Phase 2.
- ❌ CloudSEK feature replication. That is a separate scope decision (Section 6).

---

## 5. Phase 2 — Live Connectors for Adverb's 11 Sources

Each connector follows the same pattern: read API credentials from tenant config, periodic pull, normalize into URIP risk schema, push through scoring engine. The complexity per connector varies based on API surface.

### 5.1 Connector Build Approach

| # | Connector | API Type | Auth | Notes |
|---|---|---|---|---|
| 2.1 | Zscaler ZIA / ZTA / CASB | REST API | API key + Zscaler partner key | Three sub-products, each with own endpoint |
| 2.2 | Netskope | REST API | OAuth2 token | Single product, clean API |
| 2.3 | SentinelOne | REST API (Singularity) | API token | Well-documented API |
| 2.4 | Microsoft Entra ID | MS Graph API | OAuth2 + delegated permissions | Permission consent flow + sign-in risk endpoint |
| 2.5 | SharePoint / OneDrive / Teams | MS Graph API | Same as Entra (shared auth) | Three services, sharing audit logs are large data volumes |
| 2.6 | ManageEngine SDP | REST API | OAuth2 | Bidirectional — URIP creates tickets, reads status |
| 2.7 | ManageEngine Endpoint Central | REST API | OAuth2 | Patch status + missing patches |
| 2.8 | ManageEngine MDM | REST API | OAuth2 | Mobile compliance state |
| 2.9 | Tenable Vulnerability Manager | Tenable.io API | API key pair | Mature API, similar pattern to CrowdStrike Spotlight |
| 2.10 | Burpsuite Professional | Burp Enterprise API | API key | **Caveat:** Burp Pro alone has limited API. Burp Enterprise license required for full programmatic access. Confirm with Adverb. |
| 2.11 | GTB Endpoint Protector | REST API | API key | DLP policy violation events |

### 5.2 Dependencies on Adverb (blockers we cannot solve internally)

Connectors cannot ship without these from Adverb's side:

| Item | Owner | Why blocking |
|---|---|---|
| Read-only API credentials for each tool | Adverb security team | Cannot connect without keys |
| Network allowlist for URIP backend IP | Adverb network team | Some tools (Zscaler, MS Graph) require allowlisted source IPs |
| Burp Enterprise license confirmation | Adverb procurement | Burp Pro alone insufficient for full API integration |
| MS Entra app registration + admin consent | Adverb IT admin | OAuth2 requires admin to grant URIP read scopes |

These dependencies must be tracked in the SoW so the scope clock starts only when credentials are received.

### 5.3 Connector Build Order Recommendation (priority, not schedule)

Build in **value-density order** so Adverb sees demo-able progress in waves:

1. **Wave A:** Tenable + SentinelOne → most CVE / endpoint risk volume → big dashboard impact
2. **Wave B:** Zscaler + Netskope → web/cloud risk → completes external attack surface picture
3. **Wave C:** ManageEngine SDP + Endpoint Central → closes the loop with remediation
4. **Wave D:** MS Entra + SharePoint/OneDrive/Teams → identity + data exposure
5. **Wave E:** ManageEngine MDM + GTB DLP + Burpsuite → completes the 11-tool set

---

## 6. CloudSEK — Separate Scope Decision Required

This is the section that needs a **client conversation before we commit to anything**.

### 6.1 What CloudSEK actually is

CloudSEK is not a single tool. It is **three distinct products** with their own infrastructure:

| Product | What it does | Underlying infra |
|---|---|---|
| **XVigil** | Dark web monitoring, leaked credential detection, brand abuse, fake app detection | Distributed crawler fleet on Tor/I2P + Telegram bot army + DNS feed subscriptions + image-match AI |
| **BeVigil** | Mobile app + web attack surface scanning, hardcoded secret detection | APK static analysis engine + automated Play Store / App Store scraping + secret regex library |
| **SVigil** | Supply chain risk monitoring of third-party vendors | OSINT pipelines + third-party data feeds |

This took CloudSEK years and significant funding to build.

### 6.2 Two Options — Side-by-Side Comparison

Both options are presented in full so the client can make an informed choice. Each has real benefits and real trade-offs.

#### Option A — "Adverb keeps CloudSEK; URIP integrates via CloudSEK's API"

**What it means:** Adverb's existing CloudSEK subscription stays. CloudSEK does what it does best (dark web monitoring, brand abuse, supply chain risk). URIP pulls CloudSEK's alerts via API and surfaces them inside the unified URIP dashboard alongside Tenable, SentinelOne, Zscaler, etc.

**Benefits to Adverb:**
- ✅ **Single pane of glass** — CloudSEK alerts appear in URIP next to all other risk sources. No more switching dashboards.
- ✅ **Full CloudSEK product depth** — XVigil, BeVigil, SVigil — Adverb gets the complete CloudSEK feature set as-is. Nothing is lost.
- ✅ **CloudSEK alerts get URIP prioritization** — every CloudSEK finding flows through URIP's EPSS + KEV + asset criticality scoring. A leaked credential becomes a Tier-1 risk if the affected user has admin role on a Tier-1 asset.
- ✅ **Auto-ticket creation** — CloudSEK alert → URIP risk → ManageEngine SDP ticket → SLA tracking → audit trail. Workflow continuity.
- ✅ **Faster delivery** — same connector pattern as any other source (Sentinel, Tenable etc.)
- ✅ **No new operational burden** — CloudSEK runs their crawler infra, we don't have to.
- ✅ **CloudSEK roadmap inherited** — when CloudSEK adds new features, Adverb gets them automatically without us having to build anything.

**Trade-offs:**
- ❌ Adverb continues paying CloudSEK subscription (typically ₹15–40 lakh/year depending on tier).
- ❌ Two-vendor relationship to manage (URIP + CloudSEK).
- ❌ Dependency on CloudSEK API stability — if CloudSEK changes their API, our connector breaks.
- ❌ Cannot customize what CloudSEK reports — we get whatever CloudSEK chooses to expose.
- ❌ Limited ability to differentiate URIP from CloudSEK at the feature level — we are an aggregator on top.

**Best for:** Clients who already have CloudSEK and want unified visibility, or clients who value CloudSEK's specific dark-web and external-threat depth and don't want to compromise on it.

---

#### Option B — "URIP builds CloudSEK-equivalent features natively (replaces CloudSEK)"

**What it means:** Adverb cancels CloudSEK subscription. URIP builds its own dark-web monitoring, leaked-credential detection, brand abuse, mobile attack surface, and supply chain risk capabilities. Single vendor, single platform.

**Benefits to Adverb:**
- ✅ **Single vendor relationship** — one contract, one support team, one throat to choke.
- ✅ **Subscription cost saving** — CloudSEK license cost (~₹15–40 lakh/year) goes away. Money stays with Adverb (or partly funds URIP subscription expansion).
- ✅ **Tighter integration** — native features mean URIP risk register, scoring, workflow, audit log all natively understand external threat signals. No data normalization gap.
- ✅ **Customization** — Adverb can request features, modifications, custom alerting rules. With CloudSEK, Adverb is one of thousands of customers.
- ✅ **Data sovereignty** — all data stays inside URIP infra (which can be Adverb's own cloud account if they want VPC deployment). With CloudSEK, threat intel data lives in CloudSEK's cloud.
- ✅ **Strategic moat for URIP** — once we have native external-threat layer, URIP is no longer just an aggregator — it's a full platform competing with CloudSEK + Sprinto + Tenable in one product.

**Trade-offs (and these are real):**
- ❌ **Massive infra build** — distributed dark-web crawlers (Tor exit nodes, residential proxies), Telegram scraping bot fleet, paid DNS feeds (DomainTools / WhoisXML — typically $2K–5K/month each), image-matching AI for logo abuse, APK static analysis engine, internet-wide scanner (Shodan-class).
- ❌ **Paid threat intel feed licenses** — HaveIBeenPwned ($3.5K/year), DeHashed / Constella / IntelX ($10K+/year each). Real recurring cost.
- ❌ **24/7 operational burden** — crawlers fail, proxies get blocked, Telegram channels go dark. Someone is on-call.
- ❌ **8+ years of CloudSEK head start** — we will not match CloudSEK's depth on day one. Maybe not in year one.
- ❌ **Quality risk** — if our dark-web coverage is 60% of CloudSEK's, Adverb will notice. "Why did CloudSEK find this leak last year and URIP didn't this year?"
- ❌ **Engineering team expansion required** — current URIP team cannot do this alongside Phase 2 connector work. New hires (threat researcher, ML engineer) needed.
- ❌ **Slower delivery** — this is not a 2-month build. It is a multi-quarter program.

**Best for:** Clients who want a single platform long-term, are willing to accept reduced external-threat coverage in early stages in exchange for vendor consolidation and customization, and where Adverb is willing to co-fund the build (e.g., higher subscription tier or one-time platform fee).

---

### 6.3 Side-by-Side Decision Matrix

| Dimension | Option A (Integrate) | Option B (Build Native) |
|---|---|---|
| Time to value for Adverb | Fast (single connector) | Slow (multi-quarter build) |
| CloudSEK subscription cost | Continues | Eliminated |
| URIP subscription cost | Standard | Higher (covers build + ops) |
| Vendor count | 2 (URIP + CloudSEK) | 1 (URIP only) |
| External threat depth | Full (CloudSEK product) | Starts limited, grows over time |
| Customization | Limited | High |
| Data sovereignty | Mixed (some data in CloudSEK cloud) | Full (in URIP / Adverb's cloud) |
| Operational burden on Semantic Gravity | Low | High (24/7) |
| Risk to overall URIP delivery | Low | Medium-High if not staffed properly |
| Strategic value for URIP product | Marginal (aggregator) | Major (platform play) |

### 6.4 Recommended Position to Adverb

> "We can do both — and the right answer depends on what Adverb optimises for. If Adverb wants the deepest external-threat coverage right now and can keep the CloudSEK subscription, Option A gives you unified visibility fast. If Adverb wants to consolidate vendors, control the roadmap, and move external-threat data into URIP's own infra long-term, Option B is the right path — but it is a multi-quarter program and we will be transparent about coverage gaps in early stages."

**Our internal default recommendation: Option A in this engagement, Option B as a follow-on URIP v2 conversation** — because Option B done badly destroys trust, and Adverb's first URIP delivery should be a clean win.

If Adverb explicitly chooses Option B from day one, we will scope it as a separate parallel engagement with its own team, budget, and milestone definitions.

### 6.5 What we will commit to in this engagement

- ✅ **Option A — CloudSEK API connector** is included in Phase 2 by default
- ⚪ **Option B — CloudSEK-equivalent native features** is available as a separate engagement; not included by default
- Decision deferred to client review meeting (Next Steps, Section 11)

---

## 7. Compliance & Audit-Readiness Module (Sprinto-equivalent)

### 7.1 Why this module exists

Adverb (and most SaaS / regulated clients) face audits regularly — SOC 2 Type 1/2, ISO 27001, GDPR, HIPAA, PCI DSS, India DPDP, depending on their customer base. Today the audit-prep cycle is painful: spreadsheets of controls, scrambling for evidence screenshots, chasing employees for policy acknowledgments, manual access reviews three weeks before the auditor arrives.

Sprinto solved this by automating control monitoring, evidence collection, policy management, and auditor collaboration. We need the same layer inside URIP so that **any tenant is audit-ready before the audit lands**, not scrambling 30 days before.

The strategic value: URIP without this layer is a "vulnerability dashboard". URIP with this layer is a **compliance + risk + audit platform** — which is what enterprise buyers actually budget for.

### 7.2 What Sprinto Provides — Capability Map

These are Sprinto's core capabilities. Each will be evaluated against URIP's current state and a build path defined.

| # | Sprinto Capability | What It Does |
|---|---|---|
| S1 | **Continuous Control Monitoring** | Auto-checks ~200+ controls across cloud (AWS/GCP/Azure), HRMS, code repos, identity providers. Flags failing controls in real-time. |
| S2 | **Multi-Framework Coverage** | Pre-mapped controls for SOC 2 (Type 1 + 2), ISO 27001, ISO 27017, ISO 27018, ISO 27701, GDPR, HIPAA, PCI DSS, CCPA, NIST CSF, CIS, FedRAMP, CSA STAR. One control can satisfy multiple frameworks. |
| S3 | **Evidence Automation** | Auto-collects screenshots, configs, logs, ticket exports as audit evidence. Tagged to control + framework + audit period. |
| S4 | **Policy Management** | Pre-built policy templates (Information Security Policy, Acceptable Use, BCP, etc.). Version control. Employee acknowledgment tracking. |
| S5 | **Employee Security Awareness** | Onboarding training modules. Annual refresher. Phishing simulation. Pass/fail tracking. |
| S6 | **Background Verification** | Integrations with BGV providers (e.g., AuthBridge, OnGrid). Tracks employee BGV completion as a control. |
| S7 | **Access Reviews** | Quarterly / annual user access reviews. Sends reviewer the user list, captures approve/revoke decisions, generates audit trail. |
| S8 | **Risk Register** | Risk identification, owner assignment, treatment plan, residual risk, periodic review. |
| S9 | **Vendor / Third-Party Risk** | Vendor inventory, risk questionnaire, due diligence tracking, contract expiry alerts, criticality classification. |
| S10 | **Incident Management** | Security incident logging, classification, response workflow, RCA, lessons learned. |
| S11 | **Asset Inventory** | Auto-discovered + manually-added asset list with owner, classification, location. |
| S12 | **Auditor Collaboration Portal** | Read-only auditor login. Auditor sees controls, evidence, policies, can request additional evidence via the portal. |
| S13 | **Real-Time Compliance Score** | Per-framework percentage compliance with drill-down to failing controls. |
| S14 | **Continuous Compliance Reporting** | Scheduled compliance reports for management, board, customer security questionnaires. |

### 7.3 Current URIP State vs Sprinto Capabilities — Honest Map

| # | Sprinto Capability | URIP State Today | Gap |
|---|---|---|---|
| S1 | Continuous Control Monitoring | 🔴 TO BUILD — URIP monitors *vulnerabilities*, not *controls* | Need control engine that runs scheduled checks against configured rules |
| S2 | Multi-Framework Coverage | 🔴 TO BUILD — no framework data model exists | Need `frameworks`, `controls`, `framework_control_mapping` tables (covered in Phase 1 item 1.11) |
| S3 | Evidence Automation | 🔴 TO BUILD | Need `control_evidence` table, evidence storage (S3-compatible), connectors that capture evidence per scheduled control check |
| S4 | Policy Management | 🔴 TO BUILD | Need `policies` (versioned), `policy_acknowledgments`, policy template library, e-sign workflow |
| S5 | Employee Security Awareness | 🔴 TO BUILD | Either build training module OR integrate with existing LMS (KnowBe4, Hoxhunt, etc.) — **recommendation: integrate, do not build** |
| S6 | Background Verification | 🔴 TO BUILD — connector only | Integration with AuthBridge / OnGrid API to pull BGV status — no need to do BGV ourselves |
| S7 | Access Reviews | 🔴 TO BUILD | Pull user list from MS Entra (already in Phase 2 connectors), build review workflow + reviewer notification + decision capture |
| S8 | Risk Register | ✅ LIVE | URIP already has full risk register. Need to extend with control linkage (which control does this risk threaten?) |
| S9 | Vendor / Third-Party Risk | 🔴 TO BUILD | Need `vendors` table, questionnaire engine, document upload, expiry alerts |
| S10 | Incident Management | 🟡 PARTIAL | URIP `risks` table can carry incidents but lacks dedicated incident lifecycle (detection → triage → containment → eradication → recovery → lessons). Need light extension. |
| S11 | Asset Inventory | 🟡 PARTIAL | URIP has `asset_criticality_service` keyword classification. Real asset inventory (with owner, location, type) needs to be added. |
| S12 | Auditor Portal | 🔴 TO BUILD | Need read-only auditor role + dedicated portal view + evidence request workflow |
| S13 | Real-Time Compliance Score | 🔴 TO BUILD | Once controls + framework mapping exist, score is a derived view. Logic to be built. |
| S14 | Compliance Reporting | 🟡 PARTIAL | URIP has reports module. Needs framework-specific report templates (SOC 2 board pack, ISO 27001 SoA, etc.) |

**Bottom line:** 9 of 14 Sprinto capabilities are net-new build, 3 are partial extensions of existing URIP modules, 1 is already live (risk register), and 1 (training) we explicitly recommend NOT building — integrate with an existing LMS instead.

### 7.4 Phase 2 — Compliance Module Build Scope

The Compliance Module ships in Phase 2 alongside the live connectors. It is **not** a Phase 3 — both go in parallel because they share the same underlying refactor (multi-tenant, connector framework) done in Phase 1.

| # | Build Item | Description | Status |
|---|---|---|---|
| C1 | Framework + Control data model | Tables, seeders for SOC 2, ISO 27001, GDPR, HIPAA, PCI DSS, India DPDP. Cross-framework control mapping. | 🔴 TO BUILD |
| C2 | Control rule engine | Plugin architecture so each control has a check function. Scheduled execution. Pass/fail/inconclusive states. | 🔴 TO BUILD |
| C3 | Evidence collection layer | Connectors capture evidence on each control run (screenshots, configs, exports). Tagged + indexed + searchable. Object storage backed. | 🔴 TO BUILD |
| C4 | Policy management module | Policy library, version control, e-sign acknowledgment, reminder workflow, expiry alerts. | 🔴 TO BUILD |
| C5 | Access review module | Pulls user-role data from MS Entra / Okta. Assigns reviewers. Captures decisions. Generates auditor-ready report. | 🔴 TO BUILD |
| C6 | Vendor risk module | Vendor inventory, questionnaire builder, response capture, contract + DPA tracking, expiry alerts. | 🔴 TO BUILD |
| C7 | Incident lifecycle extension | Extend existing risks table with incident-specific fields: detection time, containment time, RCA, lessons. | 🔴 TO BUILD |
| C8 | Asset inventory module | Manual + auto-discovered asset register. Owner, classification, location, lifecycle state. Imports from Endpoint Central / Entra / cloud APIs. | 🔴 TO BUILD |
| C9 | Auditor portal | Separate read-only login. Filtered views by framework + audit period. Auditor evidence request workflow. Activity audit trail. | 🔴 TO BUILD |
| C10 | Compliance scoring engine | Per-framework % compliance based on control pass/fail. Trend over time. Drill-down to failing controls. | 🔴 TO BUILD |
| C11 | Framework-specific report templates | SOC 2 management report, ISO 27001 SoA, HIPAA risk analysis, GDPR Article 30 register, PCI DSS AOC inputs. | 🔴 TO BUILD |
| C12 | LMS integration (recommended over building) | Connector to KnowBe4 / Hoxhunt / similar to pull training completion. Avoids us building a training platform. | 🔴 TO BUILD |
| C13 | BGV integration | AuthBridge / OnGrid API connector to pull employee BGV status. | 🔴 TO BUILD |
| C14 | Risk → Control linkage | Extend URIP's existing risk records to optionally link to one or more controls they threaten. Failing controls surface as "open risks" automatically. | 🟡 EXTEND existing |

### 7.5 How URIP's Existing Strength Becomes a Compliance Force-Multiplier

This is the key sales narrative — Sprinto cannot do this, URIP can:

- **EPSS + KEV + MITRE enrichment + control linkage** = when a CVE lands in URIP, we already know its exploitation probability and APT attribution. If that CVE breaks SOC 2 control CC7.1 (System Operations — Detection of Vulnerabilities), it auto-creates a control failure with full threat context. Sprinto's control failures are binary (pass/fail). Ours come pre-prioritised.

- **11-source connector mesh** = Sprinto's evidence layer pulls from ~30-50 integrations. URIP's connector framework (Phase 1, item 1.6) hosts unlimited tool integrations. Same connector that ingests SentinelOne threats also captures SentinelOne evidence for the SOC 2 endpoint protection control.

- **Audit log already immutable** = URIP's `audit_log.py` is already the foundation auditors care about. Sprinto charges for this; we already have it.

The pitch to a buyer: *"Sprinto tells you you're audit-ready. URIP tells you you're audit-ready AND shows you which CVE is about to break it."*

### 7.6 Decision — We Are Building This Natively

URIP will build the Compliance & Audit-Readiness Module natively (items C1–C14 in Section 7.4). We are **not** integrating with Sprinto. This is a definitive scope decision, not an open option.

The out-of-scope items in Section 7.8 (training content, BGV execution, pen testing, legal advice, auditor services) remain out of scope.

### 7.7 Module Subscription — Compliance Module

Compliance becomes a **single new module** in URIP's catalog:

> **Compliance & Audit-Readiness Module** — framework mapping, control monitoring, evidence automation, policy management, access reviews, vendor risk, incident lifecycle, asset inventory, auditor portal, compliance scoring, framework-specific reports.

Tenants who only want vulnerability management subscribe to Core + their tool modules. Tenants who want audit-readiness add the Compliance Module on top.

### 7.8 Out of Scope (Honest Limits)

Even the full Compliance Module will explicitly NOT include:

- **Training content authoring** — we integrate with KnowBe4 / Hoxhunt / Cybeready, we do not build training videos
- **Background verification execution** — we integrate with AuthBridge / OnGrid, we do not run BGV
- **Penetration testing services** — we ingest pen test reports, we do not perform pen tests
- **Legal review of policies** — we provide templates, not legal advice
- **Auditor services** — we make audit-readiness easy, we are not the auditor

---

## 8. Modularization Strategy — "Pick What You Need"

The user requirement: *make URIP modular so any company picks the modules they need.*

### 8.1 Module Catalog (Phase 1 design output)

URIP will be sold as **9 capability modules** plus a mandatory core:

| Module | Includes | Suitable For |
|---|---|---|
| **Core** (mandatory) | Risk register, scoring engine (EPSS + KEV + MITRE), dashboard, workflow, audit, reports | Every tenant |
| **VM Module** | Tenable / Qualys / Rapid7 / CrowdStrike Spotlight connectors | Anyone running vulnerability scanners |
| **EDR Module** | SentinelOne / CrowdStrike Falcon / Defender for Endpoint connectors | Anyone with endpoint security |
| **Network Module** | Zscaler / Netskope / Palo Alto / Fortigate connectors | Cloud-first or perimeter-heavy orgs |
| **Identity Module** | MS Entra / Okta / Google Workspace connectors | Anyone with SSO |
| **Collaboration Module** | SharePoint / OneDrive / Teams / Slack / Confluence connectors | Knowledge-work orgs |
| **ITSM Module** | ServiceNow / Jira / ManageEngine SDP connectors | Anyone with formal ticketing |
| **DAST Module** | Burpsuite / OWASP ZAP / Acunetix connectors | App-heavy orgs |
| **DLP Module** | GTB / Forcepoint / Symantec DLP connectors | Compliance-driven orgs |
| **Compliance & Audit-Readiness Module** | Framework mapping (SOC 2, ISO 27001, GDPR, HIPAA, PCI DSS, India DPDP), control monitoring, evidence automation, policy mgmt, access reviews, vendor risk, incident lifecycle, asset inventory, auditor portal, compliance scoring (Section 7) | Anyone facing audits or selling to enterprise customers |

Each module has its own price point. Adverb subscribes to the modules covering their 11 tools + Compliance. Future clients pick differently.

### 8.2 Adverb's Module Selection

Based on Adverb's 8-tool list:

| Adverb needs | Modules required |
|---|---|
| Zscaler + Netskope | Network Module |
| SentinelOne | EDR Module |
| MS Entra + SharePoint/OneDrive/Teams | Identity Module + Collaboration Module |
| ManageEngine SDP + Endpoint Central + MDM | ITSM Module + (Endpoint Central / MDM go in EDR Module) |
| Tenable | VM Module |
| Burpsuite | DAST Module |
| GTB | DLP Module |
| CloudSEK alerts | Bundled in Network Module or sold as add-on |
| Audit-readiness (SOC 2 / ISO 27001 / etc.) | Compliance & Audit-Readiness Module |

**Adverb subscribes to:** Core + 8 of 9 modules (everything except DAST is dependent on Burp Enterprise license confirmation; Compliance Module is the strategic differentiator).

### 8.3 Why this matters commercially

Future clients will rarely need all 9. A pure SaaS company might want only Identity + Collaboration + DLP + Compliance. A factory might want only VM + Network + ITSM. A regulated startup might start with Core + Compliance only. The modular pricing tier lets us close those deals without forcing them to pay for what they will not use.

The **Compliance Module** is the most strategically important — it is the difference between selling a "vulnerability dashboard" (low-budget line item) and selling a "compliance + risk platform" (board-level budget line).

---

## 9. Risks We Must Document in SoW

| Risk | Mitigation |
|---|---|
| Adverb credentials delayed → Phase 2 work cannot proceed | SoW scope clock starts when creds arrive, not at signing |
| Burp Enterprise not licensed → Burp connector cannot be built | Confirm Burp Enterprise vs Pro before SoW signing |
| CloudSEK Interpretation B insisted on by Adverb | Document Interpretation A only in SoW; B is a separate engagement |
| MS Entra admin consent not granted | Identity + Collaboration modules cannot ship without this; flag as Adverb dependency |
| Scope creep ("can you also add X tool?") | New tool requests trigger change-order process, not silent absorption |
| Adverb expects Compliance Module to also include training content / BGV execution / pen testing | Section 7.8 explicitly out-of-scope; restate at SoW signing |
| Framework versioning (e.g., SOC 2 2017 → 2022 trust services criteria) | Build framework data model with version field; commit to following framework updates as part of subscription |
| Auditor portal access disputes (auditor wants more than read-only) | Define scope of auditor portal in SoW: read-only access to controls, evidence, policies; no edit rights |

---

## 10. Honest Limitations We Must Tell Adverb

Before signing, Adverb must understand:

1. **URIP is a unifier, not a scanner.** It does not discover assets or run its own vulnerability scans. It depends on Adverb's existing tools to do the discovery; URIP organizes and prioritizes what those tools find.

2. **Quality of URIP output depends on quality of input.** If Adverb's Tenable scans are stale or missing assets, URIP will reflect that gap. URIP cannot fix poor source-tool hygiene.

3. **Polling-based, not literal real-time.** Connectors poll on a schedule. Webhook-based push is possible for some tools (SentinelOne, Burp) but adds infra complexity.

4. **CloudSEK feature replication is not in scope.** Re-stating from Section 6: we integrate with CloudSEK as a data source, we do not rebuild CloudSEK.

5. **Phase 1 dashboard shows simulated data.** Until Phase 2 connectors land, Adverb's dashboard is populated with realistic-but-synthetic data so they can see the workflow and UX. This will be clearly labeled. Real data starts flowing as each connector goes live in Phase 2.

6. **We are not a SOC.** URIP does not respond to incidents. It surfaces and prioritizes them. Adverb's security team or SOC vendor still owns response.

7. **Compliance Module makes audit-readiness easy, not automatic.** URIP automates evidence collection, control monitoring, policy tracking, and reporting. Adverb still owns: control design decisions, policy approvals, employee acknowledgments, vendor selection, and the actual audit engagement with the auditor. URIP shortens the prep cycle from weeks to days; it does not eliminate Adverb's accountability.

8. **Compliance Module is not legal advice.** Framework templates and policies are starting points. Adverb's legal / compliance counsel must review and tailor them for their jurisdiction and customer contracts.

---

## 11. Next Steps

| # | Action | Owner |
|---|---|---|
| 1 | Internal review of this blueprint | Semantic Gravity team |
| 2 | Pricing model alignment (Phase 1 setup, Phase 2 per-connector + Compliance Module, ongoing subscription) | CMO |
| 3 | Adverb client review meeting + walkthrough | Semantic Gravity + Adverb |
| 4 | Resolve CloudSEK Option A (integrate via API) vs Option B (build native) | Adverb |
| 5 | Confirm Burp Enterprise license status | Adverb |
| 6 | Confirm which compliance frameworks Adverb is targeting (SOC 2 / ISO 27001 / GDPR / India DPDP / etc.) — drives priority of framework data seeding | Adverb |
| 7 | Issue SoW with locked scope, pricing, and timeline | Semantic Gravity |
| 8 | Phase 1 kickoff | Engineering |

---

## Appendix A — Comparison: Royal Enfield Engagement vs Adverb Engagement

For internal reference only. Helps the team understand how the two engagements differ.

| Dimension | Royal Enfield | Adverb |
|---|---|---|
| Engagement model | One-time platform delivery + support | SaaS subscription + per-module |
| Tools to integrate | 14 (CrowdStrike, Armis, Forescout, Cisco ISE, CyberArk, Zscaler, Fortiguard, Google Workspace, etc.) | 11 (Zscaler, Netskope, Sentinel, Entra, SP/OD/Teams, ManageEngine x3, Tenable, Burp, GTB) + CloudSEK |
| Tenancy | Single-tenant, hardcoded for RE | Multi-tenant, module-pickable |
| Industry tuning | Two-wheeler manufacturing | TBD per Adverb's stated industry |
| Asset taxonomy | Hardcoded RE keyword list | Tenant-configurable |
| External threat layer | EPSS + KEV + MITRE + OTX | Same + optional CloudSEK API connector |
| Dashboard branding | RE colors + logo | Adverb colors + logo |
| Compliance / Audit-Readiness | Not in scope | **Compliance Module included** — framework mapping, control monitoring, evidence automation, policy mgmt, access reviews, vendor risk, auditor portal |

---

## Appendix B — File / Code Reference

For internal Phase 1 planning, the files most affected by the productization work:

- **Multi-tenancy refactor:** `backend/models/*.py`, every router file
- **Connector framework:** New `backend/connectors/` package, refactor `backend/simulator.py`
- **Asset taxonomy:** `backend/services/asset_criticality_service.py`, `backend/config/tier_keywords.json`
- **Module subscription:** New `backend/models/subscription.py`, new `backend/routers/tenants.py`
- **Frontend theming:** Frontend theming layer (location depends on `urip-template/` structure)
- **RBAC scoping:** `backend/middleware/auth.py`

For Compliance Module (Phase 2):

- **Compliance schema:** New `backend/models/compliance.py` (frameworks, controls, control_evidence, policies, policy_acknowledgments, access_reviews, vendors, incidents, assets)
- **Control rule engine:** New `backend/services/control_engine.py`, scheduled execution via existing job runner
- **Evidence storage:** New `backend/services/evidence_service.py`, S3-compatible object storage
- **Policy management:** New `backend/routers/policies.py`, e-sign workflow
- **Access reviews:** New `backend/routers/access_reviews.py`, depends on Identity Module connectors
- **Vendor risk:** New `backend/routers/vendors.py`, questionnaire engine
- **Auditor portal:** New auditor role in `backend/middleware/auth.py`, dedicated read-only frontend route
- **Compliance scoring:** Extension of `backend/services/exploitability_service.py` patterns to control pass/fail aggregation
- **Framework seeders:** New `backend/seed_compliance.py` for SOC 2, ISO 27001, GDPR, HIPAA, PCI DSS, India DPDP control libraries

---

**End of document.**
