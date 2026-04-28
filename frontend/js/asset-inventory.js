/**
 * URIP Asset Inventory page controller.
 *
 * Reads from the first-class Asset REST API (built by the backend-asset-model
 * worker — see backend/routers/assets.py):
 *   GET /api/assets                — paginated, filtered, tenant-scoped list
 *   GET /api/assets/categories     — per-category counts
 *
 * Field map from /api/assets items:
 *   id, hostname, internal_ip, mac_address, device_type, device_category,
 *   os_name, os_version, owner_team, asset_tier, asset_risk_score,
 *   lifecycle_state, source_connectors, custom_tags, category, last_seen
 *
 * Derived/UI-only:
 *   starred — local-storage flag toggled by the UI star button (per browser).
 *
 * The "Open Risks" count column comes from /api/assets/{id}/risks and is
 * filled in lazily after the table renders so the initial paint is instant.
 */
(function () {
  'use strict';

  if (typeof checkAuth === 'function') checkAuth();

  var STARRED_KEY = 'urip_starred_assets';

  // Map API category strings → filter dropdown values used in the HTML.
  // Keep in sync with backend/models/asset.py::ASSET_CATEGORIES.
  var CATEGORY_FILTER_MAP = {
    'Devices': 'device',
    'Internet-Facing Assets': 'internet-facing',
    'Accounts': 'account',
    'Applications': 'application',
    'Cloud Assets': 'cloud',
    'API Collections': 'api',
  };

  function getStarred() {
    try { return new Set(JSON.parse(localStorage.getItem(STARRED_KEY) || '[]')); }
    catch (e) { return new Set(); }
  }
  function setStarred(set) {
    localStorage.setItem(STARRED_KEY, JSON.stringify(Array.from(set)));
  }

  function severityLabel(score) {
    var s = parseFloat(score) || 0;
    if (s >= 9) return 'critical';
    if (s >= 7) return 'high';
    if (s >= 4) return 'medium';
    if (s > 0) return 'low';
    return 'none';
  }

  function displayName(asset) {
    return asset.hostname || asset.internal_ip || asset.id || '(unknown asset)';
  }

  function osText(asset) {
    if (asset.os_name && asset.os_version) return asset.os_name + ' ' + asset.os_version;
    if (asset.os_name) return asset.os_name;
    if (asset.device_type) return asset.device_type;
    return '—';
  }

  // State
  var allAssets = [];
  var filters = { search: '', category: '', starred: '' };

  document.addEventListener('DOMContentLoaded', function () {
    if (typeof renderSidebar === 'function') renderSidebar('asset-inventory');
    var apiFetch = window.URIP && window.URIP.apiFetch;
    if (!apiFetch) return;

    loadAssets(apiFetch);

    document.getElementById('filterSearch').addEventListener('input', function (e) {
      filters.search = (e.target.value || '').toLowerCase(); renderTable();
    });
    document.getElementById('filterCategory').addEventListener('change', function (e) {
      filters.category = e.target.value; renderTable();
    });
    document.getElementById('filterStarred').addEventListener('change', function (e) {
      filters.starred = e.target.value; renderTable();
    });
    document.getElementById('filterReset').addEventListener('click', function () {
      filters = { search: '', category: '', starred: '' };
      document.getElementById('filterSearch').value = '';
      document.getElementById('filterCategory').value = '';
      document.getElementById('filterStarred').value = '';
      renderTable();
    });
    document.getElementById('btnExportAssets').addEventListener('click', exportCsv);
  });

  async function loadAssets(apiFetch) {
    try {
      // The Asset API caps `limit` at 200 — pull a wide first page.
      var resp = await apiFetch('/assets?limit=200&page=1', { silent: true });
      var items = (resp && resp.items) || [];
      allAssets = items.map(function (a) {
        return {
          id: a.id,
          asset: displayName(a),
          hostname: a.hostname || '',
          internal_ip: a.internal_ip || '',
          mac_address: a.mac_address || '',
          os: osText(a),
          device_type: a.device_type || '',
          device_category: a.device_category || '',
          owner: a.owner_team || '',
          score: a.asset_risk_score != null ? Number(a.asset_risk_score) : 0,
          lifecycle_state: a.lifecycle_state || '',
          source_connectors: a.source_connectors || [],
          custom_tags: a.custom_tags || {},
          category: a.category || 'Devices',
          last_seen: a.last_seen,
          asset_tier: a.asset_tier || '',
          // Filled in lazily by the per-asset risks endpoint.
          openRisks: null,
        };
      });

      document.getElementById('kpiAssetCount').textContent = String(allAssets.length);
      document.getElementById('kpiHighRiskAssets').textContent =
        String(allAssets.filter(function (a) { return a.score >= 7; }).length);
      document.getElementById('kpiStarred').textContent = String(getStarred().size);
      var withOwner = allAssets.filter(function (a) { return a.owner; }).length;
      document.getElementById('kpiOwnerCoverage').textContent = allAssets.length
        ? Math.round(100 * withOwner / allAssets.length) + '%'
        : '—';
      renderTable();

      // Lazy-fill open-risks per asset (cap at 25 to avoid hammering the API).
      var rows = allAssets.slice(0, 25);
      rows.forEach(function (a) {
        apiFetch('/assets/' + encodeURIComponent(a.id) + '/risks?status=open&limit=1', { silent: true })
          .then(function (r) {
            a.openRisks = (r && typeof r.total === 'number') ? r.total : (r && r.items ? r.items.length : 0);
            updateRiskCountCell(a);
          })
          .catch(function () {
            a.openRisks = 0;
            updateRiskCountCell(a);
          });
      });
    } catch (e) {
      console.error('asset load failed', e);
      var body = document.getElementById('assetTableBody');
      body.textContent = '';
      var tr = document.createElement('tr');
      var td = document.createElement('td');
      td.colSpan = 9;
      td.style.padding = '1.5rem';
      td.style.textAlign = 'center';
      td.style.color = 'var(--red-critical, #E74C3C)';
      td.textContent = 'Failed to load assets: ' + (e.message || e);
      tr.appendChild(td);
      body.appendChild(tr);
    }
  }

  function updateRiskCountCell(asset) {
    var cell = document.querySelector('[data-asset-risks="' + asset.id + '"]');
    if (cell) cell.textContent = asset.openRisks != null ? String(asset.openRisks) : '—';
  }

  function renderTable() {
    var body = document.getElementById('assetTableBody');
    var emptyEl = document.getElementById('assetEmptyState');
    body.textContent = '';
    var starred = getStarred();
    var filtered = allAssets.filter(function (a) {
      if (filters.search) {
        var hay = (a.asset + ' ' + (a.owner || '') + ' ' +
                   (a.internal_ip || '') + ' ' +
                   (a.source_connectors || []).join(' ')).toLowerCase();
        if (hay.indexOf(filters.search) === -1) return false;
      }
      if (filters.category) {
        var mapped = CATEGORY_FILTER_MAP[a.category] || 'device';
        if (mapped !== filters.category) return false;
      }
      if (filters.starred === 'starred' && !starred.has(a.id)) return false;
      return true;
    });
    if (!filtered.length) {
      emptyEl.style.display = '';
      body.parentElement.style.display = 'none';
      return;
    }
    emptyEl.style.display = 'none';
    body.parentElement.style.display = '';
    filtered.forEach(function (a) {
      var tr = document.createElement('tr');
      tr.style.cursor = 'pointer';

      // Star col
      var tdStar = document.createElement('td');
      var starBtn = document.createElement('button');
      starBtn.className = 'star-btn' + (starred.has(a.id) ? ' starred' : '');
      starBtn.innerHTML = '<i class="fa-' + (starred.has(a.id) ? 'solid' : 'regular') + ' fa-star"></i>';
      starBtn.title = starred.has(a.id) ? 'Unflag' : 'Flag as critical';
      starBtn.addEventListener('click', function (e) {
        e.stopPropagation();
        var s = getStarred();
        if (s.has(a.id)) s.delete(a.id); else s.add(a.id);
        setStarred(s);
        document.getElementById('kpiStarred').textContent = String(s.size);
        renderTable();
      });
      tdStar.appendChild(starBtn);
      tr.appendChild(tdStar);

      // Asset
      var tdA = document.createElement('td');
      var aLink = document.createElement('a');
      aLink.href = 'asset-detail.html?id=' + encodeURIComponent(a.id);
      aLink.style.fontWeight = '500';
      aLink.style.color = 'var(--gray-900)';
      aLink.textContent = a.asset;
      tdA.appendChild(aLink);
      tr.appendChild(tdA);

      // Category
      var tdC = document.createElement('td');
      tdC.style.fontSize = '13px';
      tdC.style.color = 'var(--gray-600)';
      tdC.textContent = a.category;
      tr.appendChild(tdC);

      // OS / Type
      var tdOs = document.createElement('td');
      tdOs.style.fontSize = '13px';
      tdOs.style.color = 'var(--gray-600)';
      tdOs.textContent = a.os;
      tr.appendChild(tdOs);

      // Last seen
      var tdL = document.createElement('td');
      tdL.style.fontSize = '13px';
      tdL.style.color = 'var(--gray-500)';
      tdL.textContent = a.last_seen
        ? (typeof DomainPage !== 'undefined' && DomainPage.formatRelative
            ? DomainPage.formatRelative(a.last_seen)
            : new Date(a.last_seen).toLocaleString())
        : '—';
      tr.appendChild(tdL);

      // Risk score pill
      var tdScore = document.createElement('td');
      var pill = document.createElement('span');
      pill.className = 'risk-pill ' + severityLabel(a.score);
      pill.textContent = a.score ? a.score.toFixed(1) : '0';
      tdScore.appendChild(pill);
      tr.appendChild(tdScore);

      // Open risks count (lazy-loaded)
      var tdN = document.createElement('td');
      tdN.style.fontWeight = '600';
      tdN.setAttribute('data-asset-risks', a.id);
      tdN.textContent = a.openRisks != null ? String(a.openRisks) : '…';
      tr.appendChild(tdN);

      // Owner
      var tdO = document.createElement('td');
      tdO.style.fontSize = '13px';
      tdO.textContent = a.owner || '—';
      if (!a.owner) tdO.style.color = 'var(--gray-400)';
      tr.appendChild(tdO);

      // Tags — render custom_tags entries as chips
      var tdT = document.createElement('td');
      var tagKeys = Object.keys(a.custom_tags || {}).slice(0, 3);
      if (tagKeys.length) {
        tagKeys.forEach(function (k) {
          var chip = document.createElement('span');
          chip.className = 'tag-chip';
          chip.textContent = a.custom_tags[k] != null
            ? (k + ':' + a.custom_tags[k])
            : k;
          tdT.appendChild(chip);
        });
      } else {
        tdT.textContent = '—';
        tdT.style.color = 'var(--gray-400)';
      }
      tr.appendChild(tdT);

      tr.addEventListener('click', function () {
        window.location.href = 'asset-detail.html?id=' + encodeURIComponent(a.id);
      });
      body.appendChild(tr);
    });
  }

  function exportCsv() {
    var header = [
      'Asset', 'Category', 'Internal IP', 'OS', 'Owner Team',
      'Asset Tier', 'Risk Score', 'Lifecycle', 'Last Seen',
    ];
    var rows = [header.join(',')];
    allAssets.forEach(function (a) {
      var line = [
        '"' + (a.asset || '').replace(/"/g, '""') + '"',
        a.category,
        a.internal_ip,
        '"' + (a.os || '').replace(/"/g, '""') + '"',
        '"' + (a.owner || '').replace(/"/g, '""') + '"',
        a.asset_tier,
        a.score ? a.score.toFixed(1) : '',
        a.lifecycle_state,
        a.last_seen || '',
      ].join(',');
      rows.push(line);
    });
    var blob = new Blob([rows.join('\n')], { type: 'text/csv' });
    var url = URL.createObjectURL(blob);
    var a = document.createElement('a');
    a.href = url; a.download = 'asset-inventory.csv';
    document.body.appendChild(a); a.click(); document.body.removeChild(a);
    setTimeout(function () { URL.revokeObjectURL(url); }, 1000);
  }
})();
