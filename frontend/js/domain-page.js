/**
 * URIP - Shared Domain Dashboard Renderer (Wave B)
 *
 * Powers the 10 domain pages + asset pages by providing:
 *   - DomainPage.init(config)        — boot a domain page
 *   - DomainPage.fetchRisksForSources(sources)  — multi-source risk fetch
 *   - DomainPage.renderConnectorTile(...)
 *   - DomainPage.renderRiskRow(...)
 *
 * Depends on: api.js (URIP.apiFetch), sidebar.js (renderSidebar), auth.js
 * Strict no-innerHTML — uses createElement throughout.
 */
(function () {
  'use strict';

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

  /**
   * Fetch the union of risks for one or more sources (the backend filter
   * is single-valued, so we run N parallel calls and merge).
   * @param {string[]} sources lowercase source names
   * @param {object} [opts] { limit, signal }
   * @returns {Promise<{items: Array, totalBySource: Object}>}
   */
  async function fetchRisksForSources(sources, opts) {
    opts = opts || {};
    var limit = opts.limit || 7;
    var perSource = Math.max(2, Math.ceil(limit * 1.5));
    var apiFetch = window.URIP && window.URIP.apiFetch;
    if (!apiFetch) return { items: [], totalBySource: {} };

    var calls = sources.map(function (s) {
      var path = '/risks?source=' + encodeURIComponent(s) +
                 '&per_page=' + perSource +
                 '&sort_by=composite_score&order=desc';
      return apiFetch(path, { silent: true })
        .then(function (resp) { return { source: s, resp: resp }; })
        .catch(function (err) { return { source: s, error: err }; });
    });

    var results = await Promise.all(calls);
    var merged = [];
    var totals = {};
    results.forEach(function (r) {
      if (r.error || !r.resp || !r.resp.items) {
        totals[r.source] = 0;
        return;
      }
      totals[r.source] = r.resp.total || r.resp.items.length;
      merged = merged.concat(r.resp.items);
    });

    // Sort merged by composite_score desc; fallback to severity weight
    var sevWeight = { critical: 4, high: 3, medium: 2, low: 1, info: 0 };
    merged.sort(function (a, b) {
      var sa = (a.composite_score != null) ? a.composite_score
             : (sevWeight[(a.severity || '').toLowerCase()] || 0);
      var sb = (b.composite_score != null) ? b.composite_score
             : (sevWeight[(b.severity || '').toLowerCase()] || 0);
      return sb - sa;
    });
    return { items: merged.slice(0, limit), totalBySource: totals };
  }

  /**
   * Try /api/risks?domain=X first; on empty/404, fall back to source filter.
   */
  async function fetchRisksForDomain(domain, sources, opts) {
    opts = opts || {};
    var limit = opts.limit || 7;
    var apiFetch = window.URIP && window.URIP.apiFetch;
    if (!apiFetch) return { items: [], totalBySource: {}, total: 0 };

    try {
      var path = '/risks?domain=' + encodeURIComponent(domain) +
                 '&per_page=' + limit +
                 '&sort_by=composite_score&order=desc';
      var resp = await apiFetch(path, { silent: true });
      if (resp && resp.items && resp.items.length > 0) {
        return { items: resp.items, total: resp.total || resp.items.length, totalBySource: {} };
      }
      // Domain field may be empty — fall back to source union
      if (sources && sources.length) {
        var fall = await fetchRisksForSources(sources, { limit: limit });
        return { items: fall.items, total: fall.items.length, totalBySource: fall.totalBySource, fellBackToSource: true };
      }
      return { items: [], total: 0, totalBySource: {} };
    } catch (e) {
      if (sources && sources.length) {
        var fb = await fetchRisksForSources(sources, { limit: limit });
        return { items: fb.items, total: fb.items.length, totalBySource: fb.totalBySource, fellBackToSource: true };
      }
      throw e;
    }
  }

  /**
   * Fetch connector status for a list of connector names. Each call is
   * /api/connectors/{name}/health; tolerant of 404 (returns null entry).
   */
  async function fetchConnectorHealth(names) {
    var apiFetch = window.URIP && window.URIP.apiFetch;
    if (!apiFetch) return [];
    var calls = names.map(function (n) {
      return apiFetch('/connectors/' + encodeURIComponent(n) + '/health', { silent: true })
        .then(function (h) { return { name: n, health: h, configured: true }; })
        .catch(function () { return { name: n, health: null, configured: false }; });
    });
    return await Promise.all(calls);
  }

  /**
   * Fetch the catalog tile for one connector (display_name etc.).
   */
  async function fetchConnectorMeta(name) {
    var apiFetch = window.URIP && window.URIP.apiFetch;
    if (!apiFetch) return null;
    try {
      return await apiFetch('/connectors/' + encodeURIComponent(name) + '/setup-guide', { silent: true });
    } catch (e) { return null; }
  }

  /**
   * Render a connector tile.
   * @param {object} info { name, display_name, configured, health, lastPoll, errorCount24h }
   */
  function renderConnectorTile(info) {
    var card = el('div', 'card');
    card.style.padding = '1rem';
    card.style.minHeight = '160px';
    card.style.display = 'flex';
    card.style.flexDirection = 'column';
    card.style.gap = '0.5rem';

    var head = el('div');
    head.style.display = 'flex';
    head.style.justifyContent = 'space-between';
    head.style.alignItems = 'flex-start';
    head.style.gap = '0.75rem';

    var titleBox = el('div');
    titleBox.style.flex = '1';
    var title = el('div');
    title.style.fontWeight = '600';
    title.style.color = 'var(--gray-900)';
    title.style.fontSize = '15px';
    title.textContent = info.display_name || info.name;
    titleBox.appendChild(title);
    var sub = el('div');
    sub.style.fontSize = '12px';
    sub.style.color = 'var(--gray-500)';
    sub.style.marginTop = '2px';
    sub.textContent = info.name;
    titleBox.appendChild(sub);
    head.appendChild(titleBox);

    var pill = el('span');
    pill.style.fontSize = '11px';
    pill.style.padding = '3px 9px';
    pill.style.borderRadius = '999px';
    pill.style.fontWeight = '600';
    pill.style.textTransform = 'uppercase';
    pill.style.letterSpacing = '0.04em';
    if (!info.configured) {
      pill.style.background = 'rgba(148,163,184,0.18)';
      pill.style.color = 'var(--gray-500)';
      pill.textContent = 'Not configured';
    } else if (info.health === 'healthy' || info.health === 'ok') {
      pill.style.background = 'rgba(39,174,96,0.15)';
      pill.style.color = 'var(--green-low, #27AE60)';
      pill.textContent = 'Healthy';
    } else if (info.health === 'degraded' || info.health === 'warn') {
      pill.style.background = 'rgba(241,196,15,0.18)';
      pill.style.color = '#B7791F';
      pill.textContent = 'Degraded';
    } else if (info.health === 'error' || info.health === 'unhealthy') {
      pill.style.background = 'rgba(231,76,60,0.15)';
      pill.style.color = 'var(--red-critical, #E74C3C)';
      pill.textContent = 'Error';
    } else {
      pill.style.background = 'rgba(148,163,184,0.18)';
      pill.style.color = 'var(--gray-500)';
      pill.textContent = 'Unknown';
    }
    head.appendChild(pill);
    card.appendChild(head);

    // Stats row
    var stats = el('div');
    stats.style.display = 'flex';
    stats.style.gap = '1rem';
    stats.style.fontSize = '12px';
    stats.style.color = 'var(--gray-600)';
    stats.style.marginTop = '0.25rem';

    var lastPoll = el('div');
    lastPoll.appendChild(faIcon('fa-clock'));
    var lpTxt = document.createTextNode(' Last poll: ' + (info.lastPoll ? formatRelative(info.lastPoll) : '—'));
    lastPoll.appendChild(lpTxt);
    stats.appendChild(lastPoll);

    var errors = el('div');
    errors.appendChild(faIcon('fa-circle-exclamation'));
    errors.appendChild(document.createTextNode(' Errors 24h: ' + (info.errorCount24h != null ? info.errorCount24h : 0)));
    if (info.errorCount24h && info.errorCount24h > 0) {
      errors.style.color = 'var(--red-critical, #E74C3C)';
    }
    stats.appendChild(errors);
    card.appendChild(stats);

    // Spacer
    var spacer = el('div');
    spacer.style.flex = '1';
    card.appendChild(spacer);

    // Action buttons
    var actions = el('div');
    actions.style.display = 'flex';
    actions.style.gap = '0.5rem';
    actions.style.marginTop = '0.5rem';

    var btn = el('a', 'btn btn-sm ' + (info.configured ? 'btn-outline' : 'btn-primary'));
    btn.href = info.configured
      ? 'connector-status.html#' + encodeURIComponent(info.name)
      : 'tool-catalog.html#' + encodeURIComponent(info.name);
    btn.style.flex = '1';
    btn.style.textAlign = 'center';
    btn.appendChild(faIcon(info.configured ? 'fa-gear' : 'fa-plug'));
    btn.appendChild(document.createTextNode(' ' + (info.configured ? 'Configure' : 'Connect')));
    actions.appendChild(btn);

    card.appendChild(actions);
    return card;
  }

  /**
   * Render a risk row (similar to dashboard alerts table).
   */
  function renderRiskRow(r) {
    var tr = document.createElement('tr');
    var tdId = el('td');
    var s = el('span', 'risk-id', r.risk_id || '—');
    tdId.appendChild(s);
    tr.appendChild(tdId);

    var tdF = el('td');
    var fName = el('div');
    fName.style.fontWeight = '500';
    fName.style.color = 'var(--gray-900)';
    fName.textContent = r.finding || '(no title)';
    tdF.appendChild(fName);
    if (r.asset) {
      var fMeta = el('div');
      fMeta.style.fontSize = '12px';
      fMeta.style.color = 'var(--gray-500)';
      fMeta.style.marginTop = '2px';
      fMeta.textContent = r.asset;
      tdF.appendChild(fMeta);
    }
    tr.appendChild(tdF);

    var tdSrc = el('td');
    tdSrc.style.fontSize = '13px';
    tdSrc.style.color = 'var(--gray-600)';
    tdSrc.textContent = r.source || '—';
    tr.appendChild(tdSrc);

    var tdScore = el('td');
    var sc = el('span');
    sc.style.fontWeight = '600';
    var scoreVal = (r.composite_score != null) ? r.composite_score
                 : (r.cvss_score != null ? r.cvss_score : '—');
    sc.textContent = (typeof scoreVal === 'number') ? scoreVal.toFixed(1) : scoreVal;
    tdScore.appendChild(sc);
    tr.appendChild(tdScore);

    var tdSev = el('td');
    var sev = el('span', 'badge badge-' + ((r.severity || 'info').toLowerCase()), r.severity || '—');
    tdSev.appendChild(sev);
    tr.appendChild(tdSev);

    return tr;
  }

  /**
   * Render an empty state inside a container.
   */
  function renderEmpty(container, opts) {
    opts = opts || {};
    container.textContent = '';
    var box = el('div', 'empty-state');
    var icon = el('div', 'empty-state-icon');
    icon.appendChild(faIcon(opts.icon || 'fa-folder-open'));
    box.appendChild(icon);
    var title = el('div', 'empty-state-title', opts.title || 'No data yet');
    box.appendChild(title);
    if (opts.text) {
      var text = el('div', 'empty-state-text', opts.text);
      box.appendChild(text);
    }
    if (opts.cta) {
      var ctaWrap = el('div');
      ctaWrap.style.marginTop = '0.75rem';
      var btn = el('a', 'btn btn-primary');
      btn.href = opts.cta.href;
      btn.appendChild(faIcon('fa-arrow-right'));
      btn.appendChild(document.createTextNode(' ' + opts.cta.label));
      ctaWrap.appendChild(btn);
      box.appendChild(ctaWrap);
    }
    container.appendChild(box);
  }

  function formatRelative(iso) {
    if (!iso) return '—';
    try {
      var d = new Date(iso);
      var diff = (Date.now() - d.getTime()) / 1000;
      if (diff < 60) return Math.round(diff) + 's ago';
      if (diff < 3600) return Math.round(diff / 60) + 'm ago';
      if (diff < 86400) return Math.round(diff / 3600) + 'h ago';
      return Math.round(diff / 86400) + 'd ago';
    } catch (e) { return iso; }
  }

  /**
   * Boot a domain page. config = {
   *   domainSlug: 'network',          // sidebar active page id (string)
   *   connectors: ['zscaler', ...],   // connector names
   *   sources: ['zscaler', ...],      // risk source filters (often = connectors)
   *   domainField: 'network',         // optional Risk.domain value
   *   catalogCategory: 'NETWORK',     // for "Manage Connectors" deep link
   *   onSpecialWidgets: function(ctx) { ... }   // page-specific widgets
   * }
   */
  function init(config) {
    if (typeof window.checkAuth === 'function') {
      window.checkAuth();
    }
    document.addEventListener('DOMContentLoaded', function () {
      if (typeof window.renderSidebar === 'function') {
        window.renderSidebar(config.domainSlug || 'dashboard');
      }
      // Wire "Manage Connectors" button if present
      var mcBtn = document.getElementById('btnManageConnectors');
      if (mcBtn && config.catalogCategory) {
        mcBtn.href = 'tool-catalog.html?category=' + encodeURIComponent(config.catalogCategory);
      }
      // Wire "Run Scan" button if present (best-effort: triggers run-now per connector)
      var scanBtn = document.getElementById('btnRunScan');
      if (scanBtn) {
        scanBtn.addEventListener('click', function () {
          handleRunScan(config.connectors || []);
        });
      }
      loadDomainData(config);
    });
  }

  async function handleRunScan(connectors) {
    var apiFetch = window.URIP && window.URIP.apiFetch;
    var notify = (window.URIP && window.URIP.showNotification) || function () {};
    if (!apiFetch || connectors.length === 0) {
      notify('Run Scan', 'No connectors configured for this domain.', 'info');
      return;
    }
    notify('Run Scan', 'Triggering ' + connectors.length + ' connector(s)…', 'info');
    var results = await Promise.all(connectors.map(function (c) {
      return apiFetch('/connectors/' + encodeURIComponent(c) + '/run-now', {
        method: 'POST', silent: true,
      }).then(function () { return { name: c, ok: true }; })
        .catch(function (e) { return { name: c, ok: false, err: e }; });
    }));
    var ok = results.filter(function (r) { return r.ok; }).length;
    notify('Run Scan',
      ok + '/' + results.length + ' connector run(s) queued.',
      ok > 0 ? 'success' : 'error');
  }

  async function loadDomainData(config) {
    // Connector tiles
    var connGrid = document.getElementById('connectorGrid');
    if (connGrid && config.connectors && config.connectors.length) {
      var loading = el('div', 'empty-state');
      loading.appendChild(faIcon('fa-spinner fa-spin'));
      var t = el('div', 'empty-state-title', 'Loading connectors…');
      loading.appendChild(t);
      connGrid.appendChild(loading);

      try {
        var healthList = await fetchConnectorHealth(config.connectors);
        var metaList = await Promise.all(config.connectors.map(fetchConnectorMeta));
        connGrid.textContent = '';
        var anyConfigured = false;
        config.connectors.forEach(function (name, idx) {
          var meta = metaList[idx];
          var hr = healthList[idx];
          var info = {
            name: name,
            display_name: meta ? meta.display_name : null,
            configured: hr && hr.configured,
            health: hr && hr.health ? (hr.health.status || hr.health.health) : null,
            lastPoll: hr && hr.health ? hr.health.last_poll_at : null,
            errorCount24h: hr && hr.health ? hr.health.error_count_24h : 0,
          };
          if (info.configured) anyConfigured = true;
          connGrid.appendChild(renderConnectorTile(info));
        });

        // KPI: connector count
        var kpiConn = document.getElementById('kpiConnectorsConfigured');
        if (kpiConn) {
          var configuredCount = healthList.filter(function (h) { return h.configured; }).length;
          kpiConn.textContent = configuredCount + ' / ' + config.connectors.length;
        }
        if (!anyConfigured) {
          var empty = el('div', 'card');
          empty.style.gridColumn = '1 / -1';
          empty.style.padding = '1.5rem';
          empty.style.textAlign = 'center';
          empty.style.color = 'var(--gray-500)';
          var emptyTitle = el('div');
          emptyTitle.style.fontWeight = '600';
          emptyTitle.style.color = 'var(--gray-700)';
          emptyTitle.style.marginBottom = '0.25rem';
          emptyTitle.textContent = 'No connectors configured for this domain yet';
          empty.appendChild(emptyTitle);
          var emptyText = el('div');
          emptyText.style.fontSize = '13px';
          emptyText.textContent = 'Connect a tool to populate this dashboard with real findings.';
          empty.appendChild(emptyText);
          // Don't show twice (tiles still render with "Connect" CTA above)
        }
      } catch (e) {
        console.error('connector load failed', e);
        connGrid.textContent = '';
        var err = el('div', 'alert alert-danger');
        err.textContent = 'Could not load connector status: ' + (e.message || e);
        connGrid.appendChild(err);
      }
    }

    // Top risks
    var risksBody = document.getElementById('topRisksBody');
    var riskBanner = document.getElementById('riskFallbackBanner');
    if (risksBody) {
      try {
        var result = await fetchRisksForDomain(
          config.domainField || config.domainSlug,
          config.sources || [],
          { limit: 7 }
        );
        risksBody.textContent = '';
        if (riskBanner) {
          riskBanner.style.display = result.fellBackToSource ? '' : 'none';
        }
        if (!result.items || result.items.length === 0) {
          var tr = document.createElement('tr');
          var td = el('td');
          td.colSpan = 5;
          td.style.padding = '2rem';
          td.style.textAlign = 'center';
          td.style.color = 'var(--gray-500)';
          td.textContent = 'No risks in this domain. Configure a connector and run a scan to populate.';
          tr.appendChild(td);
          risksBody.appendChild(tr);
        } else {
          result.items.forEach(function (r) { risksBody.appendChild(renderRiskRow(r)); });
        }

        // KPIs from totals
        var kpiTotal = document.getElementById('kpiTotalRisks');
        var kpiCritical = document.getElementById('kpiCriticalCount');
        var kpiMean = document.getElementById('kpiMeanScore');
        if (kpiTotal || kpiCritical || kpiMean) {
          // Re-fetch with bigger page just to compute KPIs honestly (capped at 100)
          var apiFetch = window.URIP && window.URIP.apiFetch;
          if (apiFetch) {
            try {
              var allRisks = [];
              if (config.sources && config.sources.length) {
                var allCalls = config.sources.map(function (s) {
                  return apiFetch('/risks?source=' + encodeURIComponent(s) + '&per_page=100', { silent: true })
                    .catch(function () { return { items: [] }; });
                });
                var allResp = await Promise.all(allCalls);
                allResp.forEach(function (r) { if (r && r.items) allRisks = allRisks.concat(r.items); });
              } else if (config.domainField) {
                var dr = await apiFetch('/risks?domain=' + encodeURIComponent(config.domainField) + '&per_page=100', { silent: true });
                if (dr && dr.items) allRisks = dr.items;
              }
              if (kpiTotal) kpiTotal.textContent = String(allRisks.length);
              if (kpiCritical) kpiCritical.textContent = String(allRisks.filter(function (x) {
                return (x.severity || '').toLowerCase() === 'critical';
              }).length);
              if (kpiMean) {
                if (allRisks.length === 0) {
                  kpiMean.textContent = '—';
                } else {
                  var sum = 0, n = 0;
                  allRisks.forEach(function (x) {
                    var v = (x.composite_score != null) ? x.composite_score : x.cvss_score;
                    if (typeof v === 'number') { sum += v; n++; }
                  });
                  kpiMean.textContent = n ? (sum / n).toFixed(1) : '—';
                }
              }
            } catch (e) {
              if (kpiTotal) kpiTotal.textContent = '—';
              if (kpiCritical) kpiCritical.textContent = '—';
              if (kpiMean) kpiMean.textContent = '—';
            }
          }
        }
      } catch (e) {
        console.error('risks load failed', e);
        risksBody.textContent = '';
        var trE = document.createElement('tr');
        var tdE = el('td');
        tdE.colSpan = 5;
        tdE.style.padding = '1.5rem';
        tdE.style.textAlign = 'center';
        tdE.style.color = 'var(--red-critical, #E74C3C)';
        tdE.textContent = 'Failed to load risks: ' + (e.message || e);
        trE.appendChild(tdE);
        risksBody.appendChild(trE);
      }
    }

    // Page-specific widgets
    if (typeof config.onSpecialWidgets === 'function') {
      try {
        await config.onSpecialWidgets({
          fetchRisksForSources: fetchRisksForSources,
          fetchConnectorMeta: fetchConnectorMeta,
        });
      } catch (e) {
        console.error('special widgets failed', e);
      }
    }
  }

  // Public API
  window.DomainPage = {
    init: init,
    fetchRisksForSources: fetchRisksForSources,
    fetchRisksForDomain: fetchRisksForDomain,
    fetchConnectorHealth: fetchConnectorHealth,
    fetchConnectorMeta: fetchConnectorMeta,
    renderConnectorTile: renderConnectorTile,
    renderRiskRow: renderRiskRow,
    renderEmpty: renderEmpty,
    formatRelative: formatRelative,
    el: el,
    faIcon: faIcon,
  };
})();
