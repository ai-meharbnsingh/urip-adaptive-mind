/**
 * ADVERB COMPLIANCE — Auth utilities
 *
 * In INTEGRATED mode the JWT comes from URIP — this script verifies it exists
 * and decodes claims for display. In STANDALONE mode the token would come from
 * a compliance-specific login (out of scope for this milestone — flagged TODO).
 *
 * Auditor portal handles its own token via auditor_invitations/accept; not
 * managed here.
 */
(function () {
  'use strict';

  function getToken() {
    return (window.COMPLIANCE && window.COMPLIANCE.getToken && window.COMPLIANCE.getToken()) ||
           localStorage.getItem('compliance_token') ||
           localStorage.getItem('urip_token') || null;
  }

  /**
   * Decode JWT payload (no signature check — display only).
   */
  function decodeClaims(token) {
    if (!token) return null;
    try {
      var parts = token.split('.');
      if (parts.length !== 3) return null;
      var payload = parts[1].replace(/-/g, '+').replace(/_/g, '/');
      while (payload.length % 4) payload += '=';
      return JSON.parse(atob(payload));
    } catch (_) { return null; }
  }

  function getCurrentUser() {
    // Try cached URIP user first
    var raw = localStorage.getItem('urip_user') || localStorage.getItem('compliance_user');
    if (raw) { try { return JSON.parse(raw); } catch (_) {} }
    // Fallback: decode from JWT
    var claims = decodeClaims(getToken());
    if (!claims) return null;
    return {
      sub: claims.sub,
      email: claims.email || claims.sub,
      full_name: claims.full_name || claims.name || claims.email || claims.sub,
      role: claims.role || (claims.is_super_admin ? 'super_admin' : 'member'),
      tenant_id: claims.tenant_id,
      is_compliance_admin: !!claims.is_compliance_admin,
      is_super_admin: !!claims.is_super_admin,
    };
  }

  /**
   * Guard: redirect to login if no token. We treat the URIP login page as the
   * shared entry point in INTEGRATED mode (../frontend/index.html), and the
   * auditor portal at auditor_portal.html for the auditor flow.
   *
   * For STANDALONE mode, this would point to a compliance login page (TODO).
   */
  function checkAuth(opts) {
    opts = opts || {};
    var token = getToken();
    if (!token) {
      // If we're already on the auditor portal, do nothing — that page has
      // its own login.
      if (window.location.pathname.indexOf('auditor_portal') > -1) return;

      // INTEGRATED mode: bounce to URIP login (relative path; falls back to
      // a placeholder login page if running standalone)
      var loginUrl = '../frontend/index.html';
      // STANDALONE TODO: build a dedicated compliance login.
      if (opts.allowStandalone === false || !document.querySelector('html')) {
        window.location.href = loginUrl;
        return;
      }
      // Render a minimal "please sign in" fallback inline so the user isn't
      // dropped on a blank screen if they hit a compliance page directly.
      renderSignInFallback();
    }
  }

  function renderSignInFallback() {
    var existing = document.getElementById('compliance-signin-fallback');
    if (existing) return;
    var bar = document.createElement('div');
    bar.id = 'compliance-signin-fallback';
    bar.style.cssText =
      'position:fixed;top:0;left:0;right:0;background:#0D1B2A;color:#fff;' +
      'padding:14px 20px;z-index:9999;display:flex;align-items:center;' +
      'gap:14px;font-family:Inter,sans-serif;font-size:14px;box-shadow:0 4px 12px rgba(0,0,0,0.3)';

    var msg = document.createElement('span');
    msg.textContent = 'You are viewing a preview without authentication. API calls will fail until a JWT is set.';
    msg.style.cssText = 'flex:1';

    var input = document.createElement('input');
    input.type = 'text';
    input.placeholder = 'Paste JWT token here…';
    input.style.cssText =
      'flex:2;padding:8px 12px;border-radius:6px;border:1px solid rgba(255,255,255,0.2);' +
      'background:rgba(255,255,255,0.08);color:#fff;font-size:13px';

    var btn = document.createElement('button');
    btn.textContent = 'Set Token';
    btn.style.cssText =
      'padding:8px 16px;background:#1ABC9C;color:#fff;border:0;' +
      'border-radius:6px;cursor:pointer;font-weight:600;font-size:13px';
    btn.addEventListener('click', function () {
      var t = input.value.trim();
      if (!t) return;
      localStorage.setItem('compliance_token', t);
      window.location.reload();
    });

    bar.appendChild(msg);
    bar.appendChild(input);
    bar.appendChild(btn);
    document.body.appendChild(bar);
    document.body.style.paddingTop = '60px';
  }

  function logout() {
    localStorage.removeItem('compliance_token');
    localStorage.removeItem('urip_token');
    localStorage.removeItem('compliance_user');
    localStorage.removeItem('urip_user');
    sessionStorage.removeItem('auditor_jwt');
    window.location.href = '../frontend/index.html';
  }

  window.checkAuth = checkAuth;
  window.getCurrentUser = getCurrentUser;
  window.logout = logout;
})();
