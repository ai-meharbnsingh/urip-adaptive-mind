**Score: 58/100**

A CISO prospect clicking around for 30 minutes will hit **dead buttons, broken connector wizards, wrong product branding, and a compliance sub-app that looks like a different product** (light theme + "Adverb Compliance" titles). The navy/teal dark cockpit is solid on the core risk pages, but the seams show everywhere else.

| Severity | What | Where (URL or file:line) | Quoted snippet | Fix |
|---|---|---|---|---|
| **Critical** | **Wrong product name** — "Adverb Compliance" in browser tab + JS/CSS comments | `/compliance/frameworks.html:6` and 10+ other compliance files | `<title>Frameworks \| Adverb Compliance</title>` | Replace every "Adverb Compliance" with "URIP" |
| **Critical** | **Dead connector wizard** — SDP link uses wrong schema key | `/domain-workflow.html:123` | `href="connector-wizard.html?tool=manageengine_sdp"` | Change to `?tool=me_sdp` or rename schema key to `manageengine_sdp` |
| **Critical** | **Dead connector wizard** — Vanta, Drata, OneTrust don't exist in schema | `/domain-compliance-summary.html:51-53` | `href="connector-wizard.html?tool=vanta"` (and drata, onetrust) | Remove links or add schemas to `connector-schemas.js` |
| **Critical** | **Missing connector** — CrowdStrike marketed everywhere but absent from wizard schema | `frontend/js/connector-schemas.js` | No `crowdstrike` key in `TOOLS` array | Add `crowdstrike` schema or remove from marketing copy |
| **Critical** | **Dead Export button** — no handler attached | `/dashboard.html:30` | `<button class="btn btn-outline" id="btnExport"><i class="fas fa-download"></i> Export</button>` | Wire `btnExport` to `generateReport()` or remove |
| **Critical** | **Dead Export CSV button** — no handler attached | `/audit-log.html:26` | `<button class="btn btn-outline" id="btnExportAudit">Export CSV</button>` | Wire to CSV export function or remove |
| **Critical** | **Leftover company name** — "Semantic Gravity" in architecture diagram | `/home.html:1819` | `<text ... font-family="Inter">SEMANTIC GRAVITY CLOUD</text>` | Replace with "URIP CLOUD" |
| **High** | **Theme break** — compliance sub-app is light/white, rest of app is dark navy | `/compliance/css/main.css:76` | `background-color: var(--gray-100);` | Import `app.css` and add `body.urip-app` class to compliance pages |
| **High** | **"Coming soon" toast** — Export on Risk Overview | `/js/risk-overview.js:29` | `window.URIP.showNotification('Export', 'PDF/CSV export coming soon.', 'info');` | Implement export or remove button |
| **High** | **"Coming soon" toast** — Add Risk on Risk Register | `/js/risk-register.js:50` | `window.URIP.showNotification('Add Risk', 'Manual risk creation — coming soon.', 'info');` | Implement form or remove button |
| **High** | **Placeholder leak** — visible "placeholder until…" text | `/domain-compliance-summary.html:132` | `<em>Vendor risk endpoint not connected — placeholder until /api/compliance/vendors lands.</em>` | Replace with meaningful empty state |
| **High** | **Placeholder leak** — visible "feature roadmap" text | `/domain-workflow.html:198` | `td2.textContent = 'Auto-remediation endpoint not available — feature roadmap.';` | Replace with generic "Not available" empty state |
| **High** | **Dead link** — forgot password goes nowhere | `/vendor-login.html:351` | `<a href="#">Forgot password?</a>` | Link to `forgot-password.html` or remove |
| **High** | **Dead links** — auditor portal tabs use `href="#"` | `/compliance/auditor_portal.html:144-147` | `<a href="#" class="auditor-tab" data-tab="evidence">` | Use `javascript:void(0)` or button elements |
| **High** | **Dead link** — CSPM empty-state CTA uses `href="#"` | `/js/cspm-dashboard.js:60` | `'<a href="#" class="btn btn-primary" onclick="showConnectModal();return false;">Connect a Cloud</a>'` | Use `href="connector-wizard.html?category=CSPM"` |
| **High** | **Dead download** — reports PDF download is a no-op | `/reports.html:235` | `URIP.showNotification('Download Started', ...); // In production...` | Implement real blob download or hide button |
| **High** | **Acme placeholder** in connector credential fields | `/js/connector-schemas.js:137` | `placeholder: 'api-admin@acme.com'` | Replace with `example.com` (7 occurrences) |
| **High** | **Empty `<th>`** with no accessible name | `/vapt-portal-dashboard.html:103` | `<th></th>` | Add `aria-label="Actions"` or visible header |
| **High** | **Empty button** — no accessible name (icon-only logout) | `/vapt-portal-submission-detail.html:27` | `<button id="logoutBtn" class="vapt-btn vapt-btn-ghost"><i class="fas fa-sign-out-alt"></i></button>` | Add `aria-label="Sign out"` |
| **High** | **Empty button** — no accessible name (icon-only logout) | `/vapt-portal-dashboard.html:27` | `<button id="logoutBtn" ...><i class="fas fa-sign-out-alt"></i></button>` | Add `aria-label="Sign out"` |
| **High** | **Empty button** — no accessible name (icon-only logout) | `/vapt-portal-submit.html:27` | `<button id="logoutBtn" ...><i class="fas fa-sign-out-alt"></i></button>` | Add `aria-label="Sign out"` |
| **High** | **Empty button** — drawer close has no aria-label | `/compliance/auditor_portal.html:258` | `<button class="modal-close" id="drawerClose"><i class="fas fa-times"></i></button>` | Add `aria-label="Close drawer"` |
| **Medium** | **TODO leak** in auth script comment | `/compliance/js/auth.js:6` | `* a compliance-specific login (out of scope for this milestone — flagged TODO).` | Remove TODO before shipping |
| **Medium** | **Font inconsistency** — trust-center pages default to system fonts | `/trust-center/request.html:8` | `font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;` | Move `Inter` to first position |
| **Medium** | **Backend gap leak** in visible code comment | `/compliance/reports.html:123` | `// BACKEND GAP: there is no /reports endpoint yet.` | Strip backend-gap comments from production build |

**What IS working (preventing a sub-50 score):**
- **Cache-Control** is correct: HTML gets `max-age=0, must-revalidate` (no-cache behavior); CSS/JS bundles get `immutable` with 1-year TTL.
- **Sidebar scroll persistence** works via `sessionStorage` (`SIDEBAR_SCROLL_KEY`).
- **Empty states** are mostly meaningful — no raw "undefined" or blank white cards; they resolve to "No assets discovered yet" or "Connect a tool" guidance.
- **Connector schemas** for `jira`, `servicenow`, `tenable`, and `manageengine_sdp` (once key is fixed) render correct fields matching `CREDENTIAL_FIELDS`.
- **All 51 app pages** load without 404s and include the viewport meta tag.
- **Canvas elements** have `role="img"` and `aria-label` on the 4 chart instances checked.
- **Risk Overview / Dashboard / CSPM** "Refresh" buttons actually trigger data reloads (not no-ops).
