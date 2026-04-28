Verdict: 88/100 — 3 critical fixes landed perfectly, but deeper audit surfaces 2 native `alert()` calls, 12 hardcoded demo placeholders, and systemic a11y gaps.

| Severity | File:line | Quoted snippet | Fix |
|----------|-----------|----------------|-----|
| CRITICAL | admin-vapt.html:238 | `.catch(function (e) { alert(e.message); });` | Replace with `URIP.showNotification('error', e.message)` or inline banner |
| CRITICAL | admin-vapt.html:291 | `.catch(function (e) { alert(e.message); });` | Replace with `URIP.showNotification('error', e.message)` or inline banner |
| HIGH | admin-vapt.html:120 | `placeholder="Alice Lead"` | Change to `placeholder="Contact name"` |
| HIGH | admin-tenant-detail.html:157 | `placeholder="Jane Doe"` | Change to `placeholder="Full name"` |
| MEDIUM | admin-vapt.html:112 | `placeholder="Acme Pentesters"` | Change to `placeholder="Vendor name"` |
| MEDIUM | admin-vapt.html:116 | `placeholder="lead@acme.example.com"` | Change to `placeholder="vendor@example.com"` |
| MEDIUM | admin-vapt.html:124 | `placeholder="Acme Pvt Ltd"` | Change to `placeholder="Organization"` |
| MEDIUM | admin-tenants.html:74 | `placeholder="Acme Technologies"` | Change to `placeholder="Tenant name"` |
| MEDIUM | admin-tenants.html:78 | `placeholder="acme"` | Change to `placeholder="tenant-slug"` |
| MEDIUM | admin-tenants.html:83 | `placeholder="acme.com"` | Change to `placeholder="tenant.com"` |
| MEDIUM | admin-tenants.html:87 | `placeholder="ciso@acme.com"` | Change to `placeholder="admin@example.com"` |
| MEDIUM | admin-tenant-detail.html:93 | `placeholder="e.g. Acme Risk Cloud"` | Change to `placeholder="e.g. Your App Name"` |
| MEDIUM | admin-tenant-detail.html:153 | `placeholder="ciso@acme.com"` | Change to `placeholder="admin@example.com"` |
| LOW | connector-wizard.html:69 | `href="#"` | Change to `href="javascript:void(0)"` or attach `event.preventDefault()` |
| LOW | dashboard.html:143,161,176 & risk-overview.html:85,104 | `<canvas id="riskByDomainChart"></canvas>` (and 4 others) | Add `role="img" aria-label="Descriptive chart title"` to each canvas |
| LOW | 26 urip-app files (dashboard.html:193, risk-register.html:78, admin-vapt.html:40, domain-*.html, etc.) | `<th>ID</th>` etc. | Add `scope="col"` to every `<th>` in data tables |
| LOW | js/shell.js (all urip-app pages) | No skip-to-content link injected before sidebar | Add `<a href="#main" class="skip-link">Skip to content</a>` as first child of `.app-shell` |

**BOTTOM LINE:** To reach 100, scrub all native `alert()` calls in admin-vapt.html (replace with toasts/banners), remove every hardcoded demo placeholder—especially fake personas like "Alice Lead" and "Jane Doe"—fix the connector-wizard `href="#"`, add `role="img" aria-label="..."` to all 5 chart canvases, add `scope="col"` to every `<th>` in data tables across the 26 affected pages, and inject a skip-to-content link at the top of the shell template.
