# Generic EASM Connector — Censys / Shodan / Detectify

One connector class fronts three EASM providers.  A tenant picks **exactly one**
via `easm_provider` and supplies a SCOPE (`monitor_domains` or `monitor_ips`)
so we never query "the entire internet".

| Provider  | API base                  | Auth model                          | Native data |
|-----------|---------------------------|-------------------------------------|-------------|
| Censys    | `https://search.censys.io` | `Authorization: Bearer <token>`     | Hosts, certs, services |
| Shodan    | `https://api.shodan.io`    | `?key=<api_key>` query string       | Ports, banners, vulns |
| Detectify | `https://api.detectify.com` | `Authorization: Bearer <token>`    | Web vuln scan results |

## Tenant credential schema

### Censys
```jsonc
{
  "easm_provider":   "censys",
  "api_token":       "censys_xxx",
  "monitor_domains": "example.com,test.com"
}
```

### Shodan
```jsonc
{
  "easm_provider":   "shodan",
  "api_key":         "shodan_xxx",
  "monitor_ips":     "1.2.3.4,5.6.7.8"
}
```

### Detectify
```jsonc
{
  "easm_provider":   "detectify",
  "api_token":       "detectify_xxx",
  "monitor_domains": "test.com"
}
```

## Provider setup steps

| Provider  | Where to generate the key                               |
|-----------|---------------------------------------------------------|
| Censys    | Censys → Account Settings → API Credentials             |
| Shodan    | Shodan → My Account → API Key                           |
| Detectify | Detectify → Settings → Team API Keys (Surface Monitoring scope) |

## Scope is mandatory

The connector iterates the scope list — it does **not** issue open-ended
"give me everything" queries.  An empty scope returns zero findings.

| Provider  | Scope field        | Why                                              |
|-----------|--------------------|--------------------------------------------------|
| Censys    | `monitor_domains`  | We run host-search per monitored domain.          |
| Shodan    | `monitor_ips`      | We host-lookup each IP.                           |
| Detectify | `monitor_domains`  | We pull findings per Surface-Monitoring domain.   |

## Severity mapping

| Signal                                                   | URIP severity |
|----------------------------------------------------------|---------------|
| `active_exploit=true` OR confirmed critical/high finding | critical      |
| Native `critical`                                        | critical      |
| Exposed admin/console interface (port title/product hits `admin`, `console`, `login`, `phpmyadmin`, `kibana`, `grafana`, `jenkins`, `wp-admin`) | high |
| Native `high`                                            | high          |
| Detected vulns (Shodan `vulns[]` non-empty)              | high          |
| Hostname matches `dev.`/`staging.`/`stg.`/`test.`/`qa.`/`uat.` | medium  |
| Native `medium`                                          | medium        |
| RFC1918 / internal-only IP exposure                       | low          |
| Otherwise                                                | low           |

When the provider returns a strong native severity (e.g. Detectify
`critical`/`high`), it overrides the structural classification.
