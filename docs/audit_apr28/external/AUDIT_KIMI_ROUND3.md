**Score: 86**

| Severity | File:line | Quoted snippet | Fix |
|---|---|---|---|
| High | index.html ~362–391 | `<label class="form-label"><i class="fas fa-envelope"></i> Email Address</label>` `<input id="loginEmail" …>` | Add `for="loginEmail"` to the label (same for password label → `loginPassword`) |
| High | register.html ~53–66 | `<label class="form-label"><i class="fas fa-building"></i> Tenant ID</label>` `<input id="tenantId" …>` | Add `for` attributes linking each label to its input (tenantId, fullName, email, password) |
| High | forgot-password.html ~52–53 | `<label class="form-label"><i class="fas fa-envelope"></i> Email Address</label>` `<input id="email" …>` | Add `for="email"` to the label |
| Medium | settings.html ~122 | `<input type="text" id="userSearch" placeholder="Search users...">` | Add `aria-label="Search users"` |
| Medium | settings.html ~156 | `<input type="text" id="connectorSearch" placeholder="Search connectors...">` | Add `aria-label="Search connectors"` |
| Medium | audit-log.html ~37 | `<input type="text" id="searchInput" placeholder="Search by user, action, or details...">` | Add `aria-label="Search audit log"` |
| Medium | audit-log.html ~42 | `<label class="filter-label">Resource Type:</label>` `<select class="filter-select" id="resourceTypeFilter">` | Associate label with select via `for="resourceTypeFilter"` (or `aria-label` on the select) |
| Medium | audit-log.html ~56 | `<label class="filter-label">Action:</label>` `<select class="filter-select" id="actionFilter">` | Associate label with select via `for="actionFilter"` (or `aria-label` on the select) |
| Medium | remediation-tracker.html ~80 | `<input type="text" id="searchInput" placeholder="Search tasks...">` | Add `aria-label="Search tasks"` |
| Medium | remediation-tracker.html ~85 | `<label class="filter-label">Status:</label>` `<select class="filter-select" id="statusFilter">` | Associate label with select via `for="statusFilter"` (or `aria-label` on the select) |
| Medium | remediation-tracker.html ~96 | `<label class="filter-label">Priority:</label>` `<select class="filter-select" id="priorityFilter">` | Associate label with select via `for="priorityFilter"` (or `aria-label` on the select) |
| Medium | threat-map.html ~462 | `<input type="text" id="ioc-search" class="ti-search-input" placeholder="Search IOCs (IP, domain, hash...)">` | Add `aria-label="Search IOCs"` |
| Medium | cspm-findings.html ~29 | `<select id="filterStatus" class="form-input" style="width:auto">` | Add `aria-label="Filter by status"` |
| Medium | cspm-findings.html ~35 | `<select id="filterSeverity" class="form-input" style="width:auto">` | Add `aria-label="Filter by severity"` |
| Medium | cspm-findings.html ~42 | `<select id="filterCloud" class="form-input" style="width:auto">` | Add `aria-label="Filter by cloud provider"` |
| Medium | risk-overview.html | No `<h1>` element on page | Add `<h1 class="page-title">Risk Overview</h1>` as the first heading |
| Medium | tool-catalog.html | No `<h1>` element on page | Add `<h1 class="page-title">Tool Catalog</h1>` as the first heading |
| Medium | connector-status.html | No `<h1>` element on page (only `<h3>`) | Add `<h1 class="page-title">Connector Status</h1>` as the first heading |
| Medium | asset-inventory.html ~65 | `<th scope="col" style="width:36px"></th>` | Add `aria-label="Select or star asset"` |
| Medium | admin-vapt.html ~48 | `<th scope="col"></th>` (Vendors table Actions column) | Add `aria-label="Actions"` |
| Medium | admin-vapt.html ~89 | `<th scope="col"></th>` (Submissions table Actions column) | Add `aria-label="Actions"` |
| Medium | admin-vapt.html ~103 | `<div id="inviteModal" class="modal-backdrop" style="display:none">` | Add `role="dialog" aria-modal="true" aria-labelledby="inviteModalTitle"` |
| Medium | admin-vapt.html ~107 | `<button class="modal-close" id="inviteClose">&times;</button>` | Add `aria-label="Close"` |
| Medium | ztna-dashboard.html ~103–104 | `<td>${p.identity_required ? '<i class="fas fa-check"></i>' : '<i class="fas fa-times"></i>'}</td>` | Wrap icons in `<span aria-label="Yes">` / `<span aria-label="No">` (or use text) |
| Low | settings.js ~181 | `editBtn.title = 'Edit User';` (icon-only button) | Add `editBtn.setAttribute('aria-label', 'Edit User');` |
| Low | asset-inventory.js ~203 | `starBtn.title = starred.has(a.id) ? 'Unflag' : 'Flag as critical';` | Add `starBtn.setAttribute('aria-label', …)` |
| Low | admin-tenants.js ~125 | `viewBtn.title = 'Open tenant';` (icon-only button) | Add `viewBtn.setAttribute('aria-label', 'Open tenant');` |
| Low | connector-status.js ~168–192 | `pull.title = 'Trigger manual pull';` `cfg.title = 'Reconfigure';` `del.title = 'Disable';` | Add `aria-label` to each of the three icon-only buttons |
| Low | admin-modules.js ~149 | `lock.title = 'Core module — always on';` (icon-only lock span) | Add `lock.setAttribute('aria-label', 'Core module — always on');` |
| Low | audit-log.js ~220–253 | `prevBtn` / `nextBtn` contain only `<i class="fas fa-chevron-left"></i>` / `<i class="fas fa-chevron-right"></i>` | Add `aria-label="Previous page"` and `aria-label="Next page"` to the buttons |
| Low | risk-register.js ~336–342 | `checkbox(riskId)` creates `<input type="checkbox">` with no label | Add `c.setAttribute('aria-label', 'Select risk ' + riskId);` |

**BOTTOM LINE:** 27 remaining accessibility issues across 16 files. The biggest gaps are: (1) unassociated or missing form labels on auth pages and app filters, (2) three pages missing an `<h1>`, (3) empty `<th>` headers and icon-only buttons relying on `title` instead of `aria-label`, and (4) the VAPT invite modal missing dialog ARIA. No critical blockers, but screen-reader and keyboard users still hit friction on core flows.
