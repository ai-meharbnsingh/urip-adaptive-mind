/**
 * URIP — Module Tools (Available Integrations) renderer.
 *
 * Used at the TOP of every domain-*.html page. Fetches GET /api/connectors,
 * filters the result by `module_code` (one or more module codes per page),
 * renders a "discovery" grid of vendor cards, and opens an inline right-side
 * drawer to configure credentials when the user clicks Configure.
 *
 * Public API:
 *   loadModuleTools(moduleCodes, containerId, opts)
 *     - moduleCodes: string[]   e.g. ['EDR','VM']  (matched against connector.module_code)
 *     - containerId: string     id of the <div> that should host the grid
 *     - opts: { title?, subtitle?, manageHref? }
 *
 * Conventions:
 *   - Strict no-innerHTML; uses createElement everywhere
 *   - Reuses window.URIP.apiFetch (api.js) — same JWT, same base URL
 *   - The drawer DOM is injected lazily on first use (one drawer per page)
 *   - Save / Test / Disconnect reuse the same backend endpoints as
 *     tool-catalog.html (/connectors/{name}/configure, /test, DELETE)
 */
(function () {
  'use strict';

  // ---------------------------------------------------------------------------
  // DOM helpers
  // ---------------------------------------------------------------------------
  function el(tag, className, text) {
    var n = document.createElement(tag);
    if (className) n.className = className;
    if (text != null) n.textContent = text;
    return n;
  }
  function faIcon(cls) {
    var i = document.createElement('i');
    i.className = 'fas ' + cls;
    return i;
  }

  // ---------------------------------------------------------------------------
  // Drawer (singleton) — created lazily
  // ---------------------------------------------------------------------------
  function ensureDrawer() {
    if (document.getElementById('mtDrawer')) return;

    var mask = el('div', 'mt-drawer-mask');
    mask.id = 'mtDrawerMask';
    mask.addEventListener('click', closeDrawer);
    document.body.appendChild(mask);

    var drawer = document.createElement('aside');
    drawer.className = 'mt-drawer';
    drawer.id = 'mtDrawer';
    drawer.setAttribute('aria-hidden', 'true');

    // Header
    var head = el('div', 'mt-drawer-h');
    var titleBlock = el('div');
    var h2 = document.createElement('h2');
    h2.id = 'mtDrawerTitle';
    h2.textContent = 'Configure Tool';
    titleBlock.appendChild(h2);
    var sub = el('div', 'mt-drawer-sub');
    sub.id = 'mtDrawerSub';
    titleBlock.appendChild(sub);
    head.appendChild(titleBlock);

    var closeBtn = el('button', 'mt-drawer-close');
    closeBtn.id = 'mtDrawerClose';
    closeBtn.setAttribute('aria-label', 'Close');
    closeBtn.appendChild(faIcon('fa-xmark'));
    closeBtn.addEventListener('click', closeDrawer);
    head.appendChild(closeBtn);
    drawer.appendChild(head);

    // Body
    var body = el('div', 'mt-drawer-b');
    body.id = 'mtDrawerBody';
    drawer.appendChild(body);

    // Footer
    var foot = el('div', 'mt-drawer-f');
    foot.id = 'mtDrawerFooter';
    drawer.appendChild(foot);

    document.body.appendChild(drawer);

    // Esc to close
    document.addEventListener('keydown', function (e) {
      if (e.key === 'Escape' && drawer.classList.contains('is-open')) closeDrawer();
    });
  }

  function closeDrawer() {
    var d = document.getElementById('mtDrawer');
    var m = document.getElementById('mtDrawerMask');
    if (d) {
      d.classList.remove('is-open');
      d.setAttribute('aria-hidden', 'true');
    }
    if (m) m.classList.remove('is-open');
  }

  function openDrawer(item) {
    ensureDrawer();
    var drawer = document.getElementById('mtDrawer');
    var mask = document.getElementById('mtDrawerMask');
    drawer.classList.add('is-open');
    drawer.setAttribute('aria-hidden', 'false');
    mask.classList.add('is-open');

    document.getElementById('mtDrawerTitle').textContent = item.display_name || item.name;
    document.getElementById('mtDrawerSub').textContent =
      (item.category || '') + ' · Module: ' + (item.module_code || 'CORE');

    var body = document.getElementById('mtDrawerBody');
    body.textContent = '';

    // Loading skeleton while we fetch the full setup-guide
    for (var i = 0; i < 4; i++) {
      var s = el('div', 'mt-skel');
      s.style.width = (50 + Math.random() * 40) + '%';
      body.appendChild(s);
    }

    fetchSetupGuide(item).then(function (full) {
      body.textContent = '';
      renderDrawerBody(body, full || item);
      renderDrawerFooter(full || item);
    });
  }

  async function fetchSetupGuide(item) {
    var apiFetch = window.URIP && window.URIP.apiFetch;
    if (!apiFetch) return item;
    try {
      return await apiFetch(
        '/connectors/' + encodeURIComponent(item.name) + '/setup-guide',
        { silent: true }
      );
    } catch (_e) {
      return item;
    }
  }

  function renderDrawerBody(body, item) {
    // Status pills row
    var statusRow = el('div');
    statusRow.style.display = 'flex';
    statusRow.style.gap = '8px';
    statusRow.style.flexWrap = 'wrap';
    statusRow.style.marginBottom = '14px';

    var statusPill = el('span', 'mt-pill ' + (item.configured ? 'is-configured' : 'is-available'));
    statusPill.textContent = item.configured ? 'CONFIGURED' : 'AVAILABLE';
    statusRow.appendChild(statusPill);

    if (item.status) {
      var lifePill = el('span', 'mt-pill is-roadmap');
      lifePill.textContent = String(item.status).toUpperCase();
      statusRow.appendChild(lifePill);
    }
    body.appendChild(statusRow);

    if (item.short_description) {
      var desc = el('p', 'mt-drawer-desc');
      desc.textContent = item.short_description;
      body.appendChild(desc);
    }

    var guide = item.setup_guide || null;

    // Quick facts (compact)
    if (guide && guide.quick_facts) {
      var qf = guide.quick_facts;
      var qSec = el('div', 'mt-drawer-section');
      var qH = el('h3', null, 'Quick Facts');
      qSec.appendChild(qH);
      var qList = el('div');
      qList.style.fontSize = '13px';
      qList.style.color = 'var(--gray-700, #475569)';
      qList.style.lineHeight = '1.7';
      [
        ['Category',   qf.category],
        ['Module',     qf.module],
        ['Difficulty', qf.difficulty],
        ['Setup time', qf.approx_setup_minutes != null ? qf.approx_setup_minutes + ' min' : null],
        ['Polling',    qf.polling_default_minutes != null ? qf.polling_default_minutes + ' min' : null]
      ].forEach(function (kv) {
        if (kv[1] == null) return;
        var row = el('div');
        var k = el('span');
        k.style.color = 'var(--gray-500, #94A3B8)';
        k.style.display = 'inline-block';
        k.style.minWidth = '100px';
        k.textContent = kv[0] + ':';
        var v = el('span');
        v.style.fontWeight = '500';
        v.textContent = kv[1];
        row.appendChild(k);
        row.appendChild(v);
        qList.appendChild(row);
      });
      qSec.appendChild(qList);
      body.appendChild(qSec);
    }

    // Credentials form
    body.appendChild(buildCredentialsForm(item));
  }

  function buildCredentialsForm(item) {
    var sec = el('div', 'mt-drawer-section');
    var h = el('h3', null, 'Credentials');
    sec.appendChild(h);

    var fields = item.credential_fields || [];
    if (!fields.length) {
      var none = el('div');
      none.style.fontSize = '13px';
      none.style.color = 'var(--gray-500, #94A3B8)';
      none.textContent = 'This connector ingests passively or via webhook — no credentials required.';
      sec.appendChild(none);
      return sec;
    }

    var form = document.createElement('form');
    form.id = 'mtForm';
    form.dataset.tool = item.name;
    form.addEventListener('submit', function (e) { e.preventDefault(); });

    fields.forEach(function (f) {
      var fld = el('div', 'mt-field');
      var lbl = document.createElement('label');
      lbl.textContent = f.label + (f.required ? ' *' : '');
      fld.appendChild(lbl);

      var inp = document.createElement('input');
      inp.type = f.secret ? 'password' : (f.type || 'text');
      inp.name = f.name;
      inp.required = !!f.required;
      inp.placeholder = f.placeholder || (f.help_text || '');
      if (f.default != null) inp.value = f.default;
      fld.appendChild(inp);

      if (f.help_text) {
        var ht = el('div', 'mt-field-help', f.help_text);
        fld.appendChild(ht);
      }
      form.appendChild(fld);
    });

    sec.appendChild(form);
    return sec;
  }

  function renderDrawerFooter(item) {
    var foot = document.getElementById('mtDrawerFooter');
    foot.textContent = '';

    var cancel = el('button', 'mt-drawer-btn is-ghost');
    cancel.type = 'button';
    cancel.textContent = 'Cancel';
    cancel.addEventListener('click', closeDrawer);
    foot.appendChild(cancel);

    var test = el('button', 'mt-drawer-btn is-ghost');
    test.type = 'button';
    test.appendChild(faIcon('fa-vial'));
    test.appendChild(document.createTextNode(' Test'));
    test.addEventListener('click', function () { runAction(item, 'test'); });
    foot.appendChild(test);

    if (item.configured) {
      var dis = el('button', 'mt-drawer-btn is-danger');
      dis.type = 'button';
      dis.appendChild(faIcon('fa-trash-can'));
      dis.appendChild(document.createTextNode(' Disconnect'));
      dis.addEventListener('click', function () { runAction(item, 'delete'); });
      foot.appendChild(dis);
    }

    var save = el('button', 'mt-drawer-btn is-primary');
    save.type = 'button';
    save.appendChild(faIcon('fa-circle-check'));
    save.appendChild(document.createTextNode(' ' + (item.configured ? 'Update' : 'Save & Enable')));
    save.addEventListener('click', function () { runAction(item, 'save'); });
    foot.appendChild(save);
  }

  function collectFormCreds() {
    var form = document.getElementById('mtForm');
    var creds = {};
    if (!form) return creds;
    Array.from(form.elements).forEach(function (f) {
      if (f.name) creds[f.name] = f.value;
    });
    return creds;
  }

  async function runAction(item, action) {
    var apiFetch = window.URIP && window.URIP.apiFetch;
    var notify = (window.URIP && window.URIP.showNotification) || function (t, m) { console.log(t, m); };
    if (!apiFetch) { notify('Error', 'API client unavailable', 'error'); return; }

    var creds = collectFormCreds();

    if (action === 'test') {
      try {
        var r = await apiFetch('/connectors/' + encodeURIComponent(item.name) + '/test', {
          method: 'POST',
          body: JSON.stringify({ credentials: creds })
        });
        notify(r && r.success ? 'Test passed' : 'Test failed',
               (r && r.message) || '',
               r && r.success ? 'success' : 'error');
      } catch (err) {
        notify('Test failed', err.message || 'Unknown error', 'error');
      }
      return;
    }

    if (action === 'save') {
      try {
        await apiFetch('/connectors/' + encodeURIComponent(item.name) + '/configure', {
          method: 'POST',
          body: JSON.stringify({ credentials: creds })
        });
        notify('Saved', (item.display_name || item.name) + ' is now configured.', 'success');
        closeDrawer();
        // Refresh all module-tools containers on the page
        if (window.__mtRefresh) window.__mtRefresh();
      } catch (err) {
        notify('Save failed', err.message || 'Unknown error', 'error');
      }
      return;
    }

    if (action === 'delete') {
      if (!confirm('Disconnect ' + (item.display_name || item.name) + '?')) return;
      try {
        await apiFetch('/connectors/' + encodeURIComponent(item.name), { method: 'DELETE' });
        notify('Disconnected', (item.display_name || item.name) + ' was disconnected.', 'success');
        closeDrawer();
        if (window.__mtRefresh) window.__mtRefresh();
      } catch (err) {
        notify('Disconnect failed', err.message || 'Unknown error', 'error');
      }
    }
  }

  // ---------------------------------------------------------------------------
  // Card rendering
  // ---------------------------------------------------------------------------
  function buildCard(item) {
    var card = el('div', 'mt-card' + (item.configured ? ' is-configured' : ''));
    card.dataset.tool = item.name;

    var head = el('div', 'mt-card-head');
    var logo = el('div', 'mt-card-logo');
    logo.textContent = (item.display_name || item.name).charAt(0).toUpperCase();
    head.appendChild(logo);

    var titles = el('div', 'mt-card-titles');
    var name = el('div', 'mt-card-name', item.display_name || item.name);
    titles.appendChild(name);
    var meta = el('div', 'mt-card-meta');
    var metaParts = [];
    if (item.category) metaParts.push(item.category);
    if (item.status) metaParts.push(item.status);
    meta.textContent = metaParts.join(' · ');
    titles.appendChild(meta);
    head.appendChild(titles);
    card.appendChild(head);

    var desc = el('div', 'mt-card-desc',
      item.short_description || 'Vendor integration for this domain.');
    card.appendChild(desc);

    var foot = el('div', 'mt-card-foot');
    var pill = el('span', 'mt-pill ' + (item.configured ? 'is-configured' : 'is-available'));
    pill.textContent = item.configured ? 'CONFIGURED' : 'AVAILABLE';
    foot.appendChild(pill);

    var btn = el('button', 'mt-configure-btn' + (item.configured ? ' is-secondary' : ''));
    btn.type = 'button';
    btn.appendChild(faIcon(item.configured ? 'fa-gear' : 'fa-plug'));
    btn.appendChild(document.createTextNode(' ' + (item.configured ? 'Manage' : 'Configure')));
    btn.addEventListener('click', function () { openDrawer(item); });
    foot.appendChild(btn);

    card.appendChild(foot);
    return card;
  }

  function renderEmpty(container, moduleCodes) {
    var box = el('div', 'mt-empty');
    var msg = el('div');
    msg.style.marginBottom = '0.375rem';
    msg.style.fontWeight = '600';
    msg.style.color = 'var(--gray-700, #475569)';
    msg.textContent = 'No connectors registered for this module yet';
    box.appendChild(msg);

    var sub = el('div');
    sub.textContent = 'Looking for: ' + (moduleCodes || []).join(', ') +
      '. New vendor integrations will appear here as they’re wired up.';
    box.appendChild(sub);

    var br = document.createElement('div');
    br.style.marginTop = '0.625rem';
    var link = document.createElement('a');
    link.href = 'tool-catalog.html';
    link.textContent = 'Browse the full Tool Catalog →';
    br.appendChild(link);
    box.appendChild(br);

    container.appendChild(box);
  }

  // ---------------------------------------------------------------------------
  // Public loader
  // ---------------------------------------------------------------------------
  // Track containers so the drawer save-handler can refresh them all.
  var _registered = [];

  function refreshAll() {
    _registered.forEach(function (r) {
      loadModuleTools(r.codes, r.id, r.opts, true);
    });
  }
  window.__mtRefresh = refreshAll;

  /**
   * Load + render the "Available integrations" section.
   *
   * @param {string[]} moduleCodes  e.g. ['EDR','VM']
   * @param {string}   containerId  id of the host <div>
   * @param {object}   [opts]       { title, subtitle, manageHref }
   * @param {boolean}  [_internal]  used by refreshAll to avoid re-registering
   */
  function loadModuleTools(moduleCodes, containerId, opts, _internal) {
    opts = opts || {};
    moduleCodes = (moduleCodes || []).map(function (c) { return String(c).toUpperCase(); });

    var host = document.getElementById(containerId);
    if (!host) {
      console.warn('module-tools: container not found:', containerId);
      return;
    }

    // Track once for refreshAll
    if (!_internal) {
      _registered.push({ codes: moduleCodes, id: containerId, opts: opts });
    }

    // Build (or rebuild) section structure
    host.textContent = '';
    host.classList.add('mt-section');

    var headRow = el('div', 'mt-section-head');
    var titleBlock = el('div');
    var h2 = document.createElement('h2');
    h2.textContent = opts.title || 'Available integrations for this module';
    titleBlock.appendChild(h2);
    var subEl = el('div', 'mt-sub');
    subEl.textContent = opts.subtitle ||
      'Connect any of the vendor tools below to start ingesting findings into this domain.';
    titleBlock.appendChild(subEl);
    headRow.appendChild(titleBlock);

    if (opts.manageHref) {
      var manageBtn = el('a', 'btn btn-sm btn-outline');
      manageBtn.href = opts.manageHref;
      manageBtn.appendChild(faIcon('fa-puzzle-piece'));
      manageBtn.appendChild(document.createTextNode(' All tools'));
      headRow.appendChild(manageBtn);
    }
    host.appendChild(headRow);

    var grid = el('div', 'mt-grid');
    grid.id = containerId + '-grid';
    host.appendChild(grid);

    // Skeletons
    for (var i = 0; i < 3; i++) {
      var sCard = el('div', 'mt-card');
      sCard.style.minHeight = '160px';
      var s1 = el('div', 'mt-skel');
      s1.style.width = '70%';
      sCard.appendChild(s1);
      var s2 = el('div', 'mt-skel');
      s2.style.width = '90%';
      s2.style.height = '40px';
      sCard.appendChild(s2);
      grid.appendChild(sCard);
    }

    var apiFetch = window.URIP && window.URIP.apiFetch;
    if (!apiFetch) {
      grid.textContent = '';
      var err = el('div', 'mt-empty');
      err.textContent = 'API client not loaded. Please refresh the page.';
      grid.appendChild(err);
      return;
    }

    // Try server-side filter first; fall back to fetching all + client-filter.
    var moduleQ = moduleCodes.length ? '?module=' + encodeURIComponent(moduleCodes.join(',')) + '&limit=200'
                                     : '?limit=200';

    apiFetch('/connectors' + moduleQ, { silent: true })
      .catch(function () { return apiFetch('/connectors?limit=200', { silent: true }); })
      .then(function (resp) {
        var items = (resp && resp.items) || [];
        // Client-side filter regardless (server may not support module= yet)
        var matched = items.filter(function (it) {
          if (!moduleCodes.length) return true;
          var mc = String(it.module_code || '').toUpperCase();
          return moduleCodes.indexOf(mc) >= 0;
        });

        // Sort: configured first, then live, then by name
        matched.sort(function (a, b) {
          if (!!b.configured - !!a.configured) return !!b.configured - !!a.configured;
          var sa = (a.status === 'live') ? 1 : 0;
          var sb = (b.status === 'live') ? 1 : 0;
          if (sb !== sa) return sb - sa;
          return (a.display_name || a.name).localeCompare(b.display_name || b.name);
        });

        grid.textContent = '';
        if (!matched.length) {
          renderEmpty(grid, moduleCodes);
          return;
        }
        matched.forEach(function (it) { grid.appendChild(buildCard(it)); });
      })
      .catch(function (err) {
        grid.textContent = '';
        var box = el('div', 'mt-empty');
        var msg = el('div');
        msg.style.color = '#B91C1C';
        msg.style.fontWeight = '600';
        msg.textContent = 'Could not load connectors';
        box.appendChild(msg);
        var sub = el('div');
        sub.textContent = (err && err.message) || 'Network error';
        box.appendChild(sub);
        grid.appendChild(box);
      });
  }

  // Public API
  window.loadModuleTools = loadModuleTools;
})();
