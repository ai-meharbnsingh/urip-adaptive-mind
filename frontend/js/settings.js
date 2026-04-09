/**
 * URIP - Settings Page (Users + Connectors)
 * Two-tab interface: Users management, Connector management.
 * All DOM via createElement + textContent (NO innerHTML).
 * Depends on: api.js (window.URIP.apiFetch, window.URIP.showNotification)
 */
(function () {
  'use strict';

  var activeTab = 'users';

  // Role display labels
  var ROLE_LABELS = {
    ciso: 'CISO',
    it_team: 'IT Team',
    auditor: 'Auditor',
    viewer: 'Viewer'
  };

  // Connector status colors
  var CONNECTOR_STATUS = {
    true: { color: '#27AE60', bg: 'rgba(39,174,96,0.1)', label: 'Active' },
    false: { color: '#E74C3C', bg: 'rgba(231,76,60,0.1)', label: 'Inactive' }
  };

  /**
   * Switch between tabs.
   *
   * @param {string} tab - "users" or "connectors"
   */
  function switchTab(tab) {
    activeTab = tab;

    // Update tab buttons
    var tabBtns = document.querySelectorAll('[data-settings-tab]');
    tabBtns.forEach(function (btn) {
      if (btn.getAttribute('data-settings-tab') === tab) {
        btn.classList.add('active');
        btn.classList.remove('btn-outline');
        btn.classList.add('btn-primary');
      } else {
        btn.classList.remove('active');
        btn.classList.remove('btn-primary');
        btn.classList.add('btn-outline');
      }
    });

    // Show/hide panels
    var usersPanel = document.getElementById('usersPanel');
    var connectorsPanel = document.getElementById('connectorsPanel');

    if (usersPanel) usersPanel.style.display = tab === 'users' ? 'block' : 'none';
    if (connectorsPanel) connectorsPanel.style.display = tab === 'connectors' ? 'block' : 'none';

    // Load data for active tab
    if (tab === 'users') loadUsers();
    if (tab === 'connectors') loadConnectors();
  }

  // ─── USERS ──────────────────────────────────────────────────

  /**
   * Load users from API and render table.
   */
  async function loadUsers() {
    try {
      var users = await window.URIP.apiFetch('/settings/users');
      renderUsersTable(users);
    } catch (err) {
      window.URIP.showNotification('Error', 'Failed to load users. You may need CISO permissions.', 'error');
    }
  }

  /**
   * Render users table.
   *
   * @param {Array} users
   */
  function renderUsersTable(users) {
    var tbody = document.getElementById('usersTableBody');
    if (!tbody) return;

    tbody.textContent = '';

    if (!users || users.length === 0) {
      var emptyRow = document.createElement('tr');
      var emptyCell = document.createElement('td');
      emptyCell.setAttribute('colspan', '6');

      var emptyState = document.createElement('div');
      emptyState.className = 'empty-state';

      var emptyIcon = document.createElement('div');
      emptyIcon.className = 'empty-state-icon';
      var iconEl = document.createElement('i');
      iconEl.className = 'fas fa-users';
      emptyIcon.appendChild(iconEl);
      emptyState.appendChild(emptyIcon);

      var emptyTitle = document.createElement('div');
      emptyTitle.className = 'empty-state-title';
      emptyTitle.textContent = 'No users found';
      emptyState.appendChild(emptyTitle);

      emptyCell.appendChild(emptyState);
      emptyRow.appendChild(emptyCell);
      tbody.appendChild(emptyRow);
      return;
    }

    users.forEach(function (user) {
      var tr = document.createElement('tr');

      // User info (avatar + name + email)
      var tdUser = document.createElement('td');
      var userDiv = document.createElement('div');
      userDiv.className = 'risk-owner';

      var avatar = document.createElement('div');
      avatar.className = 'owner-avatar';
      avatar.textContent = getInitials(user.full_name || user.email);
      userDiv.appendChild(avatar);

      var infoDiv = document.createElement('div');
      var nameDiv = document.createElement('div');
      nameDiv.style.fontWeight = '500';
      nameDiv.textContent = user.full_name || 'Unknown';
      infoDiv.appendChild(nameDiv);

      var emailDiv = document.createElement('div');
      emailDiv.style.cssText = 'font-size:0.75rem;color:#64748B';
      emailDiv.textContent = user.email || '';
      infoDiv.appendChild(emailDiv);

      userDiv.appendChild(infoDiv);
      tdUser.appendChild(userDiv);
      tr.appendChild(tdUser);

      // Role
      var tdRole = document.createElement('td');
      var roleBadge = document.createElement('span');
      roleBadge.className = 'badge badge-info';
      roleBadge.textContent = ROLE_LABELS[user.role] || user.role || '-';
      tdRole.appendChild(roleBadge);
      tr.appendChild(tdRole);

      // Team
      var tdTeam = document.createElement('td');
      tdTeam.textContent = user.team || '-';
      tr.appendChild(tdTeam);

      // Status
      var tdStatus = document.createElement('td');
      var statusBadge = document.createElement('span');
      var isActive = user.is_active !== false;
      statusBadge.style.cssText =
        'display:inline-flex;align-items:center;gap:0.375rem;padding:0.375rem 0.75rem;' +
        'font-size:0.75rem;font-weight:500;border-radius:9999px;' +
        'background-color:' + (isActive ? 'rgba(39,174,96,0.1)' : 'rgba(231,76,60,0.1)') + ';' +
        'color:' + (isActive ? '#27AE60' : '#E74C3C');

      var statusDot = document.createElement('span');
      statusDot.style.cssText =
        'width:6px;height:6px;border-radius:50%;background-color:' + (isActive ? '#27AE60' : '#E74C3C');
      statusBadge.appendChild(statusDot);
      statusBadge.appendChild(document.createTextNode(isActive ? 'Active' : 'Inactive'));
      tdStatus.appendChild(statusBadge);
      tr.appendChild(tdStatus);

      // Created
      var tdCreated = document.createElement('td');
      tdCreated.style.cssText = 'font-size:0.8125rem;color:#64748B';
      tdCreated.textContent = formatDate(user.created_at);
      tr.appendChild(tdCreated);

      // Actions
      var tdActions = document.createElement('td');
      var actionsDiv = document.createElement('div');
      actionsDiv.className = 'action-btns';

      var editBtn = document.createElement('button');
      editBtn.className = 'action-btn view';
      editBtn.title = 'Edit User';
      var editIcon = document.createElement('i');
      editIcon.className = 'fas fa-edit';
      editBtn.appendChild(editIcon);
      actionsDiv.appendChild(editBtn);

      tdActions.appendChild(actionsDiv);
      tr.appendChild(tdActions);

      tbody.appendChild(tr);
    });
  }

  // ─── CONNECTORS ─────────────────────────────────────────────

  /**
   * Load connectors from API and render table.
   */
  async function loadConnectors() {
    try {
      var connectors = await window.URIP.apiFetch('/settings/connectors');
      renderConnectorsTable(connectors);
    } catch (err) {
      window.URIP.showNotification('Error', 'Failed to load connectors. You may need CISO permissions.', 'error');
    }
  }

  /**
   * Render connectors table.
   *
   * @param {Array} connectors
   */
  function renderConnectorsTable(connectors) {
    var tbody = document.getElementById('connectorsTableBody');
    if (!tbody) return;

    tbody.textContent = '';

    if (!connectors || connectors.length === 0) {
      var emptyRow = document.createElement('tr');
      var emptyCell = document.createElement('td');
      emptyCell.setAttribute('colspan', '7');

      var emptyState = document.createElement('div');
      emptyState.className = 'empty-state';

      var emptyIcon = document.createElement('div');
      emptyIcon.className = 'empty-state-icon';
      var iconEl = document.createElement('i');
      iconEl.className = 'fas fa-plug';
      emptyIcon.appendChild(iconEl);
      emptyState.appendChild(emptyIcon);

      var emptyTitle = document.createElement('div');
      emptyTitle.className = 'empty-state-title';
      emptyTitle.textContent = 'No connectors configured';
      emptyState.appendChild(emptyTitle);

      emptyCell.appendChild(emptyState);
      emptyRow.appendChild(emptyCell);
      tbody.appendChild(emptyRow);
      return;
    }

    connectors.forEach(function (conn) {
      var tr = document.createElement('tr');

      // Name
      var tdName = document.createElement('td');
      var nameDiv = document.createElement('div');
      nameDiv.style.fontWeight = '500';
      nameDiv.textContent = conn.name || '-';
      tdName.appendChild(nameDiv);
      tr.appendChild(tdName);

      // Source Type
      var tdType = document.createElement('td');
      var typeBadge = document.createElement('span');
      typeBadge.className = 'badge badge-default';
      typeBadge.textContent = (conn.source_type || '-').toUpperCase();
      tdType.appendChild(typeBadge);
      tr.appendChild(tdType);

      // Base URL
      var tdUrl = document.createElement('td');
      var urlSpan = document.createElement('span');
      urlSpan.style.cssText = 'font-family:"SF Mono",monospace;font-size:0.8125rem;color:#64748B;max-width:200px;display:block;overflow:hidden;text-overflow:ellipsis;white-space:nowrap';
      urlSpan.textContent = conn.base_url || '-';
      urlSpan.title = conn.base_url || '';
      tdUrl.appendChild(urlSpan);
      tr.appendChild(tdUrl);

      // Status
      var tdStatus = document.createElement('td');
      var statusBadge = document.createElement('span');
      var isActive = conn.is_active !== false;
      var statusConf = CONNECTOR_STATUS[String(isActive)];
      statusBadge.style.cssText =
        'display:inline-flex;align-items:center;gap:0.375rem;padding:0.375rem 0.75rem;' +
        'font-size:0.75rem;font-weight:500;border-radius:9999px;' +
        'background-color:' + statusConf.bg + ';color:' + statusConf.color;

      var statusDot = document.createElement('span');
      statusDot.style.cssText =
        'width:6px;height:6px;border-radius:50%;background-color:' + statusConf.color;
      statusBadge.appendChild(statusDot);
      statusBadge.appendChild(document.createTextNode(statusConf.label));
      tdStatus.appendChild(statusBadge);
      tr.appendChild(tdStatus);

      // Last Sync
      var tdSync = document.createElement('td');
      tdSync.style.cssText = 'font-size:0.8125rem;color:#64748B';
      tdSync.textContent = conn.last_sync ? formatDateTime(conn.last_sync) : 'Never';
      tr.appendChild(tdSync);

      // Credentials
      var tdCreds = document.createElement('td');
      var credsBadge = document.createElement('span');
      if (conn.has_credentials) {
        credsBadge.style.cssText = 'font-size:0.75rem;color:#27AE60';
        credsBadge.textContent = 'Configured';
      } else {
        credsBadge.style.cssText = 'font-size:0.75rem;color:#E67E22';
        credsBadge.textContent = 'Not Set';
      }
      tdCreds.appendChild(credsBadge);
      tr.appendChild(tdCreds);

      // Actions
      var tdActions = document.createElement('td');
      var actionsDiv = document.createElement('div');
      actionsDiv.className = 'action-btns';

      var testBtn = document.createElement('button');
      testBtn.className = 'action-btn view';
      testBtn.title = 'Test Connection';
      var testIcon = document.createElement('i');
      testIcon.className = 'fas fa-plug';
      testBtn.appendChild(testIcon);
      testBtn.addEventListener('click', (function (connectorId) {
        return function () { testConnector(connectorId); };
      })(conn.id));
      actionsDiv.appendChild(testBtn);

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
  }

  /**
   * Test a connector's connectivity.
   *
   * @param {string} id - Connector UUID
   */
  async function testConnector(id) {
    try {
      var result = await window.URIP.apiFetch('/settings/connectors/' + id + '/test', {
        method: 'POST'
      });
      window.URIP.showNotification(
        'Connection Test',
        result.message || 'Connection successful',
        result.status === 'connected' ? 'success' : 'error'
      );
    } catch (err) {
      window.URIP.showNotification(
        'Connection Failed',
        (err && err.message) || 'Unable to connect to the service.',
        'error'
      );
    }
  }

  // ─── HELPERS ────────────────────────────────────────────────

  function getInitials(name) {
    if (!name) return '?';
    var parts = name.split(/[\s@]+/);
    if (parts.length >= 2) {
      return (parts[0][0] + parts[1][0]).toUpperCase();
    }
    return name.substring(0, 2).toUpperCase();
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

  // ─── INIT ───────────────────────────────────────────────────

  document.addEventListener('DOMContentLoaded', function () {
    // Only init on settings page
    var usersPanel = document.getElementById('usersPanel');
    var connectorsPanel = document.getElementById('connectorsPanel');
    if (!usersPanel && !connectorsPanel) return;

    // Tab click handlers
    var tabBtns = document.querySelectorAll('[data-settings-tab]');
    tabBtns.forEach(function (btn) {
      btn.addEventListener('click', function () {
        switchTab(btn.getAttribute('data-settings-tab'));
      });
    });

    // Default to users tab
    switchTab('users');
  });

  // Expose
  window.switchTab = switchTab;
  window.loadUsers = loadUsers;
  window.loadConnectors = loadConnectors;
  window.testConnector = testConnector;
})();
