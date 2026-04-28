/**
 * URIP — Module Subscription Admin UI (P1.3)
 *
 * Lists the 9 capability modules for a tenant. For each module, shows:
 *   - status (enabled / disabled / not yet provisioned)
 *   - billing tier (TRIAL / STANDARD / PREMIUM)
 *   - expiry
 *
 * Super-admin can:
 *   - toggle a module on/off
 *   - change tier
 *   - set expiry
 *   - query any tenant via ?tenant=slug
 *
 * Tenant admin (non-super) sees their own tenant only and cannot mutate.
 *
 * Backend routes used (all from backend/routers/tenants.py):
 *   GET    /api/tenants/{slug}/modules                         (read; tenant or super)
 *   POST   /api/admin/tenants/{slug}/modules                   (super-admin enable)
 *   PATCH  /api/admin/tenants/{slug}/modules/{module_code}     (super-admin tier/expiry/enabled)
 *   DELETE /api/admin/tenants/{slug}/modules/{module_code}     (super-admin soft-disable)
 *
 * Backend gap: there is NO tenant-scoped endpoint exposing the caller's own
 * slug today. So tenant admins must rely on either localStorage.urip_tenant_slug
 * (set by theming.js / by super-admin tools) or the subdomain heuristic. If
 * neither is available, we surface the slug input prominently.
 *
 * Depends on: api.js, theming.js
 */
(function () {
  'use strict';

  function $(id) { return document.getElementById(id); }

  // Module catalogue (matches backend MODULE_CODES) — display labels & icons
  var MODULES = [
    { code: 'CORE',       name: 'Core',                       icon: 'fa-shield-halved', description: 'Auth, risk register, audit log, dashboard. Always enabled.', alwaysOn: true },
    { code: 'VM',         name: 'Vulnerability Management',   icon: 'fa-bug',           description: 'Tenable / Qualys / Rapid7 connectors.' },
    { code: 'EDR',        name: 'Endpoint Detection',         icon: 'fa-laptop-medical',description: 'SentinelOne / CrowdStrike telemetry.' },
    { code: 'NETWORK',    name: 'Network / CASB / SASE',      icon: 'fa-network-wired', description: 'Zscaler / Netskope / Palo Alto.' },
    { code: 'IDENTITY',   name: 'Identity & Access',          icon: 'fa-id-badge',      description: 'MS Entra / Okta / Google Workspace.' },
    { code: 'COLLAB',     name: 'Collaboration',              icon: 'fa-users',         description: 'SharePoint / Teams / Slack / Confluence.' },
    { code: 'ITSM',       name: 'IT Service Management',      icon: 'fa-headset',       description: 'ServiceNow / Jira / ManageEngine SDP.' },
    { code: 'DAST',       name: 'Dynamic AppSec Testing',     icon: 'fa-spider',        description: 'Burpsuite / OWASP ZAP / Acunetix.' },
    { code: 'DLP',        name: 'Data Loss Prevention',       icon: 'fa-database',      description: 'GTB / Forcepoint / Symantec DLP.' },
    { code: 'COMPLIANCE', name: 'Compliance & Audit',         icon: 'fa-clipboard-check', description: 'SOC2 / ISO 27001 / GDPR / HIPAA / PCI DSS.' }
  ];

  var TIERS = ['TRIAL', 'STANDARD', 'PREMIUM'];

  var TIER_COLOR = {
    TRIAL:    { bg: 'rgba(241,196,15,0.15)', color: '#B7950B' },
    STANDARD: { bg: 'rgba(26,188,156,0.15)', color: '#1ABC9C' },
    PREMIUM:  { bg: 'rgba(99,102,241,0.15)', color: '#6366F1' }
  };

  // State
  var activeSlug = null;
  var isSuperAdmin = false;       // detected by trying super-admin only mutation paths
  var subscriptions = {};         // { module_code: subscription }

  // ---------------------------------------------------------------------------
  // Slug discovery
  // ---------------------------------------------------------------------------

  function readSlugFromQuery() {
    try {
      var p = new URLSearchParams(window.location.search);
      var s = p.get('tenant') || p.get('slug');
      return s ? s.toLowerCase() : null;
    } catch (_e) { return null; }
  }

  function discoverSlug() {
    return readSlugFromQuery()
      || (window.URIP.theming && window.URIP.theming.getTenantSlug())
      || null;
  }

  // ---------------------------------------------------------------------------
  // Render
  // ---------------------------------------------------------------------------

  function showError(msg) {
    $('modulesLoading').style.display = 'none';
    $('modulesContent').style.display = 'none';
    $('modulesError').style.display = 'flex';
    $('modulesErrorMsg').textContent = msg;
  }

  function showContent() {
    $('modulesLoading').style.display = 'none';
    $('modulesError').style.display = 'none';
    $('modulesContent').style.display = 'block';
  }

  function fmtDate(iso) {
    if (!iso) return null;
    try {
      return new Date(iso).toLocaleDateString('en-US', { year: 'numeric', month: 'short', day: 'numeric' });
    } catch (_e) {
      return iso;
    }
  }

  function renderGrid() {
    var grid = $('modulesGrid');
    grid.textContent = '';

    MODULES.forEach(function (m) {
      var sub = subscriptions[m.code] || null;
      var enabled = sub ? sub.is_enabled : (m.alwaysOn === true);
      var tier = sub ? sub.billing_tier : (m.alwaysOn ? 'STANDARD' : null);
      var expires = sub ? sub.expires_at : null;

      var card = document.createElement('div');
      card.className = 'module-card' + (enabled ? ' enabled' : ' disabled');

      // Header row
      var header = document.createElement('div');
      header.className = 'module-card-header';

      var iconWrap = document.createElement('div');
      iconWrap.className = 'module-icon';
      var icon = document.createElement('i');
      icon.className = 'fas ' + m.icon;
      iconWrap.appendChild(icon);
      header.appendChild(iconWrap);

      var titleWrap = document.createElement('div');
      titleWrap.className = 'module-title-wrap';
      var title = document.createElement('div');
      title.className = 'module-title';
      title.textContent = m.name;
      titleWrap.appendChild(title);
      var code = document.createElement('div');
      code.className = 'module-code';
      code.textContent = m.code;
      titleWrap.appendChild(code);
      header.appendChild(titleWrap);

      // Toggle (super-admin only, except CORE)
      var toggleWrap = document.createElement('div');
      toggleWrap.className = 'module-toggle-wrap';

      if (m.alwaysOn) {
        var lock = document.createElement('span');
        lock.className = 'module-locked';
        lock.title = 'Core module — always on'; lock.setAttribute('aria-label', 'Core module — always on');
        var lockIcon = document.createElement('i');
        lockIcon.className = 'fas fa-lock';
        lock.appendChild(lockIcon);
        toggleWrap.appendChild(lock);
      } else if (isSuperAdmin) {
        var label = document.createElement('label');
        label.className = 'switch';
        var cb = document.createElement('input');
        cb.type = 'checkbox';
        cb.checked = enabled;
        cb.addEventListener('change', (function (moduleCode, currentSub) {
          return function () { handleToggle(moduleCode, cb, currentSub); };
        })(m.code, sub));
        label.appendChild(cb);
        var slider = document.createElement('span');
        slider.className = 'switch-slider';
        label.appendChild(slider);
        toggleWrap.appendChild(label);
      } else {
        // Read-only badge for tenant admin
        var roBadge = document.createElement('span');
        roBadge.className = 'badge ' + (enabled ? 'badge-low' : 'badge-default');
        roBadge.textContent = enabled ? 'Enabled' : 'Disabled';
        toggleWrap.appendChild(roBadge);
      }
      header.appendChild(toggleWrap);

      card.appendChild(header);

      // Description
      var desc = document.createElement('p');
      desc.className = 'module-desc';
      desc.textContent = m.description;
      card.appendChild(desc);

      // Footer: tier + expiry
      var footer = document.createElement('div');
      footer.className = 'module-footer';

      // Tier
      var tierWrap = document.createElement('div');
      tierWrap.className = 'module-tier-wrap';
      var tierLabel = document.createElement('span');
      tierLabel.className = 'module-tier-label';
      tierLabel.textContent = 'Tier:';
      tierWrap.appendChild(tierLabel);

      if (m.alwaysOn) {
        var tierBadge = document.createElement('span');
        tierBadge.className = 'module-tier-badge';
        tierBadge.textContent = 'STANDARD';
        var c = TIER_COLOR.STANDARD;
        tierBadge.style.background = c.bg;
        tierBadge.style.color = c.color;
        tierWrap.appendChild(tierBadge);
      } else if (isSuperAdmin && enabled) {
        var sel = document.createElement('select');
        sel.className = 'module-tier-select form-input';
        TIERS.forEach(function (tt) {
          var opt = document.createElement('option');
          opt.value = tt;
          opt.textContent = tt;
          if (tt === tier) opt.selected = true;
          sel.appendChild(opt);
        });
        sel.addEventListener('change', (function (moduleCode) {
          return function () { handleTierChange(moduleCode, sel); };
        })(m.code));
        tierWrap.appendChild(sel);
      } else {
        var tb = document.createElement('span');
        tb.className = 'module-tier-badge';
        tb.textContent = tier || '—';
        if (tier && TIER_COLOR[tier]) {
          tb.style.background = TIER_COLOR[tier].bg;
          tb.style.color = TIER_COLOR[tier].color;
        }
        tierWrap.appendChild(tb);
      }
      footer.appendChild(tierWrap);

      // Expiry
      var expWrap = document.createElement('div');
      expWrap.className = 'module-expiry';
      if (enabled) {
        var formattedExpiry = expires ? fmtDate(expires) : 'No expiry';
        expWrap.textContent = 'Expires: ' + formattedExpiry;
        if (expires) {
          var expDate = new Date(expires);
          if (expDate < new Date()) {
            expWrap.style.color = '#E74C3C';
            expWrap.textContent = 'Expired ' + formattedExpiry;
          } else if ((expDate - new Date()) < 14 * 24 * 3600 * 1000) {
            expWrap.style.color = '#E67E22';
          }
        }
      } else {
        expWrap.textContent = sub ? 'Soft-disabled' : 'Not provisioned';
        expWrap.style.color = '#94A3B8';
      }
      footer.appendChild(expWrap);

      card.appendChild(footer);
      grid.appendChild(card);
    });
  }

  // ---------------------------------------------------------------------------
  // Mutations (super-admin only)
  // ---------------------------------------------------------------------------

  async function handleToggle(moduleCode, cb, currentSub) {
    var turningOn = cb.checked;
    cb.disabled = true;

    try {
      var resp;
      if (turningOn) {
        if (currentSub && !currentSub.is_enabled) {
          // re-enable existing subscription via PATCH
          resp = await window.URIP.apiFetch(
            '/admin/tenants/' + encodeURIComponent(activeSlug) + '/modules/' + encodeURIComponent(moduleCode),
            {
              method: 'PATCH',
              body: JSON.stringify({ is_enabled: true })
            }
          );
        } else {
          // brand-new subscription via POST
          resp = await window.URIP.apiFetch(
            '/admin/tenants/' + encodeURIComponent(activeSlug) + '/modules',
            {
              method: 'POST',
              body: JSON.stringify({ module_code: moduleCode, billing_tier: 'TRIAL' })
            }
          );
        }
        if (resp) subscriptions[moduleCode] = resp;
        window.URIP.showNotification('Enabled', moduleCode + ' enabled.', 'success');
      } else {
        // soft-disable via DELETE
        resp = await window.URIP.apiFetch(
          '/admin/tenants/' + encodeURIComponent(activeSlug) + '/modules/' + encodeURIComponent(moduleCode),
          { method: 'DELETE' }
        );
        if (resp && resp.subscription) subscriptions[moduleCode] = resp.subscription;
        window.URIP.showNotification('Disabled', moduleCode + ' disabled.', 'info');
      }
      renderGrid();
    } catch (err) {
      cb.checked = !turningOn;
      var msg = (err && err.body && err.body.detail) ||
                (err && err.message) || 'Failed to update module.';
      if (err && err.status === 403) {
        msg = 'Super-admin access required.';
        isSuperAdmin = false;
        renderGrid();
      }
      window.URIP.showNotification('Update Failed', msg, 'error');
    } finally {
      cb.disabled = false;
    }
  }

  async function handleTierChange(moduleCode, sel) {
    var newTier = sel.value;
    sel.disabled = true;

    try {
      var resp = await window.URIP.apiFetch(
        '/admin/tenants/' + encodeURIComponent(activeSlug) + '/modules/' + encodeURIComponent(moduleCode),
        {
          method: 'PATCH',
          body: JSON.stringify({ billing_tier: newTier })
        }
      );
      if (resp) subscriptions[moduleCode] = resp;
      window.URIP.showNotification('Tier Updated', moduleCode + ' set to ' + newTier + '.', 'success');
      renderGrid();
    } catch (err) {
      // revert
      var prev = subscriptions[moduleCode];
      if (prev) sel.value = prev.billing_tier;
      var msg = (err && err.body && err.body.detail) ||
                (err && err.message) || 'Failed to update tier.';
      window.URIP.showNotification('Tier Update Failed', msg, 'error');
    } finally {
      sel.disabled = false;
    }
  }

  // ---------------------------------------------------------------------------
  // Load
  // ---------------------------------------------------------------------------

  /**
   * Detect whether the caller is a super-admin.
   * We try GET /api/admin/tenants — super-admin only. If 200, we're super-admin.
   */
  async function detectSuperAdmin() {
    try {
      await window.URIP.apiFetch('/admin/tenants', { silent: true });
      return true;
    } catch (err) {
      return false;
    }
  }

  async function loadModules(slug) {
    if (!slug || !/^[a-z0-9-]+$/.test(slug)) {
      showError('No tenant slug provided. Set ?tenant=slug in the URL or paste a slug above.');
      return;
    }

    activeSlug = slug;
    $('pageSubtitle').textContent = 'Tenant: ' + slug;
    $('tenantSlugInput').value = slug;

    $('modulesLoading').style.display = 'flex';
    $('modulesContent').style.display = 'none';
    $('modulesError').style.display = 'none';

    try {
      // Detect super-admin first (so we know whether to render toggles)
      isSuperAdmin = await detectSuperAdmin();
      $('readOnlyNotice').style.display = isSuperAdmin ? 'none' : 'flex';

      // Fetch subscriptions for this tenant
      var subs = await window.URIP.apiFetch('/tenants/' + encodeURIComponent(slug) + '/modules');
      subscriptions = {};
      (subs || []).forEach(function (s) {
        subscriptions[s.module_code] = s;
      });

      renderGrid();
      showContent();
    } catch (err) {
      var msg;
      if (err && err.status === 403) {
        msg = 'You do not have permission to view modules for tenant "' + slug + '".';
      } else if (err && err.status === 404) {
        msg = 'Tenant "' + slug + '" not found.';
      } else {
        msg = (err && err.body && err.body.detail) ||
              (err && err.message) || 'Failed to load modules.';
      }
      showError(msg);
    }
  }

  // ---------------------------------------------------------------------------
  // Init
  // ---------------------------------------------------------------------------

  document.addEventListener('DOMContentLoaded', function () {
    if (!$('modulesGrid')) return;

    var slug = discoverSlug();
    if (slug) {
      loadModules(slug);
    } else {
      $('modulesLoading').style.display = 'none';
      showError('No tenant slug detected. Paste your tenant slug above and click Load.');
    }

    $('btnLoad').addEventListener('click', function () {
      var v = ($('tenantSlugInput').value || '').trim().toLowerCase();
      if (v) {
        // Update URL so refreshes work
        var newUrl = window.location.pathname + '?tenant=' + encodeURIComponent(v);
        window.history.replaceState({}, '', newUrl);
        loadModules(v);
      }
    });

    $('tenantSlugInput').addEventListener('keydown', function (e) {
      if (e.key === 'Enter') {
        e.preventDefault();
        $('btnLoad').click();
      }
    });
  });
})();
