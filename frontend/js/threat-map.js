/**
 * URIP - Threat Intelligence Page Controller
 * Loads threat pulses, IOCs, APT groups, dark web alerts, and geo stats.
 * All DOM via createElement + textContent. No innerHTML.
 * Depends on: api.js, auth.js, sidebar.js
 */
(function () {
  'use strict';

  // ─── Helpers ──────────────────────────────────────────────

  function el(tag, className, text) {
    var node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined && text !== null) node.textContent = text;
    return node;
  }

  function faIcon(iconClass) {
    var i = document.createElement('i');
    i.className = 'fas ' + iconClass;
    return i;
  }

  /** Create a TLP badge element. */
  function tlpBadge(tlp) {
    var colorMap = { red: '#E74C3C', amber: '#E67E22', green: '#27AE60', white: '#94A3B8' };
    var badge = el('span', 'ti-tlp-badge', 'TLP:' + (tlp || 'WHITE').toUpperCase());
    badge.style.cssText = 'display:inline-block;padding:2px 8px;border-radius:4px;font-size:11px;font-weight:700;color:#fff;background:' + (colorMap[(tlp || '').toLowerCase()] || colorMap.white);
    return badge;
  }

  /** Create a relevance bar element. */
  function relevanceBar(score) {
    var outer = el('div', 'ti-relevance-bar');
    outer.style.cssText = 'width:100%;height:8px;background:#E2E8F0;border-radius:4px;overflow:hidden';
    var inner = el('div', '');
    var pct = Math.min(100, Math.max(0, score));
    var color = pct > 80 ? '#E74C3C' : pct > 50 ? '#E67E22' : pct > 20 ? '#F1C40F' : '#27AE60';
    inner.style.cssText = 'height:100%;border-radius:4px;transition:width 0.6s ease;background:' + color + ';width:' + pct + '%';
    outer.appendChild(inner);
    return outer;
  }

  /** Create a severity badge. */
  function severityBadge(severity) {
    var colorMap = { critical: '#E74C3C', high: '#E67E22', medium: '#F1C40F', low: '#27AE60' };
    var badge = el('span', 'ti-severity-badge', (severity || 'medium').toUpperCase());
    badge.style.cssText = 'display:inline-block;padding:2px 10px;border-radius:4px;font-size:11px;font-weight:600;color:#fff;background:' + (colorMap[(severity || '').toLowerCase()] || '#94A3B8');
    return badge;
  }

  /** IOC type icon class. */
  function iocIcon(type) {
    var map = {
      'ipv4': 'fa-network-wired',
      'domain': 'fa-globe',
      'filehash-sha256': 'fa-fingerprint',
      'filehash-md5': 'fa-fingerprint',
      'email': 'fa-envelope',
      'url': 'fa-link',
      'cve': 'fa-bug'
    };
    return map[(type || '').toLowerCase()] || 'fa-circle';
  }

  /** Create a loading spinner inside a container. */
  function showLoading(container) {
    container.textContent = '';
    var wrap = el('div', 'ti-loading');
    wrap.style.cssText = 'display:flex;align-items:center;justify-content:center;padding:40px;color:#94A3B8';
    var spin = document.createElement('i');
    spin.className = 'fas fa-spinner fa-spin';
    spin.style.cssText = 'font-size:24px;margin-right:12px';
    wrap.appendChild(spin);
    wrap.appendChild(document.createTextNode('Loading...'));
    container.appendChild(wrap);
  }

  /** Create an error message inside a container. */
  function showError(container, msg) {
    container.textContent = '';
    var wrap = el('div', 'ti-error');
    wrap.style.cssText = 'display:flex;align-items:center;justify-content:center;padding:40px;color:#E74C3C';
    wrap.appendChild(faIcon('fa-exclamation-triangle'));
    wrap.appendChild(document.createTextNode(' ' + (msg || 'Failed to load data')));
    container.appendChild(wrap);
  }

  // ─── KPI Cards ────────────────────────────────────────────

  function updateKPI(id, value) {
    var elem = document.getElementById(id);
    if (elem) elem.textContent = String(value);
  }

  // ─── Threat Pulses ───────────────────────────────────────

  async function loadThreatPulses() {
    var container = document.getElementById('threat-pulses-container');
    if (!container) return;
    showLoading(container);

    try {
      var data = await window.URIP.apiFetch('/threat-intel/pulses');
      var pulses = (data && data.items) || [];
      container.textContent = '';

      updateKPI('kpi-pulses', pulses.length);

      // Count IOCs
      var totalIOCs = 0;
      pulses.forEach(function (p) { totalIOCs += (p.indicator_count || 0); });
      updateKPI('kpi-iocs', totalIOCs);

      // Count RE-relevant
      var reAlerts = pulses.filter(function (p) { return (p.relevance_score || 0) >= 50; }).length;
      updateKPI('kpi-re-alerts', reAlerts);

      if (pulses.length === 0) {
        container.appendChild(el('div', 'ti-empty', 'No threat pulses found'));
        return;
      }

      pulses.forEach(function (pulse) {
        var card = el('div', 'ti-pulse-card');

        // Header row: name + TLP
        var header = el('div', 'ti-pulse-header');
        var nameEl = el('div', 'ti-pulse-name', pulse.name || 'Unnamed Pulse');
        header.appendChild(nameEl);
        header.appendChild(tlpBadge(pulse.tlp));
        card.appendChild(header);

        // Adversary row
        if (pulse.adversary) {
          var advRow = el('div', 'ti-pulse-adversary');
          advRow.appendChild(faIcon('fa-user-secret'));
          advRow.appendChild(document.createTextNode(' ' + pulse.adversary));
          card.appendChild(advRow);
        }

        // Description
        var descEl = el('div', 'ti-pulse-desc', pulse.description || '');
        card.appendChild(descEl);

        // Meta row: countries, indicators, relevance
        var meta = el('div', 'ti-pulse-meta');

        // Countries
        var countriesEl = el('span', 'ti-pulse-countries');
        countriesEl.appendChild(faIcon('fa-map-marker-alt'));
        var countryList = (pulse.targeted_countries || []).join(', ') || 'Unknown';
        countriesEl.appendChild(document.createTextNode(' ' + countryList));
        meta.appendChild(countriesEl);

        // Indicator count
        var indEl = el('span', 'ti-pulse-indicators');
        indEl.appendChild(faIcon('fa-crosshairs'));
        indEl.appendChild(document.createTextNode(' ' + (pulse.indicator_count || 0) + ' IOCs'));
        meta.appendChild(indEl);

        card.appendChild(meta);

        // Relevance bar
        var relRow = el('div', 'ti-pulse-relevance');
        var relLabel = el('span', 'ti-relevance-label', 'RE Relevance: ' + Math.round(pulse.relevance_score || 0) + '%');
        relRow.appendChild(relLabel);
        relRow.appendChild(relevanceBar(pulse.relevance_score || 0));
        card.appendChild(relRow);

        // Tags
        if (pulse.tags && pulse.tags.length > 0) {
          var tagsRow = el('div', 'ti-pulse-tags');
          pulse.tags.forEach(function (tag) {
            var tagEl = el('span', 'ti-tag', tag);
            tagsRow.appendChild(tagEl);
          });
          card.appendChild(tagsRow);
        }

        container.appendChild(card);
      });
    } catch (err) {
      showError(container, 'Failed to load threat pulses');
      console.error('Threat pulses error:', err);
    }
  }

  // ─── IOC Table ────────────────────────────────────────────

  var allIOCs = [];

  async function loadIOCs() {
    var container = document.getElementById('ioc-table-container');
    if (!container) return;
    showLoading(container);

    try {
      var data = await window.URIP.apiFetch('/threat-intel/iocs');
      allIOCs = (data && data.items) || [];
      renderIOCTable(allIOCs, container);
    } catch (err) {
      showError(container, 'Failed to load IOCs');
      console.error('IOCs error:', err);
    }
  }

  function renderIOCTable(iocs, container) {
    container.textContent = '';

    if (iocs.length === 0) {
      container.appendChild(el('div', 'ti-empty', 'No IOCs found'));
      return;
    }

    var table = el('table', 'ti-table');

    // Header
    var thead = document.createElement('thead');
    var headerRow = document.createElement('tr');
    ['Type', 'Indicator', 'Description', 'Source Pulse', 'TLP', 'Relevance'].forEach(function (h) {
      var th = el('th', '', h);
      headerRow.appendChild(th);
    });
    thead.appendChild(headerRow);
    table.appendChild(thead);

    // Body
    var tbody = document.createElement('tbody');
    iocs.forEach(function (ioc) {
      var tr = document.createElement('tr');

      // Type with icon
      var tdType = document.createElement('td');
      var typeWrap = el('span', 'ti-ioc-type');
      typeWrap.appendChild(faIcon(iocIcon(ioc.type)));
      typeWrap.appendChild(document.createTextNode(' ' + (ioc.type || '')));
      tdType.appendChild(typeWrap);
      tr.appendChild(tdType);

      // Indicator value
      var tdInd = el('td', 'ti-ioc-value', ioc.indicator || '');
      tdInd.style.fontFamily = "'Courier New', monospace";
      tdInd.style.fontSize = '13px';
      tr.appendChild(tdInd);

      // Description
      tr.appendChild(el('td', '', ioc.description || ''));

      // Source pulse
      var tdSource = el('td', 'ti-ioc-source');
      tdSource.textContent = (ioc.source_pulse || '').substring(0, 50);
      if ((ioc.source_pulse || '').length > 50) tdSource.textContent += '...';
      tr.appendChild(tdSource);

      // TLP
      var tdTlp = document.createElement('td');
      tdTlp.appendChild(tlpBadge(ioc.tlp));
      tr.appendChild(tdTlp);

      // Relevance
      var tdRel = document.createElement('td');
      tdRel.style.minWidth = '100px';
      tdRel.appendChild(relevanceBar(ioc.relevance_score || 0));
      tr.appendChild(tdRel);

      tbody.appendChild(tr);
    });
    table.appendChild(tbody);

    var tableWrap = el('div', 'ti-table-wrap');
    tableWrap.style.overflowX = 'auto';
    tableWrap.appendChild(table);
    container.appendChild(tableWrap);
  }

  function filterIOCs(query) {
    if (!query) {
      renderIOCTable(allIOCs, document.getElementById('ioc-table-container'));
      return;
    }
    var q = query.toLowerCase();
    var filtered = allIOCs.filter(function (ioc) {
      return (ioc.indicator || '').toLowerCase().indexOf(q) !== -1 ||
             (ioc.type || '').toLowerCase().indexOf(q) !== -1 ||
             (ioc.description || '').toLowerCase().indexOf(q) !== -1 ||
             (ioc.source_pulse || '').toLowerCase().indexOf(q) !== -1;
    });
    renderIOCTable(filtered, document.getElementById('ioc-table-container'));
  }

  // ─── APT Groups ───────────────────────────────────────────

  async function loadAPTGroups() {
    var container = document.getElementById('apt-groups-container');
    if (!container) return;
    showLoading(container);

    try {
      var data = await window.URIP.apiFetch('/threat-intel/apt-groups');
      var groups = (data && data.items) || [];
      container.textContent = '';

      updateKPI('kpi-apt-groups', groups.length);

      if (groups.length === 0) {
        container.appendChild(el('div', 'ti-empty', 'No APT groups found'));
        return;
      }

      // Show first 30 to keep page responsive
      var displayGroups = groups.slice(0, 30);

      var table = el('table', 'ti-table');

      var thead = document.createElement('thead');
      var headerRow = document.createElement('tr');
      ['Name', 'Country', 'Aliases', 'Targeted Sectors', 'Description'].forEach(function (h) {
        headerRow.appendChild(el('th', '', h));
      });
      thead.appendChild(headerRow);
      table.appendChild(thead);

      var tbody = document.createElement('tbody');
      displayGroups.forEach(function (group) {
        var tr = document.createElement('tr');

        // Name
        var tdName = el('td', 'ti-apt-name', group.name || '');
        tdName.style.fontWeight = '600';
        tr.appendChild(tdName);

        // Country
        var tdCountry = el('td', '', group.country || 'Unknown');
        tr.appendChild(tdCountry);

        // Aliases
        var tdAliases = el('td', 'ti-apt-aliases');
        var aliases = (group.aliases || []).slice(0, 3);
        aliases.forEach(function (alias) {
          var tag = el('span', 'ti-tag ti-tag-sm', alias);
          tdAliases.appendChild(tag);
        });
        if ((group.aliases || []).length > 3) {
          tdAliases.appendChild(el('span', 'ti-tag ti-tag-sm ti-tag-more', '+' + ((group.aliases || []).length - 3)));
        }
        tr.appendChild(tdAliases);

        // Targeted sectors
        var tdSectors = el('td', 'ti-apt-sectors');
        (group.targeting || []).forEach(function (sector) {
          var tag = el('span', 'ti-tag ti-tag-sector', sector);
          tdSectors.appendChild(tag);
        });
        tr.appendChild(tdSectors);

        // Description (truncated)
        var desc = (group.description || '').substring(0, 120);
        if ((group.description || '').length > 120) desc += '...';
        tr.appendChild(el('td', 'ti-apt-desc', desc));

        tbody.appendChild(tr);
      });
      table.appendChild(tbody);

      var tableWrap = el('div', 'ti-table-wrap');
      tableWrap.style.overflowX = 'auto';
      tableWrap.appendChild(table);
      container.appendChild(tableWrap);

      if (groups.length > 30) {
        var moreNote = el('div', 'ti-more-note', 'Showing 30 of ' + groups.length + ' APT groups');
        moreNote.style.cssText = 'text-align:center;padding:12px;color:#94A3B8;font-size:13px';
        container.appendChild(moreNote);
      }
    } catch (err) {
      showError(container, 'Failed to load APT groups');
      console.error('APT groups error:', err);
    }
  }

  // ─── Dark Web Alerts ──────────────────────────────────────

  async function loadDarkWebAlerts() {
    var container = document.getElementById('dark-web-container');
    if (!container) return;
    showLoading(container);

    try {
      var data = await window.URIP.apiFetch('/threat-intel/dark-web');
      var alerts = (data && data.items) || [];
      container.textContent = '';

      if (alerts.length === 0) {
        container.appendChild(el('div', 'ti-empty', 'No dark web alerts'));
        return;
      }

      alerts.forEach(function (alert) {
        var card = el('div', 'ti-dw-card');

        // Severity stripe
        var severityColors = { critical: '#E74C3C', high: '#E67E22', medium: '#F1C40F', low: '#27AE60' };
        card.style.borderLeft = '4px solid ' + (severityColors[(alert.severity || '').toLowerCase()] || '#94A3B8');

        // Header: title + severity badge
        var header = el('div', 'ti-dw-header');
        var titleEl = el('div', 'ti-dw-title', alert.title || 'Alert');
        header.appendChild(titleEl);
        header.appendChild(severityBadge(alert.severity));
        card.appendChild(header);

        // Type + Source
        var typeRow = el('div', 'ti-dw-type');
        var typeLabel = el('span', 'ti-dw-type-label');
        var typeIconMap = {
          'credential_dump': 'fa-key',
          'brand_mention': 'fa-bullhorn',
          'data_leak': 'fa-database',
          'typosquat_domain': 'fa-globe',
          'exploit_sale': 'fa-bug'
        };
        typeLabel.appendChild(faIcon(typeIconMap[alert.type] || 'fa-exclamation'));
        var typeText = (alert.type || '').replace(/_/g, ' ');
        typeText = typeText.charAt(0).toUpperCase() + typeText.slice(1);
        typeLabel.appendChild(document.createTextNode(' ' + typeText));
        typeRow.appendChild(typeLabel);

        var sourceEl = el('span', 'ti-dw-source');
        sourceEl.appendChild(faIcon('fa-eye'));
        sourceEl.appendChild(document.createTextNode(' ' + (alert.source || 'Unknown')));
        typeRow.appendChild(sourceEl);
        card.appendChild(typeRow);

        // Description
        card.appendChild(el('div', 'ti-dw-desc', alert.description || ''));

        // Affected domains
        if (alert.domains_affected && alert.domains_affected.length > 0) {
          var domainsRow = el('div', 'ti-dw-domains');
          var domainsLabel = el('span', 'ti-dw-domains-label', 'Affected: ');
          domainsLabel.style.fontWeight = '600';
          domainsRow.appendChild(domainsLabel);
          alert.domains_affected.forEach(function (domain) {
            domainsRow.appendChild(el('span', 'ti-tag', domain));
          });
          card.appendChild(domainsRow);
        }

        // Status badge
        var statusRow = el('div', 'ti-dw-status-row');
        var statusColors = { active: '#E74C3C', monitoring: '#E67E22', contained: '#27AE60' };
        var statusBadge = el('span', 'ti-dw-status', (alert.status || 'unknown').toUpperCase());
        statusBadge.style.cssText = 'display:inline-block;padding:2px 10px;border-radius:4px;font-size:11px;font-weight:600;color:#fff;background:' + (statusColors[(alert.status || '').toLowerCase()] || '#94A3B8');
        statusRow.appendChild(statusBadge);

        // Accounts affected
        if (alert.affected_accounts > 0) {
          var accEl = el('span', 'ti-dw-accounts');
          accEl.appendChild(faIcon('fa-users'));
          accEl.appendChild(document.createTextNode(' ' + alert.affected_accounts + ' accounts'));
          statusRow.appendChild(accEl);
        }
        card.appendChild(statusRow);

        // Recommended actions
        if (alert.recommended_actions && alert.recommended_actions.length > 0) {
          var actionsDiv = el('div', 'ti-dw-actions');
          var actionsLabel = el('div', 'ti-dw-actions-label', 'Recommended Actions:');
          actionsDiv.appendChild(actionsLabel);
          var actionsList = el('ul', 'ti-dw-actions-list');
          alert.recommended_actions.forEach(function (action) {
            var li = el('li', '', action);
            actionsList.appendChild(li);
          });
          actionsDiv.appendChild(actionsList);
          card.appendChild(actionsDiv);
        }

        container.appendChild(card);
      });
    } catch (err) {
      showError(container, 'Failed to load dark web alerts');
      console.error('Dark web alerts error:', err);
    }
  }

  // ─── Geo Stats ────────────────────────────────────────────

  async function loadGeoStats() {
    var container = document.getElementById('geo-stats-container');
    if (!container) return;
    showLoading(container);

    try {
      var data = await window.URIP.apiFetch('/threat-intel/geo-stats');
      var stats = (data && data.items) || [];
      container.textContent = '';

      if (stats.length === 0) {
        container.appendChild(el('div', 'ti-empty', 'No geo stats available'));
        return;
      }

      stats.forEach(function (stat) {
        var card = el('div', 'ti-geo-card');

        // Color code by relevance
        var relColor = stat.max_relevance > 80 ? '#E74C3C' :
                       stat.max_relevance > 50 ? '#E67E22' :
                       stat.max_relevance > 20 ? '#F1C40F' : '#94A3B8';
        card.style.borderLeft = '4px solid ' + relColor;

        // Country header
        var header = el('div', 'ti-geo-header');
        var countryEl = el('span', 'ti-geo-country', stat.country || 'Unknown');
        countryEl.style.fontWeight = '700';
        countryEl.style.fontSize = '16px';
        header.appendChild(countryEl);

        var countBadge = el('span', 'ti-geo-count', stat.threat_count + ' threats');
        countBadge.style.cssText = 'display:inline-block;padding:2px 10px;border-radius:12px;font-size:12px;font-weight:600;color:#fff;background:' + relColor;
        header.appendChild(countBadge);
        card.appendChild(header);

        // TLP levels
        var tlpRow = el('div', 'ti-geo-tlps');
        (stat.tlp_levels || []).forEach(function (tlp) {
          tlpRow.appendChild(tlpBadge(tlp));
        });
        card.appendChild(tlpRow);

        // Pulse names
        var pulsesRow = el('div', 'ti-geo-pulses');
        (stat.pulse_names || []).forEach(function (name) {
          var truncated = name.length > 60 ? name.substring(0, 60) + '...' : name;
          var pulseTag = el('div', 'ti-geo-pulse-name');
          pulseTag.appendChild(faIcon('fa-crosshairs'));
          pulseTag.appendChild(document.createTextNode(' ' + truncated));
          pulsesRow.appendChild(pulseTag);
        });
        card.appendChild(pulsesRow);

        // Relevance bar
        var relRow = el('div', 'ti-geo-relevance');
        relRow.appendChild(el('span', '', 'Max Relevance: ' + Math.round(stat.max_relevance) + '%'));
        relRow.appendChild(relevanceBar(stat.max_relevance));
        card.appendChild(relRow);

        container.appendChild(card);
      });
    } catch (err) {
      showError(container, 'Failed to load geo stats');
      console.error('Geo stats error:', err);
    }
  }

  // ─── IOC Matches ──────────────────────────────────────────

  async function loadIOCMatches() {
    var container = document.getElementById('ioc-matches-container');
    if (!container) return;
    showLoading(container);

    try {
      var data = await window.URIP.apiFetch('/threat-intel/iocs/match');
      var matches = (data && data.items) || [];
      container.textContent = '';

      // Summary bar
      var summary = el('div', 'ti-match-summary');
      summary.style.cssText = 'display:flex;gap:24px;padding:12px 16px;background:#FEF3C7;border-radius:8px;margin-bottom:16px;font-size:13px;color:#92400E';

      var checkedEl = el('span', '');
      checkedEl.appendChild(faIcon('fa-search'));
      checkedEl.appendChild(document.createTextNode(' ' + (data.total_iocs_checked || 0) + ' IOCs checked'));
      summary.appendChild(checkedEl);

      var matchedEl = el('span', '');
      matchedEl.style.fontWeight = '700';
      matchedEl.appendChild(faIcon('fa-exclamation-triangle'));
      matchedEl.appendChild(document.createTextNode(' ' + matches.length + ' matches found'));
      summary.appendChild(matchedEl);

      var rateEl = el('span', '');
      rateEl.appendChild(faIcon('fa-percentage'));
      rateEl.appendChild(document.createTextNode(' ' + (data.match_rate || 0) + '% match rate'));
      summary.appendChild(rateEl);

      container.appendChild(summary);

      if (matches.length === 0) {
        container.appendChild(el('div', 'ti-empty', 'No IOC matches found in infrastructure'));
        return;
      }

      var table = el('table', 'ti-table');
      var thead = document.createElement('thead');
      var headerRow = document.createElement('tr');
      ['IOC', 'Type', 'Adversary', 'Matched In', 'Hits', 'Action', 'TLP'].forEach(function (h) {
        headerRow.appendChild(el('th', '', h));
      });
      thead.appendChild(headerRow);
      table.appendChild(thead);

      var tbody = document.createElement('tbody');
      matches.forEach(function (match) {
        var tr = document.createElement('tr');
        tr.style.background = '#FFF5F5';

        var tdIOC = el('td', 'ti-ioc-value', match.ioc || '');
        tdIOC.style.fontFamily = "'Courier New', monospace";
        tdIOC.style.fontSize = '13px';
        tdIOC.style.fontWeight = '600';
        tr.appendChild(tdIOC);

        tr.appendChild(el('td', '', match.ioc_type || ''));
        tr.appendChild(el('td', '', match.adversary || 'Unknown'));
        tr.appendChild(el('td', '', match.matched_in || ''));

        var tdHits = el('td', '');
        tdHits.style.fontWeight = '700';
        tdHits.style.color = '#E74C3C';
        tdHits.textContent = String(match.match_count || 0);
        tr.appendChild(tdHits);

        var tdAction = document.createElement('td');
        var actionBadge = el('span', 'ti-action-badge', match.action_taken || '');
        var actionColors = { 'Blocked': '#27AE60', 'Quarantined': '#E67E22', 'Sinkholed': '#3498DB' };
        actionBadge.style.cssText = 'display:inline-block;padding:2px 8px;border-radius:4px;font-size:11px;font-weight:600;color:#fff;background:' + (actionColors[match.action_taken] || '#94A3B8');
        tdAction.appendChild(actionBadge);
        tr.appendChild(tdAction);

        var tdTlp = document.createElement('td');
        tdTlp.appendChild(tlpBadge(match.tlp));
        tr.appendChild(tdTlp);

        tbody.appendChild(tr);
      });
      table.appendChild(tbody);

      var tableWrap = el('div', 'ti-table-wrap');
      tableWrap.style.overflowX = 'auto';
      tableWrap.appendChild(table);
      container.appendChild(tableWrap);
    } catch (err) {
      showError(container, 'Failed to load IOC matches');
      console.error('IOC matches error:', err);
    }
  }

  // ─── Init ─────────────────────────────────────────────────

  function initThreatMap() {
    // Wire up search
    var searchInput = document.getElementById('ioc-search');
    if (searchInput) {
      var debounceTimer = null;
      searchInput.addEventListener('input', function () {
        var val = searchInput.value;
        clearTimeout(debounceTimer);
        debounceTimer = setTimeout(function () { filterIOCs(val); }, 300);
      });
    }

    // Wire up refresh button
    var refreshBtn = document.getElementById('btnRefreshTI');
    if (refreshBtn) {
      refreshBtn.addEventListener('click', function () {
        window.location.reload();
      });
    }

    // Load all sections in parallel
    loadThreatPulses();
    loadIOCs();
    loadAPTGroups();
    loadDarkWebAlerts();
    loadGeoStats();
    loadIOCMatches();
  }

  // Expose
  window.initThreatMap = initThreatMap;
})();
