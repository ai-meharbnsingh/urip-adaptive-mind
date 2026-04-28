/**
 * URIP Asset Detail page controller.
 *
 * Reads from the first-class Asset REST API (built by the backend-asset-model
 * worker — see backend/routers/assets.py):
 *   GET /api/assets/{id}                — asset metadata + open-risks bundle
 *   GET /api/assets/{id}/risks          — paginated open-risk list
 *   GET /api/assets/{id}/timeline       — chronological timeline events
 *
 * The page accepts ?id=<uuid>. We also accept the legacy ?asset=<hostname>
 * param for backwards-compatibility with old links (we resolve it by listing
 * /api/assets and matching hostname/internal_ip).
 *
 * Star/critical flag is local-storage only (per browser, per id).
 */
(function () {
  'use strict';

  if (typeof checkAuth === 'function') checkAuth();

  var STARRED_KEY = 'urip_starred_assets';

  function getStarred() {
    try { return new Set(JSON.parse(localStorage.getItem(STARRED_KEY) || '[]')); }
    catch (e) { return new Set(); }
  }
  function setStarred(set) {
    localStorage.setItem(STARRED_KEY, JSON.stringify(Array.from(set)));
  }

  function getQueryParam(name) {
    var u = new URL(window.location.href);
    return u.searchParams.get(name);
  }

  function fmtDate(d) {
    if (!d) return '—';
    try {
      if (typeof DomainPage !== 'undefined' && DomainPage.formatRelative) {
        return DomainPage.formatRelative(d);
      }
      return new Date(d).toLocaleString();
    } catch (e) { return d; }
  }

  document.addEventListener('DOMContentLoaded', async function () {
    if (typeof renderSidebar === 'function') renderSidebar('asset-inventory');

    var apiFetch = window.URIP && window.URIP.apiFetch;
    if (!apiFetch) return;

    var assetId = getQueryParam('id');
    var legacyAsset = getQueryParam('asset');

    // Legacy link support: ?asset=<hostname/ip> → resolve to id via /api/assets
    if (!assetId && legacyAsset) {
      try {
        var listResp = await apiFetch(
          '/assets?search=' + encodeURIComponent(legacyAsset) + '&limit=5',
          { silent: true },
        );
        var match = ((listResp && listResp.items) || []).find(function (a) {
          return (a.hostname && a.hostname.toLowerCase() === legacyAsset.toLowerCase()) ||
                 (a.internal_ip === legacyAsset);
        });
        if (match) {
          assetId = match.id;
          // Update URL silently so subsequent reloads use the canonical id.
          var url = new URL(window.location.href);
          url.searchParams.set('id', assetId);
          url.searchParams.delete('asset');
          window.history.replaceState({}, document.title, url.toString());
        }
      } catch (e) { /* fall through to "no asset" UI */ }
    }

    if (!assetId) {
      document.getElementById('assetTitle').textContent = 'No asset selected';
      document.getElementById('assetSubtitle').textContent =
        'Add ?id=<asset-uuid> to the URL.';
      return;
    }

    // Star button — keyed by asset id
    var starBtn = document.getElementById('btnStar');
    function refreshStar() {
      var s = getStarred();
      if (s.has(assetId)) {
        starBtn.classList.add('btn-primary');
        starBtn.classList.remove('btn-outline');
        starBtn.innerHTML = '<i class="fa-solid fa-star"></i> <span>Critical</span>';
      } else {
        starBtn.classList.remove('btn-primary');
        starBtn.classList.add('btn-outline');
        starBtn.innerHTML = '<i class="fa-regular fa-star"></i> <span>Flag Critical</span>';
      }
    }
    refreshStar();
    starBtn.addEventListener('click', function () {
      var s = getStarred();
      if (s.has(assetId)) s.delete(assetId); else s.add(assetId);
      setStarred(s);
      refreshStar();
    });

    // Tag input — append to custom_tags via PATCH /api/assets/{id}
    // (PATCH requires CISO role — for non-admin users this falls back to a
    // no-op and surfaces a friendly message.)
    var tagInput = document.getElementById('tagInput');
    var ownerInput = document.getElementById('ownerInput');

    var assetRecord = null;
    var openRisks = [];

    // 1) Fetch asset bundle (metadata + open risks bundled for first paint)
    try {
      var bundle = await apiFetch('/assets/' + encodeURIComponent(assetId), { silent: true });
      assetRecord = bundle && bundle.asset;
      openRisks = (bundle && bundle.open_risks) || [];

      if (!assetRecord) {
        document.getElementById('assetTitle').textContent = 'Asset not found';
        document.getElementById('assetSubtitle').textContent = '';
        return;
      }

      var displayName = assetRecord.hostname || assetRecord.internal_ip || assetRecord.id;
      document.getElementById('assetTitle').textContent = displayName;
      document.getElementById('metaAsset').textContent = displayName;
      document.getElementById('metaCategory').textContent = assetRecord.category || '—';
      document.getElementById('metaRiskCount').textContent =
        String(bundle.risk_count != null ? bundle.risk_count : openRisks.length);
      document.getElementById('metaMaxScore').textContent =
        bundle.max_score ? bundle.max_score.toFixed(1) : '—';
      document.getElementById('metaLastSeen').textContent = fmtDate(assetRecord.last_seen);

      // Owner team (PATCHable for admins)
      ownerInput.value = assetRecord.owner_team || '';
      ownerInput.addEventListener('change', async function () {
        try {
          await apiFetch('/assets/' + encodeURIComponent(assetId), {
            method: 'PATCH',
            body: JSON.stringify({ owner_team: ownerInput.value }),
            silent: true,
          });
        } catch (e) {
          // Non-admin → 403; revert the input to the server value
          ownerInput.value = assetRecord.owner_team || '';
        }
      });

      // Render initial tags from server
      renderTagsFromAsset(assetRecord);
      tagInput.addEventListener('keydown', async function (e) {
        if (e.key !== 'Enter' || !tagInput.value.trim()) return;
        var key = tagInput.value.trim();
        var tags = Object.assign({}, assetRecord.custom_tags || {});
        if (tags[key] == null) tags[key] = true;
        try {
          var updated = await apiFetch('/assets/' + encodeURIComponent(assetId), {
            method: 'PATCH',
            body: JSON.stringify({ custom_tags: tags }),
            silent: true,
          });
          assetRecord = updated;
          tagInput.value = '';
          renderTagsFromAsset(assetRecord);
        } catch (err) {
          // Likely 403 from non-admin role
          tagInput.value = '';
        }
      });

      var subtitleSources = (assetRecord.source_connectors || []).join(', ') || 'no connectors';
      document.getElementById('assetSubtitle').textContent =
        (bundle.risk_count != null ? bundle.risk_count : openRisks.length) +
        ' open risk(s) — ' + subtitleSources;
    } catch (e) {
      console.error('asset detail load failed', e);
      document.getElementById('assetSubtitle').textContent =
        'Failed to load asset: ' + (e.message || e);
      return;
    }

    // 2) Render risks-on-asset section from /api/assets/{id}/risks
    try {
      var risksResp = await apiFetch(
        '/assets/' + encodeURIComponent(assetId) + '/risks?status=all&limit=100',
        { silent: true },
      );
      var items = (risksResp && risksResp.items) || [];

      var body = document.getElementById('riskTimelineBody');
      body.textContent = '';

      if (!items.length) {
        var tr = document.createElement('tr');
        var td = document.createElement('td');
        td.colSpan = 7;
        td.style.padding = '2rem';
        td.style.textAlign = 'center';
        td.style.color = '#94A3B8';
        td.textContent = 'No risks recorded yet for this asset.';
        tr.appendChild(td); body.appendChild(tr);
      } else {
        items.sort(function (a, b) {
          return new Date(b.created_at || 0) - new Date(a.created_at || 0);
        });
        items.forEach(function (r) {
          var tr = document.createElement('tr');
          var c = function (txt) {
            var td = document.createElement('td');
            td.textContent = txt != null && txt !== '' ? txt : '—';
            return td;
          };
          tr.appendChild(c(r.risk_id));
          var tdF = document.createElement('td');
          tdF.style.maxWidth = '380px';
          tdF.textContent = r.finding || '(no title)';
          tr.appendChild(tdF);
          tr.appendChild(c(r.source));
          var tdSev = document.createElement('td');
          var sb = document.createElement('span');
          sb.className = 'badge badge-' + (r.severity || 'info').toLowerCase();
          sb.textContent = r.severity || '—';
          tdSev.appendChild(sb); tr.appendChild(tdSev);
          var sc = r.composite_score != null ? r.composite_score : (r.cvss_score || '');
          tr.appendChild(c(typeof sc === 'number' ? sc.toFixed(1) : sc));
          tr.appendChild(c(r.status || 'open'));
          tr.appendChild(c(fmtDate(r.created_at)));
          body.appendChild(tr);
        });
      }
    } catch (e) {
      console.error('asset risks load failed', e);
    }

    // 3) Raw data button — disabled by default; enable if asset has any
    //    custom_tags content (lightweight fallback since timeline is on
    //    a separate endpoint).
    var btnRaw = document.getElementById('btnViewRaw');
    btnRaw.disabled = true;
    btnRaw.title = 'Loading timeline…';
    try {
      var tl = await apiFetch(
        '/assets/' + encodeURIComponent(assetId) + '/timeline',
        { silent: true },
      );
      var tlItems = (tl && tl.items) || [];
      if (tlItems.length) {
        btnRaw.disabled = false;
        btnRaw.title = 'View raw timeline';
        btnRaw.addEventListener('click', function () {
          var drawer = document.getElementById('rawDataDrawer');
          drawer.style.display = '';
          document.getElementById('rawDataPre').textContent =
            JSON.stringify(tl, null, 2);
        });
        document.getElementById('btnCloseRaw').addEventListener('click', function () {
          document.getElementById('rawDataDrawer').style.display = 'none';
        });
      } else {
        btnRaw.title = 'No timeline events recorded yet';
      }
    } catch (e) {
      btnRaw.title = 'Timeline unavailable';
    }
  });

  function renderTagsFromAsset(asset) {
    var row = document.getElementById('tagsRow');
    Array.from(row.querySelectorAll('.tag-chip')).forEach(function (n) { n.remove(); });
    var input = document.getElementById('tagInput');
    var tags = asset.custom_tags || {};
    Object.keys(tags).forEach(function (k) {
      var chip = document.createElement('span');
      chip.className = 'tag-chip';
      chip.textContent = tags[k] === true ? k : (k + ':' + tags[k]);
      row.insertBefore(chip, input);
    });
  }
})();
