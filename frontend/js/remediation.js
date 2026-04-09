/**
 * URIP - Remediation Tracker
 * Loads remediation tasks from API, renders table with status badges.
 * All DOM via createElement + textContent (NO innerHTML).
 * Depends on: api.js (window.URIP.apiFetch, window.URIP.showNotification)
 */
(function () {
  'use strict';

  var currentPage = 1;
  var perPage = 20;

  // Status badge color mapping
  var STATUS_CLASSES = {
    not_started: { bg: 'rgba(100,116,139,0.1)', color: '#64748B', label: 'Not Started' },
    in_progress: { bg: 'rgba(52,152,219,0.1)',   color: '#3498DB', label: 'In Progress' },
    blocked:     { bg: 'rgba(231,76,60,0.1)',     color: '#E74C3C', label: 'Blocked' },
    completed:   { bg: 'rgba(39,174,96,0.1)',     color: '#27AE60', label: 'Completed' },
    verified:    { bg: 'rgba(26,188,156,0.1)',     color: '#1ABC9C', label: 'Verified' }
  };

  // Priority badge mapping
  var PRIORITY_CLASSES = {
    critical: 'badge-critical',
    high: 'badge-high',
    medium: 'badge-medium',
    low: 'badge-low'
  };

  /**
   * Load remediation tasks from API.
   *
   * @param {number} [page=1]
   * @param {string} [statusFilter] - filter by status
   */
  async function loadRemediationTasks(page, statusFilter) {
    page = page || 1;
    currentPage = page;

    var params = new URLSearchParams();
    params.set('page', String(page));
    params.set('per_page', String(perPage));
    if (statusFilter && statusFilter !== 'all') {
      params.set('status', statusFilter);
    }

    try {
      var data = await window.URIP.apiFetch('/remediation?' + params.toString());
      renderRemediationTable(data);
    } catch (err) {
      window.URIP.showNotification('Error', 'Failed to load remediation tasks.', 'error');
    }
  }

  /**
   * Render remediation table.
   * Columns: Title, Risk ID, Priority, Status, Assigned To, Due Date, Jira Key
   *
   * @param {object} data - { items, total, page, pages }
   */
  function renderRemediationTable(data) {
    var tbody = document.getElementById('remediationTableBody');
    if (!tbody) return;

    tbody.textContent = '';

    if (!data.items || data.items.length === 0) {
      var emptyRow = document.createElement('tr');
      var emptyCell = document.createElement('td');
      emptyCell.setAttribute('colspan', '8');

      var emptyState = document.createElement('div');
      emptyState.className = 'empty-state';

      var emptyIcon = document.createElement('div');
      emptyIcon.className = 'empty-state-icon';
      var iconEl = document.createElement('i');
      iconEl.className = 'fas fa-tasks';
      emptyIcon.appendChild(iconEl);
      emptyState.appendChild(emptyIcon);

      var emptyTitle = document.createElement('div');
      emptyTitle.className = 'empty-state-title';
      emptyTitle.textContent = 'No remediation tasks found';
      emptyState.appendChild(emptyTitle);

      var emptyText = document.createElement('div');
      emptyText.className = 'empty-state-text';
      emptyText.textContent = 'Tasks will appear here when risks are assigned for remediation.';
      emptyState.appendChild(emptyText);

      emptyCell.appendChild(emptyState);
      emptyRow.appendChild(emptyCell);
      tbody.appendChild(emptyRow);
      return;
    }

    data.items.forEach(function (task) {
      var tr = document.createElement('tr');

      // Title
      var tdTitle = document.createElement('td');
      var titleDiv = document.createElement('div');
      titleDiv.style.fontWeight = '500';
      titleDiv.textContent = task.title || '-';
      tdTitle.appendChild(titleDiv);
      if (task.risk_detail && task.risk_detail.finding) {
        var subtitleDiv = document.createElement('div');
        subtitleDiv.style.cssText = 'font-size:0.75rem;color:#64748B;margin-top:0.25rem';
        subtitleDiv.textContent = task.risk_detail.finding;
        tdTitle.appendChild(subtitleDiv);
      }
      tr.appendChild(tdTitle);

      // Risk ID
      var tdRiskId = document.createElement('td');
      var riskIdSpan = document.createElement('span');
      riskIdSpan.className = 'risk-id';
      riskIdSpan.textContent = task.risk_detail ? task.risk_detail.risk_id : '-';
      tdRiskId.appendChild(riskIdSpan);
      tr.appendChild(tdRiskId);

      // Priority
      var tdPriority = document.createElement('td');
      var priorityBadge = document.createElement('span');
      priorityBadge.className = 'badge ' + (PRIORITY_CLASSES[task.priority] || 'badge-default');
      priorityBadge.textContent = capitalizeFirst(task.priority || 'medium');
      tdPriority.appendChild(priorityBadge);
      tr.appendChild(tdPriority);

      // Status
      var tdStatus = document.createElement('td');
      var statusBadge = document.createElement('span');
      var statusInfo = STATUS_CLASSES[task.status] || STATUS_CLASSES.not_started;
      statusBadge.style.cssText =
        'display:inline-flex;align-items:center;gap:0.375rem;padding:0.375rem 0.75rem;' +
        'font-size:0.75rem;font-weight:500;border-radius:9999px;' +
        'background-color:' + statusInfo.bg + ';color:' + statusInfo.color;

      var statusDot = document.createElement('span');
      statusDot.style.cssText =
        'width:6px;height:6px;border-radius:50%;background-color:' + statusInfo.color;
      statusBadge.appendChild(statusDot);
      statusBadge.appendChild(document.createTextNode(statusInfo.label));
      tdStatus.appendChild(statusBadge);
      tr.appendChild(tdStatus);

      // Assigned To
      var tdAssigned = document.createElement('td');
      tdAssigned.textContent = task.assigned_to || 'Unassigned';
      tr.appendChild(tdAssigned);

      // Due Date
      var tdDue = document.createElement('td');
      if (task.due_date) {
        var dueDiv = document.createElement('div');
        dueDiv.textContent = formatDate(task.due_date);
        tdDue.appendChild(dueDiv);

        var daysLeft = getDaysUntil(task.due_date);
        if (task.status !== 'completed' && task.status !== 'verified') {
          var dueLabel = document.createElement('div');
          dueLabel.style.fontSize = '0.75rem';
          if (daysLeft < 0) {
            dueLabel.style.color = '#E74C3C';
            dueLabel.textContent = Math.abs(daysLeft) + ' days overdue';
          } else if (daysLeft <= 3) {
            dueLabel.style.color = '#E74C3C';
            dueLabel.textContent = daysLeft + ' days left';
          } else if (daysLeft <= 7) {
            dueLabel.style.color = '#E67E22';
            dueLabel.textContent = daysLeft + ' days left';
          } else {
            dueLabel.style.color = '#27AE60';
            dueLabel.textContent = daysLeft + ' days left';
          }
          tdDue.appendChild(dueLabel);
        }
      } else {
        tdDue.textContent = '-';
      }
      tr.appendChild(tdDue);

      // Jira Key
      var tdJira = document.createElement('td');
      if (task.jira_key) {
        var jiraSpan = document.createElement('span');
        jiraSpan.style.cssText = 'font-family:"SF Mono",monospace;font-size:0.8125rem;font-weight:600;color:#1ABC9C';
        jiraSpan.textContent = task.jira_key;
        tdJira.appendChild(jiraSpan);
      } else {
        tdJira.textContent = '-';
      }
      tr.appendChild(tdJira);

      // Actions
      var tdActions = document.createElement('td');
      var actionsDiv = document.createElement('div');
      actionsDiv.className = 'action-btns';

      var viewBtn = document.createElement('button');
      viewBtn.className = 'action-btn view';
      viewBtn.title = 'View Details';
      var viewIcon = document.createElement('i');
      viewIcon.className = 'fas fa-eye';
      viewBtn.appendChild(viewIcon);
      actionsDiv.appendChild(viewBtn);

      var editBtn = document.createElement('button');
      editBtn.className = 'action-btn assign';
      editBtn.title = 'Edit';
      var editIcon = document.createElement('i');
      editIcon.className = 'fas fa-edit';
      editBtn.appendChild(editIcon);
      actionsDiv.appendChild(editBtn);

      tdActions.appendChild(actionsDiv);
      tr.appendChild(tdActions);

      tbody.appendChild(tr);
    });

    // Update pagination
    renderRemediationPagination(data.total, data.page, data.pages);

    // Update showing info
    var showingInfo = document.getElementById('remediationShowingInfo');
    if (showingInfo) {
      var start = data.items.length > 0 ? (data.page - 1) * perPage + 1 : 0;
      var end = Math.min(data.page * perPage, data.total);
      showingInfo.textContent = 'Showing ' + start + '-' + end + ' of ' + data.total + ' tasks';
    }
  }

  /**
   * Render pagination for remediation table.
   */
  function renderRemediationPagination(total, page, pages) {
    var paginationEl = document.getElementById('remediationPagination');
    if (!paginationEl) return;

    paginationEl.textContent = '';

    // Prev
    var prevBtn = document.createElement('button');
    prevBtn.className = 'pagination-btn';
    prevBtn.disabled = page <= 1;
    var prevIcon = document.createElement('i');
    prevIcon.className = 'fas fa-chevron-left';
    prevBtn.appendChild(prevIcon);
    prevBtn.addEventListener('click', function () {
      if (page > 1) {
        var statusFilter = getStatusFilterValue();
        loadRemediationTasks(page - 1, statusFilter);
      }
    });
    paginationEl.appendChild(prevBtn);

    // Page numbers
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
          return function () {
            var statusFilter = getStatusFilterValue();
            loadRemediationTasks(pageNum, statusFilter);
          };
        })(p));
        paginationEl.appendChild(btn);
      }
    });

    // Next
    var nextBtn = document.createElement('button');
    nextBtn.className = 'pagination-btn';
    nextBtn.disabled = page >= pages;
    var nextIcon = document.createElement('i');
    nextIcon.className = 'fas fa-chevron-right';
    nextBtn.appendChild(nextIcon);
    nextBtn.addEventListener('click', function () {
      if (page < pages) {
        var statusFilter = getStatusFilterValue();
        loadRemediationTasks(page + 1, statusFilter);
      }
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

  function getStatusFilterValue() {
    var el = document.getElementById('remediationStatusFilter');
    return el ? el.value : 'all';
  }

  function capitalizeFirst(str) {
    if (!str) return '';
    return str.charAt(0).toUpperCase() + str.slice(1);
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

  // ─── INIT ───────────────────────────────────────────────────

  document.addEventListener('DOMContentLoaded', function () {
    var tbody = document.getElementById('remediationTableBody');
    if (!tbody) return;

    loadRemediationTasks(1);

    // Status filter
    var statusFilter = document.getElementById('remediationStatusFilter');
    if (statusFilter) {
      statusFilter.addEventListener('change', function () {
        loadRemediationTasks(1, statusFilter.value);
      });
    }
  });

  // Expose
  window.loadRemediationTasks = loadRemediationTasks;
})();
