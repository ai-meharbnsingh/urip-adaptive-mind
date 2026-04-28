/**
 * URIP — Connector Status (Wave A)
 *
 * Per-connector health table over GET /api/connectors. Manual triggers,
 * reconfigure/disable actions per row.
 */
(function () {
  'use strict';

  if (typeof window.checkAuth === 'function') window.checkAuth();

  var state = {
    items: [],
    filters: { search: '', health: '' }
  };

  document.addEventListener('DOMContentLoaded', function () {
    window.URIP.shell.mount({
      page: 'connector-status',
      title: 'Connector Status',
      breadcrumb: 'Configuration / Connectors',
      actions: [
        { label: 'Tool Catalog', icon: 'fa-puzzle-piece', variant: 'is-ghost', href: 'tool-catalog.html' },
        { label: 'Refresh', icon: 'fa-rotate', variant: 'is-primary', onClick: load }
      ]
    });

    var debounce;
    document.getElementById('csSearch').addEventListener('input', function (e) {
      clearTimeout(debounce);
      debounce = setTimeout(function () {
        state.filters.search = e.target.value.trim().toLowerCase();
        render();
      }, 150);
    });
    document.getElementById('csHealth').addEventListener('change', function (e) {
      state.filters.health = e.target.value;
      render();
    });
    document.getElementById('csReset').addEventListener('click', function () {
      state.filters = { search: '', health: '' };
      document.getElementById('csSearch').value = '';
      document.getElementById('csHealth').value = '';
      render();
    });

    load();
  });

  async function load() {
    var body = document.getElementById('csBody');
    body.textContent = '';
    body.appendChild(spanRow('Loading…'));
    try {
      var resp = await window.URIP.apiFetch('/connectors?limit=200', { silent: true });
      state.items = ((resp && resp.items) || []).filter(function (i) { return i.configured; });
    } catch (err) {
      body.textContent = '';
      body.appendChild(spanRow(err.status === 403 ? 'CISO role required' : ('Error: ' + err.message)));
      return;
    }
    renderKPIs();
    render();
  }

  function renderKPIs() {
    var total = state.items.length;
    var ok = 0, deg = 0, err = 0;
    state.items.forEach(function (i) {
      if (i.health_status === 'ok') ok++;
      else if (i.health_status === 'degraded') deg++;
      else if (i.health_status === 'error' || i.error_count_24h > 0) err++;
    });
    document.getElementById('csTotal').textContent = total;
    document.getElementById('csOk').textContent = ok;
    document.getElementById('csDeg').textContent = deg;
    document.getElementById('csErr').textContent = err;
  }

  function render() {
    var body = document.getElementById('csBody');
    body.textContent = '';

    var rows = state.items.filter(function (i) {
      if (state.filters.search) {
        var hay = (i.display_name + ' ' + i.name + ' ' + (i.category || '')).toLowerCase();
        if (hay.indexOf(state.filters.search) === -1) return false;
      }
      if (state.filters.health && i.health_status !== state.filters.health) return false;
      return true;
    });

    if (!rows.length) {
      var empty = document.createElement('tr');
      var td = document.createElement('td');
      td.colSpan = 7;
      td.style.padding = '40px';
      td.style.textAlign = 'center';
      var inner = window.URIP.shell.makeEmpty(
        'fa-puzzle-piece',
        state.items.length ? 'No connectors match those filters' : 'No connectors configured yet',
        state.items.length ? 'Try clearing the search.' : 'Open the Tool Catalog and configure a tool to start ingesting data.'
      );
      td.appendChild(inner);
      empty.appendChild(td);
      body.appendChild(empty);
      return;
    }

    rows.forEach(function (item) { body.appendChild(buildRow(item)); });
  }

  function buildRow(item) {
    var tr = document.createElement('tr');

    // Connector name
    var n = document.createElement('td');
    var nm = document.createElement('div');
    nm.style.fontWeight = '600';
    nm.textContent = item.display_name || item.name;
    n.appendChild(nm);
    if (item.short_description) {
      var sd = document.createElement('div');
      sd.style.fontSize = '11px';
      sd.style.color = 'var(--u-fg-3)';
      sd.textContent = item.short_description;
      n.appendChild(sd);
    }
    tr.appendChild(n);

    // Category
    var c = document.createElement('td');
    c.textContent = item.category || '—';
    tr.appendChild(c);

    // Lifecycle
    var lc = document.createElement('td');
    lc.appendChild(window.URIP.shell.lifecyclePill(item.status));
    tr.appendChild(lc);

    // Health
    var h = document.createElement('td');
    var pill = document.createElement('span');
    pill.className = 'u-badge ' +
      (item.health_status === 'ok' ? 'is-ok' :
       item.health_status === 'degraded' ? 'is-medium' :
       item.health_status === 'error' ? 'is-critical' : 'is-info');
    pill.textContent = item.health_status || 'unknown';
    h.appendChild(pill);
    tr.appendChild(h);

    // Last poll
    var lp = document.createElement('td');
    lp.textContent = item.last_poll_at ? window.URIP.shell.relTime(item.last_poll_at) : 'never';
    tr.appendChild(lp);

    // Errors
    var e = document.createElement('td');
    e.textContent = item.error_count_24h || 0;
    if ((item.error_count_24h || 0) > 0) e.style.color = 'var(--sev-critical)';
    tr.appendChild(e);

    // Actions
    var a = document.createElement('td');
    a.style.textAlign = 'right';
    a.style.whiteSpace = 'nowrap';

    var pull = document.createElement('button');
    pull.className = 'u-btn is-sm';
    pull.title = 'Trigger manual pull'; pull.setAttribute('aria-label', 'Trigger manual pull');
    pull.innerHTML = '<i class="fas fa-rotate"></i>';
    pull.addEventListener('click', function (ev) {
      ev.stopPropagation();
      pollNow(item);
    });
    a.appendChild(pull);

    var cfg = document.createElement('button');
    cfg.className = 'u-btn is-sm';
    cfg.style.marginLeft = '6px';
    cfg.title = 'Reconfigure'; cfg.setAttribute('aria-label', 'Reconfigure connector');
    cfg.innerHTML = '<i class="fas fa-gear"></i>';
    cfg.addEventListener('click', function (ev) {
      ev.stopPropagation();
      window.location.href = 'tool-catalog.html?open=' + encodeURIComponent(item.name);
    });
    a.appendChild(cfg);

    var del = document.createElement('button');
    del.className = 'u-btn is-sm is-danger';
    del.style.marginLeft = '6px';
    del.title = 'Disable'; del.setAttribute('aria-label', 'Disable connector');
    del.innerHTML = '<i class="fas fa-power-off"></i>';
    del.addEventListener('click', function (ev) {
      ev.stopPropagation();
      disable(item);
    });
    a.appendChild(del);

    tr.appendChild(a);
    return tr;
  }

  async function pollNow(item) {
    try {
      await window.URIP.apiFetch('/connectors/' + encodeURIComponent(item.name) + '/run', { method: 'POST' });
      window.URIP.showNotification('Triggered', 'Manual pull queued for ' + (item.display_name || item.name), 'success');
      setTimeout(load, 2000);
    } catch (err) {
      window.URIP.showNotification('Failed', err.message || 'Could not trigger pull.', 'error');
    }
  }

  async function disable(item) {
    if (!confirm('Disable ' + (item.display_name || item.name) + '? URIP will stop polling and credentials remain stored. You can re-enable later.')) return;
    try {
      await window.URIP.apiFetch('/connectors/' + encodeURIComponent(item.name), { method: 'DELETE' });
      window.URIP.showNotification('Disabled', (item.display_name || item.name) + ' disabled.', 'success');
      load();
    } catch (err) {
      window.URIP.showNotification('Failed', err.message || 'Could not disable connector.', 'error');
    }
  }

  function spanRow(msg) {
    var tr = document.createElement('tr');
    var td = document.createElement('td');
    td.colSpan = 7;
    td.style.padding = '40px';
    td.style.textAlign = 'center';
    td.style.color = 'var(--u-fg-3)';
    td.textContent = msg;
    tr.appendChild(td);
    return tr;
  }
})();
