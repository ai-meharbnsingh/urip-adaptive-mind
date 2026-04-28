# URIP-Adverb Master Vision Document (Codex perspective)

## 1. The Client Experience — End-to-End Story

It’s Day 1 at Adverb. A new security lead opens the URIP portal and lands on a clean home screen with two things that matter immediately:

1) **A Tool Catalog** (visual grid)  
2) **A “Get Live in 60 Minutes” onboarding checklist**

### 1.1 Land on the URIP portal

The user signs in (SSO or email/password, tenant-scoped) and is placed inside Adverb’s tenant space: branding, colors, and a tenant-specific URL. The navigation shows two primary destinations:

- **URIP (Risk Intelligence)**
- **Compliance (Audit Readiness)** *(visible only if the Compliance module is licensed/enabled)*

### 1.2 Tool Catalog: pick what Adverb actually owns

The catalog is a **visual grid of connectors** grouped by category (VM, EDR/XDR, CASB/SWG/SASE, IAM, Collaboration, ITSM/UEM/MDM, DAST, DLP, External Threat). Each tile shows:

- Product name + logo
- What URIP will pull (one-line)
- Setup difficulty (Low/Medium/High)
- Data freshness target (e.g., 15-minute pull)
- “Owned / Not owned” toggle (checkbox)

Common tiles for Adverb:

- **Tenable** (VM)
- **SentinelOne** (EDR/XDR)
- **Zscaler** (SWG/SASE/CASB)
- **Netskope** (CASB/DLP)
- **Microsoft Entra ID** (IAM)
- **SharePoint / OneDrive / Teams** (Collaboration)
- **ManageEngine** (ServiceDesk Plus / Endpoint Central / MDM)
- **Burp** (DAST)
- **GTB Endpoint Protector** (DLP)
- **CloudSEK** (External Threat Monitoring)

The user simply checks the tools they actually have. URIP immediately converts this into a **tenant integration plan**: which connector modules to enable, which scopes are needed, which evidence can be auto-collected for compliance, and what the first dashboards will look like once live.

### 1.3 Guided connector setup: endpoint + credentials per tool

For each selected tool, URIP opens a guided form with:

- **API base URL / region** (where applicable)
- **Auth type** (API key, OAuth2 client, token, etc.)
- **Credential fields** (with in-form examples)
- **Required permissions/scopes checklist** (with copy-paste snippets)
- **Data preview** (“what will we ingest?”)
- **Test Connection** button

The flow is intentionally opinionated:

- Each tool shows **Configured / Not Set** at a glance (no half-finished integrations).
- Credentials are stored **encrypted in a tenant vault**, and connector actions are **audited** (who configured/tested/changed).

### 1.4 Real-time validation: “Test Connection”

When the user clicks **Test Connection**, URIP performs a handshake:

- Auth validation (key/token works)
- Permission validation (scopes allow the needed endpoints)
- Basic data pull (a minimal “sample” fetch)
- Rate-limit detection (warn if limits are too low for 15-minute freshness)

The result is shown instantly with an actionable message:

- **Connected**: ready for ingestion
- **Connected but insufficient permissions**: list missing scopes
- **Failed**: clear error (bad secret, wrong URL, allowlist needed, tenant consent missing)

### 1.5 Automatic ingestion begins (15-minute poll cycle)

Once a connector is configured and enabled, URIP starts pulling data automatically on a **15-minute poll cycle** (with per-connector overrides where needed). The user does not schedule jobs or manage cron—URIP does.

In Hybrid-SaaS:

- The **on-prem agent** executes connector pulls inside the client network.
- The agent stores **raw records locally** in its local database.
- The agent sends **encrypted, signed metadata summaries** to the cloud portal (counts, severities, deltas, health)—not raw sensitive payloads.

### 1.6 Within minutes: URIP dashboard populates with real findings

Within the first ingestion cycles, the URIP dashboard goes from empty to actionable:

- KPI cards show **total open risks**, severity breakdown, and **actively exploited** items.
- The risk register fills with normalized findings (source-labeled, deduplicated where possible).
- Each risk is enriched with real-world context: **EPSS**, **Known Exploited Vulnerabilities (KEV)**, **MITRE ATT&CK** mapping, and threat intel references.

The user can immediately:

- Filter to **Critical + Exploit-active** to get a “what can burn us this week” list.
- Assign owners, set SLA expectations, and open remediation tasks.
- Track connector health (last sync, error rate, drift warnings).

### 1.7 Within an hour: Compliance dashboard becomes meaningful

Compliance is not a separate universe. It’s a second lens on the same operational reality.

As soon as risks and configuration signals begin flowing, the Compliance service evaluates framework controls. Within an hour of onboarding:

- The compliance dashboard shows per-framework scores (SOC 2 / ISO 27001 / DPDP, etc.).
- “Failing controls” are not abstract: each failing control can **trace back to concrete underlying evidence gaps or risks** (e.g., missing MFA enforcement, unmanaged endpoints, unpatched KEV CVEs, uncontrolled external sharing).
- Evidence collection starts automatically where possible (configuration snapshots, system exports, tickets, acknowledgments).

The user experiences the platform as one product: **operational security and audit readiness converge**, with minimal manual effort.

---

## 2. Architecture — Hybrid-SaaS (per `DELIVERY_ARCHITECTURE.md`)

URIP-Adverb is designed as **Hybrid-SaaS by default**: a cloud portal for experience and intelligence, and an on-prem agent for data sovereignty.

### 2.1 The split: cloud portal vs on-prem agent

**Cloud portal (Semantic Gravity cloud)**

- UI (URIP + Compliance dashboards)
- Tenant + licensing + RBAC
- Intelligence engine (EPSS/KEV/MITRE/threat enrichment)
- Normalization contracts + schema evolution
- Aggregated metadata store (counts, scores, health, trends)
- Auditor portal (read-only, time-bound access)

**On-prem agent (Adverb network)**

- Connector runtime (all third-party tool integrations)
- Scheduler (15-minute default cycles)
- Local database holding **raw findings + raw evidence**
- Credential vault (encrypted at rest, decrypt only in-memory during runtime)
- Secure reporter to cloud (signed/encrypted payloads)

### 2.2 Secure drill-down tunnel for live raw-data fetch

Hybrid-SaaS must still support investigation. When an analyst clicks “View raw event,” the cloud requests a specific record ID and the agent returns a time-limited, tenant-scoped response that the UI renders without permanently storing the raw payload.

### 2.3 Why this is industry-standard

The model is proven in security software because it solves the real procurement objection: *“Don’t export my sensitive telemetry to your cloud.”*

- **CrowdStrike**: sensor runs on endpoints, cloud does analytics
- **Tenable**: agents/scanners run in client environments, cloud aggregates
- **Splunk**: forwarder runs on-prem, central search/indexing

---

## 3. Two Dashboards — Distinct But Linked

The platform has **two primary dashboards** with different buyers and different rhythms:

- **URIP Dashboard** (CISO + SecOps + Infra owners) — hourly/daily operational risk
- **Compliance Dashboard** (Compliance lead + IT owners + auditors) — weekly/monthly audit readiness

They are separate because they answer different questions, but linked because they share the same reality: systems, risks, evidence, and remediation.

### 3a. URIP Dashboard (Risk Intelligence)

**What it answers:** “What can hurt us, how bad is it, and are we fixing it fast enough?”

Core experience:

- **Top KPIs**
  - Total open risks
  - Critical count
  - Mean time to remediate (MTTR)
  - Exploit-active risks (KEV / threat intel flagged)
- **Risk register**
  - Fast filtering and sorting (severity, asset tier, source tool, owner team, status)
  - Drill-down to a single risk: description, upstream source, evidence, related assets, related tickets
  - Workflow actions: accept risk (with justification), assign owner, set SLA, mark remediated
- **Threat intel panel**
  - EPSS probability and trend
  - KEV alerts and prioritization
  - MITRE technique mapping / APT-style attribution when relevant
  - Optional external intel streams (e.g., OTX indicators) for context
- **Connector health status**
  - Which feeds are live, last successful pull, error counts, degraded vs healthy
  - Drift warnings (API schema changes, scope changes, rate-limit constraints)

URIP’s defining principle: **a risk is not “just a CVE.”** It is a prioritized, owner-assigned, SLA-tracked work item with exploitability context and an audit trail.

### 3b. Compliance Dashboard (Sprinto-equivalent)

**What it answers:** “If the audit was next week, would we pass—and what must we do before then?”

Core experience:

- **Per-framework compliance score**
  - SOC 2, ISO 27001, GDPR (where applicable), PCI DSS (if applicable), India DPDP, etc.
  - Score explained by pass/fail/inconclusive control counts, not just a vanity number
  - Example tenant view: **SOC 2 87%**, **ISO 27001 92%**, **India DPDP 78%** (illustrative; derived from control outcomes)
- **Failing controls list with drill-down**
  - Each failing control shows: why it failed, what evidence is missing, and who owns the fix
  - Links to the exact underlying operational signal: a URIP risk, a configuration mismatch, or a missing policy acknowledgment
- **Evidence collection status**
  - Auto-captured evidence (system snapshots, logs, exports)
  - Manual uploads (with audit logging, retention policy, and review workflow)
  - Evidence “freshness” (e.g., “needs re-capture this quarter”)
- **Policy acknowledgment status**
  - Which policies are active, expiring, and awaiting signature
  - Which employees have not acknowledged (with reminders/escalation)
- **Vendor risk**
  - Vendor inventory, criticality
  - Questionnaire workflow + document expiry tracking
  - Vendor risk score and reasons
- **Auditor portal**
  - Time-bound, read-only access scoped to frameworks and evidence sets
  - Everything is logged: what the auditor viewed, when, and for how long
- **“Action items before next audit”**
  - A prioritized punch list generated from failing controls, missing evidence, expiring policies, and vendor gaps

The Compliance dashboard is not a “compliance spreadsheet in a UI.” It is an **automation engine** that keeps evidence, controls, and readiness continuously up-to-date.

---

## 4. The Connector Library

Connectors are the bloodstream of URIP-Adverb. The connector library exists to make integrations **repeatable, testable, and safe**—not bespoke one-offs.

### 4.1 What each connector pulls (and why)

Each connector is defined by three things:

1) **What data it pulls** (findings, alerts, configuration state, audit events)  
2) **What API access is required** (keys/scopes/roles)  
3) **How it normalizes** into URIP’s risk schema (consistent severity, assets, ownership, timestamps)

Example coverage (Adverb’s core stack):

- **Tenable**: assets, vulnerabilities, CVEs/CVSS, exploit references
- **SentinelOne**: active threats, agent health, endpoint posture signals
- **Zscaler / Netskope**: web/cloud violations, risky SaaS, DLP incidents, shadow IT signals
- **Microsoft Entra ID**: risky sign-ins, privileged role assignments, conditional access violations
- **SharePoint/OneDrive/Teams**: external sharing posture, anonymous links, sensitive label violations
- **ManageEngine SDP**: ticket creation + status synchronization (closing the loop)
- **Endpoint Central / MDM**: patch compliance, device compliance state, unmanaged device signals
- **Burp**: web application scan findings (DAST) tied to application assets
- **GTB Endpoint Protector**: DLP events and policy violations
- **CloudSEK**: leaked credentials/brand abuse/external threat signals (integrated as a feed, not re-built)

High-level connector matrix (what we pull + what access is typically required):

| Tool | What URIP pulls | Typical API access required |
|---|---|---|
| Tenable | Vulnerabilities, assets, CVSS/CVE metadata | API key pair (read-only) |
| SentinelOne | Threats, agent health, posture signals | API token (read-only) |
| Zscaler | Web threat events, blocked URLs, shadow IT signals | API key + product-specific access (read-only) |
| Netskope | Cloud app risk, DLP violations, sanctioned/unsanctioned usage | OAuth2 token / API key (read-only) |
| Microsoft Entra ID | Risky sign-ins, MFA/CA signals, privileged role changes | Microsoft Graph OAuth2 + admin consent (read-only) |
| SharePoint/OneDrive/Teams | External sharing posture, link exposure, collaboration audit events | Microsoft Graph OAuth2 + admin consent (read-only) |
| ManageEngine SDP | Tickets: create/update/sync status | OAuth2 (bidirectional) |
| Endpoint Central / MDM | Patch/device compliance, missing updates | OAuth2 (read-only) |
| Burp (Enterprise) | Scan findings per target/app | API key / enterprise API access (read-only) |
| GTB Endpoint Protector | DLP policy events, device/channel violations | API key (read-only) |
| CloudSEK | External alerts (leaks, brand abuse, threat monitoring) | API token (read-only) |

### 4.2 Easy add-new-tool flow

Adding a new tool should feel like adding a new driver, not rearchitecting the car.

The add-new-tool flow is standardized:

- Implement connector contract: `authenticate`, `fetch_findings(since)`, `normalize`, `health_check`
- Provide mapping: source severities → URIP severity, asset identifiers → URIP asset keys
- Provide test harness: canned payloads + permission validation
- Register connector in the catalog with required scopes and UI fields

This creates compounding leverage: every connector after the first few is faster, safer, and more predictable.

### 4.3 Credential management and security

Connector credentials are:

- **Tenant-isolated** (no cross-tenant lookups)
- **Encrypted at rest** (vaulted; decrypt only at runtime in-memory)
- **Rotatable** (support for key rotation with zero downtime where possible)
- **Audited** (who created/updated/tested, when, and what changed)

In Hybrid-SaaS, secrets remain in the on-prem agent vault. The cloud portal never needs to see raw API keys to provide value.

### 4.4 Health monitoring per connector

Every connector exposes health signals:

- Last successful sync time
- Error rate and last error
- Pull latency and rate-limit warnings
- Data drift detection (schema changes, unexpected null fields, permission regressions)

This is essential to uphold the “no manual effort” promise: silent connector failure is the enemy.

---

## 5. Multi-Tenancy + License Modules

URIP-Adverb is built as a multi-tenant platform where each tenant can enable only what they need, and pay only for what they use.

### 5.1 Module selection and gating

Modules are picked per tenant (and can be trialed, upgraded, or disabled). Typical modules:

- Core (auth, tenant context, dashboard shell, audit log)
- VM (Tenable-class connectors)
- EDR/XDR (SentinelOne-class connectors)
- Network/CASB/SASE (Zscaler/Netskope-class connectors)
- Identity & Access (Entra-class connectors)
- Collaboration (SharePoint/Teams-class connectors)
- ITSM/UEM/MDM (ManageEngine-class connectors)
- DAST (Burp-class connectors)
- DLP (GTB-class connectors)
- **Compliance & Audit** (separately licensable)

Gating is enforced in three places:

- UI (hide unavailable modules)
- API (authorize based on tenant subscription)
- Data plane (connectors only run when enabled)

### 5.2 White-label theming per tenant

Every tenant can have:

- Their own logo and brand colors
- Tenant-specific naming (“Adverb Risk Intelligence”)
- Optional subdomain routing

This matters for adoption: teams use tools that feel “owned,” not rented.

### 5.3 RBAC and operational separation

Role-based access is module-aware:

- A DLP analyst can see only DLP risks and evidence
- A compliance lead can see Compliance dashboards but not raw vulnerability payloads
- An auditor gets time-bound read-only portal access scoped to frameworks/evidence

Multi-tenancy is not just “a tenant_id column.” It is enforced as a product principle: **no cross-tenant inference, no cross-tenant leaks, no shared secrets.**

---

## 6. The “No Manual Effort” Promise

URIP-Adverb is built around a single, testable promise:

> Once configured, the platform requires **near-zero manual data entry** to stay valuable.

What “no manual effort” concretely means:

- **Risks come in via connectors**, not spreadsheet imports
- **Controls auto-evaluate** on schedules and on relevant events (new risks, configuration changes, connector syncs)
- **Evidence auto-captures** wherever possible (snapshots, exports, tickets, logs)
- **Reports auto-generate** (per framework and per audit period)
- **Remediation auto-tracks** (ticket sync + SLA tracking)
- **Auditor self-serves** via a scoped portal—no “send me 40 PDFs” email loops

Manual work still exists for edge cases; the goal is to make it the exception, not the operating model.

---

## 7. Sales Pitch — Why Adverb Should Buy

Hybrid-SaaS is the procurement unlock. Adverb’s sensitive telemetry—vulnerabilities, endpoint alerts, identity events, evidence—can remain inside Adverb’s network. The cloud portal receives only signed metadata needed for dashboards and scoring. This sharply reduces the vendor risk footprint and accelerates approvals with enterprise buyers and formal vendor security questionnaires.

URIP-Adverb is a unified pane that collapses what is currently fragmented: a risk aggregator, a compliance tracker, and audit preparation workflows. Instead of switching between vulnerability tools, EDR, CASB, DLP, and a separate Sprinto-like compliance product, Adverb gets one operational truth: risks, controls, evidence, and remediation tied together with an audit trail.

The cost story is simple: one modular license bundle replaces multiple overlapping tools and the hidden labor cost of manual audit prep. Paying separately for a compliance SaaS, an external threat platform, and weeks of internal evidence wrangling is more expensive than a single platform that continuously prepares the audit posture as a byproduct of daily operations.

---

## 8. What Could Go Wrong (Honest)

URIP-Adverb is ambitious. The risks below are real—and the mitigations are designed upfront.

1) **API limitations and licensing surprises**  
   Some products have weak APIs unless the enterprise tier is enabled (e.g., Burp Pro vs Burp Enterprise).  
   *Mitigation:* validate licensing/API capability per connector during onboarding; use “Test Connection” to detect missing endpoints/scopes early; maintain connector capability matrix.

2) **OAuth and admin consent friction (especially Microsoft Graph)**  
   Identity/collaboration connectors often require admin approval and specific scopes that security teams are cautious about granting.  
   *Mitigation:* least-privilege scopes, tenant-guided consent flows, and explicit “why we need this” documentation; support IP allowlisting and conditional access-friendly auth.

3) **Rate limits and data volume (SharePoint/Teams audit signals can be huge)**  
   Polling too aggressively can hit limits; polling too slowly reduces freshness.  
   *Mitigation:* incremental `since` fetch, backoff strategies, per-connector interval tuning, and batching; clear freshness SLAs per connector rather than one-size-fits-all.

4) **Normalization drift and “apples to oranges” risk scoring**  
   Different tools describe severity differently; naïve merging creates false priorities.  
   *Mitigation:* explicit normalization rules, per-tenant weighting, auditability of scoring formula, and continuous validation using sampled raw payloads.

5) **False confidence from “green dashboards”**  
   A connector might be “connected” but silently missing key data due to scope changes or partial permissions.  
   *Mitigation:* connector health checks that validate coverage (not just connectivity), drift detection, and alerting when expected volumes drop unexpectedly.

6) **Hybrid-SaaS tunnel security and data exposure**  
   Drill-down access is powerful—and dangerous if mis-scoped.  
   *Mitigation:* strict tenant-bound authorization, time-limited signed requests, full audit logs, and “raw payload” views that avoid persistent cloud storage.

7) **On-prem agent operations and updates**  
   If the agent is down, ingestion pauses. If updates are painful, connector quality decays.  
   *Mitigation:* health heartbeats, clear runbooks, safe upgrade paths (versioned APIs), and “degraded mode” UX that makes data freshness explicit.

8) **Compliance frameworks are interpreted differently by auditors**  
   Control mappings can never be purely universal; auditors vary.  
   *Mitigation:* make control logic explainable, allow tenant-specific applicability and compensating controls, and keep evidence traceability strong so auditor discussion is faster and less subjective.

9) **Evidence retention, privacy, and audit boundary concerns**  
   Evidence may include sensitive screenshots, exports, or employee identifiers.  
   *Mitigation:* retention policies, encryption, role-based visibility, and in Hybrid-SaaS storing raw evidence locally with cloud-only summaries by default.

10) **“No manual effort” promise breaks on edge systems**  
   Some controls require human sign-off or systems without APIs.  
   *Mitigation:* designed manual fallback workflows that are auditable and minimal; prioritize connectors that deliver the highest automation ROI first.
