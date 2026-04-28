/**
 * URIP - Audit Log
 * Loads audit log entries from API with filtering.
 * All DOM via createElement + textContent (NO innerHTML).
 * Depends on: api.js (window.URIP.apiFetch, window.URIP.showNotification)
 */
(function () {
  'use strict';

  var currentPage = 1;
  var perPage = 20;

  // Action display names
  var ACTION_LABELS = {
    risk_created: 'Risk Created',
    risk_updated: 'Risk Updated',
    risk_assigned: 'Risk Assigned',
    acceptance_requested: 'Acceptance Requested',
    acceptance_approved: 'Acceptance Approved',
    acceptance_rejected: 'Acceptance Rejected',
    remediation_created: 'Remediation Created',
    remediation_updated: 'Remediation Updated',
    user_login: 'User Login',
    user_created: 'User Created',
    connector_tested: 'Connector Tested'
  };

  // Resource type icons
  var RESOURCE_ICONS = {
    risk: 'fa-exclamation-triangle',
    acceptance: 'fa-clipboard-check',
    remediation: 'fa-tasks',
    user: 'fa-user',
    connector: 'fa-plug'
  };

  /**
   * Load audit logs from API.
   *
   * @param {number} [page=1]
   * @param {object} [filters] - { resource_type, action }
   */
  async function loadAuditLogs(page, filters) {
    page = page || 1;
    filters = filters || {};
    currentPage = page;

    var params = new URLSearchParams();
    params.set('page', String(page));
    params.set('per_page', String(perPage));

    if (filters.resource_type && filters.resource_type !== 'all') {
      params.set('resource_type', filters.resource_type);
    }
    if (filters.action && filters.action !== 'all') {
      params.set('action', filters.action);
    }

    try {
      var data = await window.URIP.apiFetch('/audit-log?' + params.toString());
      renderAuditTable(data);
    } catch (err) {
      window.URIP.showNotification('Error', 'Failed to load audit logs.', 'error');
    }
  }

  /**
   * Render audit log table.
   * Columns: Timestamp, User, Action, Resource Type, Details, IP Address
   *
   * @param {object} data - { items, total, page, pages }
   */
  function renderAuditTable(data) {
    var tbody = document.getElementById('auditTableBody');
    if (!tbody) return;

    tbody.textContent = '';

    if (!data.items || data.items.length === 0) {
      var emptyRow = document.createElement('tr');
      var emptyCell = document.createElement('td');
      emptyCell.setAttribute('colspan', '6');

      var emptyState = document.createElement('div');
      emptyState.className = 'empty-state';

      var emptyIcon = document.createElement('div');
      emptyIcon.className = 'empty-state-icon';
      var iconEl = document.createElement('i');
      iconEl.className = 'fas fa-history';
      emptyIcon.appendChild(iconEl);
      emptyState.appendChild(emptyIcon);

      var emptyTitle = document.createElement('div');
      emptyTitle.className = 'empty-state-title';
      emptyTitle.textContent = 'No audit logs found';
      emptyState.appendChild(emptyTitle);

      var emptyText = document.createElement('div');
      emptyText.className = 'empty-state-text';
      emptyText.textContent = 'Try adjusting your filters.';
      emptyState.appendChild(emptyText);

      emptyCell.appendChild(emptyState);
      emptyRow.appendChild(emptyCell);
      tbody.appendChild(emptyRow);
      return;
    }

    data.items.forEach(function (log) {
      var tr = document.createElement('tr');

      // Timestamp
      var tdTime = document.createElement('td');
      var timeDiv = document.createElement('div');
      timeDiv.style.cssText = 'font-size:0.8125rem;color:#1E293B';
      timeDiv.textContent = formatDateTime(log.created_at);
      tdTime.appendChild(timeDiv);
      tr.appendChild(tdTime);

      // User
      var tdUser = document.createElement('td');
      var userDiv = document.createElement('div');
      userDiv.className = 'risk-owner';

      var avatar = document.createElement('div');
      avatar.className = 'owner-avatar';
      avatar.textContent = getInitials(log.user_name || '');
      userDiv.appendChild(avatar);

      var userInfo = document.createElement('div');
      var userName = document.createElement('div');
      userName.style.fontWeight = '500';
      userName.textContent = log.user_name || 'Unknown';
      userInfo.appendChild(userName);

      if (log.user_role) {
        var userRole = document.createElement('div');
        userRole.style.cssText = 'font-size:0.75rem;color:#64748B';
        userRole.textContent = log.user_role.toUpperCase();
        userInfo.appendChild(userRole);
      }

      userDiv.appendChild(userInfo);
      tdUser.appendChild(userDiv);
      tr.appendChild(tdUser);

      // Action
      var tdAction = document.createElement('td');
      var actionBadge = document.createElement('span');
      actionBadge.className = 'badge badge-info';
      actionBadge.textContent = ACTION_LABELS[log.action] || formatActionName(log.action);
      tdAction.appendChild(actionBadge);
      tr.appendChild(tdAction);

      // Resource Type
      var tdResource = document.createElement('td');
      var resourceDiv = document.createElement('div');
      resourceDiv.style.cssText = 'display:flex;align-items:center;gap:0.5rem';

      var resourceIcon = document.createElement('div');
      resourceIcon.className = 'source-icon';
      var rIcon = document.createElement('i');
      rIcon.className = 'fas ' + (RESOURCE_ICONS[log.resource_type] || 'fa-file');
      resourceIcon.appendChild(rIcon);
      resourceDiv.appendChild(resourceIcon);

      var resourceText = document.createElement('span');
      resourceText.textContent = capitalizeFirst(log.resource_type || '-');
      resourceDiv.appendChild(resourceText);

      tdResource.appendChild(resourceDiv);
      tr.appendChild(tdResource);

      // Details
      var tdDetails = document.createElement('td');
      var detailsText = document.createElement('span');
      detailsText.style.cssText = 'font-size:0.8125rem;color:#475569;max-width:250px;display:block;overflow:hidden;text-overflow:ellipsis;white-space:nowrap';
      if (log.details && typeof log.details === 'object') {
        detailsText.textContent = summarizeDetails(log.details);
      } else {
        detailsText.textContent = '-';
      }
      detailsText.title = log.details ? JSON.stringify(log.details) : '';
      tdDetails.appendChild(detailsText);
      tr.appendChild(tdDetails);

      // IP Address
      var tdIP = document.createElement('td');
      var ipSpan = document.createElement('span');
      ipSpan.style.cssText = 'font-family:"SF Mono",monospace;font-size:0.8125rem;color:#64748B';
      ipSpan.textContent = log.ip_address || '-';
      tdIP.appendChild(ipSpan);
      tr.appendChild(tdIP);

      tbody.appendChild(tr);
    });

    // Pagination
    renderAuditPagination(data.total, data.page, data.pages);

    // Showing info
    var showingInfo = document.getElementById('auditShowingInfo');
    if (showingInfo) {
      var start = data.items.length > 0 ? (data.page - 1) * perPage + 1 : 0;
      var end = Math.min(data.page * perPage, data.total);
      showingInfo.textContent = 'Showing ' + start + '-' + end + ' of ' + data.total + ' entries';
    }
  }

  /**
   * Render pagination for audit table.
   */
  function renderAuditPagination(total, page, pages) {
    var paginationEl = document.getElementById('auditPagination');
    if (!paginationEl) return;

    paginationEl.textContent = '';

    var prevBtn = document.createElement('button');
    prevBtn.className = 'pagination-btn';
    prevBtn.disabled = page <= 1;
    prevBtn.setAttribute('aria-label', 'Previous page');
    var prevIcon = document.createElement('i');
    prevIcon.className = 'fas fa-chevron-left';
    prevIcon.setAttribute('aria-hidden', 'true');
    prevBtn.appendChild(prevIcon);
    prevBtn.addEventListener('click', function () {
      if (page > 1) loadAuditLogs(page - 1, collectAuditFilters());
    });
    paginationEl.appendChild(prevBtn);

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
          return function () { loadAuditLogs(pageNum, collectAuditFilters()); };
        })(p));
        paginationEl.appendChild(btn);
      }
    });

    var nextBtn = document.createElement('button');
    nextBtn.className = 'pagination-btn';
    nextBtn.disabled = page >= pages;
    nextBtn.setAttribute('aria-label', 'Next page');
    var nextIcon = document.createElement('i');
    nextIcon.className = 'fas fa-chevron-right';
    nextIcon.setAttribute('aria-hidden', 'true');
    nextBtn.appendChild(nextIcon);
    nextBtn.addEventListener('click', function () {
      if (page < pages) loadAuditLogs(page + 1, collectAuditFilters());
    });
    paginationEl.appendChild(nextBtn);
  }

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

  function collectAuditFilters() {
    return {
      resource_type: getSelectValue('auditResourceFilter'),
      action: getSelectValue('auditActionFilter')
    };
  }

  // ─── HELPERS ────────────────────────────────────────────────

  function formatDateTime(dateStr) {
    if (!dateStr) return '-';
    try {
      var d = new Date(dateStr);
      return d.toLocaleDateString('en-US', { year: 'numeric', month: 'short', day: 'numeric' }) +
             ' ' + d.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' });
    } catch (_e) {
      return dateStr;
    }
  }

  function formatActionName(action) {
    if (!action) return '-';
    return action.replace(/_/g, ' ').replace(/\b\w/g, function (c) { return c.toUpperCase(); });
  }

  function capitalizeFirst(str) {
    if (!str) return '';
    return str.charAt(0).toUpperCase() + str.slice(1);
  }

  function getInitials(name) {
    if (!name) return '?';
    var parts = name.split(' ');
    if (parts.length >= 2) {
      return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
    }
    return name.substring(0, 2).toUpperCase();
  }

  function summarizeDetails(details) {
    if (!details) return '-';
    var keys = Object.keys(details);
    if (keys.length === 0) return '-';

    var parts = [];
    keys.slice(0, 3).forEach(function (key) {
      var val = details[key];
      if (typeof val === 'object') {
        val = JSON.stringify(val);
      }
      var strVal = String(val);
      if (strVal.length > 30) strVal = strVal.substring(0, 27) + '...';
      parts.push(key + ': ' + strVal);
    });
    return parts.join(', ');
  }

  function getSelectValue(id) {
    var el = document.getElementById(id);
    return el ? el.value : 'all';
  }

  // ─── INIT ───────────────────────────────────────────────────

  document.addEventListener('DOMContentLoaded', function () {
    var tbody = document.getElementById('auditTableBody');
    if (!tbody) return;

    loadAuditLogs(1);

    // Filter listeners
    var resourceFilter = document.getElementById('auditResourceFilter');
    if (resourceFilter) {
      resourceFilter.addEventListener('change', function () {
        loadAuditLogs(1, collectAuditFilters());
      });
    }

    var actionFilter = document.getElementById('auditActionFilter');
    if (actionFilter) {
      actionFilter.addEventListener('change', function () {
        loadAuditLogs(1, collectAuditFilters());
      });
    }
  });

  // Expose
  window.loadAuditLogs = loadAuditLogs;
})();
