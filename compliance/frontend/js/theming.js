/**
 * URIP COMPLIANCE — Tenant theming
 *
 * Pulls tenant branding from URIP (when integrated) so the compliance UI
 * matches the tenant's brand. In standalone mode this is a no-op (defaults
 * remain).
 *
 * Mirrors the URIP frontend's theming.js but only consumes the branding
 * payload — does not duplicate the upload-policy/admin-side editing UI.
 */
(function () {
  'use strict';

  var COMPLIANCE = window.COMPLIANCE || {};

  function applyVars(brand) {
    var root = document.documentElement;
    if (!brand) return;
    if (brand.color_primary) root.style.setProperty('--teal-accent', brand.color_primary);
    if (brand.color_primary_hover) root.style.setProperty('--teal-hover', brand.color_primary_hover);
    if (brand.color_navy) root.style.setProperty('--navy-primary', brand.color_navy);
    if (brand.favicon_url) {
      var link = document.querySelector("link[rel='icon']");
      if (!link) {
        link = document.createElement('link');
        link.rel = 'icon';
        document.head.appendChild(link);
      }
      link.href = brand.favicon_url;
    }
    if (brand.app_name) document.title = (document.title.split('|')[0].trim() + ' | ' + brand.app_name);
  }

  /**
   * Try to fetch branding from URIP. Falls back silently — branding is
   * decorative, never load-bearing.
   */
  async function loadTenantBranding() {
    try {
      // Try the URIP branding endpoint first (integrated mode)
      var uripBase = window.URIP_API_BASE || (window.location.hostname === 'localhost' ? 'http://localhost:8000/api' : null);
      if (!uripBase) return;
      var token = localStorage.getItem('urip_token');
      if (!token) return;
      var resp = await fetch(uripBase + '/tenant/branding', {
        headers: { 'Authorization': 'Bearer ' + token }
      });
      if (!resp.ok) return;
      var brand = await resp.json();
      COMPLIANCE.branding = brand;
      window.COMPLIANCE = COMPLIANCE;
      applyVars(brand);
      document.dispatchEvent(new CustomEvent('compliance:branding-applied'));
    } catch (_) {
      // Silent — branding is best-effort
    }
  }

  COMPLIANCE.loadTenantBranding = loadTenantBranding;
  window.COMPLIANCE = COMPLIANCE;

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', loadTenantBranding);
  } else {
    loadTenantBranding();
  }
})();
