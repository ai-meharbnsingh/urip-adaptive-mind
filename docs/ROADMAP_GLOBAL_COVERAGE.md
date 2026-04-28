# URIP Global Coverage Roadmap (consolidated)

Synthesised from 3 inputs:
1. Global Security Ecosystem table (90% of Fortune 500 / high-growth SaaS).
2. Competitive Review (RBVM / ASPM / GRC / CNAPP — where competitors hit a wall).
3. "Future Capabilities for URIP — Universal Security Integration Cockpit" strategist doc (Okta-CIAM, Prisma, Orca, Varonis, GHAS, Snyk, Sentinel, Attivo deception, SafeBreach BAS + emerging compliance frameworks).

Ground truth as of commit `99f7cd6`:
- 31 production connectors registered in `backend/connector_loader.py`
- 15 compliance frameworks seeded in `compliance/backend/compliance_backend/seeders/`
- Anything claimed elsewhere is roadmap.

---

## Part 1 — Connector roadmap (what we don't have, what to build, why)

| # | Category | Have today (real) | To build next | Why (the "must-have" reason) | Killer sentence | Effort | Tier |
|---|---|---|---|---|---|---|---|
| 1 | **Identity / SSO — Workforce** | Microsoft Entra ID | **Okta Workforce** (P0), Ping Identity, JumpCloud | Okta has 78% penetration in 2K+ employee orgs. Most mid-markets run BOTH Entra+Okta — no native dashboard reconciles them. | *"Your CISO doesn't care whether the breach came through Okta or Entra — they care that you saw it coming. We connect both so you do."* | M | P0 |
| 2 | **Identity / CIAM** | none | **Okta Customer Identity** (Auth0) | CIAM market growing 15-20% CAGR; partner portals + B2B = new attack surface. | *"Your customer portal has 10,000 logins a day; URIP knows which three are trying to reach your ERP."* | M | P2 |
| 3 | **HRIS — the offboarding loop** | none (BGV ≠ HRIS) | **Workday**, **Rippling**, **Deel**, BambooHR, HiBob | The "Offboarding Guarantee" story — no competitor bridges HR↔Security. | *"When an employee leaves, your HRIS tells URIP. Within 15 min, URIP checks Okta, GitHub, Zscaler, Cloud — if an account is still active, we raise a Critical Jira ticket."* | M | P0 |
| 4 | **Endpoint (EDR / XDR)** | CrowdStrike, SentinelOne, ManageEngine EC | **Microsoft Defender for Endpoint**, Trend Micro Vision One, Sophos Intercept X | Defender is bundled in every MS E3/E5 — biggest install base. | — | M | P0 |
| 5 | **CNAPP / Cloud — Tier-1** | AWS / Azure / GCP native | **Wiz** (#1), **Prisma Cloud** (P1), **Orca Security** (mid-market) | Standard in $1B+ revenue customers. Prisma fragments across acquired heritage; Orca is agentless mid-market. | *"Prisma Cloud finds 10,000 findings; URIP tells you which three will breach your crown jewels."* / *"Orca finds the vulnerability; URIP tells you if your identity + endpoint controls make it exploitable."* | L | P0 |
| 6 | **CNAPP — Lacework FortiCNAPP** | none | **DEFER** — post-Fortinet acquisition uncertainty | Strategist's own caveat: monitor API roadmap, don't invest until stable. | — | M-H | P3 |
| 7 | **AppSec — SAST / SCA / Secrets-in-code** | none (Burp = DAST only) | **GitHub Advanced Security** (P0), **Snyk** (P0), **SonarQube** (P1), Semgrep, Veracode, Checkmarx | 90%+ of mid-market dev runs on GitHub. ASPM competitors stop at App layer. | *"GitHub found 500 vulnerabilities; URIP tells you the 12 that are deployed, exposed, and under active exploit."* / *"Snyk tells your devs what's broken; URIP tells your CISO whether it's being fixed fast enough."* | M | P0 |
| 8 | **Vulnerability Management** | Tenable | **Qualys**, **Rapid7 InsightVM** | Together with Tenable = full RBVM (Nucleus / Vulcan kill-shot). | — | S | P1 |
| 9 | **Secrets Management** | CyberArk PAM (privileged access) | **HashiCorp Vault**, AWS/GCP/Azure Secrets Mgr | Code-to-runtime narrative — find leaked GitHub key vs Vault. | — | M | P0 |
| 10 | **SASE / Edge** | Zscaler, Netskope | **Cloudflare** | High-growth SaaS default WAF/DDoS. | — | S | P1 |
| 11 | **Firewall / NAC** | Fortinet, Forescout NAC | **Palo Alto**, **Cisco Meraki**, Check Point | F500 default + mid-market default. | — | M | P1 |
| 12 | **Data Security — DSPM (Unstructured)** | none | **Varonis** (#1) | Big 4 auditors ask for it. Mid-market presence via MSSP channel. | *"Varonis maps every permission to your crown jewels; we map every alert to the identity, device, and cloud that could abuse them."* | M | P1 |
| 13 | **Data Security — DSPM (Structured)** | none | **BigID** | Covers DBs, warehouses, data lakes — Varonis covers files only. | *"BigID found PII in Snowflake; Varonis found it on the NAS — URIP tells you which exposure will get you fined first."* | M-H | P1 |
| 14 | **Data Privacy Automation** | none | **Securiti** (Veeam-owned post-Dec 2025) | EU AI Act + GDPR want demonstrable links between data protection + security. | *"Securiti manages privacy compliance; URIP proves that compliance is actually protecting your data."* | M | P2 |
| 15 | **SIEM — Microsoft Sentinel** | generic SIEM | **Microsoft Sentinel** (specific) | Default for Entra-heavy mid-markets. | *"Sentinel sees Azure; URIP sees Azure, AWS, and the suspicious connection between them."* | M | P1 |
| 16 | **SIEM — Cloud-native alternates** | generic SIEM | **Google Chronicle**, **Panther**, **Datadog**, **Snowflake-as-SIEM** | Multi-cloud SIEM normalisation; Datadog/Snowflake are SIEM-Lite for SaaS-native. | *"Panther writes detections as code; URIP writes the story your board understands."* | L | P1 |
| 17 | **SIEM — Splunk-specific** | generic SIEM | **Splunk** native HEC + indexer integration | Legacy enterprise standard. Generic CEF works but enterprises ask "do you support Splunk natively?" | — | M | P2 |
| 18 | **Deception Tech (NEW category)** | none | **Attivo (Bishop Fox)**, **Illusive Networks** | $3.3B → $7B by 2030 (16.8% CAGR). High-fidelity, low-FP threat intel. | *"Attivo proved they're in your network; URIP makes sure they don't get to anything real."* / *"Illusive says they could reach your crown jewels; URIP shows exactly how — and whether your controls would stop them."* | M-H | P2 |
| 19 | **Breach & Attack Simulation (NEW category)** | none | **SafeBreach** (#1), **Picus Security** | Empirical control validation. SafeBreach's data turns URIP scoring from theoretical to empirical. | *"Every tool says it's working; SafeBreach proves some aren't — URIP tells you which gaps matter most."* | M | P1 |
| 20 | **External Surface / Threat Intel** | CloudSEK, EASM (Censys+Shodan+Detectify) | **BitSight**, **SecurityScorecard**, **HackerOne**, **Bugcrowd** | "Credit score" competitors expect us to ship. HackerOne replaces our generic bug_bounty. | — | S | P1 |
| 21 | **Backup / Resilience** | none | **Veeam**, **Druva**, Cohesity, Rubrik | Auditors ask "prove backups run" — auto-evidence. | — | M | P2 |
| 22 | **Email Security** | M365, generic email_security | **Proofpoint**, Mimecast, Abnormal Security | 60% of standalone email-security market. | — | S | P2 |
| 23 | **MDM** | ManageEngine MDM | **Jamf** (Mac), **Intune** (MS), Kandji | Mac shops + MS shops. | — | S | P2 |
| 24 | **OT / ICS** | Armis | Claroty, Nozomi, Dragos | Vertical-specific (oil/gas/utilities). | — | M | P3 |
| 25 | **GRC / Compliance — meta-aggregator** | Internal Compliance module + 15 frameworks | **Vanta**, **Drata**, **OneTrust GRC** as INBOUND feeds | Wizard CTAs already exist (commit `4f457ae`); actual ingestion makes URIP the meta-cockpit. | — | M | P1 |
| 26 | **Ticketing (ITSM)** | Jira ✓ ServiceNow ✓ SDP ✓ | — | Already won this category. | — | — | ✓ |

**Effort key**: S = ≤1 week, M = 1–3 weeks, L = 3–6 weeks
**Tier key**: P0 = pitch-blocker today, P1 = win-rate move, P2 = nice-to-have, P3 = vertical-specific or defer, ✓ = done

---

## Part 2 — Compliance framework roadmap

### Already shipped (the strategist doc lists some of these as "to-build" — they're already in `compliance/backend/compliance_backend/seeders/`):

| # | Framework | Seeder file | Region |
|---|---|---|---|
| 1 | SOC 2 | `soc2.py` | Global |
| 2 | ISO 27001 | `iso27001.py` | Global |
| 3 | ISO 27017 (cloud) | `iso27017.py` | Global |
| 4 | ISO 27018 (cloud PII) | `iso27018.py` | Global |
| 5 | ISO 27701 (privacy) | `iso27701.py` | Global |
| 6 | **ISO 42001** (AI MS) | `iso42001.py` | Global |
| 7 | GDPR | `gdpr.py` | EU |
| 8 | HIPAA | `hipaa.py` | US |
| 9 | PCI DSS | `pci_dss.py` | Global |
| 10 | India DPDP | `india_dpdp.py` | India |
| 11 | NIST CSF 2.0 | `nist_csf.py` | US |
| 12 | CIS Controls v8 | `cis_v8.py` | Global |
| 13 | **DORA** | `dora.py` | EU financial |
| 14 | **EU AI Act** | `eu_ai_act.py` | EU |
| 15 | **NIS2** | `nis2.py` | EU critical infra |

### Genuinely new compliance frameworks to build:

| # | Framework | Region / sector | Why | Killer sentence | Effort | Tier |
|---|---|---|---|---|---|---|
| 16 | **SEC Cybersecurity Disclosure** | US public companies | Effective Dec 2023; 4-day 8-K + 10-K. Materiality assessment requires financial context — generic compliance platforms can't do this. | *"The SEC gives you four days to disclose; URIP gives you the data to decide in four hours."* | H | P0 |
| 17 | **CMMC 2.0 / FedRAMP** | US Defense Industrial Base | 300K DIB contractors need this. C3PAO workflow + POA&M automation = differentiator. | *"CMMC asks if you're secure; URIP proves it with the tools you already run."* | H | P0 |
| 18 | **HITRUST CSF (r2 + e1)** | Healthcare / Business Associates | Sector consolidation drives BAA compliance demand. Control inheritance from CSP is gap. | *"HITRUST requires 400+ controls; URIP populates evidence for the ones your tools already enforce."* | M-H | P1 |
| 19 | **SOC 1 (ICFR)** | SaaS providers in financial supply chain | Bridges security ↔ financial controls — rare in compliance platforms. | *"SOC 1 is about financial trust; we make your security controls financially trustworthy."* | M | P1 |
| 20 | **ISO 22301 (Business Continuity)** | Global, post-pandemic resilience | Connects to incident response data we already have. | *"Business continuity that knows your security reality."* | M | P2 |
| 21 | **Singapore PDPA** | APAC | S$1M / 10% turnover fines; SE Asia coverage scarce. | *"APAC privacy compliance that speaks your security team's language."* | M | P2 |
| 22 | **Australia Privacy Act** | APAC | Notifiable Data Breaches scheme; reform pending. | *"Australia's privacy rules are changing; your compliance automation should already be ready."* | M | P2 |
| 23 | **Brazil LGPD** | LATAM | ANPD enforcement accelerating; Portuguese automation absent. | *"LGPD compliance that doesn't get lost in translation."* | M-H | P2 |
| 24 | **UAE PDPL + Saudi PDPL** | Middle East / GCC | First-mover; Arabic-language gap; bilingual evidence. | *"From São Paulo to Singapore to Riyadh, one cockpit for every privacy law."* | H | P3 |

---

## Part 3 — Updated 6-month sequence (P0s only, ordered for win-rate impact)

| Quarter | Connectors | Compliance | Story it unlocks |
|---|---|---|---|
| **Q1** | Okta Workforce, GitHub GHAS, Snyk, Workday, Wiz | SEC Cybersecurity Disclosure | "Universal Cockpit for SaaS-native enterprises" |
| **Q2** | HashiCorp Vault, Cloudflare, MS Defender for Endpoint, Microsoft Sentinel | CMMC 2.0 / FedRAMP path | "Code-to-runtime + DIB-ready" |
| **Q3** | Prisma Cloud, Orca, Splunk-native, BitSight, SafeBreach (BAS) | HITRUST | "Enterprise-tier ($1B+ revenue) addressable" |
| **Q4** | Varonis, BigID, Vanta/Drata inbound, Jamf, Intune | SOC 1, ISO 22301 | "Full DSPM + GRC-meta + financial trust" |

P2/P3 items (Lacework, Securiti, OT vendors, deception, regional privacy laws) sequence by customer-pull rather than calendar.

---

## Part 4 — Honest pushback on the strategist drafts

These show up in the strategist v5/v6/Future-Capabilities docs as "have" or "to-build" but the reality is different:

1. **"Rippling, Deel as HRIS connectors"** — listed as "have." We have AuthBridge + OnGrid which are **BGV (background-verification)**, not HRIS. They pull joining-time checks, NOT termination events — they cannot drive an offboarding loop. Real HRIS connectors are still P0 to build.
2. **"MS Defender for Endpoint as covered via MS Defender"** — listed as covered. We have Entra ID + M365 Collab, NOT Defender for Endpoint. Different API surface, different connector.
3. **"GitHub GHAS as covered"** — listed as covered. No connector. Burp Enterprise is DAST, not SAST/SCA.
4. **"Splunk, Elastic native"** — listed as covered. We have a generic CEF SIEM connector; specific Splunk HEC and Elastic Beats integration is still to-build.
5. **"NIS2, DORA, EU AI Act, ISO 42001 as future Q3 work"** — strategist Future-Capabilities doc treats them as upcoming. They are **already shipped** in `compliance/backend/compliance_backend/seeders/`. Don't double-count.
6. **"Censys integration is a gap"** — Censys is one of three providers in the existing `easm` multi-adapter connector. This one IS covered.
7. **Lacework FortiCNAPP urgency** — strategist's own implementation-complexity rating says Medium-High due to acquisition uncertainty. Defer is correct; don't list it as P0/P1.
8. **Deception (Attivo/Illusive) and BAS (SafeBreach/Picus)** — these are P1/P2, NOT P0. Mid-market doesn't expect them; they're enterprise-tier differentiators. Worth building post-AppSec, post-Wiz, post-DSPM.

The strategist marketing copy ("killer sentences") is excellent — keep it. The category coverage rationale is sound. But the "have today" column needs to align with the actual connector_loader.py imports before any of this goes into a sales deck.
