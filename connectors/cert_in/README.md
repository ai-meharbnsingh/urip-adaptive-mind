# CERT-In Connector

**Registered name:** `cert_in`

India Computer Emergency Response Team (CERT-In) advisory ingestion for URIP. Pulls public security advisories and normalizes them to the unified risk register.

---

## Data Sources

- **Primary:** RSS feed at `https://www.cert-in.org.in/s2cMainServlet?pageid=PUBVLNOTES01`
- **Fallback:** HTML scrape of the advisories listing page (BeautifulSoup) when RSS is empty or fails

## Authentication

No credentials required — CERT-In is a public source.
`authenticate()` validates site connectivity by fetching the RSS/advisories path.

### Optional Tenant Credentials

| Key | Description | Default |
|-----|-------------|---------|
| `base_url` | CERT-In base URL | `https://www.cert-in.org.in` |
| `tenant_id` | Tenant slug | `unknown` |

## Polling Schedule

Recommended: **daily** (RSS feeds rarely update faster).

## Severity Mapping

| CERT-In Severity | URIP Severity | CVSS Score |
|------------------|---------------|------------|
| Critical | critical | 9.0 |
| High | high | 7.5 |
| Medium | medium | 5.0 |
| Low | low | 3.0 |
| Unknown / missing | medium | 5.0 |

## Normalized Output

- `source`: `cert_in`
- `domain`: `advisory`
- `tags`: Indian regulatory provenance appended to description
- `cve_id`: First CVE reference from the advisory (if present)
- `asset`: First affected product (or `N/A`)

## Files

- `connector.py` — `CertInConnector(BaseConnector)`
- `api_client.py` — RSS parser + HTML scraper (`CertInAPIClient`)
- `schemas.py` — Pydantic v2 models (`CertInAdvisory`)
