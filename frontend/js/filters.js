/**
 * URIP - Risk Register Filters & Acceptance Workflow
 * All data loaded from API. NO hardcoded riskData or acceptanceData.
 * All DOM via createElement + textContent (NO innerHTML with user data).
 * Depends on: api.js (window.URIP.apiFetch, window.URIP.showNotification)
 */
(function () {
  'use strict';

  var currentPage = 1;
  var perPage = 20;

  // ─── RISK REGISTER ──────────────────────────────────────────

  /**
   * Load risks from API with filters and pagination.
   *
   * @param {number} [page=1]
   * @param {object} [filters] - { severity, source, domain, status, owner, search }
   */
  async function loadRiskRegister(page, filters) {
    page = page || 1;
    filters = filters || {};
    currentPage = page;

    var params = new URLSearchParams();
    params.set('page', String(page));
    params.set('per_page', String(perPage));

    if (filters.severity && filters.severity !== 'all') params.set('severity', filters.severity);
    if (filters.source && filters.source !== 'all') params.set('source', filters.source);
    if (filters.domain && filters.domain !== 'all') params.set('domain', filters.domain);
    if (filters.status && filters.status !== 'all') params.set('status', filters.status);
    if (filters.owner && filters.owner !== 'all') params.set('owner', filters.owner);
    if (filters.search) params.set('search', filters.search);

    try {
      var data = await window.URIP.apiFetch('/risks?' + params.toString());
      renderRiskTable(data);
    } catch (err) {
      window.URIP.showNotification('Error', 'Failed to load risk register.', 'error');
    }
  }

  /**
   * Render risk table from API response.
   * Uses createElement + textContent exclusively.
   *
   * @param {object} data - { items, total, page, pages }
   */
  function renderRiskTable(data) {
    var tbody = document.getElementById('riskTableBody');
    if (!tbody) return;

    tbody.textContent = '';

    if (!data.items || data.items.length === 0) {
      var emptyRow = document.createElement('tr');
      var emptyCell = document.createElement('td');
      emptyCell.setAttribute('colspan', '12');
      emptyCell.style.textContent = '';

      var emptyState = document.createElement('div');
      emptyState.className = 'empty-state';

      var emptyIcon = document.createElement('div');
      emptyIcon.className = 'empty-state-icon';
      var iconEl = document.createElement('i');
      iconEl.className = 'fas fa-search';
      emptyIcon.appendChild(iconEl);
      emptyState.appendChild(emptyIcon);

      var emptyTitle = document.createElement('div');
      emptyTitle.className = 'empty-state-title';
      emptyTitle.textContent = 'No risks found';
      emptyState.appendChild(emptyTitle);

      var emptyText = document.createElement('div');
      emptyText.className = 'empty-state-text';
      emptyText.textContent = 'Try adjusting your filters or search query.';
      emptyState.appendChild(emptyText);

      emptyCell.appendChild(emptyState);
      emptyRow.appendChild(emptyCell);
      tbody.appendChild(emptyRow);
    } else {
      data.items.forEach(function (risk) {
        var tr = document.createElement('tr');
        if (risk.status === 'accepted') {
          tr.className = 'accepted';
        }

        // ID
        var tdId = document.createElement('td');
        var riskIdSpan = document.createElement('span');
        riskIdSpan.className = 'risk-id';
        riskIdSpan.textContent = risk.risk_id;
        tdId.appendChild(riskIdSpan);
        tr.appendChild(tdId);

        // Finding
        var tdFinding = document.createElement('td');
        var findingDiv = document.createElement('div');
        findingDiv.className = 'risk-finding';
        var findingName = document.createElement('div');
        findingName.className = 'risk-finding-name';
        findingName.textContent = risk.finding;
        findingDiv.appendChild(findingName);
        if (risk.domain) {
          var findingDomain = document.createElement('div');
          findingDomain.className = 'risk-finding-domain';
          findingDomain.textContent = capitalizeFirst(risk.domain);
          findingDiv.appendChild(findingDomain);
        }
        tdFinding.appendChild(findingDiv);
        tr.appendChild(tdFinding);

        // Source
        var tdSource = document.createElement('td');
        var sourceDiv = document.createElement('div');
        sourceDiv.className = 'risk-source';
        var sourceIcon = document.createElement('div');
        sourceIcon.className = 'source-icon';
        var srcI = document.createElement('i');
        srcI.className = 'fas ' + getSourceIcon(risk.source);
        sourceIcon.appendChild(srcI);
        sourceDiv.appendChild(sourceIcon);
        var sourceText = document.createElement('span');
        sourceText.textContent = formatSourceName(risk.source);
        sourceDiv.appendChild(sourceText);
        tdSource.appendChild(sourceDiv);
        tr.appendChild(tdSource);

        // Domain
        var tdDomain = document.createElement('td');
        tdDomain.textContent = capitalizeFirst(risk.domain || '');
        tr.appendChild(tdDomain);

        // CVSS
        var tdCvss = document.createElement('td');
        var cvssSpan = document.createElement('span');
        cvssSpan.className = 'cvss-score ' + getCvssClass(risk.cvss_score);
        cvssSpan.textContent = (risk.cvss_score || 0).toFixed(1);
        tdCvss.appendChild(cvssSpan);
        tr.appendChild(tdCvss);

        // Severity
        var tdSev = document.createElement('td');
        var sevBadge = document.createElement('span');
        sevBadge.className = 'badge badge-' + (risk.severity || 'low');
        sevBadge.textContent = capitalizeFirst(risk.severity || 'low');
        tdSev.appendChild(sevBadge);
        tr.appendChild(tdSev);

        // Asset
        var tdAsset = document.createElement('td');
        var assetSpan = document.createElement('span');
        assetSpan.className = 'risk-asset';
        assetSpan.textContent = risk.asset || '-';
        tdAsset.appendChild(assetSpan);
        tr.appendChild(tdAsset);

        // Owner
        var tdOwner = document.createElement('td');
        var ownerDiv = document.createElement('div');
        ownerDiv.className = 'risk-owner';
        var ownerAvatar = document.createElement('div');
        ownerAvatar.className = 'owner-avatar';
        ownerAvatar.textContent = getInitials(risk.owner_team || '');
        ownerDiv.appendChild(ownerAvatar);
        var ownerText = document.createElement('span');
        ownerText.textContent = risk.owner_team || '-';
        ownerDiv.appendChild(ownerText);
        tdOwner.appendChild(ownerDiv);
        tr.appendChild(tdOwner);

        // Status
        var tdStatus = document.createElement('td');
        var statusTag = document.createElement('span');
        var statusClass = 'status-' + (risk.status || 'open').replace('_', '-');
        statusTag.className = 'status-tag ' + statusClass;
        statusTag.textContent = formatStatus(risk.status);
        tdStatus.appendChild(statusTag);
        tr.appendChild(tdStatus);

        // SLA Due
        var tdSla = document.createElement('td');
        if (risk.sla_deadline) {
          var slaDiv = document.createElement('div');
          slaDiv.className = 'risk-sla';
          var slaDate = document.createElement('div');
          slaDate.className = 'sla-date';
          slaDate.textContent = formatDate(risk.sla_deadline);
          slaDiv.appendChild(slaDate);

          var slaRemaining = document.createElement('div');
          var daysLeft = getDaysUntil(risk.sla_deadline);
          slaRemaining.className = 'sla-remaining';
          if (daysLeft < 0) {
            slaRemaining.classList.add('danger');
            slaRemaining.textContent = Math.abs(daysLeft) + ' days overdue';
          } else if (daysLeft <= 7) {
            slaRemaining.classList.add('danger');
            slaRemaining.textContent = daysLeft + ' days left';
          } else if (daysLeft <= 14) {
            slaRemaining.classList.add('warning');
            slaRemaining.textContent = daysLeft + ' days left';
          } else {
            slaRemaining.classList.add('safe');
            slaRemaining.textContent = daysLeft + ' days left';
          }
          slaDiv.appendChild(slaRemaining);
          tdSla.appendChild(slaDiv);
        } else {
          tdSla.textContent = '-';
        }
        tr.appendChild(tdSla);

        // Notes
        var tdNotes = document.createElement('td');
        tdNotes.textContent = risk.jira_ticket || '-';
        tr.appendChild(tdNotes);

        // Actions
        var tdActions = document.createElement('td');
        var actionsDiv = document.createElement('div');
        actionsDiv.className = 'action-btns';

        var viewBtn = document.createElement('button');
        viewBtn.className = 'action-btn view';
        viewBtn.title = 'View Details';
        viewBtn.appendChild(createIcon('fa-eye'));
        actionsDiv.appendChild(viewBtn);

        var assignBtn = document.createElement('button');
        assignBtn.className = 'action-btn assign';
        assignBtn.title = 'Assign';
        assignBtn.appendChild(createIcon('fa-user-plus'));
        actionsDiv.appendChild(assignBtn);

        if (risk.status !== 'accepted' && risk.status !== 'closed') {
          var acceptBtn = document.createElement('button');
          acceptBtn.className = 'action-btn accept';
          acceptBtn.title = 'Request Acceptance';
          acceptBtn.appendChild(createIcon('fa-ban'));
          actionsDiv.appendChild(acceptBtn);
        }

        tdActions.appendChild(actionsDiv);
        tr.appendChild(tdActions);

        tbody.appendChild(tr);
      });
    }

    // Update pagination
    renderPagination(data.total, data.page, data.pages);

    // Update showing info
    var showingStart = document.getElementById('showingStart');
    var showingEnd = document.getElementById('showingEnd');
    var totalItems = document.getElementById('totalItems');
    if (showingStart) showingStart.textContent = data.items.length > 0 ? String((data.page - 1) * perPage + 1) : '0';
    if (showingEnd) showingEnd.textContent = String(Math.min(data.page * perPage, data.total));
    if (totalItems) totalItems.textContent = String(data.total);
  }

  /**
   * Render pagination controls dynamically.
   */
  function renderPagination(total, page, pages) {
    var paginationEl = document.querySelector('.pagination');
    if (!paginationEl) return;

    paginationEl.textContent = '';

    // Prev button
    var prevBtn = document.createElement('button');
    prevBtn.className = 'pagination-btn';
    prevBtn.id = 'prevPage';
    prevBtn.disabled = page <= 1;
    prevBtn.appendChild(createIcon('fa-chevron-left'));
    prevBtn.addEventListener('click', function () {
      if (page > 1) loadRiskRegister(page - 1, collectFilters());
    });
    paginationEl.appendChild(prevBtn);

    // Page buttons
    var pagesToShow = calculatePageRange(page, pages);
    pagesToShow.forEach(function (p) {
      if (p === '...') {
        var dots = document.createElement('span');
        dots.className = 'text-gray-400 px-2';
        dots.textContent = '...';
        paginationEl.appendChild(dots);
      } else {
        var btn = document.createElement('button');
        btn.className = 'pagination-btn';
        if (p === page) btn.classList.add('active');
        btn.textContent = String(p);
        btn.addEventListener('click', (function (pageNum) {
          return function () { loadRiskRegister(pageNum, collectFilters()); };
        })(p));
        paginationEl.appendChild(btn);
      }
    });

    // Next button
    var nextBtn = document.createElement('button');
    nextBtn.className = 'pagination-btn';
    nextBtn.id = 'nextPage';
    nextBtn.disabled = page >= pages;
    nextBtn.appendChild(createIcon('fa-chevron-right'));
    nextBtn.addEventListener('click', function () {
      if (page < pages) loadRiskRegister(page + 1, collectFilters());
    });
    paginationEl.appendChild(nextBtn);
  }

  /**
   * Calculate which page numbers to display.
   */
  function calculatePageRange(current, total) {
    if (total <= 7) {
      var arr = [];
      for (var i = 1; i <= total; i++) arr.push(i);
      return arr;
    }

    var pages = [1];
    if (current > 3) pages.push('...');

    var start = Math.max(2, current - 1);
    var end = Math.min(total - 1, current + 1);
    for (var j = start; j <= end; j++) pages.push(j);

    if (current < total - 2) pages.push('...');
    pages.push(total);

    return pages;
  }

  /**
   * Collect current filter values from the DOM.
   */
  function collectFilters() {
    return {
      severity: getSelectValue('severityFilter'),
      source: getSelectValue('sourceFilter'),
      domain: getSelectValue('domainFilter'),
      status: getSelectValue('statusFilter'),
      owner: getSelectValue('ownerFilter'),
      search: getInputValue('searchInput')
    };
  }

  /**
   * Apply filters and reload the risk table.
   */
  function applyFilters() {
    loadRiskRegister(1, collectFilters());
  }

  // ─── ACCEPTANCE WORKFLOW ────────────────────────────────────

  /**
   * Initialize the acceptance workflow page.
   * Loads pending requests from API.
   */
  async function initializeAcceptanceWorkflow() {
    try {
      var data = await window.URIP.apiFetch('/acceptance?status=pending');
      renderAcceptanceList(data);

      // Auto-select first if available
      if (data && data.length > 0) {
        selectRequest(data[0].id, data);
      }
    } catch (err) {
      window.URIP.showNotification('Error', 'Failed to load acceptance requests.', 'error');
    }
  }

  /**
   * Render acceptance request list.
   */
  function renderAcceptanceList(requests) {
    var listEl = document.getElementById('requestList');
    if (!listEl) return;

    listEl.textContent = '';

    if (!requests || requests.length === 0) {
      var empty = document.createElement('div');
      empty.className = 'empty-state';
      empty.style.padding = '2rem';

      var emptyIcon = document.createElement('div');
      emptyIcon.className = 'empty-state-icon';
      var iconEl = document.createElement('i');
      iconEl.className = 'fas fa-clipboard-check';
      emptyIcon.appendChild(iconEl);
      empty.appendChild(emptyIcon);

      var emptyTitle = document.createElement('div');
      emptyTitle.className = 'empty-state-title';
      emptyTitle.textContent = 'No pending requests';
      empty.appendChild(emptyTitle);

      listEl.appendChild(empty);
      return;
    }

    requests.forEach(function (req, idx) {
      var item = document.createElement('div');
      item.className = 'request-item';
      if (idx === 0) item.classList.add('active');
      item.setAttribute('data-id', req.id);

      var header = document.createElement('div');
      header.className = 'request-header';

      var idSpan = document.createElement('span');
      idSpan.className = 'request-id';
      idSpan.textContent = req.risk_detail ? req.risk_detail.risk_id : req.risk_id;
      header.appendChild(idSpan);

      var badge = document.createElement('span');
      var severity = req.risk_detail ? req.risk_detail.severity : 'medium';
      badge.className = 'badge badge-' + severity;
      badge.textContent = capitalizeFirst(severity);
      header.appendChild(badge);

      item.appendChild(header);

      var title = document.createElement('div');
      title.className = 'request-title';
      title.textContent = req.risk_detail ? req.risk_detail.finding : 'Risk Acceptance Request';
      item.appendChild(title);

      var meta = document.createElement('div');
      meta.className = 'request-meta';

      var requesterSpan = document.createElement('span');
      requesterSpan.textContent = 'By: ' + (req.requester_name || 'Unknown');
      meta.appendChild(requesterSpan);

      var dateSpan = document.createElement('span');
      dateSpan.textContent = formatDate(req.created_at);
      meta.appendChild(dateSpan);

      item.appendChild(meta);

      item.addEventListener('click', (function (requestId, requestsArr) {
        return function () {
          // Update active state
          var allItems = listEl.querySelectorAll('.request-item');
          allItems.forEach(function (el) { el.classList.remove('active'); });
          item.classList.add('active');
          selectRequest(requestId, requestsArr);
        };
      })(req.id, requests));

      listEl.appendChild(item);
    });
  }

  /**
   * Show detail panel for a selected acceptance request.
   *
   * @param {string} id - acceptance request ID
   * @param {Array} [allRequests] - cached request list to avoid extra API call
   */
  function selectRequest(id, allRequests) {
    var panel = document.getElementById('detailPanel');
    if (!panel) return;

    panel.textContent = '';

    // Find request in cached list or fetch
    var req = null;
    if (allRequests) {
      for (var i = 0; i < allRequests.length; i++) {
        if (allRequests[i].id === id) { req = allRequests[i]; break; }
      }
    }

    if (!req) {
      var loading = document.createElement('div');
      loading.className = 'detail-panel-body';
      loading.textContent = 'Loading...';
      panel.appendChild(loading);
      return;
    }

    // Header
    var headerDiv = document.createElement('div');
    headerDiv.className = 'detail-panel-header';

    var headerTitle = document.createElement('h3');
    headerTitle.textContent = 'Acceptance Request Details';
    headerDiv.appendChild(headerTitle);

    var riskIdLabel = document.createElement('div');
    riskIdLabel.className = 'risk-id';
    riskIdLabel.style.marginTop = '0.5rem';
    riskIdLabel.textContent = req.risk_detail ? req.risk_detail.risk_id : '';
    headerDiv.appendChild(riskIdLabel);

    panel.appendChild(headerDiv);

    // Body
    var body = document.createElement('div');
    body.className = 'detail-panel-body';

    // Risk info section
    if (req.risk_detail) {
      addDetailSection(body, 'Risk Information', [
        { label: 'Finding', value: req.risk_detail.finding },
        { label: 'CVSS Score', value: String(req.risk_detail.cvss_score || '-') },
        { label: 'Severity', value: capitalizeFirst(req.risk_detail.severity || '') },
        { label: 'Asset', value: req.risk_detail.asset || '-' },
        { label: 'Domain', value: capitalizeFirst(req.risk_detail.domain || '') }
      ]);
    }

    // Request info section
    addDetailSection(body, 'Request Details', [
      { label: 'Requested By', value: req.requester_name || 'Unknown' },
      { label: 'Team', value: req.requester_team || '-' },
      { label: 'Justification', value: req.justification || '-' },
      { label: 'Compensating Controls', value: req.compensating_controls || '-' },
      { label: 'Residual Risk', value: req.residual_risk || '-' },
      { label: 'Recommendation', value: req.recommendation || '-' }
    ]);

    // Action buttons
    var actions = document.createElement('div');
    actions.className = 'acceptance-actions';

    var approveBtn = document.createElement('button');
    approveBtn.className = 'btn btn-primary';
    var approveIcon = document.createElement('i');
    approveIcon.className = 'fas fa-check';
    approveBtn.appendChild(approveIcon);
    approveBtn.appendChild(document.createTextNode(' Approve'));
    approveBtn.addEventListener('click', function () { approveRequest(req.id); });
    actions.appendChild(approveBtn);

    var rejectBtn = document.createElement('button');
    rejectBtn.className = 'btn btn-danger';
    var rejectIcon = document.createElement('i');
    rejectIcon.className = 'fas fa-times';
    rejectBtn.appendChild(rejectIcon);
    rejectBtn.appendChild(document.createTextNode(' Reject'));
    rejectBtn.addEventListener('click', function () { rejectRequest(req.id); });
    actions.appendChild(rejectBtn);

    body.appendChild(actions);
    panel.appendChild(body);
  }

  /**
   * Approve an acceptance request.
   *
   * @param {string} id
   */
  async function approveRequest(id) {
    try {
      await window.URIP.apiFetch('/acceptance/' + id + '/approve', { method: 'POST' });
      window.URIP.showNotification('Approved', 'Risk acceptance request has been approved.', 'success');
      initializeAcceptanceWorkflow();
    } catch (err) {
      window.URIP.showNotification('Error', 'Failed to approve request: ' + (err.message || 'Unknown error'), 'error');
    }
  }

  /**
   * Reject an acceptance request.
   *
   * @param {string} id
   */
  async function rejectRequest(id) {
    try {
      await window.URIP.apiFetch('/acceptance/' + id + '/reject', {
        method: 'POST',
        body: JSON.stringify({ reason: 'Rejected by approver' })
      });
      window.URIP.showNotification('Rejected', 'Risk acceptance request has been rejected.', 'success');
      initializeAcceptanceWorkflow();
    } catch (err) {
      window.URIP.showNotification('Error', 'Failed to reject request: ' + (err.message || 'Unknown error'), 'error');
    }
  }

  // ─── HELPERS ────────────────────────────────────────────────

  function addDetailSection(parent, title, fields) {
    var section = document.createElement('div');
    section.className = 'detail-section';

    var heading = document.createElement('h4');
    heading.style.cssText = 'font-size:0.8125rem;font-weight:600;color:#475569;text-transform:uppercase;letter-spacing:0.05em;margin-bottom:0.75rem';
    heading.textContent = title;
    section.appendChild(heading);

    fields.forEach(function (f) {
      var row = document.createElement('div');
      row.style.cssText = 'display:flex;justify-content:space-between;margin-bottom:0.625rem;font-size:0.875rem';

      var label = document.createElement('span');
      label.style.color = '#64748B';
      label.textContent = f.label;
      row.appendChild(label);

      var value = document.createElement('span');
      value.style.cssText = 'font-weight:500;color:#1E293B;text-align:right;max-width:60%;word-break:break-word';
      value.textContent = f.value;
      row.appendChild(value);

      section.appendChild(row);
    });

    parent.appendChild(section);
  }

  function createIcon(iconClass) {
    var i = document.createElement('i');
    i.className = 'fas ' + iconClass;
    return i;
  }

  function capitalizeFirst(str) {
    if (!str) return '';
    return str.charAt(0).toUpperCase() + str.slice(1);
  }

  function formatStatus(status) {
    if (!status) return 'Open';
    return status.replace(/_/g, ' ').replace(/\b\w/g, function (c) { return c.toUpperCase(); });
  }

  function formatDate(dateStr) {
    if (!dateStr) return '-';
    try {
      var d = new Date(dateStr);
      return d.toLocaleDateString('en-US', { year: 'numeric', month: 'short', day: 'numeric' });
    } catch (_e) {
      return dateStr;
    }
  }

  function getDaysUntil(dateStr) {
    if (!dateStr) return 999;
    var target = new Date(dateStr);
    var now = new Date();
    return Math.ceil((target - now) / (1000 * 60 * 60 * 24));
  }

  function getCvssClass(score) {
    if (score >= 9.0) return 'cvss-critical';
    if (score >= 7.0) return 'cvss-high';
    if (score >= 4.0) return 'cvss-medium';
    return 'cvss-low';
  }

  function getSourceIcon(source) {
    var icons = {
      crowdstrike: 'fa-crow',
      easm: 'fa-globe',
      cnapp: 'fa-cloud',
      armis: 'fa-network-wired',
      vapt: 'fa-bug',
      threat_intel: 'fa-crosshairs',
      cert_in: 'fa-certificate',
      bug_bounty: 'fa-award',
      soc: 'fa-shield-alt'
    };
    return icons[source] || 'fa-database';
  }

  function formatSourceName(source) {
    var names = {
      crowdstrike: 'CrowdStrike',
      easm: 'EASM',
      cnapp: 'CNAPP',
      armis: 'Armis',
      vapt: 'VAPT',
      threat_intel: 'Threat Intel',
      cert_in: 'CERT-In',
      bug_bounty: 'Bug Bounty',
      soc: 'SoC'
    };
    return names[source] || capitalizeFirst(source || '');
  }

  function getInitials(teamName) {
    if (!teamName) return '?';
    var words = teamName.split(/[\s-]+/);
    if (words.length >= 2) {
      return (words[0][0] + words[1][0]).toUpperCase();
    }
    return teamName.substring(0, 2).toUpperCase();
  }

  function getSelectValue(id) {
    var el = document.getElementById(id);
    return el ? el.value : 'all';
  }

  function getInputValue(id) {
    var el = document.getElementById(id);
    return el ? el.value.trim() : '';
  }

  // ─── INIT ───────────────────────────────────────────────────

  document.addEventListener('DOMContentLoaded', function () {
    // Detect which page we're on
    var isRiskRegister = !!document.getElementById('riskTableBody');
    var isAcceptance = !!document.getElementById('requestList');

    if (isRiskRegister) {
      loadRiskRegister(1, collectFilters());

      // Attach filter change listeners
      ['severityFilter', 'sourceFilter', 'domainFilter', 'statusFilter', 'ownerFilter'].forEach(function (id) {
        var el = document.getElementById(id);
        if (el) el.addEventListener('change', applyFilters);
      });

      // Search input with debounce
      var searchInput = document.getElementById('searchInput');
      if (searchInput) {
        var debounceTimer;
        searchInput.addEventListener('input', function () {
          clearTimeout(debounceTimer);
          debounceTimer = setTimeout(applyFilters, 400);
        });
      }
    }

    if (isAcceptance) {
      initializeAcceptanceWorkflow();
    }
  });

  // Expose public API
  window.loadRiskRegister = loadRiskRegister;
  window.applyFilters = applyFilters;
  window.initializeAcceptanceWorkflow = initializeAcceptanceWorkflow;
  window.selectRequest = selectRequest;
  window.approveRequest = approveRequest;
  window.rejectRequest = rejectRequest;
})();
