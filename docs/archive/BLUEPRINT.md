# SEMANTIC GRAVITY — Unified Risk Intelligence Platform (URIP)
## Solution Blueprint v1.0

**Prepared for:** Royal Enfield
**Prepared by:** Semantic Gravity
**Date:** April 2026 | **Classification:** Confidential

---

## 1. Executive Summary

Royal Enfield currently manages cybersecurity risk across 14 disparate sources — all manually consolidated into an Excel risk register. This blueprint proposes a Unified Risk Intelligence Platform (URIP) that aggregates all risk feeds, applies exploitability-first prioritization using CVSS v4.0, automates assignment and tracking, and delivers a single dashboard for CISO, IT, and executive stakeholders.

The platform does not replace existing security tools. It acts as an orchestration and intelligence layer on top of the existing stack.

### KEY NUMBERS — ROYAL ENFIELD ENVIRONMENT

| Metric | Value |
|--------|-------|
| Total Endpoints | 7,000 (User machines + Servers) |
| Security Tool Stack | CrowdStrike, Forescout NAC, Cisco ISE, CyberArk PAM, Zscaler ZTA/ZIA/CASB, Fortiguard, Google Workspace, Armis (OT) |
| Risk Sources | 14 — 9 core + 5 extended context |
| Risk Scoring | CVSS v4.0 + EPSS + KEV + Asset Criticality (5-layer composite) |
| Current Tracking | Manual Excel risk register — no SLA, no auto-assignment |
| Baseline Discovered | 6.4M vulnerabilities at start -> 1.9M after prioritization in 2 months |

---

## 2. Problem Statement

| Problem | Impact |
|---------|--------|
| 14 risk sources in separate consoles — no unified view | Security teams waste hours consolidating data manually each week |
| All risks manually entered into Excel — no SLA, no auto-assignment | SPOCs take their own time. No escalation. No accountability. |
| Risk accepted by HoD — no recommendation given, still counts in report | Board reports inflated. Accepted risk not differentiated from open risk. |
| Low-impact vulnerabilities fixed first — Zero-Days and Critical exploits wait | Resources wasted on noise. Front door open to active attackers. |

---

## 3. Proposed Solution — URIP

### 3.1 Core Workflow

```
DETECT -> AGGREGATE -> PRIORITIZE -> ASSIGN -> REMEDIATE -> REPORT
```

| Step | Action |
|------|--------|
| DETECT | Pull live feeds from all 14 sources via API connectors and file uploads |
| AGGREGATE | Normalize findings into unified risk schema — de-duplicate across sources |
| PRIORITIZE | Apply 5-layer intelligence pipeline — rank by actual attacker activity |
| ASSIGN | Auto-assign to product owner / SPOC per domain — trigger SLA timer |
| REMEDIATE | Track patch, mitigate, or accept actions — integrate with Jira/ServiceNow |
| REPORT | Generate CISO dashboard, executive summary, board report — accepted risks excluded |

### 3.2 Risk Scoring Logic

| Severity | CVSS Score | SLA (Remediation) | Action |
|----------|-----------|-------------------|--------|
| Critical | 9.0 - 10.0 | 72 hours | Immediate escalation, auto-page CISO |
| High | 7.0 - 8.9 | 7 days | Assign to owner, SLA alert at 5 days |
| Medium | 4.0 - 6.9 | 30 days | Queue in sprint, track weekly |
| Low | 0.1 - 3.9 | 90 days | Batch fix or accept with recommendation |
| None | 0.0 | - | Log only, no action required |

### 3.3 Complete Scoring Pipeline — 5 Layers

| Layer | Source | What It Tells Us | In Score? |
|-------|--------|-----------------|-----------|
| 1 - Raw CVSS | NVD / Scanner | Theoretical severity | Yes (0.55x) |
| 2 - EPSS | FIRST.org API | Exploit probability next 30 days | Yes (2.5x) |
| 3 - KEV | CISA catalog | Confirmed active exploitation | Yes (+2.0) |
| 4 - Asset Criticality | Keyword + CMDB | Business impact of affected asset | Yes (+1.0 to -0.5) |
| 5 - Threat Intel | MITRE ATT&CK + OTX | WHO is exploiting, targeting which sector | Context tag only |

### 3.4 Composite Score Formula

```
composite = max(0.0, min(10.0, 0.55*CVSS + 2.5*EPSS + KEV_bonus + asset_bonus))

KEV_bonus   = +2.0 (CISA confirmed) | 0.0 (not in KEV)
asset_bonus = +1.0 (Tier 1) | +0.5 (Tier 2) | 0.0 (Tier 3) | -0.5 (Tier 4)
EPSS fallback = 0.30 Critical | 0.20 High | 0.10 Medium | 0.05 Low (if no CVE)
```

**Why Additive:** KEV_bonus is already additive. Asset_bonus follows same pattern. Multiplicative amplifies high scores past cap — effect disappears. Additive is linear, predictable, explainable. Codex + Kimi both independently chose additive.

### 3.5 Asset Criticality Tiers

| Tier | Bonus | Keywords | Logic |
|------|-------|----------|-------|
| Tier 1 | +1.0 | SAP, ERP, HMI, SCADA, PLC, OT, ICS, Payment, Domain Admin | Breach = factory stops or critical data lost |
| Tier 2 | +0.5 | Dealer, VPN, Firewall, CRM, API, Mobile App, WAF | Breach = major disruption |
| Tier 3 | 0.0 | Wiki, Workstation, Laptop, Jenkins, Confluence | Standard priority |
| Tier 4 | -0.5 | Test, Dev, Lab, Staging, Sandbox, Kiosk | Low business impact |

**Architecture:** Option C (Codex + Kimi consensus) — auto-assign via keyword + manual override. Production connects to CrowdStrike tags or ServiceNow CMDB.

### 3.6 Exploit Status Classification

| Status | Condition | Badge |
|--------|-----------|-------|
| Weaponized | CVE in CISA KEV catalog | Red |
| Active | EPSS >= 0.5 | Orange |
| PoC | EPSS >= 0.1 | Yellow |
| None | EPSS < 0.1 or no data | No badge |

### 3.7 Real Scenarios

| CVE | CVSS | EPSS | KEV | Asset (Tier) | Composite | Calculation |
|-----|------|------|-----|-------------|-----------|-------------|
| CVE-2024-3400 (PAN-OS) | 10.0 | 0.97 | Yes | T1 (+1.0) | 10.0 | 5.5+2.4+2.0+1.0=10.9->cap 10.0 |
| CVE-2023-20198 (Cisco) | 7.2 | 0.95 | Yes | T1 (+1.0) | 9.3 | 3.96+2.38+2.0+1.0=9.34 |
| CVE-2024-31497 (PuTTY) | 5.9 | 0.02 | No | T4 (-0.5) | 2.8 | 3.25+0.05+0+(-0.5)=2.8 |
| EASM-EXP-001 (Subdomain) | 7.5 | 0.20* | No | T2 (+0.5) | 5.1 | 4.1+0.5+0+0.5=5.1 |

---

## 4. Integration Architecture

### 14 Data Source Connectors

| # | Source | Tool (RE Stack) | Data Type | Integration |
|---|--------|----------------|-----------|-------------|
| 1 | Spotlight (VM) | CrowdStrike Falcon | CVEs, endpoints | REST API |
| 2 | EASM | CrowdStrike / External | Attack surface | REST API |
| 3 | CNAPP | CrowdStrike Cloud | Cloud misconfigs | REST API |
| 4 | OT Environment | Armis | OT asset vulns | Armis API |
| 5 | VAPT Reports | External Vendor | Pentest findings | File Upload |
| 6 | Threat Intelligence | External Feed | Exploit intel | Feed / API |
| 7 | CERT-In Advisories | CERT-In Portal | Govt advisories | RSS / Manual |
| 8 | Bug Bounty | Internal/External | Researcher findings | Webhook |
| 9 | SoC Alerts | SIEM / SoC Team | Incident alerts | SIEM API |
| 10 | NAC | Forescout / Cisco ISE | Rogue devices | Syslog / API |
| 11 | PAM | CyberArk | Privilege abuse | REST API |
| 12 | CASB | Zscaler ZTA/CASB | Shadow IT | Zscaler API |
| 13 | Firewall | Fortiguard | Threat events | Syslog |
| 14 | Email | Google Workspace | Phishing, BEC | Google API |

### Enrichment Layer (applies to ALL risks from all sources)

| # | Capability | Source | Status | On Risk Rows? | In Score? |
|---|-----------|--------|--------|:---:|:---:|
| 1 | EPSS | FIRST.org API | LIVE | Yes | Yes (2.5x) |
| 2 | CISA KEV | CISA JSON | LIVE | Yes | Yes (+2.0) |
| 3 | Asset Criticality | Keyword + Manual | LIVE | Yes | Yes (+/-) |
| 4 | APT Tags | MITRE ATT&CK | LIVE | Yes | Context only |
| 5 | IOC Matching | OTX indicators | LIVE | Dashboard KPI | Context only |
| 6 | Geo Threat Map | OTX + GeoIP | LIVE | Separate page | Context only |
| 7 | Dark Web | Simulated | DEMO | Dashboard KPI | Context only |
| 8 | RE Network Logs | Client SIEM | POST GO-LIVE | Future | Future |

---

## 5. Portal Modules

### 5.1 Risk Dashboard
- Org-level risk score (aggregated across all sources)
- Breakdown by domain: Endpoint, Cloud, Network, Application, Identity, OT
- Trend chart: Risk posture over time (weekly/monthly)
- SLA breach alerts + IOC match count + Dark web alert count
- Role-based views: CISO, IT Team, Executive/Board

### 5.2 Risk Register (Replaces Excel)
- Auto-populated from all 14 source connectors
- Columns: ID, Finding, Source, Domain, CVSS, EPSS, KEV, Composite, Severity, Asset, Asset Tier, APT, Owner, Status, SLA Due, Actions
- Filter by severity, domain, source, owner, status (cascading/dynamic)
- Column sorting (ascending/descending on every column)
- View risk detail modal with full history
- Assign risk to user via picker modal
- Full audit trail per finding

### 5.3 Risk Acceptance Workflow
- Owner flags risk for acceptance -> system auto-generates recommendation
- Recommendation includes: compensating controls, monitoring requirements, re-review date
- APT WARNING: If CVE used by known APT groups, recommendation includes threat actor context
- HoD approves with digital sign-off — full audit trail
- Accepted risks tagged — excluded from all dashboards and reports
- Re-review reminder triggered at 90 days

### 5.4 Remediation Tracker
- SLA countdown per finding (Critical: 72hr, High: 7d, Medium: 30d, Low: 90d)
- Jira/ServiceNow ticket auto-creation on assignment
- SPOC notified via email + Slack/Teams on assignment and SLA breach
- Re-test tracking post-patch
- Closure requires evidence upload

### 5.5 Reporting Engine
- Executive Summary: Top 10 risks, org score, trend, SLA compliance
- CISO Report: Full register, source breakdown, owner accountability
- Board Report: Risk posture score only — accepted risks excluded
- CERT-In Compliance Report: Advisories tracked, response status
- Export: PDF, Excel

### 5.6 Threat Intelligence Map
- Threat pulses with Royal Enfield relevance scoring (brand +40, India +25, manufacturing +20)
- IOC feed: IPs, domains, hashes with match status against infrastructure
- APT group tracking from MITRE ATT&CK (187 groups with sector targeting)
- Dark web monitoring alerts (credential dumps, brand mentions)
- Regional threat breakdown by country

### 5.7 Audit Log
- Immutable record of all platform actions
- Filterable by resource type, action, user
- Full history of risk status changes, assignments, approvals

### 5.8 Settings
- User management (CISO creates/edits users)
- Connector configuration with encrypted credentials (Fernet AES-256)
- Connector health status and sync monitoring

---

## 6. Technical Architecture

### Stack
| Layer | Technology |
|-------|-----------|
| Backend | FastAPI (Python 3.12), async |
| Database | PostgreSQL 16 (Neon) |
| Cache | Redis 7 |
| Frontend | Vanilla JS + Chart.js 4.4 + Font Awesome 6 |
| Auth | JWT (HS256, 8h expiry) |
| RBAC | 4 roles: CISO, IT_Team, Executive, Board |
| Reports | ReportLab (PDF) + openpyxl (Excel) |
| Encryption | Fernet (AES-256-GCM) for connector credentials |
| Hosting | Railway (backend) + Vercel (frontend) + Neon (database) |
| CI/CD | GitHub Actions (vulnerability simulator every 15 min) |
| Repo | github.com/ai-meharbnsingh/URIP |

### Database Schema (8 tables)
- `users` — email, role, team, hashed password
- `risks` — 25+ columns including CVSS, EPSS, KEV, asset_tier, composite_score
- `risk_history` — immutable change tracking per risk
- `acceptance_requests` — justification, controls, recommendation, APT warning
- `remediation_tasks` — linked to risks, SLA tracking, Jira integration
- `connector_configs` — encrypted credentials, sync status
- `audit_logs` — every action logged with user, timestamp, details

### API Endpoints (~35)
- Auth: login, me
- Dashboard: KPIs, charts (domain/source/trend), alerts
- Risks: CRUD, filter, paginate, sort, assign, export
- Acceptance: create, approve, reject (with APT warning)
- Remediation: CRUD, status tracking
- Reports: generate PDF/Excel, CERT-In, scheduled
- Audit Log: filterable history
- Settings: users, connectors (CRUD + test)
- Threat Intel: pulses, APT groups, IOCs, IOC match, geo stats, dark web

### Security
- JWT with 8h expiry, bcrypt password hashing
- RBAC middleware: board < executive < it_team < ciso
- Connector credentials encrypted with Fernet (key from env var)
- CORS: explicit origin allowlist
- All frontend DOM via createElement + textContent (no innerHTML — XSS-safe)
- Audit trail on every write operation

### Configuration
All settings via environment variables (`.env` / Railway env vars):
- `DATABASE_URL`, `REDIS_URL`, `JWT_SECRET_KEY`, `URIP_FERNET_KEY`
- `CORS_ORIGINS`
- `CROWDSTRIKE_CLIENT_ID`, `CROWDSTRIKE_CLIENT_SECRET`
- `ARMIS_API_KEY`, `ZSCALER_API_KEY`, `CYBERARK_API_KEY`
- `OTX_API_KEY`, `VIRUSTOTAL_API_KEY`
- `JIRA_URL`, `JIRA_API_TOKEN`
- `SERVICENOW_URL`, `SERVICENOW_API_TOKEN`

---

## 7. Implementation Plan

| Phase | Timeline | Deliverable | Milestone |
|-------|----------|------------|-----------|
| Phase 1 | Week 1-2 | API connectors for CrowdStrike + Armis + VAPT upload | Live data flowing |
| Phase 2 | Week 3-4 | Risk register + CVSS scoring + SLA engine | Register live |
| Phase 3 | Week 5-6 | Acceptance workflow + HoD approval + recommendation engine | Workflow live |
| Phase 4 | Week 7-8 | Dashboard + reports + role-based access | Demo ready |
| Phase 5 | Week 9-10 | Remaining connectors + UAT | Full system live |
| Phase 6 | Week 11-12 | Go-live + handover + ops training | Production |

---

## 8. Live Platform Stats

| Metric | Value |
|--------|-------|
| Total Risks | 221 (demo dataset) |
| Distribution | Critical: 12, High: 38, Medium: 125, Low: 46 |
| KEV Flagged | 54 confirmed weaponized |
| IOC Matches | 5 infrastructure matches |
| Dark Web Alerts | 5 (credential dumps, brand mentions) |
| APT Groups Tracked | 187 (from MITRE ATT&CK) |
| Default Sort | composite_score DESC |
| Pages | 8 (Dashboard, Register, Acceptance, Remediation, Reports, Threat Map, Audit Log, Settings) |
| API Endpoints | ~35 |
| Frontend | urip-frontend.vercel.app |
| Backend | urip-backend-production.up.railway.app |
| Database | Neon PostgreSQL (project: URIP) |
| GitHub | github.com/ai-meharbnsingh/URIP |
| Simulator | GitHub Actions cron every 15 min |

---

## 9. Commercial Model

| Item | Detail |
|------|--------|
| Model | 1-time platform delivery + subscription support |
| Endpoint Tier | Up to 10,000 endpoints (covers RE's 7,000) |
| Subscription | 2-year initial term, renewable annually |
| Includes | All connectors, portal, dashboards, reports, infra support |
| Ops Handover | Portal operations handed to RE IT team post Phase 6 |
| Support | Semantic Gravity: infra-level. Royal Enfield: day-to-day ops |
| Next Step | Gurgaon demo — May 2026 |

---

## 10. What We Need From Royal Enfield

| # | Input Required |
|---|---------------|
| 01 | Read-only API keys for CrowdStrike, Armis, Zscaler CASB, SoC SIEM |
| 02 | One sample VAPT report (PDF or Excel) for parser design |
| 03 | Current Excel risk register structure (anonymized ok) |
| 04 | HoD approval hierarchy per domain |
| 05 | Ticketing system: Jira / ServiceNow / other |
| 06 | Competitor quotes (PFC and others) for benchmarking |

---

## 11.审计 Trail — Multi-LLM Review

This blueprint and codebase have been reviewed by:

| Reviewer | Model | Role | Key Findings |
|----------|-------|------|-------------|
| **Codex** | GPT-5.3 | Strategy + Human Reviewer | Additive formula approved. "Add Explain Score panel for demo." |
| **Kimi** | Moonshot | QC Director | Score: 78-85/100. "Clean architecture. OTX needs API key for live feed." |
| **Claude** | Opus 4.6 | CEO Orchestrator | Built full stack. 68 files, 8 pages, 35 endpoints. |
| **Gemini** | - | Architecture Director | Schema design, CORS fix, performance review |

---

*Semantic Gravity | contact@semanticgravity.in | Gurgaon Demo: May 2026*
