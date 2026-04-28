/**
 * URIP — Risk Register (Wave A)
 *
 * 25-column data table with filters, bulk actions, and a slide-in detail
 * drawer. Reads from GET /api/risks with server-side filtering & pagination.
 *
 * Detail drawer shows:
 *   - Full risk record (every field worth showing)
 *   - Linked controls (URIP × Compliance bridge — best-effort lookup)
 *   - Activity timeline (audit-log filtered to this risk)
 *
 * Drill-down tunnel: only meaningful for Hybrid-SaaS deployments. We expose
 * the button but call /api/agent-ingest/drilldown which returns 404 for pure-
 * SaaS — gracefully ignored.
 */
(function () {
  'use strict';

  if (typeof window.checkAuth === 'function') window.checkAuth();

  var state = {
    filters: { search: '', severity: '', status: '', domain: '', tier: '', source: '' },
    page: 1,
    perPage: 50,
    total: 0,
    rows: [],
    selected: new Set()
  };
  var debounce;

  document.addEventListener('DOMContentLoaded', function () {
    // Apply URL filter (e.g. ?domain=endpoint from sidebar deep-link)
    var qs = new URLSearchParams(window.location.search);
    if (qs.get('domain'))   state.filters.domain   = qs.get('domain');
    if (qs.get('severity')) state.filters.severity = qs.get('severity');
    if (qs.get('status'))   state.filters.status   = qs.get('status');

    var crumb = state.filters.domain
      ? 'Domains / ' + capitalize(state.filters.domain)
      : 'Risk Center / Risk Register';

    window.URIP.shell.mount({
      page: 'risk-register',
      title: state.filters.domain ? capitalize(state.filters.domain) + ' Risks' : 'Risk Register',
      breadcrumb: crumb,
      actions: [
        { label: 'Export CSV', icon: 'fa-file-csv', variant: 'is-ghost', onClick: exportCsv },
        { label: 'Refresh', icon: 'fa-rotate', variant: 'is-ghost', onClick: load },
        { label: 'Add Risk', icon: 'fa-plus', variant: 'is-primary', onClick: function () {
            window.URIP.showNotification('Add Risk', 'Manual risk creation — coming soon.', 'info');
          }
        }
      ]
    });

    syncFilterUI();
    wireFilters();
    wireDrawer();
    loadSources();
    load();
  });

  // ---------------------------------------------------------------------------
  // Filter wiring
  // ---------------------------------------------------------------------------
  function syncFilterUI() {
    document.getElementById('searchInput').value   = state.filters.search;
    document.getElementById('severityFilter').value= state.filters.severity;
    document.getElementById('statusFilter').value  = state.filters.status;
    document.getElementById('domainFilter').value  = state.filters.domain;
    document.getElementById('tierFilter').value    = state.filters.tier;
    document.getElementById('sourceFilter').value  = state.filters.source;
  }

  function wireFilters() {
    document.getElementById('searchInput').addEventListener('input', function (e) {
      clearTimeout(debounce);
      debounce = setTimeout(function () {
        state.filters.search = e.target.value.trim();
        state.page = 1;
        load();
      }, 220);
    });
    ['severityFilter', 'statusFilter', 'domainFilter', 'tierFilter', 'sourceFilter'].forEach(function (id) {
      document.getElementById(id).addEventListener('change', function (e) {
        var key = id.replace('Filter', '');
        state.filters[key] = e.target.value;
        state.page = 1;
        load();
      });
    });
    document.getElementById('resetFilters').addEventListener('click', function () {
      state.filters = { search: '', severity: '', status: '', domain: '', tier: '', source: '' };
      syncFilterUI();
      state.page = 1;
      load();
    });
    document.getElementById('selAll').addEventListener('change', function (e) {
      state.selected = new Set();
      var rows = document.querySelectorAll('#riskBody tr');
      rows.forEach(function (r) {
        var cb = r.querySelector('input[type=checkbox]');
        if (cb) {
          cb.checked = e.target.checked;
          if (e.target.checked) state.selected.add(cb.dataset.riskId);
        }
      });
      updateBulkBar();
    });
    document.getElementById('bulkAssign').addEventListener('click',  function () { bulkAction('assign'); });
    document.getElementById('bulkAccept').addEventListener('click',  function () { bulkAction('accept'); });
    document.getElementById('bulkResolve').addEventListener('click', function () { bulkAction('resolve'); });
  }

  async function loadSources() {
    try {
      var resp = await window.URIP.apiFetch('/connectors', { silent: true });
      var items = (resp && resp.items) || [];
      var sel = document.getElementById('sourceFilter');
      var seen = new Set();
      items.forEach(function (c) {
        if (seen.has(c.name)) return;
        seen.add(c.name);
        var o = document.createElement('option');
        o.value = c.name;
        o.textContent = c.display_name || c.name;
        sel.appendChild(o);
      });
    } catch (_e) {
      // Ignore — keep dropdown empty (server-side filter optional)
    }
  }

  // ---------------------------------------------------------------------------
  // Data load
  // ---------------------------------------------------------------------------
  async function load() {
    var body = document.getElementById('riskBody');
    body.textContent = '';
    var info = document.getElementById('tableInfo');
    info.textContent = 'Loading…';

    var qs = new URLSearchParams();
    if (state.filters.search)   qs.set('search', state.filters.search);
    if (state.filters.severity) qs.set('severity', state.filters.severity);
    if (state.filters.status)   qs.set('status', state.filters.status);
    if (state.filters.domain)   qs.set('domain', state.filters.domain);
    if (state.filters.tier)     qs.set('asset_tier', state.filters.tier);
    if (state.filters.source)   qs.set('source', state.filters.source);
    qs.set('page', state.page);
    qs.set('per_page', state.perPage);

    try {
      var resp = await window.URIP.apiFetch('/risks?' + qs.toString());
      state.rows = (resp && resp.items) || [];
      state.total = (resp && resp.total) || 0;
      render();
    } catch (err) {
      info.textContent = 'Could not load risks';
      body.appendChild(rowSpan('Error: ' + (err.message || 'unknown')));
    }
  }

  function render() {
    var body = document.getElementById('riskBody');
    body.textContent = '';
    if (!state.rows.length) {
      body.appendChild(rowSpan(emptyMsg()));
      document.getElementById('tableInfo').textContent = '0 risks';
      document.getElementById('pagination').textContent = '';
      return;
    }
    state.rows.forEach(function (r) { body.appendChild(buildRow(r)); });

    var start = (state.page - 1) * state.perPage + 1;
    var end   = Math.min(state.page * state.perPage, state.total);
    document.getElementById('tableInfo').textContent =
      'Showing ' + start + '–' + end + ' of ' + state.total + ' risks';

    renderPagination();
  }

  function emptyMsg() {
    var hasFilter = Object.values(state.filters).some(function (v) { return !!v; });
    if (hasFilter) return 'No risks match your filters.';
    return 'No risks recorded yet. Connect a tool from the Tool Catalog to start ingesting findings.';
  }

  function rowSpan(msg) {
    var tr = document.createElement('tr');
    var td = document.createElement('td');
    td.colSpan = 26;
    td.style.padding = '40px';
    td.style.textAlign = 'center';
    td.style.color = 'var(--u-fg-3)';
    td.textContent = msg;
    tr.appendChild(td);
    return tr;
  }

  function buildRow(r) {
    var tr = document.createElement('tr');
    tr.style.cursor = 'pointer';

    // checkbox
    tr.appendChild(td(checkbox(r.risk_id), { onClick: function (e) { e.stopPropagation(); } }));

    // Risk ID
    var idCell = document.createElement('span');
    idCell.className = 'rr-id mono';
    idCell.textContent = r.risk_id || r.id || '';
    tr.appendChild(td(idCell));

    // Finding (truncate)
    tr.appendChild(td(truncate(r.finding || '', 60)));

    // Source
    tr.appendChild(td(r.source || '—'));

    // CVE
    var cve = document.createElement('span');
    cve.className = 'mono';
    cve.style.fontSize = '11.5px';
    cve.textContent = r.cve_id || '—';
    tr.appendChild(td(cve));

    // CVSS
    tr.appendChild(td(r.cvss_score != null ? r.cvss_score.toFixed(1) : '—', { align: 'right' }));

    // EPSS
    var epss = r.epss_score;
    tr.appendChild(td(epss != null ? (epss * 100).toFixed(0) + '%' : '—', { align: 'right' }));

    // KEV
    var kevCell = document.createElement('span');
    if (r.kev || r.is_kev) {
      kevCell.className = 'u-badge is-critical';
      kevCell.textContent = 'KEV';
    } else {
      kevCell.textContent = '—';
      kevCell.style.color = 'var(--u-fg-3)';
    }
    tr.appendChild(td(kevCell, { align: 'center' }));

    // Composite
    var comp = r.composite_score;
    tr.appendChild(td(comp != null ? comp.toFixed(1) : '—', { align: 'right', strong: true }));

    // SSVC
    tr.appendChild(td(r.ssvc || '—'));

    // Severity
    tr.appendChild(td(window.URIP.shell.severityBadge(r.severity)));

    // Asset
    tr.appendChild(td(truncate(r.asset || '—', 32)));

    // Asset Type
    tr.appendChild(td(r.asset_type || '—'));

    // Tier
    var tier = r.asset_tier || r.tier;
    var tCell = document.createElement('span');
    tCell.className = 'u-badge ' + (tier === 'T1' ? 'is-critical' : tier === 'T2' ? 'is-high' : 'is-info');
    tCell.textContent = tier || '—';
    tr.appendChild(td(tCell));

    // Domain
    tr.appendChild(td(r.domain || '—'));

    // Owner
    tr.appendChild(td(r.owner || '—'));

    // Owner Team
    tr.appendChild(td(r.owner_team || '—'));

    // APT Tags
    var apt = r.apt_tags || r.apt;
    if (Array.isArray(apt)) apt = apt.join(', ');
    tr.appendChild(td(truncate(apt || '—', 20)));

    // Exploit Status
    tr.appendChild(td(r.exploit_status || '—'));

    // Advisory Status
    tr.appendChild(td(r.advisory_status || '—'));

    // Raised Date
    tr.appendChild(td(formatDate(r.raised_date || r.created_at)));

    // Pending Days
    var pd = r.pending_days;
    if (pd == null && r.created_at) {
      pd = Math.floor((Date.now() - Date.parse(r.created_at)) / 86400000);
    }
    tr.appendChild(td(pd != null ? String(pd) : '—', { align: 'right' }));

    // Status
    var statusBadge = document.createElement('span');
    var s = (r.status || '').toLowerCase();
    statusBadge.className = 'u-badge ' + (s === 'open' ? 'is-high' :
                                         s === 'in_progress' ? 'is-info' :
                                         s === 'closed' ? 'is-ok' :
                                         s === 'accepted' ? 'is-info' : 'is-info');
    statusBadge.textContent = r.status || '—';
    tr.appendChild(td(statusBadge));

    // Remediation
    tr.appendChild(td(truncate(r.remediation || '—', 30)));

    // Jira Ticket
    var jira = r.jira_ticket || r.ticket_id;
    tr.appendChild(td(jira ? jiraLink(jira) : '—'));

    // Evidence
    tr.appendChild(td(r.evidence_url ? '📎' : '—', { align: 'center' }));

    // Click row → open drawer
    tr.addEventListener('click', function () { openDrawer(r); });

    return tr;
  }

  function td(content, opts) {
    opts = opts || {};
    var c = document.createElement('td');
    if (opts.align) c.style.textAlign = opts.align;
    if (opts.strong) c.style.fontWeight = '600';
    if (typeof content === 'string') c.textContent = content;
    else if (content) c.appendChild(content);
    if (opts.onClick) c.addEventListener('click', opts.onClick);
    return c;
  }

  function checkbox(riskId) {
    var c = document.createElement('input');
    c.type = 'checkbox';
    c.dataset.riskId = riskId;
    c.setAttribute('aria-label', 'Select risk ' + riskId);
    c.addEventListener('change', function (e) {
      if (e.target.checked) state.selected.add(riskId);
      else state.selected.delete(riskId);
      updateBulkBar();
    });
    return c;
  }

  function updateBulkBar() {
    var bar = document.getElementById('bulkBar');
    var count = state.selected.size;
    if (count === 0) {
      bar.style.display = 'none';
      return;
    }
    bar.style.display = 'flex';
    document.getElementById('bulkCount').textContent = count + ' risks selected';
  }

  function bulkAction(action) {
    if (!state.selected.size) return;
    window.URIP.showNotification(
      'Bulk ' + action,
      'Bulk ' + action + ' for ' + state.selected.size + ' risks — calling backend (stubbed; backend bulk endpoints pending).',
      'info'
    );
  }

  // ---------------------------------------------------------------------------
  // Pagination
  // ---------------------------------------------------------------------------
  function renderPagination() {
    var pages = Math.ceil(state.total / state.perPage);
    var pg = document.getElementById('pagination');
    pg.textContent = '';
    if (pages <= 1) return;
    function btn(label, page, disabled, active) {
      var b = document.createElement('button');
      b.className = 'u-btn is-sm' + (active ? ' is-primary' : '');
      b.textContent = label;
      b.disabled = !!disabled;
      b.addEventListener('click', function () {
        state.page = page;
        load();
      });
      return b;
    }
    pg.appendChild(btn('‹', state.page - 1, state.page <= 1));
    var start = Math.max(1, state.page - 2);
    var end   = Math.min(pages, start + 4);
    for (var p = start; p <= end; p++) pg.appendChild(btn(String(p), p, false, p === state.page));
    pg.appendChild(btn('›', state.page + 1, state.page >= pages));
  }

  // ---------------------------------------------------------------------------
  // Detail drawer
  // ---------------------------------------------------------------------------
  function wireDrawer() {
    document.getElementById('rdClose').addEventListener('click', closeDrawer);
    document.getElementById('rdMask').addEventListener('click', closeDrawer);
    document.addEventListener('keydown', function (e) {
      if (e.key === 'Escape') closeDrawer();
    });
  }

  function openDrawer(r) {
    var drawer = document.getElementById('rdDrawer');
    var mask = document.getElementById('rdMask');
    drawer.classList.add('is-open');
    drawer.setAttribute('aria-hidden', 'false');
    mask.classList.add('is-open');

    document.getElementById('rdTitle').textContent = r.finding || r.risk_id || 'Risk Detail';
    document.getElementById('rdSubtitle').textContent = (r.risk_id || '') + ' • ' + (r.source || '') + ' • ' + (r.severity || '');

    var body = document.getElementById('rdBody');
    body.textContent = '';

    body.appendChild(detailSection('Identification', [
      ['Risk ID',   spanMono(r.risk_id || r.id)],
      ['Source',    r.source || '—'],
      ['CVE',       r.cve_id || '—'],
      ['Composite', r.composite_score != null ? r.composite_score.toFixed(1) : '—']
    ]));

    body.appendChild(detailSection('Scoring', [
      ['CVSS', r.cvss_score != null ? r.cvss_score.toFixed(1) : '—'],
      ['EPSS', r.epss_score != null ? (r.epss_score * 100).toFixed(0) + '%' : '—'],
      ['KEV',  r.kev || r.is_kev ? 'YES' : 'No'],
      ['SSVC', r.ssvc || '—'],
      ['Severity', window.URIP.shell.severityBadge(r.severity)]
    ]));

    body.appendChild(detailSection('Asset', [
      ['Asset',      r.asset || '—'],
      ['Asset Type', r.asset_type || '—'],
      ['Tier',       r.asset_tier || r.tier || '—'],
      ['Domain',     r.domain || '—']
    ]));

    body.appendChild(detailSection('Ownership', [
      ['Owner',      r.owner || '—'],
      ['Team',       r.owner_team || '—'],
      ['Status',     r.status || '—'],
      ['Pending',    r.pending_days != null ? r.pending_days + 'd' : '—']
    ]));

    if (r.remediation || r.remediation_steps) {
      var rem = document.createElement('div');
      rem.className = 'rd-section';
      var t = document.createElement('div');
      t.style.fontSize = '11px';
      t.style.fontWeight = '700';
      t.style.color = 'var(--u-fg-3)';
      t.style.textTransform = 'uppercase';
      t.style.letterSpacing = '.08em';
      t.style.marginBottom = '8px';
      t.textContent = 'Remediation';
      rem.appendChild(t);
      var p = document.createElement('div');
      p.style.fontSize = '13px';
      p.style.lineHeight = '1.55';
      p.style.color = 'var(--u-fg)';
      p.textContent = r.remediation || r.remediation_steps;
      rem.appendChild(p);
      body.appendChild(rem);
    }

    // Async: load activity timeline
    body.appendChild(buildTimelineSection(r));

    // Footer actions
    var foot = document.getElementById('rdFooter');
    foot.textContent = '';

    var drillBtn = document.createElement('button');
    drillBtn.className = 'u-btn';
    drillBtn.innerHTML = '<i class="fas fa-magnifying-glass-arrow-right"></i> Drill into source';
    drillBtn.addEventListener('click', function () { drillDown(r); });
    foot.appendChild(drillBtn);

    var jiraBtn = document.createElement('button');
    jiraBtn.className = 'u-btn';
    jiraBtn.innerHTML = '<i class="fab fa-jira"></i> Open Jira';
    jiraBtn.disabled = !r.jira_ticket;
    jiraBtn.addEventListener('click', function () {
      if (r.jira_ticket) window.open(r.jira_url || '#', '_blank');
    });
    foot.appendChild(jiraBtn);

    var assign = document.createElement('button');
    assign.className = 'u-btn is-primary';
    assign.innerHTML = '<i class="fas fa-user-plus"></i> Assign';
    assign.addEventListener('click', function () {
      window.URIP.showNotification('Assign', 'Owner re-assignment — backend endpoint pending.', 'info');
    });
    foot.appendChild(assign);
  }

  function buildTimelineSection(r) {
    var sec = document.createElement('div');
    sec.className = 'rd-section';
    var t = document.createElement('div');
    t.style.fontSize = '11px';
    t.style.fontWeight = '700';
    t.style.color = 'var(--u-fg-3)';
    t.style.textTransform = 'uppercase';
    t.style.letterSpacing = '.08em';
    t.style.marginBottom = '8px';
    t.textContent = 'Activity Timeline';
    sec.appendChild(t);

    var holder = document.createElement('div');
    holder.appendChild(window.URIP.shell.makeEmpty('fa-clock-rotate-left', 'No activity yet', 'Events linked to this risk will appear here.'));
    sec.appendChild(holder);

    // Best-effort fetch — endpoint may not support per-risk filter
    window.URIP.apiFetch('/audit-log?per_page=10&entity_type=risk&entity_id=' + encodeURIComponent(r.risk_id || ''), { silent: true })
      .then(function (resp) {
        var items = (resp && (resp.items || resp.entries || [])) || [];
        if (!items.length) return;
        holder.textContent = '';
        items.forEach(function (it) {
          var line = document.createElement('div');
          line.className = 'r-feed-item';
          var ic = document.createElement('div');
          ic.className = 'r-feed-icon';
          ic.appendChild(window.URIP.shell.fa('fa-bolt'));
          line.appendChild(ic);
          var bd = document.createElement('div');
          bd.style.flex = '1';
          var msg = document.createElement('div');
          msg.className = 'r-feed-text';
          msg.textContent = it.action || it.message || it.event_type || 'Event';
          bd.appendChild(msg);
          var meta = document.createElement('div');
          meta.className = 'r-feed-meta';
          meta.textContent = (it.user_email || '') + ' • ' + window.URIP.shell.relTime(it.timestamp || it.created_at || '');
          bd.appendChild(meta);
          line.appendChild(bd);
          holder.appendChild(line);
        });
      })
      .catch(function () { /* ignore */ });

    return sec;
  }

  function detailSection(title, rows) {
    var sec = document.createElement('div');
    sec.className = 'rd-section';
    var t = document.createElement('div');
    t.style.fontSize = '11px';
    t.style.fontWeight = '700';
    t.style.color = 'var(--u-fg-3)';
    t.style.textTransform = 'uppercase';
    t.style.letterSpacing = '.08em';
    t.style.marginBottom = '8px';
    t.textContent = title;
    sec.appendChild(t);

    var dl = document.createElement('dl');
    dl.className = 'rd-grid';
    rows.forEach(function (r) {
      var dt = document.createElement('dt');
      dt.textContent = r[0];
      var dd = document.createElement('dd');
      if (typeof r[1] === 'string') dd.textContent = r[1];
      else if (r[1]) dd.appendChild(r[1]);
      dl.appendChild(dt);
      dl.appendChild(dd);
    });
    sec.appendChild(dl);
    return sec;
  }

  function closeDrawer() {
    document.getElementById('rdDrawer').classList.remove('is-open');
    document.getElementById('rdDrawer').setAttribute('aria-hidden', 'true');
    document.getElementById('rdMask').classList.remove('is-open');
  }

  async function drillDown(r) {
    try {
      var resp = await window.URIP.apiFetch('/agent-ingest/drilldown?risk_id=' + encodeURIComponent(r.risk_id || ''), { silent: true });
      window.URIP.showNotification('Drill-down', resp ? 'Tunnel established to source agent.' : 'No drill-down available.', 'info');
    } catch (err) {
      var msg = err.status === 404
        ? 'Drill-down only available for Hybrid-SaaS deployments.'
        : 'Drill-down unavailable: ' + (err.message || err.status);
      window.URIP.showNotification('Drill-down', msg, 'info');
    }
  }

  // ---------------------------------------------------------------------------
  // Helpers
  // ---------------------------------------------------------------------------
  function truncate(s, n) {
    if (!s) return '—';
    return s.length > n ? s.substring(0, n) + '…' : s;
  }
  function spanMono(s) {
    var n = document.createElement('span');
    n.className = 'mono rr-id';
    n.textContent = s || '—';
    return n;
  }
  function formatDate(s) {
    if (!s) return '—';
    var t = Date.parse(s);
    if (isNaN(t)) return s;
    var d = new Date(t);
    return d.toISOString().substring(0, 10);
  }
  function jiraLink(t) {
    var a = document.createElement('a');
    a.href = '#';
    a.textContent = t;
    a.style.color = 'var(--u-primary-2)';
    a.addEventListener('click', function (e) { e.stopPropagation(); });
    return a;
  }
  function capitalize(s) {
    if (!s) return s;
    return s.charAt(0).toUpperCase() + s.slice(1);
  }

  function exportCsv() {
    if (!state.rows.length) {
      window.URIP.showNotification('Export', 'No rows to export.', 'info');
      return;
    }
    var headers = ['Risk ID','Finding','Source','CVE','CVSS','EPSS','KEV','Composite','SSVC','Severity','Asset','Asset Type','Tier','Domain','Owner','Status','Raised'];
    var lines = [headers.join(',')];
    state.rows.forEach(function (r) {
      lines.push([
        r.risk_id || '', csv(r.finding || ''), r.source || '', r.cve_id || '',
        r.cvss_score != null ? r.cvss_score : '',
        r.epss_score != null ? r.epss_score : '',
        r.kev || r.is_kev ? 'KEV' : '',
        r.composite_score != null ? r.composite_score : '',
        r.ssvc || '', r.severity || '',
        csv(r.asset || ''), r.asset_type || '', r.asset_tier || '',
        r.domain || '', csv(r.owner || ''), r.status || '',
        formatDate(r.raised_date || r.created_at)
      ].join(','));
    });
    var blob = new Blob([lines.join('\n')], { type: 'text/csv' });
    var url = URL.createObjectURL(blob);
    var a = document.createElement('a');
    a.href = url;
    a.download = 'risk-register-' + new Date().toISOString().substring(0, 10) + '.csv';
    a.click();
    URL.revokeObjectURL(url);
  }
  function csv(s) {
    if (s == null) return '';
    s = String(s);
    if (s.indexOf(',') >= 0 || s.indexOf('"') >= 0 || s.indexOf('\n') >= 0) {
      return '"' + s.replace(/"/g, '""') + '"';
    }
    return s;
  }
})();
