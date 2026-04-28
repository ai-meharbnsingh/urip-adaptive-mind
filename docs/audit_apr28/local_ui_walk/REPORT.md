# URIP Local UI Walk — Playwright Audit

**Date:** 2026-04-28
**Stack:** localhost:8088 (URIP backend + frontend, uvicorn) + localhost:8001 (Compliance dev) + Postgres :5433 + Redis :6379
**Auth:** admin@adaptive-mind.com / Urip@2026 (role=ciso, tenant=adaptive-demo)
**Method:** Playwright navigate → capture console errors + `/api/*` network failures per page

## Headline

**52/52 pages reachable.**
**47 pages: zero console errors / no failed API calls.**
**4 pages: real bugs (1 JS syntax error, 3 missing-endpoint clusters).**
**1 page: RBAC asymmetry (page accessible to a role that can't load its data).**

---

## Bugs (must fix)

### B-1 — `audit-log.html` JS syntax error breaks Export CSV button

**Severity:** medium (page renders but inline script fails to parse → button does nothing)
**Console:** `[ERROR] Invalid or unexpected token`
**Root cause:** `frontend/audit-log.html:141-142` has a literal newline INSIDE a string literal:

```js
exportToBlob('urip-audit-log.csv', [headers].concat(csvRows).join('
'), 'text/csv');
```

The unterminated string `('` … `')` causes the JS parser to bail on the entire `<script>` block at line 104, so the `DOMContentLoaded` handler that wires the export button never runs.

**Fix:** Replace the broken `.join('` newline `')` with `.join('\n')` on a single line.

### B-2 — `acceptance-workflow.html` calls 3 endpoints that don't exist

**Severity:** high (page boots but all three data sections fail)
**Console:** 6 errors (3 × 404 + 3 × propagated `Error: Not Found`)
**Failed requests:**
- `GET /api/acceptance/stats → 404`
- `GET /api/acceptance/pending → 404`
- `GET /api/acceptance/recent → 404`

**Note:** `GET /api/acceptance?status=pending` returns 200, so the parent route exists but the three sub-routes the frontend expects do not.

**Fix options:** implement the 3 backend routes, OR change the frontend to derive stats/pending/recent from the existing `/api/acceptance` list response.

### B-3 — `domain-compliance-summary.html` calls a missing endpoint

**Severity:** medium (page renders, summary card fails)
**Console:** 1 × 404
**Failed request:** `GET /api/compliance/frameworks/summary → 404`

**Fix:** implement the endpoint OR redirect frontend to the compliance service on `:8001`.

### B-4 — `domain-workflow.html` calls 3 endpoints that don't exist

**Severity:** high (workflow automation page is feature-empty)
**Console:** 3 × 404
**Failed requests:**
- `GET /api/auto-remediation/runs?per_page=20 → 404`
- `GET /api/integrations/jira/health → 404`
- `GET /api/integrations/servicenow/health → 404`

**Fix:** implement the 3 backend routes (auto-remediation runs list, jira/servicenow health probes).

---

## RBAC asymmetry (UX issue, not a bug)

### R-1 — `admin-tenants.html` accessible to non-super-admin users; data load 403s

**Severity:** low (correct security, bad UX)
**Console:** 1 × 403
**Failed request:** `GET /api/admin/tenants → 403`
**Cause:** seeded admin has role=`ciso`; this route requires `is_super_admin=true`.
**Fix options:**
1. Route-guard the page (redirect non-super-admin to dashboard).
2. Hide the menu item when `urip_user.is_super_admin === false`.
3. Show an empty-state with "Super-admin only" copy instead of a console error.

---

## Pages walked clean (47)

| # | Page | Notes |
|---|---|---|
| 1 | `login.html` | Sign-in flow works end-to-end. |
| 2 | `dashboard.html` | 5 API calls (kpis, risks, charts × 3) all 200. |
| 3 | `risk-overview.html` | 5 APIs 200. |
| 4 | `risk-register.html` | 2 APIs 200. |
| 5 | `remediation-tracker.html` | 1 API 200. |
| 6 | `asset-inventory.html` | clean. |
| 7 | `asset-detail.html` | works with valid UUID; the `?id=ws-82` form is correctly rejected with 422 (expected validation). |
| 8 | `connector-status.html` | clean. |
| 9 | `connector-wizard.html` | clean. |
| 10 | `tool-catalog.html` | clean. |
| 11 | `reports.html` | clean. |
| 12 | `notifications.html` | clean. |
| 13 | `global-search.html` | clean. |
| 14 | `risk-quantification.html` | clean. |
| 15 | `settings.html` | clean. |
| 16 | `attack-path.html` | clean. |
| 17 | `threat-map.html` | clean. |
| 18 | `ai-security-dashboard.html` | clean. |
| 19 | `cspm-dashboard.html` | clean. |
| 20 | `cspm-findings.html` | clean. |
| 21 | `cspm-control-detail.html` | clean. |
| 22 | `dspm-dashboard.html` | clean. |
| 23 | `ztna-dashboard.html` | clean. |
| 24-31 | `domain-{endpoint,identity,network,cloud,email-collab,mobile,ot,external-threat}.html` | all clean. |
| 32 | `admin-modules.html` | clean. |
| 33 | `admin-scoring.html` | clean. |
| 34 | `admin-tenant-detail.html` | clean (DOM autocomplete-attr verbose only). |
| 35 | `admin-vapt.html` | clean. |
| 36 | `vapt-portal-login.html` | clean. |
| 37-39 | `vapt-portal-{dashboard,submit,submission-detail}.html` | correctly redirect to `vapt-portal-login.html` when no vendor token. |
| 40 | `vendor-login.html` | clean. |
| 41 | `mfa-enroll.html` | clean. |
| 42 | `register.html` | clean (DOM autocomplete-attr verbose only). |
| 43 | `forgot-password.html` | clean. |
| 44 | `reset-password.html` | clean (DOM autocomplete-attr verbose only). |
| 45 | `index.html` | aliases to login (correct). |
| 46 | `home.html` | marketing landing, clean. |
| 47 | `io-gita-demo.html` | demo component, clean. |

---

## Service health snapshot

| Service | Port | Status |
|---|---|---|
| URIP backend (uvicorn local) | 8088 | `/api/health` 200 |
| Compliance dev server | 8001 | `/health` 200 |
| Postgres (docker) | 5433 | healthy |
| Redis (docker) | 6379 | healthy |
| Celery worker / beat | — | not started locally (not exercised by this UI walk) |

## Next steps

1. **Fix B-1** — single-line edit, ~30 s.
2. **Triage B-2 / B-3 / B-4** — decide per cluster: implement backend routes, or change frontend to use existing routes.
3. **Decide on R-1** — route-guard vs menu-hide vs empty-state.
4. (Out of scope here) test interactive flows (filtering, modals, multi-step wizards) — this walk only checked initial page load + first API burst.
