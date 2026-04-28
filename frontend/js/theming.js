/**
 * URIP — White-Label Theming Layer (P1.5)
 *
 * Loads tenant branding (app name, logo URL, primary/secondary color) at app
 * boot and injects it into:
 *   - <title> tag
 *   - top-nav app name + logo (via window.URIP.branding for sidebar.js)
 *   - --color-primary / --color-secondary CSS variables (override --teal-accent)
 *   - favicon (best-effort, only when logo URL is provided)
 *
 * Caching
 * -------
 * Branding is cached in localStorage under `urip_branding` with a 24h TTL.
 * On boot we paint immediately from cache (zero-flash), then refresh in the
 * background and repaint if the server response differs.
 *
 * Tenant slug discovery (since /auth/login does NOT return tenant_slug today)
 * --------------------------------------------------------------------------
 * 1. localStorage `urip_tenant_slug` (set explicitly by user / super-admin tools)
 * 2. Subdomain of window.location.hostname (e.g. acme.urip.app -> "acme")
 * 3. Fall back to URIP defaults — no branding fetch attempted
 *
 * Endpoints used
 * --------------
 *   GET /api/admin/tenants/{slug}     (super-admin response includes settings JSON)
 * NOTE: there is currently NO public /tenants/{slug}/branding endpoint. For
 * tenant admins we therefore can only successfully refresh branding when the
 * caller is super-admin. Regular tenant users will fall back to cached
 * branding (which super-admin pre-warms once after onboarding) or to URIP
 * defaults. Documented as a known backend gap — see Opus-B report.
 *
 * Depends on: api.js (window.URIP.apiFetch — optional, fails gracefully)
 */
(function () {
  'use strict';

  var URIP = window.URIP || {};

  // ---------------------------------------------------------------------------
  // Defaults (URIP fall-back brand)
  // ---------------------------------------------------------------------------
  var DEFAULT_BRANDING = Object.freeze({
    app_name: 'URIP',
    app_tagline: 'Unified Risk Intelligence Platform',
    logo_url: null,           // null -> use default shield-alt FA icon
    primary_color: '#1ABC9C', // matches --teal-accent
    secondary_color: '#0D1B2A'// matches --navy-primary
  });

  var CACHE_KEY = 'urip_branding';
  var CACHE_TTL_MS = 24 * 60 * 60 * 1000; // 24h
  var SLUG_KEY = 'urip_tenant_slug';

  // ---------------------------------------------------------------------------
  // Public state — populated by applyBranding(); other modules read this.
  // ---------------------------------------------------------------------------
  URIP.branding = Object.assign({}, DEFAULT_BRANDING);

  // ---------------------------------------------------------------------------
  // Tenant-slug discovery
  // ---------------------------------------------------------------------------

  /**
   * Determine the active tenant slug.
   *
   * @returns {string|null}
   */
  function getTenantSlug() {
    try {
      var stored = localStorage.getItem(SLUG_KEY);
      if (stored && /^[a-z0-9-]+$/.test(stored)) {
        return stored;
      }
    } catch (_e) { /* localStorage may be blocked */ }

    // Subdomain heuristic: <slug>.<rest...>  (skip localhost / IPs)
    var host = window.location.hostname;
    if (host && host.indexOf('.') !== -1 && !/^\d+\.\d+\.\d+\.\d+$/.test(host)) {
      var parts = host.split('.');
      // Skip "www" and obvious non-tenant labels
      if (parts.length >= 2 && parts[0] !== 'www' && parts[0] !== 'urip') {
        return parts[0].toLowerCase();
      }
    }

    return null;
  }

  /**
   * Persist a tenant slug for later page loads.
   *
   * @param {string} slug
   */
  function setTenantSlug(slug) {
    if (!slug || !/^[a-z0-9-]+$/.test(slug)) return;
    try {
      localStorage.setItem(SLUG_KEY, slug);
    } catch (_e) { /* ignore */ }
  }

  // ---------------------------------------------------------------------------
  // Cache helpers
  // ---------------------------------------------------------------------------

  function readCache() {
    try {
      var raw = localStorage.getItem(CACHE_KEY);
      if (!raw) return null;
      var parsed = JSON.parse(raw);
      if (!parsed || typeof parsed !== 'object') return null;
      if (typeof parsed.fetched_at !== 'number') return null;
      if (Date.now() - parsed.fetched_at > CACHE_TTL_MS) return null;
      return parsed.data || null;
    } catch (_e) {
      return null;
    }
  }

  function writeCache(data) {
    try {
      localStorage.setItem(CACHE_KEY, JSON.stringify({
        fetched_at: Date.now(),
        data: data
      }));
    } catch (_e) { /* ignore quota errors */ }
  }

  function clearCache() {
    try {
      localStorage.removeItem(CACHE_KEY);
    } catch (_e) { /* ignore */ }
  }

  // ---------------------------------------------------------------------------
  // Color helpers
  // ---------------------------------------------------------------------------

  /**
   * Validate a CSS color (#hex, rgb(), hsl(), or named).
   * Uses the browser to normalise — invalid values yield empty string.
   *
   * @param {string} color
   * @returns {boolean}
   */
  function isValidColor(color) {
    if (!color || typeof color !== 'string') return false;
    var probe = document.createElement('div');
    probe.style.color = '';
    probe.style.color = color;
    return probe.style.color !== '';
  }

  /**
   * Lighten or darken a hex color by `percent` (-100..+100).
   *
   * @param {string} hex
   * @param {number} percent
   * @returns {string} hex
   */
  function shadeHex(hex, percent) {
    if (!hex || hex.charAt(0) !== '#' || (hex.length !== 7 && hex.length !== 4)) {
      return hex;
    }
    var h = hex.length === 4
      ? '#' + hex.charAt(1) + hex.charAt(1) + hex.charAt(2) + hex.charAt(2) + hex.charAt(3) + hex.charAt(3)
      : hex;
    var r = parseInt(h.substring(1, 3), 16);
    var g = parseInt(h.substring(3, 5), 16);
    var b = parseInt(h.substring(5, 7), 16);
    var amt = Math.round(2.55 * percent);
    function clamp(x) { return Math.max(0, Math.min(255, x)); }
    r = clamp(r + amt);
    g = clamp(g + amt);
    b = clamp(b + amt);
    function hx(x) { var s = x.toString(16); return s.length === 1 ? '0' + s : s; }
    return '#' + hx(r) + hx(g) + hx(b);
  }

  // ---------------------------------------------------------------------------
  // Apply branding to DOM (synchronous — safe to call multiple times)
  // ---------------------------------------------------------------------------

  /**
   * Merge given branding over defaults and paint the DOM.
   *
   * @param {object} branding - partial branding object from server / cache
   */
  function applyBranding(branding) {
    var merged = Object.assign({}, DEFAULT_BRANDING, branding || {});

    // Sanity-check colors before injecting
    if (!isValidColor(merged.primary_color)) {
      merged.primary_color = DEFAULT_BRANDING.primary_color;
    }
    if (!isValidColor(merged.secondary_color)) {
      merged.secondary_color = DEFAULT_BRANDING.secondary_color;
    }

    URIP.branding = merged;

    // 1. CSS variables — override existing teal-accent and navy-primary
    var root = document.documentElement;
    root.style.setProperty('--color-primary', merged.primary_color);
    root.style.setProperty('--color-secondary', merged.secondary_color);
    root.style.setProperty('--teal-accent', merged.primary_color);
    root.style.setProperty('--teal-hover', shadeHex(merged.primary_color, -10));
    root.style.setProperty('--navy-primary', merged.secondary_color);

    // 2. <title> — preserve any existing prefix before the pipe ("Page | ...")
    if (document.title) {
      var idx = document.title.indexOf('|');
      var prefix = idx > -1 ? document.title.substring(0, idx).trim() : '';
      var suffix = merged.app_name + (merged.app_tagline ? ' - ' + merged.app_tagline : '');
      document.title = prefix ? (prefix + ' | ' + suffix) : suffix;
    }

    // 3. Favicon — best-effort, only if logo_url provided
    if (merged.logo_url) {
      var link = document.querySelector('link[rel="icon"]');
      if (!link) {
        link = document.createElement('link');
        link.rel = 'icon';
        document.head.appendChild(link);
      }
      // Don't override the default SVG with a possibly-broken external URL
      // unless caller has explicitly opted in (logo_url is a full http(s) URL).
      if (/^https?:\/\//.test(merged.logo_url)) {
        link.href = merged.logo_url;
        link.removeAttribute('type');
      }
    }

    // 4. Notify other modules (sidebar.js renders topbar/logo from URIP.branding)
    try {
      document.dispatchEvent(new CustomEvent('urip:branding-applied', {
        detail: merged
      }));
    } catch (_e) { /* IE11 etc. — non-critical */ }
  }

  // ---------------------------------------------------------------------------
  // Fetch from server (super-admin can hit /admin/tenants/{slug})
  // ---------------------------------------------------------------------------

  /**
   * Try to refresh branding from the backend. Silent on failure.
   *
   * @param {string} slug
   */
  async function refreshBranding(slug) {
    if (!slug) return;
    if (!URIP.apiFetch) return;

    try {
      var tenant = await URIP.apiFetch('/admin/tenants/' + encodeURIComponent(slug), {
        silent: true
      });
      if (!tenant || !tenant.settings) return;

      var s = tenant.settings;
      var fresh = {
        app_name: s.app_name || tenant.name || DEFAULT_BRANDING.app_name,
        app_tagline: s.app_tagline || DEFAULT_BRANDING.app_tagline,
        logo_url: s.logo_url || null,
        primary_color: s.primary_color || DEFAULT_BRANDING.primary_color,
        secondary_color: s.secondary_color || DEFAULT_BRANDING.secondary_color
      };

      writeCache(fresh);
      applyBranding(fresh);
    } catch (_err) {
      // 401 (no token) / 403 (not super-admin) / 404 (bad slug) — silent fallback.
      // Cache (if any) already painted the page during boot().
    }
  }

  // ---------------------------------------------------------------------------
  // Boot — runs immediately on script load (paint cache), then refreshes async
  // ---------------------------------------------------------------------------

  function boot() {
    // 1. Paint cached branding ASAP (zero-flash)
    var cached = readCache();
    if (cached) {
      applyBranding(cached);
    } else {
      applyBranding(DEFAULT_BRANDING);
    }

    // 2. Background refresh (only if a tenant slug is discoverable)
    var slug = getTenantSlug();
    if (slug) {
      setTenantSlug(slug); // persist any subdomain-discovered slug
      // Defer slightly so api.js/auth.js have set the JWT header source
      setTimeout(function () { refreshBranding(slug); }, 0);
    }
  }

  // Run boot synchronously — sets CSS vars BEFORE first paint where possible.
  boot();

  // ---------------------------------------------------------------------------
  // Public API
  // ---------------------------------------------------------------------------
  URIP.theming = {
    apply: applyBranding,
    refresh: refreshBranding,
    getTenantSlug: getTenantSlug,
    setTenantSlug: setTenantSlug,
    clearCache: clearCache,
    DEFAULTS: DEFAULT_BRANDING
  };
  window.URIP = URIP;
})();
