# GitHub Advanced Security (GHAS) Connector

Ingests all three GHAS security alert types from your GitHub organization:

| Alert type | GitHub endpoint | URIP source tag |
|---|---|---|
| Code Scanning (SAST) | `GET /orgs/{org}/code-scanning/alerts` | `ghas:code` |
| Secret Scanning | `GET /orgs/{org}/secret-scanning/alerts` | `ghas:secret` |
| Dependabot (SCA) | `GET /orgs/{org}/dependabot/alerts` | `ghas:dependabot` |

---

## Prerequisites

1. **GHAS license** — GitHub Advanced Security must be enabled on the organization.
   - GitHub Enterprise Cloud: enabled by default on public repos; requires GHAS license for private repos.
   - GitHub Enterprise Server ≥ 3.7: requires GHAS license.

2. **PAT scopes** — Create a Personal Access Token with:
   - `security_events` — read code-scanning + secret-scanning alerts
   - `read:org` — verify org membership / org metadata

3. **Org admin / security manager** — The token owner must be an org owner or have the Security Manager role to list org-level alerts.

---

## Setup Steps

### 1. Create a Personal Access Token (Classic)

1. Go to **GitHub → Settings → Developer settings → Personal access tokens → Tokens (classic)**.
2. Click **Generate new token (classic)**.
3. Set an expiry (90 days recommended; rotate before expiry).
4. Select scopes: `security_events`, `read:org`.
5. Click **Generate token** and copy the value immediately.

### 2. (Optional) Use a Fine-Grained PAT

Fine-grained PATs offer more precise control:
1. Go to **Settings → Developer settings → Personal access tokens → Fine-grained tokens**.
2. Set **Resource owner** to your organization.
3. Under **Organization permissions**, grant:
   - Code scanning alerts: **Read**
   - Secret scanning alerts: **Read**
   - Dependabot alerts: **Read**
4. Under **Organization permissions**, also grant:
   - Members: **Read** (equivalent to `read:org`)

### 3. Configure in URIP Tool Catalog

| Field | Value |
|---|---|
| GitHub Organization | Your org slug (e.g. `acme-corp`) |
| PAT / Token | The token copied in step 1 |
| GitHub API URL | `https://api.github.com` (default) or GHE Server URL |

### 4. GitHub Enterprise Server (GHE)

Set **GitHub API URL** to: `https://github.your-company.com/api/v3`

Ensure your URIP deployment can reach the GHE host on TCP 443.

---

## Example Output — Code Scanning Alert

```json
{
  "number": 42,
  "state": "open",
  "rule": {
    "id": "java/sql-injection",
    "severity": "error",
    "security_severity_level": "critical"
  },
  "most_recent_instance": {
    "location": {
      "path": "src/main/java/com/example/UserController.java",
      "start_line": 87,
      "end_line": 89
    }
  },
  "html_url": "https://github.com/acme-corp/backend/security/code-scanning/42"
}
```

URIP normalized record:
```json
{
  "finding": "Code scanning: java/sql-injection",
  "severity": "critical",
  "source": "ghas:code",
  "domain": "application",
  "asset": "src/main/java/com/example/UserController.java"
}
```

---

## Example Output — Secret Scanning Alert

```json
{
  "number": 7,
  "state": "open",
  "secret_type": "github_personal_access_token",
  "secret_type_display_name": "GitHub Personal Access Token",
  "html_url": "https://github.com/acme-corp/infra/security/secret-scanning/7"
}
```

URIP normalized record:
```json
{
  "finding": "Secret leaked: GitHub Personal Access Token",
  "severity": "critical",
  "source": "ghas:secret",
  "domain": "application",
  "exploit_status": "active"
}
```

---

## Example Output — Dependabot Alert

```json
{
  "number": 15,
  "state": "open",
  "security_advisory": {
    "ghsa_id": "GHSA-xxxx-xxxx-xxxx",
    "cve_id": "CVE-2021-23337",
    "summary": "Command injection in lodash",
    "severity": "high",
    "cvss_score": 7.2
  },
  "security_vulnerability": {
    "package": {
      "ecosystem": "npm",
      "name": "lodash"
    },
    "vulnerable_version_range": "< 4.17.21",
    "severity": "high"
  },
  "html_url": "https://github.com/acme-corp/frontend/security/dependabot/15"
}
```

URIP normalized record:
```json
{
  "finding": "Dependabot: lodash (< 4.17.21)",
  "severity": "high",
  "source": "ghas:dependabot",
  "domain": "application",
  "cvss_score": 7.2,
  "cve_id": "CVE-2021-23337",
  "asset": "dep:lodash"
}
```

---

## Severity Mapping

### Code Scanning
| `rule.security_severity_level` | URIP severity |
|---|---|
| `critical` | critical |
| `high` | high |
| `medium` | medium |
| `low` | low |
| _(absent)_ → falls back to `rule.severity` | |

| `rule.severity` (fallback) | URIP severity |
|---|---|
| `error` | high |
| `warning` | medium |
| `note` | low |

### Secret Scanning
All secret-scanning alerts are mapped to **critical** — any leaked secret is a P0 until rotated.

### Dependabot
Uses `security_advisory.severity` directly:
`critical → critical`, `high → high`, `medium → medium`, `low → low`.

---

## Pagination

The connector follows GitHub's `Link: rel="next"` pagination automatically and caps results at **1,000 alerts per alert type** per sync cycle to prevent runaway pulls. For organizations with more than 1,000 open alerts of any type, the connector returns the most-recently-updated 1,000.
