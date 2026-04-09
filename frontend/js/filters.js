/**
 * URIP - Risk Register Filters, Sorting, Cascading Filters & Action Handlers
 * All data loaded from API. NO hardcoded riskData or acceptanceData.
 * All DOM via createElement + textContent (NO innerHTML with user data).
 * Depends on: api.js (window.URIP.apiFetch, window.URIP.showNotification)
 */
(function () {
  'use strict';

  var currentPage = 1;
  var perPage = 20;

  // ─── SORT STATE ─────────────────────────────────────────────

  var currentSortBy = 'composite_score';
  var currentSortOrder = 'desc';

  /**
   * Map of column header display text to API sort_by field name.
   * Only columns listed here are sortable.
   */
  var SORTABLE_COLUMNS = {
    'ID': 'risk_id',
    'Finding': 'finding',
    'Source': 'source',
    'Domain': 'domain',
    'CVSS': 'cvss_score',
    'EPSS': 'epss_score',
    'KEV': 'in_kev_catalog',
    'Composite': 'composite_score',
    'Severity': 'severity',
    'Asset': 'asset',
    'Asset Tier': 'asset_tier',
    'APT': 'cve_id',
    'Owner': 'owner_team',
    'Status': 'status',
    'SLA Due': 'sla_deadline'
  };

  // ─── RISK REGISTER ──────────────────────────────────────────

  /**
   * Load risks from API with filters, sorting, and pagination.
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

    // Sorting
    params.set('sort_by', currentSortBy);
    params.set('order', currentSortOrder);

    if (filters.severity && filters.severity !== 'all') params.set('severity', filters.severity);
    if (filters.source && filters.source !== 'all') params.set('source', filters.source);
    if (filters.domain && filters.domain !== 'all') params.set('domain', filters.domain);
    if (filters.status && filters.status !== 'all') params.set('status', filters.status);
    if (filters.owner && filters.owner !== 'all') params.set('owner', filters.owner);
    if (filters.search) params.set('search', filters.search);

    try {
      var data = await window.URIP.apiFetch('/risks?' + params.toString());
      renderRiskTable(data);
      updateSortHeaders();
      loadFilterOptions(filters);
    } catch (err) {
      window.URIP.showNotification('Error', 'Failed to load risk register.', 'error');
    }
  }

  // ─── SORTABLE COLUMN HEADERS ────────────────────────────────

  /**
   * Replace static <th> text with clickable sort headers.
   * Called once on DOMContentLoaded.
   */
  function initSortableHeaders() {
    var thead = document.querySelector('.risk-table thead tr');
    if (!thead) return;

    var ths = thead.querySelectorAll('th');
    ths.forEach(function (th) {
      var label = th.textContent.trim();
      var sortField = SORTABLE_COLUMNS[label];
      if (!sortField) return; // Not sortable (e.g. "Actions")

      th.textContent = '';
      th.style.cursor = 'pointer';
      th.style.userSelect = 'none';
      th.setAttribute('data-sort-field', sortField);

      var wrapper = document.createElement('span');
      wrapper.style.cssText = 'display:inline-flex;align-items:center;gap:6px';

      var textSpan = document.createElement('span');
      textSpan.textContent = label;
      wrapper.appendChild(textSpan);

      var iconEl = document.createElement('i');
      iconEl.className = 'fas fa-sort';
      iconEl.style.cssText = 'font-size:0.75rem;opacity:0.4';
      iconEl.setAttribute('data-sort-icon', sortField);
      wrapper.appendChild(iconEl);

      th.appendChild(wrapper);

      th.addEventListener('click', (function (field) {
        return function () {
          if (currentSortBy === field) {
            currentSortOrder = currentSortOrder === 'asc' ? 'desc' : 'asc';
          } else {
            currentSortBy = field;
            currentSortOrder = 'asc';
          }
          loadRiskRegister(1, collectFilters());
        };
      })(sortField));
    });
  }

  /**
   * Update sort arrow icons on column headers to reflect current sort state.
   */
  function updateSortHeaders() {
    var icons = document.querySelectorAll('[data-sort-icon]');
    icons.forEach(function (icon) {
      var field = icon.getAttribute('data-sort-icon');
      if (field === currentSortBy) {
        icon.className = currentSortOrder === 'asc'
          ? 'fas fa-sort-up'
          : 'fas fa-sort-down';
        icon.style.opacity = '1';
      } else {
        icon.className = 'fas fa-sort';
        icon.style.opacity = '0.4';
      }
    });
  }

  // ─── CASCADING / DYNAMIC FILTERS ────────────────────────────

  /**
   * After a filter change, fetch the full filtered dataset (high per_page)
   * and update dropdown options for the OTHER filters to show only
   * values that exist in the current result set.
   *
   * @param {object} currentFilters - the filters currently applied
   */
  async function loadFilterOptions(currentFilters) {
    currentFilters = currentFilters || {};

    // Build query with current filters but large page to get all matching IDs
    var params = new URLSearchParams();
    params.set('page', '1');
    params.set('per_page', '2000');

    if (currentFilters.severity && currentFilters.severity !== 'all') params.set('severity', currentFilters.severity);
    if (currentFilters.source && currentFilters.source !== 'all') params.set('source', currentFilters.source);
    if (currentFilters.domain && currentFilters.domain !== 'all') params.set('domain', currentFilters.domain);
    if (currentFilters.status && currentFilters.status !== 'all') params.set('status', currentFilters.status);
    if (currentFilters.owner && currentFilters.owner !== 'all') params.set('owner', currentFilters.owner);
    if (currentFilters.search) params.set('search', currentFilters.search);

    try {
      var data = await window.URIP.apiFetch('/risks?' + params.toString());
      if (!data || !data.items) return;

      var items = data.items;

      // Extract unique values for each filter dimension
      var uniqueSeverities = extractUnique(items, 'severity');
      var uniqueSources = extractUnique(items, 'source');
      var uniqueDomains = extractUnique(items, 'domain');
      var uniqueStatuses = extractUnique(items, 'status');
      var uniqueOwners = extractUnique(items, 'owner_team');

      // Update each filter dropdown — but only for filters that are NOT currently selected
      // (don't change the dropdown for a filter that is actively filtering)
      if (!currentFilters.severity || currentFilters.severity === 'all') {
        updateFilterDropdown('severityFilter', uniqueSeverities, 'All Severities', capitalizeFirst);
      }
      if (!currentFilters.source || currentFilters.source === 'all') {
        updateFilterDropdown('sourceFilter', uniqueSources, 'All Sources', formatSourceName);
      }
      if (!currentFilters.domain || currentFilters.domain === 'all') {
        updateFilterDropdown('domainFilter', uniqueDomains, 'All Domains', capitalizeFirst);
      }
      if (!currentFilters.status || currentFilters.status === 'all') {
        updateFilterDropdown('statusFilter', uniqueStatuses, 'All Status', formatStatus);
      }
      if (!currentFilters.owner || currentFilters.owner === 'all') {
        updateFilterDropdown('ownerFilter', uniqueOwners, 'All Owners', formatOwnerName);
      }
    } catch (_err) {
      // Silent fail — filter options stay as-is
    }
  }

  /**
   * Extract unique non-empty values from an array of objects by key.
   *
   * @param {Array} items
   * @param {string} key
   * @returns {string[]} sorted unique values
   */
  function extractUnique(items, key) {
    var seen = {};
    items.forEach(function (item) {
      var val = item[key];
      if (val && val !== '') {
        seen[val] = true;
      }
    });
    return Object.keys(seen).sort();
  }

  /**
   * Update a <select> dropdown with new option values while preserving the current selection.
   *
   * @param {string} selectId - DOM id of the <select>
   * @param {string[]} values - available option values
   * @param {string} allLabel - label for the "all" option
   * @param {function} formatFn - function to format display text from value
   */
  function updateFilterDropdown(selectId, values, allLabel, formatFn) {
    var select = document.getElementById(selectId);
    if (!select) return;

    var currentValue = select.value;

    // Remove all options except the first "all" option
    select.textContent = '';

    // Re-add "all" option
    var allOpt = document.createElement('option');
    allOpt.value = 'all';
    allOpt.textContent = allLabel;
    select.appendChild(allOpt);

    // Add available values
    values.forEach(function (val) {
      var opt = document.createElement('option');
      opt.value = val;
      opt.textContent = formatFn(val);
      select.appendChild(opt);
    });

    // Restore previous selection if it still exists
    if (currentValue && currentValue !== 'all') {
      var exists = values.indexOf(currentValue) !== -1;
      if (exists) {
        select.value = currentValue;
      } else {
        select.value = 'all';
      }
    }
  }

  /**
   * Format owner team name for display.
   */
  function formatOwnerName(name) {
    if (!name) return '';
    return name.replace(/[-_]/g, ' ').replace(/\b\w/g, function (c) { return c.toUpperCase(); });
  }

  // ─── RISK TABLE RENDERING ──────────────────────────────────

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
      emptyCell.setAttribute('colspan', '17');
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

        // CVSS column
        var tdCvss = document.createElement('td');
        var cvssSpan = document.createElement('span');
        cvssSpan.className = 'cvss-score ' + getCvssClass(risk.cvss_score);
        cvssSpan.textContent = (risk.cvss_score || 0).toFixed(1);
        tdCvss.appendChild(cvssSpan);
        tr.appendChild(tdCvss);

        // EPSS column
        var tdEpss = document.createElement('td');
        if (risk.epss_score != null) {
          var epssWrapper = document.createElement('div');
          epssWrapper.style.cssText = 'display:flex;flex-direction:column;gap:2px';
          var epssScore = document.createElement('span');
          epssScore.style.cssText = 'font-weight:600;font-size:0.8125rem;color:#1E293B';
          epssScore.textContent = (risk.epss_score * 100).toFixed(1) + '%';
          epssWrapper.appendChild(epssScore);
          if (risk.epss_percentile != null) {
            var epssPct = document.createElement('span');
            epssPct.style.cssText = 'font-size:0.6875rem;color:#94A3B8';
            epssPct.textContent = Math.round(risk.epss_percentile) + 'th pctl';
            epssWrapper.appendChild(epssPct);
          }
          tdEpss.appendChild(epssWrapper);
        } else {
          tdEpss.style.cssText = 'color:#CBD5E1;font-size:0.8125rem';
          tdEpss.textContent = '-';
        }
        tr.appendChild(tdEpss);

        // KEV column
        var tdKev = document.createElement('td');
        if (risk.in_kev_catalog) {
          var kevBadge = document.createElement('span');
          kevBadge.style.cssText = 'display:inline-block;padding:2px 8px;border-radius:4px;font-size:0.6875rem;font-weight:700;background:#DC2626;color:#fff';
          kevBadge.textContent = 'YES';
          tdKev.appendChild(kevBadge);
        } else {
          var kevNo = document.createElement('span');
          kevNo.style.cssText = 'color:#CBD5E1;font-size:0.8125rem';
          kevNo.textContent = 'No';
          tdKev.appendChild(kevNo);
        }
        tr.appendChild(tdKev);

        // Composite column
        var tdComposite = document.createElement('td');
        if (risk.composite_score != null) {
          var compWrapper = document.createElement('div');
          compWrapper.style.cssText = 'display:flex;align-items:center;gap:6px';
          var compScore = document.createElement('span');
          compScore.className = 'cvss-score ' + getCvssClass(risk.composite_score);
          compScore.style.fontWeight = '700';
          compScore.textContent = risk.composite_score.toFixed(1);
          compWrapper.appendChild(compScore);
          // Exploit status badge
          if (risk.exploit_status === 'weaponized') {
            var weapBadge = document.createElement('span');
            weapBadge.style.cssText = 'display:inline-block;padding:1px 5px;border-radius:3px;font-size:0.5625rem;font-weight:700;background:#DC2626;color:#fff';
            weapBadge.textContent = 'WEAPONIZED';
            compWrapper.appendChild(weapBadge);
          } else if (risk.exploit_status === 'active') {
            var actBadge = document.createElement('span');
            actBadge.style.cssText = 'display:inline-block;padding:1px 5px;border-radius:3px;font-size:0.5625rem;font-weight:700;background:#EA580C;color:#fff';
            actBadge.textContent = 'ACTIVE';
            compWrapper.appendChild(actBadge);
          } else if (risk.exploit_status === 'poc') {
            var pocBadge = document.createElement('span');
            pocBadge.style.cssText = 'display:inline-block;padding:1px 5px;border-radius:3px;font-size:0.5625rem;font-weight:700;background:#D97706;color:#fff';
            pocBadge.textContent = 'POC';
            compWrapper.appendChild(pocBadge);
          }
          tdComposite.appendChild(compWrapper);
        } else {
          tdComposite.style.cssText = 'color:#CBD5E1;font-size:0.8125rem';
          tdComposite.textContent = '-';
        }
        tr.appendChild(tdComposite);

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

        // Asset Tier
        var tdTier = document.createElement('td');
        var tierLabels = { 1: 'Critical', 2: 'High', 3: 'Medium', 4: 'Low' };
        var tierColors = { 1: '#DC2626', 2: '#EA580C', 3: '#64748B', 4: '#94A3B8' };
        var tierBonuses = { 1: '+1.0', 2: '+0.5', 3: '0.0', 4: '-0.5' };
        var tier = risk.asset_tier || 3;
        var tierBadge = document.createElement('div');
        tierBadge.style.cssText = 'display:flex;flex-direction:column;gap:2px';
        var tierLabel = document.createElement('span');
        tierLabel.style.cssText = 'display:inline-block;padding:2px 8px;border-radius:4px;font-size:0.6875rem;font-weight:600;color:#fff;background:' + (tierColors[tier] || tierColors[3]);
        tierLabel.textContent = 'T' + tier + ' ' + (tierLabels[tier] || 'Medium');
        tierBadge.appendChild(tierLabel);
        var tierBonus = document.createElement('span');
        tierBonus.style.cssText = 'font-size:0.625rem;color:#94A3B8;text-align:center';
        tierBonus.textContent = tierBonuses[tier] || '0.0';
        tierBadge.appendChild(tierBonus);
        tdTier.appendChild(tierBadge);
        tr.appendChild(tdTier);

        // APT Groups
        var tdApt = document.createElement('td');
        if (risk.apt_groups && risk.apt_groups.length > 0) {
          var aptWrapper = document.createElement('div');
          aptWrapper.style.cssText = 'display:flex;flex-wrap:wrap;gap:3px';
          risk.apt_groups.forEach(function (apt) {
            var aptBadge = document.createElement('span');
            var countryCode = '';
            if (apt.country === 'Russia') countryCode = 'RU';
            else if (apt.country === 'China') countryCode = 'CN';
            else if (apt.country === 'North Korea') countryCode = 'KP';
            else if (apt.country === 'Iran') countryCode = 'IR';
            else if (apt.country === 'Various') countryCode = '--';
            else if (apt.country === 'Unknown') countryCode = '??';
            else countryCode = apt.country ? apt.country.substring(0, 2).toUpperCase() : '';

            var bgColor = '#6366F1';
            if (apt.country === 'Russia') bgColor = '#DC2626';
            else if (apt.country === 'China') bgColor = '#EA580C';
            else if (apt.country === 'North Korea') bgColor = '#7C3AED';
            else if (apt.country === 'Iran') bgColor = '#059669';
            else if (apt.country === 'Various') bgColor = '#64748B';

            aptBadge.style.cssText = 'display:inline-block;padding:2px 6px;border-radius:4px;font-size:0.625rem;font-weight:600;color:#fff;background:' + bgColor + ';white-space:nowrap';
            aptBadge.textContent = apt.name + ' (' + countryCode + ')';
            aptBadge.title = (apt.aliases && apt.aliases.length > 0 ? 'AKA: ' + apt.aliases.join(', ') + ' | ' : '') + 'Targets: ' + (apt.sectors ? apt.sectors.join(', ') : 'Unknown');
            aptWrapper.appendChild(aptBadge);
          });
          tdApt.appendChild(aptWrapper);
        } else {
          tdApt.style.cssText = 'color:#CBD5E1;font-size:0.8125rem';
          tdApt.textContent = '-';
        }
        tr.appendChild(tdApt);

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
        var statusClass = 'status-' + (risk.status || 'open').replace(/_/g, '-');
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

        // Notes (Jira Ticket)
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
        viewBtn.addEventListener('click', (function (riskId) {
          return function (e) {
            e.stopPropagation();
            showRiskDetailModal(riskId);
          };
        })(risk.risk_id));
        actionsDiv.appendChild(viewBtn);

        var assignBtn = document.createElement('button');
        assignBtn.className = 'action-btn assign';
        assignBtn.title = 'Assign';
        assignBtn.appendChild(createIcon('fa-user-plus'));
        assignBtn.addEventListener('click', (function (riskId) {
          return function (e) {
            e.stopPropagation();
            showAssignModal(riskId, e.currentTarget);
          };
        })(risk.risk_id));
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

  // ─── VIEW DETAIL MODAL ─────────────────────────────────────

  /**
   * Fetch full risk details and display in a modal overlay.
   *
   * @param {string} riskId - e.g. "RISK-001"
   */
  async function showRiskDetailModal(riskId) {
    // Remove any existing modal
    closeModal('urip-risk-detail-modal');

    // Create overlay
    var overlay = document.createElement('div');
    overlay.id = 'urip-risk-detail-modal';
    overlay.style.cssText =
      'position:fixed;top:0;left:0;width:100%;height:100%;' +
      'background:rgba(0,0,0,0.5);z-index:10000;display:flex;' +
      'align-items:center;justify-content:center;padding:20px';

    // Close on overlay click
    overlay.addEventListener('click', function (e) {
      if (e.target === overlay) closeModal('urip-risk-detail-modal');
    });

    // Modal box
    var modal = document.createElement('div');
    modal.style.cssText =
      'background:#fff;border-radius:12px;width:100%;max-width:680px;' +
      'max-height:85vh;overflow-y:auto;box-shadow:0 20px 60px rgba(0,0,0,0.3);' +
      'padding:0';

    // Loading state
    var loadingDiv = document.createElement('div');
    loadingDiv.style.cssText = 'padding:40px;text-align:center;color:#64748B';
    loadingDiv.textContent = 'Loading risk details...';
    modal.appendChild(loadingDiv);
    overlay.appendChild(modal);
    document.body.appendChild(overlay);

    try {
      var data = await window.URIP.apiFetch('/risks/' + encodeURIComponent(riskId));
      modal.textContent = '';
      renderRiskDetailContent(modal, data);
    } catch (err) {
      modal.textContent = '';
      var errorDiv = document.createElement('div');
      errorDiv.style.cssText = 'padding:40px;text-align:center;color:#E74C3C';
      errorDiv.textContent = 'Failed to load risk details: ' + (err.message || 'Unknown error');
      modal.appendChild(errorDiv);

      var closeBtn = document.createElement('button');
      closeBtn.textContent = 'Close';
      closeBtn.style.cssText =
        'display:block;margin:0 auto 20px;padding:8px 24px;border:none;' +
        'background:#64748B;color:#fff;border-radius:6px;cursor:pointer';
      closeBtn.addEventListener('click', function () { closeModal('urip-risk-detail-modal'); });
      modal.appendChild(closeBtn);
    }
  }

  /**
   * Populate the detail modal with risk information and history.
   *
   * @param {HTMLElement} modal
   * @param {object} data - API response from /risks/{risk_id}, may contain .risk and .history
   */
  function renderRiskDetailContent(modal, data) {
    // The API may return { risk: {...}, history: [...] } or just the risk object
    var risk = data.risk || data;
    var history = data.history || [];

    // Header bar
    var header = document.createElement('div');
    header.style.cssText =
      'display:flex;align-items:center;justify-content:space-between;' +
      'padding:20px 24px;border-bottom:1px solid #E2E8F0';

    var titleDiv = document.createElement('div');
    var titleH3 = document.createElement('h3');
    titleH3.style.cssText = 'margin:0;font-size:1.125rem;font-weight:600;color:#1E293B';
    titleH3.textContent = 'Risk Details';
    titleDiv.appendChild(titleH3);

    var idBadge = document.createElement('span');
    idBadge.style.cssText =
      'display:inline-block;margin-top:4px;font-size:0.8125rem;' +
      'color:#6366F1;font-weight:500';
    idBadge.textContent = risk.risk_id || '';
    titleDiv.appendChild(idBadge);
    header.appendChild(titleDiv);

    var closeBtn = document.createElement('button');
    closeBtn.style.cssText =
      'background:none;border:none;font-size:1.25rem;color:#94A3B8;' +
      'cursor:pointer;padding:4px 8px;border-radius:4px';
    closeBtn.textContent = '\u00D7'; // multiplication sign as close icon
    closeBtn.title = 'Close';
    closeBtn.addEventListener('click', function () { closeModal('urip-risk-detail-modal'); });
    header.appendChild(closeBtn);
    modal.appendChild(header);

    // Body
    var body = document.createElement('div');
    body.style.cssText = 'padding:24px';

    // Main detail fields
    var compositeText = risk.composite_score != null ? String(risk.composite_score) : '-';
    var epssText = risk.epss_score != null ? String(risk.epss_score) : '-';
    var epssPercentileText = risk.epss_percentile != null ? (Math.round(risk.epss_percentile) + 'th percentile') : '-';
    var kevText = risk.in_kev_catalog ? 'Yes (CISA KEV)' : 'No';
    var exploitText = risk.exploit_status ? capitalizeFirst(risk.exploit_status) : '-';

    var fields = [
      { label: 'Risk ID', value: risk.risk_id },
      { label: 'Finding', value: risk.finding },
      { label: 'Description', value: risk.description },
      { label: 'Source', value: formatSourceName(risk.source) },
      { label: 'Domain', value: capitalizeFirst(risk.domain) },
      { label: 'CVSS Score', value: risk.cvss_score != null ? String(risk.cvss_score) : '-' },
      { label: 'Composite Score', value: compositeText },
      { label: 'Severity', value: capitalizeFirst(risk.severity) },
      { label: 'EPSS Score', value: epssText },
      { label: 'EPSS Percentile', value: epssPercentileText },
      { label: 'In KEV Catalog', value: kevText },
      { label: 'Exploit Status', value: exploitText },
      { label: 'Asset', value: risk.asset || '-' },
      { label: 'Owner Team', value: risk.owner_team || '-' },
      { label: 'Status', value: formatStatus(risk.status) },
      { label: 'SLA Deadline', value: formatDate(risk.sla_deadline) },
      { label: 'Jira Ticket', value: risk.jira_ticket || '-' },
      { label: 'CVE ID', value: risk.cve_id || '-' },
      { label: 'Created At', value: formatDate(risk.created_at) }
    ];

    var grid = document.createElement('div');
    grid.style.cssText =
      'display:grid;grid-template-columns:1fr 1fr;gap:12px 24px;margin-bottom:24px';

    fields.forEach(function (f) {
      var fieldDiv = document.createElement('div');

      var labelEl = document.createElement('div');
      labelEl.style.cssText = 'font-size:0.75rem;font-weight:500;color:#94A3B8;text-transform:uppercase;letter-spacing:0.05em;margin-bottom:2px';
      labelEl.textContent = f.label;

      var valueEl = document.createElement('div');
      valueEl.style.cssText = 'font-size:0.875rem;color:#1E293B;word-break:break-word';
      valueEl.textContent = f.value || '-';

      // Special styling for description — full width
      if (f.label === 'Description' || f.label === 'Finding') {
        fieldDiv.style.gridColumn = '1 / -1';
      }

      fieldDiv.appendChild(labelEl);
      fieldDiv.appendChild(valueEl);
      grid.appendChild(fieldDiv);
    });

    body.appendChild(grid);

    // History section
    if (history.length > 0) {
      var historySection = document.createElement('div');
      historySection.style.cssText = 'border-top:1px solid #E2E8F0;padding-top:20px';

      var historyTitle = document.createElement('h4');
      historyTitle.style.cssText =
        'font-size:0.8125rem;font-weight:600;color:#475569;' +
        'text-transform:uppercase;letter-spacing:0.05em;margin:0 0 12px';
      historyTitle.textContent = 'Change History';
      historySection.appendChild(historyTitle);

      history.forEach(function (entry) {
        var entryDiv = document.createElement('div');
        entryDiv.style.cssText =
          'display:flex;gap:12px;padding:10px 0;border-bottom:1px solid #F1F5F9;font-size:0.8125rem';

        var timeDiv = document.createElement('div');
        timeDiv.style.cssText = 'color:#94A3B8;min-width:120px;flex-shrink:0';
        timeDiv.textContent = formatDate(entry.changed_at || entry.timestamp || entry.created_at);

        var detailDiv = document.createElement('div');
        detailDiv.style.cssText = 'color:#1E293B;flex:1';

        var userSpan = document.createElement('span');
        userSpan.style.cssText = 'font-weight:500';
        userSpan.textContent = entry.changed_by || entry.user || 'System';
        detailDiv.appendChild(userSpan);

        var actionText = document.createTextNode(
          ' changed ' + (entry.field || 'status') +
          (entry.old_value ? ' from "' + entry.old_value + '"' : '') +
          (entry.new_value ? ' to "' + entry.new_value + '"' : '')
        );
        detailDiv.appendChild(actionText);

        entryDiv.appendChild(timeDiv);
        entryDiv.appendChild(detailDiv);
        historySection.appendChild(entryDiv);
      });

      body.appendChild(historySection);
    }

    modal.appendChild(body);

    // Footer with close button
    var footer = document.createElement('div');
    footer.style.cssText =
      'padding:16px 24px;border-top:1px solid #E2E8F0;text-align:right';

    var footerCloseBtn = document.createElement('button');
    footerCloseBtn.style.cssText =
      'padding:8px 24px;border:1px solid #CBD5E1;background:#fff;' +
      'color:#475569;border-radius:6px;cursor:pointer;font-size:0.875rem;font-weight:500';
    footerCloseBtn.textContent = 'Close';
    footerCloseBtn.addEventListener('click', function () { closeModal('urip-risk-detail-modal'); });
    footer.appendChild(footerCloseBtn);
    modal.appendChild(footer);
  }

  // ─── ASSIGN MODAL ──────────────────────────────────────────

  /**
   * Show a small dropdown modal to assign a user to a risk.
   *
   * @param {string} riskId
   * @param {HTMLElement} anchorBtn - the button that was clicked, for positioning
   */
  async function showAssignModal(riskId, anchorBtn) {
    // Remove any existing assign modal
    closeModal('urip-assign-modal');

    // Create overlay
    var overlay = document.createElement('div');
    overlay.id = 'urip-assign-modal';
    overlay.style.cssText =
      'position:fixed;top:0;left:0;width:100%;height:100%;' +
      'background:rgba(0,0,0,0.3);z-index:10000;display:flex;' +
      'align-items:center;justify-content:center;padding:20px';

    overlay.addEventListener('click', function (e) {
      if (e.target === overlay) closeModal('urip-assign-modal');
    });

    // Modal box
    var modal = document.createElement('div');
    modal.style.cssText =
      'background:#fff;border-radius:10px;width:100%;max-width:400px;' +
      'box-shadow:0 20px 60px rgba(0,0,0,0.25);overflow:hidden';

    // Header
    var header = document.createElement('div');
    header.style.cssText =
      'display:flex;align-items:center;justify-content:space-between;' +
      'padding:16px 20px;border-bottom:1px solid #E2E8F0';

    var titleEl = document.createElement('h4');
    titleEl.style.cssText = 'margin:0;font-size:0.9375rem;font-weight:600;color:#1E293B';
    titleEl.textContent = 'Assign Risk ' + riskId;
    header.appendChild(titleEl);

    var closeBtn = document.createElement('button');
    closeBtn.style.cssText =
      'background:none;border:none;font-size:1.125rem;color:#94A3B8;cursor:pointer;padding:2px 6px';
    closeBtn.textContent = '\u00D7';
    closeBtn.addEventListener('click', function () { closeModal('urip-assign-modal'); });
    header.appendChild(closeBtn);
    modal.appendChild(header);

    // Body — loading state
    var body = document.createElement('div');
    body.style.cssText = 'padding:16px 20px;max-height:320px;overflow-y:auto';

    var loadingText = document.createElement('div');
    loadingText.style.cssText = 'text-align:center;color:#64748B;padding:12px';
    loadingText.textContent = 'Loading users...';
    body.appendChild(loadingText);
    modal.appendChild(body);
    overlay.appendChild(modal);
    document.body.appendChild(overlay);

    // Fetch users
    try {
      var users = await window.URIP.apiFetch('/settings/users');
      body.textContent = '';

      // users may be an array or { items: [...] }
      var userList = Array.isArray(users) ? users : (users.items || users.users || []);

      if (userList.length === 0) {
        var noUsers = document.createElement('div');
        noUsers.style.cssText = 'text-align:center;color:#94A3B8;padding:12px';
        noUsers.textContent = 'No users available.';
        body.appendChild(noUsers);
        return;
      }

      userList.forEach(function (user) {
        var userRow = document.createElement('div');
        userRow.style.cssText =
          'display:flex;align-items:center;gap:12px;padding:10px 12px;' +
          'border-radius:6px;cursor:pointer;transition:background 0.15s';

        userRow.addEventListener('mouseenter', function () {
          userRow.style.background = '#F1F5F9';
        });
        userRow.addEventListener('mouseleave', function () {
          userRow.style.background = 'transparent';
        });

        // Avatar
        var avatar = document.createElement('div');
        avatar.style.cssText =
          'width:36px;height:36px;border-radius:50%;background:#6366F1;' +
          'color:#fff;display:flex;align-items:center;justify-content:center;' +
          'font-size:0.8125rem;font-weight:600;flex-shrink:0';
        avatar.textContent = getInitials(user.name || user.username || '');

        var infoDiv = document.createElement('div');
        infoDiv.style.cssText = 'flex:1;min-width:0';

        var nameEl = document.createElement('div');
        nameEl.style.cssText = 'font-size:0.875rem;font-weight:500;color:#1E293B';
        nameEl.textContent = user.name || user.username || 'Unknown';

        var roleEl = document.createElement('div');
        roleEl.style.cssText = 'font-size:0.75rem;color:#94A3B8';
        roleEl.textContent = user.role || user.team || '';

        infoDiv.appendChild(nameEl);
        infoDiv.appendChild(roleEl);

        userRow.appendChild(avatar);
        userRow.appendChild(infoDiv);

        userRow.addEventListener('click', (function (userId, userName) {
          return function () {
            assignRiskToUser(riskId, userId, userName);
          };
        })(user.id, user.name || user.username));

        body.appendChild(userRow);
      });
    } catch (err) {
      body.textContent = '';
      var errorDiv = document.createElement('div');
      errorDiv.style.cssText = 'text-align:center;color:#E74C3C;padding:12px';
      errorDiv.textContent = 'Failed to load users: ' + (err.message || 'Unknown error');
      body.appendChild(errorDiv);
    }
  }

  /**
   * POST assignment of a user to a risk, then close the modal and reload.
   *
   * @param {string} riskId
   * @param {string} userId
   * @param {string} userName
   */
  async function assignRiskToUser(riskId, userId, userName) {
    try {
      await window.URIP.apiFetch('/risks/' + encodeURIComponent(riskId) + '/assign', {
        method: 'POST',
        body: JSON.stringify({ user_id: userId })
      });
      closeModal('urip-assign-modal');
      window.URIP.showNotification(
        'Assigned',
        'Risk ' + riskId + ' assigned to ' + userName + '.',
        'success'
      );
      // Reload the table to reflect the change
      loadRiskRegister(currentPage, collectFilters());
    } catch (err) {
      window.URIP.showNotification(
        'Error',
        'Failed to assign risk: ' + (err.message || 'Unknown error'),
        'error'
      );
    }
  }

  // ─── MODAL HELPERS ─────────────────────────────────────────

  /**
   * Close and remove a modal overlay by ID.
   *
   * @param {string} modalId
   */
  function closeModal(modalId) {
    var existing = document.getElementById(modalId);
    if (existing && existing.parentNode) {
      existing.parentNode.removeChild(existing);
    }
  }

  // ─── PAGINATION ─────────────────────────────────────────────

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
      // Initialize sortable column headers before first load
      initSortableHeaders();

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
  window.showRiskDetailModal = showRiskDetailModal;
  window.showAssignModal = showAssignModal;
})();
