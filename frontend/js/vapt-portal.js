/**
 * VAPT Vendor Portal — UI helpers (session, header, formatting).
 *
 * Exposed:
 *   VaptPortal.requireSession()  → redirect to login if no JWT
 *   VaptPortal.saveSession(resp) → persist JWT + vendor info from accept response
 *   VaptPortal.clearSession()    → wipe local state and bounce to login
 *   VaptPortal.setupChrome()     → wire vendor name + logout button
 *   VaptPortal.fmtDate(iso)      → "Apr 12, 14:32"
 */
(function () {
  'use strict';

  var SESSION_KEY = 'urip_vapt_vendor_session';

  function getSession() {
    try {
      var raw = localStorage.getItem(SESSION_KEY);
      if (!raw) return null;
      return JSON.parse(raw);
    } catch (_e) {
      return null;
    }
  }

  function saveSession(resp) {
    if (!resp || !resp.vapt_vendor_jwt) return;
    var payload = {
      jwt: resp.vapt_vendor_jwt,
      vendor: resp.vendor || null,
      expires_at: resp.expires_at || null,
    };
    localStorage.setItem(SESSION_KEY, JSON.stringify(payload));
  }

  function clearSession() {
    try { localStorage.removeItem(SESSION_KEY); } catch (_e) {}
    window.location.href = 'vapt-portal-login.html';
  }

  function requireSession() {
    var s = getSession();
    if (!s || !s.jwt) {
      window.location.href = 'vapt-portal-login.html';
    }
    return s;
  }

  function setupChrome() {
    var s = getSession();
    var nameEl = document.getElementById('vendorName');
    if (nameEl && s && s.vendor) {
      nameEl.textContent = s.vendor.name || s.vendor.contact_email || 'Vendor';
    }
    var logoutBtn = document.getElementById('logoutBtn');
    if (logoutBtn) {
      logoutBtn.addEventListener('click', clearSession);
    }
  }

  function fmtDate(iso) {
    if (!iso) return '—';
    try {
      var d = new Date(iso);
      if (isNaN(d.getTime())) return iso;
      var opts = {
        month: 'short', day: 'numeric',
        hour: '2-digit', minute: '2-digit',
      };
      return d.toLocaleString(undefined, opts);
    } catch (_e) {
      return iso;
    }
  }

  window.VaptPortal = {
    SESSION_KEY: SESSION_KEY,
    getSession: getSession,
    saveSession: saveSession,
    clearSession: clearSession,
    requireSession: requireSession,
    setupChrome: setupChrome,
    fmtDate: fmtDate,
  };
})();
