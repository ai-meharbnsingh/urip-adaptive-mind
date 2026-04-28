# URIP-Adverb Master Vision Document (Kimi perspective)

> **Premise:** Adverb (Addverb Technologies, Reliance-owned warehouse robotics) runs a security stack of 11+ tools plus CloudSEK. Today they swivel-chair between dashboards, manually correlate findings, and prepare for audits with spreadsheets. URIP-Adverb ends that. This document is what the product looks like when all phases are live.

---

## 1. Client Experience — The First Day

**09:00 AM.** Adverb's CISO receives a tenant invite link. They land on `adverb.urip.io`, branded with their logo and color palette, not Royal Enfield's. The login is SSO-backed via Microsoft Entra.

**09:05 AM.** The landing page is the **Tool Catalog** — a visual grid of every security and IT tool URIP can ingest from:
- Tenable Vulnerability Manager
- SentinelOne (Singularity)
- Zscaler (ZIA / ZTA / CASB)
- Netskope
- Microsoft Entra ID
- SharePoint / OneDrive / Teams
- ManageEngine Service Desk Plus
- ManageEngine Endpoint Central
- ManageEngine MDM
- Burpsuite Professional / Enterprise
- GTB Endpoint Protector
- CloudSEK

The CISO checks the boxes for the tools Adverb actually owns. The UI adapts instantly — only checked tools show up in the admin navigation.

**09:10 AM.** Per tool, a guided credential form appears. Not a generic "paste your API key" dump — field-by-field guidance: "Zscaler requires API Key + Partner Key + Cloud Name." "SentinelOne needs Singularity API Token + Site ID." "MS Entra requires App Registration with `User.Read.All` and `AuditLog.Read.All` permissions." Every field has inline help and a link to the vendor's own API docs.

**09:12 AM.** The CISO clicks **Test Connection** on Tenable. URIP agent (already running inside Adverb's network as a Docker container) attempts the Tenable.io API, validates read-only scope, and returns a green checkmark with a preview: "Connected. Found 2,847 assets. Last scan: 6 hours ago." If the key is wrong or the IP is not allowlisted, the error is specific: "HTTP 403 from Tenable — verify your API key has Scanner Role."

**09:20 AM.** All credentials are saved. They are encrypted at rest with Fernet inside the local agent's vault. The cloud portal never sees the raw keys.

**09:25 AM.** The CISO enables the **Compliance Module**. A framework picker appears: SOC 2 (2017 / 2022 Trust Services Criteria), ISO 27001:2022, GDPR, HIPAA, PCI DSS v4.0, India DPDP Act 2023, NIST CSF 2.0. They select SOC 2 and ISO 27001 for now. Pre-mapped control libraries load instantly — ~200 controls across both frameworks, already cross-mapped so one control can satisfy multiple frameworks.

**09:30 AM.** Auto-pull cycles begin. Every connector runs on a 15-minute cadence by default. The agent pulls raw findings from each tool, normalizes them into the URIP universal risk schema, writes the full records to Adverb's **local Postgres** (never leaves their network), and sends only aggregate metadata to the cloud:
- "Tenable: 42 critical CVEs, 187 highs, EPSS>0.5 on 12"
- "SentinelOne: 3 active threats, 2 agents offline"
- "Zscaler: 89 blocked malicious URLs, 3 shadow SaaS apps"

**09:35 AM.** The **URIP Dashboard** is already alive. Top-level KPIs: Overall Risk Score (composite of EPSS + KEV + MITRE ATT&CK + asset criticality), Critical Count, Mean Time to Remediate, Connector Health. A threat intel panel shows that 3 of Adverb's CVEs are on the CISA KEV catalog and 1 has an associated APT group from MITRE. A source-wise breakdown bar chart shows Tenable contributing the most volume, SentinelOne the highest severity.

**10:00 AM.** The CISO drills into a SentinelOne alert: "MFA fatigue attack on admin@adverb.in." The detail pane shows the URIP enrichment layer has done its work — EPSS is irrelevant here, but the Identity Module has applied the asset criticality multiplier: the account has privileged role assignments in Entra, and the target asset is classified Tier-1 (Financial Systems). Severity: Critical 9.2. SLA: 4 hours. Auto-assigned to IAM team lead. A ManageEngine SDP ticket was already created by the workflow engine.

**10:30 AM.** The **Compliance Dashboard** starts populating. Framework scores appear: SOC 2 at 74% (initial baseline), ISO 27001 at 68%. Failing controls are listed with root-cause linkage — "CC7.1 System Operations — Vulnerability Detection" is failing because URIP found 42 critical CVEs. The evidence column shows "Auto-collecting…" because the evidence automation layer is pulling Tenable scan exports and screenshots. Policy acknowledgments show 34% of employees have signed the Information Security Policy; reminder emails are queued. Vendor risk cards show 12 vendors onboarded, 3 with expiring SOC 2 reports. An action items list is auto-generated: 8 items, ranked by compliance impact.

**10:45 AM.** By the end of hour one, Adverb has a unified risk view, a compliance baseline, auto-prioritized findings, and a ticket creation loop running — all without a single spreadsheet, email thread, or manual screenshot.

---

## 2. Architecture — Hybrid-SaaS

URIP-Adverb does not force Adverb to choose between "your data in our cloud" and "run everything yourself." It uses the **Hybrid-SaaS** model proven by CrowdStrike Falcon, Tenable Nessus Agent, and Splunk Forwarder.

### Split of Responsibility

| Layer | Location | What It Is |
|---|---|---|
| **Cloud Portal** (Semantic Gravity) | Our infrastructure (Vercel + Railway/Render + Neon) | UI shell, master intelligence engine (EPSS/KEV/MITRE/OTX), compliance scoring logic, tenant/license registry, auditor portal |
| **Docker Agent** | Adverb's network | API connectors, normalizer, local Postgres, encrypted reporter, drill-down responder |
| **Sensitive Data** | Adverb's network **only** | IP addresses, hostnames, usernames, vulnerability details, compliance evidence files, audit logs, vendor documents |

### How Data Flows

1. **Agent pulls** — The Docker agent connects to Tenable, SentinelOne, Zscaler, etc. using credentials stored in its local encrypted vault.
2. **Agent normalizes** — Raw findings are mapped to the URIP universal schema.
3. **Agent stores locally** — Full records go into Adverb's Postgres. This database never leaves their network.
4. **Agent reports up** — Only summary metadata (counts, scores, compliance percentages) is sent to the cloud portal over signed HTTPS.
5. **Cloud enriches** — The cloud layers on EPSS exploit probability, CISA KEV status, MITRE APT attribution, and OTX IOC context.
6. **Cloud renders** — The dashboard displays enriched, prioritized intelligence.

### Drill-Down Tunnel

When a user clicks "View raw finding" on a CVE, the cloud does not have the raw data. Instead, it signs an ephemeral request and sends it down to the agent over a reverse WebSocket tunnel. The agent fulfills the request from its local DB, streams the raw record to the user's browser session, and the data is never persisted in the cloud. If the agent is offline, drill-down shows "Agent unreachable — data available when agent reconnects."

### Why This Model Wins Deals

Regulated buyers (PepsiCo, J&J, Reliance procurement) ask: *"Does your vendor store our sensitive infrastructure data in their cloud?"* With Hybrid-SaaS the answer is **no**. If our cloud is breached, the attacker finds only numbers — "8.2 risk score, 15 criticals" — which reveal nothing about Adverb's network topology, assets, or identities. Adverb's CISO stays in control. Their audit boundary stays clean.

---

## 3. Two Dashboards

### URIP Dashboard — The CISO View

This is the unified risk intelligence pane.

- **Risk Score KPI** — Composite 0–10 score derived from EPSS + KEV + MITRE + asset criticality + exposure. Trended over time.
- **Source Breakdown** — Live counts per connector: Tenable CVEs, SentinelOne threats, Zscaler blocks, Entra risky sign-ins, etc.
- **Threat Intel Panel** — For any selected finding, shows: EPSS probability, KEV yes/no, MITRE APT groups exploiting this CVE, related OTX IOCs. This is real, live enrichment from FIRST.org, CISA, and MITRE — not marketing content.
- **Risk Register** — Full table of all open risks with severity, owner, SLA timer, status. Filterable by source, severity, asset tier.
- **Connector Health** — Grid of all 12 connectors showing last successful pull, next scheduled pull, error count, and latency. Red/yellow/green status per connector. If a connector fails 3 pulls in a row, an alert fires.
- **Remediation Tracking** — Risks linked to ManageEngine SDP tickets with bidirectional sync. Ticket status updates in SDP reflect in URIP automatically.
- **Audit Log** — Immutable record of every state change. Who accepted a risk. Who changed a scoring weight. Who exported a report.

### Compliance Dashboard — The Sprinto-Equivalent

This is the audit-readiness and governance pane. It is a separate FastAPI service (port 8001) with its own database, integrated seamlessly into the URIP UI shell.

- **Per-Framework Score** — Big percentage rings for each enabled framework (SOC 2, ISO 27001, etc.). Drill down to category scores, then individual controls.
- **Failing Controls** — List of controls in `fail` state, sorted by compliance impact. Each failure links to root-cause risks from URIP (unique capability — Sprinto cannot do this). A failing CC7.1 control shows the 42 Tenable CVEs that caused it.
- **Evidence Status** — Per control, shows whether evidence is collected, missing, or stale. Evidence types: screenshot, config export, log snippet, ticket reference. Auto-collected where possible; manual upload where needed.
- **Policy Acknowledgments** — Which policies are published, which versions are current, who has signed, who is pending, reminder queues.
- **Vendor Scores** — Third-party vendor risk ratings derived from questionnaire responses, document expiry status (SOC 2, ISO cert, DPA), and criticality classification.
- **Auditor Portal Entry** — One-click invite to external auditors. Auditor gets a read-only, time-bound login scoped to specific frameworks and audit periods. They can browse controls, view evidence, and request additional files via a built-in workflow. They cannot edit, export bulk data, or see other tenants.
- **Action Items List** — Auto-generated priority queue: "Review 6 failed controls this week," "Renew vendor ABC's DPA (expires in 14 days)," "Complete Q2 access review," "23 employees have not acknowledged Acceptable Use Policy."
- **Access Reviews** — Quarterly / annual user access review campaigns. Pulls current user-role assignments from MS Entra. Assigns reviewers. Captures keep/revoke decisions. Generates auditor-ready report.

---

## 4. Connector Library

URIP-Adverb ships 12 connectors following a uniform plugin architecture (`authenticate`, `fetch_findings`, `normalize`, `health_check`).

| Connector | What It Pulls | Auth |
|---|---|---|
| Tenable VM | CVE inventory, CVSS, exploit availability, asset list | API key pair |
| SentinelOne | Active threats, quarantined items, agent health, vulnerable endpoints | API token |
| Zscaler | Blocked URLs, shadow SaaS apps, malicious downloads, CASB alerts | API key + partner key |
| Netskope | Cloud app risk scores, DLP violations, sanctioned vs unsanctioned usage | OAuth2 token |
| MS Entra ID | Risky sign-ins, MFA bypass attempts, conditional access violations, privileged roles | OAuth2 + admin consent |
| SharePoint / OneDrive / Teams | Anonymous link sharing, external sharing audit, sensitive label violations | Shared Entra auth |
| ManageEngine SDP | Tickets, SLA status, resolution state (bidirectional — URIP creates tickets too) | OAuth2 |
| ManageEngine Endpoint Central | Patch status per endpoint, missing critical patches, compliance score | OAuth2 |
| ManageEngine MDM | Jailbroken devices, non-compliant mobile, lost/stolen events | OAuth2 |
| Burpsuite Enterprise | Web app scan findings (XSS, SQLi, etc.) per target | API key |
| GTB Endpoint Protector | DLP policy violations, USB block events, exfiltration attempts | API key |
| CloudSEK | Dark web alerts, brand abuse, leaked credentials (via CloudSEK API — Option A) | API key |

### Credential Management

Credentials are entered once via the admin UI, validated with a live test connection, encrypted at rest with Fernet, and stored in the agent's local vault. Rotation is supported: update the key in the UI, hit Save, next pull cycle uses the new key. The cloud portal never stores or sees raw credentials.

### Health Monitoring

Every connector exposes a health check endpoint consumed by the dashboard. Metrics: last successful pull timestamp, next scheduled pull, records ingested in last run, error rate, latency p95. If a connector fails, the error message is specific (e.g., "Zscaler: HTTP 401 — API key expired"). Adverb's IT team sees this without needing to SSH into the agent.

---

## 5. Multi-Tenancy + License Modules

URIP is not rebuilt for each client. It is a **multi-tenant, module-pickable** platform.

### Module Catalog

| Module | Includes |
|---|---|
| **Core** (mandatory) | Risk register, EPSS/KEV/MITRE/OTX enrichment, scoring engine, workflow, audit log, reports |
| VM Module | Tenable / Qualys / Rapid7 connectors |
| EDR Module | SentinelOne / CrowdStrike / Defender connectors |
| Network Module | Zscaler / Netskope / Palo Alto connectors |
| Identity Module | MS Entra / Okta / Google Workspace connectors |
| Collaboration Module | SharePoint / OneDrive / Teams / Slack connectors |
| ITSM Module | ServiceNow / Jira / ManageEngine SDP connectors |
| DAST Module | Burpsuite / OWASP ZAP connectors |
| DLP Module | GTB / Forcepoint / Symantec connectors |
| **Compliance & Audit-Readiness Module** | Framework mapping, control monitoring, evidence automation, policy management, access reviews, vendor risk, auditor portal, compliance scoring |

### Gating

Each tenant has a subscription registry. Disabled modules are invisible in the UI — no routes, no nav items, no backend endpoints accessible. This prevents feature sprawl and supports clean pricing tiers. Adverb subscribes to Core + Network + EDR + Identity + Collaboration + ITSM + VM + DAST + DLP + Compliance.

### White-Label

Per tenant: logo upload, primary/secondary color tokens, app name ("Adverb Security Hub" vs "URIP"). The login page, dashboard shell, and PDF reports all reflect the tenant's brand. Royal Enfield's orange is gone; Adverb's branding is everywhere.

---

## 6. The 'No Manual Effort' Promise

Once configured, URIP-Adverb eliminates the manual work that currently consumes Adverb's security and compliance teams:

| Current Pain | URIP Replacement |
|---|---|
| Log into 11 separate tool dashboards | Single URIP dashboard |
| Copy-paste CVEs into a risk register | Auto-ingested, auto-enriched, auto-scored |
| Manually cross-reference CVEs with CISA KEV | EPSS + KEV + MITRE enrichment applied automatically to every finding |
| Email thread to assign risk owners | Auto-assignment by asset tier + role |
| Spreadsheet to track remediation SLAs | SLA service auto-derives deadlines from severity; timers visible in UI |
| Manual ticket creation in ManageEngine | Auto-ticket creation on Critical/High risks |
| Screenshot evidence for auditors | Evidence automation pulls exports/configs per control run |
| Chasing employees for policy signatures | E-sign workflow with auto-reminders |
| Quarterly access review via Excel export | Access review campaign with Entra-synced user lists |
| Vendor risk tracking in shared drive | Vendor inventory with expiry alerts and questionnaire portal |
| Audit prep scramble (30 days before) | Continuous compliance score; auditor portal always ready |

**The only manual steps remaining:**
1. Initial credential entry (one-time per tool).
2. Human judgment on risk acceptance (HoD approval workflow — tracked, not eliminated).
3. Policy content review by Adverb's legal counsel (templates provided, not legal advice).

---

## 7. Sales Pitch — Why URIP-Adverb Wins

### Data Sovereignty

Adverb's vulnerability inventory, compliance evidence, and audit logs never leave their network. This is not a feature — it is the architecture. For a Reliance-owned company selling to PepsiCo and J&J, this answers procurement security questionnaires before they are asked.

### Unified Pane

Today Adverb's team switches between Tenable, SentinelOne, Zscaler, CloudSEK, and manual spreadsheets. URIP gives them one dashboard where a Zscaler block, a SentinelOne threat, and a Tenable CVE on the same asset are correlated into a single risk record with unified severity and ownership.

### Cost Position

| Item | Annual Cost Estimate |
|---|---|
| Sprinto (compliance automation) | ₹20–40 lakh |
| CloudSEK (external threat) | ₹15–40 lakh |
| Manual audit prep (consultant time) | ₹8–15 lakh |
| Tool swivel-chair overhead (FTE cost) | ₹15–25 lakh |
| **Total current ballpark** | **₹58–120 lakh/year** |
| **URIP-Adverb (subscription)** | **Single fee, module-based, significantly lower than above stack** |

URIP replaces the aggregator cost, the compliance tool cost, and the manual overhead — while adding EPSS/KEV/MITRE enrichment and risk→control linkage that neither Sprinto nor CloudSEK provides natively.

### Threat Intelligence as a Force Multiplier

Even before live connectors ship, URIP's enrichment layer is live. Every CVE gets EPSS exploit probability, KEV exploitation status, MITRE APT group mapping, and OTX IOC context. This is free-tier external intelligence layered on top of Adverb's own tool output — turning raw scanner data into prioritized, contextualized risk.

---

## 8. What Could Go Wrong

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| **Adverb delays API credentials** | Medium | High — Phase 2 blocked | SoW scope clock starts when credentials arrive, not at signing. Simulator data keeps dashboard usable meanwhile. |
| **Burp Enterprise not licensed** | Medium | Medium — DAST module degraded | Confirm license status before SoW. Fallback: Burp Pro manual export ingestion (limited). |
| **MS Entra admin consent denied** | Low | High — Identity + Collaboration + Access Reviews blocked | Flag as explicit Adverb dependency in SoW. Provide consent guide with exact permission scopes. |
| **CloudSEK API changes / breaks** | Low | Medium — external threat alerts stop | Standard connector maintenance. Option B (native build) is a future engagement if integration becomes untenable. |
| **Agent goes offline** | Medium | Low — cloud dashboard goes stale | Agent heartbeat monitoring. Alert to Adverb IT within 5 minutes. Auto-reconnect logic in agent. Drill-down disabled gracefully; metadata cached. |
| **Compliance framework updates (e.g., SOC 2 2022 → next revision)** | Low | Medium — control library drifts | Framework data model has version field. Framework updates committed as part of ongoing subscription. |
| **Scope creep — "add one more tool"** | High | Medium | Change-order process defined in SoW. New connectors = new commercial line item. |
| **Adverb expects training videos / BGV execution / pen tests** | Low | High — expectation mismatch | Explicitly out of scope in Section 7.8 of blueprint. Restated in SoW. We integrate with LMS/BGV providers; we do not replace them. |
| **Auditor demands edit access to portal** | Low | Medium — security boundary violation | Auditor portal scope locked in SoW: read-only, time-bound, framework-scoped. Evidence request workflow handles additional needs. |
| **Connector rate limits or API deprecation** | Medium | Medium — ingestion gaps | Connector health monitoring catches this. Exponential backoff + alerting. Vendor API change tracking as ongoing maintenance. |
| **Data quality in source tools is poor** | Medium | High — URIP output is garbage | Honest limitation stated up front: URIP is a unifier, not a scanner. If Tenable scans miss assets, URIP reflects that gap. We cannot fix source-tool hygiene. |

---

## 9. North Star — What Success Looks Like at Month 6

- Adverb's security team opens **one URL** every morning.
- Every CVE has an EPSS score, a KEV flag, and an owner with an SLA timer.
- Every SOC 2 control failure traces back to the specific risks causing it.
- The external auditor logs into the auditor portal, browses evidence, and requests zero email follow-ups.
- Adverb's compliance officer generates a board-level compliance report in one click.
- No spreadsheet has been opened for audit prep in 90 days.

That is URIP-Adverb.
