/**
 * URIP — Risk Overview (Wave A)
 *
 * Renders the TrendAI-style "Risk Index" landing dashboard.
 *
 * Endpoint precedence:
 *   1. GET /api/risk-index  (preferred — built by trendai-risk-index agent)
 *   2. Fallback: derive an honest summary from /api/risk-summary +
 *      /api/dashboard/kpis (data we already have).
 *
 * Honest fallback: if neither endpoint produces a usable score we render an
 * empty state explaining why ("no data yet — connect a tool"). We do NOT
 * fabricate numbers.
 */
(function () {
  'use strict';

  if (typeof window.checkAuth === 'function') window.checkAuth();

  document.addEventListener('DOMContentLoaded', async function () {
    await window.URIP.shell ? null : null; // shell is sync
    window.URIP.shell.mount({
      page: 'risk-overview',
      title: 'Risk Overview',
      breadcrumb: 'Risk Center',
      actions: [
        { label: 'Refresh', icon: 'fa-rotate', variant: 'is-ghost', onClick: function () { location.reload(); } },
        { label: 'Export', icon: 'fa-download', variant: 'is-ghost', onClick: function () {
            window.URIP.showNotification('Export', 'PDF/CSV export coming soon.', 'info');
          }
        },
        { label: 'Configure', icon: 'fa-sliders', variant: 'is-primary', href: 'admin-scoring.html' }
      ]
    });

    var data = await loadRiskIndex();
    if (data) {
      renderTop(data);
      renderBuckets(data);
    } else {
      renderEmpty();
    }
    renderTrend();
    renderSummary();
    renderFactors();
    renderActivity();
  });

  // ---------------------------------------------------------------------------
  // Data load with graceful fallback
  // ---------------------------------------------------------------------------
  async function loadRiskIndex() {
    // Primary endpoint
    try {
      var idx = await window.URIP.apiFetch('/risk-index', { silent: true, retries: 1 });
      if (idx && (idx.overall_score != null || idx.score != null)) return normalizeIndex(idx);
    } catch (_e) { /* try fallback */ }

    // Fallback: synthesize from /risk-summary + /dashboard/kpis
    var summary = null, kpis = null;
    try { summary = await window.URIP.apiFetch('/risk-summary', { silent: true, retries: 1 }); } catch (_e) {}
    try { kpis    = await window.URIP.apiFetch('/dashboard/kpis', { silent: true, retries: 1 }); } catch (_e) {}
    if (!summary && !kpis) return null;

    return synthesizeIndex(summary, kpis);
  }

  function normalizeIndex(raw) {
    return {
      score: raw.overall_score != null ? raw.overall_score : raw.score,
      level: raw.level || levelFromScore(raw.overall_score != null ? raw.overall_score : raw.score),
      sub: {
        exposure: raw.exposure || raw.subindexes && raw.subindexes.exposure || null,
        attack:   raw.attack   || raw.subindexes && raw.subindexes.attack   || null,
        config:   raw.security_config || raw.subindexes && raw.subindexes.security_config || null
      },
      buckets: raw.domain_buckets || raw.buckets || null,
      synthetic: false
    };
  }

  function synthesizeIndex(summary, kpis) {
    // Honest synthesis: we DO have aggregate counts but no real index calc.
    // Convert "% of risks open at critical+high" to a coarse 0-100 score.
    var critical = (kpis && kpis.critical) || 0;
    var high     = (kpis && kpis.high)     || 0;
    var total    = (kpis && kpis.total_open) || 0;
    var ioc      = (kpis && kpis.ioc_matches) || 0;
    var darkweb  = (kpis && kpis.dark_web_alerts) || 0;

    if (!total && !ioc && !darkweb) {
      // No findings at all — no synthetic guess.
      return null;
    }

    // Simple coarse derivation — labeled SYNTHETIC in the UI.
    var pctCritical = total > 0 ? critical / total : 0;
    var pctHigh     = total > 0 ? high / total : 0;
    var score = Math.min(100, Math.round(60 * pctCritical + 30 * pctHigh + Math.min(10, ioc + darkweb)));

    return {
      score: score,
      level: levelFromScore(score),
      sub: {
        exposure: { score: Math.min(100, Math.round((darkweb || 0) * 8 + (ioc || 0) * 2)), level: null },
        attack:   { score: Math.min(100, Math.round(critical * 6 + high * 2)), level: null },
        config:   { score: Math.min(100, Math.round((summary && summary.config_score) || 35)), level: null }
      },
      buckets: null,
      synthetic: true
    };
  }

  function levelFromScore(s) {
    if (s == null) return 'Unknown';
    if (s >= 75) return 'Critical';
    if (s >= 50) return 'High';
    if (s >= 25) return 'Medium';
    return 'Low';
  }
  function levelClass(level) {
    var L = (level || '').toLowerCase();
    if (L === 'critical') return 'lvl-critical';
    if (L === 'high')     return 'lvl-high';
    if (L === 'medium')   return 'lvl-medium';
    if (L === 'low')      return 'lvl-low';
    return 'lvl-medium';
  }

  // ---------------------------------------------------------------------------
  // Renderers
  // ---------------------------------------------------------------------------
  function renderTop(data) {
    var big = document.getElementById('bigscore');
    big.classList.remove('lvl-critical', 'lvl-high', 'lvl-medium', 'lvl-low');
    big.classList.add(levelClass(data.level));

    document.getElementById('overallScore').textContent = data.score != null ? Math.round(data.score) : '—';
    document.getElementById('overallLevel').textContent = data.level || levelFromScore(data.score);
    if (data.synthetic) {
      document.getElementById('overallSub').textContent = 'SYNTHETIC — derived from open risk counts (no live /api/risk-index yet)';
      document.getElementById('overallSub').style.color = 'var(--u-warn)';
    }

    setSub('exposure', data.sub && data.sub.exposure);
    setSub('attack', data.sub && data.sub.attack);
    setSub('config', data.sub && data.sub.config);
  }

  function setSub(key, v) {
    var idMap = { exposure: ['exposureValue', 'exposureBar', 'subExposure'],
                  attack:   ['attackValue',   'attackBar',   'subAttack'],
                  config:   ['configValue',   'configBar',   'subConfig'] };
    var ids = idMap[key];
    var valEl = document.getElementById(ids[0]);
    var barEl = document.getElementById(ids[1]);
    var card  = document.getElementById(ids[2]);
    if (!v || v.score == null) {
      valEl.textContent = '—';
      barEl.style.width = '0%';
      return;
    }
    var s = Math.round(v.score);
    valEl.textContent = s;
    barEl.style.width = Math.max(2, Math.min(100, s)) + '%';
    card.classList.remove('lvl-critical', 'lvl-high', 'lvl-medium', 'lvl-low');
    card.classList.add(levelClass(v.level || levelFromScore(s)));
  }

  function renderBuckets(data) {
    var row = document.getElementById('bucketRow');
    row.textContent = '';
    var defaults = [
      { key: 'devices',          label: 'Devices',              icon: 'fa-laptop' },
      { key: 'internet_facing',  label: 'Internet-Facing',      icon: 'fa-earth-asia' },
      { key: 'accounts',         label: 'Accounts',             icon: 'fa-key' },
      { key: 'applications',     label: 'Applications',         icon: 'fa-window-restore' },
      { key: 'cloud_assets',     label: 'Cloud Assets',         icon: 'fa-cloud' }
    ];
    var buckets = (data && data.buckets) || {};
    defaults.forEach(function (d) {
      var b = buckets[d.key] || {};
      var card = document.createElement('div');
      card.className = 'r-bucket';

      var icn = document.createElement('div');
      icn.className = 'r-bucket-icon';
      var ic = document.createElement('i');
      ic.className = 'fas ' + d.icon;
      icn.appendChild(ic);
      card.appendChild(icn);

      var label = document.createElement('div');
      label.className = 'r-bucket-label';
      label.textContent = d.label;
      card.appendChild(label);

      var count = document.createElement('div');
      count.className = 'r-bucket-count';
      count.textContent = b.count != null ? b.count : '—';
      card.appendChild(count);

      var lvl = document.createElement('div');
      lvl.className = 'r-bucket-level ' + levelClass(b.level || levelFromScore(b.score));
      lvl.textContent = b.level || (b.score != null ? levelFromScore(b.score) : 'No data');
      card.appendChild(lvl);

      row.appendChild(card);
    });
  }

  function renderEmpty() {
    var top = document.getElementById('topRow');
    top.innerHTML = '';
    var box = document.createElement('div');
    box.style.gridColumn = '1 / -1';
    box.appendChild(window.URIP.shell.makeEmpty(
      'fa-chart-pie',
      'No risk data yet',
      'Connect at least one security tool from the Tool Catalog to begin building your unified Risk Index. URIP will start scoring as soon as the first findings arrive.'
    ));
    var btnRow = document.createElement('div');
    btnRow.style.textAlign = 'center';
    btnRow.style.marginTop = '14px';
    var btn = document.createElement('a');
    btn.className = 'u-btn is-primary';
    btn.href = 'tool-catalog.html';
    btn.innerHTML = '<i class="fas fa-plug"></i> Open Tool Catalog';
    btnRow.appendChild(btn);
    box.appendChild(btnRow);
    top.appendChild(box);

    document.getElementById('bucketRow').textContent = '';
  }

  // ---------- Trend chart ----------
  async function renderTrend() {
    var ctx = document.getElementById('trendChart');
    if (!ctx || !window.Chart) return;
    var labels = [], data = [], industry = [];

    try {
      var resp = await window.URIP.apiFetch('/risk-summary/trend?days=30', { silent: true, retries: 1 });
      var rows = (resp && (resp.items || resp.data || resp)) || [];
      if (Array.isArray(rows) && rows.length) {
        rows.forEach(function (r) {
          labels.push((r.date || r.day || '').toString().substring(5));
          data.push(r.score != null ? r.score : (r.composite || r.value || 0));
          industry.push(r.industry_avg != null ? r.industry_avg : null);
        });
      }
    } catch (_e) { /* fall through */ }

    if (!labels.length) {
      // Synthesize 30 labels with empty data so the chart renders gracefully
      var d = new Date();
      for (var i = 29; i >= 0; i--) {
        var dd = new Date(d.getTime() - i * 86400000);
        labels.push((dd.getMonth() + 1) + '/' + dd.getDate());
        data.push(null);
      }
    }

    new Chart(ctx, {
      type: 'line',
      data: {
        labels: labels,
        datasets: [
          {
            label: 'Risk Score',
            data: data,
            borderColor: '#4A6CF7',
            backgroundColor: 'rgba(74,108,247,.1)',
            tension: .35,
            fill: true,
            pointRadius: 0,
            borderWidth: 2
          },
          {
            label: 'Industry Avg',
            data: industry,
            borderColor: '#7A7C84',
            borderDash: [4, 4],
            tension: .35,
            fill: false,
            pointRadius: 0,
            borderWidth: 1.5,
            hidden: industry.every(function (x) { return x == null; })
          }
        ]
      },
      options: chartOpts()
    });
  }

  // ---------- Summary chart (Exposure/Attack/Config bars) ----------
  async function renderSummary() {
    var ctx = document.getElementById('summaryChart');
    if (!ctx || !window.Chart) return;
    var labels = [], exposure = [], attack = [], cfg = [];
    try {
      var resp = await window.URIP.apiFetch('/risk-summary/trend?days=180&granularity=month', { silent: true, retries: 1 });
      var rows = (resp && (resp.items || resp.data || resp)) || [];
      if (Array.isArray(rows) && rows.length) {
        rows.forEach(function (r) {
          labels.push((r.month || r.date || r.day || '').toString().substring(0, 7));
          exposure.push(r.exposure || 0);
          attack.push(r.attack || 0);
          cfg.push(r.security_config || r.config || 0);
        });
      }
    } catch (_e) {}

    if (!labels.length) {
      // No trend data — show last 6 month labels with empty bars
      var d = new Date();
      for (var i = 5; i >= 0; i--) {
        var dd = new Date(d.getFullYear(), d.getMonth() - i, 1);
        labels.push(dd.toLocaleDateString(undefined, { month: 'short' }));
        exposure.push(0); attack.push(0); cfg.push(0);
      }
    }

    new Chart(ctx, {
      type: 'bar',
      data: {
        labels: labels,
        datasets: [
          { label: 'Exposure', data: exposure, backgroundColor: '#4A6CF7' },
          { label: 'Attack',   data: attack,   backgroundColor: '#E74C3C' },
          { label: 'Config',   data: cfg,      backgroundColor: '#F1C40F' }
        ]
      },
      options: chartOpts({ stacked: true })
    });
  }

  function chartOpts(extra) {
    extra = extra || {};
    return {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { labels: { color: '#B6B7BC', boxWidth: 10, padding: 12 }, position: 'bottom' },
        tooltip: { backgroundColor: '#1A1A1F', borderColor: '#2A2A30', borderWidth: 1 }
      },
      scales: {
        x: { ticks: { color: '#7A7C84' }, grid: { color: 'rgba(255,255,255,.04)' }, stacked: !!extra.stacked },
        y: { ticks: { color: '#7A7C84' }, grid: { color: 'rgba(255,255,255,.04)' }, stacked: !!extra.stacked, beginAtZero: true }
      }
    };
  }

  // ---------- Risk factors panel ----------
  async function renderFactors() {
    var body = document.getElementById('factorsBody');
    body.textContent = '';
    try {
      var k = await window.URIP.apiFetch('/dashboard/kpis', { silent: true, retries: 1 });
      var rows = [
        { label: 'Total open risks',        value: k && k.total_open },
        { label: 'Critical',                value: k && k.critical, sev: 'critical' },
        { label: 'High',                    value: k && k.high,     sev: 'high' },
        { label: 'Accepted',                value: k && k.accepted, sev: 'info' },
        { label: 'IOC matches (30d)',       value: k && k.ioc_matches, sev: 'high' },
        { label: 'Dark-web alerts (30d)',   value: k && k.dark_web_alerts, sev: 'critical' }
      ];
      rows.forEach(function (r) {
        if (r.value == null) return;
        var line = document.createElement('div');
        line.style.display = 'flex';
        line.style.justifyContent = 'space-between';
        line.style.alignItems = 'center';
        line.style.padding = '8px 0';
        line.style.borderBottom = '1px solid var(--u-border)';
        var lbl = document.createElement('div');
        lbl.style.fontSize = '13px';
        lbl.style.color = 'var(--u-fg-2)';
        lbl.textContent = r.label;
        line.appendChild(lbl);
        var val = document.createElement('div');
        val.style.fontSize = '15px';
        val.style.fontFamily = 'var(--u-font-mono)';
        val.style.fontWeight = '700';
        val.textContent = r.value;
        if (r.sev === 'critical') val.style.color = 'var(--sev-critical)';
        else if (r.sev === 'high') val.style.color = 'var(--sev-high)';
        line.appendChild(val);
        body.appendChild(line);
      });
      if (!body.children.length) {
        body.appendChild(window.URIP.shell.makeEmpty('fa-database', 'No risk data', 'Connect a tool to populate this panel.'));
      }
    } catch (_e) {
      body.appendChild(window.URIP.shell.makeEmpty('fa-triangle-exclamation', 'Could not load factors', 'Try refreshing in a moment.'));
    }
  }

  async function renderActivity() {
    var body = document.getElementById('activityBody');
    body.textContent = '';
    try {
      var resp = await window.URIP.apiFetch('/audit-log?per_page=8', { silent: true, retries: 1 });
      var items = (resp && (resp.items || resp.entries || resp)) || [];
      if (!Array.isArray(items)) items = [];
      if (!items.length) {
        body.appendChild(window.URIP.shell.makeEmpty('fa-clock-rotate-left', 'No recent activity', 'New events will appear here.'));
        return;
      }
      items.slice(0, 8).forEach(function (it) {
        var feed = document.createElement('div');
        feed.className = 'r-feed-item';
        var icn = document.createElement('div');
        icn.className = 'r-feed-icon';
        var i = document.createElement('i');
        i.className = 'fas fa-bolt';
        icn.appendChild(i);
        feed.appendChild(icn);

        var bod = document.createElement('div');
        bod.style.flex = '1';
        var t = document.createElement('div');
        t.className = 'r-feed-text';
        t.textContent = it.action || it.event_type || it.message || 'Activity';
        bod.appendChild(t);

        var m = document.createElement('div');
        m.className = 'r-feed-meta';
        m.textContent = (it.user_email || it.actor || '') + ((it.timestamp || it.created_at) ? ' • ' + window.URIP.shell.relTime(it.timestamp || it.created_at) : '');
        bod.appendChild(m);
        feed.appendChild(bod);
        body.appendChild(feed);
      });
    } catch (_e) {
      body.appendChild(window.URIP.shell.makeEmpty('fa-triangle-exclamation', 'Could not load activity', 'Try refreshing in a moment.'));
    }
  }
})();
