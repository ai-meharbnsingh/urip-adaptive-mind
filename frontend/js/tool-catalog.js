/**
 * URIP — Tool Catalog (buyer-facing)
 *
 * Fully dynamic — every tile is rendered from GET /api/connectors. NO hard-coded
 * tool list anywhere. Click a tile → slide-in drawer renders the inline setup
 * guide returned by /api/connectors/{name}/setup-guide.
 *
 * Two-state status model (no internal lifecycle copy):
 *   - AVAILABLE  → registered integration, not yet wired up for this tenant
 *   - CONFIGURED → credentials saved for this tenant
 *
 * The backend already filters out simulator / building / roadmap tiers, so
 * everything reaching this page is a real integration the customer can use.
 */
(function () {
  'use strict';

  if (typeof window.checkAuth === 'function') window.checkAuth();

  // Friendly module group labels — keys are the MODULE_CODE values returned by
  // the backend; values are the headers shown above each tile group.
  var MODULE_GROUPS = {
    VM:               'Vulnerability Management',
    EDR:              'Endpoint Detection',
    IDENTITY:         'Identity',
    NETWORK:          'Network / CASB',
    DLP:              'Data Loss Prevention',
    CSPM:             'Cloud Security (CSPM)',
    DSPM:             'Data Security (DSPM)',
    EMAIL_COLLAB:     'Email & Collaboration',
    COLLABORATION:    'Email & Collaboration',
    EMAIL:            'Email & Collaboration',
    OT:               'OT Security',
    EXTERNAL_THREAT:  'External Threat',
    EASM:             'External Attack Surface',
    DAST:             'Application Security',
    BUG_BOUNTY:       'Bug Bounty',
    ITSM:             'IT Service Management',
    ADVISORY:         'Threat Advisories',
    BGV:              'Background Verification',
    PAM:              'Privileged Access',
    NAC:              'Network Access Control',
    FIREWALL:         'Network / CASB',
    LMS:              'Security Awareness',
    MOBILE:           'Mobile',
    CORE:             'Other Integrations'
  };

  var state = {
    items: [],
    categories: [],
    filters: { search: '', category: '', configured: '' }
  };

  document.addEventListener('DOMContentLoaded', function () {
    window.URIP.shell.mount({
      page: 'tool-catalog',
      title: 'Tool Catalog',
      breadcrumb: 'Configuration / Tool Catalog',
      actions: [
        { label: 'Connector Status', icon: 'fa-heart-pulse', variant: 'is-ghost', href: 'connector-status.html' },
        { label: 'Refresh', icon: 'fa-rotate', variant: 'is-ghost', onClick: function () { load(); } }
      ]
    });

    wireFilters();
    wireDrawer();
    load();
  });

  // ---------------------------------------------------------------------------
  // Filters
  // ---------------------------------------------------------------------------
  function wireFilters() {
    var debounce;
    document.getElementById('filterSearch').addEventListener('input', function (e) {
      clearTimeout(debounce);
      debounce = setTimeout(function () {
        state.filters.search = e.target.value.trim().toLowerCase();
        renderGrid();
      }, 150);
    });
    ['filterCategory', 'filterConfigured'].forEach(function (id) {
      document.getElementById(id).addEventListener('change', function (e) {
        var key = id.replace('filter', '').toLowerCase();
        state.filters[key] = e.target.value;
        renderGrid();
      });
    });
    document.getElementById('filterReset').addEventListener('click', function () {
      state.filters = { search: '', category: '', configured: '' };
      document.getElementById('filterSearch').value = '';
      document.getElementById('filterCategory').value = '';
      document.getElementById('filterConfigured').value = '';
      renderGrid();
    });
  }

  // ---------------------------------------------------------------------------
  // Data load
  // ---------------------------------------------------------------------------
  async function load() {
    var grid = document.getElementById('catalogGrid');
    grid.textContent = '';
    document.getElementById('catalogEmpty').style.display = 'none';
    document.getElementById('catalogError').style.display = 'none';

    // Skeleton tiles
    for (var i = 0; i < 8; i++) {
      var s = document.createElement('div');
      s.className = 'tc-tile';
      s.innerHTML = '<div class="u-skel" style="height:18px;width:60%;margin-bottom:8px"></div>' +
                    '<div class="u-skel" style="height:11px;width:90%"></div>';
      grid.appendChild(s);
    }

    var resp;
    try {
      resp = await window.URIP.apiFetch('/connectors?limit=200', { silent: true });
    } catch (err) {
      grid.textContent = '';
      var box = document.createElement('div');
      box.style.gridColumn = '1 / -1';
      box.appendChild(window.URIP.shell.makeEmpty(
        'fa-triangle-exclamation',
        err.status === 403 ? 'You need CISO role to view connectors' : 'Could not load connectors',
        err.message || 'Check your network and try refreshing.'
      ));
      grid.appendChild(box);
      return;
    }
    state.items = (resp && resp.items) || [];

    // Categories aggregate (best-effort)
    try {
      var cats = await window.URIP.apiFetch('/connectors/categories', { silent: true });
      state.categories = (cats && cats.categories) || [];
    } catch (_e) {
      state.categories = uniqueCategories(state.items).map(function (c) {
        return { category: c, count: state.items.filter(function (x) { return x.category === c; }).length, configured_count: 0 };
      });
    }

    populateCategoryDropdown();
    renderKPIs();
    renderGrid();
  }

  function uniqueCategories(items) {
    var s = new Set();
    items.forEach(function (i) { if (i.category) s.add(i.category); });
    return Array.from(s).sort();
  }

  function populateCategoryDropdown() {
    var sel = document.getElementById('filterCategory');
    while (sel.options.length > 1) sel.remove(1);
    state.categories.forEach(function (c) {
      var opt = document.createElement('option');
      opt.value = c.category;
      opt.textContent = c.category + ' (' + c.count + ')';
      sel.appendChild(opt);
    });
  }

  function renderKPIs() {
    var total = state.items.length;
    var configured = 0, healthy = 0, errors = 0;
    state.items.forEach(function (i) {
      if (i.configured) configured++;
      if (i.health_status === 'ok') healthy++;
      if (i.health_status === 'error' || (i.error_count_24h || 0) > 0) errors++;
    });
    document.getElementById('kpiTotal').textContent = total;
    document.getElementById('kpiConfigured').textContent = configured + ' / ' + total;
    document.getElementById('kpiHealthy').textContent = healthy;
    document.getElementById('kpiErrors').textContent = errors;
  }

  function applyFilters(item) {
    var f = state.filters;
    if (f.search) {
      var hay = (item.display_name + ' ' + item.name + ' ' + (item.category || '') + ' ' + (item.short_description || '')).toLowerCase();
      if (hay.indexOf(f.search) === -1) return false;
    }
    if (f.category && item.category !== f.category) return false;
    if (f.configured === 'yes' && !item.configured) return false;
    if (f.configured === 'no' && item.configured) return false;
    return true;
  }

  // ---------------------------------------------------------------------------
  // Grid (grouped by MODULE_CODE)
  // ---------------------------------------------------------------------------
  function moduleLabel(code) {
    if (!code) return MODULE_GROUPS.CORE;
    return MODULE_GROUPS[code] || (code.charAt(0) + code.slice(1).toLowerCase().replace(/_/g, ' '));
  }

  function groupByModule(items) {
    var groups = {};
    items.forEach(function (it) {
      var code = it.module_code || 'CORE';
      var label = moduleLabel(code);
      if (!groups[label]) groups[label] = [];
      groups[label].push(it);
    });
    // Sort items within each group by display name
    Object.keys(groups).forEach(function (k) {
      groups[k].sort(function (a, b) {
        return (a.display_name || a.name).localeCompare(b.display_name || b.name);
      });
    });
    // Return groups in alphabetical order of header label, but keep
    // "Other Integrations" last.
    var labels = Object.keys(groups).sort(function (a, b) {
      if (a === MODULE_GROUPS.CORE) return 1;
      if (b === MODULE_GROUPS.CORE) return -1;
      return a.localeCompare(b);
    });
    return labels.map(function (l) { return { label: l, items: groups[l] }; });
  }

  function renderGrid() {
    var grid = document.getElementById('catalogGrid');
    grid.textContent = '';
    var empty = document.getElementById('catalogEmpty');
    empty.style.display = 'none';

    var matches = state.items.filter(applyFilters);
    if (!matches.length) {
      empty.style.display = '';
      empty.textContent = '';
      empty.appendChild(window.URIP.shell.makeEmpty(
        'fa-magnifying-glass',
        state.items.length ? 'No integrations match those filters' : 'No integrations available',
        state.items.length ? 'Try clearing the search or filters.' : 'Connector backend may not be running yet.'
      ));
      return;
    }

    // Render module groups stacked: each group is a header + its own grid row.
    // We swap `.tc-grid` for `.tc-groups` here so headers can span the full
    // width without fighting the auto-fill column rules.
    grid.classList.remove('tc-grid');
    grid.classList.add('tc-groups');

    var groups = groupByModule(matches);
    groups.forEach(function (g) {
      var section = document.createElement('section');
      section.className = 'tc-group';

      var header = document.createElement('h2');
      header.className = 'tc-group-h';
      header.textContent = g.label;
      var count = document.createElement('span');
      count.className = 'tc-group-count';
      var configured = g.items.filter(function (i) { return i.configured; }).length;
      count.textContent = configured + ' / ' + g.items.length + ' configured';
      header.appendChild(count);
      section.appendChild(header);

      var inner = document.createElement('div');
      inner.className = 'tc-grid';
      g.items.forEach(function (it) { inner.appendChild(buildTile(it)); });
      section.appendChild(inner);

      grid.appendChild(section);
    });
  }

  function buildTile(item) {
    var tile = document.createElement('button');
    tile.type = 'button';
    tile.className = 'tc-tile';
    if (item.configured) tile.classList.add('is-configured');
    tile.setAttribute('data-tool', item.name);
    tile.setAttribute('aria-label',
      item.display_name + ' — ' + (item.configured ? 'configured' : 'available'));

    if (item.configured) {
      var mark = document.createElement('div');
      mark.className = 'tc-configured-mark';
      mark.innerHTML = '<i class="fas fa-circle-check"></i>';
      mark.title = 'Configured';
      tile.appendChild(mark);
    }

    var head = document.createElement('div');
    head.className = 'tc-tile-h';
    var logo = document.createElement('div');
    logo.className = 'tc-tile-logo';
    logo.textContent = (item.display_name || item.name).charAt(0).toUpperCase();
    head.appendChild(logo);
    var titles = document.createElement('div');
    titles.style.flex = '1';
    titles.style.minWidth = '0';
    var name = document.createElement('div');
    name.className = 'tc-tile-name';
    name.textContent = item.display_name || item.name;
    titles.appendChild(name);
    var cat = document.createElement('div');
    cat.className = 'tc-tile-cat';
    cat.textContent = item.category || '';
    titles.appendChild(cat);
    head.appendChild(titles);
    tile.appendChild(head);

    var desc = document.createElement('div');
    desc.className = 'tc-tile-desc';
    desc.textContent = item.short_description || '';
    tile.appendChild(desc);

    var foot = document.createElement('div');
    foot.className = 'tc-tile-foot';

    // Buyer-facing two-state pill: AVAILABLE vs CONFIGURED.
    // No internal lifecycle copy ("live" / "simulated" / etc.) on the tile.
    var statusPill = document.createElement('span');
    if (item.configured) {
      statusPill.className = 'u-pill is-configured';
      statusPill.textContent = 'CONFIGURED';
    } else {
      statusPill.className = 'u-pill is-available';
      statusPill.textContent = 'AVAILABLE';
    }
    foot.appendChild(statusPill);

    var meta = document.createElement('div');
    meta.className = 'tc-tile-meta';
    if (item.configured) {
      var sync = item.last_poll_at ? window.URIP.shell.relTime(item.last_poll_at) : 'never';
      var hStr = item.health_status === 'ok' ? '✓ healthy' :
                 item.health_status === 'error' ? '⚠ errors' :
                 item.health_status === 'degraded' ? '⚠ degraded' : '';
      meta.textContent = 'Sync ' + sync + (hStr ? ' • ' + hStr : '');
    } else {
      meta.textContent = 'Click to set up';
    }
    foot.appendChild(meta);
    tile.appendChild(foot);

    tile.addEventListener('click', function () { openDrawer(item); });
    return tile;
  }

  // ---------------------------------------------------------------------------
  // Drawer + setup guide
  // ---------------------------------------------------------------------------
  function wireDrawer() {
    document.getElementById('sgClose').addEventListener('click', closeDrawer);
    document.getElementById('sgMask').addEventListener('click', closeDrawer);
    document.addEventListener('keydown', function (e) {
      if (e.key === 'Escape' && document.getElementById('sgDrawer').classList.contains('is-open')) closeDrawer();
    });
  }

  function closeDrawer() {
    document.getElementById('sgDrawer').classList.remove('is-open');
    document.getElementById('sgDrawer').setAttribute('aria-hidden', 'true');
    document.getElementById('sgMask').classList.remove('is-open');
  }

  async function openDrawer(item) {
    var drawer = document.getElementById('sgDrawer');
    var mask = document.getElementById('sgMask');
    drawer.classList.add('is-open');
    drawer.setAttribute('aria-hidden', 'false');
    mask.classList.add('is-open');

    document.getElementById('sgTitle').textContent = item.display_name || item.name;
    document.getElementById('sgSubtitle').textContent = (item.category || '') + ' • Module: ' + (item.module_code || 'CORE');

    var body = document.getElementById('sgBody');
    body.textContent = '';
    body.appendChild(skeleton());

    // Fetch full guide
    var full = item;
    try {
      full = await window.URIP.apiFetch('/connectors/' + encodeURIComponent(item.name) + '/setup-guide', { silent: true });
    } catch (err) {
      // Use whatever we have on the list item
      full = item;
    }

    body.textContent = '';
    renderGuide(body, full || item);
    renderFooter(full || item);
  }

  function skeleton() {
    var d = document.createElement('div');
    for (var i = 0; i < 4; i++) {
      var s = document.createElement('div');
      s.className = 'u-skel';
      s.style.marginBottom = '10px';
      s.style.height = (14 + (i % 2) * 8) + 'px';
      d.appendChild(s);
    }
    return d;
  }

  function renderGuide(body, item) {
    var guide = item.setup_guide || null;

    // ----- Top status row -----
    // Buyer-facing: only show CONFIGURED / NOT CONFIGURED + error counter.
    // The internal lifecycle pill ("live" / "simulated" / …) is hidden here.
    var statusRow = document.createElement('div');
    statusRow.style.display = 'flex';
    statusRow.style.gap = '8px';
    statusRow.style.marginBottom = '14px';
    if (item.configured) {
      var p = document.createElement('span');
      p.className = 'u-badge is-ok';
      p.textContent = 'CONFIGURED';
      statusRow.appendChild(p);
    } else {
      var p2 = document.createElement('span');
      p2.className = 'u-badge is-info';
      p2.textContent = 'NOT CONFIGURED';
      statusRow.appendChild(p2);
    }
    if (item.error_count_24h > 0) {
      var p3 = document.createElement('span');
      p3.className = 'u-badge is-critical';
      p3.textContent = item.error_count_24h + ' ERRORS / 24H';
      statusRow.appendChild(p3);
    }
    body.appendChild(statusRow);

    if (item.short_description) {
      var sd = document.createElement('p');
      sd.style.color = 'var(--u-fg-2)';
      sd.style.fontSize = '13px';
      sd.style.lineHeight = '1.55';
      sd.style.marginBottom = '18px';
      sd.textContent = item.short_description;
      body.appendChild(sd);
    }

    // ----- If no setup_guide is present, fall back to credential_fields only -----
    if (!guide) {
      var note = document.createElement('div');
      note.className = 'u-empty';
      note.style.padding = '24px 0';
      note.appendChild(window.URIP.shell.makeEmpty(
        'fa-clipboard-list',
        'Setup guide not yet published',
        'The connector-setup-docs agent is still authoring this guide. You can still configure it below.'
      ));
      body.appendChild(note);
      body.appendChild(buildCredentialsForm(item));
      return;
    }

    // ----- Quick Facts -----
    if (guide.quick_facts) {
      var qf = guide.quick_facts;
      var sec = section('Quick Facts');
      var grid = document.createElement('div');
      grid.className = 'sg-quickfacts';
      [
        ['Category',     qf.category],
        ['Module',       qf.module],
        ['Difficulty',   qf.difficulty],
        ['Setup time',   qf.approx_setup_minutes + ' min'],
        ['Polling',      qf.polling_default_minutes + ' min'],
        ['Webhooks',     qf.supports_webhooks ? 'Yes' : 'No']
      ].forEach(function (kv) {
        if (kv[1] == null || kv[1] === 'undefined') return;
        var f = document.createElement('div');
        f.className = 'sg-fact';
        var l = document.createElement('div');
        l.className = 'sg-fact-label';
        l.textContent = kv[0];
        var v = document.createElement('div');
        v.className = 'sg-fact-value';
        v.textContent = kv[1];
        f.appendChild(l);
        f.appendChild(v);
        grid.appendChild(f);
      });
      sec.appendChild(grid);
      if (qf.vendor_docs_url) {
        var lnk = document.createElement('a');
        lnk.href = qf.vendor_docs_url;
        lnk.target = '_blank';
        lnk.rel = 'noopener';
        lnk.style.fontSize = '12px';
        lnk.style.color = 'var(--u-primary-2)';
        lnk.innerHTML = '<i class="fas fa-up-right-from-square"></i> Vendor documentation';
        sec.appendChild(lnk);
      }
      body.appendChild(sec);
    }

    // ----- What this pulls -----
    if (Array.isArray(guide.what_pulled) && guide.what_pulled.length) {
      var s2 = section('What this pulls');
      var ul = document.createElement('ul');
      ul.className = 'sg-bullets';
      guide.what_pulled.forEach(function (b) {
        var li = document.createElement('li');
        li.textContent = b;
        ul.appendChild(li);
      });
      s2.appendChild(ul);
      body.appendChild(s2);
    }

    // ----- Prerequisites -----
    if (Array.isArray(guide.prerequisites) && guide.prerequisites.length) {
      var s3 = section('Prerequisites');
      guide.prerequisites.forEach(function (p) {
        var row = document.createElement('div');
        row.style.padding = '8px 0';
        row.style.borderBottom = '1px solid var(--u-border)';
        var l = document.createElement('div');
        l.style.fontWeight = '600';
        l.style.fontSize = '12.5px';
        l.textContent = p.label;
        row.appendChild(l);
        var b = document.createElement('div');
        b.style.fontSize = '12.5px';
        b.style.color = 'var(--u-fg-2)';
        b.textContent = p.requirement;
        row.appendChild(b);
        s3.appendChild(row);
      });
      body.appendChild(s3);
    }

    // ----- Steps -----
    if (Array.isArray(guide.steps) && guide.steps.length) {
      var s4 = section('Step-by-Step Setup');
      guide.steps.forEach(function (st) {
        var row = document.createElement('div');
        row.className = 'sg-step';
        var n = document.createElement('div');
        n.className = 'sg-step-num';
        n.textContent = String(st.n);
        row.appendChild(n);
        var bd = document.createElement('div');
        bd.style.flex = '1';
        var t = document.createElement('div');
        t.className = 'sg-step-title';
        t.textContent = st.title;
        bd.appendChild(t);
        var b = document.createElement('div');
        b.className = 'sg-step-body';
        b.textContent = st.body;
        bd.appendChild(b);
        if (st.warning) {
          var w = document.createElement('div');
          w.className = 'sg-step-warn';
          w.innerHTML = '<i class="fas fa-triangle-exclamation"></i> ' + escapeHtml(st.warning);
          bd.appendChild(w);
        }
        row.appendChild(bd);
        s4.appendChild(row);
      });
      body.appendChild(s4);
    }

    // ----- Required scopes -----
    if (Array.isArray(guide.required_scopes) && guide.required_scopes.length) {
      var s5 = section('Required Scopes / Permissions');
      var sc = document.createElement('div');
      guide.required_scopes.forEach(function (sp) {
        var row = document.createElement('div');
        row.style.padding = '6px 0';
        row.style.borderBottom = '1px solid var(--u-border)';
        var n = document.createElement('div');
        n.className = 'mono';
        n.style.fontSize = '12.5px';
        n.style.color = 'var(--u-primary-2)';
        n.textContent = sp.name + (sp.required === false ? '  (optional)' : '');
        row.appendChild(n);
        var d = document.createElement('div');
        d.style.fontSize = '12px';
        d.style.color = 'var(--u-fg-2)';
        d.textContent = sp.description;
        row.appendChild(d);
        sc.appendChild(row);
      });
      s5.appendChild(sc);
      body.appendChild(s5);
    }

    // ----- Sample data (collapsible) -----
    if (guide.sample_data) {
      var s6 = section('Sample Data');
      var details = document.createElement('details');
      var summary = document.createElement('summary');
      summary.style.cursor = 'pointer';
      summary.style.fontSize = '13px';
      summary.style.color = 'var(--u-primary-2)';
      summary.textContent = 'Show one realistic finding (JSON)';
      details.appendChild(summary);
      var pre = document.createElement('pre');
      pre.className = 'sg-json';
      pre.textContent = JSON.stringify(guide.sample_data, null, 2);
      details.appendChild(pre);
      s6.appendChild(details);
      body.appendChild(s6);
    }

    // ----- Not collected -----
    if (Array.isArray(guide.not_collected) && guide.not_collected.length) {
      var s7 = section('What URIP does NOT receive');
      var ul2 = document.createElement('ul');
      ul2.className = 'sg-bullets';
      guide.not_collected.forEach(function (b) {
        var li = document.createElement('li');
        li.textContent = b;
        li.style.color = 'var(--u-ok)';
        ul2.appendChild(li);
      });
      s7.appendChild(ul2);
      body.appendChild(s7);
    }

    // ----- Common errors (accordion) -----
    if (Array.isArray(guide.common_errors) && guide.common_errors.length) {
      var s8 = section('Common Errors');
      guide.common_errors.forEach(function (e) {
        var det = document.createElement('details');
        det.className = 'sg-error-row';
        det.style.padding = '0';
        var sm = document.createElement('summary');
        sm.style.cursor = 'pointer';
        sm.style.padding = '10px 12px';
        sm.style.fontFamily = 'var(--u-font-mono)';
        sm.style.fontSize = '12px';
        sm.style.color = 'var(--sev-high)';
        sm.textContent = e.error;
        det.appendChild(sm);

        var inner = document.createElement('div');
        inner.style.padding = '10px 12px';
        var c = document.createElement('div');
        c.className = 'sg-error-cause';
        c.innerHTML = '<strong>Cause:</strong> ' + escapeHtml(e.cause);
        inner.appendChild(c);
        var f = document.createElement('div');
        f.className = 'sg-error-fix';
        f.innerHTML = '<strong>Fix:</strong> ' + escapeHtml(e.fix);
        inner.appendChild(f);
        det.appendChild(inner);
        s8.appendChild(det);
      });
      body.appendChild(s8);
    }

    // ----- Polling info -----
    if (guide.polling) {
      var s9 = section('Refresh & Cadence');
      var grid2 = document.createElement('div');
      grid2.className = 'sg-quickfacts';
      var pl = guide.polling;
      [
        ['Default poll',       pl.default_minutes + ' min'],
        ['First sync',         pl.first_sync_estimate_minutes + ' min'],
        ['Webhooks',           pl.webhook_supported ? 'Yes' : 'No'],
        ['Manual refresh',     pl.manual_refresh]
      ].forEach(function (kv) {
        var f = document.createElement('div');
        f.className = 'sg-fact';
        var l = document.createElement('div');
        l.className = 'sg-fact-label';
        l.textContent = kv[0];
        var v = document.createElement('div');
        v.className = 'sg-fact-value';
        v.textContent = kv[1];
        f.appendChild(l); f.appendChild(v);
        grid2.appendChild(f);
      });
      s9.appendChild(grid2);
      body.appendChild(s9);
    }

    // ----- Disconnect -----
    if (Array.isArray(guide.disconnect_steps) && guide.disconnect_steps.length) {
      var s10 = section('Disconnecting');
      var ol = document.createElement('ol');
      ol.style.paddingLeft = '20px';
      guide.disconnect_steps.forEach(function (st) {
        var li = document.createElement('li');
        li.style.padding = '4px 0';
        li.style.fontSize = '13px';
        li.style.color = 'var(--u-fg-2)';
        li.textContent = st;
        ol.appendChild(li);
      });
      s10.appendChild(ol);
      body.appendChild(s10);
    }

    // ----- Credentials form -----
    body.appendChild(buildCredentialsForm(item));
  }

  function buildCredentialsForm(item) {
    var sec = section('Save Credentials');
    var fields = item.credential_fields || [];
    if (!fields.length) {
      sec.appendChild(window.URIP.shell.makeEmpty('fa-key', 'No credentials needed', 'This connector ingests passively or via webhook.'));
      return sec;
    }
    var form = document.createElement('form');
    form.id = 'sgForm';
    form.dataset.tool = item.name;
    fields.forEach(function (f) {
      var fld = document.createElement('div');
      fld.style.marginBottom = '14px';
      var lbl = document.createElement('label');
      lbl.style.display = 'block';
      lbl.style.fontSize = '12px';
      lbl.style.fontWeight = '600';
      lbl.style.marginBottom = '4px';
      lbl.textContent = f.label + (f.required ? ' *' : '');
      fld.appendChild(lbl);

      var inp = document.createElement('input');
      inp.type = f.secret ? 'password' : (f.type || 'text');
      inp.name = f.name;
      inp.required = !!f.required;
      inp.className = 'u-input';
      inp.placeholder = f.placeholder || (f.help_text || '');
      if (f.default != null) inp.value = f.default;
      fld.appendChild(inp);

      if (f.help_text) {
        var ht = document.createElement('div');
        ht.style.fontSize = '11px';
        ht.style.color = 'var(--u-fg-3)';
        ht.style.marginTop = '4px';
        ht.textContent = f.help_text;
        fld.appendChild(ht);
      }
      form.appendChild(fld);
    });
    sec.appendChild(form);
    return sec;
  }

  function renderFooter(item) {
    var foot = document.getElementById('sgFooter');
    foot.textContent = '';

    var testBtn = document.createElement('button');
    testBtn.className = 'u-btn';
    testBtn.innerHTML = '<i class="fas fa-vial"></i> Test Connection';
    testBtn.addEventListener('click', function () { runAction(item, 'test'); });
    foot.appendChild(testBtn);

    if (item.configured) {
      var disBtn = document.createElement('button');
      disBtn.className = 'u-btn is-danger';
      disBtn.innerHTML = '<i class="fas fa-trash-can"></i> Disconnect';
      disBtn.addEventListener('click', function () { runAction(item, 'delete'); });
      foot.appendChild(disBtn);
    }

    var saveBtn = document.createElement('button');
    saveBtn.className = 'u-btn is-primary';
    saveBtn.innerHTML = '<i class="fas fa-circle-check"></i> ' + (item.configured ? 'Update' : 'Save & Enable');
    saveBtn.addEventListener('click', function () { runAction(item, 'save'); });
    foot.appendChild(saveBtn);
  }

  async function runAction(item, action) {
    var form = document.getElementById('sgForm');
    var creds = {};
    if (form) {
      Array.from(form.elements).forEach(function (f) {
        if (f.name) creds[f.name] = f.value;
      });
    }

    if (action === 'test') {
      try {
        var r = await window.URIP.apiFetch('/connectors/' + encodeURIComponent(item.name) + '/test', {
          method: 'POST',
          body: JSON.stringify({ credentials: creds })
        });
        window.URIP.showNotification(r.success ? 'Test passed' : 'Test failed', r.message || '', r.success ? 'success' : 'error');
      } catch (err) {
        window.URIP.showNotification('Test failed', err.message || 'Unknown error', 'error');
      }
    }

    if (action === 'save') {
      try {
        await window.URIP.apiFetch('/connectors/' + encodeURIComponent(item.name) + '/configure', {
          method: 'POST',
          body: JSON.stringify({ credentials: creds })
        });
        window.URIP.showNotification('Saved', item.display_name + ' is now configured.', 'success');
        closeDrawer();
        load();
      } catch (err) {
        window.URIP.showNotification('Save failed', err.message || 'Unknown error', 'error');
      }
    }

    if (action === 'delete') {
      if (!confirm('Disconnect ' + item.display_name + '? URIP will stop polling and credentials will be deleted.')) return;
      try {
        await window.URIP.apiFetch('/connectors/' + encodeURIComponent(item.name), { method: 'DELETE' });
        window.URIP.showNotification('Disconnected', item.display_name + ' was disconnected.', 'success');
        closeDrawer();
        load();
      } catch (err) {
        window.URIP.showNotification('Disconnect failed', err.message || 'Unknown error', 'error');
      }
    }
  }

  // ---------------------------------------------------------------------------
  // Helpers
  // ---------------------------------------------------------------------------
  function section(title) {
    var sec = document.createElement('div');
    sec.className = 'sg-section';
    var h = document.createElement('h3');
    h.textContent = title;
    sec.appendChild(h);
    return sec;
  }

  function escapeHtml(s) {
    if (!s) return '';
    return String(s).replace(/[&<>"']/g, function (c) {
      return ({ '&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;' })[c];
    });
  }
})();
