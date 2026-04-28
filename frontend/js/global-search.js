/**
 * URIP — Global Search (Wave A)
 *
 * Backend gap: GET /api/search is NOT implemented. We fall back to local
 * filtering on /api/risks?search=, /api/connectors, and /api/audit-log.
 * Each tab labels itself "filtered locally" honestly.
 */
(function () {
  'use strict';

  if (typeof window.checkAuth === 'function') window.checkAuth();

  var qs = new URLSearchParams(window.location.search);
  var query = (qs.get('q') || '').trim();
  var activeTab = 'risks';

  document.addEventListener('DOMContentLoaded', function () {
    window.URIP.shell.mount({
      page: '',
      title: 'Search Results',
      breadcrumb: 'Search'
    });

    document.getElementById('searchTermLabel').textContent = query || '(empty query)';

    document.querySelectorAll('.u-tab').forEach(function (t) {
      t.addEventListener('click', function () {
        document.querySelectorAll('.u-tab').forEach(function (x) { x.classList.remove('is-active'); });
        t.classList.add('is-active');
        activeTab = t.dataset.tab;
        runSearch();
      });
    });
    runSearch();
  });

  async function runSearch() {
    var body = document.getElementById('resultsBody');
    body.textContent = '';
    if (!query) {
      body.appendChild(window.URIP.shell.makeEmpty('fa-magnifying-glass', 'Type something in the topbar', 'Hit enter to search.'));
      return;
    }
    body.appendChild(skeleton());

    if (activeTab === 'risks')      return loadRisks(body);
    if (activeTab === 'connectors') return loadConnectors(body);
    if (activeTab === 'audit')      return loadAudit(body);
  }

  async function loadRisks(body) {
    try {
      var resp = await window.URIP.apiFetch('/risks?search=' + encodeURIComponent(query) + '&per_page=25', { silent: true });
      var items = (resp && resp.items) || [];
      body.textContent = '';
      if (!items.length) {
        body.appendChild(window.URIP.shell.makeEmpty('fa-magnifying-glass', 'No risks match', 'Try a different search.'));
        return;
      }
      var list = document.createElement('div');
      items.forEach(function (r) {
        var row = document.createElement('a');
        row.href = 'risk-register.html?search=' + encodeURIComponent(r.risk_id || '');
        row.style.display = 'flex';
        row.style.justifyContent = 'space-between';
        row.style.padding = '12px 0';
        row.style.borderBottom = '1px solid var(--u-border)';
        row.style.color = 'var(--u-fg)';
        var left = document.createElement('div');
        left.innerHTML = '<div style="font-weight:600">' + escapeHtml(r.finding || '') + '</div>' +
                         '<div style="font-size:11px;color:var(--u-fg-3)">' +
                         escapeHtml(r.risk_id || '') + ' • ' + escapeHtml(r.source || '') + ' • ' + escapeHtml(r.asset || '') + '</div>';
        row.appendChild(left);
        row.appendChild(window.URIP.shell.severityBadge(r.severity));
        list.appendChild(row);
      });
      body.appendChild(list);
    } catch (err) {
      body.textContent = '';
      body.appendChild(window.URIP.shell.makeEmpty('fa-triangle-exclamation', 'Search failed', err.message || ''));
    }
  }

  async function loadConnectors(body) {
    try {
      var resp = await window.URIP.apiFetch('/connectors?limit=200', { silent: true });
      var q = query.toLowerCase();
      var items = ((resp && resp.items) || []).filter(function (c) {
        var hay = ((c.display_name || '') + ' ' + (c.name || '') + ' ' + (c.category || '') + ' ' + (c.short_description || '')).toLowerCase();
        return hay.indexOf(q) !== -1;
      });
      body.textContent = '';
      if (!items.length) {
        body.appendChild(window.URIP.shell.makeEmpty('fa-puzzle-piece', 'No connectors match', 'Filtered locally over the full catalog.'));
        return;
      }
      var note = document.createElement('div');
      note.style.fontSize = '11px';
      note.style.color = 'var(--u-fg-3)';
      note.style.marginBottom = '10px';
      note.textContent = 'Filtered locally — backend /api/search is not yet implemented.';
      body.appendChild(note);
      items.forEach(function (c) {
        var row = document.createElement('a');
        row.href = 'tool-catalog.html?open=' + encodeURIComponent(c.name);
        row.style.display = 'flex';
        row.style.justifyContent = 'space-between';
        row.style.padding = '10px 0';
        row.style.borderBottom = '1px solid var(--u-border)';
        row.style.color = 'var(--u-fg)';
        var left = document.createElement('div');
        left.innerHTML = '<div style="font-weight:600">' + escapeHtml(c.display_name || c.name) + '</div>' +
                         '<div style="font-size:11px;color:var(--u-fg-3)">' + escapeHtml(c.category || '') + '</div>';
        row.appendChild(left);
        row.appendChild(window.URIP.shell.lifecyclePill(c.status));
        body.appendChild(row);
      });
    } catch (err) {
      body.textContent = '';
      body.appendChild(window.URIP.shell.makeEmpty('fa-triangle-exclamation', 'Search failed', err.message || ''));
    }
  }

  async function loadAudit(body) {
    try {
      var resp = await window.URIP.apiFetch('/audit-log?per_page=50', { silent: true });
      var items = (resp && (resp.items || resp.entries || [])) || [];
      var q = query.toLowerCase();
      items = items.filter(function (it) {
        var hay = JSON.stringify(it).toLowerCase();
        return hay.indexOf(q) !== -1;
      });
      body.textContent = '';
      if (!items.length) {
        body.appendChild(window.URIP.shell.makeEmpty('fa-clock-rotate-left', 'No audit entries match', 'Filtered locally over the latest 50 entries.'));
        return;
      }
      items.forEach(function (it) {
        var row = document.createElement('div');
        row.style.padding = '10px 0';
        row.style.borderBottom = '1px solid var(--u-border)';
        row.innerHTML = '<div>' + escapeHtml(it.action || it.event_type || it.message || 'Event') + '</div>' +
                        '<div style="font-size:11px;color:var(--u-fg-3)">' +
                        escapeHtml(it.user_email || it.actor || '') + ' • ' +
                        escapeHtml(it.timestamp || it.created_at || '') + '</div>';
        body.appendChild(row);
      });
    } catch (err) {
      body.textContent = '';
      body.appendChild(window.URIP.shell.makeEmpty('fa-triangle-exclamation', 'Search failed', err.message || ''));
    }
  }

  function skeleton() {
    var d = document.createElement('div');
    for (var i = 0; i < 4; i++) {
      var s = document.createElement('div');
      s.className = 'u-skel';
      s.style.marginBottom = '10px';
      d.appendChild(s);
    }
    return d;
  }

  function escapeHtml(s) {
    if (!s) return '';
    return String(s).replace(/[&<>"']/g, function (c) {
      return ({ '&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;' })[c];
    });
  }
})();
